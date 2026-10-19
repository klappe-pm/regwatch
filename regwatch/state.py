"""regwatch's own state files and the single safe way to write output.

regwatch writes in exactly two kinds of place: its state directory (snapshots,
the last-seen hashes and ingest candidates) and output paths the user names on
the command line. Every write goes through ``safe_write_text``, which refuses to
overwrite a register file and replaces the target atomically, so a crash never
leaves a half-written file and the curated register is never touched.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Iterable
from pathlib import Path

__all__ = [
    "SOURCE_ID_RE",
    "SeenState",
    "StateError",
    "load_seen",
    "read_snapshot",
    "safe_write_bytes",
    "safe_write_text",
    "save_seen",
    "snapshot_path",
    "write_snapshot",
]

SOURCE_ID_RE = re.compile(r"^[a-z0-9-]+$")
MAX_STATE_BYTES = 20_000_000

SeenState = dict[str, dict[str, str]]


class StateError(Exception):
    """A state file is unreadable or a write was refused."""


def safe_write_text(path: Path, text: str, protected: Iterable[Path]) -> None:
    """Write ``text`` as UTF-8 to ``path`` atomically unless ``path`` is a protected register file."""
    safe_write_bytes(path, text.encode("utf-8", errors="replace"), protected)


def safe_write_bytes(path: Path, data: bytes, protected: Iterable[Path]) -> None:
    """Write ``data`` to ``path`` atomically unless ``path`` is a protected register file."""
    target = path.resolve()
    if any(_same_file(target, Path(p)) for p in protected):
        raise StateError(f"refusing to overwrite protected file {path}")
    if target.is_dir():
        raise StateError(f"{path} is a directory")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            dir=target.parent, prefix=".regwatch-", suffix=".tmp"
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
            os.replace(temporary, target)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
    except OSError as exc:
        raise StateError(f"cannot write {path}: {exc.strerror or exc}") from exc


def _same_file(target: Path, protected: Path) -> bool:
    """True when ``target`` is the protected file, even under another case or a hard link.

    When both paths exist they are compared with ``os.path.samefile``, which
    follows the device and inode and so sees through case-insensitive file
    systems, symbolic links and hard links. When the target does not exist yet,
    the resolved paths are compared with case folded, so a differently cased name
    for a protected file is refused even on a case-sensitive file system.
    """
    protected = protected.resolve()
    if target.exists() and protected.exists():
        try:
            return os.path.samefile(target, protected)
        except OSError:
            return False
    return str(target).casefold() == str(protected).casefold()


def snapshot_path(snapshots_dir: Path, source_id: str) -> Path:
    """Return the snapshot file for ``source_id``, refusing ids that could escape the directory."""
    if not SOURCE_ID_RE.fullmatch(source_id):
        raise StateError(f"invalid source id '{source_id}'")
    return snapshots_dir / f"{source_id}.txt"


def read_snapshot(snapshots_dir: Path, source_id: str) -> str | None:
    """Return the stored snapshot text for ``source_id``, or None when there is none."""
    path = snapshot_path(snapshots_dir, source_id)
    if not path.is_file():
        return None
    try:
        if path.stat().st_size > MAX_STATE_BYTES:
            raise StateError(f"snapshot {path} is too large")
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise StateError(f"cannot read snapshot {path}: {exc.strerror or exc}") from exc


def write_snapshot(
    snapshots_dir: Path, source_id: str, content: str, protected: Iterable[Path]
) -> Path:
    """Store ``content`` as the snapshot for ``source_id`` and return its path."""
    path = snapshot_path(snapshots_dir, source_id)
    safe_write_text(path, content, protected)
    return path


def load_seen(path: Path) -> SeenState:
    """Load the last-seen state, returning an empty state when the file does not exist."""
    if not path.exists():
        return {}
    try:
        if path.stat().st_size > MAX_STATE_BYTES:
            raise StateError(f"state file {path} is too large")
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise StateError(f"cannot read state file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise StateError(f"state file {path} must hold a JSON object")
    state: SeenState = {}
    for source_id, entry in data.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("sha256"), str):
            raise StateError(f"state file {path} has a malformed entry for '{source_id}'")
        state[str(source_id)] = {str(k): str(v) for k, v in entry.items()}
    return state


def save_seen(path: Path, state: SeenState, protected: Iterable[Path]) -> None:
    """Write the last-seen state."""
    safe_write_text(path, json.dumps(state, indent=2, sort_keys=True) + "\n", protected)
