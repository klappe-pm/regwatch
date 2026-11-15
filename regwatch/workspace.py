"""The workspace operations that the command line and the web app share.

``regwatch sources``, ``regwatch keys`` and ``regwatch run`` print, and the web
app's JSON interface answers in JSON, but both do the same work through these
functions: read the source catalogue, add catalogue sources to the sources file,
find the sources that need a key, run a capture and a check with a run record,
read the state of the schedule, write generated copy, and build a newsletter or a
designed document.
Nothing here prints or asks a question.
"""

from __future__ import annotations

import datetime as dt
import json
import plistlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from regwatch.briefing import TIERS, build_briefing
from regwatch.catalogue import (
    CatalogueEntry,
    MergeResult,
    load_source_catalogue,
    merge_sources,
)
from regwatch.check import CaptureResult, SourceResult, capture_sources, check_sources
from regwatch.config import Config, FetchSettings
from regwatch.design import Logo, load_logo
from regwatch.document import Document, Section
from regwatch.fetch import Fetcher, SafeFetcher
from regwatch.focus import build_profile, load_catalogue
from regwatch.impact import assess_impacts
from regwatch.keys import PROVIDER_KEYS, KeyStore, KeyStoreError
from regwatch.llm import (
    SECTIONS,
    Fact,
    GenerationResult,
    Poster,
    candidate_facts,
    change_facts,
    event_facts,
    generate,
    impact_facts,
    llm_fetcher,
    obligation_facts,
    provider_for,
)
from regwatch.newsletter import (
    LOGO_CID,
    NewsletterContent,
    build_newsletter,
    email_bytes,
    newsletter_content,
    render_email_html,
    render_email_text,
)
from regwatch.register import Register, load_register, read_json_list
from regwatch.render import docx_bytes, render_document_html, render_markdown
from regwatch.schedule import CRON_TIMES, INTERVAL_SECONDS, installed_block, plist_path
from regwatch.state import (
    MAX_STATE_BYTES,
    append_call_record,
    list_run_records,
    load_seen,
    make_state_dir,
    update_register_file,
    write_run_record,
)
from regwatch.synthesis import digest_document, report_document, upcoming_obligations
from regwatch.system import System

__all__ = [
    "DOCUMENT_FORMATS",
    "DOCUMENT_KINDS",
    "NO_FACTS_NOTICE",
    "RUN_CHANGES",
    "RUN_OK",
    "RUN_UNVERIFIED",
    "SVG_LOGO_NOTE",
    "KeyedSource",
    "NewsletterFiles",
    "RunOutcome",
    "ScheduleState",
    "WorkspaceError",
    "add_sources",
    "check_key_allowed",
    "chosen_ids",
    "document_bytes",
    "document_plan",
    "fetcher_for",
    "find_entries",
    "generated_copy",
    "key_lookup",
    "keyed_source",
    "keyed_sources",
    "logo_for",
    "newsletter_files",
    "newsletter_plan",
    "premium_refusal",
    "read_candidates",
    "read_run_records",
    "run_once",
    "schedule_state",
    "source_catalogue",
    "with_summary",
]

RUN_OK = 0
RUN_CHANGES = 3
RUN_UNVERIFIED = 4


class WorkspaceError(ValueError):
    """A request the user can fix, such as an id that is not in the catalogue."""


# --- the source catalogue ------------------------------------------------------


def focus_area_ids(config: Config | None) -> list[str]:
    """The shipped focus area ids, then those of the user's own focus catalogue."""
    ids = [area.focus_id for area in load_catalogue(None)]
    if config is not None and config.profile.catalogue is not None:
        ids += [area.focus_id for area in load_catalogue(config.profile.catalogue)]
    return list(dict.fromkeys(ids))


def source_catalogue(config: Config | None) -> tuple[CatalogueEntry, ...]:
    """The shipped catalogue, plus the user's extra file when ``config`` names one."""
    if config is None:
        return load_source_catalogue(focus_area_ids(None))
    return load_source_catalogue(focus_area_ids(config), config.catalogue.extra)


def chosen_ids(config: Config) -> list[str]:
    """The ids in the user's sources file."""
    _data, sources = read_json_list(config.register.sources, "sources", "sources file")
    return [str(source.get("source_id", "")) for source in sources]


def find_entries(catalogue: Sequence[CatalogueEntry], ids: Sequence[str]) -> list[CatalogueEntry]:
    """The catalogue entries for ``ids``, without repeats. Raises for an unknown id."""
    by_id = {entry.source_id: entry for entry in catalogue}
    unknown = [source_id for source_id in ids if source_id not in by_id]
    if unknown:
        raise WorkspaceError(
            f"not in the source catalogue: {', '.join(unknown)}; "
            "try 'regwatch sources search' to find an id"
        )
    return [by_id[source_id] for source_id in dict.fromkeys(ids)]


def _write_register_list(config: Config, path: Path, data: dict[str, Any]) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    update_register_file(path, text, config.register.all_paths())


def add_sources(config: Config, entries: Sequence[CatalogueEntry]) -> MergeResult:
    """Copy ``entries`` into the sources file, adding any jurisdiction they need.

    This is ``regwatch sources add``. The jurisdictions file is written only when a
    jurisdiction was added, and the sources file only when a source was.
    """
    paths = config.register
    sources_data, sources = read_json_list(paths.sources, "sources", "sources file")
    jur_data, jurisdictions = read_json_list(
        paths.jurisdictions, "jurisdictions", "jurisdictions file"
    )
    merged = merge_sources(sources, jurisdictions, entries)
    if merged.added_jurisdictions:
        _write_register_list(
            config, paths.jurisdictions, {**jur_data, "jurisdictions": merged.jurisdictions}
        )
    if merged.added:
        _write_register_list(config, paths.sources, {**sources_data, "sources": merged.sources})
    return merged


# --- keys ----------------------------------------------------------------------


@dataclass(frozen=True)
class KeyedSource:
    """A source that needs a key: its id, the variable that names the key, and its sign-up page."""

    source_id: str
    key_env: str
    signup_url: str | None


def keyed_sources(config: Config | None, catalogue: Sequence[CatalogueEntry]) -> list[KeyedSource]:
    """The sources that need a key.

    With a configuration, the keyed sources in the user's sources file, each with
    its catalogue sign-up page when the catalogue has the source. Without one,
    every keyed catalogue entry.
    """
    if config is None:
        return [
            KeyedSource(e.source_id, e.key_env, e.signup_url)
            for e in catalogue
            if e.key_env is not None
        ]
    signup = {e.source_id: e.signup_url for e in catalogue if e.key_env is not None}
    _data, sources = read_json_list(config.register.sources, "sources", "sources file")
    found: list[KeyedSource] = []
    for source in sources:
        key_env = str(source.get("key_env", "") or "")
        if key_env:
            sid = str(source.get("source_id", ""))
            found.append(KeyedSource(sid, key_env, signup.get(sid)))
    return found


def keyed_source(
    config: Config | None, catalogue: Sequence[CatalogueEntry], source_id: str
) -> KeyedSource:
    """The keyed source ``source_id``, from the sources file first, then the catalogue."""
    for item in keyed_sources(config, catalogue):
        if item.source_id == source_id:
            return item
    for entry in catalogue:
        if entry.source_id == source_id and entry.key_env is not None:
            return KeyedSource(entry.source_id, entry.key_env, entry.signup_url)
    if source_id in PROVIDER_KEYS:
        key_env, signup = PROVIDER_KEYS[source_id]
        return KeyedSource(source_id, key_env, signup)
    raise WorkspaceError(f"'{source_id}' is not a source that needs a key")


def check_key_allowed(config: Config | None, source_id: str) -> None:
    """Refuse to store a language model provider key while premium is off.

    Generated copy is a premium feature, so its provider keys (``llm-anthropic`` and
    ``llm-openai``) can be stored only with premium on; a key for a source can
    always be stored. Removing a key is never refused.
    """
    if source_id in PROVIDER_KEYS and (config is None or not config.premium.enabled):
        raise WorkspaceError(premium_refusal("Generated copy"))


def key_lookup(store: KeyStore) -> Callable[[str], str | None]:
    """A function that returns the key for a variable, or None when none can be read."""

    def lookup(key_env: str) -> str | None:
        try:
            return store.get(key_env)
        except KeyStoreError:
            return None

    return lookup


# --- runs ----------------------------------------------------------------------


def fetcher_for(settings: FetchSettings) -> Fetcher:
    """The fetch client for ``settings``."""
    return SafeFetcher(
        settings.timeout_seconds,
        settings.max_bytes,
        settings.user_agent,
        total_timeout_seconds=settings.total_timeout_seconds,
        allow_private_hosts=settings.allow_private_hosts,
        allowed_file_roots=settings.allowed_file_roots,
    )


@dataclass(frozen=True)
class RunOutcome:
    """What one run did: captures, check results, the record and where it was written."""

    captures: tuple[CaptureResult, ...]
    results: tuple[SourceResult, ...]
    failed: tuple[CaptureResult, ...]
    counts: dict[str, int]
    code: int
    record: dict[str, Any]
    path: Path


def _stamp(moment: dt.datetime) -> str:
    return moment.astimezone(dt.UTC).strftime("%Y%m%dT%H%M%S%fZ")


def run_once(
    config: Config,
    fetcher: Fetcher,
    key_for: Callable[[str], str | None],
    clock: Callable[[], dt.datetime],
    register: Register | None = None,
) -> RunOutcome:
    """Capture every source, check every snapshot, and write a run record.

    This is ``regwatch run``. The code is 0, 3 when a source is flagged, and 4 when
    a capture failed or a source is in ``ERROR`` or ``MISSING``.
    """
    started = clock()
    register = register if register is not None else load_register(config)
    sources = list(register.sources)
    protected = config.register.all_paths()
    captures = capture_sources(sources, fetcher, config.snapshots_dir, protected, key_for)
    manual = {s.source_id for s in sources if s.mechanism == "manual"}
    failed = [c for c in captures if not c.captured and c.source_id not in manual]
    results = check_sources(
        sources, load_seen(config.seen_path), config.snapshots_dir, None, key_for
    )
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    code = RUN_OK
    if any(r.flagged for r in results):
        code = RUN_CHANGES
    if failed or any(r.needs_attention for r in results):
        code = RUN_UNVERIFIED
    ended = clock()
    record: dict[str, Any] = {
        "started": started.astimezone(dt.UTC).isoformat(timespec="seconds"),
        "ended": ended.astimezone(dt.UTC).isoformat(timespec="seconds"),
        "sources": len(sources),
        "captured": sum(1 for c in captures if c.captured),
        "capture_failed": len(failed),
        "counts": dict(sorted(counts.items())),
        "exit_code": code,
    }
    path = write_run_record(config.state_dir, record, _stamp(started), protected)
    return RunOutcome(tuple(captures), tuple(results), tuple(failed), counts, code, record, path)


_RECORD_FIELDS = ("started", "ended", "sources", "captured", "capture_failed", "exit_code")


def read_run_records(config: Config, limit: int = 50) -> list[dict[str, Any]]:
    """The newest run records, newest first. Unreadable or malformed records are skipped."""
    found: list[dict[str, Any]] = []
    for path in reversed(list_run_records(config.state_dir)):
        if len(found) >= limit:
            break
        try:
            if path.stat().st_size > MAX_STATE_BYTES:
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, RecursionError):
            continue
        if not isinstance(data, dict):
            continue
        record: dict[str, Any] = {
            name: data[name]
            for name in _RECORD_FIELDS
            if isinstance(data.get(name), str | int) and not isinstance(data.get(name), bool)
        }
        counts = data.get("counts")
        if isinstance(counts, dict):
            record["counts"] = {
                str(k): v
                for k, v in counts.items()
                if isinstance(v, int) and not isinstance(v, bool)
            }
        found.append(record)
    return found


# --- the schedule --------------------------------------------------------------


@dataclass(frozen=True)
class ScheduleState:
    """Whether a schedule is installed, how often it runs, and when it runs next.

    ``via`` is ``launchd`` or ``cron``. ``every`` is the installed cadence, read back
    from the agent or the crontab block. ``next_run`` is an ISO time in UTC: exact
    for cron, and for launchd the last run plus the interval, when there is one.
    ``note`` explains a state that could not be read.
    """

    via: str
    installed: bool
    every: str | None = None
    next_run: str | None = None
    note: str = ""


def _next_cron(every: str, now: dt.datetime) -> dt.datetime:
    """The next time cron starts a run at ``every``, in the machine's local time."""
    local = now.astimezone()
    if every == "hourly":
        candidate = local.replace(minute=17, second=0, microsecond=0)
        if candidate <= local:
            candidate += dt.timedelta(hours=1)
        return candidate
    candidate = local.replace(hour=6, minute=17, second=0, microsecond=0)
    if every == "weekly":
        candidate += dt.timedelta(days=(0 - candidate.weekday()) % 7)
        if candidate <= local:
            candidate += dt.timedelta(days=7)
        return candidate
    if candidate <= local:
        candidate += dt.timedelta(days=1)
    return candidate


def _iso(moment: dt.datetime) -> str:
    return moment.astimezone(dt.UTC).isoformat(timespec="seconds")


def schedule_state(config: Config, system: System, now: dt.datetime) -> ScheduleState:
    """Read the installed schedule without changing anything."""
    if system.is_macos:
        path = plist_path(system.home())
        if not path.is_file():
            return ScheduleState("launchd", False)
        try:
            agent = plistlib.loads(path.read_bytes())
        except (OSError, ValueError, plistlib.InvalidFileException):
            return ScheduleState("launchd", True, note="the agent file could not be read")
        interval = agent.get("StartInterval") if isinstance(agent, dict) else None
        every = next((k for k, v in INTERVAL_SECONDS.items() if v == interval), None)
        next_run = None
        records = read_run_records(config, 1)
        if every and records and isinstance(records[0].get("started"), str):
            try:
                last = dt.datetime.fromisoformat(records[0]["started"])
                next_run = _iso(last + dt.timedelta(seconds=INTERVAL_SECONDS[every]))
            except ValueError:
                next_run = None
        return ScheduleState("launchd", True, every, next_run)
    crontab_tool = system.which("crontab")
    if crontab_tool is None:
        return ScheduleState("cron", False, note="the crontab command was not found")
    result = system.runner([crontab_tool, "-l"], None)
    if result.returncode != 0:
        if "no crontab" in result.stderr.lower():
            return ScheduleState("cron", False)
        return ScheduleState("cron", False, note="the crontab could not be read")
    block = installed_block(result.stdout)
    if block is None:
        return ScheduleState("cron", False)
    every = next(
        (name for name, times in CRON_TIMES.items() if f"\n{times} " in f"\n{block}"), None
    )
    next_run = _iso(_next_cron(every, now)) if every else None
    return ScheduleState("cron", True, every, next_run)


# --- premium content -------------------------------------------------------------

PREMIUM_HINT = "turn it on with 'regwatch premium on'"
MAX_SINCE_DAYS = 366
NO_FACTS_NOTICE = (
    "Nothing in this period gives the language model anything to write from, so no "
    "request was sent and the fixed sentences are used."
)
SVG_LOGO_NOTE = (
    "The logo is an SVG, which common mail programs do not show, so the email has no logo. "
    "Use a PNG logo to show it."
)


def premium_refusal(feature: str) -> str:
    """The message for a premium feature used while premium is off."""
    return f"{feature} is a premium feature; {PREMIUM_HINT}"


def read_candidates(config: Config) -> list[dict[str, Any]]:
    """The ingest candidates as stored, or none when the file is missing or unreadable.

    The file is untrusted; every builder cleans each field it uses.
    """
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


def generated_copy(
    config: Config,
    facts: Sequence[Fact],
    purpose: str,
    key_for: Callable[[str], str | None],
    poster: Poster | None = None,
    now: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.UTC),
    sections: Sequence[str] = SECTIONS,
) -> GenerationResult:
    """Ask the configured provider for copy written from ``facts``, and record the call.

    ``sections`` are the sections the output shows; a passage for any other is
    dropped. With no facts no request is sent: the result is empty and its notice
    says the fixed sentences are used. Raises WorkspaceError when generated copy is
    off, and GenerationError when it cannot be written. The call is recorded in
    ``llm-calls.jsonl`` in the state directory with the provider, the model, the
    tokens and the duration only.
    """
    if not config.llm.enabled:
        raise WorkspaceError("generated copy is off; turn it on with 'regwatch llm on'")
    if not facts:
        return GenerationResult(notice=NO_FACTS_NOTICE)
    provider = provider_for(config.llm, poster or llm_fetcher(config), key_for)
    protected = config.register.all_paths()

    def record(entry: dict[str, object]) -> None:
        make_state_dir(config.state_dir)
        append_call_record(config.llm_calls_path, entry, protected)

    return generate(
        provider,
        facts,
        purpose,
        max_tokens=config.llm.max_tokens,
        record=record,
        now=now,
        sections=sections,
    )


def logo_for(config: Config) -> Logo | None:
    """The checked logo of the design specification, under the project folder or a file root."""
    return load_logo(config.document.logo, [config.base_dir, *config.fetch.allowed_file_roots])


def newsletter_plan(
    config: Config, today: dt.date, since_days: int
) -> tuple[Register, NewsletterContent]:
    """The register and the items of the newsletter for the last ``since_days`` days.

    Sources are checked against their stored snapshots, never fetched.
    """
    if not 1 <= since_days <= MAX_SINCE_DAYS:
        raise WorkspaceError(f"the period must be 1 to {MAX_SINCE_DAYS} days")
    register = load_register(config)
    impacts = assess_impacts(register, today, build_profile(config.profile))
    results = check_sources(register.sources, load_seen(config.seen_path), config.snapshots_dir)
    content = newsletter_content(
        register, results, impacts, read_candidates(config), today, since_days
    )
    return register, content


@dataclass(frozen=True)
class NewsletterFiles:
    """One newsletter in every form: the subject, the standalone HTML, the text and the .eml."""

    subject: str
    html: str
    text: str
    eml: bytes
    generated: bool
    dropped: tuple[str, ...] = ()
    notice: str = ""
    logo_note: str = ""


def newsletter_files(
    config: Config,
    register: Register,
    content: NewsletterContent,
    now: dt.datetime,
    generated: GenerationResult | None = None,
) -> NewsletterFiles:
    """Render the newsletter with the design specification and the closing line.

    The standalone HTML carries a PNG logo as a ``data:`` address and the ``.eml``
    as a related image part. Raises DesignError when the logo cannot be used.
    """
    design = config.document
    footer = config.newsletter.footer
    logo = logo_for(config)
    doc = build_newsletter(register, content, design, generated)
    text = render_email_text(doc, design, footer)
    page = render_email_html(
        doc, design, footer, logo=logo, logo_src=logo.data_uri if logo is not None else ""
    )
    mail = render_email_html(doc, design, footer, logo=logo, logo_src=f"cid:{LOGO_CID}")
    return NewsletterFiles(
        subject=doc.title,
        html=page,
        text=text,
        eml=email_bytes(doc.title, text, mail, now, logo),
        generated=generated is not None and generated.count > 0,
        dropped=tuple(generated.dropped) if generated is not None else (),
        notice=generated.notice if generated is not None else "",
        logo_note=SVG_LOGO_NOTE if logo is not None and logo.kind == "svg" else "",
    )


# --- documents -------------------------------------------------------------------------

DOCUMENT_KINDS = ("briefing", "digest", "report")
DOCUMENT_FORMATS = {
    "html": ("text/html; charset=utf-8", "html"),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
    "md": ("text/markdown; charset=utf-8", "md"),
}
DOCUMENT_WINDOW_DAYS = 365
DOCUMENT_FACT_LIMIT = 40


def document_plan(
    config: Config, today: dt.date, kind: str, tier: str = "v2"
) -> tuple[Document, list[Fact]]:
    """The document of ``kind`` with the design's title format, and the facts behind it.

    ``briefing`` is the tiered briefing at ``tier``, ``digest`` the register digest
    and ``report`` the change and due alert, each over a year. Sources are checked
    against their stored snapshots and never fetched.
    """
    if kind not in DOCUMENT_KINDS:
        raise WorkspaceError(f"the kind must be one of {', '.join(DOCUMENT_KINDS)}")
    if tier not in TIERS:
        raise WorkspaceError(f"the tier must be one of {', '.join(TIERS)}")
    register = load_register(config)
    upcoming = upcoming_obligations(register.obligations, DOCUMENT_WINDOW_DAYS, today)
    places = {j.jurisdiction_id: j.name for j in register.jurisdictions}
    limit = DOCUMENT_FACT_LIMIT
    if kind == "briefing":
        focus = build_profile(config.profile)
        impacts = assess_impacts(register, today, focus)
        candidates = read_candidates(config)
        doc = build_briefing(
            register, impacts, today, tier=tier, candidates=candidates, focus=focus
        )
        events = sorted(register.changelog, key=lambda e: e.date, reverse=True)[:8]
        urgent = [i for i in impacts if i.severity in ("act-now", "high")][:10]
        facts = [
            *event_facts(events, places),
            *candidate_facts(candidates[:8]),
            *impact_facts(urgent, places),
            *obligation_facts(upcoming[:10], places),
        ]
    elif kind == "digest":
        doc = digest_document(register, today, DOCUMENT_WINDOW_DAYS)
        facts = obligation_facts(upcoming[:limit], places)
    else:
        results = check_sources(register.sources, load_seen(config.seen_path), config.snapshots_dir)
        names = {s.source_id: s.name for s in register.sources}
        doc = report_document(register, results, today, DOCUMENT_WINDOW_DAYS)
        facts = [*change_facts(results, names)[:limit], *obligation_facts(upcoming[:limit], places)]
    doc.title = config.document.title(doc.title, doc.generated)
    return doc, facts


def with_summary(doc: Document, generated: GenerationResult) -> Document:
    """``doc`` opened by a Summary section that holds every kept generated passage.

    The passages come in the order of their sections, the opening first. With no
    kept passage the document is returned as it was.
    """
    passages = [passage for name in SECTIONS for passage in generated.section(name)]
    if passages:
        doc.sections.insert(0, Section("Summary", generated=passages))
    return doc


def document_bytes(config: Config, doc: Document, fmt: str) -> bytes:
    """``doc`` in ``fmt`` (``html``, ``docx`` or ``md``) with the design and its logo.

    Raises WorkspaceError for an unknown format and DesignError when the logo cannot
    be used.
    """
    if fmt not in DOCUMENT_FORMATS:
        raise WorkspaceError(f"the format must be one of {', '.join(DOCUMENT_FORMATS)}")
    if fmt == "md":
        return render_markdown(doc).encode("utf-8")
    logo = logo_for(config)
    if fmt == "html":
        return render_document_html(doc, config.document, logo).encode("utf-8")
    return docx_bytes(doc, config.document, logo)
