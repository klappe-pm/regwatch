"""Render a Document into delivery formats.

Five formats are produced from the one document model: Markdown, a web post
(Markdown with front matter), an email newsletter (HTML plus a plain text
alternative), a designed HTML document with a print stylesheet, and a Word
document. A ``.docx`` file is a zip of WordprocessingML parts, with a styles part
that carries the colours and font of the design specification, and is built here
directly, so no document library is needed.

HTML and Word output escape every piece of text. Markdown output backslash-escapes
every Markdown metacharacter, so a value renders as literal text and can never
become a link, an image, raw HTML, a heading, a list item or a horizontal rule, and
the punctuation that makes a renderer link bare text is escaped too. Plain text carries
text as it is. Every value first loses its control characters, which removes
terminal escape sequences. Every format ends with the disclaimer.

A generated passage is rendered in every format with a plain "Generated" label and
the facts it was written from beneath it, escaped like every other value.
"""

from __future__ import annotations

import html
import io
import json
import re
import zipfile
from collections.abc import Sequence
from xml.sax.saxutils import escape as xml_escape

from regwatch.config import DocumentDesign
from regwatch.design import Logo
from regwatch.document import GENERATED_LABEL, Document, GeneratedPassage
from regwatch.sanitize import clean_text, escape_markdown

__all__ = [
    "FACTS_LABEL",
    "FORMATS",
    "TAG_RE",
    "docx_bytes",
    "passage_html",
    "render_document_html",
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


FACTS_LABEL = "Written from these facts"


def _passage_markdown(passage: GeneratedPassage) -> list[str]:
    lines = [f"{GENERATED_LABEL}: {_md(passage.text)}", ""]
    if passage.facts:
        lines += [f"{FACTS_LABEL}:", ""]
        lines += [f"- {_md(fact)}" for fact in passage.facts]
        lines.append("")
    return lines


def render_markdown(doc: Document) -> str:
    """Render ``doc`` as Markdown. Every value is escaped, so it renders as literal text."""
    lines = [f"# {_md(doc.title)}", ""]
    if doc.subtitle:
        lines += [f"_{_md(doc.subtitle)}_", ""]
    lines += [f"Generated {_md(doc.generated)}.", ""]
    for section in doc.sections:
        lines += ["#" * section.level + f" {_md(section.heading)}", ""]
        for passage in section.generated:
            lines += _passage_markdown(passage)
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
        for passage in section.generated:
            lines += [f"[{GENERATED_LABEL}] {_line(passage.text)}"]
            lines += [f"    from {_line(fact)}" for fact in passage.facts]
            lines.append("")
        for paragraph in section.paragraphs:
            lines += [_line(paragraph), ""]
        for bullet in section.bullets:
            lines.append(f"  * {_line(bullet)}")
        if section.bullets:
            lines.append("")
    lines += ["-----", _line(doc.disclaimer)]
    return "\n".join(lines).rstrip() + "\n"


def passage_html(passage: GeneratedPassage, tag_color: str = "#4b5866") -> str:
    """One generated passage as an HTML block with inline styles: the label, the text, the facts.

    Every piece of text is escaped. The label is a quiet bordered tag, so a reader
    sees at once that a model wrote the text, and the facts follow in a smaller size.
    """
    esc = html.escape
    parts = [
        '<div style="margin:0 0 12px 0;padding:8px 10px;border-left:3px solid #d6dee7;">',
        '<p style="margin:0 0 6px 0;font-size:14px;line-height:1.5;">'
        f'<span style="display:inline-block;margin-right:6px;padding:0 4px;border:1px solid '
        f'{tag_color};color:{tag_color};font-size:11.5px;line-height:16px;letter-spacing:0.02em;">'
        f"{GENERATED_LABEL}</span>{esc(_line(passage.text))}</p>",
    ]
    if passage.facts:
        parts.append(
            f'<p style="margin:0;color:#4b5866;font-size:12px;line-height:1.4;">{FACTS_LABEL}:</p>'
        )
        parts.append(
            '<ul style="margin:2px 0 0 0;padding-left:18px;color:#4b5866;font-size:12px;'
            'line-height:1.4;">'
        )
        parts += [f"<li>{esc(_line(fact))}</li>" for fact in passage.facts]
        parts.append("</ul>")
    parts.append("</div>")
    return "".join(parts)


def render_newsletter_html(doc: Document) -> str:
    """Render ``doc`` as a self-contained HTML email. All text is HTML-escaped."""
    esc = html.escape
    body = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        f"<title>{esc(_line(doc.title))}</title></head>",
        '<body style="margin:0;padding:0;background:#f4f4f4;">',
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="background:#f4f4f4;">',
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
        '<p style="margin:6px 0 0 0;color:#888;font-size:12px;">'
        f"Generated {esc(_line(doc.generated))}.</p>"
    )
    body.append("</td></tr>")
    for section in doc.sections:
        body.append('<tr><td style="padding:16px 32px 0 32px;">')
        body.append(
            '<h2 style="margin:0 0 8px 0;font-size:16px;border-bottom:1px solid #eee;'
            'padding-bottom:4px;">'
            f"{esc(_line(section.heading))}</h2>"
        )
        body += [passage_html(passage) for passage in section.generated]
        for paragraph in section.paragraphs:
            body.append(
                '<p style="margin:0 0 10px 0;font-size:14px;line-height:1.5;">'
                f"{esc(_line(paragraph))}</p>"
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
        '<p style="margin:0;color:#444;font-size:12px;line-height:1.4;'
        'border-top:1px solid #eee;padding-top:12px;">'
        f"{esc(_line(doc.disclaimer))}</p>",
        "</td></tr>",
        "</table></td></tr></table></body></html>",
    ]
    return "\n".join(body) + "\n"


# --- designed HTML document ----------------------------------------------------

PAGE_CSS = {"a4": "A4", "letter": "letter"}
_INK = "#17212b"
_MUTED = "#4b5866"
_LINE = "#d6dee7"


def _document_css(design: DocumentDesign) -> str:
    """The style sheet of a designed document. Every value comes from the checked design."""
    primary, accent = design.primary_color, design.accent_color
    return f"""
@page {{ size: {PAGE_CSS[design.page_size]}; margin: 18mm 16mm; }}
html {{ background: #ffffff; }}
body {{ margin: 0; color: {_INK}; background: #ffffff; font-family: {design.font_stack};
  font-size: 15px; line-height: 1.55; }}
.page {{ max-width: 760px; margin: 0 auto; padding: 32px 24px 48px; }}
.running {{ margin: 0 0 12px; color: {_MUTED}; font-size: 12.5px; }}
.masthead {{ display: flex; align-items: center; gap: 16px; padding-bottom: 12px;
  border-bottom: 3px solid {primary}; }}
.logo {{ display: block; max-width: 200px; max-height: 56px; }}
h1 {{ margin: 0; color: {primary}; font-size: 28px; line-height: 1.25; }}
.subtitle {{ margin: 4px 0 0; color: {_MUTED}; }}
.date {{ margin: 12px 0 0; color: {_MUTED}; font-size: 13px; }}
h2 {{ margin: 28px 0 10px; padding-bottom: 4px; color: {primary}; font-size: 20px;
  border-bottom: 2px solid {accent}; }}
h3, h4 {{ margin: 20px 0 6px; color: {primary}; font-size: 16.5px; }}
p {{ margin: 0 0 10px; }}
ul {{ margin: 0 0 10px; padding-left: 22px; }}
li {{ margin: 0 0 4px; }}
.generated {{ margin: 0 0 12px; padding: 6px 12px; border-left: 3px solid {_LINE}; }}
.generated p {{ margin: 0 0 6px; }}
.tag {{ display: inline-block; margin-right: 6px; padding: 0 4px; border: 1px solid {_MUTED};
  color: {_MUTED}; font-size: 11.5px; line-height: 16px; }}
.facts {{ color: {_MUTED}; font-size: 13px; }}
.facts ul {{ margin: 2px 0 0; }}
.closing {{ margin-top: 32px; padding-top: 12px; border-top: 1px solid {_LINE};
  color: {_MUTED}; font-size: 13px; }}
@media print {{
  .page {{ max-width: none; padding: 0; }}
  h2, h3, h4 {{ break-after: avoid; }}
  .generated, li {{ break-inside: avoid; }}
}}
""".strip()


def _passage_block(passage: GeneratedPassage) -> str:
    esc = html.escape
    parts = [
        '<div class="generated">',
        f'<p><span class="tag">{GENERATED_LABEL}</span>{esc(_line(passage.text))}</p>',
    ]
    if passage.facts:
        parts.append(f'<div class="facts">{FACTS_LABEL}:<ul>')
        parts += [f"<li>{esc(_line(fact))}</li>" for fact in passage.facts]
        parts.append("</ul></div>")
    parts.append("</div>")
    return "".join(parts)


def render_document_html(
    doc: Document, design: DocumentDesign | None = None, logo: Logo | None = None
) -> str:
    """Render ``doc`` as a standalone HTML page that follows ``design``.

    The page carries its style sheet, including a print stylesheet with the page
    size, so printing it from a browser makes the PDF. The logo, PNG or SVG, is an
    inline ``data:`` image. Every piece of text is escaped.
    """
    design = design or DocumentDesign()
    esc = html.escape
    out = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{esc(_line(doc.title))}</title>",
        f"<style>\n{_document_css(design)}\n</style>",
        '</head><body><main class="page">',
    ]
    if design.header:
        out.append(f'<p class="running">{esc(_line(design.header))}</p>')
    out.append('<header class="masthead">')
    if logo is not None:
        out.append(
            f'<img class="logo" src="{logo.data_uri}" alt="{esc(_line(design.organisation))}">'
        )
    out.append(f"<div><h1>{esc(_line(doc.title))}</h1>")
    if doc.subtitle:
        out.append(f'<p class="subtitle">{esc(_line(doc.subtitle))}</p>')
    out.append("</div></header>")
    out.append(f'<p class="date">Generated {esc(_line(doc.generated))}.</p>')
    for section in doc.sections:
        tag = f"h{min(max(section.level, 2), 4)}"
        out.append(f"<section><{tag}>{esc(_line(section.heading))}</{tag}>")
        out += [_passage_block(passage) for passage in section.generated]
        out += [f"<p>{esc(_line(paragraph))}</p>" for paragraph in section.paragraphs]
        if section.bullets:
            out.append("<ul>")
            out += [f"<li>{esc(_line(bullet))}</li>" for bullet in section.bullets]
            out.append("</ul>")
        out.append("</section>")
    out.append('<footer class="closing">')
    if design.footer:
        out.append(f"<p>{esc(_line(design.footer))}</p>")
    out.append(f"<p>{esc(_line(doc.disclaimer))}</p></footer>")
    out.append("</main></body></html>")
    return "\n".join(out) + "\n"


# --- docx --------------------------------------------------------------------

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_WML = "application/vnd.openxmlformats-officedocument.wordprocessingml"
# Page width and height in twentieths of a point.
PAGE_TWIPS = {"a4": (11906, 16838), "letter": (12240, 15840)}
# Word has no "system" font; a document asks for a font every office suite has.
WORD_FONTS = {"system": "Arial"}
EMU_PER_PIXEL = 9525
LOGO_HEIGHT_EMU = 457200  # half an inch
LOGO_MAX_WIDTH_EMU = 1828800  # two inches


def _content_types(header: bool, footer: bool, png: bool) -> str:
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
    ]
    if png:
        parts.append('<Default Extension="png" ContentType="image/png"/>')
    parts.append(
        f'<Override PartName="/word/document.xml" ContentType="{_WML}.document.main+xml"/>'
    )
    parts.append(f'<Override PartName="/word/styles.xml" ContentType="{_WML}.styles+xml"/>')
    if header:
        parts.append(f'<Override PartName="/word/header1.xml" ContentType="{_WML}.header+xml"/>')
    if footer:
        parts.append(f'<Override PartName="/word/footer1.xml" ContentType="{_WML}.footer+xml"/>')
    parts.append("</Types>")
    return "".join(parts)


_ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<Relationships xmlns="{_PKG_REL}">'
    f'<Relationship Id="rId1" Type="{_REL}/officeDocument" Target="word/document.xml"/>'
    "</Relationships>"
)


def _document_rels(header: bool, footer: bool, png: bool) -> str:
    rows = [f'<Relationship Id="rIdStyles" Type="{_REL}/styles" Target="styles.xml"/>']
    if header:
        rows.append(f'<Relationship Id="rIdHeader" Type="{_REL}/header" Target="header1.xml"/>')
    if footer:
        rows.append(f'<Relationship Id="rIdFooter" Type="{_REL}/footer" Target="footer1.xml"/>')
    if png:
        rows.append(f'<Relationship Id="rIdLogo" Type="{_REL}/image" Target="media/logo.png"/>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{_PKG_REL}">' + "".join(rows) + "</Relationships>"
    )


def _style(style_id: str, name: str, run: str, paragraph: str = "") -> str:
    return (
        f'<w:style w:type="paragraph" w:styleId="{style_id}"><w:name w:val="{name}"/>'
        '<w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>'
        f"<w:pPr>{paragraph}</w:pPr><w:rPr>{run}</w:rPr></w:style>"
    )


def render_styles_xml(design: DocumentDesign | None = None) -> str:
    """The ``word/styles.xml`` part: the font, the sizes and the design's colours.

    The colours and the font come from the checked design specification.
    """
    design = design or DocumentDesign()
    font = xml_escape(WORD_FONTS.get(design.font, design.font), {'"': "&quot;"})
    primary = design.primary_color.lstrip("#").upper()
    accent = design.accent_color.lstrip("#").upper()
    muted = _MUTED.lstrip("#").upper()

    def size(half_points: int) -> str:
        return f'<w:sz w:val="{half_points}"/><w:szCs w:val="{half_points}"/>'

    heading = '<w:keepNext/><w:spacing w:before="280" w:after="100"/>'
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:styles xmlns:w="{_W}">'
        "<w:docDefaults><w:rPrDefault><w:rPr>"
        f'<w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:cs="{font}" w:eastAsia="{font}"/>'
        f'{size(22)}<w:color w:val="{_INK.lstrip("#").upper()}"/>'
        '</w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="120"/>'
        "</w:pPr></w:pPrDefault></w:docDefaults>"
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/>'
        "<w:qFormat/></w:style>"
        + _style(
            "Title",
            "Title",
            f'<w:b/><w:color w:val="{primary}"/>{size(40)}',
            '<w:spacing w:after="60"/>',
        )
        + _style("Subtitle", "Subtitle", f'<w:color w:val="{muted}"/>{size(24)}')
        + _style(
            "Heading1",
            "heading 1",
            f'<w:b/><w:color w:val="{primary}"/>{size(30)}',
            heading + f'<w:pBdr><w:bottom w:val="single" w:sz="12" w:space="2" w:color="{accent}"/>'
            '</w:pBdr><w:outlineLvl w:val="0"/>',
        )
        + _style(
            "Heading2",
            "heading 2",
            f'<w:b/><w:color w:val="{primary}"/>{size(26)}',
            heading + '<w:outlineLvl w:val="1"/>',
        )
        + _style(
            "Heading3",
            "heading 3",
            f'<w:b/><w:color w:val="{primary}"/>{size(24)}',
            heading + '<w:outlineLvl w:val="2"/>',
        )
        + _style(
            "Generated",
            "Generated passage",
            "<w:i/>",
            '<w:ind w:left="240"/><w:spacing w:after="60"/>',
        )
        + _style(
            "Facts",
            "Generated facts",
            f'<w:color w:val="{muted}"/>{size(18)}',
            '<w:ind w:left="240"/><w:spacing w:after="40"/>',
        )
        + _style("Small", "Small", f'<w:color w:val="{muted}"/>{size(18)}')
        + _style(
            "Disclaimer",
            "Disclaimer",
            f'<w:color w:val="{muted}"/>{size(18)}',
            '<w:spacing w:before="360"/><w:pBdr><w:top w:val="single" w:sz="4" '
            'w:space="6" w:color="D6DEE7"/></w:pBdr>',
        )
        + _style("Header", "header", f'<w:color w:val="{muted}"/>{size(18)}')
        + _style("Footer", "footer", f'<w:color w:val="{muted}"/>{size(18)}')
        + "</w:styles>"
    )


def _para(
    text: str,
    *,
    style: str | None = None,
    bold: bool = False,
    italic: bool = False,
    size: int | None = None,
    bullet: bool = False,
) -> str:
    properties = ("<w:b/>" if bold else "") + ("<w:i/>" if italic else "")
    if size is not None:
        properties += f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
    run_properties = f"<w:rPr>{properties}</w:rPr>" if properties else ""
    prefix = "•  " if bullet else ""
    clean = _XML_INVALID.sub("", prefix + _line(text))
    run = f'<w:r>{run_properties}<w:t xml:space="preserve">{xml_escape(clean)}</w:t></w:r>'
    style_xml = f'<w:pStyle w:val="{style}"/>' if style else ""
    return f"<w:p><w:pPr>{style_xml}</w:pPr>{run}</w:p>"


def _logo_paragraph(logo: Logo) -> str:
    height = LOGO_HEIGHT_EMU
    width = height * logo.width // max(logo.height, 1) if logo.width else height
    if width > LOGO_MAX_WIDTH_EMU:
        height = height * LOGO_MAX_WIDTH_EMU // width
        width = LOGO_MAX_WIDTH_EMU
    extent = f'cx="{width}" cy="{height}"'
    return (
        "<w:p><w:r><w:drawing>"
        f'<wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent {extent}/>'
        '<wp:docPr id="1" name="Logo"/>'
        f'<a:graphic xmlns:a="{_A}"><a:graphicData uri="{_PIC}">'
        f'<pic:pic xmlns:pic="{_PIC}"><pic:nvPicPr><pic:cNvPr id="0" name="logo.png"/>'
        '<pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="rIdLogo"/>'
        "<a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr>"
        f'<a:xfrm><a:off x="0" y="0"/><a:ext {extent}/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
        "</a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>"
    )


def render_document_xml(
    doc: Document, design: DocumentDesign | None = None, logo: Logo | None = None
) -> str:
    """Return the ``word/document.xml`` part for ``doc``, with paragraphs in named styles.

    A PNG ``logo`` opens the document; an SVG logo is left out, as not every word
    processor shows one. The section properties carry the page size and the header
    and footer references when the design has them.
    """
    design = design or DocumentDesign()
    width, height = PAGE_TWIPS[design.page_size]
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        f'<w:document xmlns:w="{_W}" xmlns:r="{_R}" xmlns:wp="{_WP}"><w:body>',
    ]
    if logo is not None and logo.kind == "png":
        parts.append(_logo_paragraph(logo))
    parts.append(_para(doc.title, style="Title"))
    if doc.subtitle:
        parts.append(_para(doc.subtitle, style="Subtitle"))
    parts.append(_para(f"Generated {doc.generated}.", style="Small"))
    for section in doc.sections:
        level = min(max(section.level - 1, 1), 3)
        parts.append(_para(section.heading, style=f"Heading{level}"))
        for passage in section.generated:
            parts.append(
                _para(f"{GENERATED_LABEL}: {passage.text}", style="Generated", italic=True)
            )
            parts += [_para(f"From {fact}", style="Facts", bullet=True) for fact in passage.facts]
        parts += [_para(paragraph) for paragraph in section.paragraphs]
        parts += [_para(bullet, bullet=True) for bullet in section.bullets]
    if design.footer:
        parts.append(_para(design.footer, style="Small"))
    parts.append(_para(doc.disclaimer, style="Disclaimer"))
    references = ""
    if design.header:
        references += '<w:headerReference w:type="default" r:id="rIdHeader"/>'
    if design.footer:
        references += '<w:footerReference w:type="default" r:id="rIdFooter"/>'
    parts.append(
        f'<w:sectPr>{references}<w:pgSz w:w="{width}" w:h="{height}"/>'
        '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="567" '
        'w:footer="567" w:gutter="0"/></w:sectPr></w:body></w:document>'
    )
    return "".join(parts)


def _running(kind: str, text: str) -> str:
    tag = "w:hdr" if kind == "header" else "w:ftr"
    style = "Header" if kind == "header" else "Footer"
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<{tag} xmlns:w="{_W}">{_para(text, style=style)}</{tag}>'
    )


def docx_bytes(
    doc: Document, design: DocumentDesign | None = None, logo: Logo | None = None
) -> bytes:
    """Return ``doc`` as the bytes of a ``.docx`` file that follows ``design``.

    The package holds the document, a styles part with the design's font and
    colours, a header and a footer part when the design has that text, and a PNG
    logo when one is given.
    """
    design = design or DocumentDesign()
    png = logo is not None and logo.kind == "png"
    header, footer = bool(design.header), bool(design.footer)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types(header, footer, png))
        archive.writestr("_rels/.rels", _ROOT_RELS)
        archive.writestr("word/document.xml", render_document_xml(doc, design, logo))
        archive.writestr("word/_rels/document.xml.rels", _document_rels(header, footer, png))
        archive.writestr("word/styles.xml", render_styles_xml(design))
        if header:
            archive.writestr("word/header1.xml", _running("header", design.header))
        if footer:
            archive.writestr("word/footer1.xml", _running("footer", design.footer))
        if png and logo is not None:
            archive.writestr("word/media/logo.png", logo.data)
    return buffer.getvalue()
