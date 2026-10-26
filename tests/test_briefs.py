from __future__ import annotations

import dataclasses
import datetime as dt
from typing import Any

import pytest
from conftest import NOW, TODAY

from regwatch.briefing import TIERS, build_briefing
from regwatch.check import SourceResult, accept_results, check_sources
from regwatch.config import Config
from regwatch.document import DISCLAIMER, Document
from regwatch.impact import assess_impacts, theme_findings
from regwatch.register import Register
from regwatch.synthesis import daily_brief, upcoming_obligations, weekly_synthesis


def headings(doc: Document) -> list[str]:
    return [s.heading for s in doc.sections]


def section(doc: Document, heading: str) -> Any:
    return next(s for s in doc.sections if s.heading == heading)


def test_upcoming_obligations(register: Register) -> None:
    soon = upcoming_obligations(register.obligations, 60, TODAY)
    assert [o.obligation_id for o in soon] == ["nl-west-school-food"]
    year = upcoming_obligations(register.obligations, 365, TODAY)
    assert [o.obligation_id for o in year] == [
        "nl-west-school-food",
        "nl-colorant-guidance",
        "nl-allergen-order",
        "sv-origin-labeling",
    ]
    assert upcoming_obligations(register.obligations, 0, TODAY) == []
    assert upcoming_obligations(register.obligations, 30, dt.date(2030, 1, 1)) == []


def test_daily_brief_with_changes_and_errors(config: Config, register: Register) -> None:
    results = check_sources(register.sources, {}, config.snapshots_dir)
    results.append(SourceResult("broken", "ERROR", "live", None, "fetch failed: boom"))
    doc = daily_brief(register, results, assess_impacts(register, TODAY), TODAY)
    assert headings(doc) == ["What Changed", "Effective Within 30 Days", "Flagged For Review"]
    changed = section(doc, "What Changed")
    assert "Four upstream sources have changed" in changed.paragraphs[0]
    assert "Northland regulator notices feed: first snapshot taken" in changed.bullets
    assert "broken: could not be read (fetch failed: boom)" in changed.bullets
    assert section(doc, "Effective Within 30 Days").bullets == [
        "15 November 2026, Northland West Region: West Region School Food Rule (enacted)"
    ]
    flagged = section(doc, "Flagged For Review").bullets
    assert flagged[0] == (
        "Cinnamon Breakfast Cereal: West Region School Food Rule "
        "(Northland West Region, act now severity)"
    )
    assert len(flagged) == 3
    assert doc.title == "Example Pantry Co. regulatory daily brief"
    assert doc.generated == "2026-10-19"
    assert doc.disclaimer.startswith(DISCLAIMER)
    assert "Synthetic example data" in doc.disclaimer


def test_daily_brief_when_quiet(config: Config, register: Register) -> None:
    seen = accept_results({}, check_sources(register.sources, {}, config.snapshots_dir), NOW)
    results = check_sources(register.sources, seen, config.snapshots_dir)
    quiet = dataclasses.replace(register, obligations=())
    doc = daily_brief(quiet, results, [], TODAY)
    assert section(doc, "What Changed").paragraphs == [
        "No upstream source changes since the last accepted baseline."
    ]
    assert (
        "Nothing reaches an effective date"
        in section(doc, "Effective Within 30 Days").paragraphs[0]
    )
    assert "No act-now or high severity" in section(doc, "Flagged For Review").paragraphs[0]


def test_weekly_synthesis(register: Register) -> None:
    impacts = assess_impacts(register, TODAY)
    findings = theme_findings(register, impacts, register.themes)
    doc = weekly_synthesis(register, impacts, findings, TODAY)
    assert headings(doc)[:4] == [
        "Executive Summary",
        "Coming Due Within 365 Days",
        "Candidate Impact By Product",
        "Cinnamon Breakfast Cereal",
    ]
    summary = section(doc, "Executive Summary").paragraphs
    assert "models three products" in summary[0]
    assert (
        "seven obligations across six jurisdictions, four of them with confirmed coverage"
        in summary[0]
    )
    # Only the severities that occur are named.
    assert "Seven candidate impacts were flagged: three act now and four watch." in summary[1]
    assert "Three of three products carry at least one." in summary[1]
    assert "Four obligations reach an effective date within a year" in summary[2]
    assert "Themes" in headings(doc)
    assert section(doc, "Sweeteners and added sugar").bullets[-1].startswith("Action:")
    actions = section(doc, "Suggested Review Items").bullets
    assert actions[0].startswith(
        "Review now: Cinnamon Breakfast Cereal against West Region School Food Rule"
    )
    assert "Inventory allergen content by product and schedule label updates." in actions
    assert doc.title == "Example Pantry Co. regulatory weekly synthesis"


def test_weekly_synthesis_without_impacts_or_themes(register: Register) -> None:
    empty = dataclasses.replace(register, obligations=())
    doc = weekly_synthesis(empty, [], [], TODAY)
    assert "Themes" not in headings(doc)
    assert section(doc, "Coming Due Within 365 Days").paragraphs == [
        "No obligations reach an effective date within a year."
    ]
    assert section(doc, "Suggested Review Items").paragraphs == [
        "No review items are outstanding this week."
    ]


def test_unknown_tier_is_rejected(register: Register) -> None:
    with pytest.raises(ValueError, match="unknown tier 'v9'"):
        build_briefing(register, [], TODAY, tier="v9")


def test_tiers_grow_in_detail(register: Register) -> None:
    impacts = assess_impacts(register, TODAY)
    docs = {tier: build_briefing(register, impacts, TODAY, tier=tier) for tier in TIERS}
    sizes = [len(docs[t].to_dict()["sections"]) for t in TIERS]
    assert sizes[0] < sizes[1] < sizes[2] or sizes[0] < sizes[2]
    assert "Key Items" in headings(docs["v1"])
    assert "Key Items" not in headings(docs["v2"])
    assert "Enforcement Themes" not in headings(docs["v1"])
    assert "Enforcement Themes" in headings(docs["v2"])
    assert "Consolidated Review Items" not in headings(docs["v2"])
    assert "Consolidated Review Items" in headings(docs["v3"])
    assert docs["v1"].subtitle == "v1 (headlines)"
    for doc in docs.values():
        assert doc.disclaimer.startswith(DISCLAIMER)
        assert doc.title == "Example Pantry Co. regulatory briefing"


def test_v1_headlines_only(register: Register) -> None:
    doc = build_briefing(register, [], TODAY, tier="v1")
    key_items = section(doc, "Key Items").bullets
    assert len(key_items) == len(register.obligations)
    assert key_items[0].startswith("Allergen Declaration Order: enacted, 2027-03-01 (nl). Summary:")
    assert any(
        b.startswith("East Region Sweetener Labeling Bill: proposed, no date") for b in key_items
    )
    recent = section(doc, "What Happened Recently")
    assert (
        recent.bullets[0]
        == "2026-10-01: Nutrition Claims Regulation opened for comment (https://registry.sv.example/rules/claims)"
    )


def test_v3_item_layout(register: Register) -> None:
    impacts = assess_impacts(register, TODAY)
    doc = build_briefing(register, impacts, TODAY, tier="v3")
    item = section(doc, "Allergen Declaration Order")
    assert item.level == 3
    text = "\n".join(item.paragraphs)
    assert "Status: enacted, effective 2027-03-01 (nl)." in item.paragraphs[0]
    assert "Affected products: Oat Granola Bar." in text
    assert "What to do. Inventory allergen content" in text
    assert (
        "Governing rule. Northland Allergen Declaration Order (https://regulator.nl.example/orders/allergen)"
        in text
    )
    assert "Source. Northland regulator (https://regulator.nl.example/orders/allergen)" in text
    assert "Obligations: Northland" in headings(doc)
    v2_text = "\n".join(
        section(
            build_briefing(register, impacts, TODAY, tier="v2"), "Allergen Declaration Order"
        ).paragraphs
    )
    assert "What to do" not in v2_text


def test_obligation_without_detail_shows_a_placeholder(register: Register) -> None:
    doc = build_briefing(register, [], TODAY, tier="v2")
    item = section(doc, "East Region Sweetener Labeling Bill")
    assert "Note. Not yet scheduled for a vote" in "\n".join(item.paragraphs)
    bare = dataclasses.replace(
        register,
        obligations=tuple(
            dataclasses.replace(o, notes="", source_url="") for o in register.obligations
        ),
    )
    item = section(
        build_briefing(bare, [], TODAY, tier="v2"), "East Region Sweetener Labeling Bill"
    )
    assert "Detail pending; confirm against the primary source." in "\n".join(item.paragraphs)
    assert not any(p.startswith("Source.") for p in item.paragraphs)


def test_recent_window_anchors_to_the_latest_event_when_nothing_is_recent(
    register: Register,
) -> None:
    doc = build_briefing(register, [], dt.date(2027, 6, 1), tier="v2", since_days=60)
    recent = section(doc, "What Happened (Last 60 Days)")
    assert "anchored to the latest recorded development" in recent.paragraphs[0]
    assert "Covering 2026-08-02 to 2026-10-01" in recent.paragraphs[0]


def test_recent_window_with_recent_events(register: Register) -> None:
    doc = build_briefing(register, [], dt.date(2026, 10, 10), tier="v2", since_days=30)
    recent = section(doc, "What Happened (Last 30 Days)")
    assert recent.paragraphs == ["Covering 2026-09-10 to 2026-10-10."]
    event_headings = [h for h in headings(doc) if h.startswith("2026-")]
    assert event_headings == ["2026-10-01: Nutrition Claims Regulation opened for comment"]


def test_empty_window(register: Register) -> None:
    empty = dataclasses.replace(register, changelog=())
    doc = build_briefing(empty, [], TODAY, tier="v1", since_days=30)
    assert (
        section(doc, "What Happened (Last 30 Days)").paragraphs[-1]
        == "No recorded developments in this window."
    )


def test_recent_count_limits_events_without_a_window(register: Register) -> None:
    doc = build_briefing(register, [], TODAY, tier="v2", recent_count=1)
    assert [h for h in headings(doc) if h[:4] == "2026" and ":" in h] == [
        "2026-10-01: Nutrition Claims Regulation opened for comment"
    ]


def test_candidates_appear_only_in_v3_and_stay_unconfirmed(register: Register) -> None:
    candidates = [
        {
            "date": "2026-10-12",
            "headline": "Proposed Rule: Allergen update",
            "what_happened": "Proposes a change.",
            "citations": [{"citation": "21 CFR 101", "url": "x"}, "bad"],
            "source_url": "https://www.example.gov/d/1",
            "document_number": "1",
        }
    ]
    v3 = build_briefing(register, [], TODAY, tier="v3", candidates=candidates)
    assert "Newly Detected, Unconfirmed" in headings(v3)
    item = section(v3, "2026-10-12: Proposed Rule: Allergen update")
    assert "What happened (unconfirmed). Proposes a change." in item.paragraphs
    assert "Citations from the feed. 21 CFR 101" in item.paragraphs
    assert "Source. 1 (https://www.example.gov/d/1)" in item.paragraphs
    v2 = build_briefing(register, [], TODAY, tier="v2", candidates=candidates)
    assert "Newly Detected, Unconfirmed" not in headings(v2)


def test_enforcement_theme_detail_by_tier(register: Register) -> None:
    v2 = section(build_briefing(register, [], TODAY, tier="v2"), "Undeclared allergens")
    v3 = section(build_briefing(register, [], TODAY, tier="v3"), "Undeclared allergens")
    assert len(v2.paragraphs) == 1
    assert any(p.startswith("Governing rule.") for p in v3.paragraphs)
    assert any(p.startswith("Note.") for p in v3.paragraphs)
    intro = section(
        build_briefing(register, [], TODAY, tier="v2"), "Enforcement Themes"
    ).paragraphs[0]
    assert "https://regulator.nl.example/enforcement" in intro


def test_briefing_without_sidecars(register: Register) -> None:
    bare = dataclasses.replace(register, detail={}, changelog=(), enforcement=None, themes=())
    doc = build_briefing(bare, [], TODAY, tier="v3")
    assert "Enforcement Themes" not in headings(doc)
    assert section(doc, "Consolidated Review Items").paragraphs == ["No review items recorded."]
    assert section(doc, "What Happened Recently").paragraphs == [
        "No recorded developments in this window."
    ]
