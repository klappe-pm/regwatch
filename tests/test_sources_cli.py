"""`regwatch sources`: list, search, show, add, remove and verify."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from conftest import NOW, TODAY, FakeFetcher

from regwatch.catalogue import filter_entries, load_source_catalogue
from regwatch.cli import main
from regwatch.config import ConfigError, load_config
from regwatch.fetch import FetchError
from regwatch.focus import load_catalogue
from regwatch.register import load_register, validate_register

CATALOGUE = load_source_catalogue([area.focus_id for area in load_catalogue(None)])
URL = {entry.source_id: entry.url for entry in CATALOGUE}
Run = Callable[..., tuple[int, str, str]]


@pytest.fixture
def run(project: Path, capsys: pytest.CaptureFixture[str]) -> Run:
    def invoke(*args: str, fetcher: Any = None, config: Path | None = None) -> tuple[int, str, str]:
        code = main(
            ["--config", str(config or project), "sources", *args],
            fetcher=fetcher,
            today=TODAY,
            now=NOW,
        )
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    return invoke


def sources_of(project: Path) -> list[dict[str, Any]]:
    data = json.loads((project.parent / "register" / "sources.json").read_text("utf-8"))
    result: list[dict[str, Any]] = data["sources"]
    return result


def jurisdiction_ids(project: Path) -> list[str]:
    data = json.loads((project.parent / "register" / "jurisdictions.json").read_text("utf-8"))
    return [j["jurisdiction_id"] for j in data["jurisdictions"]]


# --- reading the catalogue -----------------------------------------------------------


def test_list_shows_every_entry_with_its_access_label(run: Run) -> None:
    code, out, _ = run("list")
    assert code == 0
    assert "us-regulations-gov-api" in out
    assert "Free Key" in out and "Paid" in out
    assert f"regwatch sources list: {len(CATALOGUE)} sources" in out


def test_list_works_without_a_configuration(tmp_path: Path, run: Run) -> None:
    code, out, _ = run("list", "--region", "asia-pacific", config=tmp_path / "none.toml")
    assert code == 0
    assert "au-foodstandards-rss" in out
    expected = len(filter_entries(CATALOGUE, region="asia-pacific"))
    assert f"{expected} sources" in out


@pytest.mark.parametrize(
    "flags",
    [
        {"jurisdiction": "eu"},
        {"jurisdiction": "us"},
        {"access": "paid"},
        {"access": "free-key"},
        {"kind": "gazette"},
        {"category": "industry-news"},
        {"category": "logistics-and-trade"},
        {"region": "europe"},
        {"focus": "alcoholic-beverages"},
    ],
)
def test_list_filters(run: Run, flags: dict[str, str]) -> None:
    arguments = [part for key, value in flags.items() for part in (f"--{key}", value)]
    code, out, _ = run("list", "--json", *arguments)
    assert code == 0
    payload = json.loads(out)
    expected = [entry.source_id for entry in filter_entries(CATALOGUE, **flags)]  # type: ignore[arg-type]
    assert [s["source_id"] for s in payload["sources"]] == expected
    assert payload["count"] == len(expected) > 0
    for key, value in flags.items():
        if key in ("access", "kind", "category", "region"):
            assert {s[key] for s in payload["sources"]} == {value}


def test_list_chosen_reads_the_sources_file(run: Run) -> None:
    assert run("add", "au-foodstandards-rss")[0] == 0
    code, out, _ = run("list", "--chosen", "--json")
    assert code == 0
    assert [s["source_id"] for s in json.loads(out)["sources"]] == ["au-foodstandards-rss"]


def test_search_ranks_and_prints_json(run: Run) -> None:
    code, out, _ = run("search", "recalls", "--json")
    assert code == 0
    payload = json.loads(out)
    from regwatch.catalogue import rank

    assert [s["source_id"] for s in payload["sources"]] == [
        entry.source_id for entry in rank(CATALOGUE, "recalls")
    ]
    assert all("category" in s and "access_label" in s for s in payload["sources"])
    code, out, _ = run("search", "eu")
    first = out.splitlines()[0].split()[0]
    assert next(e for e in CATALOGUE if e.source_id == first).jurisdiction == "eu"


def test_show_prints_every_field(run: Run) -> None:
    code, out, _ = run("show", "us-regulations-gov-api")
    assert code == 0
    assert "Regulations.gov API v4 (Free Key)" in out
    assert "query:api_key" in out
    assert "REGWATCH_KEY_REGULATIONS_GOV" in out
    assert "category:" in out
    code, out, _ = run("show", "ca-cfia-recalls-rss", "--json")
    assert json.loads(out)["access_label"] == "Free"
    assert json.loads(out)["category"] == "regulation"


def test_an_unknown_id_is_an_error(run: Run) -> None:
    code, _, err = run("show", "nope")
    assert code == 2
    assert "not in the source catalogue: nope" in err


# --- the extra catalogue ---------------------------------------------------------------


def extra_entry() -> dict[str, Any]:
    return {
        "source_id": "nl-extra-feed",
        "name": "Northland Extra Feed",
        "publisher": "Northland",
        "jurisdiction": "nl",
        "region": "europe",
        "kind": "regulator",
        "category": "regulation",
        "mechanism": "rss",
        "url": "https://regulator.nl.example/extra.xml",
        "homepage": "https://regulator.nl.example/",
        "access": "free",
        "auth": None,
        "key_env": None,
        "signup_url": None,
        "focus_areas": [],
        "language": "en",
        "cadence": "weekly",
        "description": "An invented extra source.",
        "verified": False,
        "checked": "2026-10-23",
        "notes": None,
    }


def with_extra(project: Path, entries: list[dict[str, Any]]) -> Path:
    extra = project.parent / "my-sources.json"
    extra.write_text(json.dumps({"version": 1, "sources": entries}), encoding="utf-8")
    with project.open("a", encoding="utf-8") as handle:
        handle.write('\n[catalogue]\nextra = "my-sources.json"\n')
    return extra


def test_the_extra_catalogue_is_listed_and_can_be_added(project: Path, run: Run) -> None:
    extra = with_extra(project, [extra_entry()])
    assert extra.resolve() in load_config(project).protected_paths()
    _code, out, _ = run("search", "northland")
    assert "nl-extra-feed" in out
    code, out, _ = run("add", "nl-extra-feed")
    assert code == 0
    assert "jurisdiction" not in out  # nl is already in the register
    assert validate_register(load_config(project)) == []


def test_an_invalid_extra_catalogue_is_refused(project: Path, run: Run) -> None:
    bad = extra_entry()
    bad["url"] = "http://regulator.nl.example/extra.xml"
    with_extra(project, [bad])
    code, _, err = run("list")
    assert code == 2
    assert "url" in err


def test_the_catalogue_table_takes_only_known_keys(project: Path) -> None:
    with project.open("a", encoding="utf-8") as handle:
        handle.write('\n[catalogue]\nother = "x"\n')
    with pytest.raises(ConfigError, match="unknown keys: other"):
        load_config(project)


# --- add and remove ----------------------------------------------------------------------


def test_add_copies_entries_and_jurisdictions_and_the_register_stays_valid(
    project: Path, run: Run
) -> None:
    code, out, _ = run("add", "us-regulations-gov-api", "ca-cfia-recalls-rss")
    assert code == 0
    assert "added      jurisdiction us" in out
    assert "regwatch sources add: 2 added, 0 already present" in out
    added = {s["source_id"]: s for s in sources_of(project)}
    assert added["us-regulations-gov-api"]["auth"] == "query:api_key"
    assert added["us-regulations-gov-api"]["key_env"] == "REGWATCH_KEY_REGULATIONS_GOV"
    assert added["ca-cfia-recalls-rss"]["method"] == "poll"
    assert {"us", "ca"} <= set(jurisdiction_ids(project))
    register = load_register(load_config(project))
    keyed = next(s for s in register.sources if s.source_id == "us-regulations-gov-api")
    assert (keyed.auth, keyed.key_env) == ("query:api_key", "REGWATCH_KEY_REGULATIONS_GOV")


def test_adding_again_changes_nothing(project: Path, run: Run) -> None:
    run("add", "au-foodstandards-rss")
    before = (project.parent / "register" / "sources.json").read_bytes()
    code, out, _ = run("add", "au-foodstandards-rss")
    assert code == 0
    assert "present" in out
    assert (project.parent / "register" / "sources.json").read_bytes() == before


def test_add_never_overwrites_a_different_entry(
    project: Path, run: Run, edit_json: Callable[[Path, Callable[[Any], None]], None]
) -> None:
    run("add", "au-foodstandards-rss")

    def edit(data: Any) -> None:
        data["sources"][-1]["notes"] = "my own note"

    path = project.parent / "register" / "sources.json"
    edit_json(path, edit)
    before = path.read_bytes()
    code, _, err = run("add", "ca-cfia-recalls-rss", "au-foodstandards-rss")
    assert code == 2
    assert "different entry with the id au-foodstandards-rss" in err
    assert path.read_bytes() == before


def test_add_needs_a_configuration(tmp_path: Path, run: Run) -> None:
    code, _, err = run("add", "au-foodstandards-rss", config=tmp_path / "none.toml")
    assert code == 2
    assert "cannot read configuration file" in err


def test_add_refuses_a_sources_file_that_is_a_link(project: Path, run: Run) -> None:
    path = project.parent / "register" / "sources.json"
    real = project.parent / "real-sources.json"
    path.rename(real)
    path.symlink_to(real)
    code, _, err = run("add", "au-foodstandards-rss")
    assert code == 2
    assert "symbolic link" in err


def test_remove_takes_a_source_out(project: Path, run: Run) -> None:
    run("add", "au-foodstandards-rss")
    code, out, _ = run("remove", "au-foodstandards-rss")
    assert code == 0
    assert "removed au-foodstandards-rss" in out
    assert "au-foodstandards-rss" not in {s["source_id"] for s in sources_of(project)}


def test_remove_refuses_a_source_that_obligations_cite(project: Path, run: Run) -> None:
    code, _, err = run("remove", "nl-notices")
    assert code == 2
    assert "obligations cite source 'nl-notices'" in err
    assert "nl-notices" in {s["source_id"] for s in sources_of(project)}


def test_remove_refuses_an_unknown_source(run: Run) -> None:
    code, _, err = run("remove", "missing-source")
    assert code == 2
    assert "no source 'missing-source'" in err


# --- verify ----------------------------------------------------------------------------


def test_verify_reports_each_status_and_never_changes_the_catalogue(run: Run) -> None:
    fetcher = FakeFetcher(
        {
            URL["au-foodstandards-rss"]: "<rss/>",
            URL["ca-cfia-recalls-rss"]: FetchError("HTTP status 404"),
        }
    )
    code, out, _ = run("verify", "au-foodstandards-rss", "ca-cfia-recalls-rss", fetcher=fetcher)
    assert code == 4
    assert "ok       au-foodstandards-rss" in out
    assert "failed   ca-cfia-recalls-rss" in out and "HTTP status 404" in out
    assert "1 ok, 1 failed" in out
    assert fetcher.requested == [URL["au-foodstandards-rss"], URL["ca-cfia-recalls-rss"]]


def test_verify_without_ids_checks_every_entry(run: Run) -> None:
    fetcher = FakeFetcher()
    code, out, _ = run("verify", fetcher=fetcher)
    assert code == 4
    assert len(fetcher.requested) == len(CATALOGUE)
    assert f"0 ok, {len(CATALOGUE)} failed" in out


def test_verify_builds_a_real_fetcher_without_a_configuration(
    tmp_path: Path, run: Run, monkeypatch: pytest.MonkeyPatch
) -> None:
    import regwatch.fetch as fetch_module

    def refuse(self: object, url: str) -> str:
        raise FetchError("offline in tests")

    monkeypatch.setattr(fetch_module.SafeFetcher, "fetch", refuse)
    code, out, _ = run("verify", "au-foodstandards-rss", config=tmp_path / "none.toml")
    assert code == 4
    assert "offline in tests" in out


# --- the register rules for keyed sources --------------------------------------------------


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"auth": "query:api_key"}, "must be given together"),
        ({"key_env": "REGWATCH_KEY_X"}, "must be given together"),
        ({"auth": "cookie:x", "key_env": "REGWATCH_KEY_X"}, "does not match pattern"),
        ({"auth": "query:k", "key_env": "lower"}, "does not match pattern"),
        (
            {"auth": "query:k", "key_env": "K", "url": "file:///tmp/x"},
            "must have an https URL",
        ),
    ],
)
def test_the_register_checks_keyed_sources(
    project: Path,
    edit_json: Callable[[Path, Callable[[Any], None]], None],
    changes: dict[str, str],
    message: str,
) -> None:
    def edit(data: Any) -> None:
        data["sources"][0].update(changes)

    edit_json(project.parent / "register" / "sources.json", edit)
    errors = validate_register(load_config(project))
    assert any(message in error for error in errors), errors


def test_an_extra_entry_may_name_a_focus_area_of_the_users_own_catalogue(
    project: Path, run: Run
) -> None:
    focus = {
        "focus_areas": [
            {"focus_id": "my-area", "label": "My Area", "description": "", "terms": ["widget"]}
        ]
    }
    (project.parent / "my-focus.json").write_text(json.dumps(focus), encoding="utf-8")
    entry = extra_entry()
    entry["focus_areas"] = ["my-area"]
    with_extra(project, [entry])
    with project.open("a", encoding="utf-8") as handle:
        handle.write('\n[profile]\ncatalogue = "my-focus.json"\n')
    code, out, _ = run("list", "--focus", "my-area", "--json")
    assert code == 0
    assert "nl-extra-feed" in {s["source_id"] for s in json.loads(out)["sources"]}
