from __future__ import annotations

from pathlib import Path

import pytest

from regwatch.config import DEFAULT_CONFIG_NAME, ConfigError, load_config

BASE = """
[register]
obligations = "o.csv"
jurisdictions = "j.json"
categories = "c.json"
sources = "s.json"
portfolio = "p.json"
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "regwatch.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_default_config_name() -> None:
    assert DEFAULT_CONFIG_NAME == "regwatch.toml"


def test_loads_example_and_resolves_relative_paths(project: Path) -> None:
    config = load_config(project)
    assert config.base_dir == project.parent.resolve()
    assert config.register.obligations == project.parent.resolve() / "register/obligations.csv"
    assert config.register.detail is not None
    assert config.state_dir == project.parent.resolve() / "state"
    assert config.snapshots_dir == project.parent.resolve() / "snapshots"
    assert config.seen_path == config.state_dir / "seen.json"
    assert config.candidates_path == config.state_dir / "ingest-candidates.json"
    assert config.ingest.cfr_parts == (101, 172)
    assert config.ingest.terms == ("allergen", "label")
    assert config.fetch.max_bytes == 2_000_000


def test_defaults_when_optional_tables_are_missing(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, BASE))
    assert config.register.detail is None
    assert config.snapshots_dir == config.state_dir / "snapshots"
    assert config.fetch.timeout_seconds == 20.0
    assert config.ingest.types == ("RULE", "PRORULE", "NOTICE")
    assert config.ingest.cfr_title is None
    assert len(config.register.all_paths()) == 5


def test_all_paths_includes_optional_files(project: Path) -> None:
    assert len(load_config(project).register.all_paths()) == 9


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="cannot read configuration file"):
        load_config(tmp_path / "absent.toml")


def test_invalid_toml(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="cannot parse"):
        load_config(write(tmp_path, "[register\n"))


def test_oversized_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="larger than"):
        load_config(write(tmp_path, "# " + "x" * 300_000))


def test_missing_required_register_keys(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="missing required keys: portfolio"):
        load_config(write(tmp_path, BASE.replace('portfolio = "p.json"', "")))


def test_unknown_table_and_key(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="unknown configuration tables: extra"):
        load_config(write(tmp_path, BASE + "\n[extra]\na = 1\n"))
    with pytest.raises(ConfigError, match="unknown keys: colour"):
        load_config(write(tmp_path, BASE + '\n[fetch]\ncolour = "red"\n'))


def test_table_must_be_a_table(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="must be a table"):
        load_config(write(tmp_path, "fetch = 3\n" + BASE))


@pytest.mark.parametrize(
    ("snippet", "message"),
    [
        ("[fetch]\ntimeout_seconds = 0\n", "timeout_seconds"),
        ('[fetch]\ntimeout_seconds = "soon"\n', "timeout_seconds"),
        ("[fetch]\nmax_bytes = 0\n", "max_bytes"),
        ("[fetch]\nmax_bytes = true\n", "max_bytes"),
        ('[fetch]\nuser_agent = ""\n', "user_agent"),
        ("[ingest]\ncfr_title = 0\n", "cfr_title"),
        ('[ingest]\ncfr_parts = ["a"]\n', "cfr_parts"),
        ("[ingest]\nagencies = [1]\n", "agencies"),
        ("[ingest]\njurisdiction = 4\n", "jurisdiction"),
        ("[ingest]\nper_page = 5000\n", "per_page"),
        ('[state]\ndir = ""\n', "dir"),
    ],
)
def test_invalid_values(tmp_path: Path, snippet: str, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        load_config(write(tmp_path, BASE + "\n" + snippet))


def test_state_dir_must_not_be_a_register_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="must not be a register file"):
        load_config(write(tmp_path, BASE + '\n[state]\ndir = "o.csv"\n'))


def test_absolute_paths_are_kept(tmp_path: Path) -> None:
    text = BASE.replace('"o.csv"', f'"{tmp_path / "abs.csv"}"')
    assert load_config(write(tmp_path, text)).register.obligations == tmp_path / "abs.csv"
