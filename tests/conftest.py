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


# Files that a source distribution omits. A test that reads them is marked repo_only.
REPO_ONLY_PATHS = (".github", "docs", "CHANGELOG.md")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "repo_only: reads repository files that the source distribution omits "
        "(.github, docs, CHANGELOG.md) and skips when they are missing",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    missing = [name for name in REPO_ONLY_PATHS if not (ROOT / name).exists()]
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
