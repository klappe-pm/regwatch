"""The one network client.

Every byte regwatch reads from outside the register goes through a Fetcher.
The shipped SafeFetcher is deliberately small and enforces these rules:

- only the ``https`` and ``file`` URL schemes are accepted;
- ``file`` URLs are refused unless they lie under a configured root directory,
  and only regular files are read (never a FIFO, a device or a directory);
- a host that resolves to a loopback, link-local, private, unique local,
  reserved, multicast or otherwise non-global address is refused, for the first
  request and for every redirect, unless ``allow_private_hosts`` is set;
- the connection is made to the address that was vetted, not to a second
  lookup of the name, so a DNS answer that changes between the check and the
  connection cannot redirect the request;
- certificates are always verified against the original host name;
- a redirect may only lead to another ``https`` URL, at most 5 times, and the
  redirects share one total deadline with the request itself;
- every request has a per-operation timeout, a total deadline enforced both by
  checking the clock between reads and by a watchdog that closes the socket, and
  a hard limit on the number of bytes read;
- URLs that carry credentials, or contain control characters, are refused;
- proxy environment variables are ignored, because a proxy would resolve the
  host itself and defeat the address check;
- no shell, subprocess or external program is ever started.

Tests and embedders can supply any object with a matching ``fetch`` method, and
``SafeFetcher`` takes a resolver, a connector and a TLS wrapper so that it can be
tested without a network.
"""

from __future__ import annotations

import contextlib
import http.client
import ipaddress
import os
import socket
import ssl
import stat
import threading
import time
import urllib.request
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Protocol
from urllib.parse import urljoin, urlsplit

__all__ = [
    "ALLOWED_SCHEMES",
    "CHUNK_BYTES",
    "MAX_REDIRECTS",
    "FetchError",
    "Fetcher",
    "SafeFetcher",
    "check_url",
    "is_public_address",
]

ALLOWED_SCHEMES = frozenset({"https", "file"})
MAX_REDIRECTS = 5
CHUNK_BYTES = 16384
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})

Resolver = Callable[[str, int], list[str]]
Connector = Callable[[str, int, float], socket.socket]
Wrapper = Callable[[socket.socket, str], socket.socket]


class FetchError(Exception):
    """A fetch was refused or failed. The message is safe to show to the user."""


class Fetcher(Protocol):
    """Anything that can turn a URL into text."""

    def fetch(self, url: str) -> str:
        """Return the decoded body for ``url`` or raise FetchError."""
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


def is_public_address(address: str) -> bool:
    """True when ``address`` is a globally routable unicast IP address.

    Loopback, link-local, private (including unique local), shared, reserved,
    multicast and unspecified addresses are all not public. An IPv4 address
    written as an IPv4-mapped IPv6 address is judged as the IPv4 address.
    """
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
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
        resolver: Resolver | None = None,
        connector: Connector | None = None,
        wrapper: Wrapper | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes
        self.user_agent = user_agent
        self.total_timeout_seconds = total_timeout_seconds
        self.allow_private_hosts = allow_private_hosts
        self.allowed_file_roots = tuple(Path(root).resolve() for root in allowed_file_roots)
        self._resolver = resolver or _default_resolver
        self._connector = connector or _default_connector
        self._wrapper = wrapper or _default_wrapper

    def fetch(self, url: str) -> str:
        """Return the body of ``url`` decoded as UTF-8 with undecodable bytes replaced."""
        scheme = check_url(url)
        data = self._read_file(url) if scheme == "file" else self._read_https(url)
        return data.decode("utf-8", errors="replace")

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
            # O_NONBLOCK so that opening a FIFO cannot block; the type is checked next.
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise FetchError("only regular files can be read")
            with os.fdopen(descriptor, "rb", closefd=False) as handle:
                return self._limit(handle.read(self.max_bytes + 1))
        except (OSError, ValueError) as exc:
            raise FetchError(f"cannot read file: {getattr(exc, 'strerror', None) or exc}") from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    # --- https: URLs --------------------------------------------------------

    def _vet(self, host: str, port: int) -> list[str]:
        """Resolve ``host`` and return the addresses it is allowed to connect to."""
        try:
            addresses = [host] if _is_ip_literal(host) else self._resolver(host, port)
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

    def _read_https(self, url: str) -> bytes:
        deadline = time.monotonic() + self.total_timeout_seconds
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            body, location = self._request(current, deadline)
            if location is None:
                return body
            target = urljoin(current, location)
            if check_url(target) != "https":
                raise FetchError("redirect to a non-https URL refused")
            current = target
        raise FetchError(f"more than {MAX_REDIRECTS} redirects")

    def _request(self, url: str, deadline: float) -> tuple[bytes, str | None]:
        parts = urlsplit(url)
        host = parts.hostname or ""
        port = parts.port or 443
        addresses = self._vet(host, port)
        target = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        sock: socket.socket | None = None
        watchdog: threading.Timer | None = None
        expired = threading.Event()
        try:
            sock = self._connect(addresses, port, deadline)
            sock = self._wrapper(sock, host)
            watchdog = threading.Timer(
                max(0.001, deadline - time.monotonic()), _expire, args=(sock, expired)
            )
            watchdog.daemon = True
            watchdog.start()
            connection = http.client.HTTPConnection(host, port)
            connection.sock = sock
            connection.request(
                "GET",
                target,
                headers={
                    "Host": host if port == 443 else f"{host}:{port}",
                    "User-Agent": self.user_agent,
                    "Accept": "text/html,application/json,application/xml,*/*",
                    "Connection": "close",
                },
            )
            response = connection.getresponse()
            if response.status in REDIRECT_STATUSES:
                location = response.getheader("Location")
                if not location:
                    raise FetchError(f"HTTP status {response.status} without a Location header")
                return b"", location
            if not 200 <= response.status < 300:
                raise FetchError(f"HTTP status {response.status}")
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
