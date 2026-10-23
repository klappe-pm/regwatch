from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from regwatch.state import (
    AlreadyExistsError,
    StateError,
    load_seen,
    read_snapshot,
    safe_write_bytes,
    safe_write_text,
    save_seen,
    snapshot_path,
    write_snapshot,
    write_tree,
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


# --- write_tree: files are written through folders opened without following a link ---


def test_write_tree_creates_files_and_the_folder_level(tmp_path: Path) -> None:
    write_tree(tmp_path / "p", {"a.txt": "one", "sub/b.txt": "two"}, replace=False)
    assert (tmp_path / "p" / "a.txt").read_text(encoding="utf-8") == "one"
    assert (tmp_path / "p" / "sub" / "b.txt").read_text(encoding="utf-8") == "two"
    with pytest.raises(AlreadyExistsError, match=r"b\.txt already exists"):
        write_tree(tmp_path / "p", {"sub/b.txt": "again"}, replace=False)
    assert (tmp_path / "p" / "sub" / "b.txt").read_text(encoding="utf-8") == "two"


def test_write_tree_replace_keeps_the_mode_and_leaves_no_temporary_file(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    target = tmp_path / "sub" / "b.txt"
    target.write_text("old", encoding="utf-8")
    target.chmod(0o640)
    write_tree(tmp_path, {"sub/b.txt": "new", "c.txt": "c"}, replace=True)
    assert target.read_text(encoding="utf-8") == "new"
    assert target.stat().st_mode & 0o777 == 0o640
    assert sorted(p.name for p in tmp_path.iterdir()) == ["c.txt", "sub"]
    assert [p.name for p in (tmp_path / "sub").iterdir()] == ["b.txt"]


def test_write_tree_refuses_a_folder_that_is_a_link(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    project = tmp_path / "project"
    project.mkdir()
    (project / "sub").symlink_to(outside)
    for replace in (False, True):
        with pytest.raises(StateError, match="symbolic link"):
            write_tree(project, {"a.txt": "x", "sub/b.txt": "x"}, replace=replace)
    assert list(outside.iterdir()) == []
    assert not (project / "a.txt").exists()  # nothing is written once a folder is refused


def test_write_tree_replace_refuses_a_link_and_a_folder_in_place_of_a_file(tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("precious", encoding="utf-8")
    (tmp_path / "link.txt").symlink_to(outside)
    (tmp_path / "dir.txt").mkdir()
    with pytest.raises(StateError, match="symbolic link"):
        write_tree(tmp_path, {"link.txt": "x"}, replace=True)
    with pytest.raises(StateError, match="is a directory"):
        write_tree(tmp_path, {"dir.txt": "x"}, replace=True)
    assert outside.read_text(encoding="utf-8") == "precious"


def test_write_tree_does_not_follow_a_link_to_a_new_file(tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("precious", encoding="utf-8")
    (tmp_path / "p").mkdir()
    (tmp_path / "p" / "a.txt").symlink_to(outside)
    with pytest.raises(AlreadyExistsError):
        write_tree(tmp_path / "p", {"a.txt": "x"}, replace=False)
    assert outside.read_text(encoding="utf-8") == "precious"


# --- the branches that guard against a name clash, a failed rename and a failed open ---------


def _fixed_names(monkeypatch: pytest.MonkeyPatch, *names: str) -> None:
    """Make the random part of a temporary name come from ``names``, then repeat the last."""
    import regwatch.state as state_module

    queue = list(names)

    def token_hex(_size: int = 16) -> str:
        return queue.pop(0) if len(queue) > 1 else queue[0]

    monkeypatch.setattr(state_module.secrets, "token_hex", token_hex)


def test_write_tree_replace_skips_a_temporary_name_that_is_taken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".regwatch-aaaa.tmp").write_text("someone else's", encoding="utf-8")
    _fixed_names(monkeypatch, "aaaa", "bbbb")
    write_tree(tmp_path, {"out.txt": "new"}, replace=True)
    assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "new"
    assert (tmp_path / ".regwatch-aaaa.tmp").read_text(encoding="utf-8") == "someone else's"
    assert sorted(p.name for p in tmp_path.iterdir()) == [".regwatch-aaaa.tmp", "out.txt"]


def test_write_tree_replace_gives_up_when_every_temporary_name_is_taken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".regwatch-aaaa.tmp").write_text("someone else's", encoding="utf-8")
    _fixed_names(monkeypatch, "aaaa")
    with pytest.raises(StateError, match="cannot write in"):
        write_tree(tmp_path, {"out.txt": "new"}, replace=True)
    assert not (tmp_path / "out.txt").exists()
    assert (tmp_path / ".regwatch-aaaa.tmp").read_text(encoding="utf-8") == "someone else's"


def test_write_tree_replace_removes_its_temporary_file_when_the_rename_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "out.txt").write_text("keep", encoding="utf-8")

    def boom(*_args: object, **_kwargs: object) -> None:
        raise PermissionError(13, "denied")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(StateError, match="cannot write in"):
        write_tree(tmp_path, {"out.txt": "new"}, replace=True)
    assert [p.name for p in tmp_path.iterdir()] == ["out.txt"]
    assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "keep"


def test_write_tree_reports_a_folder_it_cannot_open_as_a_state_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_open = os.open

    def deny_directories(path: object, flags: int, *args: object, **kwargs: object) -> int:
        if flags & os.O_DIRECTORY:
            raise PermissionError(13, "Permission denied")
        return real_open(path, flags, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "open", deny_directories)
    with pytest.raises(StateError, match="Permission denied"):
        write_tree(tmp_path, {"out.txt": "x"}, replace=False)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("leaf", ["..", "."])
def test_a_path_that_names_a_folder_through_a_dot_name_is_refused(
    tmp_path: Path, leaf: str
) -> None:
    (tmp_path / "sub").mkdir()
    with pytest.raises(StateError, match="is a directory"):
        safe_write_text(tmp_path / "sub" / leaf, "x", [])


def test_safe_write_gives_up_when_every_temporary_name_is_taken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".regwatch-aaaa.tmp").write_text("someone else's", encoding="utf-8")
    _fixed_names(monkeypatch, "aaaa")
    with pytest.raises(StateError, match="cannot write"):
        safe_write_text(tmp_path / "out.txt", "x", [])
    assert not (tmp_path / "out.txt").exists()


def test_safe_write_skips_a_temporary_name_that_is_taken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".regwatch-aaaa.tmp").write_text("someone else's", encoding="utf-8")
    _fixed_names(monkeypatch, "aaaa", "bbbb")
    safe_write_text(tmp_path / "out.txt", "x", [])
    assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "x"
    assert (tmp_path / ".regwatch-aaaa.tmp").exists()


def test_a_protected_file_that_cannot_be_compared_does_not_block_a_different_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protected = tmp_path / "register.csv"
    protected.write_text("keep", encoding="utf-8")
    target = tmp_path / "out.txt"
    target.write_text("old", encoding="utf-8")

    def broken(_a: object, _b: object) -> bool:
        raise OSError(5, "input/output error")

    monkeypatch.setattr(os.path, "samefile", broken)
    safe_write_text(target, "new", [protected])
    assert target.read_text(encoding="utf-8") == "new"
    assert protected.read_text(encoding="utf-8") == "keep"
