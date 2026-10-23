"""The local server: host, origin and token checks, file containment, headers and errors.

The suite blocks socket connections, so each request is written into one end of a
socket pair and the server handles the other end directly, as it would a real
connection. Nothing here opens a browser or reaches the network.
"""

from __future__ import annotations

import base64
import hashlib
import http.client
import io
import json
import socket
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import FakeFetcher, FakeSystem

from regwatch.config import load_config
from regwatch.server import LocalServer, ServerError, content_security_policy, web_root
from regwatch.webapi import Api

# Assembled from pieces so no token-shaped literal sits in the source.
TOKEN = "-".join(["test", "token", "for", "the", "suite"])
INLINE = "self.__ready=1"


class _Bytes:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def makefile(self, *args: object, **kwargs: object) -> io.BytesIO:
        return io.BytesIO(self.data)


class Reply:
    def __init__(self, raw: bytes) -> None:
        response = http.client.HTTPResponse(_Bytes(raw))  # type: ignore[arg-type]
        response.begin()
        self.status = response.status
        self.headers = response.headers
        self.body = response.read()

    def json(self) -> dict[str, object]:
        data = json.loads(self.body)
        assert isinstance(data, dict)
        return data


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A small build folder, a secret beside it, and a link inside it that points out."""
    web = tmp_path / "web"
    (web / "changes").mkdir(parents=True)
    (web / "index.html").write_text(
        f"<html><script>{INLINE}</script><script src='/a.js'></script>overview</html>",
        encoding="utf-8",
    )
    (web / "changes" / "index.html").write_text("<html>changes</html>", encoding="utf-8")
    (web / "404.html").write_text("<html>missing</html>", encoding="utf-8")
    (web / "app.js").write_text("console.log(1)", encoding="utf-8")
    (web / "style.css").write_text("body{}", encoding="utf-8")
    (web / ".hidden").write_text("hidden", encoding="utf-8")
    secret = tmp_path / "secret.txt"
    secret.write_text("outside the build folder", encoding="utf-8")
    (web / "escape.txt").symlink_to(secret)
    (web / "escape-dir").symlink_to(tmp_path)
    return web


@pytest.fixture
def fake() -> FakeSystem:
    """Stand-ins for the keychain tools and crontab, so no real program runs."""
    return FakeSystem("linux")


@pytest.fixture
def fresh(project: Path, root: Path, fake: FakeSystem) -> Iterator[LocalServer]:
    """A server whose launch token has not been used yet."""
    api = Api(project, system=fake.system(), fetcher=FakeFetcher())
    instance = LocalServer(api, root, 0, token=TOKEN)
    yield instance
    instance.server_close()


@pytest.fixture
def server(fresh: LocalServer) -> LocalServer:
    """A server whose launch token was traded for a session, as the browser does first."""
    reply = request(fresh, "GET", f"/?token={TOKEN}", cookie=None)
    assert reply.status == 303
    return fresh


def send(server: LocalServer, raw: bytes) -> Reply:
    client, end = socket.socketpair()
    try:
        client.sendall(raw)
        client.shutdown(socket.SHUT_WR)
        server.finish_request(end, ("127.0.0.1", 50000))  # type: ignore[arg-type]
        end.close()
        chunks = []
        while chunk := client.recv(65536):
            chunks.append(chunk)
    finally:
        client.close()
    return Reply(b"".join(chunks))


def request(
    server: LocalServer,
    method: str,
    path: str,
    *,
    host: str | None = None,
    cookie: str | None = "session",
    origin: str | None = "same",
    body: object = None,
    content_type: str = "application/json",
    extra: dict[str, str] | None = None,
) -> Reply:
    """Send one request; ``cookie="session"`` sends the server's session value."""
    headers = {"Host": host or f"127.0.0.1:{server.port}"}
    if cookie == "session":
        cookie = server.session
    if cookie is not None:
        headers["Cookie"] = f"other=1; {server.cookie_name}={cookie}"
    if origin == "same":
        headers["Origin"] = f"http://127.0.0.1:{server.port}"
    elif origin is not None:
        headers["Origin"] = origin
    data = b""
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        headers["Content-Type"] = content_type
        headers["Content-Length"] = str(len(data))
    headers.update(extra or {})
    head = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
    return send(server, f"{method} {path} HTTP/1.1\r\n{head}\r\n".encode() + data)


# --- binding and the address -----------------------------------------------------


def test_the_server_binds_loopback_on_a_free_port(server: LocalServer) -> None:
    assert server.server_address[0] == "127.0.0.1"
    assert server.port > 0
    assert server.url == f"http://127.0.0.1:{server.port}/?token={TOKEN}"


def test_each_server_gets_its_own_random_token(project: Path, root: Path) -> None:
    one, two = LocalServer(Api(project), root), LocalServer(Api(project), root)
    try:
        assert one.token != two.token
        assert len(one.token) >= 40
        assert one.cookie_name != two.cookie_name
    finally:
        one.server_close()
        two.server_close()


def test_a_taken_port_is_a_server_error(server: LocalServer, project: Path, root: Path) -> None:
    with pytest.raises(ServerError, match="cannot listen"):
        LocalServer(Api(project), root, server.port)


# --- host -----------------------------------------------------------------------


def test_a_request_with_the_right_host_is_served(server: LocalServer) -> None:
    assert request(server, "GET", "/").status == 200
    assert request(server, "GET", "/", host=f"localhost:{server.port}").status == 200


@pytest.mark.parametrize(
    "host",
    [
        "evil.example",
        "evil.example:{port}",
        "127.0.0.1",
        "127.0.0.1:1",
        "localhost",
        "0.0.0.0:{port}",
    ],
)
def test_a_request_for_another_host_is_refused(server: LocalServer, host: str) -> None:
    """A DNS rebinding page reaches the server under its own host name, so it is refused."""
    reply = request(server, "GET", "/api/status", host=host.format(port=server.port))
    assert reply.status == 403
    assert reply.json() == {"error": "this server answers only to its own address"}


def test_a_request_without_a_host_is_refused(server: LocalServer) -> None:
    raw = f"GET / HTTP/1.0\r\nCookie: {server.cookie_name}={server.session}\r\n\r\n".encode()
    assert send(server, raw).status == 403


# --- origin ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "origin",
    ["http://evil.example", "null", "http://127.0.0.1:1", "https://127.0.0.1:{port}", None],
)
def test_a_change_from_another_origin_is_refused(
    server: LocalServer, project: Path, origin: str | None
) -> None:
    before = project.read_text(encoding="utf-8")
    value = origin.format(port=server.port) if origin else None
    reply = request(server, "POST", "/api/settings/premium", origin=value, body={"enabled": True})
    assert reply.status == 403
    assert reply.json()["error"] == "a change must come from this server's own pages"
    assert project.read_text(encoding="utf-8") == before


def test_a_change_from_the_same_origin_is_accepted(server: LocalServer, project: Path) -> None:
    reply = request(server, "POST", "/api/settings/premium", body={"enabled": True})
    assert reply.status == 200
    assert reply.json() == {"premium": True}
    assert load_config(project).premium.enabled is True
    reply = request(
        server,
        "POST",
        "/api/settings/premium",
        origin=f"http://localhost:{server.port}",
        body={"enabled": False},
    )
    assert reply.json() == {"premium": False}


def test_a_change_must_be_sent_as_json(server: LocalServer) -> None:
    """A plain HTML form cannot send JSON, so a cross-site form post never reaches a route."""
    reply = request(
        server, "POST", "/api/settings/premium", body=b"enabled=true", content_type="text/plain"
    )
    assert reply.status == 415


# --- token ----------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/", "/api/status", "/app.js", "/changes/"])
def test_a_request_without_the_token_is_refused(server: LocalServer, path: str) -> None:
    reply = request(server, "GET", path, cookie=None)
    assert reply.status == 403
    assert b"overview" not in reply.body
    assert "token" in reply.json()["error"]


def test_a_wrong_token_is_refused(server: LocalServer) -> None:
    assert request(server, "GET", "/api/status", cookie=f"{server.session}x").status == 403
    assert request(server, "GET", "/?token=wrong", cookie=None).status == 403
    assert request(server, "GET", "/api/status", cookie="").status == 403


def test_a_wrong_launch_token_does_not_spend_the_real_one(fresh: LocalServer) -> None:
    assert request(fresh, "GET", "/?token=wrong", cookie=None).status == 403
    assert fresh.session is None
    assert request(fresh, "GET", f"/?token={TOKEN}", cookie=None).status == 303


def test_the_launch_token_is_traded_for_a_separate_session_cookie(fresh: LocalServer) -> None:
    reply = request(fresh, "GET", f"/changes/?token={TOKEN}&q=nl", cookie=None)
    assert reply.status == 303
    assert reply.headers["Location"] == "/changes/?q=nl"
    assert reply.headers["Cache-Control"] == "no-store"
    cookie = reply.headers["Set-Cookie"]
    name, _, rest = cookie.partition("=")
    session, _, flags = rest.partition(";")
    assert name == fresh.cookie_name
    assert flags == " Path=/; HttpOnly; SameSite=Strict"
    assert session == fresh.session
    assert session != TOKEN and TOKEN not in cookie
    assert len(session) >= 40
    assert request(fresh, "GET", "/api/status", cookie=session).status == 200


def test_the_launch_token_works_only_once(fresh: LocalServer) -> None:
    """A copy of the address (the terminal, the browser's command line) is worthless once used."""
    first = request(fresh, "GET", f"/?token={TOKEN}", cookie=None)
    assert first.status == 303
    again = request(fresh, "GET", f"/?token={TOKEN}", cookie=None)
    assert again.status == 403
    assert "works only once" in again.json()["error"]
    assert "Set-Cookie" not in again.headers


def test_the_launch_token_is_not_a_session(fresh: LocalServer) -> None:
    assert request(fresh, "GET", "/api/status", cookie=TOKEN).status == 403
    request(fresh, "GET", f"/?token={TOKEN}", cookie=None)
    assert request(fresh, "GET", "/api/status", cookie=TOKEN).status == 403


def test_two_racing_exchanges_get_one_session(
    fresh: LocalServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    import secrets
    import threading
    import time

    import regwatch.server as server_module

    original = secrets.token_urlsafe

    def slow_token(size: int) -> str:
        # Widen the window between the check and the assignment, as a busy machine might.
        time.sleep(0.05)
        return original(size)

    monkeypatch.setattr(server_module.secrets, "token_urlsafe", slow_token)
    results: list[str | None] = []
    barrier = threading.Barrier(8)

    def trade() -> None:
        barrier.wait()
        results.append(fresh.exchange(TOKEN))

    threads = [threading.Thread(target=trade) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert [r for r in results if r is not None] == [fresh.session]


def test_a_signed_in_browser_that_reopens_the_address_keeps_its_session(
    server: LocalServer,
) -> None:
    session = server.session
    reply = request(server, "GET", f"/changes/?token={TOKEN}")
    assert reply.status == 303
    assert reply.headers["Location"] == "/changes/"
    assert "Set-Cookie" not in reply.headers
    assert server.session == session


@pytest.mark.parametrize("path", ["//evil.example/x", "/%2F%5Cevil.example", "/\\evil.example"])
def test_the_cleaned_address_cannot_point_at_another_host(fresh: LocalServer, path: str) -> None:
    reply = request(fresh, "GET", f"{path}?token={TOKEN}", cookie=None)
    assert reply.status == 303
    location = reply.headers["Location"]
    assert location.startswith("/") and location[1:2] not in ("/", "\\"), location
    assert location.endswith("evil.example") or location.endswith("evil.example/x")


def test_a_change_cannot_carry_the_token_in_its_address(fresh: LocalServer) -> None:
    reply = request(
        fresh, "POST", f"/api/settings/premium?token={TOKEN}", cookie=None, body={"enabled": True}
    )
    assert reply.status == 403
    assert fresh.session is None


# --- idle and excess connections --------------------------------------------------


def test_an_idle_connection_times_out() -> None:
    from regwatch.server import HANDLER_TIMEOUT_SECONDS, _Handler

    assert HANDLER_TIMEOUT_SECONDS == 30
    assert _Handler.timeout == HANDLER_TIMEOUT_SECONDS


def test_a_connection_that_sends_nothing_frees_its_thread(
    server: LocalServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The handler timeout reaches the socket, so a silent client cannot hold a thread."""
    import threading

    from regwatch.server import _Handler

    monkeypatch.setattr(_Handler, "timeout", 0.2)
    client, end = socket.socketpair()
    try:
        worker = threading.Thread(
            target=server.finish_request, args=(end, ("127.0.0.1", 50000)), daemon=True
        )
        worker.start()
        worker.join(5)
        assert not worker.is_alive()
    finally:
        client.close()
        end.close()


def test_connections_beyond_the_cap_are_closed_at_once(server: LocalServer) -> None:
    import threading
    import time

    import regwatch.server as server_module

    held: list[tuple[socket.socket, socket.socket]] = []
    try:
        for _ in range(server_module.MAX_CONNECTIONS):
            client, end = socket.socketpair()
            held.append((client, end))
            server.process_request(end, ("127.0.0.1", 50000))
        assert threading.active_count() >= server_module.MAX_CONNECTIONS
        extra_client, extra_end = socket.socketpair()
        server.process_request(extra_end, ("127.0.0.1", 50001))
        extra_client.settimeout(2)
        assert extra_client.recv(1) == b""  # closed without being handled
        extra_client.close()
    finally:
        for client, _end in held:
            client.close()
    # Once the held connections end, their slots are free again.
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        client, end = socket.socketpair()
        server.process_request(end, ("127.0.0.1", 50002))
        client.sendall(
            f"GET /api/status HTTP/1.0\r\nHost: 127.0.0.1:{server.port}\r\n\r\n".encode()
        )
        client.settimeout(2)
        if client.recv(12):
            client.close()
            break
        client.close()
        time.sleep(0.05)
    else:
        pytest.fail("no slot came free after the held connections closed")


def test_the_slot_is_released_when_a_thread_cannot_start(
    server: LocalServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    import http.server

    def fail(*args: object) -> None:
        raise RuntimeError("cannot start a thread")

    monkeypatch.setattr(http.server.ThreadingHTTPServer, "process_request", fail)
    client, end = socket.socketpair()
    with pytest.raises(RuntimeError):
        server.process_request(end, ("127.0.0.1", 50000))
    client.close()
    end.close()
    acquired = [server._slots.acquire(blocking=False) for _ in range(40)]
    import regwatch.server as server_module

    assert acquired.count(True) == server_module.MAX_CONNECTIONS


# --- files ----------------------------------------------------------------------


def test_pages_are_served_from_the_build_folder(server: LocalServer) -> None:
    reply = request(server, "GET", "/")
    assert reply.status == 200
    assert reply.headers["Content-Type"] == "text/html; charset=utf-8"
    assert b"overview" in reply.body
    assert request(server, "GET", "/changes/").body == b"<html>changes</html>"
    assert request(server, "GET", "/changes").body == b"<html>changes</html>"
    js = request(server, "GET", "/app.js")
    assert js.headers["Content-Type"] == "text/javascript; charset=utf-8"
    assert request(server, "GET", "/style.css").headers["Content-Type"].startswith("text/css")


@pytest.mark.parametrize(
    "path",
    [
        "/../secret.txt",
        "/%2e%2e/secret.txt",
        "/changes/../../secret.txt",
        "/%2E%2E%2Fsecret.txt",
        "/escape.txt",
        "/escape-dir/secret.txt",
        "/.hidden",
        "/..%5Csecret.txt",
        "/%00index.html",
    ],
)
def test_nothing_outside_the_build_folder_is_served(server: LocalServer, path: str) -> None:
    reply = request(server, "GET", path)
    assert reply.status == 404
    assert b"outside the build folder" not in reply.body
    assert b"hidden" not in reply.body
    assert reply.body == b"<html>missing</html>"


def test_a_missing_page_without_a_404_page_is_a_json_error(project: Path, tmp_path: Path) -> None:
    web = tmp_path / "bare"
    web.mkdir()
    (web / "index.html").write_text("x", encoding="utf-8")
    bare = LocalServer(Api(project), web, 0, token=TOKEN)
    try:
        request(bare, "GET", f"/?token={TOKEN}", cookie=None)
        reply = request(bare, "GET", "/nothing")
        assert reply.status == 404
        assert reply.json() == {"error": "not found"}
    finally:
        bare.server_close()


def test_every_response_carries_the_security_headers(server: LocalServer) -> None:
    for path in ("/", "/app.js", "/api/status", "/missing"):
        reply = request(server, "GET", path)
        assert reply.headers["X-Content-Type-Options"] == "nosniff"
        assert reply.headers["X-Frame-Options"] == "DENY"
        assert reply.headers["Referrer-Policy"] == "no-referrer"
        policy = reply.headers["Content-Security-Policy"]
        assert "default-src 'none'" in policy
        assert "http" not in policy
        assert "unsafe" not in policy
        assert "frame-ancestors 'none'" in policy


def test_the_policy_allows_exactly_the_page_inline_scripts(server: LocalServer) -> None:
    digest = base64.b64encode(hashlib.sha256(INLINE.encode()).digest()).decode()
    page = request(server, "GET", "/").headers["Content-Security-Policy"]
    assert f"script-src 'self' 'sha256-{digest}';" in page
    other = request(server, "GET", "/changes/").headers["Content-Security-Policy"]
    assert "script-src 'self';" in other
    assert content_security_policy([]).startswith("default-src 'none'; script-src 'self';")


def test_api_responses_are_not_cached(server: LocalServer) -> None:
    reply = request(server, "GET", "/api/status")
    assert reply.headers["Cache-Control"] == "no-store"
    assert reply.headers["Content-Type"] == "application/json; charset=utf-8"


def test_requests_are_not_logged(fresh: LocalServer, capsys: pytest.CaptureFixture[str]) -> None:
    request(fresh, "GET", f"/?token={TOKEN}", cookie=None)
    request(fresh, "GET", "/missing")
    captured = capsys.readouterr()
    assert TOKEN not in captured.err + captured.out
    assert captured.err == ""


# --- the interface over HTTP ---------------------------------------------------


def test_errors_are_short_json(server: LocalServer) -> None:
    assert request(server, "GET", "/api/nothing").json() == {"error": "no such route"}
    reply = request(server, "POST", "/api/status", body={})
    assert reply.status == 405
    reply = request(server, "PUT", "/api/status")
    assert reply.status == 501
    reply = request(server, "POST", "/", body={})
    assert reply.status == 405
    reply = request(server, "POST", "/api/settings/premium", body=b"[1]")
    assert reply.status == 400
    reply = request(server, "POST", "/api/settings/premium", body=b"{not json")
    assert reply.status == 400
    reply = request(server, "POST", "/api/settings/premium", body={"enabled": "yes"})
    assert reply.status == 400
    too_long = request(
        server,
        "POST",
        "/api/settings/premium",
        extra={"Content-Type": "application/json", "Content-Length": "70000"},
    )
    assert too_long.status == 413
    bad_length = request(
        server,
        "POST",
        "/api/settings/premium",
        extra={"Content-Type": "application/json", "Content-Length": "lots"},
    )
    assert bad_length.status == 413


def test_an_invalid_register_is_reported_without_its_contents(
    server: LocalServer, project: Path
) -> None:
    marker = "PRIVATE-REGISTER-VALUE"
    sources = project.parent / "register" / "sources.json"
    sources.write_text(json.dumps({"sources": [{"source_id": marker}]}), encoding="utf-8")
    reply = request(server, "GET", "/api/overview")
    assert reply.status == 422
    assert marker.encode() not in reply.body
    assert reply.json() == {
        "error": "the register is invalid; run 'regwatch validate' for the list"
    }


def test_a_broken_configuration_is_reported_without_its_contents(
    server: LocalServer, project: Path
) -> None:
    project.write_text('[register]\nobligations = "PRIVATE-PATH"\n', encoding="utf-8")
    reply = request(server, "GET", "/api/status")
    assert reply.status == 500
    assert b"PRIVATE" not in reply.body


def test_a_setting_that_cannot_be_saved_is_reported(server: LocalServer, project: Path) -> None:
    text = project.read_text(encoding="utf-8")
    # A dotted key at the top is valid TOML that the line editor will not rewrite.
    project.write_text("premium.enabled = false\n" + text, encoding="utf-8")
    reply = request(server, "POST", "/api/settings/premium", body={"enabled": True})
    assert reply.status == 409
    assert "by hand" in reply.json()["error"]
    assert project.read_text(encoding="utf-8").startswith("premium.enabled = false\n")


def test_an_unexpected_failure_says_nothing_about_it(
    server: LocalServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(*args: object) -> None:
        raise RuntimeError("PRIVATE-DETAIL")

    monkeypatch.setattr(Api, "status", explode)
    monkeypatch.setattr(server.api, "_routes", {("GET", "/api/status"): explode})
    reply = request(server, "GET", "/api/status")
    assert reply.status == 500
    assert reply.json() == {"error": "the request failed"}


def test_a_file_error_says_nothing_about_the_file(
    server: LocalServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args: object) -> None:
        raise OSError(13, "PRIVATE-PATH")

    monkeypatch.setattr(server.api, "_routes", {("GET", "/api/status"): fail})
    reply = request(server, "GET", "/api/status")
    assert reply.json() == {"error": "a file could not be read or written"}


def test_an_export_is_a_download(server: LocalServer) -> None:
    reply = request(server, "GET", "/api/briefing/export?kind=tiered&tier=v1&format=md")
    assert reply.status == 200
    assert reply.headers["Content-Type"] == "text/markdown; charset=utf-8"
    assert reply.headers["Content-Disposition"].startswith('attachment; filename="regwatch-')
    assert reply.headers["Cache-Control"] == "no-store"
    assert b"not legal advice" in reply.body.lower()


# --- keys never leave --------------------------------------------------------------


def test_no_route_ever_returns_a_key(server: LocalServer, fake: FakeSystem) -> None:
    """Store a key through the interface, then read every route: the value never comes back.

    The key goes into the faked keychain through the real keys module, the same way
    `regwatch keys set` stores one. Then every GET route is read, a run is started and
    awaited, and the key is removed; no response holds the value.
    """
    value = "".join(["kv", "-", "fake", "-", "value", "-", "9f3a"])
    added = request(server, "POST", "/api/catalogue/add", body={"source_id": "us-eia-api"})
    assert added.status == 200
    reply = request(server, "POST", "/api/keys/set", body={"source_id": "us-eia-api", "key": value})
    assert reply.status == 200
    assert reply.json() == {"available": True, "source_id": "us-eia-api", "present": True}
    assert fake.keychain == {"REGWATCH_KEY_EIA": value}
    bodies = [added.body, reply.body]
    routes = [path for method, path in server.api._routes if method == "GET"]
    queries = {
        "/api/search": "?q=eia",
        "/api/catalogue": "?q=eia",
        "/api/briefing/export": "?format=md",
    }
    for path in routes:
        bodies.append(request(server, "GET", path + queries.get(path, "")).body)
    bodies.append(request(server, "POST", "/api/automations/run", body={}).body)
    server.api.wait_for_run(10)
    bodies.append(request(server, "GET", "/api/automations").body)
    keys = request(server, "GET", "/api/keys").json()
    assert keys["keys"] == [
        {
            "source_id": "us-eia-api",
            "key_env": "REGWATCH_KEY_EIA",
            "present": True,
            "where": "Stored in the keychain",
            "signup_url": keys["keys"][0]["signup_url"],
        }
    ]
    fake.environ["REGWATCH_KEY_EIA"] = value
    bodies.append(request(server, "GET", "/api/keys").body)
    bodies.append(
        request(server, "POST", "/api/keys/remove", body={"source_id": "us-eia-api"}).body
    )
    for body in bodies:
        assert value.encode() not in body
    assert fake.keychain == {}


def test_the_key_routes_refuse_what_they_cannot_do(server: LocalServer) -> None:
    assert request(server, "GET", "/api/keys").json()["keys"] == []
    reply = request(server, "POST", "/api/keys/set", body={"source_id": "nl-notices", "key": "b"})
    assert reply.status == 400
    assert request(server, "POST", "/api/keys/set", body={"source_id": "a"}).status == 400
    assert request(server, "POST", "/api/keys/remove", body={"source_id": "a"}).status == 400


# --- the shipped build ------------------------------------------------------------


def test_the_shipped_web_root_is_found() -> None:
    assert (web_root() / "index.html").is_file()


def test_a_missing_build_is_a_server_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import regwatch.server as server_module

    class Files:
        def joinpath(self, name: str) -> Path:
            return tmp_path / name

    monkeypatch.setattr(server_module.resources, "files", lambda package: Files())
    with pytest.raises(ServerError, match="not built"):
        web_root()
