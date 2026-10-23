"""The local server behind ``regwatch ui``.

The server is the standard library's ``ThreadingHTTPServer``, bound to
``127.0.0.1`` only. It serves the built web app from ``regwatch/web/`` and the
JSON interface in ``regwatch.webapi``, and nothing else.

``regwatch ui`` puts a random launch token in the address it opens. The token
works once: the first request that presents it in the query gets a separate,
new session value in an ``HttpOnly``, ``SameSite=Strict`` cookie and a redirect
to the same address without the token, and the launch token is spent. Later
requests must carry the session cookie, so the printed address, and the copy in
the browser's command line, is worthless once the browser has opened it. A request is
refused when its ``Host`` is not this server's own address, when it changes
state and its ``Origin`` is not this server's own origin, or when it has no
valid token. Files are served only from inside the build folder, after symbolic
links are resolved, with a content security policy that allows no other origin.
A connection that makes no progress for 30 seconds is closed, and at most 32
connections are handled at once, so idle connections cannot exhaust the handler
threads. Errors are short JSON messages that hold no file contents. Requests are not
logged, because the first one carries the token in its query.
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import re
import secrets
import threading
from http import HTTPStatus
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit

from regwatch.config import ConfigError
from regwatch.focus import FocusError
from regwatch.register import RegisterError
from regwatch.settings import SettingsError
from regwatch.state import StateError
from regwatch.webapi import Api, ApiError, Download

__all__ = ["LocalServer", "ServerError", "content_security_policy", "web_root"]

HOST = "127.0.0.1"
MAX_BODY_BYTES = 65_536
# A connection that sends nothing, or sends a request a byte at a time, is closed
# after this long without progress, so it cannot hold a handler thread for ever.
HANDLER_TIMEOUT_SECONDS = 30
# At most this many connections are handled at once; any more are closed at once.
# One browser tab opens a handful, so this leaves room for several tabs while a
# flood of idle connections from another local program cannot exhaust threads.
MAX_CONNECTIONS = 32
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    # Next.js fetches a page's data as a .txt file and reads it as text/plain.
    ".txt": "text/plain; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".map": "application/json",
}
_INLINE_SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.DOTALL)


class ServerError(Exception):
    """The server cannot start: the web app is missing or the port is taken."""


def web_root() -> Path:
    """The built web app shipped in the package, read through importlib.resources."""
    root = resources.files("regwatch").joinpath("web")
    if not isinstance(root, Path) or not (root / "index.html").is_file():
        raise ServerError(
            "the web app is not built into this installation; "
            "run scripts/build-web.sh from a checkout"
        )
    return root


def content_security_policy(script_hashes: list[str]) -> str:
    """The policy for every response: this origin only, and the page's own inline scripts."""
    scripts = " ".join(["'self'", *(f"'sha256-{h}'" for h in script_hashes)])
    return "; ".join(
        [
            "default-src 'none'",
            f"script-src {scripts}",
            "style-src 'self'",
            "img-src 'self' data:",
            "font-src 'self'",
            "connect-src 'self'",
            "manifest-src 'self'",
            "base-uri 'none'",
            "form-action 'self'",
            "frame-ancestors 'none'",
        ]
    )


def _script_hashes(html: bytes) -> list[str]:
    text = html.decode("utf-8", errors="replace")
    return [
        base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode("ascii")
        for body in _INLINE_SCRIPT.findall(text)
        if body
    ]


class LocalServer(http.server.ThreadingHTTPServer):
    """The ``regwatch ui`` server: one project, one token, loopback only."""

    daemon_threads = True

    def __init__(self, api: Api, root: Path, port: int = 0, token: str | None = None) -> None:
        try:
            super().__init__((HOST, port), _Handler)
        except OSError as exc:
            raise ServerError(f"cannot listen on {HOST}:{port}: {exc.strerror or exc}") from exc
        self.api = api
        self.root = root.resolve()
        self.port: int = self.server_address[1]
        self.token = token or secrets.token_urlsafe(32)
        self.cookie_name = f"regwatch-{self.port}"
        self.hosts = {f"{HOST}:{self.port}", f"localhost:{self.port}"}
        self.origins = {f"http://{host}" for host in self.hosts}

        # The session value the launch token was traded for; None until then.
        self.session: str | None = None
        self._exchange_lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(MAX_CONNECTIONS)

    def process_request(self, request: Any, client_address: Any) -> None:
        """Hand the connection to a thread, or close it when every slot is taken."""
        if not self._slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        """Handle one connection in its thread and free its slot when done."""
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()

    @property
    def url(self) -> str:
        """The address to open, with the launch token. Printed once by ``regwatch ui``."""
        return f"http://{HOST}:{self.port}/?token={self.token}"

    @property
    def launch_spent(self) -> bool:
        """True once the launch token has been traded for a session."""
        return self.session is not None

    def exchange(self, value: str | None) -> str | None:
        """Trade the launch token for a new session value, once.

        Returns the session value when ``value`` is the unspent launch token, and
        None otherwise, including for every later presentation of the same token.
        """
        with self._exchange_lock:
            if self.session is not None or not _same(value, self.token):
                return None
            self.session = secrets.token_urlsafe(32)
            return self.session

    def session_matches(self, value: str | None) -> bool:
        """True when ``value`` is this server's session value."""
        session = self.session
        return session is not None and _same(value, session)


def _same(value: str | None, expected: str) -> bool:
    return value is not None and secrets.compare_digest(
        value.encode("utf-8", errors="replace"), expected.encode("utf-8")
    )


class _Handler(http.server.BaseHTTPRequestHandler):
    server: LocalServer
    server_version = "regwatch"
    sys_version = ""
    # Applied to the connection's socket before the request is read.
    timeout = HANDLER_TIMEOUT_SECONDS

    def log_message(self, format: str, *args: Any) -> None:
        """Log nothing: the first request carries the token in its query."""

    # --- responses -------------------------------------------------------------

    def _send(
        self,
        status: int,
        body: bytes,
        content_type: str,
        headers: dict[str, str] | None = None,
        script_hashes: list[str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", content_security_policy(script_hashes or []))
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8", {"Cache-Control": "no-store"})

    def _error(self, status: int, message: str) -> None:
        self._json(status, {"error": message})

    # --- checks ----------------------------------------------------------------

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").strip().lower()
        return host in self.server.hosts

    def _origin_ok(self) -> bool:
        origin = (self.headers.get("Origin") or "").strip().lower()
        return origin in self.server.origins

    def _cookie_token(self) -> str | None:
        for part in (self.headers.get("Cookie") or "").split(";"):
            name, _, value = part.strip().partition("=")
            if name == self.server.cookie_name:
                return value
        return None

    def _guard(self, query: dict[str, str]) -> bool:
        """Apply the host, origin and token checks. Sends the refusal and returns False."""
        if not self._host_ok():
            self._error(HTTPStatus.FORBIDDEN, "this server answers only to its own address")
            return False
        if self.command == "POST" and not self._origin_ok():
            self._error(HTTPStatus.FORBIDDEN, "a change must come from this server's own pages")
            return False
        if self.server.session_matches(self._cookie_token()):
            if self.command == "GET" and "token" in query:
                # Already signed in: only take the token out of the address.
                self._redirect_clean(None)
                return False
            return True
        if self.command == "GET" and "token" in query:
            session = self.server.exchange(query.get("token"))
            if session is not None:
                self._redirect_clean(session)
                return False
            if self.server.launch_spent:
                self._error(
                    HTTPStatus.FORBIDDEN,
                    "this address has been used already and works only once; "
                    "stop 'regwatch ui' and start it again for a new one",
                )
                return False
        self._error(
            HTTPStatus.FORBIDDEN,
            "open the address that 'regwatch ui' printed; this request has no valid token",
        )
        return False

    def _redirect_clean(self, session: str | None) -> None:
        """Send the browser to the same address without the token, setting the session cookie."""
        parts = urlsplit(self.path)
        rest = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "token"]
        # One leading slash only, so the target cannot read as another host ("//host").
        clean = "/" + quote(unquote(parts.path).lstrip("/\\"), safe="/")
        if rest:
            clean += "?" + urlencode(rest)
        headers = {"Location": clean, "Cache-Control": "no-store"}
        if session is not None:
            headers["Set-Cookie"] = (
                f"{self.server.cookie_name}={session}; Path=/; HttpOnly; SameSite=Strict"
            )
        self._send(HTTPStatus.SEE_OTHER, b"", "text/plain; charset=utf-8", headers)

    # --- methods ---------------------------------------------------------------

    def do_GET(self) -> None:
        self._dispatch()

    def do_POST(self) -> None:
        self._dispatch()

    def _dispatch(self) -> None:
        parts = urlsplit(self.path)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        if not self._guard(query):
            return
        if parts.path.startswith("/api/"):
            self._api(parts.path, query)
        elif self.command == "GET":
            self._static(parts.path)
        else:
            self._error(HTTPStatus.METHOD_NOT_ALLOWED, "method not allowed")

    def _body(self) -> dict[str, Any] | None:
        if self.command != "POST":
            return {}
        content_type = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if content_type != "application/json":
            self._error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "send JSON")
            return None
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            length = -1
        if not 0 <= length <= MAX_BODY_BYTES:
            self._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "the request body is too large")
            return None
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, RecursionError):
            data = None
        if not isinstance(data, dict):
            self._error(HTTPStatus.BAD_REQUEST, "the request body must be a JSON object")
            return None
        return data

    def _api(self, path: str, query: dict[str, str]) -> None:
        body = self._body()
        if body is None:
            return
        try:
            status, payload = self.server.api.handle(self.command, path, query, body)
        except ApiError as exc:
            self._error(exc.status, exc.message)
            return
        except RegisterError:
            self._error(422, "the register is invalid; run 'regwatch validate' for the list")
            return
        except (ConfigError, FocusError):
            self._error(500, "the configuration could not be read; run 'regwatch config show'")
            return
        except SettingsError:
            self._error(409, "the setting could not be saved; change it in regwatch.toml by hand")
            return
        except (StateError, OSError):
            self._error(500, "a file could not be read or written")
            return
        except Exception:
            # Whatever failed, the message could hold file contents, so it is not sent.
            self._error(500, "the request failed")
            return
        if isinstance(payload, Download):
            name = re.sub(r"[^A-Za-z0-9._-]", "_", payload.filename)
            self._send(
                status,
                payload.data,
                payload.content_type,
                {
                    "Cache-Control": "no-store",
                    "Content-Disposition": f'attachment; filename="{name}"',
                },
            )
            return
        self._json(status, payload)

    # --- files -----------------------------------------------------------------

    def _resolve(self, url_path: str) -> Path | None:
        """The file inside the build folder that ``url_path`` names, or None.

        A segment that is empty, ``.``, ``..`` or hidden is refused before any
        lookup, and the resolved file must still lie inside the build folder, so a
        symbolic link that points out of it is refused too.
        """
        decoded = unquote(url_path)
        if "\x00" in decoded or "\\" in decoded:
            return None
        segments = [s for s in decoded.split("/") if s]
        if any(s in (".", "..") or s.startswith(".") for s in segments):
            return None
        root = self.server.root
        base = root.joinpath(*segments)
        candidates = [base / "index.html"] if base.is_dir() else [base]
        if segments and not base.suffix:
            candidates += [base / "index.html", base.with_name(base.name + ".html")]
        for candidate in candidates:
            try:
                resolved = candidate.resolve(strict=True)
            except (OSError, RuntimeError):
                continue
            if resolved.is_relative_to(root) and resolved.is_file():
                return resolved
        return None

    def _static(self, url_path: str) -> None:
        found = self._resolve(url_path)
        status = HTTPStatus.OK
        if found is None:
            missing = self._resolve("/404.html")
            if missing is None:
                self._error(HTTPStatus.NOT_FOUND, "not found")
                return
            found, status = missing, HTTPStatus.NOT_FOUND
        try:
            data = found.read_bytes()
        except OSError:
            self._error(HTTPStatus.NOT_FOUND, "not found")
            return
        content_type = CONTENT_TYPES.get(found.suffix, "application/octet-stream")
        hashes = _script_hashes(data) if found.suffix == ".html" else []
        self._send(status, data, content_type, {"Cache-Control": "no-cache"}, hashes)
