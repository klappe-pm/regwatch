"""The fetch client's POST: a JSON body with the same checks, limits and deadline as a GET.

Every request goes over the fake network from test_fetch, built on socket pairs.
"""

from __future__ import annotations

import json

import pytest
from test_fetch import PUBLIC, Network, make, ok, redirect, web

from regwatch.fetch import MAX_POST_BYTES, Credential, FetchError

KEY = "fake" + "-post-" + "key-8812"


def body_of(request: bytes) -> dict[str, object]:
    return json.loads(request.split(b"\r\n\r\n", 1)[1])


def test_a_post_sends_json_and_returns_the_body() -> None:
    network = web(ok(b'{"ok": true}'))
    answer = make(network).post_json("https://example.org/v1/x", {"a": [1, "b"]})
    assert answer == '{"ok": true}'
    request = network.requests[0]
    assert request.startswith(b"POST /v1/x HTTP/1.1\r\n")
    assert b"Content-Type: application/json\r\n" in request
    assert body_of(request) == {"a": [1, "b"]}
    assert network.wrapped == ["example.org"]


def test_a_post_to_a_private_address_is_refused_like_a_get() -> None:
    network = web(hosts={"example.org": ["10.0.0.5"]})
    with pytest.raises(FetchError, match="non-public address"):
        make(network).post_json("https://example.org/", {})
    assert network.connected == []


@pytest.mark.parametrize(
    "url",
    ["http://example.org/", "ftp://example.org/", "file:///etc/passwd", "https://u:p@example.org/"],
)
def test_a_post_needs_https(url: str) -> None:
    network = web()
    with pytest.raises(FetchError):
        make(network, allow_private_hosts=True).post_json(url, {})
    assert network.connected == []


def test_plain_http_goes_only_to_loopback_with_allow_private_hosts() -> None:
    network = Network({}, [ok(b"{}")])
    with pytest.raises(FetchError, match="allow_private_hosts"):
        make(network).post_json("http://127.0.0.1:11434/api/chat", {})
    assert (
        make(network, allow_private_hosts=True).post_json(
            "http://127.0.0.1:11434/api/chat", {"m": 1}
        )
        == "{}"
    )
    assert network.connected == [("127.0.0.1", 11434)]
    # No TLS on loopback, and the Host header names the address and port.
    assert network.wrapped == []
    assert b"Host: 127.0.0.1:11434\r\n" in network.requests[0]


@pytest.mark.parametrize(
    "url", ["http://localhost:11434/", "http://10.0.0.5/", "http://[::2]/", "http://example.org/"]
)
def test_plain_http_to_a_name_or_another_address_is_refused(url: str) -> None:
    network = web(hosts={"localhost": ["127.0.0.1"], "example.org": [PUBLIC]})
    with pytest.raises(FetchError, match=r"only to 127\.0\.0\.1"):
        make(network, allow_private_hosts=True).post_json(url, {})
    assert network.connected == []


def test_a_key_is_never_sent_over_plain_http() -> None:
    network = Network({}, [ok()])
    credential = Credential("header", "x-api-key", KEY)
    with pytest.raises(FetchError, match="only over https"):
        make(network, allow_private_hosts=True).post_json(
            "http://127.0.0.1:11434/", {}, credential=credential
        )
    assert network.connected == []


def test_a_post_follows_no_redirect() -> None:
    network = web(redirect("https://example.org/other"))
    with pytest.raises(FetchError, match="not redirected"):
        make(network).post_json("https://example.org/", {})
    assert len(network.requests) == 1


def test_a_bearer_key_is_sent_in_its_header_and_kept_out_of_errors_and_bodies() -> None:
    credential = Credential("header", "Authorization", KEY, scheme="Bearer")
    network = web(ok(f'{{"echo": "{KEY}"}}'.encode()))
    answer = make(network).post_json("https://example.org/", {}, credential=credential)
    assert KEY not in answer and "[key]" in answer
    assert f"Authorization: Bearer {KEY}\r\n".encode() in network.requests[0]
    failing = web(f"HTTP/1.1 401 {KEY}\r\nContent-Length: 0\r\n\r\n".encode())
    with pytest.raises(FetchError) as caught:
        make(failing).post_json("https://example.org/", {}, credential=credential)
    assert KEY not in str(caught.value) and caught.value.__cause__ is None


def test_extra_headers_cannot_replace_or_split_a_header() -> None:
    network = web()
    for headers in ({"Host": "evil.example"}, {"Content-Type": "text/plain"}, {"X-A": "1\r\nB: 2"}):
        with pytest.raises(FetchError):
            make(network).post_json("https://example.org/", {}, headers=headers)
    with pytest.raises(FetchError):
        make(network).post_json("https://example.org/", {}, headers={"Bad Name": "x"})
    assert network.connected == []


def test_extra_headers_are_sent() -> None:
    network = web(ok())
    make(network).post_json("https://example.org/", {}, headers={"anthropic-version": "1"})
    assert b"anthropic-version: 1\r\n" in network.requests[0]


def test_the_body_and_the_answer_are_size_limited() -> None:
    network = web(ok(b"x" * 2000))
    with pytest.raises(FetchError, match="request body is larger"):
        make(network).post_json("https://example.org/", {"a": "x" * MAX_POST_BYTES})
    with pytest.raises(FetchError, match="larger than the limit"):
        make(network, max_bytes=1000).post_json("https://example.org/", {})
    with pytest.raises(FetchError, match="cannot be written as JSON"):
        make(network).post_json("https://example.org/", {"a": object()})


def test_a_key_scheme_is_letters_only_and_only_for_a_header() -> None:
    with pytest.raises(ValueError, match="scheme"):
        Credential("header", "Authorization", KEY, scheme="Bearer x")
    with pytest.raises(ValueError, match="scheme"):
        Credential("query", "key", KEY, scheme="Bearer")
    with pytest.raises(ValueError, match="Content-Type"):
        Credential("header", "Content-Type", KEY)
    assert Credential("header", "X-K", KEY).header_value == KEY


def test_a_post_url_with_a_control_character_or_bad_port_is_refused() -> None:
    network = web()
    for url in ("https://example.org/\x00", "https://example.org:99999/"):
        with pytest.raises(FetchError):
            make(network).post_json(url, {})
    assert network.connected == []
