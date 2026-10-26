"""The one network client.

Every byte regwatch reads from outside the register goes through a Fetcher.
The shipped SafeFetcher is deliberately small and enforces these rules:

- only the ``https`` and ``file`` URL schemes are accepted;
- ``file`` URLs are refused unless they lie under a configured root directory,
  and only regular files are read (never a FIFO, a device or a directory); the
  file is opened without following a link and must be the very file that was
  checked, so a swap between the check and the open is refused;
- a host that resolves to a loopback, link-local, private, unique local,
  reserved, multicast or otherwise non-global address is refused, for the first
  request and for every redirect, unless ``allow_private_hosts`` is set; an IPv6
  address that embeds an IPv4 address is judged by the IPv4 address;
- the connection is made to the address that was vetted, not to a second
  lookup of the name, so a DNS answer that changes between the check and the
  connection cannot redirect the request;
- certificates are always verified against the original host name; an
  internationalised host is sent in its ``xn--`` form and a non-ASCII path or
  query is percent-encoded;
- a redirect may only lead to another ``https`` URL, at most 5 times, and the
  redirects share one total deadline with the request itself;
- every request has a per-operation timeout, a total deadline enforced by
  checking the clock between reads, by a watchdog that closes the socket and by
  running the name lookup in a worker thread that is abandoned at the deadline,
  and a hard limit on the number of bytes read;
- URLs that carry credentials, or contain control characters, are refused;
- proxy environment variables are ignored, because a proxy would resolve the
  host itself and defeat the address check;
- no shell, subprocess or external program is ever started;
- a key for a source that needs one (a ``Credential``) is sent only over
  ``https``, only to the host and port of the URL it was given for, and only in
  the query parameter or header its source names; a redirect to another host
  drops it, and it is removed from every error message;
- ``post_json`` sends a JSON body with the same checks, limits and deadline. It
  follows no redirect, and it speaks plain ``http`` only to a loopback address
  written as an IP literal, never with a key, and only with ``allow_private_hosts``
  set or to the one ``loopback_post_url`` the client was made with: that is how a
  local model server on ``127.0.0.1`` is reached without opening every fetch.

Tests and embedders can supply any object with a matching ``fetch`` method, and
``SafeFetcher`` takes a resolver, a connector and a TLS wrapper so that it can be
tested without a network.
"""

from __future__ import annotations

import contextlib
import html
import http.client
import ipaddress
import json
import os
import re
import socket
import ssl
import stat
import threading
import time
import unicodedata
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.parse import quote, urljoin, urlsplit

from regwatch.sanitize import clean_text

__all__ = [
    "ALLOWED_SCHEMES",
    "CHUNK_BYTES",
    "MAX_POST_BYTES",
    "MAX_REDIRECTS",
    "Credential",
    "FetchError",
    "Fetcher",
    "SafeFetcher",
    "check_url",
    "is_public_address",
]

ALLOWED_SCHEMES = frozenset({"https", "file"})
MAX_REDIRECTS = 5
CHUNK_BYTES = 16384
# The largest JSON body ``post_json`` sends.
MAX_POST_BYTES = 1_000_000
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
# The three dots (ideographic full stop, fullwidth full stop, halfwidth ideographic full
# stop) that the idna codec reads as a label separator.
_IDEOGRAPHIC_DOTS = {0x3002: ".", 0xFF0E: ".", 0xFF61: "."}

Resolver = Callable[[str, int], list[str]]
Connector = Callable[[str, int, float], socket.socket]
Wrapper = Callable[[socket.socket, str], socket.socket]


MAX_MESSAGE_CHARACTERS = 1000
MAX_ERROR_BODY_BYTES = 16384


class FetchError(Exception):
    """A fetch was refused or failed. The message is safe to show to the user.

    The message is cleaned when the error is created: control characters (and so
    terminal escape sequences and line breaks) and invisible format characters are
    removed, and a very long message is cut. A server controls part of some
    messages, for example the status line it sent back, so the cleaning cannot be
    left to the code that prints the error.

    ``redact``, when given, removes a secret from the message before it is cleaned
    and cut, and again after cleaning, so neither a key cut in half at the length
    limit nor a key a server split with an invisible character survives. The
    uncleaned message is kept in ``raw`` so a caller that learns the secret later
    can rebuild the error the same way; it is never shown.

    ``status`` is the HTTP status the server answered with, when it answered with
    one that is not a success, and ``body`` is the start of the error body a POST
    received (at most ``MAX_ERROR_BODY_BYTES``), with the secret removed by
    ``redact``. The body is not cleaned and is never shown as it is: a caller reads
    the provider's own message out of it and cleans that.
    """

    def __init__(
        self,
        message: object = "",
        redact: Callable[[str], str] | None = None,
        *,
        status: int | None = None,
        body: str = "",
    ) -> None:
        text = str(message)
        if redact is not None:
            text = redact(clean_text(redact(text)))
            body = redact(body)
        self.raw = text
        self.status = status
        self.body = body
        super().__init__(clean_text(text, MAX_MESSAGE_CHARACTERS))


_CREDENTIAL_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_CREDENTIAL_SCHEME = re.compile(r"^[A-Za-z]{0,20}$")
_RESERVED_HEADERS = frozenset(
    {"host", "user-agent", "accept", "connection", "content-length", "content-type"}
)
MAX_KEY_CHARACTERS = 4096
REDACTED = "[key]"


@dataclass(frozen=True)
class Credential:
    """A key and where it goes in the request: a query parameter or a header.

    The key is hidden from ``repr``, and a value that could not be sent safely
    (empty, too long, or holding a space, a control character, a quote or a
    backslash) is refused without being repeated in the message. ``scheme`` is a
    word sent before a header key, such as ``Bearer`` in an ``Authorization``
    header; it is letters only.
    """

    placement: str
    name: str
    value: str = field(repr=False)
    scheme: str = ""

    def __post_init__(self) -> None:
        if self.placement not in ("query", "header"):
            raise ValueError("a key goes in a 'query' parameter or a 'header'")
        if not _CREDENTIAL_NAME.fullmatch(self.name):
            raise ValueError("a key parameter or header name is 1 to 64 letters, digits, - or _")
        if self.placement == "header" and self.name.lower() in _RESERVED_HEADERS:
            raise ValueError(f"the key cannot be sent in the {self.name} header")
        if not _CREDENTIAL_SCHEME.fullmatch(self.scheme) or (
            self.scheme and self.placement != "header"
        ):
            raise ValueError("a key scheme is up to 20 letters, and only for a header key")
        value = self.value
        if (
            not value
            or len(value) > MAX_KEY_CHARACTERS
            or any(not 0x21 <= ord(ch) <= 0x7E or ch in "\"'\\" for ch in value)
        ):
            raise ValueError(
                "the key must be 1 to 4096 printable ASCII characters without spaces, quotes "
                "or backslashes"
            )

    @property
    def header_value(self) -> str:
        """The value of the header that carries the key, with its scheme word when it has one."""
        return f"{self.scheme} {self.value}" if self.scheme else self.value

    @classmethod
    def from_auth(cls, auth: str, value: str) -> Credential:
        """Build a credential from a sources file ``auth`` value such as ``query:api_key``."""
        placement, _, name = auth.partition(":")
        return cls(placement, name, value)

    def redact(self, text: str) -> str:
        """``text`` with the key replaced by ``[key]``.

        The key is replaced as written, percent-encoded (as it is sent in a query),
        HTML-escaped and JSON-escaped, the forms in which a response or an error
        message usually echoes it. Longer forms are replaced first.
        """
        forms = {
            self.value,
            quote(self.value, safe=""),
            quote(self.value),
            html.escape(self.value),
            self.value.replace("/", "\\/"),
        }
        for form in sorted(forms, key=len, reverse=True):
            text = text.replace(form, REDACTED)
        return text


class Fetcher(Protocol):
    """Anything that can turn a URL into text."""

    def fetch(self, url: str, *, credential: Credential | None = None) -> str:
        """Return the decoded body for ``url`` or raise FetchError.

        ``credential`` is given only for a source that needs a key.
        """
        ...


def check_url(url: str) -> str:
    """Return the lower-cased scheme of ``url`` or raise FetchError if it is not allowed."""
    if any(ord(char) < 0x21 or 0x7F <= ord(char) <= 0x9F for char in url):
        raise FetchError("URL contains a space or a control character")
    try:
        parts = urlsplit(url)
        _ = parts.port  # reading the port validates it
    except ValueError as exc:
        raise FetchError(f"invalid URL: {exc}") from exc
    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise FetchError(f"URL scheme '{scheme or '(none)'}' is not allowed; use https or file")
    if "@" in parts.netloc:
        raise FetchError("URLs that carry credentials are not allowed")
    if scheme == "https" and not parts.hostname:
        raise FetchError("https URL has no host")
    if scheme == "file" and parts.netloc not in ("", "localhost"):
        raise FetchError("file URLs must not name a remote host")
    return scheme


_V6_REFUSED = tuple(
    ipaddress.ip_network(network)
    for network in (
        "::/8",  # IPv4-compatible and SIIT addresses, the unspecified address and ::1
        "fec0::/10",  # deprecated site-local addresses
        "64:ff9b::/32",  # NAT64 prefix: only the /96 below is allowed, judged by its IPv4
    )
)
_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_ISATAP_IDS = (0x00005EFE, 0x01005EFE, 0x02005EFE, 0x03005EFE)
"""The high half of an ISATAP interface identifier, with the universal and group bits."""


def _embedded_ipv4(ip: ipaddress.IPv6Address) -> list[ipaddress.IPv4Address] | None:
    """Every IPv4 address a translation or tunnel address carries, or None for other addresses.

    An address can carry more than one form at once (a 6to4 prefix with an ISATAP
    interface identifier), so each form is collected and all of them are judged.
    """
    found: list[ipaddress.IPv4Address] = []
    if ip in _NAT64:
        found.append(ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF))
    if ip.sixtofour is not None:
        found.append(ip.sixtofour)
    if ip.teredo is not None:
        found.extend(ip.teredo)
    if (int(ip) >> 32) & 0xFFFFFFFF in _ISATAP_IDS:
        found.append(ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF))
    return found or None


def is_public_address(address: str) -> bool:
    """True when ``address`` is a globally routable unicast IP address.

    Loopback, link-local, private (including unique local), shared, reserved,
    multicast and unspecified addresses are all not public. An IPv6 address that
    embeds an IPv4 address (an IPv4-mapped address, a NAT64 address in
    ``64:ff9b::/96``, a 6to4 address in ``2002::/16`` or a Teredo address in
    ``2001::/32``) or an ISATAP interface identifier (``0:5efe``, ``100:5efe``,
    ``200:5efe`` or ``300:5efe``, the universal and group bits each set or clear) is
    judged by the IPv4 addresses it carries, and every one of them must be public
    (a 6to4 prefix with an ISATAP identifier carries two). The whole range ``::/8``
    (which holds the IPv4-compatible, SIIT and loopback addresses), the deprecated
    site-local range ``fec0::/10`` and the NAT64 prefix ``64:ff9b::/32`` apart from
    its ``/96`` are refused outright.
    """
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        else:
            if ip not in _NAT64 and any(ip in network for network in _V6_REFUSED):
                return False
            embedded = _embedded_ipv4(ip)
            if embedded is not None:
                return all(is_public_address(str(v4)) for v4 in embedded)
    return ip.is_global and not ip.is_multicast


def _default_resolver(host: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(str(info[4][0]) for info in infos))


def _default_connector(address: str, port: int, timeout: float) -> socket.socket:
    return socket.create_connection((address, port), timeout)


class SafeFetcher:
    """Fetch https and file URLs with the limits described in the module docstring."""

    def __init__(
        self,
        timeout_seconds: float,
        max_bytes: int,
        user_agent: str,
        *,
        total_timeout_seconds: float = 60.0,
        allow_private_hosts: bool = False,
        allowed_file_roots: Iterable[Path] = (),
        loopback_post_url: str | None = None,
        resolver: Resolver | None = None,
        connector: Connector | None = None,
        wrapper: Wrapper | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes
        self.user_agent = user_agent
        self.total_timeout_seconds = total_timeout_seconds
        self.allow_private_hosts = allow_private_hosts
        # The one plain http address on this machine ``post_json`` may reach without
        # ``allow_private_hosts``: a local model server. Every other fetch is unchanged.
        if loopback_post_url is not None and not _is_loopback_post_url(loopback_post_url):
            raise ValueError("the loopback address must be plain http to 127.0.0.1 or ::1")
        self.loopback_post_url = loopback_post_url
        self.allowed_file_roots = tuple(Path(root).resolve() for root in allowed_file_roots)
        self._resolver = resolver or _default_resolver
        self._connector = connector or _default_connector
        self._wrapper = wrapper or _default_wrapper

    def fetch(self, url: str, *, credential: Credential | None = None) -> str:
        """Return the body of ``url`` decoded as UTF-8 with undecodable bytes replaced.

        With a ``credential`` the URL must be ``https``. The key is added to the
        first request and to a redirect that stays on the same host and port, and
        every error raised is cleaned of it, with its cause dropped.
        """
        if credential is None:
            scheme = check_url(url)
            data = self._read_file(url) if scheme == "file" else self._read_https(url)
            return data.decode("utf-8", errors="replace")
        try:
            if check_url(url) != "https":
                raise FetchError("a key is sent only over https; refused")
            data = self._read_https(url, credential)
        except FetchError as exc:
            raise FetchError(exc.raw, redact=credential.redact) from None
        # A server may echo the key back ("invalid api_key ..."); it must not reach
        # a snapshot, a hash or a printed line.
        return credential.redact(data.decode("utf-8", errors="replace"))

    def post_json(
        self,
        url: str,
        payload: Mapping[str, object],
        *,
        credential: Credential | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> str:
        """Send ``payload`` as a JSON body to ``url`` and return the response body.

        The address checks, the size limit and the deadline are the ones ``fetch``
        applies. No redirect is followed: a POST that is answered with one is an
        error. ``url`` is ``https``, or plain ``http`` to a loopback address written
        as an IP literal (``127.0.0.1`` or ``::1``) when no key is sent and either
        ``allow_private_hosts`` is set or ``url`` is exactly ``loopback_post_url``.
        ``headers`` are extra headers that carry no secret; they cannot replace the
        headers the client sets. Every error raised with a
        ``credential`` is cleaned of the key, with its cause dropped, and a body
        that echoes the key has it replaced.
        """
        try:
            body = json.dumps(payload, ensure_ascii=True).encode("ascii")
        except (TypeError, ValueError) as exc:
            raise FetchError("the request body cannot be written as JSON") from exc
        if len(body) > MAX_POST_BYTES:
            raise FetchError(f"the request body is larger than {MAX_POST_BYTES} bytes")
        extra = _check_headers(headers or {})
        try:
            tls = self._post_scheme(url, credential) == "https"
            deadline = time.monotonic() + self.total_timeout_seconds
            data, location = self._request(
                url,
                deadline,
                credential,
                method="POST",
                body=body,
                extra=extra,
                tls=tls,
                # Plain http was allowed above only to a loopback IP literal.
                loopback=not tls,
            )
            if location is not None:
                raise FetchError("the server answered with a redirect; a POST is not redirected")
        except FetchError as exc:
            if credential is None:
                raise
            raise FetchError(
                exc.raw, redact=credential.redact, status=exc.status, body=exc.body
            ) from None
        text = data.decode("utf-8", errors="replace")
        return credential.redact(text) if credential is not None else text

    def _post_scheme(self, url: str, credential: Credential | None) -> str:
        """``https`` or ``http`` for a POST to ``url``, or a FetchError saying why neither."""
        if any(ord(char) < 0x21 or 0x7F <= ord(char) <= 0x9F for char in url):
            raise FetchError("URL contains a space or a control character")
        try:
            parts = urlsplit(url)
            _ = parts.port
        except ValueError as exc:
            raise FetchError(f"invalid URL: {exc}") from exc
        scheme = parts.scheme.lower()
        if "@" in parts.netloc:
            raise FetchError("URLs that carry credentials are not allowed")
        if scheme == "https" and parts.hostname:
            return "https"
        if scheme != "http":
            raise FetchError("a request with a body is sent only over https")
        if credential is not None:
            raise FetchError("a key is sent only over https; refused")
        if not _is_loopback_literal(parts.hostname or ""):
            raise FetchError("plain http is allowed only to 127.0.0.1 or ::1")
        if not (self.allow_private_hosts or url == self.loopback_post_url):
            raise FetchError(
                "a request to this machine needs allow_private_hosts; set it under [fetch]"
            )
        return "http"

    def _limit(self, data: bytes) -> bytes:
        if len(data) > self.max_bytes:
            raise FetchError(f"response is larger than the limit of {self.max_bytes} bytes")
        return data

    # --- file: URLs ---------------------------------------------------------

    def _read_file(self, url: str) -> bytes:
        if not self.allowed_file_roots:
            raise FetchError(
                "file URLs are disabled; list directories in allowed_file_roots to enable them"
            )
        try:
            path = Path(urllib.request.url2pathname(urlsplit(url).path)).resolve(strict=True)
        except (OSError, ValueError, RuntimeError) as exc:
            raise FetchError(f"cannot read file: {getattr(exc, 'strerror', None) or exc}") from exc
        if not any(path.is_relative_to(root) for root in self.allowed_file_roots):
            raise FetchError("file is outside the allowed_file_roots directories")
        descriptor = -1
        try:
            vetted = os.stat(path)
            # O_NONBLOCK so that opening a FIFO cannot block; the type is checked next.
            # O_NOFOLLOW refuses a file that was swapped for a link after the check.
            descriptor = os.open(
                path,
                os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0),
            )
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != (vetted.st_dev, vetted.st_ino):
                raise FetchError("file changed while it was being opened; refused")
            if not stat.S_ISREG(opened.st_mode):
                raise FetchError("only regular files can be read")
            with os.fdopen(descriptor, "rb", closefd=False) as handle:
                return self._limit(handle.read(self.max_bytes + 1))
        except (OSError, ValueError) as exc:
            raise FetchError(f"cannot read file: {getattr(exc, 'strerror', None) or exc}") from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    # --- https: URLs --------------------------------------------------------

    def _resolve(self, host: str, port: int, deadline: float) -> list[str]:
        """Run the resolver in a worker thread and give up when the total deadline passes.

        The operating system's name lookup takes no timeout, so a slow DNS server
        would otherwise hold the whole fetch past the deadline. The worker is a
        daemon thread, so a lookup that never returns cannot keep the program alive.
        """
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise self._deadline_error()
        outcome: dict[str, object] = {}
        finished = threading.Event()

        def work() -> None:
            try:
                outcome["addresses"] = self._resolver(host, port)
            except BaseException as exc:  # handed to the caller below
                outcome["error"] = exc
            finally:
                finished.set()

        threading.Thread(target=work, daemon=True).start()
        if not finished.wait(remaining):
            raise self._deadline_error()
        error = outcome.get("error")
        if isinstance(error, BaseException):
            raise error
        addresses = outcome.get("addresses")
        return list(addresses) if isinstance(addresses, list) else []

    def _vet(self, host: str, port: int, deadline: float) -> list[str]:
        """Resolve ``host`` and return the addresses it is allowed to connect to."""
        try:
            addresses = [host] if _is_ip_literal(host) else self._resolve(host, port, deadline)
        except (OSError, ValueError) as exc:
            raise FetchError(
                f"cannot resolve host: {getattr(exc, 'strerror', None) or exc}"
            ) from exc
        if not addresses:
            raise FetchError("host did not resolve to any address")
        if not self.allow_private_hosts:
            blocked = [a for a in addresses if not is_public_address(a)]
            if blocked:
                raise FetchError(
                    "host resolves to a non-public address; set allow_private_hosts to permit this"
                )
        return addresses

    def _read_https(self, url: str, credential: Credential | None = None) -> bytes:
        deadline = time.monotonic() + self.total_timeout_seconds
        current = url
        origin = _origin(url)
        for _ in range(MAX_REDIRECTS + 1):
            # The key goes only to the host and port it was given for.
            key = credential if _origin(current) == origin else None
            body, location = self._request(current, deadline, key)
            if location is None:
                return body
            target = urljoin(current, location)
            if check_url(target) != "https":
                raise FetchError("redirect to a non-https URL refused")
            current = target
        raise FetchError(f"more than {MAX_REDIRECTS} redirects")

    def _request(
        self,
        url: str,
        deadline: float,
        credential: Credential | None = None,
        *,
        method: str = "GET",
        body: bytes | None = None,
        extra: Mapping[str, str] | None = None,
        tls: bool = True,
        loopback: bool = False,
    ) -> tuple[bytes, str | None]:
        parts = urlsplit(url)
        host = _wire_host(parts.hostname or "")
        default_port = 443 if tls else 80
        port = parts.port or default_port
        if loopback and _is_loopback_literal(host):
            # A loopback IP literal that _post_scheme allowed; no name is looked up.
            addresses = [host]
        else:
            addresses = self._vet(host, port, deadline)
        query = parts.query
        headers = {
            "Host": _host_header(host, port, default_port),
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/json,application/xml,*/*",
            "Connection": "close",
            **(extra or {}),
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        if credential is not None and credential.placement == "query":
            query = _with_parameter(query, credential.name, credential.value)
        elif credential is not None:
            headers[credential.name] = credential.header_value
        target = _wire_text((parts.path or "/") + (f"?{query}" if query else ""))
        sock: socket.socket | None = None
        watchdog: threading.Timer | None = None
        expired = threading.Event()
        try:
            sock = self._connect(addresses, port, deadline)
            if tls:
                sock = self._wrapper(sock, host)
            watchdog = threading.Timer(
                max(0.001, deadline - time.monotonic()), _expire, args=(sock, expired)
            )
            watchdog.daemon = True
            watchdog.start()
            connection = http.client.HTTPConnection(host, port)
            connection.sock = sock
            connection.request(method, target, body=body, headers=headers)
            response = connection.getresponse()
            if response.status in REDIRECT_STATUSES:
                location = response.getheader("Location")
                if not location:
                    raise FetchError(f"HTTP status {response.status} without a Location header")
                return b"", _utf8_header(location)
            if not 200 <= response.status < 300:
                detail = ""
                if method == "POST":
                    # An API says why it refused in the error body; keep the start of it.
                    try:
                        detail = response.read(MAX_ERROR_BODY_BYTES).decode(
                            "utf-8", errors="replace"
                        )
                    except (OSError, http.client.HTTPException, ValueError):
                        detail = ""
                raise FetchError(
                    f"HTTP status {response.status}", status=response.status, body=detail
                )
            declared = response.getheader("Content-Length")
            if declared is not None and declared.isdigit() and int(declared) > self.max_bytes:
                raise FetchError(f"response is larger than the limit of {self.max_bytes} bytes")
            return self._read_body(response, sock, deadline, expired), None
        except FetchError:
            raise
        except (OSError, http.client.HTTPException, ValueError) as exc:
            if expired.is_set() or time.monotonic() >= deadline:
                raise self._deadline_error() from exc
            raise FetchError(f"request failed: {getattr(exc, 'reason', None) or exc}") from exc
        finally:
            if watchdog is not None:
                watchdog.cancel()
            if sock is not None:
                _close(sock)

    def _connect(self, addresses: list[str], port: int, deadline: float) -> socket.socket:
        last: Exception | None = None
        for address in addresses:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise self._deadline_error()
            try:
                return self._connector(address, port, min(self.timeout_seconds, remaining))
            except OSError as exc:
                last = exc
        raise FetchError(f"cannot connect: {getattr(last, 'strerror', None) or last}")

    def _read_body(
        self,
        response: http.client.HTTPResponse,
        sock: socket.socket,
        deadline: float,
        expired: threading.Event,
    ) -> bytes:
        chunks: list[bytes] = []
        total = 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise self._deadline_error()
            sock.settimeout(min(self.timeout_seconds, remaining))
            chunk = response.read1(CHUNK_BYTES)
            if expired.is_set():
                # The watchdog closed the socket, which reads as end of file.
                raise self._deadline_error()
            if not chunk:
                return b"".join(chunks)
            total += len(chunk)
            if total > self.max_bytes:
                raise FetchError(f"response is larger than the limit of {self.max_bytes} bytes")
            chunks.append(chunk)

    def _deadline_error(self) -> FetchError:
        return FetchError(f"total time limit of {self.total_timeout_seconds:g} seconds exceeded")


def _origin(url: str) -> tuple[str, int]:
    """The lower-cased host and the port of an https URL, which a key is bound to."""
    parts = urlsplit(url)
    return (parts.hostname or "").lower().rstrip("."), parts.port or 443


def _with_parameter(query: str, name: str, value: str) -> str:
    """``query`` with every ``name`` parameter replaced by one carrying ``value``."""
    kept = [item for item in query.split("&") if item and item.partition("=")[0] != name]
    return "&".join([*kept, f"{name}={quote(value, safe='')}"])


def _wire_host(host: str) -> str:
    """The host as it goes on the wire: an internationalised name in its ``xn--`` form.

    The name is used for the lookup, the TLS server name and the Host header, so all
    three agree. A name that cannot be encoded is a clear ``FetchError``, and so is a
    name that the codec (IDNA 2003) would quietly turn into a different one: ``faß.de``
    becomes ``fass.de`` and a zero-width joiner or a soft hyphen is dropped. The encoded
    name must decode back to the name that was asked for, in NFC and lower case.
    """
    if host.isascii():
        return host
    error = FetchError("host name cannot be encoded as an internationalised name")
    try:
        wire = host.encode("idna").decode("ascii")
        decoded = wire.encode("ascii").decode("idna")
    except UnicodeError as exc:
        raise error from exc
    asked = unicodedata.normalize("NFC", host).lower().translate(_IDEOGRAPHIC_DOTS)
    if decoded != asked:
        raise error
    return wire


def _wire_text(target: str) -> str:
    """The request target with every non-ASCII character percent-encoded as UTF-8.

    Existing escapes and the characters that structure a URL are left alone.
    """
    if target.isascii():
        return target
    return quote(target, safe="/%:@!$&'()*+,;=-._~?")


def _utf8_header(value: str) -> str:
    """Undo the Latin-1 reading of a header value that a server wrote as raw UTF-8."""
    try:
        return value.encode("latin-1").decode("utf-8")
    except UnicodeError:
        return value


def _host_header(host: str, port: int, default_port: int = 443) -> str:
    """The Host header value: an IPv6 literal is bracketed, and a non-default port is appended."""
    name = f"[{host}]" if ":" in host else host
    return name if port == default_port else f"{name}:{port}"


_HEADER_NAME = re.compile(r"^[A-Za-z0-9-]{1,64}$")


def _check_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Extra request headers, refused when a name or value could split or replace a header."""
    checked: dict[str, str] = {}
    for name, value in headers.items():
        if not _HEADER_NAME.fullmatch(name) or name.lower() in _RESERVED_HEADERS:
            raise FetchError(f"the header name {clean_text(name, 64)!r} cannot be sent")
        if len(value) > 200 or any(not 0x20 <= ord(ch) <= 0x7E for ch in value):
            raise FetchError(f"the value of the {name} header cannot be sent")
        checked[name] = value
    return checked


def _is_loopback_literal(host: str) -> bool:
    """True for an IP literal in 127.0.0.0/8 or ``::1``; a name never counts."""
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _is_loopback_post_url(url: str) -> bool:
    """True for a plain ``http`` URL whose host is a loopback IP literal."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme == "http" and _is_loopback_literal(parts.hostname or "")


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def _default_wrapper(sock: socket.socket, host: str) -> socket.socket:
    return ssl.create_default_context().wrap_socket(sock, server_hostname=host)


def _expire(sock: socket.socket, expired: threading.Event) -> None:
    """Watchdog: mark the deadline as passed and close the socket to wake a blocked read."""
    expired.set()
    _close(sock)


def _close(sock: socket.socket) -> None:
    with contextlib.suppress(OSError):
        sock.shutdown(socket.SHUT_RDWR)
    with contextlib.suppress(OSError):
        sock.close()
