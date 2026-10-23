"""Shared fixtures. No test may touch the network or the real home directory."""

from __future__ import annotations

import datetime as dt
import json
import shutil
import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from regwatch.config import Config, load_config
from regwatch.fetch import FetchError
from regwatch.register import Register, load_register

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
TODAY = dt.date(2026, 10, 19)
NOW = dt.datetime(2026, 10, 19, 12, 0, tzinfo=dt.UTC)


class FakeFetcher:
    """A Fetcher backed by a dict. A value that is an Exception is raised instead of returned."""

    def __init__(self, responses: dict[str, str | Exception] | None = None) -> None:
        self.responses = responses or {}
        self.requested: list[str] = []

    def fetch(self, url: str) -> str:
        self.requested.append(url)
        if url not in self.responses:
            raise FetchError(f"no fake response for {url}")
        value = self.responses[url]
        if isinstance(value, Exception):
            raise value
        return value


REPOSITORY_ONLY = (".github", "docs", "CONTRIBUTING.md")
"""Paths that exist in a clone but not in the source distribution."""


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip the tests marked `repo_only` when the repository files they read are absent.

    The source distribution carries the package and its tests but not `.github/`, `docs/` or the
    community files, so a suite run from an extracted sdist must not fail on their absence.
    """
    missing = [name for name in REPOSITORY_ONLY if not (ROOT / name).exists()]
    if not missing:
        return
    skip = pytest.mark.skip(reason=f"the source distribution omits {', '.join(missing)}")
    for item in items:
        if "repo_only" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly if any test opens a socket."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a test tried to use the network")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A writable copy of the examples directory. Returns the path of its regwatch.toml."""
    target = tmp_path / "project"
    shutil.copytree(EXAMPLES, target, ignore=shutil.ignore_patterns("state", "out"))
    return target / "regwatch.toml"


@pytest.fixture
def config(project: Path) -> Config:
    return load_config(project)


@pytest.fixture
def register(config: Config) -> Register:
    return load_register(config)


@pytest.fixture
def edit_json() -> Callable[[Path, Callable[[Any], None]], None]:
    """Return a helper that loads a JSON file, applies a mutation and writes it back."""

    def edit(path: Path, mutate: Callable[[Any], None]) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        mutate(data)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    return edit


def snapshot_responses(config: Config) -> dict[str, str]:
    """Map each example source URL to the content of its stored snapshot."""
    sources = json.loads(config.register.sources.read_text(encoding="utf-8"))["sources"]
    responses: dict[str, str] = {}
    for source in sources:
        path = config.snapshots_dir / f"{source['source_id']}.txt"
        if path.exists():
            responses[source["url"]] = path.read_text(encoding="utf-8")
    return responses


class FakeSystem:
    """Stand-ins for the keychain tools, launchctl and crontab, kept in memory.

    ``calls`` records every argument list and ``inputs`` every standard input, so a test
    can prove a key never reached a command line.
    """

    def __init__(self, platform: str = "darwin", tools: tuple[str, ...] | None = None) -> None:
        self.platform = platform
        self.tools = set(
            tools if tools is not None else ("security", "secret-tool", "launchctl", "crontab")
        )
        self.keychain: dict[str, str] = {}
        self.crontab: str | None = None
        self.calls: list[list[str]] = []
        self.inputs: list[str | None] = []
        self.fail: set[str] = set()
        self.drop_stores = False
        self.environ: dict[str, str] = {}
        self.secret = ""

    def which(self, name: str) -> str | None:
        return f"/usr/bin/{name}" if name in self.tools else None

    def run(self, args: Any, stdin: str | None) -> Any:
        from regwatch.system import CommandResult

        argv = [str(a) for a in args]
        self.calls.append(argv)
        self.inputs.append(stdin)
        tool = Path(argv[0]).name
        verb = argv[1] if len(argv) > 1 else ""
        if f"{tool} {verb}" in self.fail or tool in self.fail:
            return CommandResult(1, "", "failed")
        if tool == "security" and verb == "-i":
            import shlex

            words = shlex.split(stdin or "")
            account = words[words.index("-a") + 1]
            if not self.drop_stores:
                self.keychain[account] = words[words.index("-w") + 1]
            return CommandResult(0, "security> ")
        if tool == "security":
            account = argv[argv.index("-a") + 1]
            if verb == "find-generic-password":
                if account in self.keychain:
                    return CommandResult(0, self.keychain[account] + "\n")
                return CommandResult(44, "", "not found")
            if verb == "delete-generic-password":
                return CommandResult(0 if self.keychain.pop(account, None) else 44)
        if tool == "secret-tool":
            account = argv[argv.index("account") + 1]
            if verb == "store":
                if not self.drop_stores:
                    self.keychain[account] = stdin or ""
                return CommandResult(0)
            if verb == "lookup":
                value = self.keychain.get(account)
                return CommandResult(0 if value else 1, value or "")
            if verb == "clear":
                self.keychain.pop(account, None)
                return CommandResult(0)
        if tool == "launchctl":
            return CommandResult(0)
        if tool == "crontab" and verb == "-l":
            if self.crontab is None:
                return CommandResult(1, "", "no crontab for tester")
            return CommandResult(0, self.crontab)
        if tool == "crontab" and verb == "-":
            self.crontab = stdin or ""
            return CommandResult(0)
        raise AssertionError(f"unexpected command {argv}")

    def system(self, home: Path | None = None) -> Any:
        from regwatch.system import System

        return System(
            runner=self.run,
            platform=self.platform,
            which=self.which,
            environ=self.environ,
            home=lambda: home or Path("/nonexistent-home"),
            uid=lambda: 501,
            executable="/opt/python/bin/python3",
            read_secret=lambda prompt: self.secret,
            stdin_is_terminal=lambda: False,
        )

    def argv_text(self) -> str:
        return "\n".join(" ".join(call) for call in self.calls)
