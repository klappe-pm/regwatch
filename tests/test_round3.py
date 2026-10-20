"""Regression tests for the third verification round (regwatch only)."""

from __future__ import annotations

import time

import pytest

# --- rw3-01: the code span check takes time in line with the input --------------------------


def test_escape_markdown_of_one_long_word_is_fast() -> None:
    from regwatch.sanitize import escape_markdown

    started = time.perf_counter()
    assert escape_markdown("a" * 200_000) == "a" * 200_000
    assert time.perf_counter() - started < 1.0


def test_rendering_a_one_mebibyte_word_is_bounded() -> None:
    from regwatch.document import Document, Section
    from regwatch.render import render_markdown

    word = "a" * (1024 * 1024)
    doc = Document("T", "2026-10-20", sections=[Section("S", paragraphs=[word], bullets=[word])])
    started = time.perf_counter()
    assert word in render_markdown(doc)
    assert time.perf_counter() - started < 5.0


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("a:b", "`a:b`"),
        ("1a:b", "`1a:b`"),
        ("x.y-z+q:r", "`x.y-z+q:r`"),
        ("tel:+15551234567", "`tel:+15551234567`"),
        ("a@b", "`a@b`"),
        ("12:30", "12:30"),
        ("10:30:45", "10:30:45"),
        ("Note:", "Note:"),
        ("a::b", "a::b"),
        ("1.5:2", "1\\.5:2"),
    ],
)
def test_the_code_span_choice_is_unchanged(value: str, expected: str) -> None:
    from regwatch.sanitize import escape_markdown

    assert escape_markdown(value) == expected


# --- rw3-02: a dot after a mark, a vowel sign, an emoji or a symbol is escaped too -----------

LINKIFY_VALUES = [
    "visit हिन्दी.com today",
    "visit é.com today",
    "visit \xe9.com today",
    "\U0001f600.com",
    "™.com",
    "தமிழ்.com",
]


def _markdown_for(value: str) -> str:
    from regwatch.document import Document, Section
    from regwatch.render import render_markdown

    doc = Document("T", "2026-10-20", sections=[Section("S", paragraphs=[value], bullets=[value])])
    return render_markdown(doc)


@pytest.mark.parametrize("value", LINKIFY_VALUES)
def test_markdown_it_with_linkify_links_none_of_them(value: str) -> None:
    markdown_it = pytest.importorskip("markdown_it")
    pytest.importorskip("linkify_it")
    html = markdown_it.MarkdownIt("gfm-like").render(_markdown_for(value))
    assert "<a " not in html, html


@pytest.mark.parametrize("value", LINKIFY_VALUES)
def test_cmark_gfm_links_none_of_them(value: str) -> None:
    cmarkgfm = pytest.importorskip("cmarkgfm")
    from cmarkgfm.cmark import Options

    html = cmarkgfm.github_flavored_markdown_to_html(
        _markdown_for(value), options=Options.CMARK_OPT_UNSAFE
    )
    assert "<a" not in html, html


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("é.com", "é\\.com"),
        ("™.com", "™\\.com"),
        ("a.", "a."),
        ("The end.", "The end."),
        ("a..b", "a\\.\\.b"),
        ("www.", "www\\."),
    ],
)
def test_every_dot_before_a_non_space_character_is_escaped(value: str, expected: str) -> None:
    from regwatch.sanitize import escape_markdown

    assert escape_markdown(value) == expected


# --- rw3-03: a name the idna codec would map to a different name is refused ------------------


@pytest.mark.parametrize(
    ("url", "mapped"),
    [
        ("https://faß.de/", "fass.de"),
        ("https://straße.de/", "strasse.de"),
        ("https://pay‍pal.example/", "paypal.example"),
        ("https://exa­mple.com/", "example.com"),
        ("https://οδος.gr/", "xn--pxavbq.gr"),
    ],
)
def test_a_name_that_the_idna_codec_maps_to_another_name_is_refused(url: str, mapped: str) -> None:
    from test_fetch import make, ok, web

    from regwatch.fetch import FetchError

    network = web(ok(), hosts={mapped: ["93.184.216.34"]})
    with pytest.raises(FetchError, match="host name cannot be encoded"):
        make(network).fetch(url)
    assert network.resolved == []
    assert network.connected == []


@pytest.mark.parametrize(
    "url",
    [
        "https://пример.рф/",
        "https://пример。рф/",
        "https://пример．рф/",  # noqa: RUF001
        "https://пример｡рф/",
        "https://ПРИМЕР.рф/",
    ],
)
def test_a_name_that_survives_the_round_trip_is_still_fetched(url: str) -> None:
    from test_fetch import make, ok, web

    ascii_host = "xn--e1afmkfd.xn--p1ai"
    network = web(ok(b"hi"), hosts={ascii_host: ["93.184.216.34"]})
    assert make(network).fetch(url) == "hi"
    assert network.resolved == [ascii_host]


# --- rw3-04: every embedded IPv4 address must be public -------------------------------------


@pytest.mark.parametrize(
    "address",
    [
        "2002:808:808::200:5efe:7f00:1",
        "2002:808:808::5efe:a00:1",
        "2002:7f00:1::200:5efe:808:808",
        "2002:a9fe:a9fe::5efe:808:808",
    ],
)
def test_an_address_with_two_embedded_forms_needs_both_to_be_public(address: str) -> None:
    from regwatch.fetch import is_public_address

    assert is_public_address(address) is False


def test_an_address_with_two_embedded_forms_passes_when_both_are_public() -> None:
    from regwatch.fetch import is_public_address

    assert is_public_address("2002:808:808::200:5efe:808:808")
