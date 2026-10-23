"""The ``regwatch`` command line.

Each subcommand is one stage of the engine:

    validate  check the register files against the field rules
    coverage  report how much of each jurisdiction the register covers
    list      list obligations, optionally filtered
    portfolio list the products obligations are matched against
    capture   fetch sources into stored snapshots
    check     detect changes in sources since the last accepted run
    ingest    turn a Federal Register style response into unconfirmed candidates
    impact    flag candidate impacts of obligations on products
    themes    read the impacts through the configured themes
    brief     build a daily, weekly or tiered briefing document
    render    render a saved briefing in Markdown, web, newsletter and Word formats
    digest    write a Markdown digest of the register
    report    write a change-and-due alert
    export    write one flat record per obligation as CSV and JSON
    init      create a project: configuration, an empty register and your focus areas
    config    show the effective configuration
    sources   list, search, show, add, remove and verify catalogue sources
    keys      store, list and remove the API keys some sources need
    run       capture, then check, and write a run record (what a schedule runs)
    schedule  install, show or remove a recurring run with launchd or cron
    ui        open the local web app in the browser
    premium   turn the premium features on or off, or show whether they are on

Exit status: 0 success, 1 the register is invalid or nothing could be captured,
2 a usage, configuration, network or file error, 3 changes were detected and
``check --exit-code`` was given, 4 a source could not be verified.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import webbrowser
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO, TypeVar

from regwatch import __version__
from regwatch.briefing import TIERS, build_briefing
from regwatch.catalogue import (
    ACCESS,
    CATEGORIES,
    FIELDS,
    KINDS,
    MECHANISMS,
    REGIONS,
    CatalogueEntry,
    CatalogueError,
    entry_from_dict,
    filter_entries,
    load_source_catalogue,
    rank,
)
from regwatch.check import SourceResult, accept_results, capture_sources, check_sources
from regwatch.config import (
    DEFAULT_CONFIG_NAME,
    Config,
    ConfigError,
    FetchSettings,
    load_config,
)
from regwatch.document import DISCLAIMER, Document, DocumentError, Section, make_disclaimer
from regwatch.export import build_records, records_csv
from regwatch.fetch import Credential, Fetcher, FetchError
from regwatch.focus import FocusError, FocusProfile, build_profile, load_catalogue
from regwatch.impact import SEVERITIES, Impact, assess_impacts, theme_findings
from regwatch.ingest import IngestError, build_query_url, candidates_document, parse_candidates
from regwatch.keys import KeyStore, KeyStoreError
from regwatch.onboarding import (
    SCAFFOLD_NAMES,
    InitPlan,
    OnboardingError,
    check_contact,
    check_directory,
    check_file_root,
    clean_terms,
    example_jurisdictions,
    jurisdiction_records,
    matching_entries,
    parse_focus_choice,
    scaffold_files,
    user_agent_for,
)
from regwatch.register import (
    Register,
    RegisterError,
    Source,
    load_register,
    obligations_citing_source,
    read_json_list,
    validate_register,
)
from regwatch.render import (
    FORMATS,
    TAG_RE,
    docx_bytes,
    render_markdown,
    render_newsletter_html,
    render_newsletter_text,
    render_webpost,
)
from regwatch.sanitize import clean_line, clean_text
from regwatch.schedule import (
    CADENCES,
    LABEL,
    ScheduleError,
    cron_block,
    installed_block,
    plist_bytes,
    plist_path,
    program_arguments,
    replace_block,
    schedule_cadence,
)
from regwatch.server import LocalServer, ServerError, web_root
from regwatch.settings import set_premium
from regwatch.state import (
    MAX_STATE_BYTES,
    AlreadyExistsError,
    StateError,
    load_seen,
    remove_file,
    safe_write_bytes,
    safe_write_text,
    save_seen,
    update_register_file,
    write_tree,
)
from regwatch.synthesis import daily_brief, upcoming_obligations, weekly_synthesis
from regwatch.system import System
from regwatch.webapi import Api
from regwatch.workspace import (
    KeyedSource,
    add_sources,
    chosen_ids,
    fetcher_for,
    find_entries,
    key_lookup,
    keyed_source,
    keyed_sources,
    run_once,
    source_catalogue,
)

__all__ = ["main"]

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_ERROR = 2
EXIT_CHANGES = 3
EXIT_UNVERIFIED = 4
NOTICE = "regwatch flags candidates for human review. It is not legal advice."
MAX_INPUT_BYTES = 20_000_000
NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]{0,99}$")


def _say(text: str = "", *, file: TextIO | None = None) -> None:
    """Print one line of console output.

    Every line of console output goes through here. Values that came from the
    register, a catalogue or a server are printed in these lines, so control
    characters (and with them terminal escape sequences and line breaks) and
    invisible format characters are removed first.
    """
    print(clean_line(text), file=file)


class CommandError(Exception):
    """A command failed in a way the user can fix. The message is printed as is."""


@dataclass
class _Context:
    config_path: Path
    fetcher: Fetcher | None
    today: dt.date
    now: dt.datetime
    system: System = field(default_factory=System)
    clock: Callable[[], dt.datetime] = field(default=lambda: dt.datetime.now(dt.UTC))
    _config: Config | None = field(default=None, init=False)

    def keystore(self) -> KeyStore:
        return KeyStore(self.system)

    def key_for(self, key_env: str) -> str | None:
        """The key for ``key_env``, or None when there is none or no keychain can be read."""
        return key_lookup(self.keystore())(key_env)

    @property
    def config(self) -> Config:
        if self._config is None:
            self._config = load_config(self.config_path)
        return self._config

    def live_fetcher(self) -> Fetcher:
        """The injected fetcher, or a real one built from the fetch settings."""
        if self.fetcher is not None:
            return self.fetcher
        settings = self.config.fetch if self.config_path.exists() else FetchSettings()
        return fetcher_for(settings)

    def register(self) -> Register:
        return load_register(self.config)

    def focus(self) -> FocusProfile:
        """The focus profile named in the configuration; inactive when none is set."""
        return build_profile(self.config.profile)

    def protected(self) -> list[Path]:
        """Files that a user-named output path must never overwrite.

        ``render`` works on a saved model and does not need a register, so a
        missing configuration file means there is nothing to protect.
        """
        if not self.config_path.exists():
            return []
        return self.config.protected_paths()

    def _check_output(self, path: Path) -> None:
        """Refuse a user-named output that lies inside regwatch's own state."""
        if not self.config_path.exists():
            return
        target = path.resolve()
        for directory in (self.config.state_dir, self.config.snapshots_dir):
            if target.is_relative_to(directory.resolve()):
                raise CommandError(
                    f"{path} is inside regwatch's state directory; choose another output path"
                )

    def write_text(self, path: Path, text: str) -> None:
        """Write a file the user named on the command line."""
        self._check_output(path)
        safe_write_text(path, text, self.protected())

    def write_bytes(self, path: Path, data: bytes) -> None:
        """Write a file the user named on the command line."""
        self._check_output(path)
        safe_write_bytes(path, data, self.protected())

    def write_state(self, path: Path, text: str) -> None:
        """Write one of regwatch's own state files. Only the register is protected."""
        safe_write_text(path, text, self.config.register.all_paths())


# --- register commands -------------------------------------------------------


def _cmd_validate(ctx: _Context, args: argparse.Namespace) -> int:
    errors = validate_register(ctx.config)
    for error in errors:
        _say(f"ERROR {error}")
    register = None if errors else load_register(ctx.config)
    if register is not None:
        _say(
            f"regwatch validate: {len(register.obligations)} obligations, "
            f"{len(register.sources)} sources, "
            f"{len(register.categories)} categories, {len(register.jurisdictions)} jurisdictions, "
            f"{len(register.portfolio.products)} products; errors=0"
        )
        return EXIT_OK
    _say(f"regwatch validate: errors={len(errors)}")
    return EXIT_INVALID


def _cmd_coverage(ctx: _Context, args: argparse.Namespace) -> int:
    register = ctx.register()
    rows: dict[str, int] = {}
    for obligation in register.obligations:
        rows[obligation.jurisdiction] = rows.get(obligation.jurisdiction, 0) + 1
    by_coverage: dict[str, int] = {}
    gaps: list[str] = []
    for jurisdiction in register.jurisdictions:
        by_coverage[jurisdiction.coverage] = by_coverage.get(jurisdiction.coverage, 0) + 1
        count = rows.get(jurisdiction.jurisdiction_id, 0)
        if jurisdiction.coverage == "confirmed" and count == 0:
            gaps.append(
                f"{jurisdiction.jurisdiction_id} is marked confirmed but has no obligation rows"
            )
        _say(
            f"{jurisdiction.coverage:<10} {jurisdiction.jurisdiction_id:<16} "
            f"rows={count:<3} {jurisdiction.name}"
        )
    summary = ", ".join(f"{k}={v}" for k, v in sorted(by_coverage.items()))
    _say(f"regwatch coverage: {len(register.jurisdictions)} jurisdictions; {summary}")
    for gap in gaps:
        _say(f"WARN  {gap}")
    return EXIT_OK


def _cmd_list(ctx: _Context, args: argparse.Namespace) -> int:
    register = ctx.register()
    rows = list(register.obligations)
    if args.jurisdiction:
        rows = [o for o in rows if o.jurisdiction == args.jurisdiction]
    if args.category:
        rows = [o for o in rows if args.category in o.categories]
    if args.status:
        rows = [o for o in rows if o.status == args.status]
    if args.upcoming is not None:
        rows = upcoming_obligations(rows, args.upcoming, ctx.today)
    for o in rows:
        _say(f"{o.effective_date or '(no date)':<11} {o.jurisdiction:<16} {o.status:<11} {o.title}")
    _say(f"regwatch list: {len(rows)} obligations")
    return EXIT_OK


def _cmd_portfolio(ctx: _Context, args: argparse.Namespace) -> int:
    register = ctx.register()
    for product in register.portfolio.products:
        _say(f"{product.product_id:<28} {product.name}")
        _say(
            f"{'':<28} categories: {', '.join(product.categories) or '-'}; "
            f"markets: {', '.join(product.markets)}"
        )
    _say(
        f"regwatch portfolio: {register.portfolio.name}, "
        f"{len(register.portfolio.products)} products"
    )
    return EXIT_OK


# --- source commands ---------------------------------------------------------


def _select_sources(register: Register, source_id: str | None) -> list[Source]:
    sources = list(register.sources)
    if source_id:
        sources = [s for s in sources if s.source_id == source_id]
        if not sources:
            raise CommandError(f"no source '{source_id}' in the register")
    return sources


def _cmd_capture(ctx: _Context, args: argparse.Namespace) -> int:
    register = ctx.register()
    sources = _select_sources(register, args.source)
    results = capture_sources(
        sources,
        ctx.live_fetcher(),
        ctx.config.snapshots_dir,
        ctx.config.register.all_paths(),
        ctx.key_for,
    )
    for r in results:
        label = "captured" if r.captured else "skipped"
        _say(f"{label:<10} {r.source_id:<28} {clean_text(r.detail)}")
    done = sum(1 for r in results if r.captured)
    _say(f"regwatch capture: {done}/{len(results)} sources")
    return EXIT_OK if done else EXIT_INVALID


def _run_check(
    ctx: _Context, register: Register, fetch: bool, source_id: str | None = None
) -> list[SourceResult]:
    seen = load_seen(ctx.config.seen_path)
    fetcher = ctx.live_fetcher() if fetch else None
    return check_sources(
        _select_sources(register, source_id), seen, ctx.config.snapshots_dir, fetcher, ctx.key_for
    )


def _cmd_check(ctx: _Context, args: argparse.Namespace) -> int:
    register = ctx.register()
    results = _run_check(ctx, register, args.fetch, args.source)
    counts: dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
        digest = f"  {r.sha256[:12]}" if r.sha256 else ""
        detail = f"  {clean_text(r.detail)}" if r.detail else ""
        _say(f"{r.status:<10} {r.source_id:<28} {r.origin}{digest}{detail}")
    summary = ", ".join(f"{k.lower()}={v}" for k, v in sorted(counts.items()))
    _say(f"regwatch check: {len(results)} sources; {summary}")
    flagged = [r for r in results if r.flagged]
    if args.accept:
        seen = accept_results(
            load_seen(ctx.config.seen_path),
            results,
            ctx.now,
            accept_suspicious=args.accept_suspicious,
        )
        save_seen(ctx.config.seen_path, seen, ctx.config.register.all_paths())
        _say(f"regwatch check: recorded the accepted baseline in {ctx.config.seen_path}")
    elif flagged:
        _say(
            "regwatch check: changes detected; review them, "
            "then run again with --accept to record the baseline"
        )
    if any(r.status == "SUSPICIOUS" for r in results) and not args.accept_suspicious:
        _say(
            "regwatch check: SUSPICIOUS sources are not accepted unless you add --accept-suspicious"
        )
    _say(NOTICE)
    if args.exit_code and any(r.needs_attention for r in results):
        return EXIT_UNVERIFIED
    return EXIT_CHANGES if (flagged and args.exit_code) else EXIT_OK


def _cmd_ingest(ctx: _Context, args: argparse.Namespace) -> int:
    settings = ctx.config.ingest
    since = (ctx.today - dt.timedelta(days=args.since)).isoformat()
    if args.from_file:
        path = Path(args.from_file)
        if path.stat().st_size > MAX_INPUT_BYTES:
            raise CommandError(f"{path} is larger than {MAX_INPUT_BYTES} bytes")
        text, origin = path.read_text(encoding="utf-8"), "file"
    elif args.fetch:
        text, origin = ctx.live_fetcher().fetch(build_query_url(settings, since)), "live"
    else:
        raise CommandError("ingest needs --fetch or --from-file")
    candidates = parse_candidates(text, settings, ctx.today)
    ctx.write_state(
        ctx.config.candidates_path,
        json.dumps(candidates_document(candidates, ctx.today, origin), indent=2) + "\n",
    )
    _say(f"regwatch ingest: {len(candidates)} candidate events from {origin} (since {since})")
    _say(f"regwatch ingest: wrote {ctx.config.candidates_path} (unconfirmed, for review)")
    _say(NOTICE)
    return EXIT_OK


# --- analysis commands -------------------------------------------------------


def _cmd_impact(ctx: _Context, args: argparse.Namespace) -> int:
    register = ctx.register()
    focus = ctx.focus()
    impacts = assess_impacts(register, ctx.today, focus)
    if args.product:
        impacts = [i for i in impacts if i.product_id == args.product]
    if args.severity:
        impacts = [i for i in impacts if i.severity == args.severity]
    in_focus = [i for i in impacts if i.in_focus]
    outside = [i for i in impacts if not i.in_focus]
    _print_impacts(in_focus)
    if outside:
        _say()
        _say(f"Outside your focus areas ({len(outside)}, listed after the items above):")
        _print_impacts(outside)
    summary = (
        f"regwatch impact: {len(impacts)} candidate impacts across "
        f"{len(register.portfolio.products)} products"
    )
    if focus.active:
        summary += f"; {len(in_focus)} in your focus areas, {len(outside)} outside"
    _say(summary)
    _say(NOTICE)
    return EXIT_OK


def _print_impacts(impacts: list[Impact]) -> None:
    for i in impacts:
        _say(
            f"{i.severity:<8} {i.product_id:<24} {i.jurisdiction:<14} "
            f"{i.effective_date or 'no date':<11} "
            f"{i.obligation_title}"
        )
        _say(f"{'':<8} {'; '.join(i.reasons)}")


def _cmd_themes(ctx: _Context, args: argparse.Namespace) -> int:
    register = ctx.register()
    findings = theme_findings(register, assess_impacts(register, ctx.today), register.themes)
    for f in findings:
        _say(f"## {f.title}")
        _say(f.why)
        if f.affected_products:
            _say("Affected products: " + ", ".join(f.affected_products))
        if f.obligations:
            _say("Related obligations: " + ", ".join(f.obligations))
        _say("Action: " + f.action)
        _say()
    _say(f"regwatch themes: {len(findings)} findings")
    _say(NOTICE)
    return EXIT_OK


def _load_candidates(ctx: _Context) -> list[dict[str, Any]]:
    path = ctx.config.candidates_path
    if not path.exists():
        return []
    try:
        if path.stat().st_size > MAX_STATE_BYTES:
            raise StateError(f"{path} is larger than {MAX_STATE_BYTES} bytes")
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise StateError(f"cannot read {path}: {exc}") from exc
    items = data.get("candidates", []) if isinstance(data, dict) else []
    return [item for item in items if isinstance(item, dict)]


def _write_document(ctx: _Context, doc: Document, out_dir: str | None, stem: str) -> None:
    if out_dir is None:
        sys.stdout.write(render_markdown(doc))
        return
    directory = Path(out_dir)
    ctx.write_text(directory / f"{stem}.md", render_markdown(doc))
    ctx.write_text(directory / f"{stem}.json", json.dumps(doc.to_dict(), indent=2) + "\n")
    _say(f"wrote {directory / f'{stem}.md'}")
    _say(f"wrote {directory / f'{stem}.json'}")


def _cmd_brief(ctx: _Context, args: argparse.Namespace) -> int:
    register = ctx.register()
    focus = ctx.focus()
    impacts = assess_impacts(register, ctx.today, focus)
    if args.kind == "daily":
        results = _run_check(ctx, register, args.fetch)
        doc = daily_brief(register, results, impacts, ctx.today)
        stem = "regwatch-daily-brief"
    elif args.kind == "weekly":
        findings = theme_findings(register, impacts, register.themes)
        doc = weekly_synthesis(register, impacts, findings, ctx.today)
        stem = "regwatch-weekly-brief"
    else:
        doc = build_briefing(
            register,
            impacts,
            ctx.today,
            tier=args.tier,
            recent_count=args.recent,
            since_days=args.since_days,
            candidates=_load_candidates(ctx),
            focus=focus,
        )
        stem = f"regwatch-briefing-{args.tier}"
    name = args.name if args.name is not None else stem
    if not NAME_RE.fullmatch(name):
        raise CommandError("--name may contain only letters, digits, dots, hyphens and underscores")
    _write_document(ctx, doc, args.out_dir, name)
    return EXIT_OK


def _cmd_render(ctx: _Context, args: argparse.Namespace) -> int:
    model_path = Path(args.model)
    if model_path.stat().st_size > MAX_INPUT_BYTES:
        raise CommandError(f"{model_path} is larger than {MAX_INPUT_BYTES} bytes")
    try:
        doc = Document.from_dict(json.loads(model_path.read_text(encoding="utf-8")))
    except (ValueError, RecursionError) as exc:
        raise DocumentError(f"{model_path} is not a valid document model: {exc}") from exc
    formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    unknown = [f for f in formats if f not in FORMATS]
    if unknown or not formats:
        raise CommandError(
            f"unknown formats {unknown or ['(none)']}; choose from {', '.join(FORMATS)}"
        )
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    if not all(TAG_RE.fullmatch(t) for t in tags):
        raise CommandError("tags may contain only letters, digits, hyphens and underscores")
    directory = Path(args.out_dir)
    stem = model_path.stem
    written: list[Path] = []

    def put(name: str, content: str | bytes) -> None:
        path = directory / name
        if isinstance(content, bytes):
            ctx.write_bytes(path, content)
        else:
            ctx.write_text(path, content)
        written.append(path)

    if "md" in formats:
        put(f"{stem}.md", render_markdown(doc))
    if "web" in formats:
        put(f"{stem}-webpost.md", render_webpost(doc, tags))
    if "newsletter" in formats:
        put(f"{stem}-newsletter.html", render_newsletter_html(doc))
        put(f"{stem}-newsletter.txt", render_newsletter_text(doc))
    if "docx" in formats:
        put(f"{stem}.docx", docx_bytes(doc))
    for path in written:
        _say(f"wrote {path}")
    _say(f"regwatch render: {len(written)} files")
    return EXIT_OK


def _cmd_digest(ctx: _Context, args: argparse.Namespace) -> int:
    register = ctx.register()
    upcoming = upcoming_obligations(register.obligations, args.window, ctx.today)
    names = {j.jurisdiction_id: j.name for j in register.jurisdictions}
    sections = [
        Section(
            f"Effective Within {args.window} Days",
            paragraphs=[] if upcoming else ["None."],
            bullets=[
                f"{o.effective_date}, {o.jurisdiction}: {o.title} ({o.status})" for o in upcoming
            ],
        )
    ]
    by_jurisdiction: dict[str, list[Any]] = {}
    for o in register.obligations:
        by_jurisdiction.setdefault(o.jurisdiction, []).append(o)
    sections.append(Section("Register By Jurisdiction"))
    for jid in sorted(by_jurisdiction):
        bullets = [
            f"{o.title}: {o.status}, {o.effective_date or 'no date'}"
            for o in sorted(by_jurisdiction[jid], key=lambda o: o.title)
        ]
        sections.append(Section(names.get(jid, jid), level=3, bullets=bullets))
    doc = Document(
        "regwatch digest",
        ctx.today.isoformat(),
        "Register digest for analyst review",
        sections,
        make_disclaimer(register.portfolio.disclaimer),
    )
    _emit(ctx, render_markdown(doc), args.out, "digest")
    return EXIT_OK


def _emit(ctx: _Context, text: str, out: str | None, label: str) -> None:
    if out:
        ctx.write_text(Path(out), text)
        _say(f"regwatch {label}: wrote {out}")
    else:
        sys.stdout.write(text)


def _cmd_report(ctx: _Context, args: argparse.Namespace) -> int:
    register = ctx.register()
    results = _run_check(ctx, register, args.fetch)
    flagged = [r for r in results if r.flagged]
    missing = [r for r in results if r.status == "MISSING"]
    errors = [r for r in results if r.status == "ERROR"]
    upcoming = upcoming_obligations(register.obligations, args.window, ctx.today)

    changes = Section("Source Changes To Review")
    if flagged:
        changes.bullets = [f"{r.status}: {r.source_id} ({r.origin})" for r in flagged]
    else:
        changes.paragraphs.append("No source changes since the last accepted state.")
    if missing:
        changes.paragraphs.append(
            f"{len(missing)} source(s) have no snapshot; capture one or use --fetch."
        )
    changes.bullets += [f"ERROR: {r.source_id} ({r.detail})" for r in errors]
    due = Section(
        f"Obligations Effective Within {args.window} Days",
        paragraphs=[] if upcoming else ["None."],
        bullets=[f"{o.effective_date}, {o.jurisdiction}: {o.title} ({o.status})" for o in upcoming],
    )
    doc = Document(
        "regwatch report",
        ctx.today.isoformat(),
        "Change and due alert",
        [changes, due],
        make_disclaimer(register.portfolio.disclaimer),
    )
    _emit(ctx, render_markdown(doc), args.out, "report")
    if args.json:
        payload = {
            "generated": ctx.today.isoformat(),
            "window_days": args.window,
            "source_changes": [
                {
                    "source_id": r.source_id,
                    "status": r.status,
                    "origin": r.origin,
                    "sha256": r.sha256,
                }
                for r in flagged
            ],
            "sources_missing_snapshot": [r.source_id for r in missing],
            "source_errors": [
                {"source_id": r.source_id, "detail": clean_text(r.detail)} for r in errors
            ],
            "upcoming": [
                {
                    "obligation_id": o.obligation_id,
                    "jurisdiction": o.jurisdiction,
                    "title": o.title,
                    "status": o.status,
                    "effective_date": o.effective_date,
                }
                for o in upcoming
            ],
            "disclaimer": doc.disclaimer,
        }
        ctx.write_text(Path(args.json), json.dumps(payload, indent=2) + "\n")
        _say(f"regwatch report: wrote {args.json}")
    if flagged:
        _say(
            f"regwatch report: {len(flagged)} source change(s) flagged for review", file=sys.stderr
        )
    return EXIT_OK


def _cmd_export(ctx: _Context, args: argparse.Namespace) -> int:
    records = build_records(ctx.register())
    ctx.write_text(Path(args.csv), records_csv(records))
    _say(f"regwatch export: wrote {args.csv} ({len(records)} records)")
    if args.json:
        ctx.write_text(Path(args.json), json.dumps(records, indent=2) + "\n")
        _say(f"regwatch export: wrote {args.json}")
    return EXIT_OK


# --- onboarding commands -----------------------------------------------------

_T = TypeVar("_T")
YES = ("y", "yes")


def _prompt(question: str) -> str:
    try:
        return input(clean_line(question)).strip()
    except EOFError as exc:
        raise CommandError(
            "no answer is available on standard input; give each answer as a flag, or add --yes"
        ) from exc


def _ask(question: str, parse: Callable[[str], _T]) -> _T:
    """Ask until ``parse`` accepts the answer, explaining each refusal."""
    while True:
        answer = _prompt(question)
        try:
            return parse(answer)
        except OnboardingError as exc:
            _say(f"  {exc}", file=sys.stderr)


def _comma_list(answer: str) -> list[str]:
    return [item.strip() for item in answer.split(",") if item.strip()]


def _init_directory(args: argparse.Namespace) -> Path:
    home = Path.home()
    if args.dir is not None:
        return check_directory(args.dir, home)
    here = Path.cwd().resolve()
    if here == home.resolve():
        if args.yes:
            raise CommandError("this is your home directory; name the project folder with --dir")
        _say("You are in your home directory, so regwatch will not assume a project folder.")
        return _ask(
            "Project folder (created if it does not exist): ", lambda a: check_directory(a, home)
        )
    if args.yes:
        return here
    return _ask(f"Project folder [{here}]: ", lambda a: check_directory(a or str(here), home))


def _refuse_existing(directory: Path, force: bool) -> list[str]:
    """Names of scaffold files that already exist. Raises unless ``force`` allows replacing them."""
    existing: list[str] = []
    for name in SCAFFOLD_NAMES:
        path = directory / name
        for part in (path, path.parent):
            if part != directory and part.is_symlink():
                raise CommandError(f"{part} is a symbolic link; init will not write through it")
        if os.path.lexists(path):
            existing.append(name)
    if existing and not force:
        raise CommandError(
            f"these files already exist in {directory} and were left unchanged: "
            f"{', '.join(existing)}; add --force to replace them"
        )
    return existing


def _write_scaffold(directory: Path, files: Mapping[str, str], *, replace: bool) -> None:
    """Write the scaffold.

    Without ``replace`` no file may exist yet; each is created exclusively.
    """
    try:
        write_tree(directory, files, replace=replace)
    except AlreadyExistsError as exc:
        raise CommandError(
            f"{exc} (it appeared while init was running) and was left unchanged; "
            "add --force to replace it"
        ) from exc


def _ask_focus(args: argparse.Namespace) -> tuple[str, ...]:
    catalogue = load_catalogue(None)
    if args.focus is not None:
        return parse_focus_choice(args.focus, catalogue)
    if args.yes:
        return ()
    _say("Focus areas in the catalogue:")
    for number, area in enumerate(catalogue, start=1):
        _say(f"  {number}. {area.focus_id}: {area.label}. {area.description}")
    return _ask(
        "Which apply to your business? Numbers or ids, separated by commas; Enter for none: ",
        lambda a: parse_focus_choice(_comma_list(a), catalogue),
    )


def _ask_terms(args: argparse.Namespace) -> tuple[str, ...]:
    if args.term is not None:
        return clean_terms(args.term)
    if args.yes:
        return ()
    return _ask(
        "Extra words that matter to you, separated by commas; Enter for none: ",
        lambda a: clean_terms(_comma_list(a)),
    )


def _ask_jurisdictions(args: argparse.Namespace) -> tuple[dict[str, str], ...]:
    offered = example_jurisdictions() if args.example else ()
    if args.jurisdiction is not None:
        return jurisdiction_records(args.jurisdiction)
    if args.yes:
        return offered
    hint = "Enter for none"
    if offered:
        hint = "Enter for the invented example set: " + ", ".join(j["name"] for j in offered)
    return _ask(
        f"Jurisdictions to watch, separated by commas; {hint}: ",
        lambda a: jurisdiction_records(_comma_list(a)) if a else offered,
    )


def _ask_file_roots(args: argparse.Namespace, directory: Path) -> tuple[str, ...]:
    home = Path.home()

    def roots(answer: str) -> tuple[str, ...]:
        found = tuple(check_file_root(item, directory, home) for item in _comma_list(answer))
        if not found:
            raise OnboardingError("name at least one folder")
        return found

    if args.allow_file_root is not None:
        return tuple(check_file_root(item, directory, home) for item in args.allow_file_root)
    if args.yes:
        return ()
    answer = _prompt("Allow regwatch to read local files as sources? Default is no. [y/N]: ")
    if answer.lower() not in YES:
        return ()
    return _ask("Folders it may read from, separated by commas: ", roots)


def _ask_contact(args: argparse.Namespace) -> str:
    if args.contact is not None:
        return check_contact(args.contact)
    if args.yes:
        return ""
    return _ask(
        "Contact for the User-Agent header, an email address or web page that tells site owners "
        "who runs this; Enter keeps the default: ",
        lambda a: check_contact(a) if a else "",
    )


def _summary(plan: InitPlan, names: Sequence[str], existing: Sequence[str]) -> list[str]:
    catalogue = {area.focus_id: area.label for area in load_catalogue(None)}
    areas = [catalogue.get(focus_id, focus_id) for focus_id in plan.focus_areas]
    lines = [f"regwatch init will write {len(names)} files in {plan.directory}:"]
    lines += [
        f"  {name}" + ("  (replaces an existing file)" if name in existing else "")
        for name in names
    ]
    lines += [
        f"Focus areas: {', '.join(areas) or 'none'}",
        f"Custom terms: {', '.join(plan.custom_terms) or 'none'}",
        f"Jurisdictions: {', '.join(j['name'] for j in plan.jurisdictions) or 'none'}",
        f"Local file sources: {', '.join(plan.file_roots) if plan.file_roots else 'not allowed'}",
        f"User agent: {user_agent_for(plan.contact) if plan.contact else 'the default'}",
        f"Sources: {', '.join(e.source_id for e in plan.sources) or 'none'}",
    ]
    return lines


# --- init: choosing sources ---------------------------------------------------

PICK_LIMIT = 20
_REGION_NAMES = {
    "north-america": "North America",
    "latin-america": "Latin America",
    "europe": "Europe",
    "asia-pacific": "Asia Pacific",
    "middle-east-africa": "Middle East and Africa",
    "global": "Global",
}


def _title(identifier: str) -> str:
    """``policy-and-lobbying`` as ``Policy and Lobbying``."""
    words = identifier.split("-")
    return " ".join(
        word if index and word in ("and", "of") else word.capitalize()
        for index, word in enumerate(words)
    )


def _source_line(number: int, entry: CatalogueEntry, chosen: Mapping[str, CatalogueEntry]) -> str:
    mark = "x" if entry.source_id in chosen else " "
    return (
        f"  {number:>3}. [{mark}] {entry.name} ({entry.access_label}), {entry.source_id}: "
        f"{entry.description}"
    )


def _show_grouped(
    entries: Sequence[CatalogueEntry], chosen: Mapping[str, CatalogueEntry]
) -> list[CatalogueEntry]:
    """Print ``entries`` grouped by category, then region, numbered. Returns them in that order."""
    order = {category: index for index, category in enumerate(CATEGORIES)}
    regions = {region: index for index, region in enumerate(REGIONS)}
    ordered = sorted(entries, key=lambda e: (order.get(e.category, 99), regions.get(e.region, 99)))
    heading = ""
    for number, entry in enumerate(ordered, start=1):
        current = f"{_title(entry.category)}, {_REGION_NAMES.get(entry.region, entry.region)}"
        if current != heading:
            heading = current
            _say(f"{heading}:")
        _say(_source_line(number, entry, chosen))
    return ordered


def _show_numbered(
    entries: Sequence[CatalogueEntry], chosen: Mapping[str, CatalogueEntry]
) -> list[CatalogueEntry]:
    shown = list(entries[:PICK_LIMIT])
    for number, entry in enumerate(shown, start=1):
        _say(_source_line(number, entry, chosen))
    if len(entries) > PICK_LIMIT:
        _say(f"  ... and {len(entries) - PICK_LIMIT} more; type more words to narrow the search")
    if not shown:
        _say("  no source matches; try other words, or + to add one that is not listed")
    return shown


def _toggle_tokens(
    answer: str, shown: Sequence[CatalogueEntry], by_id: Mapping[str, CatalogueEntry]
) -> list[CatalogueEntry] | None:
    """The entries an answer names by number or id, or None when it is a search instead."""
    tokens = [token for token in re.split(r"[\s,]+", answer) if token]
    picked: list[CatalogueEntry] = []
    for token in tokens:
        if token.isdecimal() and 1 <= int(token) <= len(shown):
            picked.append(shown[int(token) - 1])
        elif token in by_id:
            picked.append(by_id[token])
        else:
            return None
    return picked


def _ask_custom_source(
    by_id: Mapping[str, CatalogueEntry], today: dt.date
) -> CatalogueEntry | None:
    """Ask for the fields of a source the catalogue lacks. None when an answer is unusable."""
    _say("Add a source that is not listed. Each answer is checked like a catalogue entry.")
    answers = {
        "source_id": _prompt("  Id, lowercase words joined by hyphens, such as us-my-feed: "),
        "name": _prompt("  Name: "),
        "jurisdiction": _prompt("  Jurisdiction code, such as us, us-ca, eu or intl: ").lower(),
        "url": _prompt("  https address to watch: "),
        "mechanism": _prompt(f"  Mechanism, one of {', '.join(MECHANISMS)} [html]: ") or "html",
        "cadence": _prompt("  Cadence, hourly, daily or weekly [daily]: ") or "daily",
        "description": _prompt("  One sentence on what it publishes: "),
    }
    data: dict[str, Any] = {
        **answers,
        "publisher": answers["name"],
        "region": "global",
        "kind": "regulator",
        "category": "regulation",
        "homepage": answers["url"],
        "access": "free",
        "auth": None,
        "key_env": None,
        "signup_url": None,
        "focus_areas": [],
        "language": "en",
        "verified": False,
        "checked": today.isoformat(),
        "notes": "Added during regwatch init.",
    }
    try:
        entry = entry_from_dict({key: data[key] for key in FIELDS}, (), "the new source")
    except CatalogueError as exc:
        _say(f"  {exc}", file=sys.stderr)
        return None
    if entry.source_id in by_id:
        _say(
            f"  {entry.source_id} is already in the catalogue; choose it by its id", file=sys.stderr
        )
        return None
    return entry


class _Completer:
    """Readline completion of catalogue ids and names, used only on a terminal."""

    def __init__(self, entries: Sequence[CatalogueEntry]) -> None:
        self.words = sorted({e.source_id for e in entries} | {e.name for e in entries})
        self.matches: list[str] = []

    def __call__(self, text: str, state: int) -> str | None:
        if state == 0:
            low = text.lower()
            self.matches = [w for w in self.words if w.lower().startswith(low)]
        return self.matches[state] if state < len(self.matches) else None


def _with_completion(ctx: _Context, entries: Sequence[CatalogueEntry]) -> Callable[[], None]:
    """Turn on completion when standard input is a terminal; return the function that undoes it."""
    if not ctx.system.stdin_is_terminal():
        return lambda: None
    try:
        import readline
    except ImportError:  # pragma: no cover (every supported platform has readline)
        return lambda: None
    previous, delims = readline.get_completer(), readline.get_completer_delims()
    readline.set_completer(_Completer(entries))
    readline.set_completer_delims(",")
    readline.parse_and_bind("tab: complete")

    def restore() -> None:
        readline.set_completer(previous)
        readline.set_completer_delims(delims)

    return restore


def _pick_sources(
    ctx: _Context, catalogue: Sequence[CatalogueEntry], matches: Sequence[CatalogueEntry]
) -> tuple[CatalogueEntry, ...]:
    by_id = {entry.source_id: entry for entry in catalogue}
    chosen: dict[str, CatalogueEntry] = {}
    _say(f"Sources that match your focus areas and jurisdictions ({len(matches)}):")
    shown = _show_grouped(matches, chosen)
    restore = _with_completion(ctx, catalogue)
    try:
        while True:
            answer = _prompt(
                "Sources: numbers or ids to select or unselect, words to search, "
                "+ to add one not listed, Enter when done: "
            )
            if not answer:
                break
            if answer == "+":
                entry = _ask_custom_source(by_id, ctx.today)
                if entry is not None:
                    chosen[entry.source_id] = entry
                    _say(f"  added {entry.source_id}")
                continue
            picked = _toggle_tokens(answer, shown, by_id)
            if picked is None:
                shown = _show_numbered(rank(catalogue, answer), chosen)
                continue
            for entry in picked:
                if chosen.pop(entry.source_id, None) is None:
                    chosen[entry.source_id] = entry
                    _say(f"  selected {entry.source_id} ({entry.access_label})")
                else:
                    _say(f"  unselected {entry.source_id}")
    finally:
        restore()
    return tuple(chosen.values())


def _ask_sources(
    ctx: _Context,
    args: argparse.Namespace,
    focus_areas: Sequence[str],
    jurisdictions: Sequence[dict[str, str]],
) -> tuple[CatalogueEntry, ...]:
    catalogue = load_source_catalogue([area.focus_id for area in load_catalogue(None)])
    if args.sources is not None:
        by_id = {entry.source_id: entry for entry in catalogue}
        ids = list(dict.fromkeys(_comma_list(args.sources)))
        unknown = [source_id for source_id in ids if source_id not in by_id]
        if unknown:
            raise CommandError(f"not in the source catalogue: {', '.join(unknown)}")
        return tuple(by_id[source_id] for source_id in ids)
    if args.yes:
        return ()
    return _pick_sources(ctx, catalogue, matching_entries(catalogue, focus_areas, jurisdictions))


# --- init: after writing ------------------------------------------------------


def _offer(question: str) -> bool:
    """Ask a yes or no question after the files are written. A closed input means no."""
    try:
        return _prompt(question).lower() in YES
    except CommandError:
        return False


def _init_keys(ctx: _Context, args: argparse.Namespace, entries: Sequence[CatalogueEntry]) -> None:
    store = ctx.keystore()
    for entry in entries:
        if entry.key_env is None:
            continue
        _say(f"{entry.source_id} needs a key ({entry.access_label}).")
        if entry.signup_url:
            _say(f"  Get one at {entry.signup_url}")
        if store.status(entry.key_env).present:
            _say("  A key is already available.")
            continue
        if (
            args.yes
            or store.backend is None
            or not _offer(f"  Store the key for {entry.source_id} now? [y/N]: ")
        ):
            _say(f"  Later, run: regwatch --config {ctx.config_path} keys set {entry.source_id}")
            _say(f"  or set the environment variable {entry.key_env}.")
            continue
        try:
            value = ctx.system.read_secret(clean_line(f"  Key for {entry.source_id} (not shown): "))
            store.set(entry.key_env, value.strip())
        except (EOFError, KeyStoreError) as exc:
            reason = str(exc) if isinstance(exc, KeyStoreError) else "no key was given"
            _say(f"  {reason}; run 'regwatch keys set {entry.source_id}' later", file=sys.stderr)
            continue
        _say(f"  Stored in {store.backend_label}.")


def _init_after(ctx: _Context, args: argparse.Namespace, plan: InitPlan) -> int:
    project = _Context(
        config_path=plan.directory / SCAFFOLD_NAMES[0],
        fetcher=ctx.fetcher,
        today=ctx.today,
        now=ctx.now,
        system=ctx.system,
        clock=ctx.clock,
    )
    _init_keys(project, args, plan.sources)
    schedule = args.schedule
    if schedule is None:
        schedule = not args.yes and _offer(
            "Run capture and check on a schedule (launchd on macOS, cron elsewhere)? [y/N]: "
        )
    if schedule:
        _cmd_schedule(
            project,
            argparse.Namespace(install=True, remove=False, every=None, dry_run=False, show=False),
        )
    else:
        _say(f"To schedule runs later: regwatch --config {project.config_path} schedule --install")
    first = args.first_run
    if first is None:
        first = (
            not args.yes
            and bool(plan.sources)
            and _offer("Run a first capture and check now? [y/N]: ")
        )
    if first:
        return _cmd_run(project, argparse.Namespace())
    return EXIT_OK


def _cmd_init(ctx: _Context, args: argparse.Namespace) -> int:
    directory = _init_directory(args)
    existing = _refuse_existing(directory, args.force)
    focus_areas = _ask_focus(args)
    custom_terms = _ask_terms(args)
    jurisdictions = _ask_jurisdictions(args)
    sources = _ask_sources(ctx, args, focus_areas, jurisdictions)
    plan = InitPlan(
        directory=directory,
        focus_areas=focus_areas,
        custom_terms=custom_terms,
        jurisdictions=jurisdictions,
        file_roots=_ask_file_roots(args, directory),
        contact=_ask_contact(args),
        sources=sources,
    )
    files = scaffold_files(plan)
    _say()
    for line in _summary(plan, list(files), existing):
        _say(line)
    if not args.yes and _prompt("Create these files? [y/N]: ").lower() not in YES:
        raise CommandError("cancelled; nothing was written")
    # The questions can take a long time. Look again right before writing, so a file
    # or a link that appeared meanwhile is not replaced or followed.
    _refuse_existing(directory, args.force)
    _write_scaffold(directory, files, replace=args.force)
    _say(f"regwatch init: wrote {len(files)} files in {directory}")
    code = _init_after(ctx, args, plan)
    _say("Next, describe your products in register/portfolio.json, choose more sources with")
    _say("'regwatch sources', then check the register:")
    _say(f"  regwatch --config {directory / SCAFFOLD_NAMES[0]} validate")
    _say(NOTICE)
    return code


def _cmd_config(ctx: _Context, args: argparse.Namespace) -> int:
    config = ctx.config
    focus = build_profile(config.profile)

    def text(value: object) -> str:
        return json.dumps(value if not isinstance(value, Path) else str(value))

    def row(key: str, value: object) -> None:
        _say(f"{key} = {text(value)}")

    _say(f"# effective configuration from {config.config_path}")
    _say("[register]")
    for key in ("obligations", "jurisdictions", "categories", "sources", "portfolio"):
        row(key, getattr(config.register, key))
    for key in ("detail", "changelog", "enforcement", "themes"):
        if getattr(config.register, key) is not None:
            row(key, getattr(config.register, key))
    _say("[state]")
    row("dir", config.state_dir)
    row("snapshots", config.snapshots_dir)
    _say("[fetch]")
    fetch = config.fetch
    row("timeout_seconds", fetch.timeout_seconds)
    row("total_timeout_seconds", fetch.total_timeout_seconds)
    row("max_bytes", fetch.max_bytes)
    row("user_agent", fetch.user_agent)
    row("allow_private_hosts", fetch.allow_private_hosts)
    row("allowed_file_roots", [str(root) for root in fetch.allowed_file_roots])
    if not fetch.allowed_file_roots:
        _say("# no folders are listed, so every file source is refused")
    _say("[ingest]")
    settings = config.ingest
    row("api_url", settings.api_url)
    row("agencies", list(settings.agencies))
    row("types", list(settings.types))
    row("cfr_title", settings.cfr_title if settings.cfr_title is not None else "none")
    row("cfr_parts", list(settings.cfr_parts))
    row("terms", list(settings.terms))
    row("jurisdiction", settings.jurisdiction)
    row("per_page", settings.per_page)
    _say("[profile]")
    row("focus_areas", list(config.profile.focus_areas))
    row("custom_terms", list(config.profile.custom_terms))
    row(
        "catalogue",
        config.profile.catalogue if config.profile.catalogue else "shipped with regwatch",
    )
    _say("[premium]")
    row("enabled", config.premium.enabled)
    for area in focus.areas:
        _say(f"# focus area {area.focus_id}: {area.label}, {len(area.terms)} terms")
    if not focus.active:
        _say("# no focus areas are set, so every candidate counts as in focus")
    return EXIT_OK


# --- source catalogue commands -----------------------------------------------


def _source_catalogue(ctx: _Context) -> tuple[CatalogueEntry, ...]:
    """The shipped catalogue plus the user's extra file when a configuration names one."""
    return source_catalogue(ctx.config if ctx.config_path.exists() else None)


def _chosen_ids(ctx: _Context) -> list[str]:
    """The ids in the user's sources file."""
    return chosen_ids(ctx.config)


def _entry_line(entry: CatalogueEntry) -> str:
    return (
        f"{entry.source_id:<34} {entry.access_label:<8} {entry.jurisdiction:<6} "
        f"{entry.category:<22} {entry.name}"
    )


def _print_entries(entries: Sequence[CatalogueEntry], as_json: bool, label: str) -> None:
    if as_json:
        payload = {"count": len(entries), "sources": [entry.to_dict() for entry in entries]}
        sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        return
    for entry in entries:
        _say(_entry_line(entry))
    _say(f"regwatch sources {label}: {len(entries)} sources")


def _cmd_sources_list(ctx: _Context, args: argparse.Namespace) -> int:
    entries = filter_entries(
        _source_catalogue(ctx),
        region=args.region,
        jurisdiction=args.jurisdiction,
        kind=args.kind,
        category=args.category,
        access=args.access,
        focus=args.focus,
        chosen=_chosen_ids(ctx) if args.chosen else None,
    )
    _print_entries(entries, args.json, "list")
    return EXIT_OK


def _cmd_sources_search(ctx: _Context, args: argparse.Namespace) -> int:
    _print_entries(rank(_source_catalogue(ctx), args.text), args.json, "search")
    return EXIT_OK


def _find_entries(ctx: _Context, ids: Sequence[str]) -> list[CatalogueEntry]:
    return find_entries(_source_catalogue(ctx), ids)


def _cmd_sources_show(ctx: _Context, args: argparse.Namespace) -> int:
    entry = _find_entries(ctx, [args.id])[0]
    if args.json:
        sys.stdout.write(json.dumps(entry.to_dict(), indent=2, ensure_ascii=False) + "\n")
        return EXIT_OK
    _say(f"{entry.name} ({entry.access_label})")
    _say(entry.description)
    rows = [
        ("id", entry.source_id),
        ("publisher", entry.publisher),
        ("jurisdiction", entry.jurisdiction),
        ("region", entry.region),
        ("kind", entry.kind),
        ("category", entry.category),
        ("mechanism", entry.mechanism),
        ("url", entry.url),
        ("homepage", entry.homepage),
        ("access", entry.access),
        ("auth", entry.auth.to_text() if entry.auth else "none"),
        ("key variable", entry.key_env or "none"),
        ("sign up", entry.signup_url or "none"),
        ("focus areas", ", ".join(entry.focus_areas) or "all"),
        ("language", entry.language),
        ("cadence", entry.cadence),
        ("verified", f"{'yes' if entry.verified else 'no'}, checked {entry.checked}"),
        ("notes", entry.notes or "none"),
    ]
    for key, value in rows:
        _say(f"  {key + ':':<14} {value}")
    return EXIT_OK


def _write_register_list(ctx: _Context, path: Path, data: dict[str, Any]) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    update_register_file(path, text, ctx.config.register.all_paths())


def _cmd_sources_add(ctx: _Context, args: argparse.Namespace) -> int:
    entries = _find_entries(ctx, args.ids)
    paths = ctx.config.register
    merged = add_sources(ctx.config, entries)
    for code in merged.added_jurisdictions:
        _say(f"added      jurisdiction {code} to {paths.jurisdictions}")
    for entry in entries:
        state = "added" if entry.source_id in merged.added else "present"
        _say(f"{state:<10} {entry.source_id:<34} {entry.access_label:<8} {entry.name}")
    _say(f"regwatch sources add: {len(merged.added)} added, {len(merged.present)} already present")
    for entry in entries:
        if entry.keyed and not ctx.key_for(str(entry.key_env)):
            _say(f"{entry.source_id} needs a key: run 'regwatch keys set {entry.source_id}'")
    return EXIT_OK


def _cmd_sources_remove(ctx: _Context, args: argparse.Namespace) -> int:
    path = ctx.config.register.sources
    data, sources = read_json_list(path, "sources", "sources file")
    kept = [s for s in sources if str(s.get("source_id", "")) != args.id]
    if len(kept) == len(sources):
        raise CommandError(f"no source '{args.id}' in {path}")
    citing = obligations_citing_source(ctx.config, args.id)
    if citing:
        raise CommandError(
            f"obligations cite source '{args.id}': {', '.join(citing)}; "
            "change their source_id first"
        )
    _write_register_list(ctx, path, {**data, "sources": kept})
    _say(f"regwatch sources remove: removed {args.id} from {path}")
    _say("Its snapshot and accepted hash stay in the state directory until you delete them.")
    return EXIT_OK


def _cmd_sources_verify(ctx: _Context, args: argparse.Namespace) -> int:
    entries = _find_entries(ctx, args.ids) if args.ids else list(_source_catalogue(ctx))
    fetcher = ctx.live_fetcher()
    failed = 0
    for entry in entries:
        try:
            key = ctx.key_for(entry.key_env) if entry.auth and entry.key_env else None
            if entry.auth is not None and key:
                credential = Credential(entry.auth.type, entry.auth.name, key)
                body = fetcher.fetch(entry.url, credential=credential)
            else:
                body = fetcher.fetch(entry.url)
        except (FetchError, ValueError) as exc:
            failed += 1
            _say(f"{'failed':<8} {entry.source_id:<34} {exc}")
            continue
        _say(f"{'ok':<8} {entry.source_id:<34} {len(body.encode('utf-8'))} bytes")
    _say(f"regwatch sources verify: {len(entries) - failed} ok, {failed} failed")
    _say("The catalogue is not changed; a failure means the address needs checking.")
    return EXIT_UNVERIFIED if failed else EXIT_OK


# --- keys --------------------------------------------------------------------


def _keyed_sources(ctx: _Context) -> list[KeyedSource]:
    return keyed_sources(ctx.config if ctx.config_path.exists() else None, _source_catalogue(ctx))


def _keyed_source(ctx: _Context, source_id: str) -> KeyedSource:
    return keyed_source(
        ctx.config if ctx.config_path.exists() else None, _source_catalogue(ctx), source_id
    )


def _cmd_keys_set(ctx: _Context, args: argparse.Namespace) -> int:
    item = _keyed_source(ctx, args.source_id)
    store = ctx.keystore()
    if store.backend is None:
        raise CommandError(
            "no keychain tool was found (security on macOS, secret-tool from libsecret on "
            f"Linux); set the environment variable {item.key_env} to supply the key instead"
        )
    if item.signup_url:
        _say(f"Get a key for {item.source_id} at {item.signup_url}")
    try:
        value = ctx.system.read_secret(clean_line(f"Key for {item.source_id} (not shown): "))
    except EOFError as exc:
        raise CommandError("no key was given; nothing was stored") from exc
    store.set(item.key_env, value.strip())
    _say(f"regwatch keys: stored the key for {item.source_id} in {store.backend_label}")
    return EXIT_OK


def _cmd_keys_list(ctx: _Context, args: argparse.Namespace) -> int:
    store = ctx.keystore()
    items = _keyed_sources(ctx)
    labels = {
        "environment": "set in the environment",
        "keychain": "stored",
        "missing": "missing",
        "unavailable": "missing (no keychain tool)",
    }
    for item in items:
        status = store.status(item.key_env)
        _say(f"{labels[status.source]:<27} {item.source_id:<34} {item.key_env}")
    present = sum(1 for item in items if store.status(item.key_env).present)
    _say(
        f"regwatch keys: {present} of {len(items)} keyed sources have a key ({store.backend_label})"
    )
    return EXIT_OK


def _cmd_keys_remove(ctx: _Context, args: argparse.Namespace) -> int:
    item = _keyed_source(ctx, args.source_id)
    removed = ctx.keystore().delete(item.key_env)
    if removed:
        _say(f"regwatch keys: removed the key for {item.source_id}")
    else:
        _say(f"regwatch keys: no key was stored for {item.source_id}")
    if ctx.system.environ.get(item.key_env):
        _say(f"The environment variable {item.key_env} is still set and still supplies a key.")
    return EXIT_OK


# --- run and schedule --------------------------------------------------------


def _cmd_run(ctx: _Context, args: argparse.Namespace) -> int:
    outcome = run_once(ctx.config, ctx.live_fetcher(), ctx.key_for, ctx.clock, ctx.register())
    for c in outcome.captures:
        label = "captured" if c.captured else "skipped"
        _say(f"{label:<10} {c.source_id:<28} {clean_text(c.detail)}")
    for r in outcome.results:
        detail = f"  {clean_text(r.detail)}" if r.detail else ""
        _say(f"{r.status:<10} {r.source_id:<28} {r.origin}{detail}")
    summary = ", ".join(f"{k.lower()}={v}" for k, v in sorted(outcome.counts.items()))
    _say(
        f"regwatch run: {len(outcome.results)} sources; {summary}; "
        f"capture failures={len(outcome.failed)}"
    )
    _say(f"regwatch run: wrote {outcome.path}")
    _say(NOTICE)
    return outcome.code


def _schedule_parts(ctx: _Context) -> tuple[list[str], Path, Path]:
    config = ctx.config
    arguments = program_arguments(ctx.system.executable, config.config_path)
    return arguments, config.base_dir, config.state_dir / "schedule.log"


def _schedule_every(ctx: _Context, requested: str | None) -> str:
    if requested:
        return str(requested)
    return schedule_cadence(source.cadence for source in ctx.register().sources)


def _tool(ctx: _Context, name: str) -> str:
    path = ctx.system.which(name)
    if path is None:
        raise CommandError(f"the {name} command was not found, so no schedule can be managed")
    return path


def _read_crontab(ctx: _Context) -> str:
    result = ctx.system.runner([_tool(ctx, "crontab"), "-l"], None)
    if result.returncode == 0:
        return result.stdout
    if "no crontab" in result.stderr.lower():
        return ""
    raise CommandError(
        f"crontab -l failed with status {result.returncode}; the crontab was left unchanged"
    )


def _write_crontab(ctx: _Context, text: str) -> None:
    result = ctx.system.runner([_tool(ctx, "crontab"), "-"], text)
    if result.returncode != 0:
        raise CommandError(f"crontab could not install the new table (status {result.returncode})")


def _cmd_schedule(ctx: _Context, args: argparse.Namespace) -> int:
    if args.install and args.remove:
        raise CommandError("choose one of --install and --remove")
    system = ctx.system
    every = _schedule_every(ctx, args.every)
    arguments, working_dir, log_path = _schedule_parts(ctx)
    if system.is_macos:
        return _schedule_launchd(ctx, args, every, arguments, working_dir, log_path)
    return _schedule_cron(ctx, args, every, arguments, working_dir, log_path)


def _schedule_launchd(
    ctx: _Context,
    args: argparse.Namespace,
    every: str,
    arguments: list[str],
    working_dir: Path,
    log_path: Path,
) -> int:
    system = ctx.system
    path = plist_path(system.home())
    domain = f"gui/{system.uid()}"
    if args.install:
        data = plist_bytes(arguments, every, working_dir, log_path)
        commands = [
            ["launchctl", "bootout", f"{domain}/{LABEL}"],
            ["launchctl", "bootstrap", domain, str(path)],
        ]
        if args.dry_run:
            _say(f"regwatch schedule: would write {path}:")
            for line in data.decode("utf-8").splitlines():
                _say(f"  {line}")
            for command in commands:
                _say("would run: " + " ".join(command))
            return EXIT_OK
        launchctl = _tool(ctx, "launchctl")
        safe_write_bytes(path, data, ctx.config.protected_paths())
        system.runner([launchctl, "bootout", f"{domain}/{LABEL}"], None)
        result = system.runner([launchctl, "bootstrap", domain, str(path)], None)
        if result.returncode != 0:
            raise CommandError(
                f"launchctl bootstrap failed with status {result.returncode}; {path} was written "
                "but is not loaded"
            )
        _say(f"regwatch schedule: installed {LABEL} to run {every}, from {path}")
        _say(
            f"Output goes to {log_path}, and each run writes a record under {ctx.config.state_dir}."
        )
        return EXIT_OK
    if args.remove:
        if args.dry_run:
            _say(f"would run: launchctl bootout {domain}/{LABEL}")
            _say(f"would remove {path}")
            return EXIT_OK
        system.runner([_tool(ctx, "launchctl"), "bootout", f"{domain}/{LABEL}"], None)
        removed = remove_file(path, ctx.config.protected_paths())
        _say(
            f"regwatch schedule: removed {path}"
            if removed
            else "regwatch schedule: nothing to remove"
        )
        return EXIT_OK
    installed = path.is_file()
    _say(f"launchd agent {LABEL}: {'installed' if installed else 'not installed'} at {path}")
    _say(f"cadence: {every}")
    _say("command: " + " ".join(arguments))
    return EXIT_OK


def _schedule_cron(
    ctx: _Context,
    args: argparse.Namespace,
    every: str,
    arguments: list[str],
    working_dir: Path,
    log_path: Path,
) -> int:
    block = cron_block(arguments, every, working_dir, log_path)
    if args.dry_run and not args.remove:
        _say("regwatch schedule: would add this block to your crontab:")
        for line in block.splitlines():
            _say(f"  {line}")
        return EXIT_OK
    current = _read_crontab(ctx)
    if args.install:
        _write_crontab(ctx, replace_block(current, block))
        _say(f"regwatch schedule: installed {LABEL} in your crontab to run {every}")
        _say(
            f"Output goes to {log_path}, and each run writes a record under {ctx.config.state_dir}."
        )
        return EXIT_OK
    existing = installed_block(current)
    if args.remove:
        if existing is None:
            _say("regwatch schedule: nothing to remove")
            return EXIT_OK
        if args.dry_run:
            _say("regwatch schedule: would remove this block from your crontab:")
            for line in existing.splitlines():
                _say(f"  {line}")
            return EXIT_OK
        _write_crontab(ctx, replace_block(current, None))
        _say(f"regwatch schedule: removed {LABEL} from your crontab")
        return EXIT_OK
    _say(f"crontab block {LABEL}: {'installed' if existing else 'not installed'}")
    for line in (existing or block).splitlines():
        _say(f"  {line}")
    return EXIT_OK


# --- workspace commands ------------------------------------------------------


def _cmd_ui(ctx: _Context, args: argparse.Namespace) -> int:
    if not 0 <= args.port <= 65535:
        raise CommandError("--port must be from 0 to 65535")
    ctx.config  # noqa: B018 (load and validate the configuration before starting)
    api = Api(
        ctx.config_path.resolve(),
        system=ctx.system,
        fetcher=ctx.fetcher,
        clock=ctx.clock,
    )
    server = LocalServer(api, web_root(), args.port)
    _say(f"regwatch ui: serving {ctx.config.base_dir} at {server.url}")
    _say(
        "regwatch ui: the address holds a private token that works once, in the first "
        "browser that opens it; press Ctrl+C to stop"
    )
    if not args.no_open:
        webbrowser.open(server.url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _say()
    finally:
        server.server_close()
    _say("regwatch ui: stopped")
    return EXIT_OK


def _cmd_premium(ctx: _Context, args: argparse.Namespace) -> int:
    if args.action != "status":
        set_premium(ctx.config_path, args.action == "on")
    enabled = load_config(ctx.config_path).premium.enabled
    _say(f"regwatch premium: {'on' if enabled else 'off'}")
    if not enabled:
        _say("Newsletters, documents, generated copy and runs more often than daily are locked.")
    return EXIT_OK


# --- parser ------------------------------------------------------------------

_Handler = Callable[[_Context, argparse.Namespace], int]


def _build_parser() -> tuple[argparse.ArgumentParser, dict[str, _Handler]]:
    parser = argparse.ArgumentParser(
        prog="regwatch",
        description=(
            "Monitor regulatory sources for changes and flag candidate impacts on your register."
        ),
        epilog=DISCLAIMER,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"regwatch {__version__}")
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_NAME,
        help=f"configuration file (default: {DEFAULT_CONFIG_NAME})",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")
    handlers: dict[str, _Handler] = {}

    def add(name: str, handler: _Handler, help_text: str) -> argparse.ArgumentParser:
        handlers[name] = handler
        return sub.add_parser(name, help=help_text, description=help_text, epilog=DISCLAIMER)

    add("validate", _cmd_validate, "validate the register files against the field rules")
    add("coverage", _cmd_coverage, "report per-jurisdiction coverage")

    p = add("list", _cmd_list, "list obligations with optional filters")
    p.add_argument("--jurisdiction")
    p.add_argument("--category")
    p.add_argument("--status")
    p.add_argument("--upcoming", type=int, help="only obligations effective within N days")

    add("portfolio", _cmd_portfolio, "list the products obligations are matched against")

    p = add("capture", _cmd_capture, "fetch sources into stored snapshots")
    p.add_argument("--source", help="capture only this source id")

    p = add("check", _cmd_check, "detect changes in sources since the last accepted run")
    p.add_argument(
        "--fetch", action="store_true", help="fetch each source now instead of reading its snapshot"
    )
    p.add_argument(
        "--accept", action="store_true", help="record the current hashes as the new baseline"
    )
    p.add_argument(
        "--exit-code", action="store_true", help="exit with status 3 when changes are detected"
    )
    p.add_argument(
        "--accept-suspicious",
        action="store_true",
        help="with --accept, also record sources reported SUSPICIOUS (empty or much shorter)",
    )
    p.add_argument("--source", help="check only this source id")

    p = add(
        "ingest", _cmd_ingest, "turn a Federal Register style response into unconfirmed candidates"
    )
    p.add_argument("--fetch", action="store_true", help="fetch the API now")
    p.add_argument("--from-file", help="parse a saved API response instead of fetching")
    p.add_argument("--since", type=int, default=365, help="look back this many days (default: 365)")

    p = add("impact", _cmd_impact, "flag candidate impacts of obligations on products")
    p.add_argument("--product", help="only this product id")
    p.add_argument("--severity", choices=list(SEVERITIES))

    add("themes", _cmd_themes, "read the impacts through the configured themes")

    p = add("brief", _cmd_brief, "build a daily, weekly or tiered briefing")
    p.add_argument("--kind", choices=["tiered", "daily", "weekly"], default="tiered")
    p.add_argument(
        "--tier", choices=list(TIERS), default="v3", help="detail level for the tiered briefing"
    )
    p.add_argument(
        "--since-days", type=int, help="window the recent section of the tiered briefing"
    )
    p.add_argument(
        "--recent", type=int, default=8, help="how many recent events to show (default: 8)"
    )
    p.add_argument(
        "--fetch",
        action="store_true",
        help="daily kind: fetch sources instead of reading snapshots",
    )
    p.add_argument(
        "--out-dir", help="write the Markdown and the JSON model here instead of printing"
    )
    p.add_argument("--name", help="file stem for the written files")

    p = add("render", _cmd_render, "render a saved briefing model into delivery formats")
    p.add_argument("model", help="path to a briefing JSON model written by 'regwatch brief'")
    p.add_argument(
        "--formats", default=",".join(FORMATS), help=f"comma list of {', '.join(FORMATS)}"
    )
    p.add_argument("--out-dir", default=".", help="directory for the rendered files")
    p.add_argument("--tags", default="regulatory", help="tags for the web post front matter")

    p = add("digest", _cmd_digest, "write a Markdown digest of the register")
    p.add_argument(
        "--window", type=int, default=365, help="upcoming horizon in days (default: 365)"
    )
    p.add_argument("--out", help="write to this path instead of printing")

    p = add("report", _cmd_report, "write a change-and-due alert")
    p.add_argument(
        "--window", type=int, default=365, help="upcoming horizon in days (default: 365)"
    )
    p.add_argument(
        "--fetch", action="store_true", help="fetch sources instead of reading snapshots"
    )
    p.add_argument("--out", help="write Markdown to this path instead of printing")
    p.add_argument("--json", help="also write the machine-readable report here")

    p = add("export", _cmd_export, "write one flat record per obligation")
    p.add_argument("--csv", required=True, help="CSV output path")
    p.add_argument("--json", help="also write the records as JSON here")

    p = add(
        "init",
        _cmd_init,
        "create a project: configuration, an empty register and your focus areas",
    )
    p.epilog = (
        "Every question has a flag. A question whose flag is given is not asked. " + DISCLAIMER
    )
    p.add_argument(
        "--dir",
        help="the project folder; default the current folder, never assumed in your home folder",
    )
    p.add_argument(
        "--focus", action="append", metavar="ID", help="a focus area id or number; repeat for more"
    )
    p.add_argument(
        "--term", action="append", metavar="TERM", help="an extra word that matters to you; repeat"
    )
    p.add_argument(
        "--jurisdiction", action="append", metavar="NAME", help="a jurisdiction to watch; repeat"
    )
    p.add_argument(
        "--allow-file-root",
        action="append",
        metavar="FOLDER",
        help="allow file sources under this folder; repeat. Without it local files are refused",
    )
    p.add_argument("--contact", help="email address or web page placed in the User-Agent header")
    p.add_argument(
        "--example",
        action="store_true",
        help="offer the invented example jurisdictions as the default answer",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="use the default for every question that has no flag, and do not ask to confirm",
    )
    p.add_argument("--force", action="store_true", help="replace files that already exist")
    p.add_argument(
        "--sources",
        metavar="ID,ID",
        help="catalogue sources to watch, separated by commas; an empty value chooses none",
    )
    p.add_argument(
        "--schedule",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="install a recurring run after writing, or with --no-schedule do not ask",
    )
    p.add_argument(
        "--first-run",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="run a first capture and check after writing, or with --no-first-run do not ask",
    )

    p = add("config", _cmd_config, "show the effective configuration")
    actions = p.add_subparsers(dest="config_command", required=True, metavar="action")
    actions.add_parser(
        "show",
        help="print every setting, resolved, including focus areas and file roots",
        epilog=DISCLAIMER,
    )
    _add_sources_parser(sub, handlers)
    _add_keys_parser(sub, handlers)

    add("run", _cmd_run, "capture every source, check them and write a run record")

    p = add("schedule", _cmd_schedule, "install, show or remove a recurring run")
    p.add_argument("--install", action="store_true", help="install or replace the schedule")
    p.add_argument("--remove", action="store_true", help="remove the schedule")
    p.add_argument("--show", action="store_true", help="show the schedule (the default)")
    p.add_argument(
        "--every",
        choices=list(CADENCES),
        help="how often to run; default the most frequent cadence among your sources",
    )
    p.add_argument(
        "--dry-run", action="store_true", help="print what would change and change nothing"
    )

    p = add("ui", _cmd_ui, "open the local web app in the browser")
    p.add_argument("--port", type=int, default=0, help="port on 127.0.0.1 (default: a free one)")
    p.add_argument("--no-open", action="store_true", help="print the address but open no browser")

    p = add("premium", _cmd_premium, "turn the premium features on or off, or show their state")
    p.add_argument("action", choices=["on", "off", "status"])
    return parser, handlers


def _add_keys_parser(sub: Any, handlers: dict[str, _Handler]) -> None:
    keys = sub.add_parser(
        "keys",
        help="store, list and remove the API keys some sources need",
        description="Keep the keys of keyed sources in the system keychain. No key is printed.",
        epilog=DISCLAIMER,
    )
    actions = keys.add_subparsers(dest="keys_command", required=True, metavar="action")
    handlers["keys set"] = _cmd_keys_set
    p = actions.add_parser("set", help="prompt for a key and store it", epilog=DISCLAIMER)
    p.add_argument("source_id", metavar="SOURCE_ID")
    handlers["keys list"] = _cmd_keys_list
    actions.add_parser("list", help="show which keyed sources have a key", epilog=DISCLAIMER)
    handlers["keys remove"] = _cmd_keys_remove
    p = actions.add_parser("remove", help="delete a stored key", epilog=DISCLAIMER)
    p.add_argument("source_id", metavar="SOURCE_ID")


def _add_sources_parser(sub: Any, handlers: dict[str, _Handler]) -> None:
    sources = sub.add_parser(
        "sources",
        help="list, search, show, add, remove and verify catalogue sources",
        description="Choose sources to watch from the catalogue that ships with regwatch.",
        epilog=DISCLAIMER,
    )
    actions = sources.add_subparsers(dest="sources_command", required=True, metavar="action")

    def action(name: str, handler: _Handler, help_text: str) -> argparse.ArgumentParser:
        handlers[f"sources {name}"] = handler
        parser: argparse.ArgumentParser = actions.add_parser(
            name, help=help_text, description=help_text, epilog=DISCLAIMER
        )
        return parser

    p = action("list", _cmd_sources_list, "list catalogue sources, with filters")
    p.add_argument("--region", choices=list(REGIONS))
    p.add_argument("--jurisdiction", help="a jurisdiction code; also matches its subdivisions")
    p.add_argument("--kind", choices=list(KINDS))
    p.add_argument("--category", choices=list(CATEGORIES))
    p.add_argument("--access", choices=list(ACCESS))
    p.add_argument("--focus", metavar="ID", help="sources for this focus area")
    p.add_argument("--chosen", action="store_true", help="only sources in your sources file")
    p.add_argument("--json", action="store_true", help="print JSON instead of lines")

    p = action("search", _cmd_sources_search, "search the catalogue, best match first")
    p.add_argument("text", help="words to look for")
    p.add_argument("--json", action="store_true", help="print JSON instead of lines")

    p = action("show", _cmd_sources_show, "show every field of one catalogue source")
    p.add_argument("id")
    p.add_argument("--json", action="store_true", help="print JSON instead of lines")

    p = action("add", _cmd_sources_add, "copy catalogue sources into your sources file")
    p.add_argument("ids", nargs="+", metavar="ID")

    p = action("remove", _cmd_sources_remove, "remove a source from your sources file")
    p.add_argument("id")

    p = action("verify", _cmd_sources_verify, "fetch catalogue addresses and report each status")
    p.add_argument("ids", nargs="*", metavar="ID", help="default: every catalogue source")


def main(
    argv: Sequence[str] | None = None,
    *,
    fetcher: Fetcher | None = None,
    today: dt.date | None = None,
    now: dt.datetime | None = None,
    system: System | None = None,
) -> int:
    """Run the command line and return the exit status.

    ``fetcher``, ``today``, ``now`` and ``system`` exist so tests and embedders can
    supply a fake network client, a fixed clock, and a stand-in for the programs
    that keep keys and install schedules.
    """
    parser, handlers = _build_parser()
    args = parser.parse_args(argv)
    moment = now or dt.datetime.now(dt.UTC)
    ctx = _Context(
        config_path=Path(args.config),
        fetcher=fetcher,
        today=today or moment.date(),
        now=moment,
        system=system or System(),
    )
    if now is not None:
        ctx.clock = lambda: moment
    command = args.command
    if command in ("sources", "keys"):
        command = f"{command} {getattr(args, f'{command}_command')}"
    try:
        return handlers[command](ctx, args)
    except RegisterError as exc:
        if exc.errors != [str(exc)]:
            for error in exc.errors:
                _say(f"ERROR {error}", file=sys.stderr)
        _say(f"error: {exc}; run 'regwatch validate' for the list", file=sys.stderr)
        return EXIT_INVALID
    except (
        CommandError,
        CatalogueError,
        ConfigError,
        KeyStoreError,
        ScheduleError,
        StateError,
        FetchError,
        FocusError,
        IngestError,
        ServerError,
        DocumentError,
        ValueError,
        OSError,
    ) as exc:
        _say(f"error: {clean_text(str(exc))}", file=sys.stderr)
        return EXIT_ERROR
