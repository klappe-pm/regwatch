"""Focus areas: the catalogue, matching, and what they do to ranking and briefings."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest
from conftest import TODAY

from regwatch import focus as focus_module
from regwatch.briefing import build_briefing
from regwatch.config import ProfileSettings
from regwatch.document import Document, Section
from regwatch.focus import (
    CUSTOM_TERMS_KEY,
    FocusArea,
    FocusError,
    FocusProfile,
    build_profile,
    load_catalogue,
    parse_catalogue,
    shipped_catalogue_text,
)
from regwatch.impact import assess_impacts
from regwatch.register import Obligation, Product, Register
from regwatch.synthesis import daily_brief, weekly_synthesis

OUTSIDE = "Outside Your Focus Areas"


def entry(**changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"focus_id": "tea", "label": "Tea", "terms": ["tea"]}
    return {**base, **changes}


# --- the catalogue -----------------------------------------------------------


def test_the_shipped_catalogue_covers_the_expected_areas() -> None:
    areas = load_catalogue()
    ids = [a.focus_id for a in areas]
    assert ids == [
        "non-alcoholic-beverages",
        "alcoholic-beverages",
        "cannabis-and-hemp-products",
        "traditional-foods",
        "dietary-supplements",
        "infant-food",
        "pet-food",
        "cosmetics",
    ]
    assert all(a.terms and a.label and a.description for a in areas)
    assert all(t == t.lower() for a in areas for t in a.terms)


def test_the_shipped_catalogue_text_is_valid_json() -> None:
    assert json.loads(shipped_catalogue_text())["version"] == 1


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ([], "must hold a 'focus_areas' list"),
        ({"focus_areas": "x"}, "must hold a 'focus_areas' list"),
        ({"focus_areas": ["x"]}, "entry 1 must be an object"),
        ({"focus_areas": [entry(extra=1)]}, "unknown keys: extra"),
        ({"focus_areas": [entry(focus_id="Tea Time")]}, "lowercase letters, digits and hyphens"),
        ({"focus_areas": [entry(focus_id="")]}, "'focus_id' must be a non-empty string"),
        ({"focus_areas": [entry(label=" ")]}, "'label' must be a non-empty string"),
        ({"focus_areas": [entry(terms=[])]}, "'terms' must be a non-empty list"),
        ({"focus_areas": [entry(terms="tea")]}, "'terms' must be a non-empty list"),
        ({"focus_areas": [entry(terms=["tea", ""])]}, "'terms' must be a non-empty list"),
        ({"focus_areas": [entry(description=3)]}, "'description' must be a string"),
        ({"focus_areas": [entry(), entry()]}, "duplicate focus_id 'tea'"),
    ],
)
def test_a_bad_catalogue_is_refused(data: object, message: str) -> None:
    with pytest.raises(FocusError, match=message):
        parse_catalogue(data)


def test_parse_catalogue_normalises_terms() -> None:
    (area,) = parse_catalogue({"focus_areas": [entry(terms=[" Green Tea ", "green tea", "Chai"])]})
    assert area == FocusArea("tea", "Tea", "", ("green tea", "chai"))


def test_load_catalogue_from_a_file(tmp_path: Path) -> None:
    path = tmp_path / "areas.json"
    path.write_text(json.dumps({"focus_areas": [entry()]}), encoding="utf-8")
    assert [a.focus_id for a in load_catalogue(path)] == ["tea"]


def test_load_catalogue_reports_unreadable_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(FocusError, match="cannot read focus catalogue"):
        load_catalogue(tmp_path / "missing.json")
    bad_text = tmp_path / "binary.json"
    bad_text.write_bytes(b"\xff\xfe")
    with pytest.raises(FocusError, match="cannot read focus catalogue"):
        load_catalogue(bad_text)
    not_json = tmp_path / "not-json.json"
    not_json.write_text("{", encoding="utf-8")
    with pytest.raises(FocusError, match="is not valid JSON"):
        load_catalogue(not_json)
    deep = tmp_path / "deep.json"
    deep.write_text("[" * 5000, encoding="utf-8")
    with pytest.raises(FocusError, match="is not valid JSON"):
        load_catalogue(deep)
    big = tmp_path / "big.json"
    big.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(focus_module, "MAX_CATALOGUE_BYTES", 1)
    with pytest.raises(FocusError, match="is larger than 1 bytes"):
        load_catalogue(big)


# --- the profile -------------------------------------------------------------


def test_build_profile_without_choices_is_inactive() -> None:
    profile = build_profile(ProfileSettings())
    assert profile == FocusProfile()
    assert profile.active is False
    assert profile.matches("anything at all") == ()
    assert profile.names() == []


def test_build_profile_resolves_ids_and_lowercases_custom_terms() -> None:
    profile = build_profile(ProfileSettings(("pet-food", "cosmetics"), ("Boba",)))
    assert profile.active is True
    assert [a.focus_id for a in profile.areas] == ["pet-food", "cosmetics"]
    assert profile.custom_terms == ("boba",)
    assert profile.names() == ["Pet food", "Cosmetics", "custom terms"]


def test_build_profile_rejects_unknown_ids() -> None:
    with pytest.raises(FocusError, match="unknown focus areas: wine-bar; the catalogue offers"):
        build_profile(ProfileSettings(("wine-bar",)))


def test_build_profile_reads_a_user_catalogue(tmp_path: Path) -> None:
    path = tmp_path / "areas.json"
    path.write_text(json.dumps({"focus_areas": [entry()]}), encoding="utf-8")
    profile = build_profile(ProfileSettings(("tea",), (), path))
    assert profile.matches("Tea labelling") == ("tea",)
    with pytest.raises(FocusError, match="unknown focus areas: pet-food"):
        build_profile(ProfileSettings(("pet-food",), (), path))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Distilled spirits labeling", ("alcoholic-beverages",)),
        ("DISTILLED SPIRITS", ("alcoholic-beverages",)),
        ("A rule for wines", ("alcoholic-beverages",)),
        ("Rules on twine and brewing", ()),
        ("the abvious choice", ()),
        ("hemp-derived CBD oil", ("cannabis-and-hemp-products",)),
        ("Pet food and a soft drink", ("non-alcoholic-beverages", "pet-food")),
        ("Fish and chips", ()),
        ("", ()),
    ],
)
def test_matching_is_by_whole_word_without_regard_to_case(
    text: str, expected: tuple[str, ...]
) -> None:
    profile = build_profile(ProfileSettings(tuple(a.focus_id for a in load_catalogue())))
    assert profile.matches(text) == expected


def test_custom_terms_are_reported_under_their_own_key() -> None:
    profile = FocusProfile(custom_terms=("boba",))
    assert profile.matches("A boba shop rule") == (CUSTOM_TERMS_KEY,)
    assert profile.matches("nothing here") == ()


def test_matching_looks_across_all_the_texts_given() -> None:
    profile = FocusProfile(custom_terms=("kombucha",))
    assert profile.matches("one", "two", "Kombucha") == (CUSTOM_TERMS_KEY,)


def test_candidate_matching_ignores_non_text_fields() -> None:
    profile = FocusProfile(custom_terms=("allergen",))
    assert profile.match_candidate({"headline": "Allergen update", "what_happened": 3}) == (
        CUSTOM_TERMS_KEY,
    )
    assert profile.match_candidate({"headline": None, "what_happened": None}) == ()


# --- ranking -----------------------------------------------------------------


def test_without_a_profile_ranking_is_unchanged(register: Register) -> None:
    plain = assess_impacts(register, TODAY)
    assert assess_impacts(register, TODAY, FocusProfile()) == plain
    assert all(i.in_focus and i.focus == () for i in plain)
    assert not any(r.startswith("focus:") for i in plain for r in i.reasons)


def test_focus_areas_rank_matching_candidates_first(register: Register) -> None:
    plain = assess_impacts(register, TODAY)
    ranked = assess_impacts(register, TODAY, ALLERGEN)

    flags = [i.in_focus for i in ranked]
    assert flags == sorted(flags, reverse=True), "in-focus candidates must all come first"
    assert any(flags) and not all(flags)

    # Plain ranking puts the school food rule first. The allergen focus moves the two
    # candidates for the oat bar, whose category is allergens, ahead of every other candidate,
    # including the lower severity one that was last in the plain order.
    assert (plain[0].product_id, plain[0].obligation_id) == (
        "cinnamon-cereal",
        "nl-west-school-food",
    )
    assert [(i.product_id, i.obligation_id) for i in ranked[:2]] == [
        ("oat-bar", "nl-allergen-order"),
        ("oat-bar", "sv-nutrition-claims"),
    ]
    assert ranked[0].reasons[-1] == "focus: custom-terms"
    assert ranked[0].focus == (CUSTOM_TERMS_KEY,)
    assert ranked[1].severity == "watch"
    assert ranked[2].severity == "act-now" and not ranked[2].in_focus


def test_ranking_never_drops_a_candidate(register: Register) -> None:
    plain = assess_impacts(register, TODAY)
    for terms in (("sweetener",), ("zzz-matches-nothing",), ("allergen", "carmine")):
        ranked = assess_impacts(register, TODAY, FocusProfile(custom_terms=terms))
        key = lambda i: (i.product_id, i.obligation_id)  # noqa: E731
        assert sorted(map(key, ranked)) == sorted(map(key, plain))
        assert [i.severity for i in ranked if i.in_focus] == sorted(
            (i.severity for i in ranked if i.in_focus),
            key=["act-now", "high", "watch", "info"].index,
        )


def test_a_profile_that_matches_nothing_marks_everything_outside(register: Register) -> None:
    ranked = assess_impacts(register, TODAY, FocusProfile(custom_terms=("zzz-matches-nothing",)))
    assert len(ranked) == len(assess_impacts(register, TODAY))
    assert not any(i.in_focus for i in ranked)
    assert [i.severity for i in ranked] == [i.severity for i in assess_impacts(register, TODAY)]


def test_a_product_match_counts_as_in_focus(register: Register) -> None:
    profile = FocusProfile(custom_terms=("oat granola",))
    ranked = assess_impacts(register, TODAY, profile)
    assert {i.product_id for i in ranked if i.in_focus} == {"oat-bar"}


# --- briefings ---------------------------------------------------------------


def headings(doc: Document) -> list[str]:
    return [s.heading for s in doc.sections]


def section(doc: Document, heading: str) -> Section:
    (found,) = [s for s in doc.sections if s.heading == heading]
    return found


def all_text(doc: Document) -> str:
    return "\n".join(
        s.heading + "\n" + "\n".join(s.paragraphs) + "\n" + "\n".join(s.bullets)
        for s in doc.sections
    )


ALLERGEN = FocusProfile(custom_terms=("allergen",))


@pytest.mark.parametrize("tier", ["v1", "v2", "v3"])
def test_briefing_lists_everything_and_puts_outside_items_last(
    register: Register, tier: str
) -> None:
    impacts = assess_impacts(register, TODAY, ALLERGEN)
    plain = build_briefing(register, impacts, TODAY, tier=tier)
    doc = build_briefing(register, impacts, TODAY, tier=tier, focus=ALLERGEN)
    assert not any(OUTSIDE in h for h in headings(plain))
    divider = "Key Items Outside Your Focus Areas" if tier == "v1" else OUTSIDE
    at = headings(doc).index(divider)
    before = all_text(Document("t", "", "", doc.sections[:at]))
    after = all_text(Document("t", "", "", doc.sections[at:]))
    assert "Allergen Declaration Order" in before
    outside_titles = [s.heading for s in doc.sections[at:]] + doc.sections[at].bullets
    assert not any("Allergen Declaration Order" in t for t in outside_titles)
    assert "West Region School Food Rule" in after
    text = all_text(doc)
    for obligation in register.obligations:
        assert obligation.title in text, f"{obligation.title} was dropped"
    scope = section(doc, "Scope").paragraphs[0]
    assert "Focus areas: custom terms." in scope


def test_v1_splits_key_items(register: Register) -> None:
    doc = build_briefing(register, [], TODAY, tier="v1", focus=ALLERGEN)
    inside = section(doc, "Key Items").bullets
    outside = section(doc, "Key Items Outside Your Focus Areas").bullets
    assert len(inside) + len(outside) == len(register.obligations)
    assert any("Allergen Declaration Order" in b for b in inside)
    assert not any("Allergen Declaration Order" in b for b in outside)


def test_coming_due_is_split_and_complete(register: Register) -> None:
    doc = build_briefing(register, [], TODAY, tier="v1", focus=ALLERGEN)
    inside = section(doc, "Coming Due").bullets
    outside = section(doc, "Coming Due Outside Your Focus Areas").bullets
    assert inside == ["2027-03-01, nl: Allergen Declaration Order (enacted)"]
    assert len(inside) + len(outside) == 4


def test_an_inactive_profile_changes_nothing(register: Register) -> None:
    impacts = assess_impacts(register, TODAY)
    plain = build_briefing(register, impacts, TODAY, tier="v3")
    assert build_briefing(register, impacts, TODAY, tier="v3", focus=FocusProfile()) == plain


CANDIDATES = [
    {
        "date": "2026-10-12",
        "headline": "Allergen labeling update",
        "what_happened": "Proposes more.",
    },
    {"date": "2026-10-09", "headline": "Fee schedule", "what_happened": "Sets fees."},
    {"date": "2026-10-08", "headline": "Another fee", "what_happened": "More fees."},
]


def test_candidates_are_split_and_each_group_is_capped(register: Register) -> None:
    doc = build_briefing(
        register, [], TODAY, tier="v3", candidates=CANDIDATES, focus=ALLERGEN, recent_count=1
    )
    names = headings(doc)
    start = names.index("Newly Detected, Unconfirmed")
    assert names[start + 1] == "2026-10-12: Allergen labeling update"
    assert names[start + 2] == "Newly Detected Outside Your Focus Areas, Unconfirmed"
    assert names[start + 3] == "2026-10-09: Fee schedule"
    assert "2026-10-08: Another fee" not in names
    assert (
        "Three items from the ingest feed"
        in section(doc, "Newly Detected, Unconfirmed").paragraphs[0]
    )
    assert (
        "Two items from the ingest feed mention none"
        in section(doc, "Newly Detected Outside Your Focus Areas, Unconfirmed").paragraphs[0]
    )


def test_candidates_without_an_outside_group(register: Register) -> None:
    doc = build_briefing(register, [], TODAY, tier="v3", candidates=CANDIDATES[:1], focus=ALLERGEN)
    assert "Newly Detected Outside Your Focus Areas, Unconfirmed" not in headings(doc)
    assert "2026-10-12: Allergen labeling update" in headings(doc)


def test_detail_text_can_bring_an_obligation_into_focus(register: Register) -> None:
    detail = register.detail["nl-colorant-guidance"]
    boosted = dataclasses.replace(
        register,
        detail={
            **register.detail,
            "nl-colorant-guidance": dataclasses.replace(detail, summary="Mentions kombucha."),
        },
    )
    profile = FocusProfile(custom_terms=("kombucha",))
    doc = build_briefing(boosted, [], TODAY, tier="v1", focus=profile)
    assert any("Voluntary Colorant Phase-Out" in b for b in section(doc, "Key Items").bullets)


def test_daily_brief_lists_outside_candidates_under_their_own_heading(
    register: Register,
) -> None:
    impacts = assess_impacts(register, TODAY, FocusProfile(custom_terms=("sweetener",)))
    doc = daily_brief(register, [], impacts, TODAY)
    assert "Flagged Outside Your Focus Areas" in headings(doc)
    inside = section(doc, "Flagged For Review").bullets
    outside = section(doc, "Flagged Outside Your Focus Areas").bullets
    assert inside and outside
    assert not set(inside) & set(outside)
    quiet = daily_brief(register, [], assess_impacts(register, TODAY), TODAY)
    assert "Flagged Outside Your Focus Areas" not in headings(quiet)


def test_weekly_synthesis_lists_outside_candidates_under_their_own_heading(
    register: Register,
) -> None:
    impacts = assess_impacts(register, TODAY, FocusProfile(custom_terms=("sweetener",)))
    doc = weekly_synthesis(register, impacts, [], TODAY)
    names = headings(doc)
    divider = names.index("Candidate Impact Outside Your Focus Areas")
    inside = [b for s in doc.sections[:divider] if s.level == 3 for b in s.bullets]
    outside = [b for s in doc.sections[divider:] if s.level == 3 for b in s.bullets]
    assert len(inside) == sum(i.in_focus for i in impacts)
    assert len(outside) == sum(not i.in_focus for i in impacts)
    assert len(inside) + len(outside) == len(impacts)
    review = section(doc, "Suggested Review Items").bullets
    assert any(b.endswith("Outside your focus areas.") for b in review)
    plain = weekly_synthesis(register, assess_impacts(register, TODAY), [], TODAY)
    assert "Candidate Impact Outside Your Focus Areas" not in headings(plain)


# --- small model checks used by the above ------------------------------------


def test_obligation_and_product_helpers_read_the_expected_fields() -> None:
    profile = FocusProfile(custom_terms=("sucralose", "granola", "claim-x", "csv"))
    obligation = Obligation(
        "o",
        "nl",
        "statute",
        "",
        "T",
        ("a",),
        ("Sucralose",),
        (),
        (),
        "enacted",
        "",
        "",
        "s",
        "",
        "d",
        "high",
        "",
    )
    product = Product("p", "Oat Granola", "", (), (), ("claim-x",), ("nl",), ())
    assert profile.match_obligation(obligation) == (CUSTOM_TERMS_KEY,)
    assert profile.match_product(product) == (CUSTOM_TERMS_KEY,)
    assert FocusProfile(custom_terms=("csv",)).match_product(product) == ()
