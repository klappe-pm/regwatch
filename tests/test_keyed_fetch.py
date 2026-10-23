"""Keyed fetches: the key goes only where its source says, only over https, and never further."""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any

import pytest
from test_fetch import PUBLIC, make, ok, redirect, web

from regwatch.check import capture_sources, check_sources, fetch_source
from regwatch.fetch import Credential, FetchError
from regwatch.register import Source

KEY = "fake" + "-key-" + "4567"


def query(name: str = "api_key", value: str = KEY) -> Credential:
    return Credential("query", name, value)


def request_line(raw: bytes) -> str:
    return raw.split(b"\r\n", 1)[0].decode()


def test_a_query_key_is_added_to_the_request() -> None:
    network = web(ok())
    make(network).fetch("https://example.org/docs?a=1", credential=query())
    assert request_line(network.requests[0]) == f"GET /docs?a=1&api_key={KEY} HTTP/1.1"


def test_an_existing_parameter_of_the_same_name_is_replaced() -> None:
    network = web(ok())
    make(network).fetch("https://example.org/docs?api_key=other&b=2", credential=query())
    assert request_line(network.requests[0]) == f"GET /docs?b=2&api_key={KEY} HTTP/1.1"


def test_a_key_value_is_percent_encoded_in_a_query() -> None:
    network = web(ok())
    make(network).fetch("https://example.org/", credential=query(value="a&b=c"))
    assert request_line(network.requests[0]) == "GET /?api_key=a%26b%3Dc HTTP/1.1"


def test_a_header_key_is_sent_as_that_header_only() -> None:
    network = web(ok())
    make(network).fetch("https://example.org/", credential=Credential("header", "X-Api-Key", KEY))
    raw = network.requests[0].decode()
    assert f"X-Api-Key: {KEY}\r\n" in raw
    assert KEY not in request_line(network.requests[0])


def test_without_a_credential_nothing_is_added() -> None:
    network = web(ok())
    make(network).fetch("https://example.org/a")
    assert request_line(network.requests[0]) == "GET /a HTTP/1.1"


@pytest.mark.parametrize("url", ["file:///tmp/feed.xml", "http://example.org/"])
def test_a_key_is_never_sent_without_https(url: str, tmp_path: Path) -> None:
    network = web()
    fetcher = make(network, allowed_file_roots=[tmp_path])
    with pytest.raises(FetchError, match=r"only over https|not allowed"):
        fetcher.fetch(url, credential=query())
    assert network.connected == []


def test_a_redirect_on_the_same_host_keeps_the_key() -> None:
    network = web(redirect("/next"), ok())
    make(network).fetch("https://example.org/start", credential=query())
    assert request_line(network.requests[1]) == f"GET /next?api_key={KEY} HTTP/1.1"


@pytest.mark.parametrize(
    "target",
    ["https://other.example.org/next", "https://example.org:8443/next", "https://EXAMPLE.net/x"],
)
def test_a_redirect_to_another_host_or_port_drops_the_key(target: str) -> None:
    hosts = {"example.org": [PUBLIC], "other.example.org": [PUBLIC], "example.net": [PUBLIC]}
    network = web(redirect(target), ok(), hosts=hosts)
    make(network).fetch("https://example.org/start", credential=Credential("header", "X-K", KEY))
    assert KEY in network.requests[0].decode()
    assert KEY not in network.requests[1].decode()


def test_a_redirect_to_another_host_and_back_does_not_regain_the_key_on_the_way() -> None:
    hosts = {"example.org": [PUBLIC], "other.example.org": [PUBLIC]}
    network = web(redirect("https://other.example.org/a"), redirect("/b"), ok(), hosts=hosts)
    make(network).fetch("https://example.org/start", credential=query())
    assert KEY not in network.requests[1].decode()
    assert KEY not in network.requests[2].decode()


def test_an_error_message_never_holds_the_key() -> None:
    def echo_key(server: socket.socket) -> None:
        server.sendall(b"HTTP/1.1 XYZ " + KEY.encode() + b"\r\n\r\n")

    network = web(echo_key)
    with pytest.raises(FetchError) as caught:
        make(network).fetch("https://example.org/", credential=query())
    assert KEY not in str(caught.value)
    assert "[key]" in str(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__


def test_an_encoded_key_is_redacted_too() -> None:
    credential = query(value="a&b")
    assert credential.redact("x a%26b y a&b") == "x [key] y [key]"


def test_the_html_and_json_forms_of_a_key_are_redacted() -> None:
    credential = query(value="a&b/c")
    assert credential.redact('x a&amp;b/c y "a&b\\/c" z a%26b%2Fc w a%26b/c') == (
        'x [key] y "[key]" z [key] w [key]'
    )


@pytest.mark.parametrize(
    "body",
    [
        f'{{"error": "invalid api_key {KEY}"}}',
        f"<p>Your key {KEY.replace('-', '&#45;')} is wrong, {KEY}</p>",
        f'{{"echo": "{KEY}", "url": "/v1?api_key={KEY}"}}',
    ],
)
def test_a_response_that_echoes_the_key_is_returned_without_it(body: str) -> None:
    network = web(ok(body.encode()))
    text = make(network).fetch("https://example.org/", credential=query())
    assert KEY not in text
    assert "[key]" in text


def test_a_snapshot_never_holds_a_key_the_server_echoed(tmp_path: Path) -> None:
    body = f'{{"error": "invalid api_key {KEY}"}}'.encode()
    source = keyed_source(source_id="fred", mechanism="api", url="https://example.org/x")
    results = capture_sources([source], make(web(ok(body))), tmp_path, [], lambda env: KEY)
    assert results[0].captured
    assert KEY not in (tmp_path / "fred.txt").read_text(encoding="utf-8")


def test_any_fetcher_has_an_echoed_key_removed() -> None:
    """fetch_source redacts too, so a fetcher other than SafeFetcher cannot store the key."""
    fetcher = KeyedFetcher(body=f"<rss><title>{KEY}</title></rss>")
    text = fetch_source(keyed_source(), fetcher, {"REGWATCH_KEY_ZZ": KEY}.get)
    assert KEY not in text and "[key]" in text


@pytest.mark.parametrize("padding", range(955, 975, 3))
def test_a_key_cut_by_the_message_limit_is_still_removed(padding: int) -> None:
    """The key is removed before the message is cut, so no half of it survives.

    The padding moves the key across the 1,000 character limit of the message.
    """

    def long_status(server: socket.socket) -> None:
        server.sendall(b"HTTP/1.1 XYZ " + b"x" * padding + KEY.encode() + b"\r\n\r\n")

    with pytest.raises(FetchError) as caught:
        make(web(long_status)).fetch("https://example.org/", credential=query())
    message = str(caught.value)
    assert KEY[:4] not in message
    assert len(message) <= 1000


def test_a_key_split_by_an_invisible_character_is_still_removed() -> None:
    """Cleaning removes a zero-width space, so the key is removed again after cleaning."""
    split = KEY[:4] + "​" + KEY[4:]
    error = FetchError(f"the server said {split}", redact=query().redact)
    assert KEY not in str(error)
    assert str(error) == "the server said [key]"


def test_fetch_source_redacts_an_error_from_any_fetcher() -> None:
    class Failing:
        def fetch(self, url: str, *, credential: Credential | None = None) -> str:
            raise FetchError(f"the server said {KEY}")

    with pytest.raises(FetchError) as caught:
        fetch_source(keyed_source(), Failing(), {"REGWATCH_KEY_ZZ": KEY}.get)
    assert str(caught.value) == "the server said [key]"
    assert caught.value.__cause__ is None


def test_a_credential_hides_its_value() -> None:
    credential = query()
    assert KEY not in repr(credential)
    assert Credential.from_auth("header:X-Key", KEY) == Credential("header", "X-Key", KEY)


@pytest.mark.parametrize(
    ("placement", "name", "value", "message"),
    [
        ("cookie", "k", KEY, "query"),
        ("query", "bad name", KEY, "1 to 64"),
        ("header", "Host", KEY, "Host header"),
        ("header", "user-agent", KEY, "header"),
        ("query", "k", "", "printable"),
        ("query", "k", "line\r\nX: y", "printable"),
        ("query", "k", "x" * 4097, "printable"),
    ],
)
def test_an_unsafe_credential_is_refused_without_repeating_the_key(
    placement: str, name: str, value: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message) as caught:
        Credential(placement, name, value)
    if len(value) > 3:
        assert value not in str(caught.value)


# --- capture and check ------------------------------------------------------------------


class KeyedFetcher:
    """Answers every URL, and records whether a credential came with it."""

    def __init__(self, body: str = "<rss><item><title>x</title></item></rss>") -> None:
        self.body = body
        self.seen: list[tuple[str, Credential | None]] = []

    def fetch(self, url: str, *, credential: Credential | None = None) -> str:
        self.seen.append((url, credential))
        return self.body


def keyed_source(**changes: Any) -> Source:
    values: dict[str, Any] = {
        "source_id": "zz-keyed",
        "jurisdiction": "zz",
        "name": "Keyed",
        "url": "https://api.example.org/v1",
        "method": "poll",
        "mechanism": "rss",
        "cadence": "daily",
        "notes": "",
        "auth": "query:api_key",
        "key_env": "REGWATCH_KEY_ZZ",
    }
    values.update(changes)
    return Source(**values)


def test_a_keyed_source_without_a_key_is_an_error_that_says_how_to_add_one() -> None:
    fetcher = KeyedFetcher()
    with pytest.raises(FetchError, match="regwatch keys set zz-keyed") as caught:
        fetch_source(keyed_source(), fetcher, lambda name: None)
    assert "REGWATCH_KEY_ZZ" in str(caught.value)
    with pytest.raises(FetchError, match="no key"):
        fetch_source(keyed_source(), fetcher)
    assert fetcher.seen == []


def test_a_keyed_source_gets_its_key_and_an_unkeyed_source_gets_none() -> None:
    fetcher = KeyedFetcher()
    fetch_source(keyed_source(), fetcher, {"REGWATCH_KEY_ZZ": KEY}.get)
    fetch_source(keyed_source(auth="", key_env=""), fetcher, {"REGWATCH_KEY_ZZ": KEY}.get)
    assert fetcher.seen[0][1] == query()
    assert fetcher.seen[1][1] is None


def test_an_unusable_stored_key_is_an_error_without_the_key() -> None:
    with pytest.raises(FetchError, match="cannot be used") as caught:
        fetch_source(keyed_source(), KeyedFetcher(), lambda name: "has space")
    assert "has space" not in str(caught.value)


def test_snapshots_and_check_results_never_hold_the_key(tmp_path: Path) -> None:
    source = keyed_source()
    fetcher = KeyedFetcher()
    lookup = {"REGWATCH_KEY_ZZ": KEY}.get
    captured = capture_sources([source], fetcher, tmp_path, [], lookup)
    assert captured[0].captured
    results = check_sources([source], {}, tmp_path, fetcher, lookup)
    assert results[0].status == "NEW"
    stored = "".join(p.read_text(encoding="utf-8") for p in tmp_path.rglob("*") if p.is_file())
    assert KEY not in stored
    assert KEY not in repr(results) + repr(captured)
    missing = check_sources([source], {}, tmp_path, fetcher, lambda name: None)
    assert missing[0].status == "ERROR"
    assert "regwatch keys set" in missing[0].detail
