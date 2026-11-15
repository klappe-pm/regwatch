"""The web interface's catalogue, keys, schedule and runs call the same code as the commands.

Every program is faked with FakeSystem and every fetch with FakeFetcher, so no
keychain tool, crontab or network is touched.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest
from conftest import NOW, TODAY, FakeFetcher, FakeSystem, snapshot_responses

from regwatch.cli import main
from regwatch.config import load_config
from regwatch.fetch import FetchError
from regwatch.schedule import cron_block, plist_bytes, plist_path, program_arguments
from regwatch.state import list_run_records
from regwatch.webapi import SUPPLY_CATEGORIES, Api, ApiError

KEY = "fake" + "-key-" + "4417"
KEYED = "us-eia-api"
KEY_ENV = "REGWATCH_KEY_EIA"
SUPPLY = "gb-tate-and-lyle-news"


def make(project: Path, fake: FakeSystem | None = None, **kwargs: Any) -> Api:
    system = (fake or FakeSystem("linux")).system(kwargs.pop("home", None))
    return Api(project, today=lambda: TODAY, system=system, clock=lambda: NOW, **kwargs)


def get(api: Api, path: str, **query: str) -> Any:
    status, payload = api.handle("GET", path, query, {})
    assert status == 200
    return payload


def post(api: Api, path: str, body: dict[str, Any]) -> Any:
    status, payload = api.handle("POST", path, {}, body)
    assert status == 200
    return payload


def refused(api: Api, path: str, body: dict[str, Any]) -> ApiError:
    with pytest.raises(ApiError) as caught:
        api.handle("POST", path, {}, body)
    return caught.value


# --- the catalogue ---------------------------------------------------------------


def test_the_catalogue_is_the_shipped_one_ranked_like_sources_search(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    api = make(project)
    everything = get(api, "/api/catalogue")
    assert everything["available"] is True
    assert everything["total"] == len(everything["entries"]) > 500
    assert everything["categories"][0] == "regulation"
    assert set(everything["facets"]["access"]) == {"free", "free-key", "paid"}
    ranked = get(api, "/api/catalogue", q="regulations gov")["entries"]
    assert main(["--config", str(project), "sources", "search", "regulations gov", "--json"]) == 0
    cli = [s["source_id"] for s in json.loads(capsys.readouterr().out)["sources"]]
    assert [e["source_id"] for e in ranked] == cli
    assert ranked and all(set(e) >= {"category", "access_label", "chosen"} for e in ranked)


def test_the_catalogue_filters_by_category_then_region_kind_and_access(project: Path) -> None:
    api = make(project)
    supply = get(api, "/api/catalogue", category="packaging-materials")["entries"]
    assert supply and all(e["category"] == "packaging-materials" for e in supply)
    narrowed = get(api, "/api/catalogue", category="regulation", region="europe", access="free")
    assert narrowed["entries"]
    assert all(
        (e["category"], e["region"], e["access"]) == ("regulation", "europe", "free")
        for e in narrowed["entries"]
    )
    kind = get(api, "/api/catalogue", kind="recalls")["entries"]
    assert kind and all(e["kind"] == "recalls" for e in kind)
    assert get(api, "/api/catalogue", q="zzzz-nothing-matches")["entries"] == []


def test_a_catalogue_entry_carries_no_key_and_no_request_address(project: Path) -> None:
    entries = get(make(project), "/api/catalogue", q=KEYED)["entries"]
    entry = next(e for e in entries if e["source_id"] == KEYED)
    assert "url" not in entry and "auth" not in entry and "key_env" not in entry
    assert entry["access_label"] == "Free Key"


def test_adding_a_source_is_sources_add(project: Path) -> None:
    api = make(project)
    added = post(api, "/api/catalogue/add", {"source_id": SUPPLY})
    assert added["added"] == [SUPPLY] and added["present"] == []
    assert added["added_jurisdictions"] == ["gb"]
    config = load_config(project)
    sources = json.loads(config.register.sources.read_text(encoding="utf-8"))["sources"]
    assert sources[-1]["source_id"] == SUPPLY
    chosen = get(api, "/api/catalogue", q=SUPPLY)["entries"]
    assert next(e for e in chosen if e["source_id"] == SUPPLY)["chosen"] is True
    again = post(api, "/api/catalogue/add", {"source_id": SUPPLY})
    assert again["added"] == [] and again["present"] == [SUPPLY]
    assert any(s["source_id"] == SUPPLY for s in get(api, "/api/sources")["sources"])


def test_adding_gives_the_same_files_as_the_command(project: Path, tmp_path: Path) -> None:
    other = tmp_path / "other"
    import shutil

    shutil.copytree(project.parent, other)
    post(make(project), "/api/catalogue/add", {"source_id": KEYED})
    assert main(["--config", str(other / "regwatch.toml"), "sources", "add", KEYED]) == 0
    for name in ("sources.json", "jurisdictions.json"):
        mine = (project.parent / "register" / name).read_text(encoding="utf-8")
        theirs = (other / "register" / name).read_text(encoding="utf-8")
        assert mine == theirs, name


def test_adding_says_when_a_source_needs_a_key(project: Path) -> None:
    fake = FakeSystem("linux")
    assert post(make(project, fake), "/api/catalogue/add", {"source_id": KEYED})["needs_key"]
    fake.keychain[KEY_ENV] = KEY
    again = post(make(project, fake), "/api/catalogue/add", {"source_id": KEYED})
    assert again["needs_key"] is False
    assert KEY not in json.dumps(again)


def test_adding_an_unknown_or_conflicting_source_is_refused(project: Path, edit_json: Any) -> None:
    api = make(project)
    unknown = refused(api, "/api/catalogue/add", {"source_id": "no-such-source"})
    assert unknown.status == 400
    sources = load_config(project).register.sources

    def plant(data: dict[str, Any]) -> None:
        data["sources"].append(
            {
                "source_id": SUPPLY,
                "jurisdiction": "nl",
                "name": "Mine",
                "url": "https://registry.nl.example/feed",
                "method": "poll",
                "mechanism": "rss",
                "cadence": "daily",
                "notes": "",
            }
        )

    edit_json(sources, plant)
    before = sources.read_text(encoding="utf-8")
    conflict = refused(api, "/api/catalogue/add", {"source_id": SUPPLY})
    assert conflict.status == 409
    assert sources.read_text(encoding="utf-8") == before
    assert refused(api, "/api/catalogue/add", {"source_id": ""}).status == 400


# --- the overview's supply chain ----------------------------------------------------


def test_the_supply_chain_lists_chosen_supply_sources_with_their_status(project: Path) -> None:
    api = make(project)
    assert get(api, "/api/overview")["supply_chain"]["sources"] == []
    post(api, "/api/catalogue/add", {"source_id": SUPPLY})
    post(api, "/api/catalogue/add", {"source_id": "eu-packaging-europe"})
    post(api, "/api/catalogue/add", {"source_id": KEYED})
    post(api, "/api/catalogue/add", {"source_id": "us-regulations-gov-api"})
    supply = get(api, "/api/overview")["supply_chain"]
    assert supply["categories"] == list(SUPPLY_CATEGORIES)
    rows = {row["source_id"]: row for row in supply["sources"]}
    # us-eia-api publishes energy prices, so it is a commodities source; the
    # regulations.gov docket API is regulation and stays out.
    assert set(rows) == {SUPPLY, "eu-packaging-europe", KEYED}
    assert rows[KEYED]["category"] == "commodities-and-forecasts"
    assert rows[SUPPLY]["category"] == "ingredients-supply"
    assert rows[SUPPLY]["status"] == "MISSING"


# --- keys -----------------------------------------------------------------------------


def test_keys_list_presence_for_the_users_keyed_sources(project: Path) -> None:
    fake = FakeSystem("linux")
    api = make(project, fake)
    assert get(api, "/api/keys")["keys"] == []
    post(api, "/api/catalogue/add", {"source_id": KEYED})
    [row] = get(api, "/api/keys")["keys"]
    assert row == {
        "source_id": KEYED,
        "key_env": KEY_ENV,
        "present": False,
        "where": "Not set",
        "signup_url": row["signup_url"],
    }
    assert row["signup_url"].startswith("https://")
    fake.environ[KEY_ENV] = KEY
    [row] = get(api, "/api/keys")["keys"]
    assert row["present"] is True and row["where"] == "Set in the environment"


def test_keys_are_set_and_removed_as_the_command_does(project: Path) -> None:
    fake = FakeSystem("darwin")
    api = make(project, fake)
    post(api, "/api/catalogue/add", {"source_id": KEYED})
    answer = post(api, "/api/keys/set", {"source_id": KEYED, "key": KEY})
    assert answer == {"available": True, "source_id": KEYED, "present": True}
    assert fake.keychain == {KEY_ENV: KEY}
    assert KEY not in fake.argv_text()
    [row] = get(api, "/api/keys")["keys"]
    assert row["where"] == "Stored in the keychain"
    removed = post(api, "/api/keys/remove", {"source_id": KEYED})
    assert removed["removed"] is True and removed["present"] is False
    assert fake.keychain == {}
    assert post(api, "/api/keys/remove", {"source_id": KEYED})["removed"] is False


def test_a_key_is_refused_without_a_keychain_or_for_a_source_that_needs_none(
    project: Path,
) -> None:
    api = make(project, FakeSystem("linux", tools=()))
    post(api, "/api/catalogue/add", {"source_id": KEYED})
    assert get(api, "/api/keys")["keychain_available"] is False
    assert get(make(project), "/api/keys")["keychain_available"] is True
    no_tool = refused(api, "/api/keys/set", {"source_id": KEYED, "key": KEY})
    assert no_tool.status == 409 and KEY_ENV in no_tool.message and KEY not in no_tool.message
    plain = refused(api, "/api/keys/set", {"source_id": "nl-notices", "key": KEY})
    assert plain.status == 400 and KEY not in plain.message


def test_an_unusable_key_is_refused_without_echoing_it(project: Path) -> None:
    fake = FakeSystem("darwin")
    api = make(project, fake)
    post(api, "/api/catalogue/add", {"source_id": KEYED})
    bad = KEY + "'\"\\"
    error = refused(api, "/api/keys/set", {"source_id": KEYED, "key": bad})
    assert error.status == 400
    assert KEY not in error.message
    assert fake.keychain == {}


def test_a_keychain_failure_on_remove_is_reported_without_detail(project: Path) -> None:
    fake = FakeSystem("darwin")
    fake.keychain[KEY_ENV] = KEY
    api = make(project, fake)
    post(api, "/api/catalogue/add", {"source_id": KEYED})
    fake.fail.add("security delete-generic-password")
    error = refused(api, "/api/keys/remove", {"source_id": KEYED})
    assert error.status == 409 and KEY not in error.message


# --- the schedule ---------------------------------------------------------------------


def test_no_schedule_is_reported_as_not_installed(project: Path) -> None:
    state = get(make(project), "/api/automations")["schedule"]
    assert state == {
        "available": True,
        "via": "cron",
        "installed": False,
        "every": None,
        "next_run": None,
        "note": "",
    }
    missing = get(make(project, FakeSystem("linux", tools=())), "/api/automations")["schedule"]
    assert missing["note"] == "the crontab command was not found"
    broken = FakeSystem("linux")
    broken.fail.add("crontab -l")
    unread = get(make(project, broken), "/api/automations")["schedule"]
    assert unread["installed"] is False and unread["note"] == "the crontab could not be read"


@pytest.mark.parametrize(
    ("every", "next_run"),
    [
        ("hourly", "2026-10-19T12:17:00+00:00"),
        ("daily", "2026-10-20T06:17:00+00:00"),
        ("weekly", "2026-10-26T06:17:00+00:00"),
    ],
)
def test_a_cron_schedule_reports_its_cadence_and_next_run(
    project: Path, monkeypatch: pytest.MonkeyPatch, every: str, next_run: str
) -> None:
    monkeypatch.setenv("TZ", "UTC")
    import time

    time.tzset()
    fake = FakeSystem("linux")
    arguments = program_arguments("/opt/python/bin/python3", project)
    fake.crontab = "MAILTO=x\n" + cron_block(arguments, every, project.parent, project.parent / "l")
    overview = get(make(project, fake), "/api/overview")["schedule"]
    assert overview["installed"] is True
    assert overview["every"] == every
    assert overview["next_run"] == next_run


def test_a_launchd_schedule_reports_its_cadence_and_the_next_run_after_the_last(
    project: Path, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    path = plist_path(home)
    path.parent.mkdir(parents=True)
    arguments = program_arguments("/opt/python/bin/python3", project)
    path.write_bytes(plist_bytes(arguments, "daily", project.parent, project.parent / "log"))
    api = make(project, FakeSystem("darwin"), home=home)
    state = get(api, "/api/automations")["schedule"]
    assert (state["via"], state["installed"], state["every"], state["next_run"]) == (
        "launchd",
        True,
        "daily",
        None,
    )
    runner = make(project, FakeSystem("darwin"), home=home, fetcher=FakeFetcher())
    post(runner, "/api/automations/run", {})
    runner.wait_for_run(10)
    assert get(api, "/api/automations")["schedule"]["next_run"] == "2026-10-20T12:00:00+00:00"
    path.write_bytes(b"not a plist")
    assert get(api, "/api/automations")["schedule"]["note"] == "the agent file could not be read"


def test_an_unrecognised_launchd_interval_has_no_next_run(project: Path, tmp_path: Path) -> None:
    import plistlib

    home = tmp_path / "home"
    path = plist_path(home)
    path.parent.mkdir(parents=True)
    path.write_bytes(plistlib.dumps({"StartInterval": 7}))
    state = get(make(project, FakeSystem("darwin"), home=home), "/api/automations")["schedule"]
    assert state["installed"] is True and state["every"] is None and state["next_run"] is None


# --- running now --------------------------------------------------------------------------


def test_run_now_is_regwatch_run_in_the_background(project: Path) -> None:
    config = load_config(project)
    api = make(project, fetcher=FakeFetcher(snapshot_responses(config)))
    assert get(api, "/api/automations")["runs"] == {"available": True, "records": []}
    assert post(api, "/api/automations/run", {}) == {"available": True, "running": True}
    api.wait_for_run(10)
    automations = get(api, "/api/automations")
    assert automations["running"] is False and automations["last_error"] == ""
    [record] = automations["runs"]["records"]
    assert record["exit_code"] == 3
    assert record["counts"] == {"MANUAL": 1, "NEW": 4}
    assert record["started"] == NOW.isoformat(timespec="seconds")
    assert len(list_run_records(config.state_dir)) == 1


def test_only_one_run_at_a_time(project: Path) -> None:
    release = threading.Event()
    entered = threading.Event()

    class Slow(FakeFetcher):
        def fetch(self, url: str, **kwargs: Any) -> str:
            entered.set()
            release.wait(10)
            raise FetchError("stopped")

    api = make(project, fetcher=Slow())
    post(api, "/api/automations/run", {})
    assert entered.wait(10)
    try:
        assert get(api, "/api/automations")["running"] is True
        busy = refused(api, "/api/automations/run", {})
        assert busy.status == 409 and busy.message == "a run is already in progress"
    finally:
        release.set()
        api.wait_for_run(10)
    assert get(api, "/api/automations")["running"] is False


def test_a_failed_run_reports_its_kind_and_no_detail(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import regwatch.webapi as module

    def explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("PRIVATE-DETAIL")

    monkeypatch.setattr(module, "run_once", explode)
    api = make(project, fetcher=FakeFetcher())
    post(api, "/api/automations/run", {})
    api.wait_for_run(10)
    error = get(api, "/api/automations")["last_error"]
    assert error == "the run failed; run 'regwatch run' in a terminal to see why"
    assert "PRIVATE" not in error


def test_run_records_skip_unreadable_files_and_keep_only_known_fields(project: Path) -> None:
    config = load_config(project)
    runs = config.state_dir / "runs"
    runs.mkdir(parents=True)
    good = {"started": "s", "exit_code": 0, "counts": {"NEW": 1, "x": "y"}, "extra": "z"}
    (runs / "run-20261019T120000Z-aaaaaaaa.json").write_text(json.dumps(good), encoding="utf-8")
    (runs / "run-20261019T120001Z-bbbbbbbb.json").write_text("{broken", encoding="utf-8")
    (runs / "run-20261019T120002Z-cccccccc.json").write_text("[1]", encoding="utf-8")
    records = get(make(project), "/api/automations")["runs"]["records"]
    assert records == [{"started": "s", "exit_code": 0, "counts": {"NEW": 1}}]


def test_the_search_reaches_the_catalogue(project: Path) -> None:
    sources = get(make(project), "/api/search", q="tate lyle")["sources"]
    assert {
        "source_id": SUPPLY,
        "name": sources[0]["name"],
        "jurisdiction": "gb",
        "mine": False,
    } in sources
