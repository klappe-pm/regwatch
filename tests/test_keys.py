"""Keys in the keychain: storing, reading, removing, and never showing a key."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from conftest import FakeSystem

import regwatch.system as system_module
from regwatch.keys import KeyStore, KeyStoreError, check_key
from regwatch.system import CommandResult, System, run_command

# Assembled from fragments so no file holds a token-shaped value.
KEY = "fake" + "-key-" + "0123"
VAR = "REGWATCH_KEY_TEST"


@pytest.fixture(params=["darwin", "linux"])
def fake(request: pytest.FixtureRequest) -> FakeSystem:
    return FakeSystem(platform=request.param)


def store_for(fake: FakeSystem) -> KeyStore:
    return KeyStore(fake.system())


def test_a_key_is_stored_read_back_and_removed(fake: FakeSystem) -> None:
    store = store_for(fake)
    assert store.backend == ("macos" if fake.platform == "darwin" else "linux")
    assert store.status(VAR).source == "missing"
    store.set(VAR, KEY)
    assert store.get(VAR) == KEY
    assert store.status(VAR).source == "keychain"
    assert store.status(VAR).present
    assert store.delete(VAR) is True
    assert store.get(VAR) is None
    assert store.delete(VAR) is False


def test_the_key_never_reaches_a_command_line(fake: FakeSystem) -> None:
    store = store_for(fake)
    store.set(VAR, KEY)
    store.get(VAR)
    store.delete(VAR)
    assert KEY not in fake.argv_text()
    assert any(KEY in (text or "") for text in fake.inputs)


def test_macos_writes_the_command_to_security_interactive_mode() -> None:
    fake = FakeSystem("darwin")
    store_for(fake).set(VAR, KEY)
    assert fake.calls[0] == ["/usr/bin/security", "-i"]
    assert fake.inputs[0] == (
        f'add-generic-password -U -s regwatch -a {VAR} -l "regwatch {VAR}" -w "{KEY}"\n'
    )


def test_linux_passes_the_key_to_secret_tool_on_standard_input() -> None:
    fake = FakeSystem("linux")
    store_for(fake).set(VAR, KEY)
    assert fake.calls[0][:2] == ["/usr/bin/secret-tool", "store"]
    assert fake.inputs[0] == KEY


def test_the_environment_overrides_the_keychain(fake: FakeSystem) -> None:
    fake.environ[VAR] = "from" + "-environment"
    store = store_for(fake)
    store.set(VAR, KEY)
    assert store.get(VAR) == "from-environment"
    assert store.status(VAR).source == "environment"
    assert store.stored(VAR) == KEY


def test_without_a_keychain_tool_the_environment_variable_is_named() -> None:
    fake = FakeSystem("darwin", tools=())
    store = store_for(fake)
    assert store.backend is None
    assert store.backend_label == "no keychain"
    assert store.get(VAR) is None
    assert store.status(VAR).source == "unavailable"
    with pytest.raises(KeyStoreError, match=f"set the environment variable {VAR}"):
        store.set(VAR, KEY)
    with pytest.raises(KeyStoreError, match="no keychain tool"):
        store.delete(VAR)
    assert KeyStore(System(platform="win32")).backend is None


def test_a_failed_store_is_reported_without_the_key(fake: FakeSystem) -> None:
    fake.fail.add("security -i" if fake.platform == "darwin" else "secret-tool store")
    with pytest.raises(KeyStoreError) as caught:
        store_for(fake).set(VAR, KEY)
    assert "could not store" in str(caught.value)
    assert KEY not in str(caught.value)


def test_a_store_that_silently_did_nothing_is_reported(fake: FakeSystem) -> None:
    fake.drop_stores = True
    with pytest.raises(KeyStoreError, match="did not keep the key") as caught:
        store_for(fake).set(VAR, KEY)
    assert KEY not in str(caught.value)


def test_a_failed_removal_is_reported(fake: FakeSystem) -> None:
    store = store_for(fake)
    store.set(VAR, KEY)
    fake.fail.add(
        "security delete-generic-password" if fake.platform == "darwin" else "secret-tool clear"
    )
    with pytest.raises(KeyStoreError, match="could not remove"):
        store.delete(VAR)


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("", "empty"),
        ("x" * 4097, "longer than 4096"),
        ("with space", "printable ASCII"),
        ('quote"' + "d", "printable ASCII"),
        ("back\\slash", "printable ASCII"),
        ("line\nbreak", "printable ASCII"),
        ("café", "printable ASCII"),
    ],
)
def test_an_unusable_key_is_refused_without_repeating_it(value: str, message: str) -> None:
    with pytest.raises(KeyStoreError, match=message) as caught:
        check_key(value)
    if value:
        assert value not in str(caught.value)
    assert check_key(KEY) == KEY


def _security_room(var: str) -> int:
    fixed = f'add-generic-password -U -s regwatch -a {var} -l "regwatch {var}" -w ""\n'
    return 4095 - len(fixed.encode())


def test_the_security_line_fits_its_4096_byte_buffer() -> None:
    """security -i reads a line with fgets into 4096 bytes; a longer one runs its tail."""
    fake = FakeSystem("darwin")
    value = "k" * _security_room(VAR)
    store_for(fake).set(VAR, value)
    assert len(fake.inputs[0].encode()) == 4095
    assert fake.inputs[0].endswith(f'-w "{value}"\n')


@pytest.mark.parametrize("extra", [1, 50])
def test_a_key_too_long_for_the_security_line_is_refused(extra: int) -> None:
    fake = FakeSystem("darwin")
    value = "k" * (_security_room(VAR) + extra)
    with pytest.raises(KeyStoreError, match="too long for the macOS keychain command") as caught:
        store_for(fake).set(VAR, value)
    assert f"at most {_security_room(VAR)} characters" in str(caught.value)
    assert VAR in str(caught.value)
    assert value not in str(caught.value)
    assert fake.calls == [] and fake.inputs == []


def test_secret_tool_has_no_line_limit() -> None:
    fake = FakeSystem("linux")
    value = "k" * 4096
    store_for(fake).set(VAR, value)
    assert store_for(fake).stored(VAR) == value


def test_the_key_variable_name_is_checked(fake: FakeSystem) -> None:
    store = store_for(fake)
    for operation in (store.get, store.stored, store.status, store.delete):
        with pytest.raises(KeyStoreError, match="not a key variable name"):
            operation("bad name; rm")
    with pytest.raises(KeyStoreError, match="not a key variable name"):
        store.set("lower", KEY)
    assert fake.calls == []


# --- the runner ------------------------------------------------------------------------


def test_run_command_returns_status_and_output(tmp_path: Path) -> None:
    script = tmp_path / "echo.py"
    script.write_text("import sys\nprint(sys.stdin.read().upper())\n", encoding="utf-8")
    import sys

    result = run_command([sys.executable, "-I", str(script)], "abc")
    assert result == CommandResult(0, "ABC\n", "")
    assert "ABC" not in repr(result)


def test_run_command_reports_a_missing_program_and_a_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run_command([str(tmp_path / "missing")]).returncode == 127

    def slow(*args: object, **kwargs: object) -> object:
        raise subprocess.TimeoutExpired("x", 1)

    monkeypatch.setattr(system_module.subprocess, "run", slow)
    assert run_command(["anything"]) == CommandResult(124, "", "timed out")


def test_system_platform_flags() -> None:
    assert System(platform="darwin").is_macos
    assert System(platform="linux").is_linux
    assert not System(platform="linux").is_macos
    assert isinstance(System().uid(), int)
