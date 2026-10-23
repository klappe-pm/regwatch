"""The JSON interface reads the project as the command line does and writes only settings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import TODAY

from regwatch import webapi
from regwatch.config import load_config
from regwatch.webapi import Api, ApiError, Download


@pytest.fixture
def api(project: Path) -> Api:
    return Api(project, today=lambda: TODAY)


def get(api: Api, path: str, **query: str) -> Any:
    status, payload = api.handle("GET", path, query, {})
    assert status == 200
    return payload


def post(api: Api, path: str, body: dict[str, Any]) -> Any:
    status, payload = api.handle("POST", path, {}, body)
    assert status == 200
    return payload


def test_unknown_routes_and_methods_are_refused(api: Api) -> None:
    with pytest.raises(ApiError) as missing:
        api.handle("GET", "/api/nothing", {}, {})
    assert missing.value.status == 404
    with pytest.raises(ApiError) as wrong:
        api.handle("POST", "/api/overview", {}, {})
    assert wrong.value.status == 405


def test_status_names_the_project_and_premium(api: Api) -> None:
    status = get(api, "/api/status")
    assert status["project"] == "project"
    assert status["premium"] is False
    assert status["version"]


def test_the_overview_counts_sources_from_snapshots(api: Api) -> None:
    overview = get(api, "/api/overview")
    assert overview["counts"] == {"new": 4, "changed": 0, "suspicious": 0, "failing": 0}
    assert overview["sources"] == 5
    assert overview["generated"] == TODAY.isoformat()
    assert overview["priority"] and overview["priority"][0]["severity"] == "act-now"
    assert overview["schedule"] == {"available": False, "command": "regwatch schedule"}
    assert overview["supply_chain"] == {"available": False, "command": "regwatch sources add"}
    assert all(item["effective_date"] >= TODAY.isoformat() for item in overview["upcoming"])


def test_the_overview_uses_the_schedule_and_signals_when_they_land(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(webapi, "schedule_status", lambda config: {"every": "daily"})
    monkeypatch.setattr(webapi, "supply_chain_signals", lambda config: [{"title": "x"}])
    overview = get(api, "/api/overview")
    assert overview["schedule"] == {"available": True, "every": "daily"}
    assert overview["supply_chain"] == {"available": True, "signals": [{"title": "x"}]}


def test_changes_hold_results_impacts_and_cleaned_candidates(api: Api, project: Path) -> None:
    state = project.parent / "state"
    state.mkdir()
    (state / "ingest-candidates.json").write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "date": "2026-10-01",
                        "headline": "Rule\x1b[2J: allergen‮ update",
                        "source_url": "javascript:alert(1)",
                        "agency": 5,
                    },
                    "not a candidate",
                ]
            }
        ),
        encoding="utf-8",
    )
    changes = get(api, "/api/changes")
    assert len(changes["sources"]) == 5
    assert changes["impacts"]
    assert changes["severities"] == ["act-now", "high", "watch", "info"]
    [candidate] = changes["candidates"]
    assert "\x1b" not in candidate["headline"] and "‮" not in candidate["headline"]
    assert candidate["source_url"] == ""
    assert candidate["agency"] == ""
    assert candidate["confidence"] == "unconfirmed"


@pytest.mark.parametrize("content", ["{not json", "[1, 2]", "x" * 10])
def test_an_unreadable_candidates_file_means_no_candidates(
    api: Api, project: Path, content: str
) -> None:
    state = project.parent / "state"
    state.mkdir()
    (state / "ingest-candidates.json").write_text(content, encoding="utf-8")
    assert get(api, "/api/changes")["candidates"] == []


def test_an_oversized_candidates_file_is_ignored(
    api: Api, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = project.parent / "state"
    state.mkdir()
    (state / "ingest-candidates.json").write_text('{"candidates": [{}]}', encoding="utf-8")
    monkeypatch.setattr(webapi, "MAX_STATE_BYTES", 5)
    assert get(api, "/api/changes")["candidates"] == []


def test_sources_list_the_users_sources_with_status(api: Api) -> None:
    sources = get(api, "/api/sources")["sources"]
    assert [s["source_id"] for s in sources][:2] == ["nl-notices", "nl-east-gazette"]
    manual = next(s for s in sources if s["mechanism"] == "manual")
    assert manual["status"] == "MANUAL"
    assert all(s["url"] == "" or s["url"].startswith("https://") for s in sources)


def test_the_catalogue_is_unavailable_until_it_lands(api: Api) -> None:
    assert get(api, "/api/catalogue", q="food") == {
        "available": False,
        "command": "regwatch sources search",
        "entries": [],
        "facets": {},
    }
    assert post(api, "/api/catalogue/add", {"source_id": "x"}) == {
        "available": False,
        "command": "regwatch sources add",
    }


ENTRIES = [
    {
        "source_id": "a",
        "name": "Alpha",
        "category": "regulation",
        "region": "europe",
        "kind": "regulator",
        "access": "free",
        "jurisdiction": "eu",
    },
    {
        "source_id": "b",
        "name": "Beta",
        "category": "packaging-materials",
        "region": "europe",
        "kind": "news",
        "access": "paid",
        "jurisdiction": "gb",
    },
    {
        "source_id": "c",
        "name": "Gamma",
        "category": "regulation",
        "region": "asia",
        "kind": "gazette",
        "access": "free-key",
        "jurisdiction": "jp",
    },
]


def test_the_catalogue_filters_by_category_region_kind_and_access(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []

    def entries(query: str) -> list[dict[str, Any]]:
        seen.append(query)
        return [dict(e) for e in ENTRIES]

    monkeypatch.setattr(webapi, "catalogue_entries", entries)
    everything = get(api, "/api/catalogue", q="  al\x1b  ")
    assert seen == ["al"]
    assert everything["facets"]["category"] == ["packaging-materials", "regulation"]
    assert everything["facets"]["access"] == ["free", "free-key", "paid"]
    assert [
        e["source_id"] for e in get(api, "/api/catalogue", category="regulation")["entries"]
    ] == [
        "a",
        "c",
    ]
    narrowed = get(api, "/api/catalogue", category="regulation", region="asia", kind="gazette")
    assert [e["source_id"] for e in narrowed["entries"]] == ["c"]
    assert get(api, "/api/catalogue", access="paid")["entries"][0]["source_id"] == "b"


def test_adding_a_catalogue_source_goes_through_the_adapter(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(webapi, "add_catalogue_source", lambda config, sid: {"source_id": sid})
    assert post(api, "/api/catalogue/add", {"source_id": "a"}) == {
        "available": True,
        "source_id": "a",
    }
    with pytest.raises(ApiError) as bad:
        api.handle("POST", "/api/catalogue/add", {}, {"source_id": ""})
    assert bad.value.status == 400
    with pytest.raises(ApiError):
        api.handle("POST", "/api/catalogue/add", {}, {"source_id": "x" * 101})


def test_obligations_carry_their_impacts(api: Api) -> None:
    obligations = get(api, "/api/obligations")["obligations"]
    assert obligations
    with_impacts = [o for o in obligations if o["impacts"]]
    assert with_impacts
    assert all(i["obligation_id"] == o["obligation_id"] for o in with_impacts for i in o["impacts"])
    assert all(o["jurisdiction_name"] for o in obligations)


@pytest.mark.parametrize("kind", ["tiered", "daily", "weekly"])
def test_each_briefing_kind_renders_with_the_disclaimer(api: Api, kind: str) -> None:
    briefing = get(api, "/api/briefing", kind=kind, tier="v1")
    assert briefing["kinds"] == ["tiered", "daily", "weekly"]
    assert "not legal advice" in briefing["document"]["disclaimer"].lower()
    assert briefing["document"]["sections"]


def test_a_briefing_includes_unconfirmed_candidates_at_full_detail(api: Api, project: Path) -> None:
    state = project.parent / "state"
    state.mkdir()
    (state / "ingest-candidates.json").write_text(
        json.dumps({"candidates": [{"date": "2026-10-01", "headline": "Notice: colour"}]}),
        encoding="utf-8",
    )
    text = json.dumps(get(api, "/api/briefing", kind="tiered", tier="v3"))
    assert "Notice: colour" in text


@pytest.mark.parametrize("query", [{"kind": "monthly"}, {"tier": "v9"}])
def test_an_unknown_briefing_is_refused(api: Api, query: dict[str, str]) -> None:
    with pytest.raises(ApiError) as refused:
        api.handle("GET", "/api/briefing", query, {})
    assert refused.value.status == 400


@pytest.mark.parametrize(
    ("fmt", "content_type", "start"),
    [
        ("md", "text/markdown; charset=utf-8", b"#"),
        ("html", "text/html; charset=utf-8", b"<!doctype html>"),
        ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", b"PK"),
    ],
)
def test_a_briefing_exports_in_each_format(
    api: Api, fmt: str, content_type: str, start: bytes
) -> None:
    download = get(api, "/api/briefing/export", kind="weekly", format=fmt)
    assert isinstance(download, Download)
    assert download.content_type == content_type
    assert download.filename == f"regwatch-weekly-{TODAY.isoformat()}.{fmt}"
    assert download.data.lstrip().startswith(start)


def test_an_unknown_export_format_is_refused(api: Api) -> None:
    with pytest.raises(ApiError):
        api.handle("GET", "/api/briefing/export", {"format": "pdf"}, {})


def test_automations_are_unavailable_until_they_land(api: Api) -> None:
    assert get(api, "/api/automations") == {
        "premium": False,
        "schedule": {"available": False, "command": "regwatch schedule"},
        "runs": {"available": False, "command": "regwatch run", "records": []},
    }
    assert post(api, "/api/automations/run", {}) == {"available": False, "command": "regwatch run"}


def test_automations_use_the_adapters_when_they_land(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(webapi, "schedule_status", lambda config: {"every": "daily"})
    monkeypatch.setattr(webapi, "run_records", lambda config: [{"exit_code": 0}])
    monkeypatch.setattr(webapi, "run_now", lambda config: {"exit_code": 3})
    automations = get(api, "/api/automations")
    assert automations["schedule"] == {"available": True, "every": "daily"}
    assert automations["runs"] == {"available": True, "records": [{"exit_code": 0}]}
    assert post(api, "/api/automations/run", {}) == {"available": True, "record": {"exit_code": 3}}


def test_settings_list_the_focus_catalogue_and_premium(api: Api) -> None:
    settings = get(api, "/api/settings")
    assert settings["focus_areas"] == []
    assert {"id", "label", "description"} == set(settings["focus_catalogue"][0])
    assert settings["premium"] is False
    assert settings["design"]["available"] is False
    assert settings["llm"]["available"] is False


def test_focus_areas_are_saved_and_read_back(api: Api, project: Path) -> None:
    known = [a["id"] for a in get(api, "/api/settings")["focus_catalogue"]]
    saved = post(api, "/api/settings/focus", {"focus_areas": [known[1], known[0], known[1]]})
    assert saved == {"focus_areas": [known[1], known[0]]}
    assert load_config(project).profile.focus_areas == (known[1], known[0])
    assert "# Example configuration." in project.read_text(encoding="utf-8")


@pytest.mark.parametrize("areas", [["no-such-area"], "pet-food", [1], ["Bad Id"]])
def test_unknown_focus_areas_are_refused(api: Api, project: Path, areas: object) -> None:
    before = project.read_text(encoding="utf-8")
    with pytest.raises((ApiError, ValueError)):
        api.handle("POST", "/api/settings/focus", {}, {"focus_areas": areas})
    assert project.read_text(encoding="utf-8") == before


def test_premium_is_saved_through_the_interface(api: Api, project: Path) -> None:
    assert post(api, "/api/settings/premium", {"enabled": True}) == {"premium": True}
    assert get(api, "/api/status")["premium"] is True
    assert post(api, "/api/settings/premium", {"enabled": False}) == {"premium": False}
    with pytest.raises(ApiError):
        api.handle("POST", "/api/settings/premium", {}, {"enabled": 1})


def test_search_finds_sources_changes_and_obligations(api: Api) -> None:
    results = get(api, "/api/search", q="Allergen")
    assert results["query"] == "allergen"
    assert results["obligations"]
    assert any(c["kind"] == "impact" for c in results["changes"])
    sources = get(api, "/api/search", q="southvale")["sources"]
    assert sources and all(s["mine"] for s in sources)
    assert get(api, "/api/search", q="  ") == {
        "query": "",
        "sources": [],
        "changes": [],
        "obligations": [],
    }


def test_search_reaches_the_catalogue_and_unconfirmed_candidates(
    api: Api, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        webapi,
        "catalogue_entries",
        lambda query: [
            {"source_id": "nl-notices", "name": "Already watched"},
            {"source_id": "zz", "name": "Zed Gazette", "jurisdiction": "zz"},
        ],
    )
    state = project.parent / "state"
    state.mkdir()
    (state / "ingest-candidates.json").write_text(
        json.dumps({"candidates": [{"headline": "Zed notice", "what_happened": "x"}]}),
        encoding="utf-8",
    )
    results = get(api, "/api/search", q="zed")
    assert results["sources"] == [
        {"source_id": "zz", "name": "Zed Gazette", "jurisdiction": "zz", "mine": False}
    ]
    assert results["changes"][0]["kind"] == "candidate"


def test_results_are_capped(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        webapi,
        "catalogue_entries",
        lambda query: [{"source_id": f"s{i}", "name": f"Source {i}"} for i in range(30)],
    )
    assert len(get(api, "/api/search", q="source")["sources"]) == webapi.MAX_RESULTS
