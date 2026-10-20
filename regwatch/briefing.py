"""The tiered briefing.

The same data renders at three levels of detail so a report can be rolled out to
a team from simple to complete:

- ``v1``: headlines only. What happened, what is coming due, and one short entry
  per obligation.
- ``v2``: adds context and the governing citations for each item, and the
  enforcement themes.
- ``v3``: the complete briefing. Adds what to do about each item, the affected
  products, the unconfirmed ingest candidates and a consolidated action list.

Each item is written as what happened, what it means and what to do, with links
back to primary sources. The function is pure: it takes loaded data and returns a
Document.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping
from typing import Any

from regwatch.document import Document, Section, make_disclaimer
from regwatch.focus import FocusProfile
from regwatch.impact import Impact
from regwatch.register import ChangeEvent, Citation, Obligation, Register, parse_date
from regwatch.sanitize import clean_text, safe_https_url
from regwatch.synthesis import upcoming_obligations

__all__ = ["TIERS", "build_briefing"]

TIERS = ("v1", "v2", "v3")
TIER_RANK = {name: rank for rank, name in enumerate(TIERS, start=1)}
TIER_LABEL = {"v1": "v1 (headlines)", "v2": "v2 (context and citations)", "v3": "v3 (full detail)"}
STATUS_ORDER = {
    "enacted": 0,
    "finalized": 0,
    "voluntary": 1,
    "proposed": 2,
    "in-progress": 3,
    "monitoring": 4,
}
COMING_DUE_DAYS = 540


def _plain(value: object) -> str:
    return clean_text(value) if isinstance(value, str) else ""


def _citations(items: Iterable[Citation]) -> str:
    return "; ".join(f"{c.citation} ({c.url})" if c.url else c.citation for c in items)


def _products_by_obligation(impacts: Iterable[Impact]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for impact in impacts:
        names = grouped.setdefault(impact.obligation_id, [])
        if impact.product_name not in names:
            names.append(impact.product_name)
    return grouped


def _recent_events(
    register: Register, today: dt.date, since_days: int | None, recent_count: int
) -> tuple[list[ChangeEvent], tuple[dt.date, dt.date, bool] | None]:
    """Select recent change log events, optionally windowed.

    With a window the anchor is today when there is recent activity, otherwise
    the latest recorded event, so a report stays populated against an older
    change log and states the window it actually covers.
    """
    dated = [(e, parse_date(e.date)) for e in register.changelog]
    known = [(e, d) for e, d in dated if d is not None]
    if since_days is None:
        ordered = [e for e, _ in sorted(known, key=lambda pair: pair[1], reverse=True)]
        return ordered[:recent_count], None
    latest = max((d for _, d in known), default=today)
    start_of_recent = today - dt.timedelta(days=since_days)
    anchor = today if any(start_of_recent <= d <= today for _, d in known) else latest
    start = anchor - dt.timedelta(days=since_days)
    chosen = [(e, d) for e, d in known if start <= d <= anchor]
    ordered = [e for e, _ in sorted(chosen, key=lambda pair: pair[1], reverse=True)]
    return ordered, (start, anchor, anchor != today)


def _source_text(register: Register, obligation: Obligation) -> str:
    info = register.detail.get(obligation.obligation_id)
    if info and info.backlinks:
        first = info.backlinks[0]
        return f"{first.citation} ({first.url})" if first.url else first.citation
    if obligation.source_url:
        return f"{obligation.jurisdiction} source ({obligation.source_url})"
    return ""


def _headline(obligation: Obligation) -> str:
    date = obligation.effective_date or "no date"
    return f"{obligation.title}: {obligation.status}, {date} ({obligation.jurisdiction})"


def _short_entry(register: Register, obligation: Obligation) -> str:
    info = register.detail.get(obligation.obligation_id)
    text = _headline(obligation)
    if info:
        text += f". Summary: {info.summary}"
        source = _source_text(register, obligation)
        if source:
            text += f" Source: {source}"
    return text


def _obligation_section(
    register: Register, obligation: Obligation, products: Mapping[str, list[str]], tier: str
) -> Section:
    info = register.detail.get(obligation.obligation_id)
    effective = f", effective {obligation.effective_date}" if obligation.effective_date else ""
    paragraphs = [f"Status: {obligation.status}{effective} ({obligation.jurisdiction})."]
    if info:
        impacts = info.impacts
        if products.get(obligation.obligation_id):
            impacts += f" Affected products: {', '.join(products[obligation.obligation_id])}."
        paragraphs += [
            f"Summary. {info.summary}",
            f"Impacts. {impacts}",
            f"Implications. {info.implications}",
        ]
        if info.citations:
            paragraphs.append(f"Governing rule. {_citations(info.citations)}")
        if tier == "v3":
            paragraphs.append(f"What to do. {info.action}")
    else:
        paragraphs.append(f"Summary. {obligation.title} ({obligation.status}).")
        paragraphs.append(
            f"Note. {obligation.notes or 'Detail pending; confirm against the primary source.'}"
        )
    source = _source_text(register, obligation)
    if source:
        paragraphs.append(f"Source. {source}")
    return Section(obligation.title, level=3, paragraphs=paragraphs)


def _jurisdiction_sections(
    register: Register,
    obligations: Iterable[Obligation],
    products: Mapping[str, list[str]],
    tier: str,
    jurisdiction_names: Mapping[str, str],
) -> list[Section]:
    """Obligations grouped under one heading per jurisdiction, ordered by jurisdiction name."""
    by_jurisdiction: dict[str, list[Obligation]] = {}
    for obligation in obligations:
        by_jurisdiction.setdefault(obligation.jurisdiction, []).append(obligation)
    sections: list[Section] = []
    for jurisdiction in sorted(by_jurisdiction, key=lambda j: jurisdiction_names.get(j, j)):
        sections.append(
            Section(f"Obligations: {jurisdiction_names.get(jurisdiction, jurisdiction)}")
        )
        sections += [
            _obligation_section(register, o, products, tier) for o in by_jurisdiction[jurisdiction]
        ]
    return sections


def _candidate_section(candidate: Mapping[str, Any]) -> Section:
    """One unconfirmed ingest candidate. The candidates file is untrusted, so every field is cleaned."""
    what = _plain(candidate.get("what_happened"))
    paragraphs = [f"What happened (unconfirmed). {what}"]
    raw_citations = candidate.get("citations")
    citations = raw_citations if isinstance(raw_citations, list) else []
    cited = "; ".join(_plain(c.get("citation")) for c in citations if isinstance(c, dict)).strip(
        "; "
    )
    if cited:
        paragraphs.append(f"Citations from the feed. {cited}")
    link = safe_https_url(candidate.get("source_url"))
    if link:
        paragraphs.append(f"Source. {_plain(candidate.get('document_number'))} ({link})")
    heading = f"{_plain(candidate.get('date'))}: {_plain(candidate.get('headline'))}"
    return Section(heading, level=3, paragraphs=paragraphs)


def build_briefing(
    register: Register,
    impacts: Iterable[Impact],
    today: dt.date,
    *,
    tier: str = "v3",
    recent_count: int = 8,
    since_days: int | None = None,
    candidates: Iterable[Mapping[str, Any]] = (),
    focus: FocusProfile | None = None,
) -> Document:
    """Build the briefing at ``tier`` (``v1``, ``v2`` or ``v3``).

    Raises ValueError for an unknown tier. ``candidates`` are the unconfirmed
    events from ingest; they appear only in ``v3`` and are always labelled
    unconfirmed.

    With an active ``focus`` profile, obligations, dated items and candidates that
    mention a focus area are listed first and the rest follow under an "outside
    your focus areas" heading. Nothing is left out.
    """
    if tier not in TIER_RANK:
        raise ValueError(f"unknown tier '{tier}'")
    rank = TIER_RANK[tier]
    profile = focus or FocusProfile()
    products = _products_by_obligation(impacts)
    jurisdiction_names = {j.jurisdiction_id: j.name for j in register.jurisdictions}
    sections: list[Section] = []

    def in_focus(obligation: Obligation) -> bool:
        detail = register.detail.get(obligation.obligation_id)
        return not profile.active or bool(profile.match_obligation(obligation, detail))

    scope = f"Tracked regulatory obligations and developments for the {register.portfolio.name} portfolio."
    if rank >= 2:
        scope += " Each item carries its governing citations where the register records them."
    if rank == 3:
        scope += " Each item is written as what happened, what it means and what to do, with links to primary sources."
    if profile.active:
        scope += (
            f" Focus areas: {', '.join(profile.names())}. Items that mention a focus area come first;"
            " the rest follow under an outside-your-focus-areas heading, so nothing is left out."
        )
    sections.append(Section("Scope", paragraphs=[scope]))

    events, window = _recent_events(register, today, since_days, recent_count)
    heading = (
        "What Happened Recently"
        if since_days is None
        else f"What Happened (Last {since_days} Days)"
    )
    recent = Section(heading)
    if window and window[2]:
        recent.paragraphs.append(
            f"Covering {window[0].isoformat()} to {window[1].isoformat()}, anchored to the latest recorded "
            "development because the change log has no newer entries."
        )
    elif window:
        recent.paragraphs.append(f"Covering {window[0].isoformat()} to {window[1].isoformat()}.")
    if not events:
        recent.paragraphs.append("No recorded developments in this window.")
    elif tier == "v1":
        recent.bullets = [
            f"{e.date}: {e.headline}" + (f" ({e.source_url})" if e.source_url else "")
            for e in events
        ]
    sections.append(recent)
    if events and tier != "v1":
        for event in events:
            paragraphs = [f"What happened. {event.what_happened}"] if event.what_happened else []
            if event.citations:
                paragraphs.append(f"Governing rule. {_citations(event.citations)}")
            origin = ", ".join(
                part
                for part in (event.agency, jurisdiction_names.get(event.jurisdiction, ""))
                if part
            )
            source = f"{origin} ({event.source_url})" if event.source_url else origin
            if source:
                paragraphs.append(f"Source. {source}")
            sections.append(
                Section(f"{event.date}: {event.headline}", level=3, paragraphs=paragraphs)
            )

    due = upcoming_obligations(register.obligations, COMING_DUE_DAYS, today)
    due_lines = [(o, f"{o.effective_date}, {o.jurisdiction}: {o.title} ({o.status})") for o in due]
    focused_due = [line for o, line in due_lines if in_focus(o)]
    other_due = [line for o, line in due_lines if not in_focus(o)]
    sections.append(
        Section(
            "Coming Due",
            paragraphs=[]
            if focused_due
            else ["Nothing with a dated effective date in the horizon."],
            bullets=focused_due,
        )
    )
    if other_due:
        sections.append(Section("Coming Due Outside Your Focus Areas", bullets=other_due))

    candidate_list = list(candidates)
    if tier == "v3" and candidate_list:
        focused = [c for c in candidate_list if not profile.active or profile.match_candidate(c)]
        other = [c for c in candidate_list if profile.active and not profile.match_candidate(c)]
        sections.append(
            Section(
                "Newly Detected, Unconfirmed",
                paragraphs=[
                    f"{len(candidate_list)} item(s) from the ingest feed, flagged for confirmation by a person "
                    "before they are added to the curated change log."
                ],
            )
        )
        sections += [_candidate_section(c) for c in focused[:recent_count]]
        if other:
            sections.append(
                Section(
                    "Newly Detected Outside Your Focus Areas, Unconfirmed",
                    paragraphs=[
                        f"{len(other)} item(s) from the ingest feed mention none of your focus areas."
                    ],
                )
            )
            sections += [_candidate_section(c) for c in other[:recent_count]]

    ordered = sorted(register.obligations, key=lambda o: (STATUS_ORDER.get(o.status, 9), o.title))
    focused_items = [o for o in ordered if in_focus(o)]
    other_items = [o for o in ordered if not in_focus(o)]
    if tier == "v1":
        sections.append(
            Section("Key Items", bullets=[_short_entry(register, o) for o in focused_items])
        )
        if other_items:
            sections.append(
                Section(
                    "Key Items Outside Your Focus Areas",
                    bullets=[_short_entry(register, o) for o in other_items],
                )
            )
    else:
        sections += _jurisdiction_sections(
            register, focused_items, products, tier, jurisdiction_names
        )
        if other_items:
            sections.append(
                Section(
                    "Outside Your Focus Areas",
                    paragraphs=[
                        f"{len(other_items)} obligation(s) mention none of your focus areas. They "
                        "are listed after the ones that do, so nothing is left out."
                    ],
                )
            )
            sections += _jurisdiction_sections(
                register, other_items, products, tier, jurisdiction_names
            )
    ordered = focused_items + other_items

    if rank >= 2 and register.enforcement and register.enforcement.themes:
        intro = "Recurring enforcement themes signal where attention lands."
        if register.enforcement.reference_url:
            intro += f" Live reference: {register.enforcement.reference_url}."
        sections.append(Section("Enforcement Themes", paragraphs=[intro]))
        for theme in register.enforcement.themes:
            paragraphs = [f"What triggers it. {theme.what_triggers}"]
            if tier == "v3":
                if theme.citations:
                    paragraphs.append(f"Governing rule. {_citations(theme.citations)}")
                if theme.note:
                    paragraphs.append(f"Note. {theme.note}")
            sections.append(Section(theme.theme, level=3, paragraphs=paragraphs))

    if tier == "v3":
        actions: list[str] = []
        seen: set[str] = set()
        for obligation in ordered:
            info = register.detail.get(obligation.obligation_id)
            if info and info.action not in seen:
                actions.append(f"{obligation.title}: {info.action}")
                seen.add(info.action)
        sections.append(
            Section(
                "Consolidated Review Items",
                paragraphs=[] if actions else ["No review items recorded."],
                bullets=actions,
            )
        )

    return Document(
        title=f"{register.portfolio.name} regulatory briefing",
        subtitle=TIER_LABEL[tier],
        generated=today.isoformat(),
        sections=sections,
        disclaimer=make_disclaimer(register.portfolio.disclaimer),
    )
