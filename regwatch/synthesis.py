"""Turn register rows, check results and impacts into document models.

Two cadences are produced. The daily brief is short and driven by what changed.
The weekly synthesis maps the whole register onto the portfolio. The digest lists
the register by jurisdiction and the report is a change and due alert. All are
deterministic: they assemble text from structured data and call no external
service, so the same inputs always give the same document.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping

from regwatch.check import SourceResult
from regwatch.document import Document, Section, make_disclaimer
from regwatch.impact import SEVERITIES, SEVERITY_RANK, Finding, Impact
from regwatch.register import Obligation, Register, parse_date
from regwatch.wording import (
    count,
    join_clauses,
    number,
    prose_date,
    severity_label,
    status_phrase,
)

__all__ = [
    "daily_brief",
    "digest_document",
    "report_document",
    "upcoming_obligations",
    "weekly_synthesis",
]


def upcoming_obligations(
    obligations: Iterable[Obligation], days: int, today: dt.date
) -> list[Obligation]:
    """Return obligations whose effective date falls from today to ``days`` days ahead.

    The soonest comes first.
    """
    horizon = today + dt.timedelta(days=days)
    kept = []
    for obligation in obligations:
        date = parse_date(obligation.effective_date)
        if date is not None and today <= date <= horizon:
            kept.append(obligation)
    return sorted(kept, key=lambda o: o.effective_date)


def _due_line(obligation: Obligation, places: Mapping[str, str] | None = None) -> str:
    place = (places or {}).get(obligation.jurisdiction, obligation.jurisdiction)
    return (
        f"{prose_date(obligation.effective_date)}, {place}: "
        f"{obligation.title} ({obligation.status})"
    )


def _places(register: Register) -> dict[str, str]:
    return {j.jurisdiction_id: j.name for j in register.jurisdictions}


def _source_names(register: Register) -> dict[str, str]:
    return {s.source_id: s.name for s in register.sources}


def _source_line(result: SourceResult, names: Mapping[str, str]) -> str:
    return f"{names.get(result.source_id, result.source_id)}: " + status_phrase(
        result.status, result.detail
    )


def _product_sections(impacts: list[Impact], places: Mapping[str, str]) -> list[Section]:
    """One level 3 section per product, products with the worst candidate first."""
    by_product: dict[str, list[Impact]] = {}
    for impact in impacts:
        by_product.setdefault(impact.product_name, []).append(impact)
    sections = []
    for name in sorted(
        by_product, key=lambda n: min(SEVERITY_RANK[i.severity] for i in by_product[n])
    ):
        bullets = [
            f"{i.obligation_title}, {places.get(i.jurisdiction, i.jurisdiction)}, "
            f"{severity_label(i.severity)} severity"
            + (f", effective {prose_date(i.effective_date)}" if i.effective_date else "")
            + (f" [{'; '.join(i.reasons)}]" if i.reasons else "")
            for i in by_product[name]
        ]
        sections.append(Section(name, level=3, bullets=bullets))
    return sections


def daily_brief(
    register: Register,
    results: Iterable[SourceResult],
    impacts: Iterable[Impact],
    today: dt.date,
) -> Document:
    """Build the short, change-driven brief."""
    result_list = list(results)
    impact_list = list(impacts)
    sections: list[Section] = []
    places, names = _places(register), _source_names(register)

    changed = [r for r in result_list if r.flagged]
    what_changed = Section("What Changed")
    if changed:
        what_changed.paragraphs.append(
            f"{count(len(changed), 'upstream source').capitalize()} "
            f"{'has' if len(changed) == 1 else 'have'} changed since the last accepted "
            f"baseline and {'needs' if len(changed) == 1 else 'need'} a look."
        )
        what_changed.bullets = [_source_line(r, names) for r in changed]
    else:
        what_changed.paragraphs.append(
            "No upstream source changes since the last accepted baseline."
        )
    errors = [r for r in result_list if r.status == "ERROR"]
    if errors:
        what_changed.bullets += [_source_line(r, names) for r in errors]
    sections.append(what_changed)

    soon = upcoming_obligations(register.obligations, 30, today)
    sections.append(
        Section(
            "Effective Within 30 Days",
            paragraphs=[] if soon else ["Nothing reaches an effective date in the next 30 days."],
            bullets=[_due_line(o, places) for o in soon],
        )
    )

    urgent = [i for i in impact_list if i.severity in ("act-now", "high")]
    priority = [i for i in urgent if i.in_focus][:6]
    outside = [i for i in urgent if not i.in_focus][:6]

    def flagged(items: list[Impact]) -> list[str]:
        return [
            f"{i.product_name}: {i.obligation_title} "
            f"({places.get(i.jurisdiction, i.jurisdiction)}, {severity_label(i.severity)} severity)"
            for i in items
        ]

    sections.append(
        Section(
            "Flagged For Review",
            paragraphs=[] if priority else ["No act-now or high severity candidate impacts today."],
            bullets=flagged(priority),
        )
    )
    if outside:
        sections.append(Section("Flagged Outside Your Focus Areas", bullets=flagged(outside)))
    return Document(
        title=f"{register.portfolio.name} regulatory daily brief",
        subtitle="Change detection and near-term obligations",
        generated=today.isoformat(),
        sections=sections,
        disclaimer=make_disclaimer(register.portfolio.disclaimer),
    )


def weekly_synthesis(
    register: Register,
    impacts: Iterable[Impact],
    findings: Iterable[Finding],
    today: dt.date,
) -> Document:
    """Build the full weekly analysis of the register against the portfolio."""
    impact_list = list(impacts)
    finding_list = list(findings)
    products = register.portfolio.products
    confirmed = sum(1 for j in register.jurisdictions if j.coverage == "confirmed")
    counts = {name: sum(1 for i in impact_list if i.severity == name) for name in SEVERITIES}
    impacted = sorted({i.product_id for i in impact_list})
    soonest = upcoming_obligations(register.obligations, 365, today)

    places = _places(register)
    severity_clauses = [
        f"{number(counts[name])} {severity_label(name)}" if counts[name] else ""
        for name in SEVERITIES
    ]
    flagged_text = (
        f"{count(len(impact_list), 'candidate impact').capitalize()} "
        f"{'was' if len(impact_list) == 1 else 'were'} flagged: "
        f"{join_clauses(severity_clauses)}. "
        f"{number(len(impacted)).capitalize()} of {count(len(products), 'product')} "
        f"{'carries' if len(impacted) == 1 else 'carry'} at least one."
        if impact_list
        else "No candidate impact was flagged."
    )
    summary = [
        f"{register.portfolio.name} models {count(len(products), 'product')}. The register "
        f"tracks {count(len(register.obligations), 'obligation')} across "
        f"{count(len(register.jurisdictions), 'jurisdiction')}, "
        f"{number(confirmed)} of them with confirmed coverage.",
        flagged_text,
    ]
    if soonest:
        first = soonest[0]
        summary.append(
            f"{count(len(soonest), 'obligation').capitalize()} "
            f"{'reaches' if len(soonest) == 1 else 'reach'} an effective date within a year; "
            f"the soonest is {first.title} "
            f"({places.get(first.jurisdiction, first.jurisdiction)}) on "
            f"{prose_date(first.effective_date)}."
        )
    sections = [Section("Executive Summary", paragraphs=summary)]
    sections.append(
        Section(
            "Coming Due Within 365 Days",
            paragraphs=[] if soonest else ["No obligations reach an effective date within a year."],
            bullets=[_due_line(o, places) for o in soonest],
        )
    )
    sections.append(
        Section(
            "Candidate Impact By Product",
            paragraphs=[
                f"{number(len(impacted)).capitalize()} of {count(len(products), 'product')} "
                f"{'has' if len(impacted) == 1 else 'have'} flagged candidates. Each product's "
                "candidates are listed worst first. Each one needs human confirmation."
            ],
        )
    )
    sections += _product_sections([i for i in impact_list if i.in_focus], places)
    outside = [i for i in impact_list if not i.in_focus]
    if outside:
        sections.append(
            Section(
                "Candidate Impact Outside Your Focus Areas",
                paragraphs=[
                    f"{count(len(outside), 'candidate').capitalize()} "
                    f"{'mentions' if len(outside) == 1 else 'mention'} none of your focus "
                    f"areas. {'It is' if len(outside) == 1 else 'They are'} listed after the "
                    "ones that do, and each one still needs human confirmation."
                ],
            )
        )
        sections += _product_sections(outside, places)

    if finding_list:
        sections.append(
            Section(
                "Themes",
                paragraphs=[
                    "Where the portfolio meets the rules, read through each configured theme."
                ],
            )
        )
        for finding in finding_list:
            bullets = []
            if finding.affected_products:
                bullets.append("Affected products: " + ", ".join(finding.affected_products))
            if finding.obligations:
                bullets.append("Related obligations: " + ", ".join(finding.obligations))
            bullets.append("Action: " + finding.action)
            sections.append(
                Section(finding.title, level=3, paragraphs=[finding.why], bullets=bullets)
            )

    actions = [
        "Review now: "
        f"{i.product_name} against {i.obligation_title} "
        f"({places.get(i.jurisdiction, i.jurisdiction)}"
        + (f", effective {prose_date(i.effective_date)}" if i.effective_date else "")
        + ")."
        + ("" if i.in_focus else " Outside your focus areas.")
        for i in impact_list
        if i.severity == "act-now"
    ]
    for finding in finding_list:
        if finding.action not in actions:
            actions.append(finding.action)
    sections.append(
        Section(
            "Suggested Review Items",
            paragraphs=[] if actions else ["No review items are outstanding this week."],
            bullets=actions,
        )
    )
    return Document(
        title=f"{register.portfolio.name} regulatory weekly synthesis",
        subtitle="Candidate impact analysis for review",
        generated=today.isoformat(),
        sections=sections,
        disclaimer=make_disclaimer(register.portfolio.disclaimer),
    )


def digest_document(register: Register, today: dt.date, window: int) -> Document:
    """The register digest: obligations effective within ``window`` days, then every
    obligation grouped by jurisdiction."""
    upcoming = upcoming_obligations(register.obligations, window, today)
    names = _places(register)
    sections = [
        Section(
            f"Effective Within {window} Days",
            paragraphs=[] if upcoming else ["None."],
            bullets=[_due_line(o, names) for o in upcoming],
        )
    ]
    by_jurisdiction: dict[str, list[Obligation]] = {}
    for obligation in register.obligations:
        by_jurisdiction.setdefault(obligation.jurisdiction, []).append(obligation)
    sections.append(Section("Register By Jurisdiction"))
    for jid in sorted(by_jurisdiction):
        bullets = [
            f"{o.title}: {o.status}, "
            + (f"effective {prose_date(o.effective_date)}" if o.effective_date else "no date")
            for o in sorted(by_jurisdiction[jid], key=lambda o: o.title)
        ]
        sections.append(Section(names.get(jid, jid), level=3, bullets=bullets))
    return Document(
        f"{register.portfolio.name} register digest",
        today.isoformat(),
        "Register digest for analyst review",
        sections,
        make_disclaimer(register.portfolio.disclaimer),
    )


def report_document(
    register: Register, results: Iterable[SourceResult], today: dt.date, window: int
) -> Document:
    """The change and due alert: source changes to review and obligations coming due."""
    result_list = list(results)
    flagged = [r for r in result_list if r.flagged]
    missing = [r for r in result_list if r.status == "MISSING"]
    errors = [r for r in result_list if r.status == "ERROR"]
    upcoming = upcoming_obligations(register.obligations, window, today)
    names, places = _source_names(register), _places(register)
    changes = Section("Source Changes To Review")
    if flagged:
        changes.bullets = [_source_line(r, names) for r in flagged]
    else:
        changes.paragraphs.append("No source changes since the last accepted state.")
    if missing:
        changes.paragraphs.append(
            f"{count(len(missing), 'source').capitalize()} "
            f"{'has' if len(missing) == 1 else 'have'} no snapshot yet; capture one or use "
            "--fetch."
        )
    changes.bullets += [_source_line(r, names) for r in errors]
    due = Section(
        f"Obligations Effective Within {window} Days",
        paragraphs=[] if upcoming else ["None."],
        bullets=[_due_line(o, places) for o in upcoming],
    )
    return Document(
        f"{register.portfolio.name} change and due alert",
        today.isoformat(),
        "Change and due alert",
        [changes, due],
        make_disclaimer(register.portfolio.disclaimer),
    )
