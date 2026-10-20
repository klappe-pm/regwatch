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
