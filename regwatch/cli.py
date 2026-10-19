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

Exit status: 0 success, 1 the register is invalid or nothing could be captured,
2 a usage, configuration, network or file error, 3 changes were detected and
``check --exit-code`` was given.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from regwatch import __version__
from regwatch.briefing import TIERS, build_briefing
from regwatch.check import SourceResult, accept_results, capture_sources, check_sources
from regwatch.config import DEFAULT_CONFIG_NAME, Config, ConfigError, load_config
from regwatch.document import DISCLAIMER, Document, DocumentError, Section, make_disclaimer
from regwatch.export import build_records, records_csv
from regwatch.fetch import Fetcher, FetchError, SafeFetcher
from regwatch.impact import SEVERITIES, assess_impacts, theme_findings
from regwatch.ingest import IngestError, build_query_url, candidates_document, parse_candidates
from regwatch.register import (
    Register,
    RegisterError,
    Source,
    load_register,
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
from regwatch.sanitize import clean_text
from regwatch.state import StateError, load_seen, safe_write_bytes, safe_write_text, save_seen
from regwatch.synthesis import daily_brief, upcoming_obligations, weekly_synthesis

__all__ = ["main"]

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_ERROR = 2
EXIT_CHANGES = 3
EXIT_UNVERIFIED = 4
NOTICE = "regwatch flags candidates for human review. It is not legal advice."
MAX_INPUT_BYTES = 20_000_000
NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]{0,99}$")


class CommandError(Exception):
    """A command failed in a way the user can fix. The message is printed as is."""


@dataclass
class _Context:
    config_path: Path
    fetcher: Fetcher | None
    today: dt.date
    now: dt.datetime
    _config: Config | None = field(default=None, init=False)

    @property
    def config(self) -> Config:
        if self._config is None:
            self._config = load_config(self.config_path)
        return self._config

    def live_fetcher(self) -> Fetcher:
        """The injected fetcher, or a real one built from the fetch settings."""
        if self.fetcher is not None:
            return self.fetcher
        settings = self.config.fetch
        return SafeFetcher(
            settings.timeout_seconds,
            settings.max_bytes,
            settings.user_agent,
            total_timeout_seconds=settings.total_timeout_seconds,
            allow_private_hosts=settings.allow_private_hosts,
            allowed_file_roots=settings.allowed_file_roots,
        )

    def register(self) -> Register:
        return load_register(self.config)

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
        print(f"ERROR {error}")
    register = None if errors else load_register(ctx.config)
    if register is not None:
        print(
            f"regwatch validate: {len(register.obligations)} obligations, {len(register.sources)} sources, "
            f"{len(register.categories)} categories, {len(register.jurisdictions)} jurisdictions, "
            f"{len(register.portfolio.products)} products; errors=0"
        )
        return EXIT_OK
    print(f"regwatch validate: errors={len(errors)}")
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
        print(
            f"{jurisdiction.coverage:<10} {jurisdiction.jurisdiction_id:<16} rows={count:<3} {jurisdiction.name}"
        )
    summary = ", ".join(f"{k}={v}" for k, v in sorted(by_coverage.items()))
    print(f"regwatch coverage: {len(register.jurisdictions)} jurisdictions; {summary}")
    for gap in gaps:
        print(f"WARN  {gap}")
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
        print(
            f"{o.effective_date or '(no date)':<11} {o.jurisdiction:<16} {o.status:<11} {o.title}"
        )
    print(f"regwatch list: {len(rows)} obligations")
    return EXIT_OK


def _cmd_portfolio(ctx: _Context, args: argparse.Namespace) -> int:
    register = ctx.register()
    for product in register.portfolio.products:
        print(f"{product.product_id:<28} {product.name}")
        print(
            f"{'':<28} categories: {', '.join(product.categories) or '-'}; markets: {', '.join(product.markets)}"
        )
    print(
        f"regwatch portfolio: {register.portfolio.name}, {len(register.portfolio.products)} products"
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
        sources, ctx.live_fetcher(), ctx.config.snapshots_dir, ctx.config.register.all_paths()
    )
    for r in results:
        label = "captured" if r.captured else "skipped"
        print(f"{label:<10} {r.source_id:<28} {r.detail}")
    done = sum(1 for r in results if r.captured)
    print(f"regwatch capture: {done}/{len(results)} sources")
    return EXIT_OK if done else EXIT_INVALID


def _run_check(
    ctx: _Context, register: Register, fetch: bool, source_id: str | None = None
) -> list[SourceResult]:
    seen = load_seen(ctx.config.seen_path)
    fetcher = ctx.live_fetcher() if fetch else None
    return check_sources(
        _select_sources(register, source_id), seen, ctx.config.snapshots_dir, fetcher
    )


def _cmd_check(ctx: _Context, args: argparse.Namespace) -> int:
    register = ctx.register()
    results = _run_check(ctx, register, args.fetch, args.source)
    counts: dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
        digest = f"  {r.sha256[:12]}" if r.sha256 else ""
        detail = f"  {clean_text(r.detail)}" if r.detail else ""
        print(f"{r.status:<10} {r.source_id:<28} {r.origin}{digest}{detail}")
    summary = ", ".join(f"{k.lower()}={v}" for k, v in sorted(counts.items()))
    print(f"regwatch check: {len(results)} sources; {summary}")
    flagged = [r for r in results if r.flagged]
    if args.accept:
        seen = accept_results(
            load_seen(ctx.config.seen_path),
            results,
            ctx.now,
            accept_suspicious=args.accept_suspicious,
        )
        save_seen(ctx.config.seen_path, seen, ctx.config.register.all_paths())
        print(f"regwatch check: recorded the accepted baseline in {ctx.config.seen_path}")
    elif flagged:
        print(
            "regwatch check: changes detected; review them, then run again with --accept to record the baseline"
        )
    if any(r.status == "SUSPICIOUS" for r in results) and not args.accept_suspicious:
        print(
            "regwatch check: SUSPICIOUS sources are not accepted unless you add --accept-suspicious"
        )
    print(NOTICE)
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
    print(f"regwatch ingest: {len(candidates)} candidate events from {origin} (since {since})")
    print(f"regwatch ingest: wrote {ctx.config.candidates_path} (unconfirmed, for review)")
    print(NOTICE)
    return EXIT_OK


# --- analysis commands -------------------------------------------------------


def _cmd_impact(ctx: _Context, args: argparse.Namespace) -> int:
    register = ctx.register()
    impacts = assess_impacts(register, ctx.today)
    if args.product:
        impacts = [i for i in impacts if i.product_id == args.product]
    if args.severity:
        impacts = [i for i in impacts if i.severity == args.severity]
    for i in impacts:
        print(
            f"{i.severity:<8} {i.product_id:<24} {i.jurisdiction:<14} {i.effective_date or 'no date':<11} "
            f"{i.obligation_title}"
        )
        print(f"{'':<8} {'; '.join(i.reasons)}")
    print(
        f"regwatch impact: {len(impacts)} candidate impacts across {len(register.portfolio.products)} products"
    )
    print(NOTICE)
    return EXIT_OK


def _cmd_themes(ctx: _Context, args: argparse.Namespace) -> int:
    register = ctx.register()
    findings = theme_findings(register, assess_impacts(register, ctx.today), register.themes)
    for f in findings:
        print(f"## {f.title}")
        print(f.why)
        if f.affected_products:
            print("Affected products: " + ", ".join(f.affected_products))
        if f.obligations:
            print("Related obligations: " + ", ".join(f.obligations))
        print("Action: " + f.action)
        print()
    print(f"regwatch themes: {len(findings)} findings")
    print(NOTICE)
    return EXIT_OK


def _load_candidates(ctx: _Context) -> list[dict[str, Any]]:
    path = ctx.config.candidates_path
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
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
    print(f"wrote {directory / f'{stem}.md'}")
    print(f"wrote {directory / f'{stem}.json'}")


def _cmd_brief(ctx: _Context, args: argparse.Namespace) -> int:
    register = ctx.register()
    impacts = assess_impacts(register, ctx.today)
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
        print(f"wrote {path}")
    print(f"regwatch render: {len(written)} files")
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
        print(f"regwatch {label}: wrote {out}")
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
        print(f"regwatch report: wrote {args.json}")
    if flagged:
        print(
            f"regwatch report: {len(flagged)} source change(s) flagged for review", file=sys.stderr
        )
    return EXIT_OK


def _cmd_export(ctx: _Context, args: argparse.Namespace) -> int:
    records = build_records(ctx.register())
    ctx.write_text(Path(args.csv), records_csv(records))
    print(f"regwatch export: wrote {args.csv} ({len(records)} records)")
    if args.json:
        ctx.write_text(Path(args.json), json.dumps(records, indent=2) + "\n")
        print(f"regwatch export: wrote {args.json}")
    return EXIT_OK


# --- parser ------------------------------------------------------------------

_Handler = Callable[[_Context, argparse.Namespace], int]


def _build_parser() -> tuple[argparse.ArgumentParser, dict[str, _Handler]]:
    parser = argparse.ArgumentParser(
        prog="regwatch",
        description="Monitor regulatory sources for changes and flag candidate impacts on your register.",
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
    return parser, handlers


def main(
    argv: Sequence[str] | None = None,
    *,
    fetcher: Fetcher | None = None,
    today: dt.date | None = None,
    now: dt.datetime | None = None,
) -> int:
    """Run the command line and return the exit status.

    ``fetcher``, ``today`` and ``now`` exist so tests and embedders can supply a
    fake network client and a fixed clock.
    """
    parser, handlers = _build_parser()
    args = parser.parse_args(argv)
    moment = now or dt.datetime.now(dt.UTC)
    ctx = _Context(
        config_path=Path(args.config),
        fetcher=fetcher,
        today=today or moment.date(),
        now=moment,
    )
    try:
        return handlers[args.command](ctx, args)
    except RegisterError as exc:
        if exc.errors != [str(exc)]:
            for error in exc.errors:
                print(f"ERROR {error}", file=sys.stderr)
        print(f"error: {exc}; run 'regwatch validate' for the list", file=sys.stderr)
        return EXIT_INVALID
    except (
        CommandError,
        ConfigError,
        StateError,
        FetchError,
        IngestError,
        DocumentError,
        ValueError,
        OSError,
    ) as exc:
        print(f"error: {clean_text(str(exc))}", file=sys.stderr)
        return EXIT_ERROR
