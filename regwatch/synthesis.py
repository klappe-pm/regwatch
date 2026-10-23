"""Turn register rows, check results and impacts into document models.

Two cadences are produced. The daily brief is short and driven by what changed.
The weekly synthesis maps the whole register onto the portfolio. The digest lists
the register by jurisdiction and the report is a change and due alert. All are
deterministic: they assemble text from structured data and call no external
service, so the same inputs always give the same document.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable

from regwatch.check import SourceResult
from regwatch.document import Document, Section, make_disclaimer
from regwatch.impact import SEVERITIES, SEVERITY_RANK, Finding, Impact
from regwatch.register import Obligation, Register, parse_date

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


def _due_line(obligation: Obligation) -> str:
    return (
        f"{obligation.effective_date}, {obligation.jurisdiction}: "
        f"{obligation.title} ({obligation.status})"
    )


def _product_sections(impacts: list[Impact]) -> list[Section]:
    """One level 3 section per product, products with the worst candidate first."""
    by_product: dict[str, list[Impact]] = {}
    for impact in impacts:
        by_product.setdefault(impact.product_name, []).append(impact)
    sections = []
    for name in sorted(
        by_product, key=lambda n: min(SEVERITY_RANK[i.severity] for i in by_product[n])
    ):
        bullets = [
            f"{i.obligation_title}, {i.jurisdiction}, {i.severity}"
            + (f", effective {i.effective_date}" if i.effective_date else "")
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

    changed = [r for r in result_list if r.flagged]
    what_changed = Section("What Changed")
    if changed:
        what_changed.paragraphs.append(
            f"{len(changed)} upstream source(s) changed since the last accepted baseline "
            "and need a look."
        )
        what_changed.bullets = [f"{r.status}: {r.source_id}" for r in changed]
    else:
        what_changed.paragraphs.append(
            "No upstream source changes since the last accepted baseline."
        )
    errors = [r for r in result_list if r.status == "ERROR"]
    if errors:
        what_changed.bullets += [f"ERROR: {r.source_id} ({r.detail})" for r in errors]
    sections.append(what_changed)

    soon = upcoming_obligations(register.obligations, 30, today)
    sections.append(
        Section(
            "Effective Within 30 Days",
            paragraphs=[] if soon else ["Nothing reaches an effective date in the next 30 days."],
            bullets=[_due_line(o) for o in soon],
        )
    )

    urgent = [i for i in impact_list if i.severity in ("act-now", "high")]
    priority = [i for i in urgent if i.in_focus][:6]
    outside = [i for i in urgent if not i.in_focus][:6]

    def flagged(items: list[Impact]) -> list[str]:
        return [
            f"{i.product_name}: {i.obligation_title} ({i.jurisdiction}, {i.severity})"
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

    summary = [
        f"{register.portfolio.name} models {len(products)} product(s). The register tracks "
        f"{len(register.obligations)} obligation(s) across "
        f"{len(register.jurisdictions)} jurisdiction(s), "
        f"{confirmed} of them with confirmed coverage.",
        f"{len(impact_list)} candidate impact(s) were flagged: {counts['act-now']} act-now, "
        f"{counts['high']} high, {counts['watch']} watch and {counts['info']} informational. "
        f"{len(impacted)} of {len(products)} product(s) carry at least one.",
    ]
    if soonest:
        first = soonest[0]
        summary.append(
            f"{len(soonest)} obligation(s) reach an effective date within a year; the soonest is "
            f"{first.title} ({first.jurisdiction}) on {first.effective_date}."
        )
    sections = [Section("Executive Summary", paragraphs=summary)]
    sections.append(
        Section(
            "Coming Due Within 365 Days",
            paragraphs=[] if soonest else ["No obligations reach an effective date within a year."],
            bullets=[_due_line(o) for o in soonest],
        )
    )
    sections.append(
        Section(
            "Candidate Impact By Product",
            paragraphs=[
                f"{len(impacted)} of {len(products)} product(s) have flagged candidates. "
                "Each product's "
                "candidates are listed worst first. Each one needs human confirmation."
            ],
        )
    )
    sections += _product_sections([i for i in impact_list if i.in_focus])
    outside = [i for i in impact_list if not i.in_focus]
    if outside:
        sections.append(
            Section(
                "Candidate Impact Outside Your Focus Areas",
                paragraphs=[
                    f"{len(outside)} candidate(s) mention none of your focus areas. "
                    "They are listed "
                    "after the ones that do, and each one still needs human confirmation."
                ],
            )
        )
        sections += _product_sections(outside)

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
        f"{i.product_name} against {i.obligation_title} ({i.jurisdiction}"
        + (f", effective {i.effective_date}" if i.effective_date else "")
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
    names = {j.jurisdiction_id: j.name for j in register.jurisdictions}
    sections = [
        Section(
            f"Effective Within {window} Days",
            paragraphs=[] if upcoming else ["None."],
            bullets=[_due_line(o) for o in upcoming],
        )
    ]
    by_jurisdiction: dict[str, list[Obligation]] = {}
    for obligation in register.obligations:
        by_jurisdiction.setdefault(obligation.jurisdiction, []).append(obligation)
    sections.append(Section("Register By Jurisdiction"))
    for jid in sorted(by_jurisdiction):
        bullets = [
            f"{o.title}: {o.status}, {o.effective_date or 'no date'}"
            for o in sorted(by_jurisdiction[jid], key=lambda o: o.title)
        ]
        sections.append(Section(names.get(jid, jid), level=3, bullets=bullets))
    return Document(
        "regwatch digest",
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
    changes = Section("Source Changes To Review")
    if flagged:
        changes.bullets = [f"{r.status}: {r.source_id} ({r.origin})" for r in flagged]
    else:
        changes.paragraphs.append("No source changes since the last accepted state.")
    if missing:
        changes.paragraphs.append(
            f"{len(missing)} source(s) have no snapshot; capture one or use --fetch."
        )
    changes.bullets += [f"ERROR: {r.source_id} ({r.detail})" for r in errors]
    due = Section(
        f"Obligations Effective Within {window} Days",
        paragraphs=[] if upcoming else ["None."],
        bullets=[_due_line(o) for o in upcoming],
    )
    return Document(
        "regwatch report",
        today.isoformat(),
        "Change and due alert",
        [changes, due],
        make_disclaimer(register.portfolio.disclaimer),
    )
