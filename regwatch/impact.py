"""Candidate impact analysis.

Impact analysis joins the obligations in the register to the products in the
portfolio and flags the pairs a person should look at. Everything here is a
pure function over already loaded data.

An obligation is flagged against a product only when all three gates pass:

1. Exposure: the obligation's jurisdiction and one of the product's markets lie
   on the same path of the jurisdiction tree, so a national rule reaches a
   regional market and a product sold nationally is exposed to every regional
   rule.
2. Scope: the obligation has no scope tags (or the tag ``all``), or shares a
   tag with the product's scopes.
3. Attribute match: the obligation and the product share a category, a named
   term or a claim.

A flagged pair is a candidate for review, never a determination.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass

from regwatch.register import Obligation, Product, Register, Theme, ancestors

__all__ = [
    "SEVERITIES",
    "Finding",
    "Impact",
    "assess_impacts",
    "jurisdiction_applies",
    "scope_applies",
    "theme_findings",
]

SEVERITIES = ("act-now", "high", "watch", "info")
SEVERITY_RANK = {name: rank for rank, name in enumerate(SEVERITIES)}
STATUS_WEIGHT = {
    "enacted": 2,
    "finalized": 2,
    "proposed": 1,
    "voluntary": 1,
    "in-progress": 1,
    "monitoring": 0,
}


@dataclass(frozen=True)
class Impact:
    """One flagged obligation and product pair."""

    product_id: str
    product_name: str
    obligation_id: str
    obligation_title: str
    jurisdiction: str
    status: str
    effective_date: str
    reasons: tuple[str, ...]
    severity: str


@dataclass(frozen=True)
class Finding:
    """A theme lens result: why it matters, what to do and who it touches."""

    key: str
    title: str
    why: str
    action: str
    affected_products: tuple[str, ...]
    obligations: tuple[str, ...]


def jurisdiction_applies(
    jurisdiction: str, markets: Iterable[str], parents: dict[str, str]
) -> bool:
    """True when ``jurisdiction`` and any of ``markets`` lie on one path of the tree."""
    above_jurisdiction = ancestors(jurisdiction, parents)
    for market in markets:
        if market == jurisdiction or market in above_jurisdiction:
            return True
        if jurisdiction in ancestors(market, parents):
            return True
    return False


def scope_applies(obligation_scope: Iterable[str], product_scopes: Iterable[str]) -> bool:
    """True when the obligation has no scope limit or shares a scope with the product."""
    scope = set(obligation_scope)
    if not scope or "all" in scope:
        return True
    return bool(scope & set(product_scopes))


def _near_term(effective_date: str, status: str, today: dt.date) -> int:
    try:
        days = (dt.date.fromisoformat(effective_date) - today).days if effective_date else None
    except ValueError:
        days = None
    if days is None:
        return 0
    if days < 0:
        return 2 if status in ("enacted", "finalized") else 0
    if days <= 180:
        return 2
    if days <= 365:
        return 1
    return 0


def _severity(score: int) -> str:
    if score >= 4:
        return "act-now"
    if score >= 3:
        return "high"
    return "watch" if score >= 1 else "info"


def _impact_for(
    obligation: Obligation, product: Product, parents: dict[str, str], today: dt.date
) -> Impact | None:
    if not jurisdiction_applies(obligation.jurisdiction, product.markets, parents):
        return None
    if not scope_applies(obligation.scope, product.scopes):
        return None
    category_match = sorted(set(obligation.categories) & set(product.categories))
    product_terms = {term.lower() for term in product.terms}
    term_match = sorted(term for term in obligation.terms if term.lower() in product_terms)
    claim_match = sorted(set(obligation.claims) & set(product.claims))
    if not (category_match or term_match or claim_match):
        return None

    reasons: list[str] = []
    if category_match:
        reasons.append("category: " + ", ".join(category_match))
    if term_match:
        reasons.append("term: " + ", ".join(term_match))
    if claim_match:
        reasons.append("claim: " + ", ".join(claim_match))

    score = STATUS_WEIGHT.get(obligation.status, 0)
    score += _near_term(obligation.effective_date, obligation.status, today)
    score += 1 if term_match else 0
    return Impact(
        product_id=product.product_id,
        product_name=product.name,
        obligation_id=obligation.obligation_id,
        obligation_title=obligation.title,
        jurisdiction=obligation.jurisdiction,
        status=obligation.status,
        effective_date=obligation.effective_date,
        reasons=tuple(reasons),
        severity=_severity(score),
    )


def assess_impacts(register: Register, today: dt.date | None = None) -> list[Impact]:
    """Flag candidate impacts of every obligation on every product, worst first."""
    today = today or dt.date.today()
    parents = {j.jurisdiction_id: j.parent for j in register.jurisdictions}
    impacts: list[Impact] = []
    for product in register.portfolio.products:
        for obligation in register.obligations:
            impact = _impact_for(obligation, product, parents, today)
            if impact is not None:
                impacts.append(impact)
    impacts.sort(
        key=lambda i: (SEVERITY_RANK[i.severity], i.effective_date or "9999", i.product_id)
    )
    return impacts


def theme_findings(
    register: Register, impacts: Iterable[Impact], themes: Iterable[Theme]
) -> list[Finding]:
    """Apply each configured theme as a lens over the obligations and impacts."""
    impact_list = list(impacts)
    categories_of = {o.obligation_id: set(o.categories) for o in register.obligations}
    titles = {o.obligation_id: o.title for o in register.obligations}
    product_categories = {p.product_id: set(p.categories) for p in register.portfolio.products}
    product_names = {p.product_id: p.name for p in register.portfolio.products}

    findings: list[Finding] = []
    for theme in themes:
        wanted = set(theme.categories)
        obligations = sorted({titles[oid] for oid, cats in categories_of.items() if cats & wanted})
        affected = sorted(
            {
                product_names[i.product_id]
                for i in impact_list
                if categories_of.get(i.obligation_id, set()) & wanted
                and product_categories.get(i.product_id, set()) & wanted
            }
        )
        if not obligations and not affected:
            continue
        findings.append(
            Finding(
                theme.key, theme.title, theme.why, theme.action, tuple(affected), tuple(obligations)
            )
        )
    return findings
