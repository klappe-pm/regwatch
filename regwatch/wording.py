"""Plain wording for the sentences regwatch builds: counts, lists, dates and labels.

Every count in a fixed sentence goes through ``count``, so no sentence says
"source(s)", and a summary is built from its non-zero clauses only, joined with
commas and a final "and". Dates in prose read "15 November 2026", and a period
reads "20 to 26 October".
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from regwatch.register import parse_date

__all__ = [
    "MONTHS",
    "PROVIDER_NAMES",
    "SEVERITY_LABELS",
    "count",
    "date_range",
    "join_clauses",
    "long_date",
    "number",
    "prose_date",
    "provider_name",
    "severity_label",
    "status_phrase",
]

_SMALL = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
SEVERITY_LABELS = {"act-now": "act now", "high": "high", "watch": "watch", "info": "information"}
PROVIDER_NAMES = {"anthropic": "Anthropic", "openai": "OpenAI", "ollama": "Ollama"}


def number(n: int) -> str:
    """``n`` as a reader expects it in a sentence: words up to nine, digits from 10."""
    return _SMALL[n] if 0 < n < len(_SMALL) else ("none" if n == 0 else str(n))


def count(n: int, one: str, many: str | None = None) -> str:
    """``n`` with the noun in the right number: "one source", "12 sources", "no sources".

    Zero to nine are written as words. ``many`` is the plural when adding "s" is wrong.
    """
    noun = one if n == 1 else (many if many is not None else f"{one}s")
    word = _SMALL[n] if 0 <= n < len(_SMALL) else str(n)
    return f"{word} {noun}"


def join_clauses(clauses: Sequence[str]) -> str:
    """The non-empty clauses joined with commas and a final "and"."""
    kept = [clause for clause in clauses if clause]
    if len(kept) <= 1:
        return "".join(kept)
    return f"{', '.join(kept[:-1])} and {kept[-1]}"


def long_date(day: dt.date) -> str:
    """A date in prose: "15 November 2026"."""
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


def prose_date(value: str) -> str:
    """``value`` as a prose date when it is a valid ISO date, otherwise unchanged."""
    day = parse_date(value)
    return long_date(day) if day is not None else value


def date_range(start: dt.date, end: dt.date) -> str:
    """A period in prose: "20 to 26 October", "28 September to 4 October", and the years
    when the period crosses one: "28 December 2026 to 3 January 2027". One day is that day."""
    if start == end:
        return long_date(start)
    if start.year != end.year:
        return f"{long_date(start)} to {long_date(end)}"
    if start.month != end.month:
        return f"{start.day} {MONTHS[start.month - 1]} to {end.day} {MONTHS[end.month - 1]}"
    return f"{start.day} to {end.day} {MONTHS[end.month - 1]}"


def severity_label(severity: str) -> str:
    """A severity as a reader says it: "act now", not "act-now"."""
    return SEVERITY_LABELS.get(severity, severity)


def provider_name(provider: str) -> str:
    """A provider's own name: "Anthropic", "OpenAI", "Ollama"."""
    return PROVIDER_NAMES.get(provider, provider)


def status_phrase(status: str, detail: str = "") -> str:
    """What a source check found, in words."""
    if status == "NEW":
        return "first snapshot taken"
    if status == "CHANGED":
        return "content changed"
    if status == "MISSING":
        return "no snapshot yet"
    if status == "ERROR":
        return f"could not be read ({detail})" if detail else "could not be read"
    if status == "SUSPICIOUS":
        return f"looks wrong ({detail})" if detail else "looks wrong"
    if status == "UNCHANGED":
        return "unchanged"
    return status.lower()
