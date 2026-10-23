"""The guided part of `regwatch init`: choosing sources, keys, a schedule and a first run."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from conftest import NOW, TODAY, FakeSystem
from test_keyed_fetch import KeyedFetcher

from regwatch.catalogue import load_source_catalogue
from regwatch.cli import _Completer, _Context, _title, _with_completion, main
from regwatch.config import load_config
from regwatch.focus import load_catalogue
from regwatch.onboarding import matching_entries
from regwatch.register import validate_register

KEY = "fake" + "-key-" + "1112"
CATALOGUE = load_source_catalogue([area.focus_id for area in load_catalogue(None)])
Run = Callable[..., tuple[int, str, str]]


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "home"
    directory.mkdir()
    monkeypatch.setenv("HOME", str(directory))
    monkeypatch.chdir(directory)
    return directory


@pytest.fixture
def run(capsys: pytest.CaptureFixture[str]) -> Run:
    def invoke(
        *args: str, fake: FakeSystem | None = None, fetcher: Any = None
    ) -> tuple[int, str, str]:
        system = (fake or FakeSystem("linux")).system()
        code = main(list(args), today=TODAY, now=NOW, system=system, fetcher=fetcher)
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    return invoke


@pytest.fixture
def answers(monkeypatch: pytest.MonkeyPatch) -> Callable[..., list[str]]:
    def script(*replies: str) -> list[str]:
        remaining = list(replies)
        prompts: list[str] = []

        def fake(prompt: str = "") -> str:
            prompts.append(prompt)
            if not remaining:
                raise EOFError
            return remaining.pop(0)

        monkeypatch.setattr("builtins.input", fake)
        return prompts

    return script


def sources_in(directory: Path) -> dict[str, dict[str, str]]:
    data = json.loads((directory / "register" / "sources.json").read_text("utf-8"))
    return {s["source_id"]: s for s in data["sources"]}


def assert_valid(directory: Path) -> None:
    assert validate_register(load_config(directory / "regwatch.toml")) == []


# --- matching -------------------------------------------------------------------------


def ids(entries: list[Any]) -> set[str]:
    return {entry.source_id for entry in entries}


def test_matching_keeps_every_entry_without_choices() -> None:
    assert len(matching_entries(CATALOGUE, [], [])) == len(CATALOGUE)


def test_matching_by_jurisdiction_name_id_parent_and_international() -> None:
    by_name = ids(matching_entries(CATALOGUE, [], [{"jurisdiction_id": "x", "name": "Canada"}]))
    assert "ca-cfia-recalls-rss" in by_name
    assert all(
        e.jurisdiction in ("intl",) or e.jurisdiction.split("-")[0] == "ca"
        for e in CATALOGUE
        if e.source_id in by_name
    )
    by_id = ids(matching_entries(CATALOGUE, [], [{"jurisdiction_id": "us", "name": "US"}]))
    assert {e.source_id for e in CATALOGUE if e.jurisdiction == "us-ca"} <= by_id
    assert "gb-fsa-food-alerts-api" not in by_id
    assert {e.source_id for e in CATALOGUE if e.jurisdiction == "intl"} <= by_id


def test_matching_by_focus_keeps_entries_for_every_area() -> None:
    found = matching_entries(CATALOGUE, ["alcoholic-beverages"], [])
    assert all(not e.focus_areas or "alcoholic-beverages" in e.focus_areas for e in found)
    assert any(e.focus_areas for e in found)
    assert len(found) < len(CATALOGUE)
    # An entry that lists no focus area serves every area, so it is kept.
    general = {e.source_id for e in CATALOGUE if not e.focus_areas}
    assert general and general <= ids(found)


# --- flags ------------------------------------------------------------------------------


def test_sources_by_flag_are_written_with_their_jurisdictions(
    home: Path, run: Run, answers: Callable[..., list[str]]
) -> None:
    prompts = answers()
    directory = home / "work"
    code, out, _ = run(
        "init",
        "--dir",
        str(directory),
        "--yes",
        "--jurisdiction",
        "United States",
        "--sources",
        "us-fda-recalls-rss, us-regulations-gov-api,gb-fsa-food-alerts-api",
    )
    assert code == 0
    assert prompts == []
    chosen = sources_in(directory)
    assert set(chosen) == {"us-fda-recalls-rss", "us-regulations-gov-api", "gb-fsa-food-alerts-api"}
    assert chosen["us-fda-recalls-rss"]["jurisdiction"] == "united-states"
    assert chosen["gb-fsa-food-alerts-api"]["jurisdiction"] == "gb"
    assert chosen["us-regulations-gov-api"]["auth"] == "query:api_key"
    assert "Sources: us-fda-recalls-rss, us-regulations-gov-api, gb-fsa-food-alerts-api" in out
    assert "us-regulations-gov-api needs a key (Free Key)." in out
    assert "keys set us-regulations-gov-api" in out
    assert "schedule --install" in out
    assert_valid(directory)


def test_an_unknown_source_flag_writes_nothing(home: Path, run: Run) -> None:
    directory = home / "work"
    code, _, err = run("init", "--dir", str(directory), "--yes", "--sources", "nope")
    assert code == 2
    assert "not in the source catalogue: nope" in err
    assert not directory.exists()


def test_schedule_and_first_run_by_flag(home: Path, run: Run) -> None:
    fake = FakeSystem("linux")
    directory = home / "work"
    fetcher = KeyedFetcher()
    code, out, _ = run(
        "init",
        "--dir",
        str(directory),
        "--yes",
        "--sources",
        "ca-cfia-recalls-rss",
        "--schedule",
        "--first-run",
        fake=fake,
        fetcher=fetcher,
    )
    assert fake.crontab is not None and "regwatch" in fake.crontab
    assert "installed io.github.klappe-pm.regwatch" in out
    assert "regwatch run: 1 sources" in out
    assert code == 3  # the first run sees a NEW source
    assert len(list((directory / "state" / "runs").iterdir())) == 1


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_a_missing_scheduler_does_not_stop_init(home: Path, run: Run, platform: str) -> None:
    """Without crontab or launchctl, init says so, then still runs and gives its guidance."""
    fake = FakeSystem(platform, tools=())
    directory = home / "work"
    code, out, err = run(
        "init",
        "--dir",
        str(directory),
        "--yes",
        "--sources",
        "ca-cfia-recalls-rss",
        "--schedule",
        "--first-run",
        fake=fake,
        fetcher=KeyedFetcher(),
    )
    tool = "launchctl" if platform == "darwin" else "crontab"
    assert f"the {tool} command was not found" in err
    assert "no schedule was installed" in out and "schedule --install" in out
    assert "regwatch run: 1 sources" in out
    assert "Next, describe your products" in out
    assert code == 3  # the first run's result is kept
    assert_valid(directory)


def test_a_missing_scheduler_without_a_first_run_exits_2(home: Path, run: Run) -> None:
    code, out, err = run(
        "init",
        "--dir",
        str(home / "work"),
        "--yes",
        "--schedule",
        "--no-first-run",
        fake=FakeSystem("linux", tools=()),
    )
    assert code == 2
    assert "crontab command was not found" in err
    assert "Next, describe your products" in out


def test_no_schedule_and_no_first_run_are_not_asked(
    home: Path, run: Run, answers: Callable[..., list[str]]
) -> None:
    prompts = answers("", "", "", "", "", "", "y")
    code, _out, _ = run("init", "--dir", str(home / "w"), "--no-schedule", "--no-first-run")
    assert code == 0
    assert not any("schedule" in p.lower() for p in prompts)


# --- the interactive picker ----------------------------------------------------------------


def test_the_picker_groups_selects_unselects_and_searches(
    home: Path, run: Run, answers: Callable[..., list[str]]
) -> None:
    directory = home / "work"
    prompts = answers(
        "pet-food",  # focus
        "",  # terms
        "United Kingdom",  # jurisdictions
        "gb-fsa-food-alerts-api",  # select by id
        "gb-fsa-food-alerts-api",  # and unselect it again
        "food standards agency alerts",  # search
        "1",  # select the first result
        "zzzz qqqq",  # a search with no result
        "",  # done
        "",  # files
        "",  # contact
        "y",  # create
        "n",  # schedule
        "n",  # first run
    )
    code, out, _ = run("init", "--dir", str(directory), fake=FakeSystem("linux"))
    assert code == 0
    assert "Regulation, Europe:" in out
    assert "(Free)" in out
    assert "selected gb-fsa-food-alerts-api" in out
    assert "unselected gb-fsa-food-alerts-api" in out
    assert "no source matches" in out
    chosen = sources_in(directory)
    from regwatch.catalogue import rank

    assert list(chosen) == [rank(CATALOGUE, "food standards agency alerts")[0].source_id]
    assert prompts[-1].startswith("Run a first capture and check now?")
    assert_valid(directory)


def test_a_long_search_says_how_many_more(
    home: Path, run: Run, answers: Callable[..., list[str]]
) -> None:
    answers("", "", "", "regulator", "", "", "", "n")
    code, out, err = run("init", "--dir", str(home / "w"))
    assert code == 2 and "cancelled" in err
    assert "more; type more words to narrow the search" in out


def test_a_source_that_is_not_listed_can_be_added(
    home: Path, run: Run, answers: Callable[..., list[str]]
) -> None:
    directory = home / "work"
    answers(
        "",
        "",
        "",
        "+",
        "gb-my-feed",
        "My Feed",
        "GB",
        "http://feeds.example.org/x.xml",  # refused: not https
        "rss",
        "",
        "A feed of my own.",
        "+",
        "gb-my-feed",
        "My Feed",
        "gb",
        "https://feeds.example.org/x.xml",
        "rss",
        "",
        "A feed of my own.",
        "+",
        "us-fda-recalls-rss",  # already in the catalogue
        "x",
        "us",
        "https://example.org/",
        "",
        "",
        "Something.",
        "",
        "",
        "",
        "y",
    )
    code, out, err = run("init", "--dir", str(directory))
    assert code == 0
    assert "URL scheme 'http' is not allowed" in err
    assert "already in the catalogue" in err
    assert "added gb-my-feed" in out
    feed = sources_in(directory)["gb-my-feed"]
    assert feed["mechanism"] == "rss" and feed["cadence"] == "daily"
    assert_valid(directory)


def test_keys_schedule_and_first_run_when_answered_yes(
    home: Path, run: Run, answers: Callable[..., list[str]]
) -> None:
    fake = FakeSystem("darwin")
    fake.secret = KEY
    directory = home / "work"
    prompts = answers("", "", "", "us-regulations-gov-api", "", "", "", "y", "y", "y", "y")
    fetcher = KeyedFetcher()
    code, out, _ = run("init", "--dir", str(directory), fake=fake, fetcher=fetcher)
    assert any(p.startswith("  Store the key for us-regulations-gov-api now?") for p in prompts)
    assert fake.keychain == {"REGWATCH_KEY_REGULATIONS_GOV": KEY}
    assert "Stored in the macOS login keychain." in out
    assert KEY not in out and KEY not in fake.argv_text()
    assert (home / "Library").exists() is False  # the fake home is elsewhere
    assert any(call[1] == "bootstrap" for call in fake.calls if "launchctl" in call[0])
    assert fetcher.seen[0][1] is not None and fetcher.seen[0][1].value == KEY
    assert code == 3


def test_a_key_already_present_or_refused_is_reported(
    home: Path, run: Run, answers: Callable[..., list[str]]
) -> None:
    fake = FakeSystem("linux")
    fake.environ["REGWATCH_KEY_REGULATIONS_GOV"] = KEY
    answers("", "", "", "us-regulations-gov-api", "", "", "", "y", "n", "n")
    code, out, _ = run("init", "--dir", str(home / "a"), fake=fake)
    assert code == 0 and "A key is already available." in out

    fake = FakeSystem("linux")
    fake.secret = "has space"
    answers("", "", "", "us-regulations-gov-api", "", "", "", "y", "y", "n", "n")
    code, _out, err = run("init", "--dir", str(home / "b"), fake=fake)
    assert code == 0
    assert "run 'regwatch keys set us-regulations-gov-api' later" in err
    assert "has space" not in err
    assert fake.keychain == {}


# --- completion ------------------------------------------------------------------------------


def test_the_completer_offers_ids_only() -> None:
    """A name holds spaces, which end the word readline completes, so only ids are offered."""
    completer = _Completer(CATALOGUE)
    assert completer("us-fda-recalls", 0) == "us-fda-recalls-rss"
    assert completer("us-fda-recalls", 1) is None
    offered = [completer("US", state) for state in range(len(CATALOGUE))]
    offered = [word for word in offered if word]
    assert offered and all(" " not in word for word in offered)
    assert all(word in {e.source_id for e in CATALOGUE} for word in offered)


def test_each_word_of_an_answer_completes_on_its_own() -> None:
    """Space is a delimiter, so the second id of "nl-notices us-fda-rec" completes."""
    from regwatch.cli import COMPLETER_DELIMS

    assert " " in COMPLETER_DELIMS and "," in COMPLETER_DELIMS
    line = "ca-cfia-recalls-rss us-fda-rec"
    word = re.split(f"[{re.escape(COMPLETER_DELIMS)}]", line)[-1]
    assert _Completer(CATALOGUE)(word, 0) == "us-fda-recalls-rss"


def test_a_name_typed_in_full_selects_its_source(
    home: Path, run: Run, answers: Callable[..., list[str]]
) -> None:
    by_id = {entry.source_id: entry for entry in CATALOGUE}
    name = by_id["us-fda-recalls-rss"].name
    assert sum(1 for e in CATALOGUE if e.name.casefold() == name.casefold()) == 1
    answers("", "", "", name.upper(), "", "", "", "y")
    directory = home / "work"
    code, out, _ = run("init", "--dir", str(directory), "--no-schedule", "--no-first-run")
    assert code == 0, out
    assert "selected us-fda-recalls-rss" in out
    assert "us-fda-recalls-rss" in sources_in(directory)


def test_the_picker_toggles_by_a_full_name_and_searches_otherwise() -> None:
    from regwatch.cli import _toggle_tokens

    by_id = {entry.source_id: entry for entry in CATALOGUE}
    entry = by_id["gb-fsa-food-alerts-api"]
    assert _toggle_tokens(f"  {entry.name.lower()} ", [], by_id) == [entry]
    assert _toggle_tokens(entry.name.split()[0], [], by_id) is None


def test_completion_is_turned_on_only_for_a_terminal_and_then_restored() -> None:
    import readline
    from dataclasses import replace

    fake = FakeSystem("linux")
    ctx = _Context(Path("x.toml"), None, TODAY, NOW, fake.system())
    assert _with_completion(ctx, CATALOGUE)() is None
    before = readline.get_completer()
    ctx = _Context(
        Path("x.toml"), None, TODAY, NOW, replace(fake.system(), stdin_is_terminal=lambda: True)
    )
    restore = _with_completion(ctx, CATALOGUE)
    assert isinstance(readline.get_completer(), _Completer)
    restore()
    assert readline.get_completer() is before


def test_group_headings_keep_small_words_lower_case() -> None:
    assert _title("policy-and-lobbying") == "Policy and Lobbying"
    assert _title("regulation") == "Regulation"
