"""`regwatch keys`, `regwatch run` and `regwatch schedule`, with every system call faked."""

from __future__ import annotations

import json
import plistlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from conftest import NOW, TODAY, FakeFetcher, FakeSystem, snapshot_responses

from regwatch.cli import main
from regwatch.config import load_config
from regwatch.schedule import (
    LABEL,
    ScheduleError,
    cron_block,
    installed_block,
    plist_bytes,
    plist_path,
    program_arguments,
    replace_block,
    schedule_cadence,
)
from regwatch.state import KEEP_RUN_RECORDS, list_run_records, write_run_record

KEY = "fake" + "-key-" + "8910"
Run = Callable[..., tuple[int, str, str]]


@pytest.fixture
def run(project: Path, capsys: pytest.CaptureFixture[str]) -> Run:
    def invoke(
        *args: str, fake: FakeSystem | None = None, fetcher: Any = None, home: Path | None = None
    ) -> tuple[int, str, str]:
        system = (fake or FakeSystem()).system(home)
        code = main(
            ["--config", str(project), *args], fetcher=fetcher, today=TODAY, now=NOW, system=system
        )
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    return invoke


# --- the builders -----------------------------------------------------------------------


def test_the_schedule_cadence_is_the_most_frequent_one() -> None:
    assert schedule_cadence(["weekly", "Daily"]) == "daily"
    assert schedule_cadence(["weekly", "hourly"]) == "hourly"
    assert schedule_cadence(["weekly"]) == "weekly"
    assert schedule_cadence(["monthly", ""]) == "daily"


def test_program_arguments_name_the_interpreter_by_absolute_path(tmp_path: Path) -> None:
    config = tmp_path / "regwatch.toml"
    assert program_arguments("/usr/bin/python3", config) == [
        "/usr/bin/python3",
        "-m",
        "regwatch",
        "--config",
        str(config.resolve()),
        "run",
    ]
    with pytest.raises(ScheduleError, match="not absolute"):
        program_arguments("python3", config)


def test_the_plist_runs_regwatch_at_the_cadence(tmp_path: Path) -> None:
    data = plistlib.loads(
        plist_bytes(["/py", "-m", "regwatch"], "hourly", tmp_path, tmp_path / "l")
    )
    assert data["Label"] == LABEL
    assert data["StartInterval"] == 3600
    assert data["ProgramArguments"] == ["/py", "-m", "regwatch"]
    assert data["WorkingDirectory"] == str(tmp_path)
    assert plist_path(Path("/h")) == Path("/h/Library/LaunchAgents") / f"{LABEL}.plist"
    with pytest.raises(ScheduleError, match="unknown cadence"):
        plist_bytes([], "monthly", tmp_path, tmp_path)


def test_the_cron_block_quotes_every_part_and_refuses_percent(tmp_path: Path) -> None:
    folder = tmp_path / "my project"
    block = cron_block(["/py", "-m", "regwatch"], "weekly", folder, folder / "s.log")
    lines = block.splitlines()
    assert lines[0].startswith("# BEGIN " + LABEL)
    assert lines[1].startswith("17 6 * * 1 cd ")
    assert f"'{folder}'" in lines[1]
    assert lines[2] == f"# END {LABEL}"
    with pytest.raises(ScheduleError, match="%"):
        cron_block(["/py"], "daily", tmp_path / "a%b", tmp_path)
    with pytest.raises(ScheduleError, match="unknown cadence"):
        cron_block(["/py"], "monthly", tmp_path, tmp_path)


def test_the_block_replaces_only_itself() -> None:
    block = cron_block(["/py"], "daily", Path("/p"), Path("/p/l"))
    mine = "MAILTO=me\n0 1 * * * backup\n"
    installed = replace_block(mine, block)
    assert installed == mine + block
    assert installed_block(installed) == block
    newer = cron_block(["/py"], "hourly", Path("/p"), Path("/p/l"))
    assert replace_block(installed, newer) == mine + newer
    assert replace_block(installed, None) == mine
    assert replace_block("no newline", block) == "no newline\n" + block
    assert installed_block(mine) is None


# --- keys ---------------------------------------------------------------------------------


def add_keyed(run: Run) -> None:
    assert run("sources", "add", "us-regulations-gov-api")[0] == 0


def test_keys_set_prompts_stores_and_never_prints_the_key(run: Run) -> None:
    fake = FakeSystem("linux")
    fake.secret = KEY + "\n"
    add_keyed(run)
    code, out, err = run("keys", "set", "us-regulations-gov-api", fake=fake)
    assert code == 0
    assert "Get a key for us-regulations-gov-api at https://" in out
    assert "stored the key" in out
    assert fake.keychain == {"REGWATCH_KEY_REGULATIONS_GOV": KEY}
    assert KEY not in out + err + fake.argv_text()


def test_keys_list_shows_presence_only(run: Run) -> None:
    fake = FakeSystem("darwin")
    fake.keychain["REGWATCH_KEY_REGULATIONS_GOV"] = KEY
    add_keyed(run)
    code, out, _ = run("keys", "list", fake=fake)
    assert code == 0
    assert "stored" in out and "us-regulations-gov-api" in out
    assert "1 of 1 keyed sources have a key" in out
    assert KEY not in out
    fake.environ["REGWATCH_KEY_REGULATIONS_GOV"] = KEY
    _code, out, _ = run("keys", "list", fake=fake)
    assert "set in the environment" in out and KEY not in out


def test_keys_list_without_a_configuration_shows_keyed_catalogue_sources(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeSystem("darwin", tools=())
    code = main(["--config", str(tmp_path / "none.toml"), "keys", "list"], system=fake.system())
    out = capsys.readouterr().out
    assert code == 0
    assert "missing (no keychain tool)" in out
    assert "us-regulations-gov-api" in out


def test_keys_remove_deletes_and_mentions_the_environment(run: Run) -> None:
    fake = FakeSystem("darwin")
    fake.keychain["REGWATCH_KEY_REGULATIONS_GOV"] = KEY
    fake.environ["REGWATCH_KEY_REGULATIONS_GOV"] = KEY
    code, out, _ = run("keys", "remove", "us-regulations-gov-api", fake=fake)
    assert code == 0
    assert "removed the key" in out
    assert "still set" in out
    assert fake.keychain == {}
    _code, out, _ = run("keys", "remove", "us-regulations-gov-api", fake=fake)
    assert "no key was stored" in out


def test_keys_refuse_a_source_that_needs_no_key(run: Run) -> None:
    code, _, err = run("keys", "set", "nl-notices")
    assert code == 2
    assert "not a source that needs a key" in err


def test_keys_set_without_a_keychain_names_the_variable(run: Run) -> None:
    code, _, err = run("keys", "set", "us-regulations-gov-api", fake=FakeSystem("linux", ()))
    assert code == 2
    assert "REGWATCH_KEY_REGULATIONS_GOV" in err


def test_keys_set_refuses_an_unusable_key_without_echoing_it(run: Run) -> None:
    fake = FakeSystem("darwin")
    fake.secret = "has space"
    code, out, err = run("keys", "set", "us-regulations-gov-api", fake=fake)
    assert code == 2
    assert "has space" not in out + err
    assert fake.keychain == {}


def test_keys_set_with_closed_input_stores_nothing(run: Run, project: Path) -> None:
    fake = FakeSystem("darwin")

    def closed(prompt: str) -> str:
        raise EOFError

    from dataclasses import replace

    system = replace(fake.system(), read_secret=closed)
    code = main(["--config", str(project), "keys", "set", "us-regulations-gov-api"], system=system)
    assert code == 2
    assert fake.keychain == {}


def test_capture_uses_the_stored_key(run: Run, project: Path) -> None:
    from test_keyed_fetch import KeyedFetcher

    fake = FakeSystem("linux")
    fake.keychain["REGWATCH_KEY_REGULATIONS_GOV"] = KEY
    add_keyed(run)
    fetcher = KeyedFetcher()
    code, out, _ = run("capture", "--source", "us-regulations-gov-api", fake=fake, fetcher=fetcher)
    assert code == 0
    assert fetcher.seen[0][1] is not None and fetcher.seen[0][1].value == KEY
    assert KEY not in out
    _code, out, _ = run("check", "--fetch", "--source", "us-regulations-gov-api", fetcher=fetcher)
    assert "no key for us-regulations-gov-api" in out
    _code, out, _ = run("sources", "add", "us-regulations-gov-api")
    assert "needs a key" in out


def test_verify_sends_the_key_when_one_is_stored(run: Run) -> None:
    from test_keyed_fetch import KeyedFetcher

    fake = FakeSystem("darwin")
    fake.keychain["REGWATCH_KEY_REGULATIONS_GOV"] = KEY
    fetcher = KeyedFetcher()
    code, _out, _ = run("sources", "verify", "us-regulations-gov-api", fake=fake, fetcher=fetcher)
    assert code == 0
    assert fetcher.seen[0][1] is not None
    fake.keychain.clear()
    run("sources", "verify", "us-regulations-gov-api", fake=fake, fetcher=fetcher)
    assert fetcher.seen[1][1] is None


# --- run ----------------------------------------------------------------------------------


def test_run_captures_checks_and_writes_a_record(run: Run, project: Path) -> None:
    config = load_config(project)
    fetcher = FakeFetcher(dict(snapshot_responses(config)))
    code, out, _ = run("run", fetcher=fetcher)
    assert "regwatch run:" in out
    records = list_run_records(config.state_dir)
    assert len(records) == 1
    record = json.loads(records[0].read_text(encoding="utf-8"))
    assert record["started"] == "2026-10-19T12:00:00+00:00"
    assert record["exit_code"] == code
    assert record["sources"] == 5
    assert record["captured"] == 4
    assert record["capture_failed"] == 0
    assert record["counts"] == {"MANUAL": 1, "NEW": 4}
    assert code == 3


def test_run_reports_a_failed_capture_as_unverified(run: Run, project: Path) -> None:
    code, out, _ = run("run", fetcher=FakeFetcher())
    assert code == 4
    record = json.loads(list_run_records(load_config(project).state_dir)[0].read_text("utf-8"))
    assert record["capture_failed"] == 4
    assert "capture failures=4" in out


def test_run_records_keep_the_newest(tmp_path: Path) -> None:
    for second in range(7):
        write_run_record(tmp_path, {"n": second}, f"20261019T1200{second:02d}Z", [], keep=3)
    (tmp_path / "runs" / "notes.txt").write_text("mine", encoding="utf-8")
    records = list_run_records(tmp_path)
    assert [json.loads(p.read_text("utf-8"))["n"] for p in records] == [4, 5, 6]
    assert (tmp_path / "runs" / "notes.txt").exists()
    assert KEEP_RUN_RECORDS == 500
    assert list_run_records(tmp_path / "none") == []
    from regwatch.state import StateError

    with pytest.raises(StateError, match="start time"):
        write_run_record(tmp_path, {}, "../x", [])


def test_python_m_regwatch_runs_the_command_line() -> None:
    import runpy
    import sys

    argv = sys.argv
    sys.argv = ["regwatch", "--version"]
    try:
        with pytest.raises(SystemExit) as caught:
            runpy.run_module("regwatch", run_name="__main__")
    finally:
        sys.argv = argv
    assert caught.value.code == 0


# --- schedule -----------------------------------------------------------------------------


def test_schedule_installs_a_launchd_agent(run: Run, tmp_path: Path, project: Path) -> None:
    fake = FakeSystem("darwin")
    home = tmp_path / "home"
    code, out, _ = run("schedule", "--install", fake=fake, home=home)
    assert code == 0
    path = plist_path(home)
    agent = plistlib.loads(path.read_bytes())
    assert agent["ProgramArguments"] == [
        "/opt/python/bin/python3",
        "-m",
        "regwatch",
        "--config",
        str(project.resolve()),
        "run",
    ]
    assert agent["StartInterval"] == 86400
    assert fake.calls == [
        ["/usr/bin/launchctl", "bootout", f"gui/501/{LABEL}"],
        ["/usr/bin/launchctl", "bootstrap", "gui/501", str(path)],
    ]
    assert "installed" in out
    code, out, _ = run("schedule", "--show", fake=fake, home=home)
    assert "installed at" in out and "cadence: daily" in out
    code, out, _ = run("schedule", "--remove", fake=fake, home=home)
    assert code == 0 and not path.exists()
    code, out, _ = run("schedule", "--remove", fake=fake, home=home)
    assert "nothing to remove" in out


def test_schedule_dry_run_changes_nothing(run: Run, tmp_path: Path) -> None:
    fake = FakeSystem("darwin")
    home = tmp_path / "home"
    code, out, _ = run(
        "schedule", "--install", "--every", "weekly", "--dry-run", fake=fake, home=home
    )
    assert code == 0
    assert "<integer>604800</integer>" in out
    assert "would run: launchctl bootstrap" in out
    assert fake.calls == [] and not home.exists()
    code, out, _ = run("schedule", "--remove", "--dry-run", fake=fake, home=home)
    assert "would remove" in out and fake.calls == []


def test_schedule_reports_a_failed_bootstrap(run: Run, tmp_path: Path) -> None:
    fake = FakeSystem("darwin")
    fake.fail.add("launchctl bootstrap")
    code, _, err = run("schedule", "--install", fake=fake, home=tmp_path / "home")
    assert code == 2
    assert "is not loaded" in err


def test_schedule_installs_and_removes_a_crontab_block(run: Run) -> None:
    fake = FakeSystem("linux")
    fake.crontab = "MAILTO=me\n"
    run("premium", "on")
    code, out, _ = run("schedule", "--install", "--every", "hourly", fake=fake)
    assert code == 0
    assert fake.crontab.startswith("MAILTO=me\n# BEGIN " + LABEL)
    assert "17 * * * * cd " in fake.crontab
    code, out, _ = run("schedule", fake=fake)
    assert "crontab block" in out and ": installed" in out
    code, out, _ = run("schedule", "--remove", "--dry-run", fake=fake)
    assert "would remove" in out and "BEGIN" in fake.crontab
    code, out, _ = run("schedule", "--remove", fake=fake)
    assert fake.crontab == "MAILTO=me\n"
    code, out, _ = run("schedule", "--remove", fake=fake)
    assert "nothing to remove" in out


def test_schedule_on_an_empty_crontab_and_in_a_dry_run(run: Run) -> None:
    fake = FakeSystem("linux")
    code, out, _ = run("schedule", "--install", "--dry-run", fake=fake)
    assert code == 0 and "would add" in out and fake.crontab is None
    code, out, _ = run("schedule", fake=fake)
    assert "not installed" in out
    run("schedule", "--install", fake=fake)
    assert fake.crontab is not None and fake.crontab.startswith("# BEGIN")


def test_schedule_never_replaces_a_crontab_it_could_not_read(run: Run) -> None:
    fake = FakeSystem("linux")
    fake.crontab = "keep me\n"
    fake.fail.add("crontab -l")
    code, _, err = run("schedule", "--install", fake=fake)
    assert code == 2
    assert "left unchanged" in err
    assert fake.crontab == "keep me\n"
    fake.fail = {"crontab -"}
    code, _, err = run("schedule", "--install", fake=fake)
    assert code == 2 and "could not install" in err


@pytest.mark.parametrize("platform", ["darwin", "linux"])
def test_a_schedule_installed_before_any_run_creates_the_state_folder(
    run: Run, project: Path, tmp_path: Path, platform: str
) -> None:
    """The job's log file is in the state folder, which neither cron nor launchd creates."""
    state = load_config(project).state_dir
    assert not state.exists()
    code, out, _ = run("schedule", "--install", fake=FakeSystem(platform), home=tmp_path / "home")
    assert code == 0, out
    assert state.is_dir()
    assert str(state / "schedule.log") in out


def test_a_dry_run_does_not_create_the_state_folder(run: Run, project: Path) -> None:
    state = load_config(project).state_dir
    run("schedule", "--install", "--dry-run", fake=FakeSystem("linux"))
    assert not state.exists()


def test_a_state_path_that_is_a_file_stops_the_install(run: Run, project: Path) -> None:
    state = load_config(project).state_dir
    state.write_text("not a folder", encoding="utf-8")
    fake = FakeSystem("linux")
    code, _, err = run("schedule", "--install", fake=fake)
    assert code == 2 and "is not a folder" in err
    assert fake.crontab is None


def test_a_dangling_link_as_the_state_path_stops_the_install(
    run: Run, project: Path, tmp_path: Path
) -> None:
    state = load_config(project).state_dir
    state.symlink_to(tmp_path / "nowhere")
    code, _, err = run("schedule", "--install", fake=FakeSystem("linux"))
    assert code == 2 and "symbolic link" in err
    assert not (tmp_path / "nowhere").exists()


# --- premium: runs more often than daily ----------------------------------------------


def make_a_source_hourly(project: Path) -> None:
    path = project.parent / "register" / "sources.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["sources"][0]["cadence"] = "hourly"
    path.write_text(json.dumps(data), encoding="utf-8")


def test_without_premium_every_hourly_is_refused(run: Run) -> None:
    fake = FakeSystem("linux")
    code, _, err = run("schedule", "--install", "--every", "hourly", fake=fake)
    assert code == 2
    assert "premium feature" in err and "regwatch premium on" in err
    assert fake.crontab is None and fake.calls == []
    code, _, err = run("schedule", "--install", "--every", "hourly", "--dry-run", fake=fake)
    assert code == 2


def test_without_premium_an_hourly_source_is_scheduled_daily(run: Run, project: Path) -> None:
    make_a_source_hourly(project)
    fake = FakeSystem("linux")
    code, out, _ = run("schedule", "--install", fake=fake)
    assert code == 0
    assert "runs daily" in out and "regwatch premium on" in out
    assert "to run daily" in out
    assert "\n17 6 * * * cd " in "\n" + (fake.crontab or "")


def test_with_premium_hourly_runs_are_allowed(run: Run, project: Path) -> None:
    make_a_source_hourly(project)
    run("premium", "on")
    fake = FakeSystem("linux")
    code, out, _ = run("schedule", "--install", fake=fake)
    assert code == 0 and "to run hourly" in out and "premium feature" not in out
    assert "17 * * * * cd " in (fake.crontab or "")


def test_removing_never_asks_for_premium(run: Run) -> None:
    code, out, _ = run("schedule", "--remove", "--every", "hourly", fake=FakeSystem("linux"))
    assert code == 0 and "nothing to remove" in out


def test_weekly_and_daily_need_no_premium(run: Run) -> None:
    for every in ("daily", "weekly"):
        fake = FakeSystem("linux")
        code, out, _ = run("schedule", "--install", "--every", every, fake=fake)
        assert code == 0 and f"to run {every}" in out


def test_schedule_needs_its_tool_and_one_action(run: Run) -> None:
    code, _, err = run("schedule", "--install", fake=FakeSystem("linux", tools=()))
    assert code == 2 and "crontab command was not found" in err
    code, _, err = run("schedule", "--install", "--remove")
    assert code == 2 and "choose one" in err
