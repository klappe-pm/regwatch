"""The JSON interface behind ``regwatch ui``.

``Api.handle`` takes a method, a path, the query and a parsed JSON body and
returns a status and a payload. It reads the project the same way the command
line does, through ``load_config`` and ``load_register``, and it does the same
work as the commands through the same functions: the source catalogue, its
ranking and ``sources add`` through ``regwatch.workspace``, keys through
``regwatch.keys``, the schedule and run records through ``regwatch.workspace``,
and ``regwatch run`` through ``workspace.run_once``. Every write goes through
``regwatch.state``. It never prints; ``regwatch.server`` carries it over HTTP.

Only a run started from the Automations page reaches the network, and it runs in
a background thread, one at a time.

No route returns the value of a key. The key routes accept a key once and answer
only whether one is available and where it comes from.

The newsletter, document and design and language model settings routes are
premium features: with premium off they answer 403 with a message that names
``regwatch premium on``. Generated copy is written only on a POST to a generate
route, which reaches the configured provider through the fetch client; the result
is kept in memory so the preview and the downloads show the same text.
"""

from __future__ import annotations

import datetime as dt
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from regwatch import __version__
from regwatch.briefing import TIERS, build_briefing
from regwatch.catalogue import CATEGORIES, CatalogueEntry, CatalogueError, filter_entries, rank
from regwatch.check import SourceResult, check_sources
from regwatch.config import (
    DEFAULT_MODELS,
    FONTS,
    LLM_PROVIDERS,
    PAGE_SIZES,
    Config,
    load_config,
)
from regwatch.design import DesignError
from regwatch.document import Document
from regwatch.fetch import Fetcher
from regwatch.focus import FocusProfile, build_profile, load_catalogue
from regwatch.impact import SEVERITIES, Impact, assess_impacts, theme_findings
from regwatch.keys import PROVIDER_KEYS, KeyStore, KeyStoreError
from regwatch.llm import GenerationError, GenerationResult, Poster
from regwatch.register import Register, load_register
from regwatch.render import docx_bytes, render_markdown, render_newsletter_html
from regwatch.sanitize import clean_text, safe_https_url
from regwatch.settings import (
    SettingsError,
    set_design,
    set_focus_areas,
    set_llm,
    set_newsletter_footer,
    set_premium,
)
from regwatch.state import load_seen
from regwatch.synthesis import daily_brief, upcoming_obligations, weekly_synthesis
from regwatch.system import System
from regwatch.workspace import (
    DOCUMENT_FORMATS,
    DOCUMENT_KINDS,
    MAX_SINCE_DAYS,
    WorkspaceError,
    add_sources,
    chosen_ids,
    document_bytes,
    document_plan,
    fetcher_for,
    find_entries,
    generated_copy,
    key_lookup,
    keyed_source,
    keyed_sources,
    newsletter_files,
    newsletter_plan,
    premium_refusal,
    read_candidates,
    read_run_records,
    run_once,
    schedule_state,
    source_catalogue,
    with_summary,
)

__all__ = ["SUPPLY_CATEGORIES", "Api", "ApiError", "Download"]

JsonObject = dict[str, Any]
MAX_RESULTS = 8
MAX_QUERY = 200
CATALOGUE_FILTERS = ("category", "region", "kind", "access")
SUPPLY_CATEGORIES = ("ingredients-supply", "packaging-materials", "commodities-and-forecasts")
BRIEFING_KINDS = ("tiered", "daily", "weekly")
EXPORT_FORMATS = {
    "md": ("text/markdown; charset=utf-8", "md"),
    "html": ("text/html; charset=utf-8", "html"),
    "docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "docx",
    ),
}
NEWSLETTER_FORMATS = {
    "eml": ("message/rfc822", "eml"),
    "html": ("text/html; charset=utf-8", "html"),
    "txt": ("text/plain; charset=utf-8", "txt"),
}
NEWSLETTER_PERIODS = (7, 14, 30, 90)
KEY_SOURCE_LABELS = {
    "environment": "Set in the environment",
    "keychain": "Stored in the keychain",
    "missing": "Not set",
    "unavailable": "Not set (no keychain tool)",
}


class ApiError(Exception):
    """A request the interface refuses. ``message`` is short and holds no file contents."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass(frozen=True)
class Download:
    """A file the browser saves rather than a JSON payload."""

    filename: str
    content_type: str
    data: bytes


Payload = JsonObject | Download


# --- helpers -----------------------------------------------------------------


def _query_text(query: Mapping[str, str], name: str, limit: int = MAX_QUERY) -> str:
    return clean_text(query.get(name, ""))[:limit]


def _result(result: SourceResult, names: Mapping[str, str]) -> JsonObject:
    return {
        "source_id": result.source_id,
        "name": names.get(result.source_id, result.source_id),
        "status": result.status,
        "origin": result.origin,
        "detail": clean_text(result.detail, 300),
        "flagged": result.flagged,
        "needs_attention": result.needs_attention,
    }


def _impact(impact: Impact) -> JsonObject:
    return {
        "product_id": impact.product_id,
        "product_name": impact.product_name,
        "obligation_id": impact.obligation_id,
        "obligation_title": impact.obligation_title,
        "jurisdiction": impact.jurisdiction,
        "status": impact.status,
        "effective_date": impact.effective_date,
        "severity": impact.severity,
        "reasons": list(impact.reasons),
        "focus": list(impact.focus),
        "in_focus": impact.in_focus,
    }


def _candidate(item: Mapping[str, Any]) -> JsonObject:
    """A candidate from the state file, cleaned again: the file may have been edited."""

    def text(key: str, limit: int) -> str:
        value = item.get(key)
        return clean_text(value, limit) if isinstance(value, str) else ""

    return {
        "date": text("date", 10),
        "jurisdiction": text("jurisdiction", 40),
        "agency": text("agency", 120),
        "headline": text("headline", 240),
        "what_happened": text("what_happened", 320),
        "type": text("type", 40),
        "source_url": safe_https_url(item.get("source_url")),
        "confidence": "unconfirmed",
    }


def _entry(entry: CatalogueEntry, chosen: set[str]) -> JsonObject:
    """A catalogue entry for the Sources page. A key variable name is a name, not a key."""
    return {
        "source_id": entry.source_id,
        "name": entry.name,
        "publisher": entry.publisher,
        "jurisdiction": entry.jurisdiction,
        "region": entry.region,
        "kind": entry.kind,
        "category": entry.category,
        "access": entry.access,
        "access_label": entry.access_label,
        "cadence": entry.cadence,
        "description": entry.description,
        "homepage": safe_https_url(entry.homepage),
        "signup_url": safe_https_url(entry.signup_url),
        "chosen": entry.source_id in chosen,
    }


def _matches(query: str, *fields: object) -> bool:
    return query in " ".join(str(f) for f in fields).casefold()


def _body_text(body: Mapping[str, Any], name: str, limit: int) -> str:
    value = body.get(name)
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ApiError(400, f"'{name}' must be a non-empty string of at most {limit} characters")
    return value.strip()


class Api:
    """The routes of the JSON interface, over one project's configuration file.

    ``system``, ``fetcher`` and ``clock`` are the same seams the command line has:
    the programs that keep keys and read the schedule, the network client a run
    uses, and the time.
    """

    def __init__(
        self,
        config_path: Path,
        today: Callable[[], dt.date] = dt.date.today,
        *,
        system: System | None = None,
        fetcher: Fetcher | None = None,
        clock: Callable[[], dt.datetime] | None = None,
        poster: Poster | None = None,
    ) -> None:
        self.config_path = config_path
        self.poster = poster
        # Generated copy by what it was written for, so a preview and its downloads match.
        self._generated: dict[tuple[str, ...], GenerationResult] = {}
        self._generate_lock = threading.Lock()
        self.today = today
        self.system = system or System()
        self.fetcher = fetcher
        self.clock = clock or (lambda: dt.datetime.now(dt.UTC))
        self._run_lock = threading.Lock()
        self._run_thread: threading.Thread | None = None
        self._run_error = ""
        self._routes: dict[tuple[str, str], Callable[[Mapping[str, str], JsonObject], Payload]] = {
            ("GET", "/api/status"): self.status,
            ("GET", "/api/overview"): self.overview,
            ("GET", "/api/changes"): self.changes,
            ("GET", "/api/sources"): self.sources,
            ("GET", "/api/catalogue"): self.catalogue,
            ("POST", "/api/catalogue/add"): self.catalogue_add,
            ("GET", "/api/obligations"): self.obligations,
            ("GET", "/api/briefing"): self.briefing,
            ("GET", "/api/briefing/export"): self.briefing_export,
            ("GET", "/api/automations"): self.automations,
            ("POST", "/api/automations/run"): self.automations_run,
            ("GET", "/api/keys"): self.keys,
            ("POST", "/api/keys/set"): self.keys_set,
            ("POST", "/api/keys/remove"): self.keys_remove,
            ("GET", "/api/settings"): self.settings,
            ("POST", "/api/settings/premium"): self.settings_premium,
            ("POST", "/api/settings/focus"): self.settings_focus,
            ("POST", "/api/settings/design"): self.settings_design,
            ("POST", "/api/settings/llm"): self.settings_llm,
            ("GET", "/api/newsletter"): self.newsletter,
            ("POST", "/api/newsletter/generate"): self.newsletter_generate,
            ("GET", "/api/newsletter/export"): self.newsletter_export,
            ("GET", "/api/document"): self.document,
            ("POST", "/api/document/generate"): self.document_generate,
            ("GET", "/api/document/export"): self.document_export,
            ("GET", "/api/search"): self.search,
        }

    def handle(
        self, method: str, path: str, query: Mapping[str, str], body: JsonObject
    ) -> tuple[int, Payload]:
        """Answer one request. Raises ApiError for a refusal the caller should report."""
        route = self._routes.get((method, path))
        if route is None:
            if any(p == path for _m, p in self._routes):
                raise ApiError(405, "method not allowed")
            raise ApiError(404, "no such route")
        return 200, route(query, body)

    # --- loading -------------------------------------------------------------

    def _config(self) -> Config:
        return load_config(self.config_path)

    def _project(self) -> tuple[Config, Register, FocusProfile]:
        config = self._config()
        return config, load_register(config), build_profile(config.profile)

    def _store(self) -> KeyStore:
        return KeyStore(self.system)

    def _check(self, config: Config, register: Register) -> list[SourceResult]:
        """Check every source against its stored snapshot. Never fetches."""
        return check_sources(register.sources, load_seen(config.seen_path), config.snapshots_dir)

    def _raw_candidates(self, config: Config) -> list[JsonObject]:
        """The candidates file as the command line reads it; a briefing cleans each field."""
        return read_candidates(config)

    def _candidates(self, config: Config) -> list[JsonObject]:
        return [_candidate(item) for item in self._raw_candidates(config)]

    def _schedule(self, config: Config) -> JsonObject:
        state = schedule_state(config, self.system, self.clock())
        return {
            "available": True,
            "via": state.via,
            "installed": state.installed,
            "every": state.every,
            "next_run": state.next_run,
            "note": state.note,
        }

    def _supply_chain(
        self, config: Config, register: Register, results: Sequence[SourceResult]
    ) -> list[JsonObject]:
        """Your sources in the supply chain categories, with their last status."""
        category = {e.source_id: e.category for e in source_catalogue(config)}
        status = {r.source_id: r for r in results}
        rows = []
        for source in register.sources:
            if category.get(source.source_id) not in SUPPLY_CATEGORIES:
                continue
            result = status.get(source.source_id)
            rows.append(
                {
                    "source_id": source.source_id,
                    "name": source.name,
                    "category": category[source.source_id],
                    "jurisdiction": source.jurisdiction,
                    "status": result.status if result else "",
                    "detail": clean_text(result.detail, 300) if result else "",
                }
            )
        return rows

    # --- routes --------------------------------------------------------------

    def status(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        config = self._config()
        return {
            "version": __version__,
            "project": config.base_dir.name,
            "premium": config.premium.enabled,
        }

    def overview(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        config, register, focus = self._project()
        today = self.today()
        results = self._check(config, register)
        counts = {
            "new": sum(r.status == "NEW" for r in results),
            "changed": sum(r.status == "CHANGED" for r in results),
            "suspicious": sum(r.status == "SUSPICIOUS" for r in results),
            "failing": sum(r.needs_attention for r in results),
        }
        names = {s.source_id: s.name for s in register.sources}
        impacts = assess_impacts(register, today, focus)
        upcoming = upcoming_obligations(register.obligations, 90, today)
        return {
            "generated": today.isoformat(),
            "counts": counts,
            "sources": len(results),
            "flagged": [_result(r, names) for r in results if r.flagged or r.needs_attention],
            "priority": [_impact(i) for i in impacts[:MAX_RESULTS]],
            "upcoming": [
                {
                    "obligation_id": o.obligation_id,
                    "title": o.title,
                    "jurisdiction": o.jurisdiction,
                    "effective_date": o.effective_date,
                    "status": o.status,
                }
                for o in upcoming[:MAX_RESULTS]
            ],
            "schedule": self._schedule(config),
            "supply_chain": {
                "available": True,
                "sources": self._supply_chain(config, register, results),
                "categories": list(SUPPLY_CATEGORIES),
            },
        }

    def changes(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        config, register, focus = self._project()
        names = {s.source_id: s.name for s in register.sources}
        results = self._check(config, register)
        return {
            "sources": [_result(r, names) for r in results],
            "impacts": [_impact(i) for i in assess_impacts(register, self.today(), focus)],
            "candidates": self._candidates(config),
            "severities": list(SEVERITIES),
        }

    def sources(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        config, register, _focus = self._project()
        status = {r.source_id: r for r in self._check(config, register)}
        return {
            "sources": [
                {
                    "source_id": s.source_id,
                    "name": s.name,
                    "jurisdiction": s.jurisdiction,
                    "mechanism": s.mechanism,
                    "cadence": s.cadence,
                    "url": safe_https_url(s.url),
                    "status": status[s.source_id].status if s.source_id in status else "",
                    "detail": clean_text(status[s.source_id].detail, 300)
                    if s.source_id in status
                    else "",
                }
                for s in register.sources
            ]
        }

    def catalogue(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        """The catalogue ranked for ``q`` by the ranking ``regwatch sources search`` uses."""
        config = self._config()
        everything = source_catalogue(config)
        chosen = set(chosen_ids(config))
        ranked = rank(everything, _query_text(query, "q"))
        facets = {
            name: sorted({str(getattr(e, name)) for e in everything}) for name in CATALOGUE_FILTERS
        }
        picked = {name: _query_text(query, name, 60) or None for name in CATALOGUE_FILTERS}
        entries = filter_entries(
            ranked,
            category=picked["category"],
            region=picked["region"],
            kind=picked["kind"],
            access=picked["access"],
        )
        return {
            "available": True,
            "total": len(everything),
            "entries": [_entry(entry, chosen) for entry in entries],
            "facets": facets,
            "categories": list(CATEGORIES),
        }

    def catalogue_add(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        """Add one catalogue source to your sources file, as ``regwatch sources add`` does."""
        source_id = _body_text(body, "source_id", 100)
        config = self._config()
        catalogue = source_catalogue(config)
        try:
            entries = find_entries(catalogue, [source_id])
        except WorkspaceError as exc:
            raise ApiError(400, "that id is not in the source catalogue") from exc
        try:
            merged = add_sources(config, entries)
        except CatalogueError as exc:
            raise ApiError(
                409,
                "your sources file already has a different source with this id; "
                "change it in the file by hand",
            ) from exc
        entry = entries[0]
        lookup = key_lookup(self._store())
        needs_key = entry.key_env is not None and entry.keyed and not lookup(entry.key_env)
        return {
            "available": True,
            "source_id": entry.source_id,
            "added": list(merged.added),
            "present": list(merged.present),
            "added_jurisdictions": list(merged.added_jurisdictions),
            "needs_key": needs_key,
        }

    def obligations(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        _config, register, focus = self._project()
        impacts = assess_impacts(register, self.today(), focus)
        by_obligation: dict[str, list[JsonObject]] = {}
        for impact in impacts:
            by_obligation.setdefault(impact.obligation_id, []).append(_impact(impact))
        names = {j.jurisdiction_id: j.name for j in register.jurisdictions}
        return {
            "obligations": [
                {
                    "obligation_id": o.obligation_id,
                    "title": o.title,
                    "jurisdiction": o.jurisdiction,
                    "jurisdiction_name": names.get(o.jurisdiction, o.jurisdiction),
                    "instrument": o.instrument,
                    "citation": o.citation,
                    "status": o.status,
                    "effective_date": o.effective_date,
                    "categories": list(o.categories),
                    "source_url": safe_https_url(o.source_url),
                    "impacts": by_obligation.get(o.obligation_id, []),
                }
                for o in register.obligations
            ]
        }

    def _document(self, query: Mapping[str, str]) -> tuple[Document, str]:
        kind = query.get("kind", "tiered")
        tier = query.get("tier", "v3")
        if kind not in BRIEFING_KINDS:
            raise ApiError(400, f"kind must be one of {', '.join(BRIEFING_KINDS)}")
        if tier not in TIERS:
            raise ApiError(400, f"tier must be one of {', '.join(TIERS)}")
        config, register, focus = self._project()
        today = self.today()
        impacts = assess_impacts(register, today, focus)
        if kind == "daily":
            return daily_brief(register, self._check(config, register), impacts, today), "daily"
        if kind == "weekly":
            findings = theme_findings(register, impacts, register.themes)
            return weekly_synthesis(register, impacts, findings, today), "weekly"
        document = build_briefing(
            register,
            impacts,
            today,
            tier=tier,
            candidates=self._raw_candidates(config),
            focus=focus,
        )
        return document, f"briefing-{tier}"

    def briefing(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        document, _stem = self._document(query)
        return {"kinds": list(BRIEFING_KINDS), "tiers": list(TIERS), "document": document.to_dict()}

    def briefing_export(self, query: Mapping[str, str], body: JsonObject) -> Download:
        fmt = query.get("format", "md")
        if fmt not in EXPORT_FORMATS:
            raise ApiError(400, f"format must be one of {', '.join(EXPORT_FORMATS)}")
        document, stem = self._document(query)
        content_type, suffix = EXPORT_FORMATS[fmt]
        if fmt == "md":
            data = render_markdown(document).encode("utf-8")
        elif fmt == "html":
            data = render_newsletter_html(document).encode("utf-8")
        else:
            data = docx_bytes(document)
        return Download(f"regwatch-{stem}-{self.today().isoformat()}.{suffix}", content_type, data)

    # --- automations ---------------------------------------------------------

    @property
    def running(self) -> bool:
        """True while a run started from the web app is in progress."""
        thread = self._run_thread
        return thread is not None and thread.is_alive()

    def wait_for_run(self, timeout: float | None = None) -> None:
        """Wait for a run started from the web app to finish. For tests and embedders."""
        thread = self._run_thread
        if thread is not None:
            thread.join(timeout)

    def automations(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        config = self._config()
        return {
            "premium": config.premium.enabled,
            "schedule": self._schedule(config),
            "runs": {"available": True, "records": read_run_records(config)},
            "running": self.running,
            "last_error": self._run_error,
        }

    def _run_in_background(self, config: Config) -> None:
        try:
            fetcher = self.fetcher or fetcher_for(config.fetch)
            run_once(config, fetcher, key_lookup(self._store()), self.clock)
            self._run_error = ""
        except Exception:
            # Whatever failed, its message could quote a file, so only the kind is kept.
            self._run_error = "the run failed; run 'regwatch run' in a terminal to see why"

    def automations_run(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        """Start ``regwatch run`` in a background thread. One run at a time."""
        config = self._config()
        with self._run_lock:
            if self.running:
                raise ApiError(409, "a run is already in progress")
            self._run_error = ""
            thread = threading.Thread(
                target=self._run_in_background, args=(config,), name="regwatch-run", daemon=True
            )
            self._run_thread = thread
            thread.start()
        return {"available": True, "running": True}

    # --- keys ----------------------------------------------------------------

    def keys(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        """Which keyed sources have a key, and where it comes from. Never the key."""
        config = self._config()
        store = self._store()
        rows = []
        for item in keyed_sources(config, source_catalogue(config)):
            try:
                where = store.status(item.key_env).source
            except KeyStoreError:
                where = "unavailable"
            rows.append(
                {
                    "source_id": item.source_id,
                    "key_env": item.key_env,
                    "present": where in ("environment", "keychain"),
                    "where": KEY_SOURCE_LABELS.get(where, "Not set"),
                    "signup_url": safe_https_url(item.signup_url),
                }
            )
        return {
            "available": True,
            "keychain": store.backend_label,
            "keychain_available": store.backend is not None,
            "keys": rows,
        }

    def _keyed(self, source_id: str) -> tuple[Config, str]:
        config = self._config()
        try:
            item = keyed_source(config, source_catalogue(config), source_id)
        except WorkspaceError as exc:
            raise ApiError(400, "that source does not need a key") from exc
        return config, item.key_env

    def keys_set(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        """Store a key, as ``regwatch keys set`` does. The answer never holds the key."""
        source_id = _body_text(body, "source_id", 100)
        key = _body_text(body, "key", 4096)
        _config, key_env = self._keyed(source_id)
        store = self._store()
        if store.backend is None:
            raise ApiError(
                409,
                f"no keychain tool was found; set the environment variable {key_env} instead",
            )
        try:
            store.set(key_env, key)
        except KeyStoreError as exc:
            raise ApiError(
                400, "the key was not stored; check it has no quotes, backslashes or spaces"
            ) from exc
        return {"available": True, "source_id": source_id, "present": True}

    def keys_remove(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        """Remove a stored key, as ``regwatch keys remove`` does."""
        source_id = _body_text(body, "source_id", 100)
        _config, key_env = self._keyed(source_id)
        store = self._store()
        try:
            removed = store.delete(key_env)
        except KeyStoreError as exc:
            raise ApiError(409, "the key could not be removed from the keychain") from exc
        in_environment = bool(self.system.environ.get(key_env))
        return {
            "available": True,
            "source_id": source_id,
            "removed": removed,
            "present": in_environment,
            "still_in_environment": in_environment,
        }

    # --- settings ------------------------------------------------------------

    def settings(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        config = self._config()
        catalogue = load_catalogue(config.profile.catalogue)
        design = config.document
        store = self._store()
        keys = []
        for key_id, (key_env, signup) in PROVIDER_KEYS.items():
            try:
                where = store.status(key_env).source
            except KeyStoreError:
                where = "unavailable"
            keys.append(
                {
                    "id": key_id,
                    "provider": key_id.removeprefix("llm-"),
                    "key_env": key_env,
                    "present": where in ("environment", "keychain"),
                    "where": KEY_SOURCE_LABELS.get(where, "Not set"),
                    "signup_url": safe_https_url(signup),
                }
            )
        logo = ""
        if design.logo is not None:
            logo = (
                design.logo.relative_to(config.base_dir).as_posix()
                if design.logo.is_relative_to(config.base_dir)
                else str(design.logo)
            )
        return {
            "focus_areas": list(config.profile.focus_areas),
            "custom_terms": list(config.profile.custom_terms),
            "focus_catalogue": [
                {"id": a.focus_id, "label": a.label, "description": a.description}
                for a in catalogue
            ],
            "premium": config.premium.enabled,
            "design": {
                "available": True,
                "title_format": design.title_format,
                "organisation": design.organisation,
                "primary_color": design.primary_color,
                "accent_color": design.accent_color,
                "font": design.font,
                "logo": logo,
                "header": design.header,
                "footer": design.footer,
                "page_size": design.page_size,
                "newsletter_footer": config.newsletter.footer,
                "fonts": list(FONTS),
                "page_sizes": list(PAGE_SIZES),
            },
            "llm": {
                "available": True,
                "enabled": config.llm.enabled,
                "provider": config.llm.provider,
                "model": config.llm.model,
                "providers": list(LLM_PROVIDERS),
                "default_models": dict(DEFAULT_MODELS),
                "allow_private_hosts": config.fetch.allow_private_hosts,
                "keys": keys,
            },
        }

    def settings_premium(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        enabled = body.get("enabled")
        if not isinstance(enabled, bool):
            raise ApiError(400, "'enabled' must be true or false")
        set_premium(self.config_path, enabled)
        return {"premium": self._config().premium.enabled}

    def settings_focus(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        areas = body.get("focus_areas")
        if not isinstance(areas, list) or not all(isinstance(a, str) for a in areas):
            raise ApiError(400, "'focus_areas' must be a list of focus area ids")
        config = self._config()
        known = [a.focus_id for a in load_catalogue(config.profile.catalogue)]
        set_focus_areas(self.config_path, areas, known)
        return {"focus_areas": list(self._config().profile.focus_areas)}

    def settings_design(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        """Save the design specification, checked as ``regwatch.toml`` is checked."""
        self._premium("Document design")
        values = body.get("design")
        if not isinstance(values, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in values.items()
        ):
            raise ApiError(400, "'design' must be an object of text values")
        footer = values.pop("newsletter_footer", None)
        try:
            set_design(self.config_path, values)
            if isinstance(footer, str):
                set_newsletter_footer(self.config_path, footer)
        except SettingsError as exc:
            # The message names the rule that was broken, never file contents.
            raise ApiError(400, str(exc)[:300]) from exc
        return self.settings(query, {})

    def settings_llm(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        """Save the generated copy settings: on or off, the provider and the model."""
        self._premium("Generated copy")
        enabled, provider, model = body.get("enabled"), body.get("provider"), body.get("model")
        if enabled is not None and not isinstance(enabled, bool):
            raise ApiError(400, "'enabled' must be true or false")
        if provider is not None and provider not in LLM_PROVIDERS:
            raise ApiError(400, f"'provider' must be one of {', '.join(LLM_PROVIDERS)}")
        if model is not None and not isinstance(model, str):
            raise ApiError(400, "'model' must be text")
        try:
            set_llm(self.config_path, enabled=enabled, provider=provider, model=model)
        except SettingsError as exc:
            raise ApiError(400, str(exc)[:300]) from exc
        return self.settings(query, {})

    # --- newsletters and documents ----------------------------------------------

    def _premium(self, feature: str) -> Config:
        config = self._config()
        if not config.premium.enabled:
            raise ApiError(403, premium_refusal(feature))
        return config

    def _since(self, value: object) -> int:
        text = str(value) if value is not None else "7"
        if not text.isdigit() or not 1 <= int(text) <= MAX_SINCE_DAYS:
            raise ApiError(400, f"'since' must be a number of days from 1 to {MAX_SINCE_DAYS}")
        return int(text)

    def _generate(
        self, config: Config, cache: tuple[str, ...], facts: Any, purpose: str
    ) -> GenerationResult:
        if not config.llm.enabled:
            raise ApiError(409, "generated copy is off; turn it on in Settings")
        if not self._generate_lock.acquire(blocking=False):
            raise ApiError(409, "generated copy is already being written")
        try:
            result = generated_copy(
                config, facts, purpose, key_lookup(self._store()), self.poster, self.clock
            )
        except GenerationError as exc:
            # The message holds the provider's status with the key removed, never a prompt.
            raise ApiError(502, str(exc)[:300]) from exc
        finally:
            self._generate_lock.release()
        self._generated[cache] = result
        return result

    def _newsletter(self, since: int, generated: bool, *, generate: bool = False) -> Any:
        config = self._premium("Newsletters")
        today = self.today()
        cache = ("newsletter", str(since), today.isoformat())
        register, content = newsletter_plan(config, today, since)
        result: GenerationResult | None = None
        if generate:
            result = self._generate(
                config,
                cache,
                content.facts(),
                f"the newsletter for {content.start.isoformat()} to {content.end.isoformat()}",
            )
        elif generated:
            result = self._generated.get(cache)
            if result is None:
                raise ApiError(
                    409, "press Generate first; no generated copy is kept for this period"
                )
        try:
            return newsletter_files(config, register, content, self.clock(), result)
        except DesignError as exc:
            raise ApiError(422, f"the logo cannot be used: {exc}"[:300]) from exc

    def _newsletter_payload(self, since: int, files: Any) -> JsonObject:
        return {
            "available": True,
            "since": since,
            "periods": list(NEWSLETTER_PERIODS),
            "subject": files.subject,
            "html": files.html,
            "text": files.text,
            "generated": files.generated,
            "dropped": list(files.dropped),
        }

    def newsletter(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        """The newsletter for ``since`` days; ``generated=1`` shows the kept generated copy."""
        since = self._since(query.get("since"))
        files = self._newsletter(since, query.get("generated") == "1")
        return self._newsletter_payload(since, files)

    def newsletter_generate(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        """Write the newsletter's opening and summaries with the language model."""
        since = self._since(body.get("since"))
        return self._newsletter_payload(since, self._newsletter(since, False, generate=True))

    def newsletter_export(self, query: Mapping[str, str], body: JsonObject) -> Download:
        fmt = query.get("format", "eml")
        if fmt not in NEWSLETTER_FORMATS:
            raise ApiError(400, f"format must be one of {', '.join(NEWSLETTER_FORMATS)}")
        since = self._since(query.get("since"))
        files = self._newsletter(since, query.get("generated") == "1")
        content_type, suffix = NEWSLETTER_FORMATS[fmt]
        data = {
            "eml": files.eml,
            "html": files.html.encode("utf-8"),
            "txt": files.text.encode("utf-8"),
        }[fmt]
        name = f"regwatch-newsletter-{self.today().isoformat()}.{suffix}"
        return Download(name, content_type, data)

    def _document_args(self, values: Mapping[str, Any]) -> tuple[str, str]:
        kind = str(values.get("kind") or "briefing")
        tier = str(values.get("tier") or "v2")
        if kind not in DOCUMENT_KINDS:
            raise ApiError(400, f"kind must be one of {', '.join(DOCUMENT_KINDS)}")
        if tier not in TIERS:
            raise ApiError(400, f"tier must be one of {', '.join(TIERS)}")
        return kind, tier

    def _designed(
        self, kind: str, tier: str, generated: bool, *, generate: bool = False
    ) -> tuple[Config, Document, list[str]]:
        config = self._premium("Documents")
        today = self.today()
        cache = ("document", kind, tier, today.isoformat())
        doc, facts = document_plan(config, today, kind, tier)
        result: GenerationResult | None = None
        if generate:
            result = self._generate(
                config, cache, facts, f"the summary that opens a regulatory {kind}"
            )
        elif generated:
            result = self._generated.get(cache)
            if result is None:
                raise ApiError(
                    409, "press Generate first; no generated copy is kept for this document"
                )
        if result is not None:
            doc = with_summary(doc, result)
        return config, doc, list(result.dropped) if result is not None else []

    def _document_payload(
        self, kind: str, tier: str, generated: bool, generate: bool = False
    ) -> JsonObject:
        config, doc, dropped = self._designed(kind, tier, generated, generate=generate)
        try:
            page = document_bytes(config, doc, "html").decode("utf-8")
        except DesignError as exc:
            raise ApiError(422, f"the logo cannot be used: {exc}"[:300]) from exc
        return {
            "available": True,
            "kind": kind,
            "tier": tier,
            "kinds": list(DOCUMENT_KINDS),
            "formats": list(DOCUMENT_FORMATS),
            "title": doc.title,
            "html": page,
            "generated": any(section.generated for section in doc.sections),
            "dropped": dropped,
        }

    def document(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        """A preview of the document in the design; ``generated=1`` adds the kept summary."""
        kind, tier = self._document_args(query)
        return self._document_payload(kind, tier, query.get("generated") == "1")

    def document_generate(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        """Write the document's opening summary with the language model."""
        kind, tier = self._document_args(body)
        return self._document_payload(kind, tier, False, generate=True)

    def document_export(self, query: Mapping[str, str], body: JsonObject) -> Download:
        kind, tier = self._document_args(query)
        fmt = query.get("format", "html")
        if fmt not in DOCUMENT_FORMATS:
            raise ApiError(400, f"format must be one of {', '.join(DOCUMENT_FORMATS)}")
        config, doc, _dropped = self._designed(kind, tier, query.get("generated") == "1")
        try:
            data = document_bytes(config, doc, fmt)
        except DesignError as exc:
            raise ApiError(422, f"the logo cannot be used: {exc}"[:300]) from exc
        content_type, suffix = DOCUMENT_FORMATS[fmt]
        return Download(f"regwatch-{kind}-{self.today().isoformat()}.{suffix}", content_type, data)

    # --- search --------------------------------------------------------------

    def search(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        text = _query_text(query, "q").casefold().strip()
        if not text:
            return {"query": "", "sources": [], "changes": [], "obligations": []}
        config, register, focus = self._project()
        sources: list[JsonObject] = [
            {"source_id": s.source_id, "name": s.name, "jurisdiction": s.jurisdiction, "mine": True}
            for s in register.sources
            if _matches(text, s.source_id, s.name, s.jurisdiction, s.notes)
        ]
        mine = {s.source_id for s in register.sources}
        for entry in rank(source_catalogue(config), text):
            if entry.source_id not in mine:
                sources.append(
                    {
                        "source_id": entry.source_id,
                        "name": entry.name,
                        "jurisdiction": entry.jurisdiction,
                        "mine": False,
                    }
                )
        changes: list[JsonObject] = [
            {"kind": "impact", **_impact(i)}
            for i in assess_impacts(register, self.today(), focus)
            if _matches(text, i.obligation_title, i.product_name, i.jurisdiction, *i.reasons)
        ]
        changes += [
            {"kind": "candidate", **c}
            for c in self._candidates(config)
            if _matches(text, c["headline"], c["what_happened"], c["agency"])
        ]
        obligations = [
            {
                "obligation_id": o.obligation_id,
                "title": o.title,
                "jurisdiction": o.jurisdiction,
                "status": o.status,
            }
            for o in register.obligations
            if _matches(text, o.obligation_id, o.title, o.citation, o.jurisdiction, *o.terms)
        ]
        return {
            "query": text,
            "sources": sources[:MAX_RESULTS],
            "changes": changes[:MAX_RESULTS],
            "obligations": obligations[:MAX_RESULTS],
        }
