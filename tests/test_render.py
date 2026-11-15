from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile

import pytest

from regwatch.document import DISCLAIMER, Document, Section
from regwatch.render import (
    FORMATS,
    docx_bytes,
    render_document_xml,
    render_markdown,
    render_newsletter_html,
    render_newsletter_text,
    render_webpost,
)

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def sample(**changes: object) -> Document:
    doc = Document(
        title="Weekly <brief>",
        generated="2026-10-19",
        subtitle="Candidates & notes",
        sections=[
            Section("Changes", paragraphs=["One paragraph."], bullets=["first", "second"]),
            Section("Detail", level=3, paragraphs=["Deeper."]),
        ],
    )
    for key, value in changes.items():
        setattr(doc, key, value)
    return doc


def test_formats() -> None:
    assert FORMATS == ("md", "web", "newsletter", "docx")


def test_markdown() -> None:
    text = render_markdown(sample())
    assert text.startswith(
        "# Weekly \\<brief\\>\n\n_Candidates \\& notes_\n\nPrepared 19 October 2026.\n\n"
        "## Changes\n\n"
    )
    assert "One paragraph.\n\n- first\n- second\n\n### Detail\n\nDeeper.\n" in text
    assert text.endswith(f"---\n\n> {DISCLAIMER}\n")


def test_markdown_values_cannot_start_new_structure() -> None:
    doc = sample(title="Title\n# injected heading")
    doc.sections[0].bullets = ["item\n- extra item", "line one\n\n## sneaky"]
    doc.sections[0].paragraphs = ["para\n# not a heading"]
    text = render_markdown(doc)
    assert "\n# injected" not in text
    assert "\n## sneaky" not in text
    assert "\n- extra item" not in text
    assert "\n# not a heading" not in text
    assert "# Title \\# injected heading" in text


def test_markdown_without_subtitle() -> None:
    assert "_" not in render_markdown(sample(subtitle="")).split("Generated")[0]


def test_html_escapes_everything() -> None:
    doc = sample(title="<script>alert(1)</script>", subtitle='"quoted" & <b>')
    doc.sections[0].paragraphs = ["<img src=x onerror=alert(1)>"]
    doc.sections[0].bullets = ["<a href='javascript:alert(1)'>x</a>"]
    doc.sections[0].heading = "<h2>"
    html_text = render_newsletter_html(doc)
    for fragment in ("<script", "<img", "<a href", "<b>"):
        assert fragment not in html_text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_text
    assert "&lt;img src=x onerror=alert(1)&gt;" in html_text
    assert html_text.count("<h1") == 1
    assert "&quot;quoted&quot; &amp; &lt;b&gt;" in html_text


def test_html_structure_and_disclaimer() -> None:
    html_text = render_newsletter_html(sample())
    assert html_text.startswith("<!doctype html>")
    assert "<li>first</li>" in html_text
    assert DISCLAIMER in html_text
    parsed = ET.fromstring(
        html_text.split("\n", 1)[1].replace('<meta charset="utf-8">', '<meta charset="utf-8"/>')
    )
    assert parsed.tag == "html"


def test_html_without_subtitle_or_bullets() -> None:
    doc = Document("T", "2026-01-01", sections=[Section("Only", paragraphs=["p"])])
    html_text = render_newsletter_html(doc)
    assert "<ul" not in html_text
    assert "color:#555" not in html_text


def test_newsletter_text() -> None:
    text = render_newsletter_text(sample())
    assert text.splitlines()[:3] == [
        "Weekly <brief>",
        "Candidates & notes",
        "Prepared 19 October 2026.",
    ]
    assert "CHANGES\n\nOne paragraph.\n\n  * first\n  * second\n" in text
    assert text.rstrip().endswith(DISCLAIMER)


def test_webpost_front_matter() -> None:
    text = render_webpost(sample(title='He said: "hi"\nnext: line'), ["regulatory", "weekly_1"])
    front, _, body = text.partition("\n---\n\n")
    lines = front.splitlines()
    assert lines[0] == "---"
    assert lines[1] == 'title: "He said: \\"hi\\" next: line"'
    assert lines[2] == 'date: "2026-10-19"'
    assert lines[3] == 'summary: "Candidates & notes"'
    assert lines[4:] == ["tags:", "  - regulatory", "  - weekly_1", "draft: true"]
    assert body.startswith("# He said")


@pytest.mark.parametrize(
    "tag", ["has space", "semi;colon", "new\nline", "", "x" * 41, "tag: injected"]
)
def test_webpost_rejects_unsafe_tags(tag: str) -> None:
    with pytest.raises(ValueError, match="invalid tag"):
        render_webpost(sample(), [tag])


def test_docx_is_a_valid_package() -> None:
    data = docx_bytes(sample())
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert sorted(archive.namelist()) == [
            "[Content_Types].xml",
            "_rels/.rels",
            "word/_rels/document.xml.rels",
            "word/document.xml",
            "word/styles.xml",
        ]
        for name in archive.namelist():
            ET.fromstring(archive.read(name))
        document = ET.fromstring(archive.read("word/document.xml"))
    texts = ["".join(t.text or "" for t in p.iter(f"{W}t")) for p in document.iter(f"{W}p")]
    assert texts[0] == "Weekly <brief>"
    assert "•  first" in texts
    assert texts[-1] == DISCLAIMER


def test_docx_survives_markup_and_control_characters() -> None:
    doc = sample(title="A & B <c> \x00\x07 end")
    doc.sections[0].bullets = ["]]> <w:p> \x0b tail"]
    xml_text = render_document_xml(doc)
    document = ET.fromstring(xml_text)
    texts = ["".join(t.text or "" for t in p.iter(f"{W}t")) for p in document.iter(f"{W}p")]
    assert texts[0] == "A & B <c> end"
    assert "•  ]]> <w:p> tail" in texts


def test_every_format_carries_the_disclaimer() -> None:
    doc = Document.from_dict({"title": "T", "generated": "g", "sections": [], "disclaimer": ""})
    assert DISCLAIMER in render_markdown(doc)
    assert DISCLAIMER in render_webpost(doc, [])
    assert DISCLAIMER in render_newsletter_html(doc)
    assert DISCLAIMER in render_newsletter_text(doc)
    assert DISCLAIMER in render_document_xml(doc)
