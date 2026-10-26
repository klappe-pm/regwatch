"""The JSON interface reads the project as the command line does."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import NOW, TODAY, FakeSystem

from regwatch import workspace
from regwatch.config import load_config
from regwatch.webapi import Api, ApiError, Download


@pytest.fixture
def api(project: Path) -> Api:
    """The interface with every program faked: no keychain tool or crontab really runs."""
    return Api(project, today=lambda: TODAY, system=FakeSystem("linux").system(), clock=lambda: NOW)


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
    assert overview["schedule"]["installed"] is False
    assert overview["supply_chain"]["sources"] == []
    assert all(item["effective_date"] >= TODAY.isoformat() for item in overview["upcoming"])


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
    monkeypatch.setattr(workspace, "MAX_STATE_BYTES", 5)
    assert get(api, "/api/changes")["candidates"] == []


def test_sources_list_the_users_sources_with_status(api: Api) -> None:
    sources = get(api, "/api/sources")["sources"]
    assert [s["source_id"] for s in sources][:2] == ["nl-notices", "nl-east-gazette"]
    manual = next(s for s in sources if s["mechanism"] == "manual")
    assert manual["status"] == "MANUAL"
    assert all(s["url"] == "" or s["url"].startswith("https://") for s in sources)


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


def test_settings_list_the_focus_catalogue_and_premium(api: Api) -> None:
    settings = get(api, "/api/settings")
    assert settings["focus_areas"] == []
    assert {"id", "label", "description"} == set(settings["focus_catalogue"][0])
    assert settings["premium"] is False
    # The design and provider settings are listed whether premium is on or off;
    # saving them, like every premium route, is refused while it is off.
    assert settings["design"]["available"] is True
    assert settings["llm"]["enabled"] is False
    assert all(not key["present"] or key["where"] for key in settings["llm"]["keys"])


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
