"""Configuration file loading.

A regwatch project is described by one TOML file that names the user's register
files, the directory where regwatch keeps its own state, and the network and
ingest settings. Every path in the file is resolved relative to the directory
that holds the file. Unknown keys and wrong types are rejected so a typo never
silently changes behaviour.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_CONFIG_NAME",
    "CatalogueSettings",
    "Config",
    "ConfigError",
    "FetchSettings",
    "IngestSettings",
    "ProfileSettings",
    "RegisterPaths",
    "file_root_is_too_broad",
    "load_config",
]

DEFAULT_CONFIG_NAME = "regwatch.toml"
DEFAULT_USER_AGENT = "regwatch/0.1 (+https://github.com/klappe-pm/regwatch)"
DEFAULT_API_URL = "https://www.federalregister.gov/api/v1/documents.json"
FOCUS_ID_RE = re.compile(r"^[a-z0-9-]+$")
MAX_CONFIG_BYTES = 256_000
MAX_FETCH_BYTES_CEILING = 100_000_000

_REQUIRED_REGISTER = ("obligations", "jurisdictions", "categories", "sources", "portfolio")
_OPTIONAL_REGISTER = ("detail", "changelog", "enforcement", "themes")


class ConfigError(Exception):
    """The configuration file is missing, unreadable or invalid."""


@dataclass(frozen=True)
class RegisterPaths:
    """Locations of the user's register files. regwatch only ever reads these."""

    obligations: Path
    jurisdictions: Path
    categories: Path
    sources: Path
    portfolio: Path
    detail: Path | None = None
    changelog: Path | None = None
    enforcement: Path | None = None
    themes: Path | None = None

    def all_paths(self) -> list[Path]:
        """Every configured register path, resolved, for write protection."""
        candidates = [
            self.obligations,
            self.jurisdictions,
            self.categories,
            self.sources,
            self.portfolio,
            self.detail,
            self.changelog,
            self.enforcement,
            self.themes,
        ]
        return [path.resolve() for path in candidates if path is not None]


@dataclass(frozen=True)
class FetchSettings:
    """Limits applied to every network or file fetch."""

    timeout_seconds: float = 20.0
    max_bytes: int = 2_000_000
    user_agent: str = DEFAULT_USER_AGENT
    total_timeout_seconds: float = 60.0
    allow_private_hosts: bool = False
    allowed_file_roots: tuple[Path, ...] = ()


@dataclass(frozen=True)
class IngestSettings:
    """Filters for the Federal Register style candidate ingest."""

    api_url: str = DEFAULT_API_URL
    agencies: tuple[str, ...] = ()
    types: tuple[str, ...] = ("RULE", "PRORULE", "NOTICE")
    cfr_title: int | None = None
    cfr_parts: tuple[int, ...] = ()
    terms: tuple[str, ...] = ()
    jurisdiction: str = ""
    per_page: int = 100


@dataclass(frozen=True)
class ProfileSettings:
    """What the user's business cares about, recorded by ``regwatch init``.

    ``focus_areas`` are identifiers from the focus catalogue and ``custom_terms``
    are extra words of the user's own. ``catalogue`` is an optional path to a
    catalogue file that replaces the shipped one.
    """

    focus_areas: tuple[str, ...] = ()
    custom_terms: tuple[str, ...] = ()
    catalogue: Path | None = None


@dataclass(frozen=True)
class CatalogueSettings:
    """The user's own source catalogue file, read after the shipped one, if any."""

    extra: Path | None = None


@dataclass(frozen=True)
class Config:
    """The parsed configuration, with every path made absolute."""

    base_dir: Path
    register: RegisterPaths
    state_dir: Path
    snapshots_dir: Path
    fetch: FetchSettings
    ingest: IngestSettings
    config_path: Path
    profile: ProfileSettings = ProfileSettings()
    catalogue: CatalogueSettings = CatalogueSettings()

    def protected_paths(self) -> list[Path]:
        """Files that a user-named output path must never overwrite.

        The register files, this configuration file, the focus catalogue and the
        extra source catalogue when they are configured, and regwatch's own state
        files.
        """
        catalogue = [self.profile.catalogue.resolve()] if self.profile.catalogue else []
        if self.catalogue.extra is not None:
            catalogue.append(self.catalogue.extra.resolve())
        return [
            *self.register.all_paths(),
            self.config_path.resolve(),
            self.seen_path.resolve(),
            self.candidates_path.resolve(),
            *catalogue,
        ]

    @property
    def seen_path(self) -> Path:
        """File that records the last accepted content hash of each source."""
        return self.state_dir / "seen.json"

    @property
    def candidates_path(self) -> Path:
        """File that holds unconfirmed candidate events from ingest."""
        return self.state_dir / "ingest-candidates.json"


def _table(data: dict[str, Any], name: str, allowed: tuple[str, ...]) -> dict[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ConfigError(f"[{name}] must be a table")
    unknown = sorted(set(value) - set(allowed))
    if unknown:
        raise ConfigError(f"[{name}] has unknown keys: {', '.join(unknown)}")
    return value


def _string(table: dict[str, Any], key: str, section: str, default: str | None = None) -> str:
    value = table.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"[{section}] {key} must be a non-empty string")
    return value


def _str_list(
    table: dict[str, Any], key: str, section: str, default: tuple[str, ...]
) -> tuple[str, ...]:
    value = table.get(key, list(default))
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ConfigError(f"[{section}] {key} must be a list of non-empty strings")
    return tuple(value)


def _integer(
    table: dict[str, Any], key: str, section: str, default: int, low: int, high: int
) -> int:
    value = table.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ConfigError(f"[{section}] {key} must be an integer from {low} to {high}")
    return value


def file_root_is_too_broad(path: Path, home: Path | None) -> bool:
    """True when ``path`` is a file system root, the home directory or a parent of it.

    Such a folder as a ``file`` source root would allow almost any file to be read.
    A parent of the home directory holds the home directory, and so everything in it.
    """
    resolved = path.resolve()
    if resolved == Path(resolved.anchor):
        return True
    if home is None:
        return False
    home_resolved = home.resolve()
    return resolved == home_resolved or resolved in home_resolved.parents


def _home() -> Path | None:
    try:
        return Path.home()
    except (RuntimeError, KeyError):
        return None


def _resolve(base: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (base / path)


def _seconds(table: dict[str, Any], key: str, default: float) -> float:
    value = table.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int | float) or not 0 < value <= 3600:
        raise ConfigError(f"[fetch] {key} must be a number above 0 and at most 3600")
    return float(value)


def _parse_fetch(table: dict[str, Any], base: Path) -> FetchSettings:
    allow_private = table.get("allow_private_hosts", False)
    if not isinstance(allow_private, bool):
        raise ConfigError("[fetch] allow_private_hosts must be true or false")
    roots = _str_list(table, "allowed_file_roots", "fetch", ())
    resolved_roots = tuple(_resolve(base, root) for root in roots)
    for root, resolved in zip(roots, resolved_roots, strict=True):
        if file_root_is_too_broad(resolved, _home()):
            raise ConfigError(
                f"[fetch] allowed_file_roots entry '{root}' is too broad; name the folder that "
                "holds the files, not a file system root, your home directory or a folder that "
                "contains it"
            )
    return FetchSettings(
        timeout_seconds=_seconds(table, "timeout_seconds", FetchSettings.timeout_seconds),
        total_timeout_seconds=_seconds(
            table, "total_timeout_seconds", FetchSettings.total_timeout_seconds
        ),
        allow_private_hosts=allow_private,
        allowed_file_roots=resolved_roots,
        max_bytes=_integer(
            table, "max_bytes", "fetch", FetchSettings.max_bytes, 1, MAX_FETCH_BYTES_CEILING
        ),
        user_agent=_string(table, "user_agent", "fetch", DEFAULT_USER_AGENT),
    )


def _parse_ingest(table: dict[str, Any]) -> IngestSettings:
    title = table.get("cfr_title")
    if title is not None and (isinstance(title, bool) or not isinstance(title, int) or title < 1):
        raise ConfigError("[ingest] cfr_title must be a positive integer")
    parts = table.get("cfr_parts", [])
    if not isinstance(parts, list) or not all(
        isinstance(p, int) and not isinstance(p, bool) and p > 0 for p in parts
    ):
        raise ConfigError("[ingest] cfr_parts must be a list of positive integers")
    jurisdiction = table.get("jurisdiction", "")
    if not isinstance(jurisdiction, str):
        raise ConfigError("[ingest] jurisdiction must be a string")
    return IngestSettings(
        api_url=_string(table, "api_url", "ingest", DEFAULT_API_URL),
        agencies=_str_list(table, "agencies", "ingest", ()),
        types=_str_list(table, "types", "ingest", IngestSettings.types),
        cfr_title=title,
        cfr_parts=tuple(parts),
        terms=tuple(term.lower() for term in _str_list(table, "terms", "ingest", ())),
        jurisdiction=jurisdiction,
        per_page=_integer(table, "per_page", "ingest", 100, 1, 1000),
    )


def _parse_profile(table: dict[str, Any], base: Path) -> ProfileSettings:
    areas = _str_list(table, "focus_areas", "profile", ())
    if not all(FOCUS_ID_RE.fullmatch(area) for area in areas):
        raise ConfigError(
            "[profile] focus_areas must hold identifiers of lowercase letters, digits and hyphens"
        )
    catalogue = (
        _resolve(base, _string(table, "catalogue", "profile")) if "catalogue" in table else None
    )
    return ProfileSettings(
        focus_areas=tuple(dict.fromkeys(areas)),
        custom_terms=tuple(dict.fromkeys(_str_list(table, "custom_terms", "profile", ()))),
        catalogue=catalogue,
    )


def _parse_catalogue(table: dict[str, Any], base: Path) -> CatalogueSettings:
    if "extra" not in table:
        return CatalogueSettings()
    return CatalogueSettings(_resolve(base, _string(table, "extra", "catalogue")))


def load_config(path: Path) -> Config:
    """Read and validate the configuration file at ``path``.

    Raises ConfigError for a missing or oversized file, invalid TOML, unknown
    keys, wrong types or a missing required register path.
    """
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ConfigError(f"cannot read configuration file {path}: {exc.strerror}") from exc
    if size > MAX_CONFIG_BYTES:
        raise ConfigError(f"configuration file {path} is larger than {MAX_CONFIG_BYTES} bytes")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"cannot parse configuration file {path}: {exc}") from exc

    unknown_tables = sorted(
        set(data) - {"register", "state", "fetch", "ingest", "profile", "catalogue"}
    )
    if unknown_tables:
        raise ConfigError(f"unknown configuration tables: {', '.join(unknown_tables)}")

    base = path.resolve().parent
    register = _table(data, "register", _REQUIRED_REGISTER + _OPTIONAL_REGISTER)
    missing = [key for key in _REQUIRED_REGISTER if key not in register]
    if missing:
        raise ConfigError(f"[register] is missing required keys: {', '.join(missing)}")
    resolved: dict[str, Path | None] = {}
    for key in _REQUIRED_REGISTER:
        resolved[key] = _resolve(base, _string(register, key, "register"))
    for key in _OPTIONAL_REGISTER:
        resolved[key] = (
            _resolve(base, _string(register, key, "register")) if key in register else None
        )

    state = _table(data, "state", ("dir", "snapshots"))
    state_dir = _resolve(base, _string(state, "dir", "state", "state"))
    snapshots = (
        _resolve(base, _string(state, "snapshots", "state"))
        if "snapshots" in state
        else state_dir / "snapshots"
    )

    paths = RegisterPaths(
        obligations=_require(resolved, "obligations"),
        jurisdictions=_require(resolved, "jurisdictions"),
        categories=_require(resolved, "categories"),
        sources=_require(resolved, "sources"),
        portfolio=_require(resolved, "portfolio"),
        detail=resolved["detail"],
        changelog=resolved["changelog"],
        enforcement=resolved["enforcement"],
        themes=resolved["themes"],
    )
    protected = set(paths.all_paths())
    for label, directory in (("state dir", state_dir), ("snapshots dir", snapshots)):
        if directory.resolve() in protected:
            raise ConfigError(f"the {label} must not be a register file")

    return Config(
        base_dir=base,
        register=paths,
        state_dir=state_dir,
        snapshots_dir=snapshots,
        fetch=_parse_fetch(
            _table(
                data,
                "fetch",
                (
                    "timeout_seconds",
                    "total_timeout_seconds",
                    "max_bytes",
                    "user_agent",
                    "allow_private_hosts",
                    "allowed_file_roots",
                ),
            ),
            base,
        ),
        config_path=path.resolve(),
        catalogue=_parse_catalogue(_table(data, "catalogue", ("extra",)), base),
        profile=_parse_profile(
            _table(data, "profile", ("focus_areas", "custom_terms", "catalogue")), base
        ),
        ingest=_parse_ingest(
            _table(
                data,
                "ingest",
                (
                    "api_url",
                    "agencies",
                    "types",
                    "cfr_title",
                    "cfr_parts",
                    "terms",
                    "jurisdiction",
                    "per_page",
                ),
            )
        ),
    )


def _require(resolved: dict[str, Path | None], key: str) -> Path:
    value = resolved[key]
    # Required keys are checked before this call, so this guard exists for the type checker.
    if value is None:  # pragma: no cover
        raise ConfigError(f"[register] {key} is required")
    return value
