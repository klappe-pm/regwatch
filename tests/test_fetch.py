from __future__ import annotations

import ast
import os
import socket
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest

import regwatch.fetch as fetch_module
from regwatch.fetch import (
    ALLOWED_SCHEMES,
    MAX_REDIRECTS,
    FetchError,
    SafeFetcher,
    check_url,
    is_public_address,
)

PUBLIC = "93.184.216.34"
Handler = bytes | Callable[[socket.socket], None]


def ok(body: bytes = b"hello", extra: str = "") -> bytes:
    head = f"HTTP/1.1 200 OK\r\nContent-Length: {len(body)}\r\n{extra}\r\n"
    return head.encode() + body


def redirect(location: str, code: int = 302) -> bytes:
    return f"HTTP/1.1 {code} Found\r\nLocation: {location}\r\nContent-Length: 0\r\n\r\n".encode()


class Network:
    """A fake network: a resolver, a connector backed by socket pairs, and a TLS wrapper."""

    def __init__(self, hosts: dict[str, list[str]], handlers: list[Handler]) -> None:
        self.hosts = hosts
        self.handlers = list(handlers)
        self.resolved: list[str] = []
        self.connected: list[tuple[str, int]] = []
        self.wrapped: list[str] = []
        self.requests: list[bytes] = []
        self.clients: list[socket.socket] = []

    def resolver(self, host: str, port: int) -> list[str]:
        self.resolved.append(host)
        if host not in self.hosts:
            raise OSError(0, "name not known")
        return self.hosts[host]

    def connector(self, address: str, port: int, timeout: float) -> socket.socket:
        self.connected.append((address, port))
        client, server = socket.socketpair()
        self.clients.append(client)
        handler = self.handlers.pop(0)
        threading.Thread(target=self._serve, args=(server, handler), daemon=True).start()
        return client

    def wrapper(self, sock: socket.socket, host: str) -> socket.socket:
        self.wrapped.append(host)
        return sock

    def _serve(self, server: socket.socket, handler: Handler) -> None:
        try:
            data = b""
            while b"\r\n\r\n" not in data:
                chunk = server.recv(4096)
                if not chunk:
                    return
                data += chunk
            self.requests.append(data)
            if isinstance(handler, bytes):
                server.sendall(handler)
            else:
                handler(server)
        except OSError:
            pass
        finally:
            server.close()


def make(network: Network, **kwargs: object) -> SafeFetcher:
    options: dict[str, object] = {"total_timeout_seconds": 5.0}
    options.update(kwargs)
    return SafeFetcher(
        5,
        int(options.pop("max_bytes", 1000)),  # type: ignore[call-overload]
        "regwatch-test",
        resolver=network.resolver,
        connector=network.connector,
        wrapper=network.wrapper,
        **options,  # type: ignore[arg-type]
    )


def web(*handlers: Handler, hosts: dict[str, list[str]] | None = None) -> Network:
    return Network(hosts or {"example.org": [PUBLIC]}, list(handlers))


# --- URL checks ---------------------------------------------------------------


def test_allowed_schemes() -> None:
    assert frozenset({"https", "file"}) == ALLOWED_SCHEMES


@pytest.mark.parametrize(
    "url",
    [
        "http://example.org/a",
        "ftp://example.org/a",
        "javascript:alert(1)",
        "data:text/plain,hello",
        "gopher://example.org",
        "/just/a/path",
        "example.org/no-scheme",
        "",
    ],
)
def test_disallowed_schemes_are_refused(url: str) -> None:
    with pytest.raises(FetchError, match="not allowed"):
        check_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.org/a\x00b",
        "file:///tmp/a\x00b",
        "https://exa mple.org/",
        "https://example.org/\n",
        "https://example.org/\x7f",
    ],
)
def test_control_characters_and_spaces_are_refused(url: str) -> None:
    with pytest.raises(FetchError, match="control character"):
        check_url(url)


def test_credentials_in_url_are_refused() -> None:
    with pytest.raises(FetchError, match="credentials"):
        check_url("https://user:pass@example.org/")


def test_https_without_host_is_refused() -> None:
    with pytest.raises(FetchError, match="no host"):
        check_url("https:///path")


def test_remote_file_host_is_refused() -> None:
    with pytest.raises(FetchError, match="remote host"):
        check_url("file://example.org/etc/passwd")


@pytest.mark.parametrize(
    "url", ["https://[::1", "https://example.org:notaport/", "https://example.org:99999/"]
)
def test_invalid_url_is_refused(url: str) -> None:
    with pytest.raises(FetchError, match="invalid URL"):
        check_url(url)


def test_accepts_https_and_file() -> None:
    assert check_url("HTTPS://example.org/x") == "https"
    assert check_url("file:///tmp/x") == "file"
    assert check_url("file://localhost/tmp/x") == "file"


# --- file: URLs ---------------------------------------------------------------


def file_fetcher(root: Path, max_bytes: int = 1000) -> SafeFetcher:
    return SafeFetcher(5, max_bytes, "regwatch-test", allowed_file_roots=[root])


def test_file_urls_are_disabled_without_a_root(tmp_path: Path) -> None:
    path = tmp_path / "doc.txt"
    path.write_text("secret", encoding="utf-8")
    with pytest.raises(FetchError, match="file URLs are disabled"):
        SafeFetcher(5, 1000, "ua").fetch(path.as_uri())


def test_file_inside_a_root_is_read(tmp_path: Path) -> None:
    path = tmp_path / "doc.txt"
    path.write_text("héllo", encoding="utf-8")
    assert file_fetcher(tmp_path).fetch(path.as_uri()) == "héllo"


def test_file_outside_every_root_is_refused(tmp_path: Path) -> None:
    root, outside = tmp_path / "root", tmp_path / "outside.txt"
    root.mkdir()
    outside.write_text("secret", encoding="utf-8")
    with pytest.raises(FetchError, match="outside the allowed_file_roots"):
        file_fetcher(root).fetch(outside.as_uri())


def test_symlink_that_escapes_the_root_is_refused(tmp_path: Path) -> None:
    root, outside = tmp_path / "root", tmp_path / "outside.txt"
    root.mkdir()
    outside.write_text("secret", encoding="utf-8")
    (root / "link.txt").symlink_to(outside)
    with pytest.raises(FetchError, match="outside the allowed_file_roots"):
        file_fetcher(root).fetch((root / "link.txt").as_uri())


def test_dot_dot_segments_cannot_leave_the_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "outside.txt").write_text("secret", encoding="utf-8")
    with pytest.raises(FetchError, match="outside"):
        file_fetcher(root).fetch(f"file://{root}/../outside.txt")


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs POSIX named pipes")
def test_fifo_is_refused_without_blocking(tmp_path: Path) -> None:
    fifo = tmp_path / "pipe"
    os.mkfifo(fifo)
    start = time.monotonic()
    with pytest.raises(FetchError, match="only regular files"):
        file_fetcher(tmp_path).fetch(fifo.as_uri())
    assert time.monotonic() - start < 2


def test_directory_is_refused(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    with pytest.raises(FetchError, match="only regular files"):
        file_fetcher(tmp_path).fetch((tmp_path / "sub").as_uri())


@pytest.mark.skipif(not Path("/dev/zero").exists(), reason="needs /dev/zero")
def test_device_file_is_refused() -> None:
    with pytest.raises(FetchError, match="only regular files"):
        file_fetcher(Path("/dev")).fetch("file:///dev/zero")


def test_nul_byte_in_a_file_url_fails_only_that_fetch(tmp_path: Path) -> None:
    fetcher = file_fetcher(tmp_path)
    for url in ("file:///tmp/a%00b", f"file://{tmp_path}/a%00b"):
        with pytest.raises(FetchError):
            fetcher.fetch(url)
    with pytest.raises(FetchError):
        fetcher.fetch("file:///tmp/a\x00b")


def test_file_size_limit(tmp_path: Path) -> None:
    path = tmp_path / "big.txt"
    path.write_bytes(b"x" * 11)
    with pytest.raises(FetchError, match="larger than the limit of 10 bytes"):
        file_fetcher(tmp_path, max_bytes=10).fetch(path.as_uri())
    path.write_bytes(b"x" * 10)
    assert file_fetcher(tmp_path, max_bytes=10).fetch(path.as_uri()) == "x" * 10


def test_undecodable_bytes_are_replaced(tmp_path: Path) -> None:
    path = tmp_path / "doc.bin"
    path.write_bytes(b"ok\xff")
    assert file_fetcher(tmp_path).fetch(path.as_uri()) == "ok�"


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FetchError, match="cannot read file"):
        file_fetcher(tmp_path).fetch((tmp_path / "absent").as_uri())


def test_fetch_refuses_disallowed_scheme_before_any_io() -> None:
    with pytest.raises(FetchError):
        SafeFetcher(5, 1000, "ua").fetch("http://example.org/")


# --- https: success and pinning ------------------------------------------------


def test_https_success_pins_the_vetted_address_and_verifies_the_name() -> None:
    network = web(ok(b"body text"))
    assert make(network).fetch("https://example.org/path?q=1") == "body text"
    assert network.connected == [(PUBLIC, 443)]
    assert network.wrapped == ["example.org"]
    request = network.requests[0].decode()
    assert request.startswith("GET /path?q=1 HTTP/1.1\r\n")
    assert "Host: example.org\r\n" in request
    assert "User-Agent: regwatch-test\r\n" in request


def test_non_default_port_is_sent_in_the_host_header() -> None:
    network = web(ok())
    make(network).fetch("https://example.org:8443/")
    assert network.connected == [(PUBLIC, 8443)]
    assert "Host: example.org:8443\r\n" in network.requests[0].decode()


def test_the_name_is_resolved_once_so_a_dns_rebind_cannot_change_the_address() -> None:
    answers = iter([[PUBLIC], ["127.0.0.1"], ["127.0.0.1"]])

    class Rebinding(Network):
        def resolver(self, host: str, port: int) -> list[str]:
            self.resolved.append(host)
            return next(answers)

    network = Rebinding({}, [ok()])
    make(network).fetch("https://example.org/")
    assert network.resolved == ["example.org"]
    assert network.connected == [(PUBLIC, 443)]


def test_the_socket_is_closed_afterwards() -> None:
    network = web(ok())
    make(network).fetch("https://example.org/")
    assert network.clients[0].fileno() == -1


def test_proxy_environment_variables_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:3128")
    network = web(ok())
    make(network).fetch("https://example.org/")
    assert network.connected == [(PUBLIC, 443)]


def test_tries_the_next_vetted_address_when_one_does_not_connect() -> None:
    class Flaky(Network):
        def connector(self, address: str, port: int, timeout: float) -> socket.socket:
            if address == PUBLIC:
                self.connected.append((address, port))
                raise OSError(111, "refused")
            return super().connector(address, port, timeout)

    network = Flaky({"example.org": [PUBLIC, "93.184.216.35"]}, [ok()])
    assert make(network).fetch("https://example.org/") == "hello"
    assert network.connected == [(PUBLIC, 443), ("93.184.216.35", 443)]


def test_connection_failure_is_a_fetch_error() -> None:
    class Down(Network):
        def connector(self, address: str, port: int, timeout: float) -> socket.socket:
            raise OSError(111, "Connection refused")

    with pytest.raises(FetchError, match="cannot connect: Connection refused"):
        make(Down({"example.org": [PUBLIC]}, [])).fetch("https://example.org/")


def test_resolution_failures() -> None:
    with pytest.raises(FetchError, match="cannot resolve host"):
        make(web()).fetch("https://unknown.example/")
    with pytest.raises(FetchError, match="did not resolve"):
        make(web(hosts={"example.org": []})).fetch("https://example.org/")


# --- https: private address ranges ---------------------------------------------


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "127.1.2.3",
        "10.0.0.5",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",
        "100.64.0.1",
        "0.0.0.0",  # noqa: S104
        "224.0.0.1",
        "240.0.0.1",
        "::1",
        "::",
        "fc00::1",
        "fd12:3456::1",
        "fe80::1",
        "ff02::1",
        "::ffff:127.0.0.1",
        "::ffff:10.0.0.1",
    ],
)
def test_non_public_addresses_are_refused(address: str) -> None:
    assert is_public_address(address) is False
    network = web(ok(), hosts={"example.org": [address]})
    with pytest.raises(FetchError, match="non-public address"):
        make(network).fetch("https://example.org/")
    assert network.connected == []


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/",
        "https://[::1]/",
        "https://10.1.2.3:8443/",
        "https://169.254.169.254/latest",
    ],
)
def test_ip_literal_urls_are_vetted_too(url: str) -> None:
    network = web(ok())
    with pytest.raises(FetchError, match="non-public address"):
        make(network).fetch(url)
    assert network.connected == [] and network.resolved == []


def test_one_private_answer_among_public_ones_refuses_the_host() -> None:
    network = web(ok(), hosts={"example.org": [PUBLIC, "10.0.0.1"]})
    with pytest.raises(FetchError, match="non-public"):
        make(network).fetch("https://example.org/")


def test_allow_private_hosts_opts_in() -> None:
    network = web(ok(), hosts={"intranet.example": ["10.0.0.1"]})
    assert make(network, allow_private_hosts=True).fetch("https://intranet.example/") == "hello"
    assert network.connected == [("10.0.0.1", 443)]


def test_public_addresses() -> None:
    assert is_public_address(PUBLIC)
    assert is_public_address("2606:4700:4700::1111")
    assert not is_public_address("not an address")


# --- https: redirects ------------------------------------------------------------


def test_redirect_to_a_private_host_is_refused_at_the_second_hop() -> None:
    network = web(
        redirect("https://internal.example/admin"),
        ok(),
        hosts={"example.org": [PUBLIC], "internal.example": ["192.168.0.10"]},
    )
    with pytest.raises(FetchError, match="non-public"):
        make(network).fetch("https://example.org/")
    assert network.connected == [(PUBLIC, 443)]


def test_redirect_to_a_loopback_literal_is_refused() -> None:
    network = web(redirect("https://127.0.0.1:8080/"), ok())
    with pytest.raises(FetchError, match="non-public"):
        make(network).fetch("https://example.org/")


@pytest.mark.parametrize(
    "target",
    ["http://example.org/", "ftp://example.org/", "file:///etc/passwd", "javascript:alert(1)"],
)
def test_redirect_to_another_scheme_is_refused(target: str) -> None:
    network = web(redirect(target), ok())
    with pytest.raises(FetchError, match=r"not allowed|non-https"):
        make(network).fetch("https://example.org/")


def test_relative_redirect_is_followed() -> None:
    network = web(redirect("/moved"), ok(b"final"))
    assert make(network).fetch("https://example.org/start") == "final"
    assert network.requests[1].decode().startswith("GET /moved HTTP/1.1")
    assert network.connected == [(PUBLIC, 443), (PUBLIC, 443)]


def test_redirect_loop_is_capped() -> None:
    network = web(*[redirect("/again")] * (MAX_REDIRECTS + 2))
    with pytest.raises(FetchError, match=f"more than {MAX_REDIRECTS} redirects"):
        make(network).fetch("https://example.org/")
    assert len(network.connected) == MAX_REDIRECTS + 1


def test_redirect_without_a_location_is_an_error() -> None:
    with pytest.raises(FetchError, match="without a Location"):
        make(web(b"HTTP/1.1 302 Found\r\nContent-Length: 0\r\n\r\n")).fetch("https://example.org/")


# --- https: errors, size and time -------------------------------------------------


def test_http_error_status() -> None:
    with pytest.raises(FetchError, match="HTTP status 404"):
        make(web(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")).fetch(
            "https://example.org/"
        )


def test_size_limit_on_declared_length() -> None:
    with pytest.raises(FetchError, match="larger than the limit of 5 bytes"):
        make(web(ok(b"x" * 50)), max_bytes=5).fetch("https://example.org/")


def test_size_limit_on_the_body_without_a_declared_length() -> None:
    body = b"HTTP/1.1 200 OK\r\nConnection: close\r\n\r\n" + b"x" * 50
    with pytest.raises(FetchError, match="larger than the limit of 5 bytes"):
        make(web(body), max_bytes=5).fetch("https://example.org/")


def test_a_body_exactly_at_the_limit_is_accepted() -> None:
    assert make(web(ok(b"12345")), max_bytes=5).fetch("https://example.org/") == "12345"


def drip(prefix: bytes, piece: bytes, interval: float) -> Callable[[socket.socket], None]:
    def serve(server: socket.socket) -> None:
        server.sendall(prefix)
        while True:
            server.sendall(piece)
            time.sleep(interval)

    return serve


def test_a_server_that_drips_the_body_hits_the_total_deadline() -> None:
    handler = drip(b"HTTP/1.1 200 OK\r\nConnection: close\r\n\r\n", b"x", 0.02)
    start = time.monotonic()
    with pytest.raises(FetchError, match=r"total time limit of 0\.4 seconds exceeded"):
        make(web(handler), total_timeout_seconds=0.4, max_bytes=10_000_000).fetch(
            "https://example.org/"
        )
    assert time.monotonic() - start < 3


def test_a_server_that_drips_the_headers_hits_the_total_deadline() -> None:
    handler = drip(b"HTTP/1.1 200 OK\r\n", b"X-Pad: 1\r\n", 0.02)
    start = time.monotonic()
    with pytest.raises(FetchError, match="total time limit"):
        make(web(handler), total_timeout_seconds=0.4).fetch("https://example.org/")
    assert time.monotonic() - start < 3


def test_a_server_that_never_answers_hits_the_total_deadline() -> None:
    def silent(server: socket.socket) -> None:
        time.sleep(5)

    start = time.monotonic()
    with pytest.raises(FetchError, match="total time limit"):
        make(web(silent), total_timeout_seconds=0.3).fetch("https://example.org/")
    assert time.monotonic() - start < 3


def test_redirects_share_one_total_deadline() -> None:
    def slow_redirect(server: socket.socket) -> None:
        time.sleep(0.25)
        server.sendall(redirect("/next"))

    network = web(*[slow_redirect] * 5)
    start = time.monotonic()
    with pytest.raises(FetchError, match="total time limit"):
        make(network, total_timeout_seconds=0.6).fetch("https://example.org/")
    assert time.monotonic() - start < 3
    assert len(network.connected) < 5


# --- structure ----------------------------------------------------------------------


def test_no_subprocess_or_shell_use() -> None:
    tree = ast.parse(Path(fetch_module.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not imported & {"subprocess", "shlex", "pty", "ctypes", "pickle", "marshal"}
    calls = {
        f"{n.func.value.id}.{n.func.attr}"
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and isinstance(n.func.value, ast.Name)
    }
    assert not calls & {"os.system", "os.popen", "os.execv", "os.spawnv"}
