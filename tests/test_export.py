from __future__ import annotations

import csv
import dataclasses
import io

from regwatch.export import RECORD_COLUMNS, build_records, records_csv
from regwatch.register import Register


def test_records_join_detail_when_present(register: Register) -> None:
    records = {r["obligation_id"]: r for r in build_records(register)}
    assert len(records) == 7
    order = records["nl-allergen-order"]
    assert order["jurisdiction"] == "nl"
    assert order["topics"] == "allergens"
    assert order["summary"].startswith("Requires a plain statement")
    assert order["citations"] == "Northland Allergen Declaration Order"
    assert order["source_url"] == "https://regulator.nl.example/orders/allergen"
    assert set(order) == set(RECORD_COLUMNS)


def test_records_without_detail_use_the_register_row(register: Register) -> None:
    bill = next(
        r for r in build_records(register) if r["obligation_id"] == "nl-east-sweetener-bill"
    )
    assert bill["summary"] == ""
    assert bill["topics"] == ""
    assert bill["source_url"] == "https://gazette.east.nl.example/bills/14"
    assert bill["effective_date"] == ""


def test_backlink_wins_over_the_register_url(register: Register) -> None:
    guidance = next(
        r for r in build_records(register) if r["obligation_id"] == "nl-colorant-guidance"
    )
    assert guidance["source_url"] == "https://regulator.nl.example/guidance/colorants"
    assert guidance["topics"] == "colorants;claims"


def test_topics_use_the_register_delimiter(register: Register) -> None:
    custom = dataclasses.replace(register, delimiter="|")
    guidance = next(
        r for r in build_records(custom) if r["obligation_id"] == "nl-colorant-guidance"
    )
    assert guidance["topics"] == "colorants|claims"


def test_csv_has_header_and_roundtrips(register: Register) -> None:
    records = build_records(register)
    text = records_csv(records)
    assert text.splitlines()[0] == ",".join(RECORD_COLUMNS)
    assert "\r" not in text
    assert list(csv.DictReader(io.StringIO(text))) == records


def test_csv_quotes_commas_and_newlines() -> None:
    row = {column: "" for column in RECORD_COLUMNS}
    row["summary"] = 'has, comma and "quote"\nand newline'
    parsed = list(csv.DictReader(io.StringIO(records_csv([row]))))
    assert parsed[0]["summary"] == row["summary"]
