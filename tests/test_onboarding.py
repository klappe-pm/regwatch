"""`regwatch init`, `regwatch config show` and the onboarding helpers."""

from __future__ import annotations

import json
import tomllib
from collections.abc import Callable
from pathlib import Path

import pytest
from conftest import NOW, TODAY

from regwatch.cli import main
from regwatch.config import ConfigError, load_config
from regwatch.focus import load_catalogue
from regwatch.onboarding import (
    SCAFFOLD_NAMES,
    InitPlan,
    OnboardingError,
    check_contact,
    check_directory,
    check_file_root,
    clean_terms,
    clean_value,
    example_jurisdictions,
    jurisdiction_records,
    parse_focus_choice,
    scaffold_files,
    user_agent_for,
)
from regwatch.register import load_register, validate_register

Run = Callable[..., tuple[int, str, str]]


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A stand-in home directory, so nothing here can reach the real one."""
    directory = tmp_path / "home"
    directory.mkdir()
    monkeypatch.setenv("HOME", str(directory))
    monkeypatch.chdir(directory)
    return directory


@pytest.fixture
def run(capsys: pytest.CaptureFixture[str]) -> Run:
    def invoke(*args: str) -> tuple[int, str, str]:
        code = main(list(args), today=TODAY, now=NOW)
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    return invoke


@pytest.fixture
def answers(monkeypatch: pytest.MonkeyPatch) -> Callable[..., list[str]]:
    """Script the replies to input(). Returns the list of prompts that were shown."""

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


def project_dir(home: Path, name: str = "work") -> Path:
    return home / name


def read_config(directory: Path) -> dict[str, object]:
    return tomllib.loads((directory / "regwatch.toml").read_text(encoding="utf-8"))


def assert_valid_register(directory: Path) -> None:
    config = load_config(directory / "regwatch.toml")
    assert validate_register(config) == []
    load_register(config)


# --- init with flags ---------------------------------------------------------


def test_init_with_yes_creates_a_valid_empty_project(home: Path, run: Run) -> None:
    directory = project_dir(home)
    code, out, _ = run("init", "--yes", "--dir", str(directory))
    assert code == 0
    for name in SCAFFOLD_NAMES:
        assert (directory / name).is_file(), name
    assert_valid_register(directory)
    register = load_register(load_config(directory / "regwatch.toml"))
    assert register.obligations == () and register.portfolio.products == ()
    config = read_config(directory)
    assert config["profile"] == {
        "focus_areas": [],
        "custom_terms": [],
        "catalogue": "focus-areas.json",
    }
    assert "fetch" not in config, "defaults are not written when nothing was answered"
    assert f"wrote 7 files in {directory}" in out
    assert f"regwatch --config {directory / 'regwatch.toml'} validate" in out
    assert "not legal advice" in out
    code, out, _ = run("--config", str(directory / "regwatch.toml"), "validate")
    assert code == 0 and "errors=0" in out


def test_init_records_every_answer_given_as_a_flag(home: Path, run: Run) -> None:
    directory = project_dir(home)
    code, out, _ = run(
        "init",
        "--yes",
        "--dir",
        str(directory),
        "--focus",
        "1",
        "--focus",
        "pet-food",
        "--term",
        "Boba",
        "--term",
        "boba",
        "--jurisdiction",
        "Greater Eastland",
        "--jurisdiction",
        "Eastland",
        "--allow-file-root",
        "feeds",
        "--contact",
        "ops@example.com",
    )
    assert code == 0
    config = read_config(directory)
    assert config["profile"] == {
        "focus_areas": ["non-alcoholic-beverages", "pet-food"],
        "custom_terms": ["Boba"],
        "catalogue": "focus-areas.json",
    }
    assert config["fetch"] == {
        "user_agent": "regwatch/0.1.0 (+ops@example.com)",
        "allowed_file_roots": ["feeds"],
    }
    loaded = load_config(directory / "regwatch.toml")
    assert loaded.fetch.allowed_file_roots == (directory.resolve() / "feeds",)
    assert loaded.fetch.user_agent == "regwatch/0.1.0 (+ops@example.com)"
    jurisdictions = json.loads((directory / "register/jurisdictions.json").read_text("utf-8"))
    assert [j["jurisdiction_id"] for j in jurisdictions["jurisdictions"]] == [
        "greater-eastland",
        "eastland",
    ]
    assert_valid_register(directory)
    assert "Focus areas: Non-alcoholic beverages, Pet food" in out
    assert "Local file sources: feeds" in out


def test_init_copies_the_catalogue_so_it_can_be_edited(home: Path, run: Run) -> None:
    directory = project_dir(home)
    run("init", "--yes", "--dir", str(directory), "--focus", "cosmetics")
    copy = directory / "focus-areas.json"
    data = json.loads(copy.read_text(encoding="utf-8"))
    data["focus_areas"].append(
        {"focus_id": "tea-rooms", "label": "Tea rooms", "terms": ["tea room"]}
    )
    copy.write_text(json.dumps(data), encoding="utf-8")
    assert len(load_catalogue(copy)) == len(load_catalogue()) + 1
    config_path = directory / "regwatch.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace('["cosmetics"]', '["tea-rooms"]'),
        encoding="utf-8",
    )
    code, out, _ = run("--config", str(config_path), "config", "show")
    assert code == 0 and "# focus area tea-rooms: Tea rooms, 1 terms" in out


def test_init_without_example_never_offers_the_invented_jurisdictions(home: Path, run: Run) -> None:
    directory = project_dir(home)
    run("init", "--yes", "--dir", str(directory))
    data = json.loads((directory / "register/jurisdictions.json").read_text("utf-8"))
    assert data == {"jurisdictions": []}


def test_init_example_offers_the_invented_jurisdictions(home: Path, run: Run) -> None:
    directory = project_dir(home)
    code, _, _ = run("init", "--yes", "--example", "--dir", str(directory))
    assert code == 0
    data = json.loads((directory / "register/jurisdictions.json").read_text("utf-8"))
    assert [j["jurisdiction_id"] for j in data["jurisdictions"]] == [
        "nl",
        "nl-east",
        "nl-west",
        "sv",
        "sv-multi",
    ]
    assert_valid_register(directory)
    other = project_dir(home, "other")
    run("init", "--yes", "--example", "--dir", str(other), "--jurisdiction", "Mine")
    assert [
        j["name"]
        for j in json.loads((other / "register/jurisdictions.json").read_text("utf-8"))[
            "jurisdictions"
        ]
    ] == ["Mine"]


def test_init_defaults_to_the_current_directory_when_it_is_not_home(
    home: Path, run: Run, monkeypatch: pytest.MonkeyPatch
) -> None:
    here = project_dir(home)
    here.mkdir()
    monkeypatch.chdir(here)
    assert run("init", "--yes")[0] == 0
    assert (here / "regwatch.toml").is_file()


def test_init_refuses_to_assume_the_home_directory(home: Path, run: Run) -> None:
    code, _, err = run("init", "--yes")
    assert code == 2
    assert "this is your home directory; name the project folder with --dir" in err
    assert not (home / "regwatch.toml").exists()
    code, _, err = run("init", "--yes", "--dir", str(home))
    assert code == 2 and "not the home directory itself" in err
    code, _, err = run("init", "--yes", "--dir", "~")
    assert code == 2 and "not the home directory itself" in err


def test_init_refuses_a_file_as_the_project_directory(home: Path, run: Run) -> None:
    target = home / "taken"
    target.write_text("x", encoding="utf-8")
    code, _, err = run("init", "--yes", "--dir", str(target))
    assert code == 2 and "exists and is not a directory" in err


# --- never overwriting -------------------------------------------------------


def test_init_refuses_to_overwrite_without_force(home: Path, run: Run) -> None:
    directory = project_dir(home)
    assert run("init", "--yes", "--dir", str(directory))[0] == 0
    (directory / "regwatch.toml").write_text("# mine\n", encoding="utf-8")
    code, _, err = run("init", "--yes", "--dir", str(directory), "--focus", "pet-food")
    assert code == 2
    assert "regwatch.toml" in err and "register/obligations.csv" in err
    assert "add --force to replace them" in err
    assert (directory / "regwatch.toml").read_text(encoding="utf-8") == "# mine\n"


def test_init_with_force_replaces_files_and_says_so(home: Path, run: Run) -> None:
    directory = project_dir(home)
    run("init", "--yes", "--dir", str(directory))
    (directory / "register/obligations.csv").write_text("mine\n", encoding="utf-8")
    code, out, _ = run("init", "--yes", "--force", "--dir", str(directory), "--focus", "pet-food")
    assert code == 0
    assert "register/obligations.csv  (replaces an existing file)" in out
    assert read_config(directory)["profile"]["focus_areas"] == ["pet-food"]  # type: ignore[index]
    assert_valid_register(directory)


def test_init_does_not_write_through_a_symbolic_link(home: Path, run: Run) -> None:
    directory = project_dir(home)
    directory.mkdir()
    elsewhere = home / "elsewhere"
    elsewhere.mkdir()
    (directory / "register").symlink_to(elsewhere, target_is_directory=True)
    code, _, err = run("init", "--yes", "--force", "--dir", str(directory))
    assert code == 2 and "is a symbolic link" in err
    assert list(elsewhere.iterdir()) == []

    (directory / "register").unlink()
    victim = home / "victim.txt"
    victim.write_text("keep", encoding="utf-8")
    (directory / "regwatch.toml").symlink_to(victim)
    code, _, err = run("init", "--yes", "--force", "--dir", str(directory))
    assert code == 2 and "is a symbolic link" in err
    assert victim.read_text(encoding="utf-8") == "keep"


def test_init_force_cannot_replace_a_directory(home: Path, run: Run) -> None:
    directory = project_dir(home)
    (directory / "regwatch.toml").mkdir(parents=True)
    code, _, err = run("init", "--yes", "--force", "--dir", str(directory))
    assert code == 2 and "is a directory" in err


# --- bad flag values ---------------------------------------------------------


@pytest.mark.parametrize(
    ("flags", "message"),
    [
        (["--focus", "wine-bar"], "'wine-bar' is not a focus area"),
        (["--focus", "99"], "there is no focus area number 99"),
        (["--contact", "café@example.com"], "printable ASCII"),
        (["--contact", " "], "printable ASCII"),
        (["--allow-file-root", "/"], "too broad"),
        (["--allow-file-root", "~"], "too broad"),
        (["--allow-file-root", " "], "a folder must not be empty"),
        (["--jurisdiction", "!!!"], "no letters or digits"),
        (["--term", "bad\x07term"], "control or invisible"),
        (["--term", "x" * 201], "longer than 200"),
    ],
)
def test_init_rejects_bad_flag_values_and_writes_nothing(
    home: Path, run: Run, flags: list[str], message: str
) -> None:
    directory = project_dir(home)
    code, _, err = run("init", "--yes", "--dir", str(directory), *flags)
    assert code == 2 and message in err
    assert not directory.exists() or list(directory.iterdir()) == []


# --- interactive -------------------------------------------------------------


def test_init_asks_every_question_and_confirms(
    home: Path, run: Run, answers: Callable[..., list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    here = project_dir(home)
    here.mkdir()
    monkeypatch.chdir(here)
    prompts = answers(
        "",  # project folder: accept the current directory
        "1, pet-food",  # focus areas
        "boba, Boba, kombucha",  # extra terms
        "Westmark, Eastmark",  # jurisdictions
        "yes",  # allow local files
        "feeds, /srv/rules",  # folders
        "me@example.com",  # contact
        "y",  # confirm
    )
    code, out, _ = run("init")
    assert code == 0
    assert prompts[0].startswith(f"Project folder [{here.resolve()}]")
    assert "1. non-alcoholic-beverages: Non-alcoholic beverages." in out
    assert "8. cosmetics: Cosmetics." in out
    config = read_config(here)
    assert config["profile"] == {
        "focus_areas": ["non-alcoholic-beverages", "pet-food"],
        "custom_terms": ["boba", "kombucha"],
        "catalogue": "focus-areas.json",
    }
    assert config["fetch"]["allowed_file_roots"] == ["feeds", "/srv/rules"]  # type: ignore[index]
    assert config["fetch"]["user_agent"].endswith("(+me@example.com)")  # type: ignore[index]
    assert_valid_register(here)
    assert "Create these files? [y/N]: " in prompts[-1]


def test_init_defaults_to_no_local_files_and_the_default_agent(
    home: Path, run: Run, answers: Callable[..., list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    here = project_dir(home)
    here.mkdir()
    monkeypatch.chdir(here)
    answers("", "", "", "", "", "", "y")
    code, out, _ = run("init")
    assert code == 0
    assert "Local file sources: not allowed" in out
    assert "User agent: the default" in out
    assert "fetch" not in read_config(here)


def test_init_asks_again_after_an_unusable_answer(
    home: Path, run: Run, answers: Callable[..., list[str]]
) -> None:
    directory = project_dir(home)
    answers(
        str(directory),  # home directory: asked, not assumed
        "99",  # no such focus area
        "wine-bar",  # not in the catalogue
        "3",  # good
        "",  # terms
        "???",  # no letters
        "Northland",  # good
        "y",  # allow files
        "/",  # too broad
        ",",  # no folder named
        "feeds",  # good
        "café",  # not ASCII
        "ops@example.com",  # good
        "y",
    )
    code, out, err = run("init")
    assert code == 0
    assert "You are in your home directory, so regwatch will not assume a project folder." in out
    for message in (
        "there is no focus area number 99",
        "'wine-bar' is not a focus area",
        "no letters or digits",
        "too broad",
        "name at least one folder",
        "printable ASCII",
    ):
        assert message in err
    assert read_config(directory)["profile"]["focus_areas"] == [  # type: ignore[index]
        "cannabis-and-hemp-products"
    ]


def test_init_in_the_home_directory_rejects_an_answer_that_is_home(
    home: Path, run: Run, answers: Callable[..., list[str]]
) -> None:
    directory = project_dir(home)
    answers(str(home), str(directory), "", "", "", "", "", "y")
    code, _, err = run("init")
    assert code == 0 and "not the home directory itself" in err
    assert (directory / "regwatch.toml").is_file()


def test_init_example_default_answer_is_the_example_set(
    home: Path, run: Run, answers: Callable[..., list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    here = project_dir(home)
    here.mkdir()
    monkeypatch.chdir(here)
    prompts = answers("", "", "", "", "", "", "y")
    assert run("init", "--example")[0] == 0
    asked = next(p for p in prompts if p.startswith("Jurisdictions"))
    assert "Enter for the invented example set: Northland, Northland East Region" in asked
    data = json.loads((here / "register/jurisdictions.json").read_text("utf-8"))
    assert len(data["jurisdictions"]) == 5


def test_init_without_example_says_enter_means_none(
    home: Path, run: Run, answers: Callable[..., list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    here = project_dir(home)
    here.mkdir()
    monkeypatch.chdir(here)
    prompts = answers("", "", "", "", "", "", "y")
    run("init")
    asked = next(p for p in prompts if p.startswith("Jurisdictions"))
    assert "Enter for none" in asked and "Northland" not in asked


def test_a_question_with_a_flag_is_not_asked(
    home: Path, run: Run, answers: Callable[..., list[str]]
) -> None:
    directory = project_dir(home)
    prompts = answers("", "y")
    code, _, _ = run(
        "init",
        "--dir",
        str(directory),
        "--focus",
        "pet-food",
        "--jurisdiction",
        "Westmark",
        "--allow-file-root",
        "feeds",
        "--contact",
        "me@example.com",
    )
    assert code == 0
    assert len(prompts) == 2
    assert prompts[0].startswith("Extra words") and prompts[1].startswith("Create these files")


def test_declining_the_confirmation_writes_nothing(
    home: Path, run: Run, answers: Callable[..., list[str]]
) -> None:
    directory = project_dir(home)
    answers("", "", "", "", "", "n")
    code, out, err = run("init", "--dir", str(directory))
    assert code == 2 and "cancelled; nothing was written" in err
    assert "regwatch init will write 7 files" in out
    assert not directory.exists()


def test_init_without_input_explains_how_to_script_it(
    home: Path, run: Run, answers: Callable[..., list[str]]
) -> None:
    answers()
    code, _, err = run("init", "--dir", str(project_dir(home)))
    assert code == 2 and "give each answer as a flag, or add --yes" in err


# --- config show -------------------------------------------------------------


def test_config_show_prints_the_effective_configuration(project: Path, run: Run) -> None:
    code, out, _ = run("--config", str(project), "config", "show")
    assert code == 0
    base = project.parent.resolve()
    assert f'obligations = "{base / "register/obligations.csv"}"' in out
    assert f'dir = "{base / "state"}"' in out
    assert 'user_agent = "regwatch/0.1 (+https://github.com/klappe-pm/regwatch)"' in out
    assert "allowed_file_roots = []" in out
    assert "# no folders are listed, so every file source is refused" in out
    assert 'agencies = ["example-food-agency"]' in out
    assert "cfr_title = 21" in out
    assert "focus_areas = []" in out
    assert 'catalogue = "shipped with regwatch"' in out
    assert "# no focus areas are set, so every candidate counts as in focus" in out
    assert "detail =" in out


def test_config_show_lists_focus_areas_and_file_roots(home: Path, run: Run) -> None:
    directory = project_dir(home)
    run(
        "init",
        "--yes",
        "--dir",
        str(directory),
        "--focus",
        "cosmetics",
        "--focus",
        "infant-food",
        "--term",
        "boba",
        "--allow-file-root",
        "feeds",
        "--contact",
        "me@example.com",
    )
    code, out, _ = run("--config", str(directory / "regwatch.toml"), "config", "show")
    assert code == 0
    assert 'focus_areas = ["cosmetics", "infant-food"]' in out
    assert 'custom_terms = ["boba"]' in out
    assert f'catalogue = "{directory.resolve() / "focus-areas.json"}"' in out
    assert "# focus area cosmetics: Cosmetics, 15 terms" in out
    assert "# focus area infant-food: Infant food, 12 terms" in out
    assert f'allowed_file_roots = ["{directory.resolve() / "feeds"}"]' in out
    assert "every file source is refused" not in out
    assert "(+me@example.com)" in out
    assert "detail =" not in out


def test_config_show_reports_a_bad_profile(project: Path, run: Run) -> None:
    project.write_text(
        project.read_text(encoding="utf-8") + '\n[profile]\nfocus_areas = ["wine-bar"]\n',
        encoding="utf-8",
    )
    code, _, err = run("--config", str(project), "config", "show")
    assert code == 2 and "unknown focus areas: wine-bar" in err


def test_config_needs_an_action(run: Run, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as stopped:
        main(["config"])
    assert stopped.value.code == 2


# --- commands honour the profile --------------------------------------------


def with_profile(project: Path, body: str) -> None:
    project.write_text(
        project.read_text(encoding="utf-8") + "\n[profile]\n" + body, encoding="utf-8"
    )


def test_impact_ranks_by_focus_and_lists_the_rest_under_a_heading(project: Path, run: Run) -> None:
    with_profile(project, 'custom_terms = ["allergen"]\n')
    code, out, _ = run("--config", str(project), "impact")
    assert code == 0
    lines = out.splitlines()
    assert lines[0].split()[1] == "oat-bar"
    heading = next(
        i for i, line in enumerate(lines) if line.startswith("Outside your focus areas (")
    )
    assert heading > 2
    assert "Outside your focus areas (5, listed after the items above):" in out
    assert (
        "regwatch impact: 7 candidate impacts across 3 products; 2 in your focus areas, 5 outside"
        in out
    )
    for title in ("West Region School Food Rule", "Voluntary Colorant Phase-Out"):
        assert title in "\n".join(lines[heading:])


def test_impact_output_is_unchanged_without_a_profile(project: Path, run: Run) -> None:
    code, out, _ = run("--config", str(project), "impact")
    assert code == 0
    assert "Outside your focus areas" not in out
    assert "focus:" not in out
    assert "regwatch impact: 7 candidate impacts across 3 products\n" in out


def test_brief_uses_the_profile(project: Path, run: Run, tmp_path: Path) -> None:
    with_profile(project, 'custom_terms = ["allergen"]\n')
    out_dir = tmp_path / "briefs"
    assert run("--config", str(project), "brief", "--tier", "v2", "--out-dir", str(out_dir))[0] == 0
    text = (out_dir / "regwatch-briefing-v2.md").read_text(encoding="utf-8")
    assert "Outside Your Focus Areas" in text
    assert "West Region School Food Rule" in text
    assert text.index("Allergen Declaration Order") < text.index("Outside Your Focus Areas")
    assert run("--config", str(project), "brief", "--kind", "weekly")[0] == 0
    assert run("--config", str(project), "brief", "--kind", "daily")[0] == 0


# --- config profile parsing --------------------------------------------------


def test_profile_defaults(config_path: Path) -> None:
    profile = load_config(config_path).profile
    assert profile.focus_areas == () and profile.custom_terms == () and profile.catalogue is None


@pytest.fixture
def config_path(project: Path) -> Path:
    return project


def test_profile_is_parsed_and_resolved(project: Path) -> None:
    with_profile(
        project,
        'focus_areas = ["pet-food", "pet-food", "cosmetics"]\ncustom_terms = ["a", "a", "b"]\n'
        'catalogue = "mine.json"\n',
    )
    config = load_config(project)
    assert config.profile.focus_areas == ("pet-food", "cosmetics")
    assert config.profile.custom_terms == ("a", "b")
    assert config.profile.catalogue == project.parent.resolve() / "mine.json"
    assert (project.parent.resolve() / "mine.json") in config.protected_paths()


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ('focus_areas = ["Pet Food"]\n', "identifiers of lowercase letters"),
        ('focus_areas = "pet-food"\n', "must be a list of non-empty strings"),
        ("custom_terms = [1]\n", "must be a list of non-empty strings"),
        ('catalogue = ""\n', "catalogue must be a non-empty string"),
        ('colour = "red"\n', r"\[profile\] has unknown keys: colour"),
    ],
)
def test_profile_errors(project: Path, body: str, message: str) -> None:
    with_profile(project, body)
    with pytest.raises(ConfigError, match=message):
        load_config(project)


# --- helpers -----------------------------------------------------------------


def test_clean_value() -> None:
    assert clean_value("  ok ", "x") == "ok"
    separators = ["a" + chr(0x2028) + "b", "a" + chr(0x202E) + "b"]
    for bad in ("", "  ", "a\tb", *separators, "a\ud800b", "y" * 201):
        with pytest.raises(OnboardingError):
            clean_value(bad, "x")


def test_clean_terms_drops_blanks_and_case_repeats() -> None:
    assert clean_terms(["Tea", " tea ", "", "Chai"]) == ("Tea", "Chai")


def test_check_contact_and_user_agent() -> None:
    assert check_contact(" me@example.com ") == "me@example.com"
    assert user_agent_for("me@example.com") == "regwatch/0.1.0 (+me@example.com)"
    for bad in ("", "é", "a\nb", "x" * 201):
        with pytest.raises(OnboardingError):
            check_contact(bad)


def test_check_directory_and_file_root(home: Path, tmp_path: Path) -> None:
    assert check_directory(str(tmp_path / "new"), home) == (tmp_path / "new").resolve()
    with pytest.raises(OnboardingError):
        check_directory(str(home), home)
    base = tmp_path / "project"
    assert check_file_root("feeds", base, home) == "feeds"
    assert check_file_root("/srv/feeds", base, home) == "/srv/feeds"
    assert check_file_root(".", base, home) == "."
    for bad in ("/", str(home), "~"):
        with pytest.raises(OnboardingError, match="too broad"):
            check_file_root(bad, base, home)
    with pytest.raises(OnboardingError, match="too broad"):
        check_file_root("..", home / "project", home)


def test_parse_focus_choice() -> None:
    catalogue = load_catalogue()
    assert parse_focus_choice(["2", "cosmetics", "2", " ", ""], catalogue) == (
        "alcoholic-beverages",
        "cosmetics",
    )
    assert parse_focus_choice([], catalogue) == ()
    for bad in ("0", "9", "nope"):
        with pytest.raises(OnboardingError):
            parse_focus_choice([bad], catalogue)


def test_jurisdiction_records() -> None:
    records = jurisdiction_records(["North Land", "", "north-land", "North  Land!"])
    assert [r["jurisdiction_id"] for r in records] == ["north-land", "north-land-2", "north-land-3"]
    assert all(r["coverage"] == "tracked" for r in records)
    with pytest.raises(OnboardingError, match="no letters or digits"):
        jurisdiction_records(["!!!"])


def test_example_jurisdictions_are_valid_and_invented() -> None:
    records = example_jurisdictions()
    assert len(records) == 5 and {"nl", "sv-multi"} <= {r["jurisdiction_id"] for r in records}


def test_scaffold_files_refuses_an_answer_that_cannot_be_stored(tmp_path: Path) -> None:
    with pytest.raises(OnboardingError, match="cannot be stored in the configuration"):
        scaffold_files(InitPlan(tmp_path, custom_terms=("\ud800",)))


def test_scaffold_files_names_match_the_constant(tmp_path: Path) -> None:
    assert tuple(scaffold_files(InitPlan(tmp_path))) == SCAFFOLD_NAMES
