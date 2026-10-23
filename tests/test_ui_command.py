"""`regwatch ui` starts the server on loopback, prints the address and opens the browser."""

from __future__ import annotations

from pathlib import Path

import pytest

import regwatch.cli as cli
from regwatch.cli import main
from regwatch.server import LocalServer, ServerError


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: calls.append(url) or True)
    return calls


@pytest.fixture
def stops(monkeypatch: pytest.MonkeyPatch) -> list[LocalServer]:
    served: list[LocalServer] = []

    def serve(self: LocalServer, poll_interval: float = 0.5) -> None:
        served.append(self)
        raise KeyboardInterrupt

    monkeypatch.setattr(LocalServer, "serve_forever", serve)
    return served


def test_ui_prints_the_address_and_opens_it(
    project: Path, opened: list[str], stops: list[LocalServer], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--config", str(project), "ui"]) == 0
    [server] = stops
    out = capsys.readouterr().out
    assert server.url in out
    assert opened == [server.url]
    assert server.server_address[0] == "127.0.0.1"
    assert server.api.config_path == project.resolve()
    assert "stopped" in out


def test_ui_can_leave_the_browser_closed(
    project: Path, opened: list[str], stops: list[LocalServer]
) -> None:
    assert main(["--config", str(project), "ui", "--no-open"]) == 0
    assert opened == []
    assert len(stops) == 1


def test_ui_checks_the_configuration_before_starting(
    tmp_path: Path, opened: list[str], stops: list[LocalServer], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--config", str(tmp_path / "missing.toml"), "ui"]) == 2
    assert stops == [] and opened == []
    assert "cannot read configuration file" in capsys.readouterr().err


def test_ui_refuses_a_port_out_of_range(
    project: Path, stops: list[LocalServer], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--config", str(project), "ui", "--port", "70000"]) == 2
    assert "--port must be from 0 to 65535" in capsys.readouterr().err
    assert stops == []


def test_ui_reports_a_missing_build(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def missing() -> Path:
        raise ServerError("the web app is not built into this installation")

    monkeypatch.setattr(cli, "web_root", missing)
    assert main(["--config", str(project), "ui"]) == 2
    assert "not built" in capsys.readouterr().err
