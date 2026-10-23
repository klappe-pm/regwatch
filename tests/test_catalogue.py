"""The source catalogue: its validation, the one search ranking, filters and merging."""

from __future__ import annotations

import copy
import json
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

from regwatch.catalogue import (
    ACCESS_LABELS,
    CATEGORIES,
    FIELDS,
    KINDS,
    CatalogueEntry,
    CatalogueError,
    entry_from_dict,
    entry_to_source,
    filter_entries,
    jurisdiction_name,
    load_source_catalogue,
    merge_sources,
    parse_source_catalogue,
    rank,
)
from regwatch.fetch import check_url
from regwatch.focus import load_catalogue

FOCUS = tuple(area.focus_id for area in load_catalogue(None))


def shipped() -> dict[str, Any]:
    text = resources.files("regwatch").joinpath("data/source-catalogue.json").read_text("utf-8")
    data: dict[str, Any] = json.loads(text)
    return data


def raw(**changes: Any) -> dict[str, Any]:
    """A valid entry with ``changes`` applied."""
    entry: dict[str, Any] = {
        "source_id": "zz-test-feed",
        "name": "Test Feed",
        "publisher": "Test Publisher",
        "jurisdiction": "zz",
        "region": "europe",
        "kind": "regulator",
        "category": "regulation",
        "mechanism": "rss",
        "url": "https://feeds.example.org/a.xml",
        "homepage": "https://example.org/",
        "access": "free",
        "auth": None,
        "key_env": None,
        "signup_url": None,
        "focus_areas": [],
        "language": "en",
        "cadence": "daily",
        "description": "A feed used by the tests.",
        "verified": True,
        "checked": "2026-10-23",
        "notes": None,
    }
    entry.update(changes)
    return entry


def keyed(**changes: Any) -> dict[str, Any]:
    base = raw(
        source_id="zz-keyed-api",
        access="free-key",
        mechanism="api",
        auth={"type": "query", "name": "api_key"},
        key_env="REGWATCH_KEY_ZZ",
        signup_url="https://example.org/signup",
    )
    base.update(changes)
    return base


def build(**changes: Any) -> CatalogueEntry:
    return entry_from_dict(raw(**changes), FOCUS)


# --- the shipped file -------------------------------------------------------------


def test_the_shipped_catalogue_loads_and_every_url_passes_the_fetch_checks() -> None:
    entries = load_source_catalogue(FOCUS)
    assert len(entries) == len(shipped()["sources"]) >= 500
    for entry in entries:
        assert check_url(entry.url) == "https"
        assert check_url(entry.homepage) == "https"
        assert entry.category in CATEGORIES
        assert entry.kind in KINDS
    assert {entry.access for entry in entries} == {"free", "free-key", "paid"}
    assert len({entry.source_id for entry in entries}) == len(entries)


def test_every_shipped_entry_has_exactly_the_documented_fields() -> None:
    for entry in shipped()["sources"]:
        assert tuple(entry) == FIELDS


def test_the_shipped_descriptions_use_no_dash_as_punctuation() -> None:
    for entry in shipped()["sources"]:
        for key in ("name", "description", "notes"):
            value = entry[key] or ""
            assert " - " not in value and "--" not in value, entry["source_id"]


def test_jurisdiction_names() -> None:
    assert jurisdiction_name("us") == "United States"
    assert jurisdiction_name("us-ca") == "California"
    assert jurisdiction_name("zz") == "ZZ"


# --- validation ---------------------------------------------------------------------


def test_a_valid_entry_builds() -> None:
    entry = build(focus_areas=["pet-food"], notes="A note.")
    assert entry.access_label == "Free"
    assert not entry.keyed
    assert entry.to_dict()["focus_areas"] == ["pet-food"]
    assert entry.to_dict()["access_label"] == "Free"
    assert entry.to_dict()["category"] == "regulation"


def test_a_keyed_entry_builds() -> None:
    entry = entry_from_dict(keyed(), FOCUS)
    assert entry.keyed
    assert entry.access_label == "Free Key"
    assert entry.to_dict()["auth"] == {"type": "query", "name": "api_key"}


def test_access_labels() -> None:
    assert ACCESS_LABELS == {"free": "Free", "free-key": "Free Key", "paid": "Paid"}


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"source_id": "Bad_Id"}, "source_id"),
        ({"source_id": "x" * 81}, "longer than 80"),
        ({"name": ""}, "'name'"),
        ({"name": "x" * 201}, "longer than"),
        ({"name": "Bad‮name"}, "invisible"),
        ({"description": "x" * 161}, "longer than 160"),
        ({"jurisdiction": "USA"}, "jurisdiction"),
        ({"region": "mars"}, "region"),
        ({"kind": "blog"}, "kind"),
        ({"category": "gossip"}, "category"),
        ({"category": None}, "category"),
        ({"mechanism": "ftp"}, "mechanism"),
        ({"url": "http://example.org/"}, "url"),
        ({"url": "file:///etc/passwd"}, "must be an https URL"),
        ({"url": "https://user@example.org/"}, "credentials"),
        ({"url": "https://example.org/a b"}, "space"),
        ({"url": 5}, "url"),
        ({"homepage": "javascript:alert(1)"}, "homepage"),
        ({"access": "cheap"}, "access"),
        ({"focus_areas": ["moon-cheese"]}, "unknown focus"),
        ({"focus_areas": "pet-food"}, "focus_areas"),
        ({"focus_areas": ["pet-food", "pet-food"]}, "repeats"),
        ({"language": "eng"}, "language"),
        ({"cadence": "monthly"}, "cadence"),
        ({"verified": "yes"}, "verified"),
        ({"checked": "23/10/2026"}, "checked"),
        ({"checked": 20261023}, "checked"),
        ({"notes": ""}, "notes"),
        ({"auth": {"type": "query", "name": "k"}, "key_env": "K"}, "free source"),
        ({"key_env": "K"}, "both be set"),
    ],
)
def test_invalid_fields_are_refused(changes: dict[str, Any], message: str) -> None:
    with pytest.raises(CatalogueError, match=message):
        build(**changes)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"auth": None, "key_env": None}, "free-key source must have"),
        ({"signup_url": None}, "free-key source must have"),
        ({"auth": {"type": "cookie", "name": "k"}}, "auth.type"),
        ({"auth": {"type": "query", "name": "a b"}}, "auth.name"),
        ({"auth": {"type": "query"}}, "exactly 'type' and 'name'"),
        ({"auth": "query:api_key"}, "exactly 'type' and 'name'"),
        ({"key_env": "lower"}, "key_env"),
        ({"signup_url": "http://example.org/"}, "signup_url"),
    ],
)
def test_keyed_entries_must_say_where_the_key_goes(changes: dict[str, Any], message: str) -> None:
    with pytest.raises(CatalogueError, match=message):
        entry_from_dict(keyed(**changes), FOCUS)


def test_unknown_and_missing_keys_are_refused() -> None:
    with pytest.raises(CatalogueError, match="unknown keys: colour"):
        entry_from_dict(raw(colour="blue"), FOCUS)
    entry = raw()
    del entry["category"]
    with pytest.raises(CatalogueError, match="missing keys: category"):
        entry_from_dict(entry, FOCUS)
    with pytest.raises(CatalogueError, match="must be an object"):
        entry_from_dict([], FOCUS)


def test_the_file_shape_is_checked() -> None:
    with pytest.raises(CatalogueError, match="exactly 'version' and 'sources'"):
        parse_source_catalogue({"sources": []}, FOCUS)
    with pytest.raises(CatalogueError, match="unsupported version"):
        parse_source_catalogue({"version": 2, "sources": []}, FOCUS)
    with pytest.raises(CatalogueError, match="unsupported version"):
        parse_source_catalogue({"version": True, "sources": []}, FOCUS)
    with pytest.raises(CatalogueError, match="must be a list"):
        parse_source_catalogue({"version": 1, "sources": {}}, FOCUS)


def test_ids_must_be_unique_and_every_bad_entry_is_named() -> None:
    data = {"version": 1, "sources": [raw(), raw(), raw(source_id="zz-other", kind="x")]}
    with pytest.raises(CatalogueError) as caught:
        parse_source_catalogue(data, FOCUS)
    assert "duplicate source_id 'zz-test-feed'" in str(caught.value)
    assert "entry 3" in str(caught.value)


def test_an_extra_file_follows_the_same_rules(tmp_path: Path) -> None:
    extra = tmp_path / "extra.json"
    extra.write_text(json.dumps({"version": 1, "sources": [raw()]}), encoding="utf-8")
    entries = load_source_catalogue(FOCUS, extra)
    assert entries[-1].source_id == "zz-test-feed"

    extra.write_text(json.dumps({"version": 1, "sources": [raw(url="http://x.org/")]}), "utf-8")
    with pytest.raises(CatalogueError, match="url"):
        load_source_catalogue(FOCUS, extra)

    clash = raw(source_id="us-fda-recalls-rss")
    extra.write_text(json.dumps({"version": 1, "sources": [clash]}), encoding="utf-8")
    with pytest.raises(CatalogueError, match="repeats ids of the shipped catalogue"):
        load_source_catalogue(FOCUS, extra)


def test_an_unreadable_extra_file_is_a_catalogue_error(tmp_path: Path) -> None:
    with pytest.raises(CatalogueError, match="cannot read"):
        load_source_catalogue(FOCUS, tmp_path / "missing.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    with pytest.raises(CatalogueError, match="not valid JSON"):
        load_source_catalogue(FOCUS, bad)
    big = tmp_path / "big.json"
    big.write_bytes(b" " * 5_000_001)
    with pytest.raises(CatalogueError, match="larger than"):
        load_source_catalogue(FOCUS, big)


# --- ranking -------------------------------------------------------------------------


def entries_for_search() -> list[CatalogueEntry]:
    return [
        build(source_id="aa-one", name="Bulletin of Things", jurisdiction="aa", description="x."),
        build(source_id="bb-alerts", name="Food Alerts", jurisdiction="bb", description="Alerts."),
        build(source_id="cc-foodstuff", name="Foodstuffs Notices", jurisdiction="cc"),
        build(source_id="dd-seafood", name="Seafood Board", jurisdiction="dd"),
        build(source_id="ee-misc", name="Misc", jurisdiction="ee", publisher="Food Office"),
        build(source_id="bb", name="Bee Bee", jurisdiction="zz", kind="news"),
    ]


def ids(entries: list[CatalogueEntry]) -> list[str]:
    return [entry.source_id for entry in entries]


def test_whole_words_beat_prefixes_which_beat_substrings() -> None:
    found = ids(rank(entries_for_search(), "food"))
    assert found == ["bb-alerts", "ee-misc", "cc-foodstuff", "dd-seafood"]


def test_ranking_is_case_insensitive_and_needs_every_word() -> None:
    entries = entries_for_search()
    assert ids(rank(entries, "FOOD ALERTS")) == ["bb-alerts"]
    assert ids(rank(entries, "food nothing")) == []


def test_an_exact_id_or_jurisdiction_comes_first() -> None:
    entries = entries_for_search()
    assert ids(rank(entries, "bb"))[:2] == ["bb-alerts", "bb"]
    assert ids(rank(entries, "cc-foodstuff"))[0] == "cc-foodstuff"
    assert ids(rank(entries, "zz")) == ["bb"]


def test_ties_keep_catalogue_order_and_an_empty_query_returns_all() -> None:
    entries = entries_for_search()
    assert ids(rank(entries, "europe")) == ids(entries)
    assert ids(rank(entries, "  ")) == ids(entries)
    assert ids(rank(entries, "---")) == []


def test_search_covers_kind_category_region_and_publisher() -> None:
    entries = [
        build(source_id="aa-x", kind="market-data", category="commodities-and-forecasts"),
        build(source_id="bb-x", region="asia-pacific", publisher="Canadian Office"),
        build(source_id="cc-x", category="industry-news"),
    ]
    assert ids(rank(entries, "market data")) == ["aa-x"]
    assert ids(rank(entries, "forecasts")) == ["aa-x"]
    assert ids(rank(entries, "industry-news")) == ["cc-x"]
    assert ids(rank(entries, "asia-pacific")) == ["bb-x"]
    assert ids(rank(entries, "canadian")) == ["bb-x"]


def test_fields_are_weighted_name_first_and_description_last() -> None:
    entries = [
        build(source_id="aa-desc", name="Notices", description="About widgets."),
        build(source_id="bb-cat", name="Notices", category="packaging-materials"),
        build(source_id="cc-kind", name="Notices", kind="lobbying-disclosure"),
        build(source_id="dd-pub", name="Notices", publisher="Widget Office"),
        build(source_id="ee-name", name="Widget Notices"),
    ]
    assert ids(rank(entries, "widget")) == ["ee-name", "dd-pub", "aa-desc"]
    assert ids(rank(entries, "packaging lobbying")) == []
    assert ids(rank(entries, "lobbying")) == ["cc-kind"]
    assert ids(rank(entries, "materials")) == ["bb-cat"]


def test_the_access_label_and_focus_areas_are_searched() -> None:
    entries = [
        build(source_id="aa-x"),
        entry_from_dict(keyed(source_id="bb-x"), FOCUS),
        build(source_id="cc-x", focus_areas=["pet-food"]),
    ]
    assert ids(rank(entries, "free key")) == ["bb-x"]
    assert ids(rank(entries, "pet")) == ["cc-x"]


@pytest.mark.parametrize(
    ("british", "american"),
    [
        ("aluminium", "aluminum"),
        ("labelling", "labeling"),
        ("flavour", "flavor"),
        ("colouring", "coloring"),
        ("organisation", "organization"),
        ("sulphites", "sulfites"),
    ],
)
def test_british_and_american_spellings_find_each_other(british: str, american: str) -> None:
    entries = [
        build(source_id="aa-british", name=f"{british.title()} Notices"),
        build(source_id="bb-american", name=f"{american.title()} Notices"),
        build(source_id="cc-other", name="Other Notices"),
    ]
    assert ids(rank(entries, british)) == ["aa-british", "bb-american"]
    assert ids(rank(entries, american)) == ["aa-british", "bb-american"]


def test_a_short_word_matches_only_a_whole_word_or_an_id_part() -> None:
    entries = [
        build(source_id="aa-cancer", name="Cancer Registry", description="Canada and more."),
        build(source_id="us-ca-board", jurisdiction="us-ca", name="Board"),
        build(source_id="bb-ca", name="Ca Notices"),
    ]
    assert ids(rank(entries, "ca")) == ["bb-ca", "us-ca-board"]
    assert ids(rank(entries, "can")) == ["aa-cancer"]


def test_a_publisher_is_found_by_its_initials() -> None:
    entries = [
        build(source_id="aa-one", name="FDA Notices", publisher="Food and Drug Agency Elsewhere"),
        build(
            source_id="bb-two", name="FDA Notices", publisher="U.S. Food and Drug Administration"
        ),
    ]
    assert ids(rank(entries, "fda")) == ["bb-two", "aa-one"]


def test_an_exact_jurisdiction_lists_its_official_sources_first() -> None:
    entries = [
        build(source_id="zz-news", name="ZZ News", kind="news"),
        build(source_id="zz-portal", name="ZZ Portal", kind="data-portal"),
        build(source_id="zz-gazette", name="Gazette", kind="gazette"),
    ]
    assert ids(rank(entries, "zz")) == ["zz-gazette", "zz-portal", "zz-news"]


# The shipped catalogue: what a person typing these words should see first.
CATALOGUE = load_source_catalogue(FOCUS)


def top(query: str, count: int) -> list[str]:
    return ids(rank(CATALOGUE, query))[:count]


def test_fda_lists_the_fda_own_sources_first() -> None:
    by_id = {entry.source_id: entry for entry in CATALOGUE}
    own = [i for i in top("fda", 25) if by_id[i].publisher.endswith("Food and Drug Administration")]
    assert top("fda", 10) == own[:10]
    assert all(i.startswith(("us-fda-", "us-openfda-")) for i in top("fda", 10))


def test_aluminium_and_aluminum_find_the_same_sources() -> None:
    assert ids(rank(CATALOGUE, "aluminium")) == ids(rank(CATALOGUE, "aluminum"))
    assert {
        "eu-european-aluminium-feed",
        "us-aluminum-association-feed",
        "gb-lme-aluminium",
        "us-cme-aluminum",
    } <= set(top("aluminium", 5))


def test_california_lists_california_sources() -> None:
    assert all(i.startswith("us-ca-") for i in top("california", 10))


def test_pet_food_lists_the_pet_food_sources_first() -> None:
    assert set(top("pet food", 4)) == {
        "us-pet-food-processing",
        "eu-fediaf-pet-food",
        "us-pfi-rss",
        "us-pet-food-industry-rss",
    }


def test_eu_lists_the_eu_institutions_near_the_top() -> None:
    found = top("eu", 10)
    assert all(i.startswith("eu-") for i in found)
    assert "eu-eur-lex-official-journal" in found
    assert "eu-commission-food-safety-news" in found
    assert any(i.startswith("eu-efsa-") for i in found)
    assert not any(i in found for i in ("eu-beveragedaily-rss", "eu-foodnavigator-rss"))


def test_packaging_lists_packaging_sources() -> None:
    by_id = {entry.source_id: entry for entry in CATALOGUE}
    assert all("Packaging" in by_id[i].name for i in top("packaging", 10))


def test_lobbying_lists_the_us_disclosure_records_first() -> None:
    assert top("lobbying", 2) == ["us-house-lobbying-disclosure", "us-senate-lda-api"]
    assert {"eu-transparency-register", "ca-registry-of-lobbyists"} <= set(top("lobbying", 8))


def test_a_jurisdiction_code_lists_only_that_jurisdiction_first() -> None:
    count = sum(1 for entry in CATALOGUE if entry.jurisdiction == "us-ca")
    found = rank(CATALOGUE, "us-ca")
    assert [e.jurisdiction for e in found[:count]] == ["us-ca"] * count
    assert found[0].kind in ("regulator", "legislature", "gazette", "court")


def test_free_key_lists_exactly_the_free_key_sources() -> None:
    found = rank(CATALOGUE, "free key")
    assert {e.source_id for e in found} == {
        e.source_id for e in CATALOGUE if e.access == "free-key"
    }


# --- filters -------------------------------------------------------------------------


def test_filters() -> None:
    entries = [
        build(source_id="us-a", jurisdiction="us"),
        build(source_id="us-ca-b", jurisdiction="us-ca", region="north-america"),
        build(source_id="pet-c", focus_areas=["pet-food"], kind="recalls"),
        build(
            source_id="paid-d", access="paid", signup_url="https://e.org/", category="industry-news"
        ),
    ]
    assert ids(filter_entries(entries, jurisdiction="us")) == ["us-a", "us-ca-b"]
    assert ids(filter_entries(entries, jurisdiction="us-ca")) == ["us-ca-b"]
    assert ids(filter_entries(entries, region="north-america")) == ["us-ca-b"]
    assert ids(filter_entries(entries, kind="recalls")) == ["pet-c"]
    assert ids(filter_entries(entries, access="paid")) == ["paid-d"]
    assert ids(filter_entries(entries, category="industry-news")) == ["paid-d"]
    assert ids(filter_entries(entries, focus="cosmetics")) == ["us-a", "us-ca-b", "paid-d"]
    assert ids(filter_entries(entries, focus="pet-food")) == ids(entries)
    assert ids(filter_entries(entries, chosen=["paid-d"])) == ["paid-d"]
    assert ids(filter_entries(entries, chosen=[])) == []


# --- choosing ------------------------------------------------------------------------


def test_an_entry_maps_to_the_sources_file_fields() -> None:
    entry = entry_from_dict(keyed(mechanism="email-list"), FOCUS)
    source = entry_to_source(entry)
    assert source == {
        "source_id": "zz-keyed-api",
        "jurisdiction": "zz",
        "name": "Test Feed",
        "url": "https://feeds.example.org/a.xml",
        "method": "subscribe",
        "mechanism": "email-list",
        "cadence": "daily",
        "notes": "A feed used by the tests.",
        "auth": "query:api_key",
        "key_env": "REGWATCH_KEY_ZZ",
    }
    assert entry_to_source(build())["method"] == "poll"
    assert "auth" not in entry_to_source(build())


def test_merge_adds_sources_and_their_jurisdictions() -> None:
    entry = build(source_id="us-ca-thing", jurisdiction="us-ca")
    result = merge_sources([], [], [entry, entry])
    assert result.added == ("us-ca-thing",)
    assert result.added_jurisdictions == ("us", "us-ca")
    assert result.jurisdictions == [
        {"jurisdiction_id": "us", "name": "United States", "coverage": "tracked"},
        {"jurisdiction_id": "us-ca", "name": "California", "coverage": "tracked", "parent": "us"},
    ]
    assert result.sources[0]["jurisdiction"] == "us-ca"


def test_merge_reuses_a_jurisdiction_the_user_named_by_name() -> None:
    existing = [{"jurisdiction_id": "united-states", "name": "united states", "coverage": "x"}]
    result = merge_sources([], existing, [build(source_id="us-a", jurisdiction="us")])
    assert result.added_jurisdictions == ()
    assert result.sources[0]["jurisdiction"] == "united-states"


def test_merge_leaves_an_identical_entry_and_refuses_a_different_one() -> None:
    entry = build()
    first = merge_sources([], [], [entry])
    again = merge_sources(first.sources, first.jurisdictions, [entry])
    assert again.added == ()
    assert again.present == ("zz-test-feed",)
    assert again.sources == first.sources

    changed = copy.deepcopy(first.sources)
    changed[0]["name"] = "Edited by hand"
    other = build(source_id="zz-new")
    with pytest.raises(CatalogueError, match="different entry with the id zz-test-feed"):
        merge_sources(changed, first.jurisdictions, [other, entry])
