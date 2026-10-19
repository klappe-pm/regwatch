"""Flatten the register into one record per obligation for spreadsheets and analysis."""

from __future__ import annotations

import csv
import io

from regwatch.register import Register

__all__ = ["FORMULA_STARTS", "RECORD_COLUMNS", "build_records", "neutralise_cell", "records_csv"]

RECORD_COLUMNS = (
    "obligation_id",
    "jurisdiction",
    "status",
    "effective_date",
    "topics",
    "summary",
    "impacts",
    "implications",
    "action",
    "source_url",
    "citations",
)


def build_records(register: Register) -> list[dict[str, str]]:
    """Return one normalized record per obligation, joined with its detail record when it has one."""
    delimiter = register.delimiter
    records: list[dict[str, str]] = []
    for obligation in register.obligations:
        info = register.detail.get(obligation.obligation_id)
        backlink = info.backlinks[0].url if info and info.backlinks else ""
        records.append(
            {
                "obligation_id": obligation.obligation_id,
                "jurisdiction": obligation.jurisdiction,
                "status": obligation.status,
                "effective_date": obligation.effective_date,
                "topics": delimiter.join(info.topics) if info else "",
                "summary": info.summary if info else "",
                "impacts": info.impacts if info else "",
                "implications": info.implications if info else "",
                "action": info.action if info else "",
                "source_url": backlink or obligation.source_url,
                "citations": delimiter.join(c.citation for c in info.citations) if info else "",
            }
        )
    return records


FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def neutralise_cell(value: str) -> str:
    """Prefix an apostrophe to a cell a spreadsheet would read as a formula.

    A cell that starts with ``=``, ``+``, ``-``, ``@``, a tab or a carriage return
    would be executed by a spreadsheet program, so it gets a leading apostrophe,
    which the program hides and treats as text.
    """
    return "'" + value if value.startswith(FORMULA_STARTS) else value


def records_csv(records: list[dict[str, str]]) -> str:
    """Return ``records`` as CSV text with a header row, with formula cells neutralised."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(RECORD_COLUMNS), lineterminator="\n")
    writer.writeheader()
    writer.writerows(
        {key: neutralise_cell(value) for key, value in record.items()} for record in records
    )
    return buffer.getvalue()
