"""Change detection.

For each source regwatch reduces the content to a signal, hashes it and compares
the hash with the last accepted one. It reports NEW, CHANGED or UNCHANGED, plus
MISSING (no content to look at), MANUAL (an analyst reviews it by hand) and
ERROR (the fetch or the parse failed). A signal that is empty, or that has shrunk
to less than half of its accepted length, is reported as SUSPICIOUS even when it
differs from the baseline, because content that disappears is the usual way a
change is hidden. Detection only flags. The last-seen state
changes only when the caller explicitly accepts the results.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from regwatch.extract import ExtractError, extract_signal, signal_hash
from regwatch.fetch import Credential, Fetcher, FetchError
from regwatch.register import Source
from regwatch.state import SeenState, read_snapshot, write_snapshot

__all__ = [
    "MIN_PRIOR_LENGTH",
    "SHRINK_RATIO",
    "CaptureResult",
    "KeyLookup",
    "SourceResult",
    "accept_results",
    "capture_sources",
    "check_sources",
    "fetch_source",
]

SHRINK_RATIO = 0.5
MIN_PRIOR_LENGTH = 20


@dataclass(frozen=True)
class SourceResult:
    """The outcome of checking one source."""

    source_id: str
    status: str
    origin: str
    sha256: str | None
    detail: str = ""
    signal_length: int | None = None

    @property
    def flagged(self) -> bool:
        """True when a human should look at this source."""
        return self.status in ("NEW", "CHANGED", "SUSPICIOUS")

    @property
    def needs_attention(self) -> bool:
        """True when the source could not be verified: it errored or has no content."""
        return self.status in ("ERROR", "MISSING")


@dataclass(frozen=True)
class CaptureResult:
    """The outcome of capturing one source into a snapshot."""

    source_id: str
    captured: bool
    detail: str


KeyLookup = Callable[[str], str | None]
"""Returns the key for a ``key_env`` name, or None when there is none."""


def fetch_source(source: Source, fetcher: Fetcher, key_for: KeyLookup | None = None) -> str:
    """Fetch one source, adding its key when its entry says it needs one.

    Raises FetchError when a keyed source has no key, naming the variable and the
    command that would supply it, and never the key itself.
    """
    if not source.auth:
        return fetcher.fetch(source.url)
    value = key_for(source.key_env) if key_for is not None else None
    if not value:
        raise FetchError(
            f"no key for {source.source_id}; run 'regwatch keys set {source.source_id}' "
            f"or set the environment variable {source.key_env}"
        )
    try:
        credential = Credential.from_auth(source.auth, value)
    except ValueError as exc:
        raise FetchError(f"the key for {source.source_id} cannot be used: {exc}") from None
    return fetcher.fetch(source.url, credential=credential)


def check_sources(
    sources: Iterable[Source],
    seen: SeenState,
    snapshots_dir: Path,
    fetcher: Fetcher | None = None,
    key_for: KeyLookup | None = None,
) -> list[SourceResult]:
    """Compare every source with its last accepted hash.

    With a ``fetcher`` the content is fetched now, with each keyed source's key
    from ``key_for``. Without one, the stored snapshot is used, so a check is
    repeatable offline.
    """
    results: list[SourceResult] = []
    for source in sources:
        sid = source.source_id
        if source.mechanism == "manual":
            results.append(SourceResult(sid, "MANUAL", "manual", None, "review by hand"))
            continue
        origin = "live" if fetcher is not None else "snapshot"
        try:
            content = (
                fetch_source(source, fetcher, key_for)
                if fetcher is not None
                else read_snapshot(snapshots_dir, sid)
            )
        except FetchError as exc:
            results.append(SourceResult(sid, "ERROR", origin, None, f"fetch failed: {exc}"))
            continue
        if content is None:
            results.append(
                SourceResult(
                    sid, "MISSING", "none", None, "no snapshot; capture one or use --fetch"
                )
            )
            continue
        try:
            signal = extract_signal(source.mechanism, content)
        except ExtractError as exc:
            results.append(SourceResult(sid, "ERROR", origin, None, str(exc)))
            continue
        digest = signal_hash(signal)
        entry = seen.get(sid, {})
        prior = entry.get("sha256")
        status = "NEW" if prior is None else ("CHANGED" if prior != digest else "UNCHANGED")
        detail = ""
        prior_length = (
            int(entry["signal_length"]) if entry.get("signal_length", "").isdigit() else 0
        )
        if not signal.strip():
            status, detail = "SUSPICIOUS", "signal is empty"
        elif prior_length >= MIN_PRIOR_LENGTH and len(signal) < prior_length * SHRINK_RATIO:
            status = "SUSPICIOUS"
            detail = f"signal shrank from {prior_length} to {len(signal)} characters"
        results.append(SourceResult(sid, status, origin, digest, detail, len(signal)))
    return results


def accept_results(
    seen: SeenState,
    results: Iterable[SourceResult],
    now: dt.datetime,
    accept_suspicious: bool = False,
) -> SeenState:
    """Return a copy of ``seen`` with the hashes from ``results`` recorded as the new baseline.

    A SUSPICIOUS result is skipped unless ``accept_suspicious`` is true, so an
    emptied or truncated source cannot become the baseline by accident.
    """
    updated = {sid: dict(entry) for sid, entry in seen.items()}
    stamp = now.astimezone(dt.UTC).isoformat(timespec="seconds")
    for result in results:
        if result.sha256 is None or (result.status == "SUSPICIOUS" and not accept_suspicious):
            continue
        updated[result.source_id] = {
            "sha256": result.sha256,
            "origin": result.origin,
            "checked": stamp,
            "signal_length": str(result.signal_length or 0),
        }
    return updated


def capture_sources(
    sources: Iterable[Source],
    fetcher: Fetcher,
    snapshots_dir: Path,
    protected: Iterable[Path],
    key_for: KeyLookup | None = None,
) -> list[CaptureResult]:
    """Fetch each non-manual source and store the raw content as its snapshot.

    A keyed source gets its key from ``key_for``. The snapshot holds the body
    only, never the request URL, so a key in a query parameter is not stored.
    """
    protected_paths = list(protected)
    results: list[CaptureResult] = []
    for source in sources:
        if source.mechanism == "manual":
            results.append(CaptureResult(source.source_id, False, "manual source, not fetched"))
            continue
        try:
            content = fetch_source(source, fetcher, key_for)
        except FetchError as exc:
            results.append(CaptureResult(source.source_id, False, f"fetch failed: {exc}"))
            continue
        write_snapshot(snapshots_dir, source.source_id, content, protected_paths)
        results.append(
            CaptureResult(source.source_id, True, f"{len(content.encode('utf-8'))} bytes")
        )
    return results
