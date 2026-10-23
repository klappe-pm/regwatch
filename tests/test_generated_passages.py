"""Generated passages in the document model: kept with their facts, labelled and escaped."""

from __future__ import annotations

import io
import zipfile

import pytest

from regwatch.document import Document, DocumentError, GeneratedPassage, Section
from regwatch.render import (
    FACTS_LABEL,
    docx_bytes,
    passage_html,
    render_markdown,
    render_newsletter_html,
    render_newsletter_text,
)
from regwatch.sanitize import escape_markdown

HOSTILE = "<script>alert(1)</script> [x](https://evil.example) **bold**"
PASSAGE = GeneratedPassage(
    text=HOSTILE,
    cites=["change:a"],
    facts=["change:a: Source <b>A</b> changed"],
    provider="anthropic",
    model="claude-opus-5-5",
)


def document() -> Document:
    return Document(
        "Title",
        "2026-10-19",
        sections=[Section("Changes", paragraphs=["Fixed."], generated=[PASSAGE])],
    )


def test_a_passage_round_trips_through_the_model() -> None:
    doc = document()
    data = doc.to_dict()
    assert data["sections"][0]["generated"][0]["cites"] == ["change:a"]
    assert Document.from_dict(data) == doc
    plain = Document("T", "g", sections=[Section("H")]).to_dict()
    assert "generated" not in plain["sections"][0]


@pytest.mark.parametrize(
    "generated",
    [
        "x",
        [1],
        [{"cites": []}],
        [{"text": "t", "cites": "x"}],
        [{"text": "t", "facts": [1]}],
        [{"text": "t"}] * 201,
    ],
)
def test_a_malformed_passage_is_refused(generated: object) -> None:
    data = {"title": "T", "generated": "g", "sections": [{"heading": "H", "generated": generated}]}
    with pytest.raises(DocumentError):
        Document.from_dict(data)


def test_markdown_labels_the_passage_and_lists_its_facts_escaped() -> None:
    text = render_markdown(document())
    assert "Generated: " in text and f"{FACTS_LABEL}:" in text
    assert f"Generated: {escape_markdown(HOSTILE)}" in text
    assert "\\<script\\>" in text and "\\<b\\>" in text


def test_html_labels_the_passage_and_escapes_it() -> None:
    page = render_newsletter_html(document())
    assert ">Generated</span>" in page and "<script>" not in page
    assert "&lt;script&gt;" in page and "&lt;b&gt;A&lt;/b&gt;" in page
    block = passage_html(GeneratedPassage("t"))
    assert FACTS_LABEL not in block


def test_text_and_word_carry_the_label_and_the_facts() -> None:
    text = render_newsletter_text(document())
    assert "[Generated] <script>" in text and "from change:a: Source <b>A</b> changed" in text
    with zipfile.ZipFile(io.BytesIO(docx_bytes(document()))) as archive:
        body = archive.read("word/document.xml").decode()
    assert "Generated: &lt;script&gt;" in body and "<w:i/>" in body
    assert "From change:a" in body
