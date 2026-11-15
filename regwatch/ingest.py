"""Candidate ingest from a Federal Register style API.

The Federal Register API is public and reports, for every document, the title,
abstract, publication date, link and the Code of Federal Regulations references
it amends. This module turns a response into candidate change log events.
Candidates are always flagged unconfirmed: the feed says what was published, a
person decides whether it matters and copies it into the curated change log.

The response is untrusted. It is parsed as JSON only, every field is type
checked and truncated, links are kept only when they use https, and a document
that does not have the expected shape is skipped rather than guessed at.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from typing import Any
from urllib.parse import urlencode

from regwatch.config import IngestSettings
from regwatch.sanitize import clean_text, safe_https_url

__all__ = ["IngestError", "build_query_url", "candidates_document", "parse_candidates"]

FIELDS = (
    "title",
    "abstract",
    "publication_date",
    "html_url",
    "document_number",
    "type",
    "cfr_references",
    "agencies",
)
MAX_DOCUMENTS = 1000
_DIGITS = re.compile(r"^[0-9]{1,4}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9._-]{1,40}$")


class IngestError(ValueError):
    """The ingest response is not usable."""


def build_query_url(settings: IngestSettings, since: str) -> str:
    """Return the API URL for documents published on or after ``since`` (ISO date)."""
    try:
        dt.date.fromisoformat(since)
    except ValueError as exc:
        raise IngestError(f"'{since}' is not an ISO date") from exc
    pairs: list[tuple[str, str]] = [("per_page", str(settings.per_page)), ("order", "newest")]
    pairs += [("conditions[type][]", kind) for kind in settings.types]
    pairs += [("conditions[agencies][]", agency) for agency in settings.agencies]
    pairs.append(("conditions[publication_date][gte]", since))
    pairs += [("fields[]", name) for name in FIELDS]
    return f"{settings.api_url}?{urlencode(pairs)}"


def _number(value: Any) -> str:
    if isinstance(value, bool):
        return ""
    text = str(value) if isinstance(value, int | str) else ""
    return text if _DIGITS.fullmatch(text) else ""


def _citations(document: dict[str, Any]) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    references = document.get("cfr_references")
    for ref in references if isinstance(references, list) else []:
        if not isinstance(ref, dict):
            continue
        title, part = _number(ref.get("title")), _number(ref.get("part"))
        if not title or not part:
            continue
        citation = f"{title} CFR {part}"
        if citation not in seen:
            seen.add(citation)
            found.append(
                {
                    "citation": citation,
                    "url": f"https://www.ecfr.gov/current/title-{title}/part-{part}",
                }
            )
    return found


def _text(value: Any, limit: int) -> str:
    """A field as one clean line: no control or escape characters, cut to ``limit``."""
    return clean_text(value, limit) if isinstance(value, str) else ""


def _https(value: Any) -> str:
    """A link only when it is a plain https link; see ``safe_https_url``."""
    return safe_https_url(value)


def _identifier(value: Any) -> str:
    """A document number: letters, digits, dots, hyphens and underscores only."""
    text = clean_text(value) if isinstance(value, str) else ""
    return text if _IDENTIFIER.fullmatch(text) else ""


def _is_relevant(document: dict[str, Any], settings: IngestSettings) -> bool:
    if not settings.cfr_parts and not settings.terms:
        return True
    references = document.get("cfr_references")
    for ref in references if isinstance(references, list) else []:
        if not isinstance(ref, dict):
            continue
        title, part = _number(ref.get("title")), _number(ref.get("part"))
        title_ok = settings.cfr_title is None or title == str(settings.cfr_title)
        if title_ok and part and int(part) in settings.cfr_parts:
            return True
    haystack = (
        f"{_text(document.get('title'), 2000)} {_text(document.get('abstract'), 5000)}".lower()
    )
    return any(term in haystack for term in settings.terms)


def _agency(document: dict[str, Any]) -> str:
    agencies = document.get("agencies")
    if isinstance(agencies, list) and agencies and isinstance(agencies[0], dict):
        return _text(agencies[0].get("name"), 120)
    return ""


def parse_candidates(
    json_text: str, settings: IngestSettings, today: dt.date
) -> list[dict[str, Any]]:
    """Turn an API response into unconfirmed candidate events, newest first.

    Raises IngestError when the text is not JSON or does not have a ``results`` list.
    """
    try:
        data = json.loads(json_text)
    except (ValueError, RecursionError) as exc:
        raise IngestError(f"response is not valid JSON: {exc}") from exc
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        raise IngestError("response has no 'results' list")
    candidates: list[dict[str, Any]] = []
    for document in results[:MAX_DOCUMENTS]:
        if not isinstance(document, dict) or not _is_relevant(document, settings):
            continue
        kind = _text(document.get("type"), 40) or "Document"
        title = _text(document.get("title"), 200)
        published = _text(document.get("publication_date"), 10)
        candidates.append(
            {
                "date": published if re.fullmatch(r"\d{4}-\d{2}-\d{2}", published) else "",
                "jurisdiction": settings.jurisdiction,
                "agency": _agency(document),
                "obligation_id": None,
                "headline": f"{kind}: {title}",
                "what_happened": _text(document.get("abstract") or document.get("title"), 320),
                "citations": _citations(document),
                "source_url": _https(document.get("html_url")),
                "document_number": _identifier(document.get("document_number")),
                "type": kind,
                "needs_review": True,
                "confidence": "unconfirmed",
                "detected": today.isoformat(),
            }
        )
    candidates.sort(key=lambda c: c["date"], reverse=True)
    return candidates


def candidates_document(
    candidates: list[dict[str, Any]], today: dt.date, origin: str
) -> dict[str, Any]:
    """Wrap candidates with provenance for writing to the state directory."""
    return {
        "version": "0.1.0",
        "generated": today.isoformat(),
        "origin": origin,
        "note": (
            "Unconfirmed candidates from the feed. A person confirms each one and copies it "
            "into the curated change log by hand. regwatch never edits the change log. "
            "Not legal advice."
        ),
        "candidates": candidates,
    }
