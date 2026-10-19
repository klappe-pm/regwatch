from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from regwatch.state import (
    StateError,
    load_seen,
    read_snapshot,
    safe_write_bytes,
    safe_write_text,
    save_seen,
    snapshot_path,
    write_snapshot,
)


def test_safe_write_text_creates_parents_and_replaces(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "out.txt"
    safe_write_text(target, "one", [])
    safe_write_text(target, "two", [])
    assert target.read_text(encoding="utf-8") == "two"
    assert [p.name for p in target.parent.iterdir()] == ["out.txt"]


def test_safe_write_bytes(tmp_path: Path) -> None:
    safe_write_bytes(tmp_path / "x.bin", b"\x00\x01", [])
    assert (tmp_path / "x.bin").read_bytes() == b"\x00\x01"


def test_text_is_written_as_utf8_with_lf(tmp_path: Path) -> None:
    safe_write_text(tmp_path / "t.txt", "é\nline", [])
    assert (tmp_path / "t.txt").read_bytes() == "é\nline".encode()


def test_protected_register_file_is_never_overwritten(tmp_path: Path) -> None:
    register = tmp_path / "obligations.csv"
    register.write_text("keep", encoding="utf-8")
    with pytest.raises(StateError, match="refusing to overwrite protected file"):
        safe_write_text(register, "clobber", [register])
    assert register.read_text(encoding="utf-8") == "keep"


def test_protection_follows_relative_paths_and_symlinks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    register = tmp_path / "obligations.csv"
    register.write_text("keep", encoding="utf-8")
    link = tmp_path / "link.csv"
    link.symlink_to(register)
    with pytest.raises(StateError):
        safe_write_text(link, "clobber", [register])
    monkeypatch.chdir(tmp_path)
    with pytest.raises(StateError):
        safe_write_text(Path("sub/../obligations.csv"), "clobber", [register])
    assert register.read_text(encoding="utf-8") == "keep"


def test_directory_target_is_refused(tmp_path: Path) -> None:
    with pytest.raises(StateError, match="is a directory"):
        safe_write_text(tmp_path, "x", [])


def test_write_failure_leaves_no_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(src: object, dst: object) -> None:
        raise PermissionError(13, "denied")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(StateError, match="cannot write"):
        safe_write_text(tmp_path / "out.txt", "x", [])
    assert list(tmp_path.iterdir()) == []


def test_snapshot_roundtrip(tmp_path: Path) -> None:
    assert read_snapshot(tmp_path, "src-1") is None
    path = write_snapshot(tmp_path / "snaps", "src-1", "content", [])
    assert path == tmp_path / "snaps" / "src-1.txt"
    assert read_snapshot(tmp_path / "snaps", "src-1") == "content"


@pytest.mark.parametrize("bad", ["../escape", "a/b", "UPPER", "", "with space", "a.b", ".."])
def test_snapshot_ids_cannot_escape_the_directory(tmp_path: Path, bad: str) -> None:
    with pytest.raises(StateError, match="invalid source id"):
        snapshot_path(tmp_path, bad)
    with pytest.raises(StateError):
        write_snapshot(tmp_path, bad, "x", [])
    with pytest.raises(StateError):
        read_snapshot(tmp_path, bad)


def test_oversized_snapshot_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "big.txt").write_text("0123456789", encoding="utf-8")
    monkeypatch.setattr("regwatch.state.MAX_STATE_BYTES", 5)
    with pytest.raises(StateError, match="too large"):
        read_snapshot(tmp_path, "big")


def test_seen_roundtrip_and_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "state" / "seen.json"
    assert load_seen(path) == {}
    state = {"b": {"sha256": "2", "origin": "live"}, "a": {"sha256": "1", "origin": "snapshot"}}
    save_seen(path, state, [])
    assert load_seen(path) == state
    assert list(json.loads(path.read_text(encoding="utf-8"))) == ["a", "b"]


@pytest.mark.parametrize(
    "content",
    ["not json", "[]", '{"a": 1}', '{"a": {"origin": "x"}}', '{"a": {"sha256": 5}}'],
)
def test_malformed_seen_state_is_rejected(tmp_path: Path, content: str) -> None:
    path = tmp_path / "seen.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(StateError):
        load_seen(path)


def test_oversized_seen_state_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "seen.json"
    path.write_text("{}" + " " * 20, encoding="utf-8")
    monkeypatch.setattr("regwatch.state.MAX_STATE_BYTES", 5)
    with pytest.raises(StateError, match="too large"):
        load_seen(path)


def test_save_seen_refuses_protected_path(tmp_path: Path) -> None:
    path = tmp_path / "seen.json"
    with pytest.raises(StateError):
        save_seen(path, {}, [path])


def test_unreadable_snapshot_is_a_state_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "src.txt").write_text("x", encoding="utf-8")

    def refuse(self: Path, *args: object, **kwargs: object) -> str:
        raise PermissionError(13, "denied")

    monkeypatch.setattr(Path, "read_text", refuse)
    with pytest.raises(StateError, match="cannot read snapshot"):
        read_snapshot(tmp_path, "src")
