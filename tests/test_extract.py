from __future__ import annotations

import time

import pytest
from conftest import FIXTURES

from regwatch.extract import ExtractError, extract_signal, signal_hash

RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>t</title>
<item><title>B  item</title><link>https://x.example/b</link><guid>g2</guid><pubDate>d2</pubDate></item>
<item><title>A item</title><link>https://x.example/a</link><guid>g1</guid><pubDate>d1</pubDate></item>
</channel></rss>"""


def test_signal_hash_is_sha256_hex() -> None:
    assert signal_hash("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_plain_text_is_normalised() -> None:
    assert extract_signal("email-list", "line one  \r\nline two\r\n\r\n") == "line one\nline two"
    assert extract_signal("unknown-mechanism", "  keep  ") == "keep"


def test_html_strips_markup_script_and_style() -> None:
    page = (
        "<html><head><style>p{color:red}</style><script>alert('x')</script></head>"
        "<body><p>Hello <b>world</b> &amp; friends</p><!-- hidden --></body></html>"
    )
    assert extract_signal("html", page) == "Hello world & friends"


def test_html_signal_ignores_markup_only_changes() -> None:
    first = "<div><p>Rule   text</p></div>"
    second = "<section class='new'>\n<p>Rule text</p>\n</section>"
    assert extract_signal("html", first) == extract_signal("html", second)


def test_html_tolerates_unbalanced_tags() -> None:
    assert extract_signal("html", "</script><p>ok</style>") == "ok"
    assert extract_signal("html", "<script>never closed") == ""


def test_api_results_are_sorted_rows() -> None:
    body = (
        '{"results": [{"publication_date": "2026-01-02", "document_number": "2", "title": "B"},'
        ' {"publication_date": "2026-01-01", "document_number": "1", "title": "A"}]}'
    )
    reordered = (
        '{"results": [{"title": "A", "document_number": "1", "publication_date": "2026-01-01"},'
        ' {"title": "B", "document_number": "2", "publication_date": "2026-01-02"}], "count": 99}'
    )
    assert extract_signal("api", body) == "2026-01-01\t1\tA\n2026-01-02\t2\tB"
    assert extract_signal("api", reordered) == extract_signal("api", body)


def test_api_other_json_is_canonicalised() -> None:
    assert extract_signal("api", '{"b": 1,\n "a": [1, 2]}') == '{"a":[1,2],"b":1}'
    assert extract_signal("api", '{"results": []}') == '{"results":[]}'
    assert extract_signal("api", '{"results": [1, 2]}') == '{"results":[1,2]}'


def test_api_invalid_json_falls_back_to_text() -> None:
    assert extract_signal("api", "  not json  ") == "not json"


def test_api_deeply_nested_json_does_not_crash() -> None:
    assert extract_signal("api", "[" * 100_000) == "[" * 100_000


def test_rss_items_are_sorted_and_whitespace_normalised() -> None:
    signal = extract_signal("rss", RSS)
    assert signal.splitlines() == [
        "d1\tg1\thttps://x.example/a\tA item",
        "d2\tg2\thttps://x.example/b\tB item",
    ]


def test_atom_entries_use_href_and_updated() -> None:
    signal = extract_signal("rss", (FIXTURES / "feed-atom.xml").read_text(encoding="utf-8"))
    assert signal.splitlines() == [
        "2026-10-01T00:00:00Z\turn:example:1\thttps://regulator.example/first\tFirst entry",
        "2026-10-02T00:00:00Z\turn:example:2\thttps://regulator.example/second\tSecond entry",
    ]


def test_feed_with_no_items_has_an_empty_signal() -> None:
    assert extract_signal("rss", "<rss><channel><title>t</title></channel></rss>") == ""


def test_entity_expansion_document_is_refused_without_parsing() -> None:
    start = time.monotonic()
    with pytest.raises(ExtractError, match="DTD or entity"):
        extract_signal("rss", (FIXTURES / "feed-entity-bomb.xml").read_text(encoding="utf-8"))
    assert time.monotonic() - start < 1


@pytest.mark.parametrize(
    "document",
    [
        '<!DOCTYPE rss SYSTEM "file:///etc/passwd"><rss/>',
        "<!doctype rss><rss/>",
        '<?xml version="1.0"?><!ENTITY x "y"><rss/>',
        "<! DOCTYPE rss><rss/>",
    ],
)
def test_any_dtd_or_entity_declaration_is_refused(document: str) -> None:
    with pytest.raises(ExtractError):
        extract_signal("rss", document)


def test_malformed_xml_is_refused() -> None:
    with pytest.raises(ExtractError, match="not well-formed"):
        extract_signal("rss", "<rss><channel>")


def test_non_feed_xml_is_refused() -> None:
    with pytest.raises(ExtractError, match="not an RSS or Atom feed"):
        extract_signal("rss", "<html><body>hello</body></html>")


def test_extract_never_evaluates_content() -> None:
    marker = "__import__('os').system('exit 1')"
    assert extract_signal("api", f'{{"results": [{{"title": "{marker}"}}]}}').endswith(marker)
    assert marker in extract_signal("email-list", marker)
