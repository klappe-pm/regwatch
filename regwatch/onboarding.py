"""Onboarding: the files that ``regwatch init`` creates and the checks on the answers.

Everything here is a pure function over already collected answers, apart from
reading package data and asking the file system what a path resolves to. Asking
the questions and printing belong to the command line layer. The scaffold is a
configuration file, an empty register that validates, and a copy of the focus
catalogue that the user can edit.
"""

from __future__ import annotations

import json
import re
import tomllib
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from regwatch import __version__
from regwatch.catalogue import CatalogueEntry, jurisdiction_name, merge_sources
from regwatch.config import DEFAULT_CONFIG_NAME, file_root_is_too_broad
from regwatch.focus import FocusArea, shipped_catalogue_text
from regwatch.register import load_schema

__all__ = [
    "CATALOGUE_NAME",
    "SCAFFOLD_NAMES",
    "InitPlan",
    "OnboardingError",
    "check_contact",
    "check_directory",
    "check_file_root",
    "clean_terms",
    "clean_value",
    "example_jurisdictions",
    "jurisdiction_records",
    "matching_entries",
    "parse_focus_choice",
    "scaffold_files",
    "user_agent_for",
]

CATALOGUE_NAME = "focus-areas.json"
SCAFFOLD_NAMES = (
    DEFAULT_CONFIG_NAME,
    "register/obligations.csv",
    "register/jurisdictions.json",
    "register/categories.json",
    "register/sources.json",
    "register/portfolio.json",
    CATALOGUE_NAME,
)
MAX_VALUE_LENGTH = 200
# Control, format, surrogate, private use and unassigned characters, and line and paragraph
# separators.
INVISIBLE_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"})
CONTACT_RE = re.compile(r"[ -~]{1,200}")


class OnboardingError(ValueError):
    """An answer to an onboarding question is not usable. The message says why."""


@dataclass(frozen=True)
class InitPlan:
    """Everything ``regwatch init`` will write, as collected from the answers."""

    directory: Path
    focus_areas: tuple[str, ...] = ()
    custom_terms: tuple[str, ...] = ()
    jurisdictions: tuple[dict[str, str], ...] = ()
    file_roots: tuple[str, ...] = ()
    contact: str = ""
    sources: tuple[CatalogueEntry, ...] = ()


def clean_value(value: str, what: str) -> str:
    """Return ``value`` trimmed.

    Raise OnboardingError if it is empty, long or has control characters.
    """
    text = value.strip()
    if not text:
        raise OnboardingError(f"{what} must not be empty")
    if len(text) > MAX_VALUE_LENGTH:
        raise OnboardingError(f"{what} is longer than {MAX_VALUE_LENGTH} characters")
    if any(unicodedata.category(ch) in INVISIBLE_CATEGORIES for ch in text):
        raise OnboardingError(f"{what} must not contain control or invisible characters")
    return text


def clean_terms(values: Iterable[str]) -> tuple[str, ...]:
    """Trim and check custom terms, dropping blanks and repeats that differ only in case."""
    seen: dict[str, str] = {}
    for value in values:
        if value.strip():
            term = clean_value(value, "a custom term")
            seen.setdefault(term.lower(), term)
    return tuple(seen.values())


def check_contact(value: str) -> str:
    """Check the text placed after ``regwatch/<version> (+`` in the User-Agent header."""
    text = value.strip()
    if not CONTACT_RE.fullmatch(text):
        raise OnboardingError(
            f"the contact must be 1 to {MAX_VALUE_LENGTH} printable ASCII characters, "
            "such as an email address or a web page"
        )
    return text


def user_agent_for(contact: str) -> str:
    """The User-Agent header that names this tool, its version and a contact."""
    return f"regwatch/{__version__} (+{contact})"


def check_directory(value: str, home: Path) -> Path:
    """Return the project directory for ``value``, refusing the home directory itself."""
    path = Path(clean_value(value, "the project directory")).expanduser().resolve()
    if path == home.resolve():
        raise OnboardingError(
            "the project directory must be a folder inside your home directory, "
            "not the home directory itself"
        )
    if path.exists() and not path.is_dir():
        raise OnboardingError(f"{path} exists and is not a directory")
    return path


def check_file_root(value: str, base: Path, home: Path) -> str:
    """Check a folder that file sources may be read from. Returns the text to store.

    A relative folder is resolved against ``base``, the project directory, exactly
    as the configuration loader does. The root of a file system and the home
    directory are refused because they would allow almost any file to be read.
    """
    text = clean_value(value, "a folder")
    candidate = Path(text).expanduser()
    resolved = (candidate if candidate.is_absolute() else base / candidate).resolve()
    if file_root_is_too_broad(resolved, home):
        raise OnboardingError(
            f"{text} is too broad; name the folder that holds the files, "
            "not a file system root, your home directory or a folder that contains it"
        )
    return text


def parse_focus_choice(tokens: Sequence[str], catalogue: Sequence[FocusArea]) -> tuple[str, ...]:
    """Turn identifiers or one-based list numbers into catalogue identifiers.

    Raises OnboardingError for a token that is neither a number in range nor an
    identifier in the catalogue. Repeats are dropped and order is kept.
    """
    by_id = {area.focus_id for area in catalogue}
    chosen: list[str] = []
    for raw in tokens:
        token = raw.strip()
        if not token:
            continue
        if token.isdecimal():
            index = int(token)
            if not 1 <= index <= len(catalogue):
                raise OnboardingError(f"there is no focus area number {token}")
            focus_id = catalogue[index - 1].focus_id
        elif token in by_id:
            focus_id = token
        else:
            raise OnboardingError(f"'{token}' is not a focus area in the catalogue")
        if focus_id not in chosen:
            chosen.append(focus_id)
    return tuple(chosen)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def jurisdiction_records(names: Iterable[str]) -> tuple[dict[str, str], ...]:
    """Build one tracked jurisdiction record per name, with an identifier made from the name.

    Raises OnboardingError when a name has no letters or digits to make an
    identifier from. Two names that give the same identifier get a numeric suffix.
    """
    records: list[dict[str, str]] = []
    used: set[str] = set()
    for raw in names:
        if not raw.strip():
            continue
        name = clean_value(raw, "a jurisdiction")
        base = _slug(name)
        if not base:
            raise OnboardingError(f"'{name}' has no letters or digits to make an identifier from")
        identifier, number = base, 2
        while identifier in used:
            identifier, number = f"{base}-{number}", number + 1
        used.add(identifier)
        records.append({"jurisdiction_id": identifier, "name": name, "coverage": "tracked"})
    return tuple(records)


def _serves_jurisdiction(entry: CatalogueEntry, jurisdictions: Sequence[dict[str, str]]) -> bool:
    if not jurisdictions or entry.jurisdiction == "intl":
        return True
    code = entry.jurisdiction
    parent = code.split("-", 1)[0]
    keys = {code, parent, jurisdiction_name(code).casefold(), jurisdiction_name(parent).casefold()}
    return any(
        record.get("jurisdiction_id", "") in keys or record.get("name", "").casefold() in keys
        for record in jurisdictions
    )


def matching_entries(
    entries: Iterable[CatalogueEntry],
    focus_areas: Sequence[str],
    jurisdictions: Sequence[dict[str, str]],
) -> list[CatalogueEntry]:
    """The catalogue entries that fit the chosen focus areas and jurisdictions.

    An entry fits a focus when it lists one of the areas or lists none (which
    means every area). It fits a jurisdiction when its code, the country above a
    subdivision, or the name of either matches a chosen jurisdiction's id or name;
    international entries always fit. With no focus or no jurisdiction chosen,
    that filter keeps everything.
    """
    chosen = set(focus_areas)
    return [
        entry
        for entry in entries
        if (not chosen or not entry.focus_areas or chosen & set(entry.focus_areas))
        and _serves_jurisdiction(entry, jurisdictions)
    ]


def example_jurisdictions() -> tuple[dict[str, str], ...]:
    """The invented jurisdictions that ``regwatch init --example`` offers.

    They are read from package data.
    """
    path = resources.files("regwatch").joinpath("data/example-jurisdictions.json")
    return tuple(json.loads(path.read_text(encoding="utf-8"))["jurisdictions"])


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _toml_list(values: Iterable[str]) -> str:
    return "[" + ", ".join(_toml_string(v) for v in values) + "]"


def _config_text(plan: InitPlan) -> str:
    lines = [
        "# regwatch configuration, created by 'regwatch init'.",
        "# Every path is relative to this file. docs/reference/configuration.md lists every key.",
        "",
        "[register]",
        'obligations = "register/obligations.csv"',
        'jurisdictions = "register/jurisdictions.json"',
        'categories = "register/categories.json"',
        'sources = "register/sources.json"',
        'portfolio = "register/portfolio.json"',
        "",
        "[state]",
        'dir = "state"',
        "",
        "[profile]",
        "# Focus areas rank the candidates that matter to your business ahead of the rest.",
        "# Nothing is dropped: candidates that match no focus area are listed afterwards.",
        f"focus_areas = {_toml_list(plan.focus_areas)}",
        f"custom_terms = {_toml_list(plan.custom_terms)}",
        f"catalogue = {_toml_string(CATALOGUE_NAME)}",
    ]
    fetch: list[str] = []
    if plan.contact:
        fetch.append(f"user_agent = {_toml_string(user_agent_for(plan.contact))}")
    if plan.file_roots:
        fetch.append(f"allowed_file_roots = {_toml_list(plan.file_roots)}")
    if fetch:
        lines += ["", "[fetch]", *fetch]
    return "\n".join(lines) + "\n"


def scaffold_files(plan: InitPlan) -> dict[str, str]:
    """Return the text of every file to create, keyed by path relative to the project directory.

    Raises OnboardingError if the generated configuration is not valid TOML,
    which means an answer held a character that cannot be stored.
    """
    config = _config_text(plan)
    try:
        tomllib.loads(config)
        config.encode("utf-8")
    except (tomllib.TOMLDecodeError, UnicodeEncodeError) as exc:
        raise OnboardingError(f"an answer cannot be stored in the configuration: {exc}") from exc

    def document(payload: object) -> str:
        return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

    header = ",".join(load_schema()["obligation_fields"])
    merged = merge_sources([], plan.jurisdictions, plan.sources)
    return {
        DEFAULT_CONFIG_NAME: config,
        "register/obligations.csv": header + "\n",
        "register/jurisdictions.json": document({"jurisdictions": merged.jurisdictions}),
        "register/categories.json": document({"categories": []}),
        "register/sources.json": document({"sources": merged.sources}),
        "register/portfolio.json": document(
            {"name": "My portfolio", "disclaimer": "", "products": []}
        ),
        CATALOGUE_NAME: shipped_catalogue_text(),
    }
