from __future__ import annotations

import dataclasses
import datetime as dt

import pytest
from conftest import TODAY

from regwatch.impact import (
    assess_impacts,
    jurisdiction_applies,
    scope_applies,
    theme_findings,
)
from regwatch.register import Obligation, Product, Register

PARENTS = {"nl": "", "nl-east": "nl", "nl-west": "nl", "sv": "", "sv-multi": "sv"}


@pytest.mark.parametrize(
    ("jurisdiction", "markets", "expected"),
    [
        ("nl", ["nl"], True),
        ("nl", ["nl-east"], True),
        ("nl-east", ["nl"], True),
        ("nl-east", ["nl-east"], True),
        ("nl-east", ["nl-west"], False),
        ("nl-east", ["sv"], False),
        ("sv-multi", ["sv"], True),
        ("sv", ["sv-multi"], True),
        ("nl-west", ["nl-east", "nl-west"], True),
        ("nl", [], False),
        ("unknown", ["nl"], False),
    ],
)
def test_jurisdiction_applies(jurisdiction: str, markets: list[str], expected: bool) -> None:
    assert jurisdiction_applies(jurisdiction, markets, PARENTS) is expected


@pytest.mark.parametrize(
    ("obligation_scope", "product_scopes", "expected"),
    [
        ([], [], True),
        (["all"], [], True),
        (["all", "school-channel"], [], True),
        (["school-channel"], [], False),
        (["school-channel"], ["retail"], False),
        (["school-channel"], ["retail", "school-channel"], True),
        (["retail", "export"], ["export"], True),
    ],
)
def test_scope_applies(
    obligation_scope: list[str], product_scopes: list[str], expected: bool
) -> None:
    assert scope_applies(obligation_scope, product_scopes) is expected


def test_example_impacts_are_ranked_and_explained(register: Register) -> None:
    impacts = assess_impacts(register, TODAY)
    assert [(i.severity, i.product_id, i.obligation_id) for i in impacts] == [
        ("act-now", "cinnamon-cereal", "nl-west-school-food"),
        ("act-now", "berry-spread", "nl-colorant-guidance"),
        ("act-now", "oat-bar", "nl-allergen-order"),
        ("watch", "berry-spread", "nl-east-sweetener-bill"),
        ("watch", "cinnamon-cereal", "nl-east-sweetener-bill"),
        ("watch", "cinnamon-cereal", "sv-multi-sweetener-bills"),
        ("watch", "oat-bar", "sv-nutrition-claims"),
    ]
    first = impacts[0]
    assert first.reasons == ("category: sweeteners", "term: sucralose")
    assert first.product_name == "Cinnamon Breakfast Cereal"
    assert first.effective_date == "2026-11-15"


def test_scope_gate_excludes_school_rule_for_products_outside_the_channel(
    register: Register,
) -> None:
    products = tuple(
        dataclasses.replace(p, scopes=("retail",)) for p in register.portfolio.products
    )
    trimmed = dataclasses.replace(
        register, portfolio=dataclasses.replace(register.portfolio, products=products)
    )
    ids = {i.obligation_id for i in assess_impacts(trimmed, TODAY)}
    assert "nl-west-school-food" not in ids


def test_exposure_gate_excludes_other_regions(register: Register) -> None:
    only_east = Product("p", "P", "", ("sweeteners",), (), (), ("nl-east",), ("retail",))
    portfolio = dataclasses.replace(register.portfolio, products=(only_east,))
    narrowed = dataclasses.replace(register, portfolio=portfolio)
    ids = {i.obligation_id for i in assess_impacts(narrowed, TODAY)}
    assert "nl-east-sweetener-bill" in ids
    assert "nl-west-school-food" not in ids
    assert "sv-multi-sweetener-bills" not in ids


def test_attribute_gate_requires_a_match(register: Register) -> None:
    bare = Product("p", "P", "", (), (), (), ("nl", "sv"), ("retail",))
    narrowed = dataclasses.replace(
        register, portfolio=dataclasses.replace(register.portfolio, products=(bare,))
    )
    assert assess_impacts(narrowed, TODAY) == []


def test_term_matching_is_case_insensitive(register: Register) -> None:
    product = Product("p", "P", "", (), ("CARMINE",), (), ("nl",), ("retail",))
    narrowed = dataclasses.replace(
        register, portfolio=dataclasses.replace(register.portfolio, products=(product,))
    )
    impacts = assess_impacts(narrowed, TODAY)
    assert [i.obligation_id for i in impacts] == ["nl-colorant-guidance"]
    assert impacts[0].reasons == ("term: carmine",)


def obligation(**changes: object) -> Obligation:
    base = Obligation(
        "o",
        "nl",
        "statute",
        "",
        "T",
        ("sweeteners",),
        (),
        (),
        (),
        "enacted",
        "",
        "",
        "src",
        "",
        "2026-01-01",
        "high",
        "",
    )
    return dataclasses.replace(base, **changes)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("changes", "severity"),
    [
        ({"status": "enacted", "effective_date": "2026-12-01"}, "act-now"),
        ({"status": "enacted", "effective_date": "2027-08-01"}, "high"),
        ({"status": "enacted", "effective_date": "2030-01-01"}, "watch"),
        ({"status": "enacted", "effective_date": "2026-01-01"}, "act-now"),
        ({"status": "proposed", "effective_date": "2026-01-01"}, "watch"),
        ({"status": "proposed", "effective_date": "2026-12-01"}, "high"),
        ({"status": "proposed", "effective_date": "2027-08-01"}, "watch"),
        ({"status": "proposed", "effective_date": ""}, "watch"),
        ({"status": "monitoring", "effective_date": ""}, "info"),
        ({"status": "monitoring", "effective_date": "not-a-date"}, "info"),
        ({"status": "voluntary", "effective_date": "2026-12-01"}, "high"),
    ],
)
def test_severity_scoring(register: Register, changes: dict[str, object], severity: str) -> None:
    product = Product("p", "P", "", ("sweeteners",), (), (), ("nl",), ())
    custom = dataclasses.replace(
        register,
        obligations=(obligation(**changes),),
        portfolio=dataclasses.replace(register.portfolio, products=(product,)),
    )
    assert [i.severity for i in assess_impacts(custom, TODAY)] == [severity]


def test_a_named_term_adds_a_point(register: Register) -> None:
    def severity_for(product: Product) -> str:
        custom = dataclasses.replace(
            register,
            obligations=(
                obligation(terms=("sucralose",), status="proposed", effective_date="2026-12-01"),
            ),
            portfolio=dataclasses.replace(register.portfolio, products=(product,)),
        )
        return assess_impacts(custom, TODAY)[0].severity

    category_only = Product("p", "P", "", ("sweeteners",), (), (), ("nl",), ())
    with_term = Product("p", "P", "", ("sweeteners",), ("sucralose",), (), ("nl",), ())
    assert severity_for(category_only) == "high"
    assert severity_for(with_term) == "act-now"


def test_today_defaults_to_the_current_date(register: Register) -> None:
    assert assess_impacts(register) == assess_impacts(register, dt.date.today())


def test_theme_findings(register: Register) -> None:
    impacts = assess_impacts(register, TODAY)
    findings = theme_findings(register, impacts, register.themes)
    by_key = {f.key: f for f in findings}
    assert set(by_key) == {"sweeteners", "allergens"}
    sweet = by_key["sweeteners"]
    assert sweet.title == "Sweeteners and added sugar"
    assert sweet.affected_products == ("Berry Fruit Spread", "Cinnamon Breakfast Cereal")
    assert sweet.obligations == (
        "East Region Sweetener Labeling Bill",
        "Regional Sweetener Bills (aggregate)",
        "West Region School Food Rule",
    )
    assert by_key["allergens"].affected_products == ("Oat Granola Bar",)


def test_theme_without_matching_obligations_or_products_is_skipped(register: Register) -> None:
    from regwatch.register import Theme

    ghost = Theme("ghost", "Ghost", ("origin-labeling",), "why", "act")
    findings = theme_findings(register, [], [ghost])
    assert [f.key for f in findings] == ["ghost"]
    assert findings[0].affected_products == ()
    empty = Theme("none", "None", ("colorants-nothing",), "why", "act")
    assert theme_findings(register, [], [empty]) == []
