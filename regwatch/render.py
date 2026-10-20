"""Render a Document into delivery formats.

Four formats are produced from the one document model: Markdown, a web post
(Markdown with front matter), an email newsletter (HTML plus a plain text
alternative) and a Word document. A ``.docx`` file is a zip of WordprocessingML
parts and is built here directly, so no document library is needed.

HTML and Word output escape every piece of text. Markdown output backslash-escapes
every Markdown metacharacter, so a value renders as literal text and can never
become a link, an image, raw HTML, a heading, a list item or a horizontal rule, and
the punctuation that makes a renderer link bare text is escaped too. Plain text carries
text as it is. Every value first loses its control characters, which removes
terminal escape sequences. Every format ends with the disclaimer.
"""

from __future__ import annotations

import html
import io
import json
import re
import zipfile
from collections.abc import Sequence
from xml.sax.saxutils import escape as xml_escape

from regwatch.document import Document
from regwatch.sanitize import clean_text, escape_markdown

__all__ = [
    "FORMATS",
    "TAG_RE",
    "docx_bytes",
    "render_document_xml",
    "render_markdown",
    "render_newsletter_html",
    "render_newsletter_text",
    "render_webpost",
]

FORMATS = ("md", "web", "newsletter", "docx")
TAG_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
_XML_INVALID = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")


def _line(text: str) -> str:
    """One clean line: control characters and lone surrogates removed, whitespace collapsed."""
    return clean_text(text)


def _md(text: str) -> str:
    """One clean line with Markdown metacharacters escaped."""
    return escape_markdown(clean_text(text))


def render_markdown(doc: Document) -> str:
    """Render ``doc`` as Markdown. Every value is escaped, so it renders as literal text."""
    lines = [f"# {_md(doc.title)}", ""]
    if doc.subtitle:
        lines += [f"_{_md(doc.subtitle)}_", ""]
    lines += [f"Generated {_md(doc.generated)}.", ""]
    for section in doc.sections:
        lines += ["#" * section.level + f" {_md(section.heading)}", ""]
        for paragraph in section.paragraphs:
            lines += [_md(paragraph), ""]
        for bullet in section.bullets:
            lines.append(f"- {_md(bullet)}")
        if section.bullets:
            lines.append("")
    lines += ["---", "", f"> {_md(doc.disclaimer)}", ""]
    return "\n".join(lines).rstrip() + "\n"


def render_webpost(doc: Document, tags: Sequence[str]) -> str:
    """Render ``doc`` as a draft web post: Markdown with YAML front matter.

    Raises ValueError for a tag that is not made of letters, digits, hyphens and underscores.
    """
    for tag in tags:
        if not TAG_RE.fullmatch(tag):
            raise ValueError(f"invalid tag '{tag}'")
    front = [
        "---",
        f"title: {json.dumps(_line(doc.title))}",
        f"date: {json.dumps(_line(doc.generated))}",
        f"summary: {json.dumps(_line(doc.subtitle))}",
        "tags:",
        *[f"  - {tag}" for tag in tags],
        "draft: true",
        "---",
        "",
        "",
    ]
    return "\n".join(front) + render_markdown(doc)


def render_newsletter_text(doc: Document) -> str:
    """Render ``doc`` as the plain text alternative of the newsletter."""
    lines = [_line(doc.title)]
    if doc.subtitle:
        lines.append(_line(doc.subtitle))
    lines += [f"Generated {_line(doc.generated)}.", ""]
    for section in doc.sections:
        lines += [_line(section.heading).upper(), ""]
        for paragraph in section.paragraphs:
            lines += [_line(paragraph), ""]
        for bullet in section.bullets:
            lines.append(f"  * {_line(bullet)}")
        if section.bullets:
            lines.append("")
    lines += ["-----", _line(doc.disclaimer)]
    return "\n".join(lines).rstrip() + "\n"


def render_newsletter_html(doc: Document) -> str:
    """Render ``doc`` as a self-contained HTML email. All text is HTML-escaped."""
    esc = html.escape
    body = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        f"<title>{esc(_line(doc.title))}</title></head>",
        '<body style="margin:0;padding:0;background:#f4f4f4;">',
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;">',
        '<tr><td align="center" style="padding:24px 12px;">',
        '<table role="presentation" width="640" cellpadding="0" cellspacing="0" '
        'style="background:#ffffff;font-family:Helvetica,Arial,sans-serif;color:#1a1a1a;">',
        '<tr><td style="padding:28px 32px 8px 32px;">',
        f'<h1 style="margin:0;font-size:22px;line-height:1.3;">{esc(_line(doc.title))}</h1>',
    ]
    if doc.subtitle:
        body.append(
            f'<p style="margin:6px 0 0 0;color:#555;font-size:14px;">{esc(_line(doc.subtitle))}</p>'
        )
    body.append(
        f'<p style="margin:6px 0 0 0;color:#888;font-size:12px;">Generated {esc(_line(doc.generated))}.</p>'
    )
    body.append("</td></tr>")
    for section in doc.sections:
        body.append('<tr><td style="padding:16px 32px 0 32px;">')
        body.append(
            '<h2 style="margin:0 0 8px 0;font-size:16px;border-bottom:1px solid #eee;padding-bottom:4px;">'
            f"{esc(_line(section.heading))}</h2>"
        )
        for paragraph in section.paragraphs:
            body.append(
                f'<p style="margin:0 0 10px 0;font-size:14px;line-height:1.5;">{esc(_line(paragraph))}</p>'
            )
        if section.bullets:
            body.append(
                '<ul style="margin:0 0 10px 0;padding-left:20px;font-size:14px;line-height:1.5;">'
            )
            body += [f"<li>{esc(_line(bullet))}</li>" for bullet in section.bullets]
            body.append("</ul>")
        body.append("</td></tr>")
    body += [
        '<tr><td style="padding:16px 32px 28px 32px;">',
        '<p style="margin:0;color:#444;font-size:12px;line-height:1.4;border-top:1px solid #eee;padding-top:12px;">'
        f"{esc(_line(doc.disclaimer))}</p>",
        "</td></tr>",
        "</table></td></tr></table></body></html>",
    ]
    return "\n".join(body) + "\n"


# --- docx --------------------------------------------------------------------

_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    "</Types>"
)

_ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="word/document.xml"/>'
    "</Relationships>"
)

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _para(text: str, *, bold: bool = False, size: int | None = None, bullet: bool = False) -> str:
    properties = "<w:b/>" if bold else ""
    if size is not None:
        properties += f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
    run_properties = f"<w:rPr>{properties}</w:rPr>" if properties else ""
    prefix = "•  " if bullet else ""
    clean = _XML_INVALID.sub("", prefix + _line(text))
    run = f'<w:r>{run_properties}<w:t xml:space="preserve">{xml_escape(clean)}</w:t></w:r>'
    return f'<w:p><w:pPr><w:spacing w:after="120"/></w:pPr>{run}</w:p>'


def render_document_xml(doc: Document) -> str:
    """Return the ``word/document.xml`` part for ``doc``."""
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        f'<w:document xmlns:w="{_W}"><w:body>',
        _para(doc.title, bold=True, size=36),
    ]
    if doc.subtitle:
        parts.append(_para(doc.subtitle, size=22))
    parts.append(_para(f"Generated {doc.generated}.", size=18))
    for section in doc.sections:
        parts.append(_para(section.heading, bold=True, size=28 if section.level <= 2 else 24))
        parts += [_para(paragraph) for paragraph in section.paragraphs]
        parts += [_para(bullet, bullet=True) for bullet in section.bullets]
    parts.append(_para(doc.disclaimer, size=18))
    parts.append("<w:sectPr/></w:body></w:document>")
    return "".join(parts)


def docx_bytes(doc: Document) -> bytes:
    """Return ``doc`` as the bytes of a ``.docx`` file."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        archive.writestr("_rels/.rels", _ROOT_RELS)
        archive.writestr("word/document.xml", render_document_xml(doc))
    return buffer.getvalue()
