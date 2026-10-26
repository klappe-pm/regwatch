"""The send-ready newsletter: a period's changes, candidates and impacts as an email.

The newsletter is built as a ``Document`` from structured data, the same way every
briefing is, and rendered three ways:

- an HTML email: inline styles only, a table layout at most 600 pixels wide that common
  mail clients render, the colours, font and logo of the document design
  specification, and a closing line the user writes for replies or unsubscribing;
- a plain text part with the same content;
- an ``.eml`` file that holds both as ``multipart/alternative``, with a PNG logo as
  a related part, a subject and no recipient. Regwatch never sends it.

Without generated copy, the opening and the summary of each section are fixed
sentences built from the data. With it, they are generated passages, labelled and
shown with the facts they cite. Every value is escaped, and the newsletter ends with
the disclaimer like every other document.
"""

from __future__ import annotations

import datetime as dt
import email.policy
import html
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import format_datetime
from typing import Any

from regwatch.check import SourceResult
from regwatch.config import DocumentDesign
from regwatch.design import Logo
from regwatch.document import Document, Section, make_disclaimer
from regwatch.impact import Impact
from regwatch.llm import (
    Fact,
    GenerationResult,
    candidate_facts,
    change_facts,
    event_facts,
    impact_facts,
)
from regwatch.register import ChangeEvent, Register, parse_date
from regwatch.render import passage_html, render_newsletter_text
from regwatch.sanitize import clean_text, defang_links, safe_https_url

__all__ = [
    "EMAIL_WIDTH",
    "LOGO_CID",
    "MAX_IMPACTS",
    "NEWSLETTER_SECTIONS",
    "NewsletterContent",
    "build_newsletter",
    "email_bytes",
    "newsletter_content",
    "render_email_html",
    "render_email_text",
]

NEWSLETTER_SECTIONS = ("opening", "changes", "candidates", "impacts")
"""The generated copy sections a newsletter shows; it has no obligations section."""
EMAIL_WIDTH = 600
LOGO_CID = "logo@regwatch"
MAX_IMPACTS = 10
MAX_ITEMS = 40
INK = "#17212b"
MUTED = "#4b5866"
LINE = "#d6dee7"
SURFACE = "#f4f6f8"


@dataclass(frozen=True)
class NewsletterContent:
    """The items of one period, chosen from the register, the checks and the candidates."""

    start: dt.date
    end: dt.date
    changes: tuple[SourceResult, ...]
    events: tuple[ChangeEvent, ...]
    candidates: tuple[Mapping[str, Any], ...]
    impacts: tuple[Impact, ...]
    names: Mapping[str, str]

    def facts(self) -> list[Fact]:
        """The facts generated copy may be written from: every item in the newsletter."""
        return [
            *change_facts(self.changes, self.names),
            *event_facts(self.events),
            *candidate_facts(self.candidates),
            *impact_facts(self.impacts),
        ]


def newsletter_content(
    register: Register,
    results: Iterable[SourceResult],
    impacts: Iterable[Impact],
    candidates: Iterable[Mapping[str, Any]],
    today: dt.date,
    since_days: int,
) -> NewsletterContent:
    """Choose the period's items: sources that changed or need attention, change log
    events and ingest candidates dated in the last ``since_days`` days, and the act now
    and high severity impacts, those in focus first. The period is ``since_days`` days
    ending today, today included: 7 days to 19 October start on 13 October."""
    start = today - dt.timedelta(days=since_days - 1)

    def in_period(value: object) -> bool:
        date = parse_date(value) if isinstance(value, str) else None
        return date is not None and start <= date <= today

    return NewsletterContent(
        start=start,
        end=today,
        changes=tuple(r for r in results if r.flagged or r.needs_attention)[:MAX_ITEMS],
        events=tuple(
            sorted(
                (e for e in register.changelog if in_period(e.date)),
                key=lambda e: e.date,
                reverse=True,
            )
        )[:MAX_ITEMS],
        candidates=tuple(c for c in candidates if in_period(c.get("date")))[:MAX_ITEMS],
        impacts=tuple(i for i in impacts if i.severity in ("act-now", "high"))[:MAX_IMPACTS],
        names={s.source_id: s.name for s in register.sources},
    )


def _plain(value: object, limit: int = 300) -> str:
    return clean_text(value, limit) if isinstance(value, str) else ""


def _candidate_line(candidate: Mapping[str, Any]) -> str:
    # The candidates file is untrusted: an address in its text is written so no mail
    # client links it, and the only link is the checked source address.
    agency = defang_links(_plain(candidate.get("agency"), 120))
    line = f"{_plain(candidate.get('date'), 10)}, {agency}: "
    line += defang_links(_plain(candidate.get("headline"), 240))
    link = safe_https_url(candidate.get("source_url"))
    return f"{line} ({link})" if link else line


def build_newsletter(
    register: Register,
    content: NewsletterContent,
    design: DocumentDesign,
    generated: GenerationResult | None = None,
) -> Document:
    """The newsletter as a document. ``generated`` replaces the fixed sentences it covers."""

    def summary(section: str, fixed: str) -> tuple[list[str], list[Any]]:
        passages = generated.section(section) if generated is not None else []
        return ([] if passages else [fixed]), passages

    changes, events = content.changes, content.events
    candidates, impacts = content.candidates, content.impacts
    opening_text = (
        f"From {content.start.isoformat()} to {content.end.isoformat()}: "
        f"{len(changes)} source change(s) to look at, {len(events)} recorded development(s), "
        f"{len(candidates)} unconfirmed item(s) from the feed and {len(impacts)} candidate "
        "impact(s) of act now or high severity."
    )
    paragraphs, passages = summary("opening", opening_text)
    sections = [Section("In This Issue", paragraphs=paragraphs, generated=passages)]

    changed_lines = [
        f"{r.status}: {content.names.get(r.source_id, r.source_id)}"
        + (f" ({_plain(r.detail, 200)})" if r.detail else "")
        for r in changes
    ] + [f"{e.date}, {e.jurisdiction}: {e.headline}" for e in events]
    fixed = (
        f"{len(changes)} source(s) changed or could not be read, and {len(events)} development(s) "
        "were recorded in the change log in this period."
        if changed_lines
        else "No source changed and no development was recorded in this period."
    )
    paragraphs, passages = summary("changes", fixed)
    sections.append(
        Section("What Changed", paragraphs=paragraphs, bullets=changed_lines, generated=passages)
    )

    fixed = (
        f"{len(candidates)} item(s) from the ingest feed need a person to confirm them before "
        "they are added to the change log."
        if candidates
        else "The ingest feed found nothing new in this period."
    )
    paragraphs, passages = summary("candidates", fixed)
    sections.append(
        Section(
            "Newly Detected, Unconfirmed",
            paragraphs=paragraphs,
            bullets=[_candidate_line(c) for c in candidates],
            generated=passages,
        )
    )

    fixed = (
        f"{len(impacts)} candidate impact(s) of act now or high severity; each needs a person "
        "to confirm it."
        if impacts
        else "No candidate impact of act now or high severity."
    )
    paragraphs, passages = summary("impacts", fixed)
    sections.append(
        Section(
            "Impacts To Review",
            paragraphs=paragraphs,
            bullets=[
                f"{i.product_name}: {i.obligation_title} ({i.jurisdiction}, {i.severity}"
                + (f", effective {i.effective_date}" if i.effective_date else "")
                + ")"
                for i in impacts
            ],
            generated=passages,
        )
    )
    today = content.end.isoformat()
    return Document(
        title=design.title(f"{register.portfolio.name} regulatory newsletter", today),
        subtitle=f"{content.start.isoformat()} to {today}",
        generated=today,
        sections=sections,
        disclaimer=make_disclaimer(register.portfolio.disclaimer),
    )


# --- rendering ------------------------------------------------------------------------


def _esc(text: str, limit: int | None = None) -> str:
    return html.escape(clean_text(text, limit))


def render_email_html(
    doc: Document,
    design: DocumentDesign,
    footer: str,
    *,
    logo: Logo | None = None,
    logo_src: str = "",
) -> str:
    """The newsletter as an HTML email: inline styles, tables, at most 600 pixels wide.

    ``logo_src`` is where the logo image is loaded from: ``cid:logo@regwatch`` in the
    ``.eml`` file and a ``data:`` address in the standalone file. Only a PNG logo is
    used, because common mail clients do not show SVG. Every value is escaped, and
    the colours and the font come from the checked design specification.
    """
    font = html.escape(design.font_stack, quote=True)
    primary, accent = design.primary_color, design.accent_color
    title = _esc(doc.title)
    out = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{title}</title></head>",
        f'<body style="margin:0;padding:0;background:{SURFACE};">',
        f'<div style="display:none;max-height:0;overflow:hidden;">{_esc(doc.subtitle)}</div>',
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background:{SURFACE};">',
        '<tr><td align="center" style="padding:24px 12px;">',
        # width="600" for clients that read only the attribute; the style lets the table
        # shrink to the screen, since the cell around it adds 12 pixels on each side.
        f'<table role="presentation" width="{EMAIL_WIDTH}" cellpadding="0" cellspacing="0" '
        f'border="0" style="width:100%;max-width:{EMAIL_WIDTH}px;background:#ffffff;'
        f'font-family:{font};color:{INK};">',
    ]
    if logo is not None and logo.kind == "png" and logo_src:
        width = min(logo.width or 160, 200)
        out.append(
            '<tr><td style="padding:20px 32px 12px 32px;">'
            f'<img src="{html.escape(logo_src, quote=True)}" alt="{_esc(design.organisation)}" '
            f'width="{width}" style="display:block;border:0;max-width:{width}px;height:auto;">'
            "</td></tr>"
        )
    if design.header:
        out.append(
            f'<tr><td style="padding:8px 32px 0 32px;font-size:12px;line-height:16px;'
            f'color:{MUTED};">{_esc(design.header)}</td></tr>'
        )
    out += [
        f'<tr><td style="padding:20px 32px;background:{primary};">',
        f'<h1 style="margin:0;font-size:22px;line-height:28px;color:#ffffff;">{title}</h1>',
        f'<p style="margin:4px 0 0 0;font-size:14px;line-height:20px;color:#ffffff;">'
        f"{_esc(doc.subtitle)}</p>",
        "</td></tr>",
    ]
    for section in doc.sections:
        out.append('<tr><td style="padding:20px 32px 0 32px;">')
        out.append(
            f'<h2 style="margin:0 0 8px 0;padding-bottom:4px;font-size:17px;line-height:24px;'
            f'color:{primary};border-bottom:2px solid {accent};">{_esc(section.heading)}</h2>'
        )
        out += [passage_html(passage, MUTED) for passage in section.generated]
        out += [
            f'<p style="margin:0 0 10px 0;font-size:15px;line-height:22px;">{_esc(p)}</p>'
            for p in section.paragraphs
        ]
        if section.bullets:
            out.append(
                '<ul style="margin:0 0 10px 0;padding-left:20px;font-size:15px;line-height:22px;">'
            )
            out += [f'<li style="margin:0 0 4px 0;">{_esc(b)}</li>' for b in section.bullets]
            out.append("</ul>")
        out.append("</td></tr>")
    closing = [f"{_esc(footer)}"]
    if design.footer:
        closing.insert(0, _esc(design.footer))
    out.append(
        '<tr><td style="padding:24px 32px 28px 32px;">'
        + "".join(
            f'<p style="margin:0 0 8px 0;font-size:13px;line-height:18px;color:{INK};">{line}</p>'
            for line in closing
        )
        + f'<p style="margin:12px 0 0 0;padding-top:12px;border-top:1px solid {LINE};'
        f'font-size:12px;line-height:17px;color:{MUTED};">{_esc(doc.disclaimer)}</p>'
        "</td></tr>"
    )
    out.append("</table></td></tr></table></body></html>")
    return "\n".join(out) + "\n"


def render_email_text(doc: Document, design: DocumentDesign, footer: str) -> str:
    """The plain text part: the newsletter text with the header, footer and closing line."""
    text = render_newsletter_text(doc)
    head = f"{clean_text(design.header)}\n\n" if design.header else ""
    body, _, disclaimer = text.rpartition("-----\n")
    closing = [clean_text(line) for line in (design.footer, footer) if line.strip()]
    return head + body + "\n".join(closing) + "\n\n-----\n" + disclaimer


def email_bytes(
    subject: str,
    text: str,
    html_body: str,
    now: dt.datetime,
    logo: Logo | None = None,
) -> bytes:
    """The ``.eml`` file: ``multipart/alternative`` with the text and the HTML, no recipients.

    A PNG logo is attached to the HTML part as a related image with the content id
    the HTML names. ``X-Unsent: 1`` asks a mail program that supports it to open the
    file as a draft. Regwatch never sends it.
    """
    message = EmailMessage(policy=email.policy.SMTP)
    message["Subject"] = clean_text(subject, 200)
    message["Date"] = format_datetime(now)
    message["X-Unsent"] = "1"
    message.set_content(text, charset="utf-8")
    message.add_alternative(html_body, subtype="html", charset="utf-8")
    if logo is not None and logo.kind == "png":
        for part in message.iter_parts():
            if part.get_content_type() == "text/html":
                # Inline, and a related part naming its root's type, so a mail
                # program shows the logo in the message instead of as an attachment.
                part.add_related(
                    logo.data,
                    maintype="image",
                    subtype="png",
                    cid=f"<{LOGO_CID}>",
                    filename="logo.png",
                    disposition="inline",
                )
                part.set_param("type", "text/html")
    return message.as_bytes()
