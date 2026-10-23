"""regwatch's own state files and the single safe way to write output.

regwatch writes in exactly two kinds of place: its state directory (snapshots,
the last-seen hashes and ingest candidates) and output paths the user names on
the command line. Every write goes through ``safe_write_text``, which refuses to
overwrite a register file and replaces the target atomically, so a crash never
leaves a half-written file and the curated register is never touched.
"""

from __future__ import annotations

import contextlib
import errno
import json
import os
import re
import secrets
import stat
from collections.abc import Iterable, Mapping
from pathlib import Path

__all__ = [
    "SOURCE_ID_RE",
    "AlreadyExistsError",
    "SeenState",
    "StateError",
    "list_run_records",
    "load_seen",
    "make_state_dir",
    "read_snapshot",
    "remove_file",
    "safe_write_bytes",
    "safe_write_text",
    "save_seen",
    "snapshot_path",
    "update_register_file",
    "write_run_record",
    "write_snapshot",
    "write_tree",
]

SOURCE_ID_RE = re.compile(r"^[a-z0-9-]+$")
MAX_STATE_BYTES = 20_000_000
RUNS_DIR = "runs"
KEEP_RUN_RECORDS = 500
_RUN_NAME = re.compile(r"^run-\d{8}T\d{6}Z-[0-9a-f]{8}\.json$")

SeenState = dict[str, dict[str, str]]


class StateError(Exception):
    """A state file is unreadable or a write was refused."""


class AlreadyExistsError(StateError):
    """A file that was to be created exclusively already exists."""


def safe_write_text(path: Path, text: str, protected: Iterable[Path]) -> None:
    """Write ``text`` as UTF-8 to ``path`` atomically.

    Refuse when ``path`` is a protected register file.
    """
    safe_write_bytes(path, text.encode("utf-8", errors="replace"), protected)


def safe_write_bytes(path: Path, data: bytes, protected: Iterable[Path]) -> None:
    """Write ``data`` to ``path`` atomically unless ``path`` is a protected register file.

    An output path that is itself a symbolic link is refused, so a link planted in a
    shared directory cannot make regwatch replace a file elsewhere. Folders above
    the file are resolved as usual. The new file replaces the one at the literal
    path: an existing file keeps its permission bits, and a new file gets the
    permissions the process umask allows, as any ordinary program would give it.
    regwatch writes no file that is meant to be private (snapshots, the last-seen
    hashes, ingest candidates and the files a user names are all ordinary output).
    """
    target = _literal_target(path)
    if any(_same_file(target, Path(p)) for p in protected):
        raise StateError(f"refusing to overwrite protected file {path}")
    if target.is_symlink():
        raise StateError(f"{path} is a symbolic link; regwatch will not write through it")
    if target.is_dir():
        raise StateError(f"{path} is a directory")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        mode = _existing_mode(target)
        descriptor, temporary = _create_temporary(target.parent)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                if mode is not None:
                    os.fchmod(handle.fileno(), mode)
                handle.write(data)
            os.replace(temporary, target)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
    except OSError as exc:
        raise StateError(f"cannot write {path}: {exc.strerror or exc}") from exc


def make_state_dir(path: Path) -> None:
    """Create the state directory and its parents when they do not exist yet.

    A scheduled run sends its output to a log file in this folder, which the
    shell (cron) or launchd opens before regwatch starts; neither creates a
    missing folder, so a schedule installed before the first run would never run.
    """
    if path.is_symlink() and not path.is_dir():
        raise StateError(f"{path} is a symbolic link that does not lead to a folder")
    if path.exists() and not path.is_dir():
        raise StateError(f"{path} is not a folder")
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StateError(f"cannot create {path}: {exc.strerror or exc}") from exc


def update_register_file(path: Path, text: str, register_paths: Iterable[Path]) -> None:
    """Rewrite one register file atomically, while every other register file stays protected.

    This is the only write to a register file, and only ``regwatch sources add``
    and ``regwatch sources remove`` make it, to the sources and jurisdictions files.
    """
    target = path.resolve()
    others = [p for p in register_paths if Path(p).resolve() != target]
    safe_write_text(path, text, others)


def write_tree(directory: Path, files: Mapping[str, str], *, replace: bool) -> None:
    """Write ``files`` (relative names with at most one folder level) under ``directory``.

    Every folder is opened once, without following a link (``O_DIRECTORY`` and
    ``O_NOFOLLOW``), before any file is written, and every file is then created
    through that open folder, so a folder that is swapped for a link afterwards
    cannot redirect a write: the writes go to the folder that was opened.

    Without ``replace`` each file is created with ``O_EXCL`` and without following
    a link, and one that already exists raises AlreadyExistsError. With ``replace``
    each file is written to a temporary file in its folder and renamed into place
    through the same folder, an existing file keeps its permission bits, and a path
    that is a symbolic link is refused. New files get 0o644 (or the 0o666 of a
    replacement), as limited by the umask. Raises StateError for any other failure.
    """
    opened: dict[str, int] = {}
    try:
        directory.mkdir(parents=True, exist_ok=True)
        opened[""] = _open_directory(directory)
        for name in files:
            folder = name.rpartition("/")[0]
            if folder and folder not in opened:
                _make_folder(opened[""], folder)
                opened[folder] = _open_directory(
                    folder, dir_fd=opened[""], shown=directory / folder
                )
        for name, text in files.items():
            folder, _, leaf = name.rpartition("/")
            data = text.encode("utf-8", errors="replace")
            if replace:
                _replace_in(opened[folder], leaf, data, directory / name)
            else:
                _create_in(opened[folder], leaf, data, directory / name)
    except OSError as exc:
        raise StateError(f"cannot write in {directory}: {exc.strerror or exc}") from exc
    finally:
        for descriptor in opened.values():
            os.close(descriptor)


def _open_directory(path: Path | str, dir_fd: int | None = None, shown: Path | None = None) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        return os.open(path, flags, dir_fd=dir_fd)
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.ENOTDIR):
            raise StateError(
                f"{shown or path} is a symbolic link or not a directory; "
                "regwatch will not write through it"
            ) from exc
        raise


def _make_folder(parent_fd: int, name: str) -> None:
    with contextlib.suppress(FileExistsError):
        os.mkdir(name, 0o777, dir_fd=parent_fd)


def _create_in(directory_fd: int, leaf: str, data: bytes, shown: Path) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    try:
        descriptor = os.open(leaf, flags, 0o644, dir_fd=directory_fd)
    except FileExistsError as exc:
        raise AlreadyExistsError(f"{shown} already exists") from exc
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)


def _replace_in(directory_fd: int, leaf: str, data: bytes, shown: Path) -> None:
    mode: int | None = None
    try:
        info = os.stat(leaf, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        info = None
    if info is not None:
        if stat.S_ISLNK(info.st_mode):
            raise StateError(f"{shown} is a symbolic link; regwatch will not write through it")
        if stat.S_ISDIR(info.st_mode):
            raise StateError(f"{shown} is a directory")
        mode = stat.S_IMODE(info.st_mode)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    for _ in range(100):
        temporary = f".regwatch-{secrets.token_hex(8)}.tmp"
        try:
            descriptor = os.open(temporary, flags, 0o666, dir_fd=directory_fd)
            break
        except FileExistsError:
            continue
    else:
        raise OSError(errno.EEXIST, "cannot create a temporary file")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            if mode is not None:
                os.fchmod(handle.fileno(), mode)
            handle.write(data)
        os.replace(temporary, leaf, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temporary, dir_fd=directory_fd)
        raise


def _literal_target(path: Path) -> Path:
    """``path`` with the folders above it resolved but its last part left as written."""
    if path.name in ("", ".", ".."):
        return path.resolve()
    return path.parent.resolve() / path.name


def _existing_mode(target: Path) -> int | None:
    """The permission bits of the regular file at ``target``, or None when there is none."""
    try:
        info = os.lstat(target)
    except FileNotFoundError:
        return None
    return stat.S_IMODE(info.st_mode) if stat.S_ISREG(info.st_mode) else None


def _create_temporary(directory: Path) -> tuple[int, str]:
    """Create a new file next to the target. Its mode is 0o666 as limited by the umask."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    for _ in range(100):
        name = directory / f".regwatch-{secrets.token_hex(8)}.tmp"
        try:
            return os.open(name, flags, 0o666), str(name)
        except FileExistsError:
            continue
    raise OSError(errno.EEXIST, "cannot create a temporary file")


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


def remove_file(path: Path, protected: Iterable[Path]) -> bool:
    """Delete the file at ``path``; True when there was one. A protected file is refused.

    A symbolic link at ``path`` is removed as a link; its target is left alone.
    """
    if any(_same_file(_literal_target(path), Path(p)) for p in protected):
        raise StateError(f"refusing to remove protected file {path}")
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise StateError(f"cannot remove {path}: {exc.strerror or exc}") from exc
    return True


def write_run_record(
    state_dir: Path,
    record: Mapping[str, object],
    started: str,
    protected: Iterable[Path],
    keep: int = KEEP_RUN_RECORDS,
) -> Path:
    """Write one run record to ``<state>/runs/`` and keep only the newest ``keep`` records.

    ``started`` is the start time as ``YYYYMMDDTHHMMSSZ``, which makes the names sort
    in time order. Only files named like a run record are ever removed.
    """
    directory = state_dir / RUNS_DIR
    path = directory / f"run-{started}-{secrets.token_hex(4)}.json"
    if not _RUN_NAME.fullmatch(path.name):
        raise StateError(f"invalid run record start time '{started}'")
    protected_paths = list(protected)
    safe_write_text(path, json.dumps(record, indent=2, sort_keys=True) + "\n", protected_paths)
    records = list_run_records(state_dir)
    for old in records[: max(0, len(records) - keep)]:
        remove_file(old, protected_paths)
    return path


def list_run_records(state_dir: Path) -> list[Path]:
    """The run record files in ``<state>/runs/``, oldest first."""
    directory = state_dir / RUNS_DIR
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir() if _RUN_NAME.fullmatch(p.name) and p.is_file())
