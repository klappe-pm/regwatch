"""The register: data model, loading and validation.

The register is the set of files the user curates: obligations (CSV) and the
jurisdiction, category, source and portfolio catalogs (JSON), plus optional
sidecars for human-readable detail, a curated change log, enforcement themes
and impact themes. regwatch reads these files and never writes to them.

Loading always validates first. A register with errors is never half-loaded,
so a typo in a reference cannot silently drop an obligation from an analysis.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from regwatch.config import Config

__all__ = [
    "Category",
    "ChangeEvent",
    "Citation",
    "DetailRecord",
    "Enforcement",
    "EnforcementTheme",
    "Jurisdiction",
    "Obligation",
    "Portfolio",
    "Product",
    "Register",
    "RegisterError",
    "Source",
    "Theme",
    "ancestors",
    "load_register",
    "load_schema",
    "parse_date",
    "split_list",
    "validate_register",
]

MAX_REGISTER_FILE_BYTES = 20_000_000
# Tab, line feed and carriage return are allowed: a CSV cell may hold a line break, and
# every printer turns them into spaces. ESC and the rest of C0, DEL and C1 are refused.
_CONTROL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
JsonObject = dict[str, Any]


class RegisterError(Exception):
    """A register file is unreadable, malformed or fails validation."""

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or [message]


@dataclass(frozen=True)
class Jurisdiction:
    """A place whose rules the register tracks. ``parent`` builds the exposure tree."""

    jurisdiction_id: str
    name: str
    parent: str
    level: str
    coverage: str
    notes: str


@dataclass(frozen=True)
class Category:
    """A named class of regulated attribute that obligations and products share."""

    category_id: str
    label: str
    definition: str


@dataclass(frozen=True)
class Source:
    """A place regwatch reads to detect change."""

    source_id: str
    jurisdiction: str
    name: str
    url: str
    method: str
    mechanism: str
    cadence: str
    notes: str


@dataclass(frozen=True)
class Obligation:
    """One distinct obligation in one jurisdiction."""

    obligation_id: str
    jurisdiction: str
    instrument: str
    citation: str
    title: str
    categories: tuple[str, ...]
    terms: tuple[str, ...]
    claims: tuple[str, ...]
    scope: tuple[str, ...]
    status: str
    effective_date: str
    key_date_note: str
    source_id: str
    source_url: str
    last_reviewed: str
    confidence: str
    notes: str


@dataclass(frozen=True)
class Product:
    """Something the user sells or operates that obligations may touch."""

    product_id: str
    name: str
    kind: str
    categories: tuple[str, ...]
    terms: tuple[str, ...]
    claims: tuple[str, ...]
    markets: tuple[str, ...]
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class Portfolio:
    """The subject of the analysis and its products."""

    name: str
    disclaimer: str
    products: tuple[Product, ...]


@dataclass(frozen=True)
class Citation:
    """A legal citation with an optional link."""

    citation: str
    url: str


@dataclass(frozen=True)
class DetailRecord:
    """Human-written detail for one obligation, used by the tiered briefing."""

    summary: str
    impacts: str
    implications: str
    action: str
    topics: tuple[str, ...]
    citations: tuple[Citation, ...]
    backlinks: tuple[Citation, ...]


@dataclass(frozen=True)
class ChangeEvent:
    """One dated entry in the curated change log."""

    date: str
    jurisdiction: str
    agency: str
    obligation_id: str
    headline: str
    what_happened: str
    citations: tuple[Citation, ...]
    source_url: str


@dataclass(frozen=True)
class EnforcementTheme:
    """A recurring enforcement theme."""

    theme: str
    what_triggers: str
    note: str
    citations: tuple[Citation, ...]


@dataclass(frozen=True)
class Enforcement:
    """Enforcement themes with an optional link to the live enforcement database."""

    reference_url: str
    themes: tuple[EnforcementTheme, ...]


@dataclass(frozen=True)
class Theme:
    """A named lens over impacts, selected by category."""

    key: str
    title: str
    categories: tuple[str, ...]
    why: str
    action: str


@dataclass(frozen=True)
class Register:
    """A fully validated register."""

    delimiter: str
    jurisdictions: tuple[Jurisdiction, ...]
    categories: tuple[Category, ...]
    sources: tuple[Source, ...]
    obligations: tuple[Obligation, ...]
    portfolio: Portfolio
    detail: dict[str, DetailRecord] = field(default_factory=dict)
    changelog: tuple[ChangeEvent, ...] = ()
    enforcement: Enforcement | None = None
    themes: tuple[Theme, ...] = ()


# --- small helpers -----------------------------------------------------------


def parse_date(value: str) -> dt.date | None:
    """Parse an ISO ``YYYY-MM-DD`` date, returning None for anything else."""
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def split_list(value: str, delimiter: str) -> list[str]:
    """Split a delimited cell into trimmed, non-empty items."""
    return [item.strip() for item in (value or "").split(delimiter) if item.strip()]


def load_schema() -> JsonObject:
    """Return the packaged field rules, read through importlib.resources."""
    text = resources.files("regwatch").joinpath("data/schema.json").read_text(encoding="utf-8")
    schema: JsonObject = json.loads(text)
    return schema


def ancestors(jurisdiction_id: str, parents: dict[str, str]) -> list[str]:
    """Return the parent chain of ``jurisdiction_id``, nearest first, stopping on a cycle."""
    chain: list[str] = []
    current = parents.get(jurisdiction_id, "")
    while current and current not in chain and current != jurisdiction_id:
        chain.append(current)
        current = parents.get(current, "")
    return chain


def _read_text(path: Path, label: str) -> str:
    try:
        if path.stat().st_size > MAX_REGISTER_FILE_BYTES:
            raise RegisterError(f"{label} {path} is larger than {MAX_REGISTER_FILE_BYTES} bytes")
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        detail = exc.strerror if isinstance(exc, OSError) and exc.strerror else str(exc)
        raise RegisterError(f"cannot read {label} {path}: {detail}") from exc


def _read_json_object(path: Path, label: str) -> JsonObject:
    text = _read_text(path, label)
    try:
        data = json.loads(text)
    except (ValueError, RecursionError) as exc:
        raise RegisterError(f"{label} {path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise RegisterError(f"{label} {path} must hold a JSON object at the top level")
    return data


def _json_list(data: JsonObject, key: str, label: str) -> list[JsonObject]:
    value = data.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise RegisterError(f"{label} must hold a '{key}' list of objects")
    return value


def _read_obligation_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    text = _read_text(path, "obligations file").lstrip("﻿")
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""))
        header = list(reader.fieldnames or [])
        rows: list[dict[str, str]] = []
        for raw in reader:
            has_surplus = None in raw
            has_gap = any(value is None for key, value in raw.items() if key is not None)
            row = {key: (value or "") for key, value in raw.items() if key is not None}
            if has_surplus or has_gap:
                row["__extra__"] = "1"
            rows.append(row)
    except csv.Error as exc:
        raise RegisterError(f"obligations file {path} is not valid CSV: {exc}") from exc
    return header, rows


# --- validation --------------------------------------------------------------


def _cell_items(rule: JsonObject, raw: Any, delimiter: str) -> list[str] | None:
    """Return the items of a cell, or None when a list was given for a scalar field."""
    if rule.get("list"):
        if isinstance(raw, list):
            return [str(item).strip() for item in raw if str(item).strip()]
        return split_list("" if raw is None else str(raw), delimiter)
    if isinstance(raw, list | dict):
        return None
    text = "" if raw is None else str(raw).strip()
    return [text] if text else []


def _check_item(
    field_name: str, rule: JsonObject, item: str, refs: dict[str, set[str]]
) -> list[str]:
    errors: list[str] = []
    if _CONTROL.search(item):
        return [f"field '{field_name}' contains a control character"]
    enum = rule.get("enum")
    if enum is not None and item not in enum:
        errors.append(f"field '{field_name}' value '{item}' not in {enum}")
    pattern = rule.get("pattern")
    if pattern is not None and not re.fullmatch(pattern, item):
        errors.append(f"field '{field_name}' value '{item}' does not match pattern {pattern}")
    kind = rule.get("type")
    if kind in ("date", "date-or-empty") and parse_date(item) is None:
        errors.append(f"field '{field_name}' value '{item}' is not an ISO date")
    if kind == "url-or-empty" and not _is_url(item, {"https"}):
        errors.append(f"field '{field_name}' value '{item}' is not an https URL")
    if kind == "fetch-url" and not _is_url(item, {"https", "file"}):
        errors.append(f"field '{field_name}' value '{item}' is not an https or file URL")
    ref = rule.get("ref")
    if ref is not None and item not in refs.get(ref, set()):
        errors.append(f"field '{field_name}' references unknown {ref} '{item}'")
    return errors


def _is_url(value: str, schemes: set[str]) -> bool:
    try:
        parts = urlsplit(value)
    except ValueError:
        return False
    return parts.scheme.lower() in schemes and (
        parts.scheme.lower() == "file" or bool(parts.hostname)
    )


def _check_record(
    prefix: str,
    record: JsonObject,
    fields: JsonObject,
    refs: dict[str, set[str]],
    delimiter: str,
) -> list[str]:
    errors: list[str] = []
    for field_name, rule in fields.items():
        items = _cell_items(rule, record.get(field_name), delimiter)
        if items is None:
            errors.append(f"{prefix}: field '{field_name}' must be a single value")
            continue
        if rule.get("required") and not items:
            errors.append(f"{prefix}: field '{field_name}' is required but empty")
            continue
        for item in items:
            errors += [f"{prefix}: {e}" for e in _check_item(field_name, rule, item, refs)]
    return errors


def _check_catalog(
    name: str,
    records: list[JsonObject],
    fields: JsonObject,
    refs: dict[str, set[str]],
    delimiter: str,
    first_row: int = 1,
) -> list[str]:
    errors: list[str] = []
    key = next(name_ for name_, rule in fields.items() if rule.get("unique"))
    seen: set[str] = set()
    for index, record in enumerate(records, start=first_row):
        identifier = str(record.get(key, "") or "")
        prefix = f"{name} entry {index} ({identifier or '?'})"
        if identifier in seen:
            errors.append(f"{prefix}: duplicate {key}")
        seen.add(identifier)
        errors += _check_record(prefix, record, fields, refs, delimiter)
        extra = sorted(set(record) - set(fields) - {"__extra__"})
        if name != "obligations" and extra:
            errors.append(f"{prefix}: unexpected fields {extra}")
    return errors


def _control_errors(label: str, value: object) -> list[str]:
    """One error for each string, in nested JSON, that holds a control character.

    A control character in register text can carry a terminal escape sequence, so
    it is refused. The walk is iterative so deeply nested input cannot exhaust the
    stack.
    """
    errors: list[str] = []
    pending: list[tuple[str, object]] = [(label, value)]
    while pending:
        where, current = pending.pop()
        if isinstance(current, str):
            if _CONTROL.search(current):
                errors.append(f"{where}: contains a control character")
        elif isinstance(current, list):
            pending.extend((f"{where}[{index}]", item) for index, item in enumerate(current))
        elif isinstance(current, dict):
            for key, item in current.items():
                pending.append((f"{where}.{key}", item))
                if _CONTROL.search(str(key)):
                    errors.append(f"{where}: a field name contains a control character")
    return errors


def _check_parents(jurisdictions: list[JsonObject]) -> list[str]:
    parents = {
        str(j.get("jurisdiction_id", "")): str(j.get("parent", "") or "") for j in jurisdictions
    }
    errors: list[str] = []
    for jid, parent in parents.items():
        if parent == jid:
            errors.append(
                f"jurisdictions entry ({jid}): parent must not be the jurisdiction itself"
            )
            continue
        seen = [jid]
        current = parent
        while current:
            if current in seen:
                errors.append(f"jurisdictions entry ({jid}): parent chain contains a cycle")
                break
            seen.append(current)
            current = parents.get(current, "")
    return errors


@dataclass
class _Raw:
    obligation_header: list[str]
    obligations: list[dict[str, str]]
    jurisdictions: list[JsonObject]
    categories: list[JsonObject]
    sources: list[JsonObject]
    portfolio: JsonObject
    products: list[JsonObject]
    detail: JsonObject | None
    changelog: list[JsonObject] | None
    enforcement: JsonObject | None
    themes: list[JsonObject] | None


def _read_raw(config: Config) -> _Raw:
    paths = config.register
    header, rows = _read_obligation_rows(paths.obligations)
    jurisdictions = _json_list(
        _read_json_object(paths.jurisdictions, "jurisdictions file"),
        "jurisdictions",
        "jurisdictions file",
    )
    categories = _json_list(
        _read_json_object(paths.categories, "categories file"), "categories", "categories file"
    )
    sources = _json_list(
        _read_json_object(paths.sources, "sources file"), "sources", "sources file"
    )
    portfolio = _read_json_object(paths.portfolio, "portfolio file")
    products = _json_list(portfolio, "products", "portfolio file")
    detail = _read_json_object(paths.detail, "detail file") if paths.detail else None
    changelog = (
        _json_list(
            _read_json_object(paths.changelog, "change log file"), "events", "change log file"
        )
        if paths.changelog
        else None
    )
    enforcement = (
        _read_json_object(paths.enforcement, "enforcement file") if paths.enforcement else None
    )
    themes = (
        _json_list(_read_json_object(paths.themes, "themes file"), "themes", "themes file")
        if paths.themes
        else None
    )
    return _Raw(
        header,
        rows,
        jurisdictions,
        categories,
        sources,
        portfolio,
        products,
        detail,
        changelog,
        enforcement,
        themes,
    )


def _validate_raw(raw: _Raw) -> list[str]:
    schema = load_schema()
    delimiter = str(schema.get("list_delimiter", ";"))
    refs = {
        "jurisdictions": {str(j.get("jurisdiction_id", "")) for j in raw.jurisdictions},
        "categories": {str(c.get("category_id", "")) for c in raw.categories},
        "sources": {str(s.get("source_id", "")) for s in raw.sources},
    }
    errors: list[str] = []
    errors += _check_catalog(
        "jurisdictions", raw.jurisdictions, schema["jurisdiction_fields"], refs, delimiter
    )
    errors += _check_parents(raw.jurisdictions)
    errors += _check_catalog(
        "categories", raw.categories, schema["category_fields"], refs, delimiter
    )
    errors += _check_catalog("sources", raw.sources, schema["source_fields"], refs, delimiter)
    errors += _check_catalog("products", raw.products, schema["product_fields"], refs, delimiter)

    fields: JsonObject = schema["obligation_fields"]
    missing_columns = [name for name in fields if name not in raw.obligation_header]
    if missing_columns:
        errors.append(f"obligations header is missing columns {missing_columns}")
    unexpected = sorted(set(raw.obligation_header) - set(fields))
    if unexpected:
        errors.append(f"obligations header has unexpected columns {unexpected}")
    rows: list[JsonObject] = [dict(row) for row in raw.obligations]
    errors += _check_catalog("obligations", rows, fields, refs, delimiter, first_row=2)
    for index, row in enumerate(rows, start=2):
        if row.get("__extra__"):
            errors.append(f"obligations entry {index}: row has more or fewer cells than the header")

    obligation_ids = {row.get("obligation_id", "") for row in raw.obligations}
    errors += _validate_sidecars(raw, obligation_ids, refs)
    errors += _control_errors(
        "portfolio file", {key: v for key, v in raw.portfolio.items() if key != "products"}
    )
    for label, value in (
        ("detail file", raw.detail),
        ("change log file", raw.changelog),
        ("enforcement file", raw.enforcement),
        ("themes file", raw.themes),
    ):
        if value is not None:
            errors += _control_errors(label, value)
    return errors


def _require_text(prefix: str, record: JsonObject, keys: Iterable[str]) -> list[str]:
    return [
        f"{prefix}: field '{key}' is required but empty"
        for key in keys
        if not str(record.get(key, "") or "").strip()
    ]


def _check_citations(prefix: str, record: JsonObject, key: str, url_key: str) -> list[str]:
    value = record.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        return [f"{prefix}: field '{key}' must be a list of objects"]
    errors: list[str] = []
    label_key = "citation" if key == "citations" else "label"
    for item in value:
        if not str(item.get(label_key, "")).strip():
            errors.append(f"{prefix}: each entry in '{key}' needs a '{label_key}'")
        url = str(item.get(url_key, "") or "")
        if url and not _is_url(url, {"https"}):
            errors.append(f"{prefix}: '{key}' url '{url}' is not an https URL")
    return errors


def _validate_sidecars(raw: _Raw, obligation_ids: set[str], refs: dict[str, set[str]]) -> list[str]:
    errors: list[str] = []
    if raw.detail is not None:
        records = raw.detail.get("detail")
        vocabulary = raw.detail.get("topics_vocabulary", [])
        if not isinstance(records, dict) or not all(isinstance(v, dict) for v in records.values()):
            errors.append("detail file must hold a 'detail' object keyed by obligation_id")
        else:
            vocab = set(vocabulary) if isinstance(vocabulary, list) else set()
            for oid, info in records.items():
                prefix = f"detail '{oid}'"
                if oid not in obligation_ids:
                    errors.append(f"{prefix}: not a known obligation_id")
                errors += _require_text(
                    prefix, info, ("summary", "impacts", "implications", "action")
                )
                topics = info.get("topics", [])
                if not isinstance(topics, list):
                    errors.append(f"{prefix}: field 'topics' must be a list")
                elif vocab:
                    errors += [
                        f"{prefix}: topic '{t}' not in topics_vocabulary"
                        for t in topics
                        if t not in vocab
                    ]
                errors += _check_citations(prefix, info, "citations", "url")
                errors += _check_citations(prefix, info, "backlinks", "url")
    if raw.changelog is not None:
        for index, event in enumerate(raw.changelog, start=1):
            prefix = f"changelog entry {index}"
            if parse_date(str(event.get("date", ""))) is None:
                errors.append(f"{prefix}: date '{event.get('date', '')}' is not an ISO date")
            errors += _require_text(prefix, event, ("headline",))
            jurisdiction = str(event.get("jurisdiction", "") or "")
            if jurisdiction and jurisdiction not in refs["jurisdictions"]:
                errors.append(
                    f"{prefix}: jurisdiction '{jurisdiction}' is not a known jurisdiction"
                )
            oid = str(event.get("obligation_id", "") or "")
            if oid and oid not in obligation_ids:
                errors.append(f"{prefix}: obligation_id '{oid}' is not a known obligation")
            errors += _check_citations(prefix, event, "citations", "url")
    if raw.enforcement is not None:
        themes = raw.enforcement.get("themes", [])
        if not isinstance(themes, list) or not all(isinstance(t, dict) for t in themes):
            errors.append("enforcement file must hold a 'themes' list of objects")
        else:
            for index, theme in enumerate(themes, start=1):
                prefix = f"enforcement theme {index}"
                errors += _require_text(prefix, theme, ("theme", "what_triggers"))
                errors += _check_citations(prefix, theme, "citations", "url")
    if raw.themes is not None:
        keys: set[str] = set()
        for index, theme in enumerate(raw.themes, start=1):
            prefix = f"theme {index}"
            errors += _require_text(prefix, theme, ("key", "title", "why", "action"))
            key = str(theme.get("key", ""))
            if key in keys:
                errors.append(f"{prefix}: duplicate key '{key}'")
            keys.add(key)
            categories = theme.get("categories", [])
            if not isinstance(categories, list) or not categories:
                errors.append(f"{prefix}: field 'categories' must be a non-empty list")
            else:
                errors += [
                    f"{prefix}: references unknown categories '{c}'"
                    for c in categories
                    if c not in refs["categories"]
                ]
    return errors


def validate_register(config: Config) -> list[str]:
    """Return every validation error in the register, or an empty list when it is valid.

    Raises RegisterError when a file cannot be read or parsed at all.
    """
    return _validate_raw(_read_raw(config))


# --- building ----------------------------------------------------------------


def _s(record: JsonObject | dict[str, str], key: str) -> str:
    value = record.get(key, "")
    return "" if value is None else str(value).strip()


def _t(record: JsonObject | dict[str, str], key: str, delimiter: str) -> tuple[str, ...]:
    items = _cell_items({"list": True}, record.get(key), delimiter) or []
    return tuple(items)


def _citations(record: JsonObject, key: str, label_key: str) -> tuple[Citation, ...]:
    return tuple(
        Citation(_s(item, label_key), _s(item, "url")) for item in record.get(key, []) or []
    )


def _build(raw: _Raw, delimiter: str) -> Register:
    jurisdictions = tuple(
        Jurisdiction(
            _s(j, "jurisdiction_id"),
            _s(j, "name"),
            _s(j, "parent"),
            _s(j, "level"),
            _s(j, "coverage"),
            _s(j, "notes"),
        )
        for j in raw.jurisdictions
    )
    categories = tuple(
        Category(_s(c, "category_id"), _s(c, "label"), _s(c, "definition")) for c in raw.categories
    )
    sources = tuple(
        Source(
            _s(s, "source_id"),
            _s(s, "jurisdiction"),
            _s(s, "name"),
            _s(s, "url"),
            _s(s, "method"),
            _s(s, "mechanism"),
            _s(s, "cadence"),
            _s(s, "notes"),
        )
        for s in raw.sources
    )
    obligations = tuple(
        Obligation(
            obligation_id=_s(o, "obligation_id"),
            jurisdiction=_s(o, "jurisdiction"),
            instrument=_s(o, "instrument"),
            citation=_s(o, "citation"),
            title=_s(o, "title"),
            categories=_t(o, "categories", delimiter),
            terms=_t(o, "terms", delimiter),
            claims=_t(o, "claims", delimiter),
            scope=_t(o, "scope", delimiter),
            status=_s(o, "status"),
            effective_date=_s(o, "effective_date"),
            key_date_note=_s(o, "key_date_note"),
            source_id=_s(o, "source_id"),
            source_url=_s(o, "source_url"),
            last_reviewed=_s(o, "last_reviewed"),
            confidence=_s(o, "confidence"),
            notes=_s(o, "notes"),
        )
        for o in raw.obligations
    )
    products = tuple(
        Product(
            _s(p, "product_id"),
            _s(p, "name"),
            _s(p, "kind"),
            _t(p, "categories", delimiter),
            _t(p, "terms", delimiter),
            _t(p, "claims", delimiter),
            _t(p, "markets", delimiter),
            _t(p, "scopes", delimiter),
        )
        for p in raw.products
    )
    portfolio = Portfolio(
        _s(raw.portfolio, "name") or "Portfolio", _s(raw.portfolio, "disclaimer"), products
    )

    detail: dict[str, DetailRecord] = {}
    if raw.detail is not None:
        for oid, info in raw.detail.get("detail", {}).items():
            detail[oid] = DetailRecord(
                _s(info, "summary"),
                _s(info, "impacts"),
                _s(info, "implications"),
                _s(info, "action"),
                _t(info, "topics", delimiter),
                _citations(info, "citations", "citation"),
                _citations(info, "backlinks", "label"),
            )
    changelog = tuple(
        ChangeEvent(
            _s(e, "date"),
            _s(e, "jurisdiction"),
            _s(e, "agency"),
            _s(e, "obligation_id"),
            _s(e, "headline"),
            _s(e, "what_happened"),
            _citations(e, "citations", "citation"),
            _s(e, "source_url"),
        )
        for e in (raw.changelog or [])
    )
    enforcement = None
    if raw.enforcement is not None:
        enforcement = Enforcement(
            _s(raw.enforcement, "reference_url"),
            tuple(
                EnforcementTheme(
                    _s(t, "theme"),
                    _s(t, "what_triggers"),
                    _s(t, "note"),
                    _citations(t, "citations", "citation"),
                )
                for t in raw.enforcement.get("themes", [])
            ),
        )
    themes = tuple(
        Theme(
            _s(t, "key"),
            _s(t, "title"),
            _t(t, "categories", delimiter),
            _s(t, "why"),
            _s(t, "action"),
        )
        for t in (raw.themes or [])
    )
    return Register(
        delimiter,
        jurisdictions,
        categories,
        sources,
        obligations,
        portfolio,
        detail,
        changelog,
        enforcement,
        themes,
    )


def load_register(config: Config) -> Register:
    """Read, validate and build the register described by ``config``.

    Raises RegisterError, carrying every validation message in ``errors``, when
    any file is unreadable or the register is invalid.
    """
    raw = _read_raw(config)
    errors = _validate_raw(raw)
    if errors:
        raise RegisterError(f"the register has {len(errors)} validation error(s)", errors)
    return _build(raw, str(load_schema().get("list_delimiter", ";")))
