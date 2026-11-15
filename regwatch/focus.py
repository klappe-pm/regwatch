"""Focus areas: the part of the regulatory world that matters to this user's business.

A focus area is a named set of terms, such as the words that describe one kind of
product. The shipped catalogue is package data and can be replaced by a copy that
the user edits. A profile is the chosen areas plus any custom terms. It decides
which candidates are listed first. It never removes one: a candidate that matches
no focus area is listed afterwards, under its own heading.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

from regwatch.config import FOCUS_ID_RE, ProfileSettings
from regwatch.register import DetailRecord, Obligation, Product

__all__ = [
    "CUSTOM_TERMS_KEY",
    "FocusArea",
    "FocusError",
    "FocusProfile",
    "build_profile",
    "load_catalogue",
    "parse_catalogue",
    "shipped_catalogue_text",
]

CUSTOM_TERMS_KEY = "custom-terms"
MAX_CATALOGUE_BYTES = 1_000_000
CATALOGUE_RESOURCE = "data/focus-areas.json"


class FocusError(Exception):
    """The focus catalogue is unreadable or invalid, or the profile names an unknown area."""


@dataclass(frozen=True)
class FocusArea:
    """One entry of the catalogue."""

    focus_id: str
    label: str
    description: str
    terms: tuple[str, ...]


@lru_cache(maxsize=1024)
def _pattern(term: str) -> re.Pattern[str]:
    """Match ``term`` as whole words, allowing a plural ending, in lower-cased text."""
    return re.compile(r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?:e?s)?(?![a-z0-9])")


def _mentions(terms: Iterable[str], haystack: str) -> bool:
    return any(_pattern(term).search(haystack) for term in terms)


@dataclass(frozen=True)
class FocusProfile:
    """The chosen focus areas and custom terms.

    A profile with neither is inactive: it matches nothing and every candidate is
    treated as in focus, so a user who sets no focus areas sees no change.
    """

    areas: tuple[FocusArea, ...] = ()
    custom_terms: tuple[str, ...] = ()

    @property
    def active(self) -> bool:
        """True when at least one area or custom term is set."""
        return bool(self.areas or self.custom_terms)

    def names(self) -> list[str]:
        """The label of every chosen area, then ``custom terms`` when there are any."""
        names = [area.label for area in self.areas]
        if self.custom_terms:
            names.append("custom terms")
        return names

    def matches(self, *texts: str) -> tuple[str, ...]:
        """Identifiers of the areas whose terms appear in ``texts``, in profile order.

        Custom terms report as ``CUSTOM_TERMS_KEY``. Matching is by whole word,
        without regard to case, and a plural ending is allowed.
        """
        haystack = "\n".join(texts).lower()
        found = [area.focus_id for area in self.areas if _mentions(area.terms, haystack)]
        if _mentions(self.custom_terms, haystack):
            found.append(CUSTOM_TERMS_KEY)
        return tuple(found)

    def match_obligation(
        self, obligation: Obligation, detail: DetailRecord | None = None
    ) -> tuple[str, ...]:
        """Focus matches for an obligation, read from its title, terms, claims and notes."""
        texts = [
            obligation.title,
            obligation.citation,
            obligation.notes,
            *obligation.categories,
            *obligation.terms,
            *obligation.claims,
        ]
        if detail is not None:
            texts += [detail.summary, detail.impacts, *detail.topics]
        return self.matches(*texts)

    def match_product(self, product: Product) -> tuple[str, ...]:
        """Focus matches for a product, read from its name, kind, terms and claims."""
        return self.matches(
            product.name, product.kind, *product.categories, *product.terms, *product.claims
        )

    def match_candidate(self, candidate: Mapping[str, Any]) -> tuple[str, ...]:
        """Focus matches for an unconfirmed ingest candidate, read from its headline and text."""
        texts = [candidate.get("headline"), candidate.get("what_happened")]
        return self.matches(*(text for text in texts if isinstance(text, str)))


def shipped_catalogue_text() -> str:
    """The shipped catalogue file, read through importlib.resources."""
    return resources.files("regwatch").joinpath(CATALOGUE_RESOURCE).read_text(encoding="utf-8")


def _text_field(entry: Mapping[str, Any], key: str, where: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise FocusError(f"{where}: '{key}' must be a non-empty string")
    return value.strip()


def parse_catalogue(data: object, label: str = "the focus catalogue") -> tuple[FocusArea, ...]:
    """Validate a decoded catalogue and return its areas.

    Raises FocusError for a wrong shape, a duplicate or malformed identifier, or
    an area with no terms.
    """
    if not isinstance(data, dict) or not isinstance(data.get("focus_areas"), list):
        raise FocusError(f"{label} must hold a 'focus_areas' list")
    areas: list[FocusArea] = []
    seen: set[str] = set()
    for index, entry in enumerate(data["focus_areas"], start=1):
        where = f"{label} entry {index}"
        if not isinstance(entry, dict):
            raise FocusError(f"{where} must be an object")
        unknown = sorted(set(entry) - {"focus_id", "label", "description", "terms"})
        if unknown:
            raise FocusError(f"{where} has unknown keys: {', '.join(unknown)}")
        focus_id = _text_field(entry, "focus_id", where)
        if not FOCUS_ID_RE.fullmatch(focus_id):
            raise FocusError(
                f"{where}: focus_id '{focus_id}' must use lowercase letters, digits and hyphens"
            )
        if focus_id in seen:
            raise FocusError(f"{where}: duplicate focus_id '{focus_id}'")
        seen.add(focus_id)
        terms = entry.get("terms")
        if (
            not isinstance(terms, list)
            or not terms
            or not all(isinstance(t, str) and t.strip() for t in terms)
        ):
            raise FocusError(f"{where}: 'terms' must be a non-empty list of non-empty strings")
        description = entry.get("description", "")
        if not isinstance(description, str):
            raise FocusError(f"{where}: 'description' must be a string")
        areas.append(
            FocusArea(
                focus_id,
                _text_field(entry, "label", where),
                description.strip(),
                tuple(dict.fromkeys(t.strip().lower() for t in terms)),
            )
        )
    return tuple(areas)


def load_catalogue(path: Path | None = None) -> tuple[FocusArea, ...]:
    """Load the catalogue at ``path``, or the shipped one when ``path`` is None.

    Raises FocusError when the file cannot be read or fails validation.
    """
    if path is None:
        text, label = shipped_catalogue_text(), "the shipped focus catalogue"
    else:
        label = f"focus catalogue {path}"
        try:
            if path.stat().st_size > MAX_CATALOGUE_BYTES:
                raise FocusError(f"{label} is larger than {MAX_CATALOGUE_BYTES} bytes")
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            detail = exc.strerror if isinstance(exc, OSError) and exc.strerror else str(exc)
            raise FocusError(f"cannot read {label}: {detail}") from exc
    try:
        data = json.loads(text)
    except (ValueError, RecursionError) as exc:
        raise FocusError(f"{label} is not valid JSON: {exc}") from exc
    return parse_catalogue(data, label)


def build_profile(settings: ProfileSettings) -> FocusProfile:
    """Resolve the chosen area identifiers against the catalogue.

    Raises FocusError when an identifier is not in the catalogue.
    """
    if not settings.focus_areas and not settings.custom_terms:
        return FocusProfile()
    by_id = {area.focus_id: area for area in load_catalogue(settings.catalogue)}
    unknown = [focus_id for focus_id in settings.focus_areas if focus_id not in by_id]
    if unknown:
        raise FocusError(
            f"unknown focus areas: {', '.join(unknown)}; the catalogue offers {', '.join(by_id)}"
        )
    return FocusProfile(
        tuple(by_id[focus_id] for focus_id in settings.focus_areas),
        tuple(term.lower() for term in settings.custom_terms),
    )
