from __future__ import annotations

import datetime as dt
from pathlib import Path

from conftest import NOW, FakeFetcher, snapshot_responses

from regwatch.check import (
    CaptureResult,
    SourceResult,
    accept_results,
    capture_sources,
    check_sources,
)
from regwatch.config import Config
from regwatch.fetch import FetchError
from regwatch.register import Register


def statuses(results: list[SourceResult]) -> dict[str, str]:
    return {r.source_id: r.status for r in results}


def test_snapshot_check_is_new_then_unchanged(config: Config, register: Register) -> None:
    results = check_sources(register.sources, {}, config.snapshots_dir)
    assert statuses(results) == {
        "nl-notices": "NEW",
        "nl-east-gazette": "NEW",
        "sv-register-api": "NEW",
        "sv-subscription": "NEW",
        "sv-newsroom": "MANUAL",
    }
    assert all(r.origin == "snapshot" for r in results if r.status == "NEW")
    seen = accept_results({}, results, NOW)
    again = check_sources(register.sources, seen, config.snapshots_dir)
    assert {s for s in statuses(again).values()} == {"UNCHANGED", "MANUAL"}


def test_changed_content_is_detected(config: Config, register: Register) -> None:
    seen = accept_results({}, check_sources(register.sources, {}, config.snapshots_dir), NOW)
    path = config.snapshots_dir / "sv-register-api.txt"
    path.write_text(
        path.read_text(encoding="utf-8").replace("SV-2026-097", "SV-2026-098"), encoding="utf-8"
    )
    results = check_sources(register.sources, seen, config.snapshots_dir)
    assert statuses(results)["sv-register-api"] == "CHANGED"
    assert statuses(results)["nl-notices"] == "UNCHANGED"
    assert [r.source_id for r in results if r.flagged] == ["sv-register-api"]


def test_markup_only_html_change_is_unchanged(config: Config, register: Register) -> None:
    seen = accept_results({}, check_sources(register.sources, {}, config.snapshots_dir), NOW)
    path = config.snapshots_dir / "nl-east-gazette.txt"
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace("<ul>", "<ol class='x'>").replace("</ul>", "</ol>"), encoding="utf-8"
    )
    assert (
        statuses(check_sources(register.sources, seen, config.snapshots_dir))["nl-east-gazette"]
        == "UNCHANGED"
    )


def test_missing_snapshot(config: Config, register: Register) -> None:
    (config.snapshots_dir / "nl-notices.txt").unlink()
    results = check_sources(register.sources, {}, config.snapshots_dir)
    missing = next(r for r in results if r.source_id == "nl-notices")
    assert (missing.status, missing.origin, missing.sha256) == ("MISSING", "none", None)
    assert not missing.flagged


def test_live_check_uses_the_fetcher_not_the_snapshot(config: Config, register: Register) -> None:
    responses = snapshot_responses(config)
    fetcher = FakeFetcher(responses)
    results = check_sources(register.sources, {}, config.snapshots_dir, fetcher)
    assert all(r.origin == "live" for r in results if r.status == "NEW")
    assert "https://api.sv.example/documents.json" in fetcher.requested
    assert "https://news.sv.example/press" not in fetcher.requested

    changed = dict(responses)
    changed["https://regulator.nl.example/notices.xml"] = responses[
        "https://regulator.nl.example/notices.xml"
    ].replace("nl-notice-2026-0901", "nl-notice-2026-0902")
    seen = accept_results({}, results, NOW)
    results = check_sources(register.sources, seen, config.snapshots_dir, FakeFetcher(changed))
    assert statuses(results)["nl-notices"] == "CHANGED"


def test_fetch_failure_is_an_error_status_not_an_exception(
    config: Config, register: Register
) -> None:
    fetcher = FakeFetcher(
        {"https://regulator.nl.example/notices.xml": FetchError("HTTP status 503")}
    )
    results = check_sources(register.sources, {}, config.snapshots_dir, fetcher)
    first = next(r for r in results if r.source_id == "nl-notices")
    assert first.status == "ERROR"
    assert "HTTP status 503" in first.detail
    assert next(r for r in results if r.source_id == "nl-east-gazette").status == "ERROR"


def test_unsafe_feed_is_an_error_status(config: Config, register: Register) -> None:
    (config.snapshots_dir / "nl-notices.txt").write_text(
        '<!DOCTYPE rss [<!ENTITY a "b">]><rss/>', encoding="utf-8"
    )
    results = check_sources(register.sources, {}, config.snapshots_dir)
    bad = next(r for r in results if r.source_id == "nl-notices")
    assert bad.status == "ERROR"
    assert "DTD or entity" in bad.detail


def test_accept_results_records_only_hashed_results() -> None:
    results = [
        SourceResult("a", "NEW", "live", "h1"),
        SourceResult("b", "ERROR", "live", None, "boom"),
        SourceResult("c", "MANUAL", "manual", None),
    ]
    prior = {"b": {"sha256": "old", "origin": "live", "checked": "x"}}
    updated = accept_results(prior, results, NOW)
    assert updated["a"] == {
        "sha256": "h1",
        "origin": "live",
        "checked": "2026-10-19T12:00:00+00:00",
        "signal_length": "0",
    }
    assert updated["b"]["sha256"] == "old"
    assert "c" not in updated
    assert prior == {"b": {"sha256": "old", "origin": "live", "checked": "x"}}


def test_accept_results_converts_to_utc() -> None:
    zone = dt.timezone(dt.timedelta(hours=5))
    moment = dt.datetime(2026, 1, 1, 5, 0, tzinfo=zone)
    updated = accept_results({}, [SourceResult("a", "NEW", "live", "h")], moment)
    assert updated["a"]["checked"] == "2026-01-01T00:00:00+00:00"


def test_capture_writes_snapshots_and_skips_manual(tmp_path: Path, register: Register) -> None:
    responses: dict[str, str | Exception] = {
        s.url: f"content of {s.source_id}" for s in register.sources if s.mechanism != "manual"
    }
    responses["https://api.sv.example/documents.json"] = FetchError("HTTP status 500")
    results = capture_sources(register.sources, FakeFetcher(responses), tmp_path / "snaps", [])
    by_id = {r.source_id: r for r in results}
    assert by_id["nl-notices"] == CaptureResult("nl-notices", True, "21 bytes")
    assert by_id["sv-newsroom"].captured is False
    assert "manual" in by_id["sv-newsroom"].detail
    assert "HTTP status 500" in by_id["sv-register-api"].detail
    assert (tmp_path / "snaps" / "nl-notices.txt").read_text(
        encoding="utf-8"
    ) == "content of nl-notices"
    assert not (tmp_path / "snaps" / "sv-register-api.txt").exists()
