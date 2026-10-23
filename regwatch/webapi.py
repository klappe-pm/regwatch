"""The JSON interface behind ``regwatch ui``.

``Api.handle`` takes a method, a path, the query and a parsed JSON body and
returns a status and a payload. It reads the project the same way the command
line does, through ``load_config`` and ``load_register``, and every write goes
through ``regwatch.settings``, which writes through ``regwatch.state``. It
never prints and never touches the network; ``regwatch.server`` carries it over
HTTP.

Some pages show features that other parts of Regwatch provide: the source
catalogue and its search, API keys in the keychain, and the schedule with its run
records. Those are reached only through the adapter functions in the section
marked "adapters" below. Until a feature lands its adapter returns ``None`` and
the interface answers ``{"available": false}``, so the pages show an empty state
that names the command that will fill it. When a feature lands, its adapter is
the one place that changes.

No route returns the value of a key. The key routes accept a key once and answer
only whether one is stored.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from regwatch import __version__
from regwatch.briefing import TIERS, build_briefing
from regwatch.check import SourceResult, check_sources
from regwatch.config import Config, load_config
from regwatch.document import Document
from regwatch.focus import FocusProfile, build_profile, load_catalogue
from regwatch.impact import SEVERITIES, Impact, assess_impacts, theme_findings
from regwatch.register import Register, load_register
from regwatch.render import docx_bytes, render_markdown, render_newsletter_html
from regwatch.sanitize import clean_text, safe_https_url
from regwatch.settings import set_focus_areas, set_premium
from regwatch.state import MAX_STATE_BYTES, load_seen
from regwatch.synthesis import daily_brief, upcoming_obligations, weekly_synthesis

__all__ = ["CATEGORIES", "Api", "ApiError", "Download"]

JsonObject = dict[str, Any]
MAX_RESULTS = 8
MAX_QUERY = 200
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
CATALOGUE_FILTERS = ("category", "region", "kind", "access")
BRIEFING_KINDS = ("tiered", "daily", "weekly")
EXPORT_FORMATS = {
    "md": ("text/markdown; charset=utf-8", "md"),
    "html": ("text/html; charset=utf-8", "html"),
    "docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "docx",
    ),
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

# --- adapters ----------------------------------------------------------------
# Each returns None while the feature it reaches has not landed. Replace the body
# with a call into the feature's module when it does; nothing else changes.


def catalogue_entries(query: str) -> list[JsonObject] | None:
    """Catalogue entries ranked for ``query`` (all of them when it is empty), or None."""
    return None


def add_catalogue_source(config: Config, source_id: str) -> JsonObject | None:
    """Copy a catalogue entry into the user's sources file, or None."""
    return None


def key_status(config: Config) -> list[JsonObject] | None:
    """For each keyed source: ``source_id``, ``key_env`` and ``present``. Never a value."""
    return None


def store_key(config: Config, source_id: str, key: str) -> bool | None:
    """Store a key in the keychain; True when stored, or None."""
    return None


def delete_key(config: Config, source_id: str) -> bool | None:
    """Remove a stored key; True when one was removed, or None."""
    return None


def schedule_status(config: Config) -> JsonObject | None:
    """The installed schedule: ``every`` and ``next_run``, or None."""
    return None


def run_records(config: Config) -> list[JsonObject] | None:
    """Run records from the state directory, newest first, or None."""
    return None


def run_now(config: Config) -> JsonObject | None:
    """Run a capture and a check now and return its run record, or None."""
    return None


def supply_chain_signals(config: Config) -> list[JsonObject] | None:
    """Input cost and packaging signals from supply chain sources, or None."""
    return None


# --- helpers -----------------------------------------------------------------


def _unavailable(command: str, **extra: Any) -> JsonObject:
    return {"available": False, "command": command, **extra}


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


def _matches(query: str, *fields: object) -> bool:
    return query in " ".join(str(f) for f in fields).casefold()


def _body_text(body: Mapping[str, Any], name: str, limit: int) -> str:
    value = body.get(name)
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ApiError(400, f"'{name}' must be a non-empty string of at most {limit} characters")
    return value.strip()


class Api:
    """The routes of the JSON interface, over one project's configuration file."""

    def __init__(self, config_path: Path, today: Callable[[], dt.date] = dt.date.today) -> None:
        self.config_path = config_path
        self.today = today
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

    def _check(self, config: Config, register: Register) -> list[SourceResult]:
        """Check every source against its stored snapshot. Never fetches."""
        return check_sources(register.sources, load_seen(config.seen_path), config.snapshots_dir)

    def _raw_candidates(self, config: Config) -> list[JsonObject]:
        """The candidates file as the command line reads it; a briefing cleans each field."""
        path = config.candidates_path
        if not path.is_file():
            return []
        try:
            if path.stat().st_size > MAX_STATE_BYTES:
                return []
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, RecursionError):
            return []
        items = data.get("candidates", []) if isinstance(data, dict) else []
        return [item for item in items if isinstance(item, dict)]

    def _candidates(self, config: Config) -> list[JsonObject]:
        return [_candidate(item) for item in self._raw_candidates(config)]

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
        schedule = schedule_status(config)
        signals = supply_chain_signals(config)
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
            "schedule": (
                _unavailable("regwatch schedule")
                if schedule is None
                else {"available": True, **schedule}
            ),
            "supply_chain": (
                _unavailable("regwatch sources add")
                if signals is None
                else {"available": True, "signals": signals}
            ),
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
        entries = catalogue_entries(_query_text(query, "q"))
        if entries is None:
            return _unavailable("regwatch sources search", entries=[], facets={})
        facets = {
            name: sorted({str(e.get(name, "")) for e in entries if e.get(name)})
            for name in CATALOGUE_FILTERS
        }
        for name in CATALOGUE_FILTERS:
            wanted = _query_text(query, name, 60)
            if wanted:
                entries = [e for e in entries if str(e.get(name, "")) == wanted]
        return {"available": True, "entries": entries, "facets": facets}

    def catalogue_add(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        source_id = _body_text(body, "source_id", 100)
        added = add_catalogue_source(self._config(), source_id)
        if added is None:
            return _unavailable("regwatch sources add")
        return {"available": True, **added}

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

    def automations(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        config = self._config()
        schedule = schedule_status(config)
        runs = run_records(config)
        return {
            "premium": config.premium.enabled,
            "schedule": (
                _unavailable("regwatch schedule")
                if schedule is None
                else {"available": True, **schedule}
            ),
            "runs": (
                _unavailable("regwatch run", records=[])
                if runs is None
                else {"available": True, "records": runs}
            ),
        }

    def automations_run(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        record = run_now(self._config())
        if record is None:
            return _unavailable("regwatch run")
        return {"available": True, "record": record}

    def keys(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        found = key_status(self._config())
        if found is None:
            return _unavailable("regwatch keys list", keys=[])
        # Only these three fields leave the interface, whatever the adapter returns.
        keys = [
            {
                "source_id": str(k.get("source_id", "")),
                "key_env": str(k.get("key_env", "")),
                "present": k.get("present") is True,
            }
            for k in found
        ]
        return {"available": True, "keys": keys}

    def keys_set(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        source_id = _body_text(body, "source_id", 100)
        key = _body_text(body, "key", 4096)
        stored = store_key(self._config(), source_id, key)
        if stored is None:
            return _unavailable("regwatch keys set")
        return {"available": True, "source_id": source_id, "present": bool(stored)}

    def keys_remove(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        source_id = _body_text(body, "source_id", 100)
        removed = delete_key(self._config(), source_id)
        if removed is None:
            return _unavailable("regwatch keys remove")
        return {"available": True, "source_id": source_id, "present": False}

    def settings(self, query: Mapping[str, str], body: JsonObject) -> JsonObject:
        config = self._config()
        catalogue = load_catalogue(config.profile.catalogue)
        return {
            "focus_areas": list(config.profile.focus_areas),
            "custom_terms": list(config.profile.custom_terms),
            "focus_catalogue": [
                {"id": a.focus_id, "label": a.label, "description": a.description}
                for a in catalogue
            ],
            "premium": config.premium.enabled,
            "design": _unavailable("regwatch documents design"),
            "llm": _unavailable("regwatch generate"),
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
        mine = {s["source_id"] for s in sources} | {s.source_id for s in register.sources}
        for entry in catalogue_entries(text) or []:
            if entry.get("source_id") not in mine:
                sources.append(
                    {
                        "source_id": str(entry.get("source_id", "")),
                        "name": str(entry.get("name", "")),
                        "jurisdiction": str(entry.get("jurisdiction", "")),
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
