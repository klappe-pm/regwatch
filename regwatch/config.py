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
    "AA_CONTRAST",
    "DEFAULT_CONFIG_NAME",
    "DEFAULT_MODELS",
    "DOCUMENT_KEYS",
    "FONTS",
    "LLM_PROVIDERS",
    "PAGE_SIZES",
    "CatalogueSettings",
    "Config",
    "ConfigError",
    "DocumentDesign",
    "FetchSettings",
    "IngestSettings",
    "LlmSettings",
    "NewsletterSettings",
    "PremiumSettings",
    "ProfileSettings",
    "RegisterPaths",
    "check_color",
    "check_title_format",
    "contrast_with_white",
    "file_root_is_too_broad",
    "load_config",
    "parse_document_table",
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
class PremiumSettings:
    """The premium toggle, ``[premium] enabled``. Off unless the file turns it on.

    Regwatch is MIT licensed, so this is a product boundary, not a lock: the web app
    shows premium features with a note while it is off, and anyone can turn it on.
    """

    enabled: bool = False


LLM_PROVIDERS = ("anthropic", "openai", "ollama")
DEFAULT_MODELS = {"anthropic": "claude-opus-5-5", "openai": "gpt-5-mini", "ollama": "llama3.2"}
MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,99}$")


@dataclass(frozen=True)
class LlmSettings:
    """The generated copy stage, ``[llm]``. Off unless the file turns it on.

    ``model`` is empty for the provider's default. ``max_tokens`` caps one answer and
    ``timeout_seconds`` is the whole deadline of one call.
    """

    enabled: bool = False
    provider: str = "anthropic"
    model: str = ""
    max_tokens: int = 4000
    timeout_seconds: float = 180.0

    @property
    def effective_model(self) -> str:
        """The model a call names: the configured one, or the provider's default."""
        return self.model or DEFAULT_MODELS[self.provider]


PAGE_SIZES = ("a4", "letter")
FONTS = {
    "system": "-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    "Arial": "Arial, Helvetica, sans-serif",
    "Helvetica": "Helvetica, Arial, sans-serif",
    "Verdana": "Verdana, Geneva, sans-serif",
    "Tahoma": "Tahoma, Verdana, sans-serif",
    "Trebuchet MS": "'Trebuchet MS', Helvetica, sans-serif",
    "Georgia": "Georgia, 'Times New Roman', serif",
    "Times New Roman": "'Times New Roman', Times, serif",
    "Garamond": "Garamond, Georgia, serif",
    "Courier New": "'Courier New', Courier, monospace",
}
"""The fonts a design may name, each with the CSS stack it renders with."""
HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
TITLE_FIELDS = ("title", "date", "organisation")
AA_CONTRAST = 4.5


def contrast_with_white(color: str) -> float:
    """The WCAG 2.2 contrast ratio of ``#rrggbb`` against white, from 1 to 21."""

    def channel(value: int) -> float:
        c = value / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    red, green, blue = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    luminance = 0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue)
    return 1.05 / (luminance + 0.05)


def check_color(value: object, key: str) -> str:
    """``value`` as a lower case ``#rrggbb`` colour that meets AA against white, or ConfigError."""
    if not isinstance(value, str) or not HEX_COLOR_RE.fullmatch(value):
        raise ConfigError(f"[document] {key} must be a colour written #rrggbb")
    ratio = contrast_with_white(value)
    if ratio < AA_CONTRAST:
        raise ConfigError(
            f"[document] {key} {value} has a contrast of {ratio:.2f}:1 against white; "
            f"text needs at least {AA_CONTRAST}:1 (WCAG 2.2 AA), so choose a darker colour"
        )
    return value.lower()


def check_title_format(value: object) -> str:
    """A title format that uses only ``{title}``, ``{date}`` and ``{organisation}``."""
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise ConfigError("[document] title_format must be a string of 1 to 200 characters")
    for field_name in re.findall(r"\{([^{}]*)\}", value):
        if field_name not in TITLE_FIELDS:
            raise ConfigError(
                "[document] title_format may use only {title}, {date} and {organisation}"
            )
    rest = re.sub(r"\{(?:title|date|organisation)\}", "", value)
    if "{" in rest or "}" in rest:
        raise ConfigError("[document] title_format has an unmatched brace")
    return value


@dataclass(frozen=True)
class DocumentDesign:
    """The design specification documents and newsletters follow, ``[document]``.

    Colours are ``#rrggbb`` that meet WCAG 2.2 AA against white, the font is one of
    ``FONTS``, and ``logo`` is a PNG or SVG file under the project folder or an
    allowed file root, read and checked only when a document is built.
    """

    title_format: str = "{title}"
    organisation: str = ""
    primary_color: str = "#1d5a92"
    accent_color: str = "#a8481a"
    font: str = "system"
    logo: Path | None = None
    header: str = ""
    footer: str = ""
    page_size: str = "a4"

    @property
    def font_stack(self) -> str:
        """The CSS font stack for ``font``."""
        return FONTS[self.font]

    def title(self, title: str, date: str) -> str:
        """``title_format`` filled in with the document's title, its date and the organisation.

        A document's own title starts with the portfolio name, which is often the
        organisation, so when the format names ``{organisation}`` a leading
        organisation name is taken off the title first and the rest starts with a
        capital: "Pantry Co: Regulatory newsletter", not "Pantry Co: Pantry Co
        regulatory newsletter".
        """
        organisation = self.organisation.strip()
        if organisation and "{organisation}" in self.title_format:
            title = _without_leading(title, organisation)
        return (
            self.title_format.replace("{title}", title)
            .replace("{date}", date)
            .replace("{organisation}", self.organisation)
            .strip()
            or title
        )


def _without_leading(title: str, name: str) -> str:
    """``title`` without a leading ``name`` (any case, as a whole word), capitalised."""
    if not title.casefold().startswith(name.casefold()):
        return title
    rest = title[len(name) :]
    if rest[:1].isalnum():
        return title
    rest = rest.lstrip(" .,:;")
    return rest[:1].upper() + rest[1:] if rest else title


DEFAULT_NEWSLETTER_FOOTER = (
    "You receive this newsletter because you asked for it. Reply to this message to stop."
)


@dataclass(frozen=True)
class NewsletterSettings:
    """The newsletter's closing line, ``[newsletter] footer``: how to reply or unsubscribe."""

    footer: str = DEFAULT_NEWSLETTER_FOOTER


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
    premium: PremiumSettings = PremiumSettings()
    llm: LlmSettings = LlmSettings()
    document: DocumentDesign = DocumentDesign()
    newsletter: NewsletterSettings = NewsletterSettings()

    @property
    def llm_calls_path(self) -> Path:
        """File that records each generated copy call: provider, model, tokens and duration."""
        return self.state_dir / "llm-calls.jsonl"

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
    value: object = table.get(key, default)
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


def _parse_premium(table: dict[str, Any]) -> PremiumSettings:
    enabled = table.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ConfigError("[premium] enabled must be true or false")
    return PremiumSettings(enabled=enabled)


def _parse_llm(table: dict[str, Any]) -> LlmSettings:
    enabled = table.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ConfigError("[llm] enabled must be true or false")
    provider = table.get("provider", "anthropic")
    if provider not in LLM_PROVIDERS:
        raise ConfigError(f"[llm] provider must be one of {', '.join(LLM_PROVIDERS)}")
    model = table.get("model", "")
    if not isinstance(model, str) or (model and not MODEL_RE.fullmatch(model)):
        raise ConfigError(
            "[llm] model must be a model name of letters, digits and . _ : / - "
            "(at most 100 characters), or empty for the provider's default"
        )
    timeout = table.get("timeout_seconds", LlmSettings.timeout_seconds)
    if isinstance(timeout, bool) or not isinstance(timeout, int | float) or not 0 < timeout <= 600:
        raise ConfigError("[llm] timeout_seconds must be a number above 0 and at most 600")
    return LlmSettings(
        enabled=enabled,
        provider=provider,
        model=model,
        max_tokens=_integer(table, "max_tokens", "llm", LlmSettings.max_tokens, 256, 32000),
        timeout_seconds=float(timeout),
    )


def _short_text(table: dict[str, Any], key: str, section: str, limit: int, default: str) -> str:
    value = table.get(key, default)
    if not isinstance(value, str) or len(value) > limit:
        raise ConfigError(f"[{section}] {key} must be a string of at most {limit} characters")
    if any(ord(ch) < 0x20 or 0x7F <= ord(ch) <= 0x9F for ch in value):
        raise ConfigError(f"[{section}] {key} must not hold control characters")
    return value


def _parse_document(table: dict[str, Any], base: Path) -> DocumentDesign:
    default = DocumentDesign()
    font = table.get("font", default.font)
    if font not in FONTS:
        raise ConfigError(f"[document] font must be one of {', '.join(FONTS)}")
    page_size = table.get("page_size", default.page_size)
    if page_size not in PAGE_SIZES:
        raise ConfigError(f"[document] page_size must be one of {', '.join(PAGE_SIZES)}")
    logo = table.get("logo", "")
    if not isinstance(logo, str):
        raise ConfigError("[document] logo must be a path")
    return DocumentDesign(
        title_format=check_title_format(table.get("title_format", default.title_format)),
        organisation=_short_text(table, "organisation", "document", 120, ""),
        primary_color=check_color(
            table.get("primary_color", default.primary_color), "primary_color"
        ),
        accent_color=check_color(table.get("accent_color", default.accent_color), "accent_color"),
        font=font,
        logo=_resolve(base, logo) if logo.strip() else None,
        header=_short_text(table, "header", "document", 200, ""),
        footer=_short_text(table, "footer", "document", 300, ""),
        page_size=page_size,
    )


DOCUMENT_KEYS = (
    "title_format",
    "organisation",
    "primary_color",
    "accent_color",
    "font",
    "logo",
    "header",
    "footer",
    "page_size",
)


def parse_document_table(table: dict[str, Any], base: Path) -> DocumentDesign:
    """Check a ``[document]`` table as ``load_config`` does and return the design.

    Raises ConfigError for an unknown key or a value that ``load_config`` would refuse.
    """
    unknown = sorted(set(table) - set(DOCUMENT_KEYS))
    if unknown:
        raise ConfigError(f"[document] has unknown keys: {', '.join(unknown)}")
    return _parse_document(table, base)


def _parse_newsletter(table: dict[str, Any]) -> NewsletterSettings:
    footer = _short_text(table, "footer", "newsletter", 300, DEFAULT_NEWSLETTER_FOOTER)
    return NewsletterSettings(footer=footer.strip() or DEFAULT_NEWSLETTER_FOOTER)


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
        set(data)
        - {
            "register",
            "state",
            "fetch",
            "ingest",
            "profile",
            "catalogue",
            "premium",
            "llm",
            "document",
            "newsletter",
        }
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
        premium=_parse_premium(_table(data, "premium", ("enabled",))),
        llm=_parse_llm(
            _table(data, "llm", ("enabled", "provider", "model", "max_tokens", "timeout_seconds"))
        ),
        document=_parse_document(
            _table(data, "document", DOCUMENT_KEYS),
            base,
        ),
        newsletter=_parse_newsletter(_table(data, "newsletter", ("footer",))),
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
