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
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
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
from regwatch.wording import (
    count,
    date_range,
    join_clauses,
    prose_date,
    severity_label,
    status_phrase,
)

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
    places: Mapping[str, str] = field(default_factory=dict)
    """Jurisdiction names by id, so a reader sees "United States", not "us"."""

    def facts(self) -> list[Fact]:
        """The facts generated copy may be written from: every item in the newsletter."""
        return [
            *change_facts(self.changes, self.names),
            *event_facts(self.events, self.places),
            *candidate_facts(self.candidates),
            *impact_facts(self.impacts, self.places),
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
        places={j.jurisdiction_id: j.name for j in register.jurisdictions},
    )


def _plain(value: object, limit: int = 300) -> str:
    return clean_text(value, limit) if isinstance(value, str) else ""


def _candidate_line(candidate: Mapping[str, Any]) -> str:
    # The candidates file is untrusted: an address in its text is written so no mail
    # client links it, and the only link is the checked source address.
    agency = defang_links(_plain(candidate.get("agency"), 120))
    headline = defang_links(_plain(candidate.get("headline"), 240))
    when = prose_date(_plain(candidate.get("date"), 10))
    lead = ", ".join(part for part in (when, agency) if part)
    line = f"{lead}: {headline}" if lead and headline else lead or headline
    link = safe_https_url(candidate.get("source_url"))
    return f"{line} ({link})" if link else line


def _impact_line(impact: Impact, places: Mapping[str, str]) -> str:
    place = places.get(impact.jurisdiction, impact.jurisdiction)
    details = [place, f"{severity_label(impact.severity)} severity"]
    if impact.effective_date:
        details.append(f"effective {prose_date(impact.effective_date)}")
    return f"{impact.product_name}: {impact.obligation_title} ({', '.join(details)})"


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
    period = date_range(content.start, content.end)
    unread = [r for r in changes if r.needs_attention]
    moved = [r for r in changes if not r.needs_attention]
    clauses = [
        count(len(moved), "source change") + " to look at" if moved else "",
        count(len(unread), "source") + " that could not be checked" if unread else "",
        count(len(events), "recorded development") if events else "",
        count(len(candidates), "unconfirmed item") + " from the feed" if candidates else "",
        count(len(impacts), "candidate impact") + " of act now or high severity" if impacts else "",
    ]
    opening_text = (
        f"From {period}: {join_clauses(clauses)}."
        if any(clauses)
        else f"Nothing changed and nothing new was found from {period}."
    )
    paragraphs, passages = summary("opening", opening_text)
    sections = [Section("In This Issue", paragraphs=paragraphs, generated=passages)]

    changed_lines = [
        f"{content.names.get(r.source_id, r.source_id)}: "
        f"{status_phrase(r.status, _plain(r.detail, 200))}"
        for r in changes
    ] + [
        f"{prose_date(e.date)}, {content.places.get(e.jurisdiction, e.jurisdiction)}: {e.headline}"
        for e in events
    ]
    clauses = [
        f"{count(len(moved), 'source')} changed" if moved else "",
        f"{count(len(unread), 'source')} could not be checked" if unread else "",
        f"{count(len(events), 'development')} {'was' if len(events) == 1 else 'were'} "
        "recorded in the change log"
        if events
        else "",
    ]
    fixed = (
        f"In this period {join_clauses(clauses)}."
        if changed_lines
        else "No source changed and no development was recorded in this period."
    )
    paragraphs, passages = summary("changes", fixed)
    sections.append(
        Section("What Changed", paragraphs=paragraphs, bullets=changed_lines, generated=passages)
    )

    fixed = (
        f"{count(len(candidates), 'item').capitalize()} from the ingest feed "
        f"{'needs' if len(candidates) == 1 else 'need'} a person to confirm "
        f"{'it' if len(candidates) == 1 else 'them'} before "
        f"{'it is' if len(candidates) == 1 else 'they are'} added to the change log."
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
        f"{count(len(impacts), 'candidate impact').capitalize()} of act now or high severity; "
        + ("it needs" if len(impacts) == 1 else "each needs")
        + " a person to confirm it."
        if impacts
        else "No candidate impact of act now or high severity."
    )
    paragraphs, passages = summary("impacts", fixed)
    sections.append(
        Section(
            "Impacts To Review",
            paragraphs=paragraphs,
            bullets=[_impact_line(i, content.places) for i in impacts],
            generated=passages,
        )
    )
    today = content.end.isoformat()
    return Document(
        title=design.title(f"{register.portfolio.name} regulatory newsletter", today),
        subtitle=period,
        generated=today,
        sections=sections,
        disclaimer=make_disclaimer(register.portfolio.disclaimer),
    )


# --- rendering ------------------------------------------------------------------------


def _esc(text: str, limit: int | None = None) -> str:
    return html.escape(clean_text(text, limit))


_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
_DATE = re.compile(
    r"\d{4}-\d{2}-\d{2}"
    rf"|\d{{1,2}}(?: to \d{{1,2}})? (?:{_MONTHS})(?: \d{{4}})?"
    rf"|(?:{_MONTHS}) \d{{4}}"
)
NOWRAP = '<span style="white-space:nowrap;">'


def _dated(text: str) -> str:
    """Escaped ``text`` with each date kept on one line, so a narrow screen cannot split it."""
    return _DATE.sub(lambda match: f"{NOWRAP}{match.group(0)}</span>", _esc(text))


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
    # The header line runs above everything, the logo included, as it does on a page.
    if design.header:
        out.append(
            f'<tr><td style="padding:12px 32px 0 32px;font-size:12px;line-height:16px;'
            f'color:{MUTED};">{_esc(design.header)}</td></tr>'
        )
    if logo is not None and logo.kind == "png" and logo_src:
        width = min(logo.width or 160, 200)
        out.append(
            '<tr><td style="padding:20px 32px 12px 32px;">'
            f'<img src="{html.escape(logo_src, quote=True)}" alt="{_esc(design.organisation)}" '
            f'width="{width}" style="display:block;border:0;max-width:{width}px;height:auto;">'
            "</td></tr>"
        )
    out += [
        f'<tr><td style="padding:20px 32px;background:{primary};">',
        f'<h1 style="margin:0;font-size:22px;line-height:28px;color:#ffffff;">'
        f"{_dated(doc.title)}</h1>",
        f'<p style="margin:4px 0 0 0;font-size:14px;line-height:20px;color:#ffffff;">'
        f"{_dated(doc.subtitle)}</p>",
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
            f'<p style="margin:0 0 10px 0;font-size:15px;line-height:22px;">{_dated(p)}</p>'
            for p in section.paragraphs
        ]
        if section.bullets:
            out.append(
                '<ul style="margin:0 0 10px 0;padding-left:20px;font-size:15px;line-height:22px;">'
            )
            out += [f'<li style="margin:0 0 4px 0;">{_dated(b)}</li>' for b in section.bullets]
            out.append("</ul>")
        out.append("</td></tr>")
    # Only lines with text: an empty footer gives no empty paragraph.
    closing = [_esc(line) for line in (design.footer, footer) if line.strip()]
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
