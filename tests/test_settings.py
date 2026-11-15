"""Editing one setting in regwatch.toml keeps the rest of the file, and premium round-trips."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from regwatch.cli import main
from regwatch.config import ConfigError, load_config
from regwatch.settings import SettingsError, edit_setting, set_focus_areas, set_premium
from regwatch.state import StateError

BASE = """# my project
[register]
obligations = "o.csv"  # the rows

[profile]
focus_areas = [
  "pet-food",  # one
  "cosmetics",
]
custom_terms = ["oat"]

[fetch]
max_bytes = 10
"""


def test_a_missing_table_is_added_at_the_end() -> None:
    edited = edit_setting(BASE, "premium", "enabled", True)
    assert edited.startswith(BASE)
    assert edited.endswith("\n[premium]\nenabled = true\n")
    assert tomllib.loads(edited)["premium"] == {"enabled": True}


def test_a_file_without_a_final_newline_gets_one() -> None:
    edited = edit_setting('[register]\nobligations = "o"', "premium", "enabled", False)
    assert edited == '[register]\nobligations = "o"\n\n[premium]\nenabled = false\n'


def test_a_missing_key_is_added_to_its_table() -> None:
    edited = edit_setting(BASE, "fetch", "allow_private_hosts", True)
    assert "max_bytes = 10\nallow_private_hosts = true\n" in edited
    assert "# my project" in edited


def test_an_existing_value_is_replaced_in_place_even_over_several_lines() -> None:
    edited = edit_setting(BASE, "profile", "focus_areas", ["infant-food"])
    data = tomllib.loads(edited)
    assert data["profile"] == {"focus_areas": ["infant-food"], "custom_terms": ["oat"]}
    assert '[profile]\nfocus_areas = ["infant-food"]\ncustom_terms = ["oat"]' in edited
    assert 'obligations = "o.csv"  # the rows' in edited


def test_brackets_inside_strings_and_comments_do_not_end_a_value_early() -> None:
    text = '[profile]\ncustom_terms = [\n  "a]b",  # ]] here\n  "c",\n]\nfocus_areas = []\n'
    edited = edit_setting(text, "profile", "custom_terms", ["d"])
    assert tomllib.loads(edited)["profile"] == {"custom_terms": ["d"], "focus_areas": []}


def test_values_are_written_as_safe_toml_strings() -> None:
    tricky = ['quote " and \\ backslash', "line\nbreak", "]"]
    edited = edit_setting(BASE, "profile", "custom_terms", tricky)
    assert tomllib.loads(edited)["profile"]["custom_terms"] == tricky


@pytest.mark.parametrize(
    "text",
    [
        "premium.enabled = false\n",
        "premium = { enabled = false }\n",
        "[premium]\nenabled.x = 1\n",
    ],
)
def test_a_form_the_editor_cannot_rewrite_is_refused(text: str) -> None:
    with pytest.raises(SettingsError, match="by hand"):
        edit_setting(text, "premium", "enabled", True)


def test_a_key_that_is_not_a_table_is_refused() -> None:
    with pytest.raises(SettingsError, match="not a table"):
        edit_setting('premium = "yes"\n', "premium", "enabled", True)


def test_invalid_toml_and_bad_names_are_refused() -> None:
    with pytest.raises(SettingsError, match="not valid TOML"):
        edit_setting("[broken\n", "premium", "enabled", True)
    with pytest.raises(SettingsError, match="setting name"):
        edit_setting(BASE, "premium]\nx", "enabled", True)
    with pytest.raises(SettingsError, match="setting name"):
        edit_setting(BASE, "premium", "Enabled", True)


def test_the_loader_reads_premium_and_defaults_it_off(project: Path) -> None:
    assert load_config(project).premium.enabled is False
    project.write_text(project.read_text(encoding="utf-8") + "\n[premium]\nenabled = true\n")
    assert load_config(project).premium.enabled is True


@pytest.mark.parametrize("extra", ['enabled = "yes"', "enabled = 1", "other = true"])
def test_the_loader_refuses_a_bad_premium_table(project: Path, extra: str) -> None:
    project.write_text(project.read_text(encoding="utf-8") + f"\n[premium]\n{extra}\n")
    with pytest.raises(ConfigError, match=r"\[premium\]"):
        load_config(project)


def test_set_premium_round_trips_and_keeps_comments(project: Path) -> None:
    set_premium(project, True)
    assert load_config(project).premium.enabled is True
    set_premium(project, False)
    assert load_config(project).premium.enabled is False
    text = project.read_text(encoding="utf-8")
    assert text.count("[premium]") == 1
    assert "# The next four files are optional." in text


def test_set_premium_refuses_a_linked_configuration(project: Path, tmp_path: Path) -> None:
    link = project.parent / "linked.toml"
    link.symlink_to(project)
    with pytest.raises(StateError, match="symbolic link"):
        set_premium(link, True)
    assert load_config(project).premium.enabled is False


def test_set_focus_areas_refuses_unknown_ids(project: Path) -> None:
    with pytest.raises(SettingsError, match="unknown focus areas: nope"):
        set_focus_areas(project, ["nope"], ["pet-food"])
    set_focus_areas(project, ["pet-food", "pet-food"], ["pet-food"])
    assert load_config(project).profile.focus_areas == ("pet-food",)


def test_the_premium_command_round_trips(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--config", str(project), "premium", "status"]) == 0
    out = capsys.readouterr().out
    assert "regwatch premium: off" in out
    assert "locked" in out
    assert main(["--config", str(project), "premium", "on"]) == 0
    assert "regwatch premium: on" in capsys.readouterr().out
    assert load_config(project).premium.enabled is True
    assert main(["--config", str(project), "config", "show"]) == 0
    assert "[premium]\nenabled = true" in capsys.readouterr().out
    assert main(["--config", str(project), "premium", "off"]) == 0
    assert load_config(project).premium.enabled is False


def test_the_premium_command_reports_a_file_it_cannot_edit(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project.write_text("premium.enabled = false\n" + project.read_text(encoding="utf-8"))
    assert main(["--config", str(project), "premium", "on"]) == 2
    assert "by hand" in capsys.readouterr().err
