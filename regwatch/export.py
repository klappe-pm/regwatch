"""Flatten the register into one record per obligation for spreadsheets and analysis."""

from __future__ import annotations

import csv
import io
import re
import unicodedata

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


FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r", "\n")
_FORMULA_CHARS = frozenset("=+-@")
_SEPARATORS = ";,\t\r\n"
_SPLIT = re.compile(f"([{re.escape(_SEPARATORS)}])")


def _starts_formula(segment: str) -> bool:
    """True when a spreadsheet would read ``segment`` as a formula.

    Leading whitespace and invisible format characters are skipped, because a
    spreadsheet skips them too. A fullwidth ``=`` and its relatives count, because
    they fold to the ASCII character under NFKC.
    """
    for char in segment:
        if char.isspace() or unicodedata.category(char) == "Cf":
            continue
        return unicodedata.normalize("NFKC", char) in _FORMULA_CHARS
    return False


def neutralise_cell(value: str) -> str:
    """Prefix an apostrophe to every part of a cell a spreadsheet would read as a formula.

    A cell is read as a formula when it starts with ``=``, ``+``, ``-``, ``@``, a
    tab, a carriage return or a line feed, also after leading whitespace or
    invisible format characters, and also in the fullwidth forms. Spreadsheet
    programs in many locales split a line on ``;`` as well as ``,``, and a tab or
    a line break can start a new cell too, so the same test is applied to the text
    after each of those separators. A part that would be a formula gets a leading
    apostrophe, which the program hides and treats as text.
    """
    if value.startswith(("\t", "\r", "\n")):
        value = "'" + value
    parts = _SPLIT.split(value)
    for index in range(0, len(parts), 2):
        if _starts_formula(parts[index]):
            parts[index] = "'" + parts[index]
    return "".join(parts)


def records_csv(records: list[dict[str, str]]) -> str:
    """Return ``records`` as CSV text with a header row.

    Every field is quoted, and formula cells are neutralised, including the parts
    of a cell that follow a ``;``, a ``,``, a tab or a line break.
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=list(RECORD_COLUMNS), lineterminator="\n", quoting=csv.QUOTE_ALL
    )
    writer.writeheader()
    writer.writerows(
        {key: neutralise_cell(value) for key, value in record.items()} for record in records
    )
    return buffer.getvalue()
