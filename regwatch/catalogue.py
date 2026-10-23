"""The source catalogue: sources a user can choose to watch, and the one search ranking.

The catalogue is package data, ``regwatch/data/source-catalogue.json``, and a user
may add an extra file of their own (``[catalogue] extra`` in ``regwatch.toml``).
Both are validated by the same strict rules: unknown keys are errors, identifiers
are unique across both files, every value is from its allowed set, a keyed source
names where its key goes, and every address passes the fetch client's URL checks.

Choosing a source copies its entry into the user's own sources file, which stays
the only list ``capture`` and ``check`` read. The catalogue is never read during a
run. Everything here is pure apart from reading package data and the extra file.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from regwatch.fetch import FetchError, check_url
from regwatch.keys import KEY_ENV_RE, KEY_ENV_RULE, shared_key_errors

__all__ = [
    "ACCESS",
    "ACCESS_LABELS",
    "CADENCES",
    "CATEGORIES",
    "FIELDS",
    "KINDS",
    "MECHANISMS",
    "REGIONS",
    "Auth",
    "CatalogueEntry",
    "CatalogueError",
    "MergeResult",
    "entry_from_dict",
    "entry_to_source",
    "filter_entries",
    "jurisdiction_name",
    "load_source_catalogue",
    "merge_sources",
    "parse_source_catalogue",
    "rank",
]

CATALOGUE_RESOURCE = "data/source-catalogue.json"
NAMES_RESOURCE = "data/jurisdiction-names.json"
MAX_CATALOGUE_BYTES = 5_000_000
MAX_DESCRIPTION = 160
MAX_TEXT = 200
MAX_NOTES = 300

FIELDS = (
    "source_id",
    "name",
    "publisher",
    "jurisdiction",
    "region",
    "kind",
    "category",
    "mechanism",
    "url",
    "homepage",
    "access",
    "auth",
    "key_env",
    "signup_url",
    "focus_areas",
    "language",
    "cadence",
    "description",
    "verified",
    "checked",
    "notes",
)
REGIONS = (
    "north-america",
    "latin-america",
    "europe",
    "asia-pacific",
    "middle-east-africa",
    "global",
)
KINDS = (
    "regulator",
    "legislature",
    "gazette",
    "court",
    "standards",
    "recalls",
    "data-portal",
    "news",
    "industry",
    "aggregator",
    "lobbying-disclosure",
    "interest-group",
    "supplier",
    "market-data",
    "forecast",
)
CATEGORIES = (
    "regulation",
    "policy-and-lobbying",
    "ingredients-supply",
    "packaging-materials",
    "commodities-and-forecasts",
    "manufacturing-and-chemicals",
    "logistics-and-trade",
    "construction-and-facilities",
    "industry-news",
)
MECHANISMS = ("rss", "api", "html", "email-list", "manual")
ACCESS = ("free", "free-key", "paid")
ACCESS_LABELS = {"free": "Free", "free-key": "Free Key", "paid": "Paid"}
CADENCES = ("hourly", "daily", "weekly")
AUTH_TYPES = ("query", "header")

SOURCE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
JURISDICTION_RE = re.compile(r"^(?:intl|eu|[a-z]{2}(?:-[a-z0-9]{1,3})?)$")
AUTH_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
LANGUAGE_RE = re.compile(r"^[a-z]{2}$")
_INVISIBLE = frozenset({"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"})
_WORD = re.compile(r"[a-z0-9]+")


class CatalogueError(Exception):
    """The source catalogue is unreadable or invalid, or a choice cannot be applied."""


@dataclass(frozen=True)
class Auth:
    """Where a keyed source takes its key: a query parameter or a request header."""

    type: str
    name: str

    def to_text(self) -> str:
        """The ``type:name`` form stored in a sources file."""
        return f"{self.type}:{self.name}"


@dataclass(frozen=True)
class CatalogueEntry:
    """One source in the catalogue."""

    source_id: str
    name: str
    publisher: str
    jurisdiction: str
    region: str
    kind: str
    category: str
    mechanism: str
    url: str
    homepage: str
    access: str
    auth: Auth | None
    key_env: str | None
    signup_url: str | None
    focus_areas: tuple[str, ...]
    language: str
    cadence: str
    description: str
    verified: bool
    checked: str
    notes: str | None

    @property
    def access_label(self) -> str:
        """``Free``, ``Free Key`` or ``Paid``."""
        return ACCESS_LABELS[self.access]

    @property
    def keyed(self) -> bool:
        """True when a request to this source carries a key."""
        return self.auth is not None

    def to_dict(self) -> dict[str, Any]:
        """The entry as JSON data, with the access label added for display."""
        data: dict[str, Any] = {name: getattr(self, name) for name in FIELDS}
        data["auth"] = (
            None if self.auth is None else {"type": self.auth.type, "name": self.auth.name}
        )
        data["focus_areas"] = list(self.focus_areas)
        data["access_label"] = self.access_label
        return data


# --- validation ----------------------------------------------------------------


def _text(value: object, field: str, limit: int, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"'{field}' must be a non-empty string")
        return ""
    text = value.strip()
    if len(text) > limit:
        errors.append(f"'{field}' is longer than {limit} characters")
    if any(unicodedata.category(ch) in _INVISIBLE for ch in text):
        errors.append(f"'{field}' must not contain control or invisible characters")
    return text


def _choice(value: object, field: str, allowed: Sequence[str], errors: list[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        errors.append(f"'{field}' must be one of {', '.join(allowed)}")
        return ""
    return value


def _pattern(value: object, field: str, pattern: re.Pattern[str], errors: list[str]) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        errors.append(f"'{field}' has an invalid value")
        return ""
    return value


def _https(value: object, field: str, errors: list[str]) -> str:
    if not isinstance(value, str):
        errors.append(f"'{field}' must be an https URL")
        return ""
    try:
        scheme = check_url(value)
    except FetchError as exc:
        errors.append(f"'{field}' is refused by the fetch client: {exc}")
        return ""
    if scheme != "https":
        errors.append(f"'{field}' must be an https URL")
        return ""
    return value


def entry_from_dict(data: object, focus_ids: Iterable[str], where: str = "entry") -> CatalogueEntry:
    """Validate one decoded entry and build it. Raises CatalogueError listing every problem."""
    if not isinstance(data, dict):
        raise CatalogueError(f"{where} must be an object")
    errors: list[str] = []
    unknown = sorted(set(data) - set(FIELDS))
    if unknown:
        errors.append(f"unknown keys: {', '.join(unknown)}")
    missing = [name for name in FIELDS if name not in data]
    if missing:
        errors.append(f"missing keys: {', '.join(missing)}")
    if errors:
        raise CatalogueError(f"{where}: {'; '.join(errors)}")

    source_id = _pattern(data["source_id"], "source_id", SOURCE_ID_RE, errors)
    if source_id and len(source_id) > 80:
        errors.append("'source_id' is longer than 80 characters")
    access = _choice(data["access"], "access", ACCESS, errors)

    auth: Auth | None = None
    raw_auth = data["auth"]
    if raw_auth is not None:
        if not isinstance(raw_auth, dict) or set(raw_auth) != {"type", "name"}:
            errors.append("'auth' must be null or an object with exactly 'type' and 'name'")
        else:
            auth = Auth(
                _choice(raw_auth["type"], "auth.type", AUTH_TYPES, errors),
                _pattern(raw_auth["name"], "auth.name", AUTH_NAME_RE, errors),
            )
    key_env = data["key_env"]
    if key_env is not None and (not isinstance(key_env, str) or not KEY_ENV_RE.fullmatch(key_env)):
        errors.append(f"'key_env' must be {KEY_ENV_RULE}")
        key_env = ""
    signup_url = data["signup_url"]
    if signup_url is not None:
        signup_url = _https(signup_url, "signup_url", errors)

    if (auth is None) != (data["key_env"] is None):
        errors.append("'auth' and 'key_env' must both be set or both be null")
    if access == "free-key" and (auth is None or data["key_env"] is None or signup_url is None):
        errors.append("a free-key source must have 'auth', 'key_env' and 'signup_url'")
    if access == "free" and auth is not None:
        errors.append("a free source must not have 'auth'; use access 'free-key'")

    focus_known = set(focus_ids)
    raw_focus = data["focus_areas"]
    focus: tuple[str, ...] = ()
    if not isinstance(raw_focus, list) or not all(isinstance(f, str) for f in raw_focus):
        errors.append("'focus_areas' must be a list of focus area ids")
    else:
        unknown_focus = [f for f in raw_focus if f not in focus_known]
        if unknown_focus:
            errors.append(f"'focus_areas' names unknown focus areas: {', '.join(unknown_focus)}")
        if len(set(raw_focus)) != len(raw_focus):
            errors.append("'focus_areas' repeats an id")
        focus = tuple(raw_focus)

    verified = data["verified"]
    if not isinstance(verified, bool):
        errors.append("'verified' must be true or false")
    checked = data["checked"]
    try:
        if not isinstance(checked, str) or len(checked) != 10:
            raise ValueError
        dt.date.fromisoformat(checked)
    except ValueError:
        errors.append("'checked' must be a date written YYYY-MM-DD")
    notes = data["notes"]
    if notes is not None:
        notes = _text(notes, "notes", MAX_NOTES, errors)

    entry = CatalogueEntry(
        source_id=source_id,
        name=_text(data["name"], "name", MAX_TEXT, errors),
        publisher=_text(data["publisher"], "publisher", MAX_TEXT, errors),
        jurisdiction=_pattern(data["jurisdiction"], "jurisdiction", JURISDICTION_RE, errors),
        region=_choice(data["region"], "region", REGIONS, errors),
        kind=_choice(data["kind"], "kind", KINDS, errors),
        category=_choice(data["category"], "category", CATEGORIES, errors),
        mechanism=_choice(data["mechanism"], "mechanism", MECHANISMS, errors),
        url=_https(data["url"], "url", errors),
        homepage=_https(data["homepage"], "homepage", errors),
        access=access,
        auth=auth,
        key_env=key_env if isinstance(key_env, str) and key_env else None,
        signup_url=signup_url if isinstance(signup_url, str) and signup_url else None,
        focus_areas=focus,
        language=_pattern(data["language"], "language", LANGUAGE_RE, errors),
        cadence=_choice(data["cadence"], "cadence", CADENCES, errors),
        description=_text(data["description"], "description", MAX_DESCRIPTION, errors),
        verified=bool(verified),
        checked=str(checked),
        notes=notes or None,
    )
    if errors:
        raise CatalogueError(f"{where} ({data.get('source_id', '?')}): {'; '.join(errors)}")
    return entry


def parse_source_catalogue(
    data: object, focus_ids: Iterable[str], label: str = "the source catalogue"
) -> tuple[CatalogueEntry, ...]:
    """Validate a decoded catalogue file and return its entries in file order.

    Raises CatalogueError naming every invalid entry.
    """
    if not isinstance(data, dict) or set(data) != {"version", "sources"}:
        raise CatalogueError(f"{label} must hold exactly 'version' and 'sources'")
    if data["version"] != 1 or isinstance(data["version"], bool):
        raise CatalogueError(f"{label} has an unsupported version; regwatch reads version 1")
    if not isinstance(data["sources"], list):
        raise CatalogueError(f"{label}: 'sources' must be a list")
    focus = tuple(focus_ids)
    entries: list[CatalogueEntry] = []
    errors: list[str] = []
    seen: set[str] = set()
    for index, raw in enumerate(data["sources"], start=1):
        try:
            entry = entry_from_dict(raw, focus, f"{label} entry {index}")
        except CatalogueError as exc:
            errors.append(str(exc))
            continue
        if entry.source_id in seen:
            errors.append(f"{label} entry {index}: duplicate source_id '{entry.source_id}'")
            continue
        seen.add(entry.source_id)
        entries.append(entry)
    errors += [f"{label}: {message}" for message in _key_conflicts(entries)]
    if errors:
        raise CatalogueError("; ".join(errors))
    return tuple(entries)


def _key_conflicts(entries: Iterable[CatalogueEntry]) -> list[str]:
    return shared_key_errors(
        (entry.source_id, entry.key_env, entry.url) for entry in entries if entry.key_env
    )


def _read(path: Path, label: str) -> object:
    try:
        if path.stat().st_size > MAX_CATALOGUE_BYTES:
            raise CatalogueError(f"{label} is larger than {MAX_CATALOGUE_BYTES} bytes")
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        detail = exc.strerror if isinstance(exc, OSError) and exc.strerror else str(exc)
        raise CatalogueError(f"cannot read {label}: {detail}") from exc
    try:
        return json.loads(text)
    except (ValueError, RecursionError) as exc:
        raise CatalogueError(f"{label} is not valid JSON: {exc}") from exc


def load_source_catalogue(
    focus_ids: Iterable[str], extra: Path | None = None
) -> tuple[CatalogueEntry, ...]:
    """The shipped catalogue followed by the entries of the user's ``extra`` file, if any.

    Both files follow the same rules, and an id may appear only once across them.
    """
    focus = tuple(focus_ids)
    text = resources.files("regwatch").joinpath(CATALOGUE_RESOURCE).read_text(encoding="utf-8")
    entries = list(parse_source_catalogue(json.loads(text), focus, "the shipped source catalogue"))
    if extra is not None:
        label = f"source catalogue {extra}"
        added = parse_source_catalogue(_read(extra, label), focus, label)
        known = {entry.source_id for entry in entries}
        clashes = [entry.source_id for entry in added if entry.source_id in known]
        if clashes:
            raise CatalogueError(
                f"{label} repeats ids of the shipped catalogue: {', '.join(clashes)}"
            )
        conflicts = _key_conflicts([*entries, *added])
        if conflicts:
            raise CatalogueError(f"{label}: {'; '.join(conflicts)}")
        entries += added
    return tuple(entries)


# --- search and filters --------------------------------------------------------


# British spellings and the American ones they are searched as, so a search for
# either finds both. Each key is a word start; the rest of the word is kept, so
# "labelling" becomes "labeling" and "flavours" becomes "flavors".
SPELLINGS = {
    "aluminium": "aluminum",
    "labell": "label",
    "flavour": "flavor",
    "colour": "color",
    "odour": "odor",
    "fibre": "fiber",
    "centre": "center",
    "organis": "organiz",
    "authoris": "authoriz",
    "harmonis": "harmoniz",
    "standardis": "standardiz",
    "sulph": "sulf",
    "programme": "program",
    "catalogue": "catalog",
    "licence": "license",
    "defence": "defense",
}
# How much a match in each field counts. The id, the jurisdiction, the kind, the
# region, the category and the focus areas are matched by their hyphen-separated parts.
SEARCH_WEIGHTS = {
    "name": 4,
    "source_id": 3,
    "publisher": 3,
    "jurisdiction": 2,
    "kind": 2,
    "access_label": 2,
    "region": 1,
    "category": 1,
    "focus_areas": 1,
    "description": 1,
}
# Within one match quality, a publisher's own official sources come before the rest.
_KIND_TIERS = {
    "regulator": 0,
    "legislature": 0,
    "gazette": 0,
    "court": 0,
    "recalls": 1,
    "lobbying-disclosure": 1,
    "data-portal": 1,
    "standards": 1,
}
_ACRONYM_SKIP = frozenset(
    {"and", "of", "the", "for", "de", "du", "des", "la", "le", "et", "on", "in"}
)
SHORT_TOKEN = 2
"""A query word this short (such as ``ca``) matches only a whole word or id part."""


def _spelling(word: str) -> str:
    for british, american in SPELLINGS.items():
        if word.startswith(british):
            return american + word[len(british) :]
    return word


def _words(text: str) -> list[str]:
    return [_spelling(word) for word in _WORD.findall(text.lower())]


def _acronym(text: str) -> str:
    """The initials of a publisher's name: U.S. Food and Drug Administration is ``fda``."""
    parts = [w for w in _WORD.findall(text.lower()) if len(w) > 1 and w not in _ACRONYM_SKIP]
    return "".join(part[0] for part in parts) if len(parts) > 1 else ""


def _search_fields(entry: CatalogueEntry) -> list[tuple[list[str], int]]:
    acronym = _acronym(entry.publisher)
    values = {
        "name": _words(entry.name),
        "source_id": _words(entry.source_id),
        "publisher": _words(entry.publisher) + ([acronym] if acronym else []),
        "jurisdiction": _words(entry.jurisdiction),
        "kind": _words(entry.kind),
        "access_label": _words(entry.access_label),
        "region": _words(entry.region),
        "category": _words(entry.category),
        "focus_areas": [word for area in entry.focus_areas for word in _words(area)],
        "description": _words(entry.description),
    }
    return [(values[name], weight) for name, weight in SEARCH_WEIGHTS.items()]


def _match(token: str, words: Sequence[str]) -> int:
    """3 for a whole word, 2 for the start of a word, 1 inside a word, 0 for none."""
    if token in words:
        return 3
    if len(token) <= SHORT_TOKEN:
        return 0
    if any(word.startswith(token) for word in words):
        return 2
    return 1 if any(token in word for word in words) else 0


def rank(entries: Sequence[CatalogueEntry], text: str) -> list[CatalogueEntry]:
    """Entries that match ``text``, best first. The one ranking every surface uses.

    The match is case-insensitive over the name, id, publisher (and the initials
    of its name), jurisdiction, kind, access label, region, category, focus areas
    and description, with British and American spellings treated alike. Every
    word of the query must match somewhere. A query word of one or two letters
    matches only a whole word or a part of an id or code, so ``ca`` finds
    ``us-ca`` and not Canada's "Cancer". An entry whose id or jurisdiction equals
    the whole query comes first, its official sources (regulators, legislatures,
    gazettes and courts) before the rest. Otherwise entries are ordered by how
    well each word matches (a whole word above the start of a word above a match
    inside a word), then by the weighted sum of the fields it matches in
    (``SEARCH_WEIGHTS``), then official sources first. Ties keep catalogue order.
    An empty query returns every entry in catalogue order.
    """
    query = text.strip().lower()
    if not query:
        return list(entries)
    tokens = [_spelling(token) for token in _WORD.findall(query)]
    scored: list[tuple[tuple[int, ...], CatalogueEntry]] = []
    for index, entry in enumerate(entries):
        exact = 0 if query in (entry.source_id, entry.jurisdiction) else 1
        fields = _search_fields(entry)
        quality = 0
        weighted = 0
        matched = True
        for token in tokens:
            levels = [_match(token, words) for words, _weight in fields]
            quality += max(levels)
            weighted += sum(
                level * weight for level, (_w, weight) in zip(levels, fields, strict=True)
            )
            matched = matched and max(levels) > 0
        if exact and (not tokens or not matched):
            continue
        tier = _KIND_TIERS.get(entry.kind, 2)
        key = (
            (exact, tier, -quality, -weighted, index)
            if exact == 0
            else (exact, -quality, -weighted, tier, index)
        )
        scored.append((key, entry))
    scored.sort(key=lambda item: item[0])
    return [entry for _key, entry in scored]


def _in_jurisdiction(entry: CatalogueEntry, jurisdiction: str) -> bool:
    return entry.jurisdiction == jurisdiction or entry.jurisdiction.startswith(f"{jurisdiction}-")


def filter_entries(
    entries: Iterable[CatalogueEntry],
    *,
    region: str | None = None,
    jurisdiction: str | None = None,
    kind: str | None = None,
    category: str | None = None,
    access: str | None = None,
    focus: str | None = None,
    chosen: Iterable[str] | None = None,
) -> list[CatalogueEntry]:
    """The entries that pass every filter given.

    ``jurisdiction`` also matches its subdivisions (``us`` matches ``us-ca``),
    ``focus`` matches an entry that lists the area or lists none (which means
    every area), and ``chosen`` keeps only the ids it holds.
    """
    picked = None if chosen is None else set(chosen)
    found: list[CatalogueEntry] = []
    for entry in entries:
        if region and entry.region != region:
            continue
        if jurisdiction and not _in_jurisdiction(entry, jurisdiction):
            continue
        if kind and entry.kind != kind:
            continue
        if category and entry.category != category:
            continue
        if access and entry.access != access:
            continue
        if focus and entry.focus_areas and focus not in entry.focus_areas:
            continue
        if picked is not None and entry.source_id not in picked:
            continue
        found.append(entry)
    return found


# --- choosing sources ------------------------------------------------------------


def _names() -> Mapping[str, str]:
    text = resources.files("regwatch").joinpath(NAMES_RESOURCE).read_text(encoding="utf-8")
    names: dict[str, str] = json.loads(text)["names"]
    return names


def jurisdiction_name(code: str) -> str:
    """A readable name for a catalogue jurisdiction code; the code itself when none is known."""
    return _names().get(code, code.upper())


def entry_to_source(entry: CatalogueEntry, jurisdiction_id: str | None = None) -> dict[str, str]:
    """The sources file entry for a chosen catalogue entry.

    ``jurisdiction_id`` replaces the catalogue code when the user's register
    already names that jurisdiction with another id.
    """
    source = {
        "source_id": entry.source_id,
        "jurisdiction": jurisdiction_id or entry.jurisdiction,
        "name": entry.name,
        "url": entry.url,
        "method": "subscribe" if entry.mechanism == "email-list" else "poll",
        "mechanism": entry.mechanism,
        "cadence": entry.cadence,
        "notes": entry.description,
    }
    if entry.auth is not None and entry.key_env is not None:
        source["auth"] = entry.auth.to_text()
        source["key_env"] = entry.key_env
    return source


@dataclass(frozen=True)
class MergeResult:
    """The new sources and jurisdictions lists, and what changed."""

    sources: list[dict[str, Any]]
    jurisdictions: list[dict[str, Any]]
    added: tuple[str, ...]
    present: tuple[str, ...]
    added_jurisdictions: tuple[str, ...]


def _resolve_jurisdiction(code: str, jurisdictions: list[dict[str, Any]], added: list[str]) -> str:
    """The register id for ``code``, adding a tracked record (and its parent) when missing."""
    by_id = {str(j.get("jurisdiction_id", "")) for j in jurisdictions}
    if code in by_id:
        return code
    name = jurisdiction_name(code)
    for existing in jurisdictions:
        if str(existing.get("name", "")).strip().casefold() == name.casefold():
            return str(existing.get("jurisdiction_id", ""))
    record: dict[str, Any] = {"jurisdiction_id": code, "name": name, "coverage": "tracked"}
    parent = code.split("-", 1)[0] if "-" in code else ""
    if parent:
        record["parent"] = _resolve_jurisdiction(parent, jurisdictions, added)
    jurisdictions.append(record)
    added.append(code)
    return code


def merge_sources(
    sources: Sequence[Mapping[str, Any]],
    jurisdictions: Sequence[Mapping[str, Any]],
    entries: Sequence[CatalogueEntry],
) -> MergeResult:
    """Add ``entries`` to a sources list, adding any jurisdiction they need.

    An entry already present with the same content is left alone. An existing
    source with the same id but different content is never overwritten: the
    whole merge is refused with CatalogueError, so nothing is half applied.
    """
    new_sources = [dict(source) for source in sources]
    new_jurisdictions = [dict(record) for record in jurisdictions]
    by_id = {str(source.get("source_id", "")): source for source in new_sources}
    added: list[str] = []
    present: list[str] = []
    added_jurisdictions: list[str] = []
    conflicts: list[str] = []
    for entry in entries:
        if entry.source_id in added:
            continue
        trial = list(new_jurisdictions)
        jurisdiction_id = _resolve_jurisdiction(entry.jurisdiction, trial, [])
        wanted = entry_to_source(entry, jurisdiction_id)
        existing = by_id.get(entry.source_id)
        if existing is not None:
            if dict(existing) == wanted:
                present.append(entry.source_id)
            else:
                conflicts.append(entry.source_id)
            continue
        _resolve_jurisdiction(entry.jurisdiction, new_jurisdictions, added_jurisdictions)
        new_sources.append(wanted)
        by_id[entry.source_id] = wanted
        added.append(entry.source_id)
    if conflicts:
        raise CatalogueError(
            "the sources file already has a different entry with the id "
            f"{', '.join(conflicts)}; remove it first or edit the file by hand"
        )
    return MergeResult(
        new_sources,
        new_jurisdictions,
        tuple(added),
        tuple(present),
        tuple(added_jurisdictions),
    )
