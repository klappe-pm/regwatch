"""The operating system as the rest of regwatch sees it: one place that starts programs.

Keys are kept in the system keychain through the ``security`` command on macOS and
``secret-tool`` on Linux, and schedules are installed through ``launchctl`` and
``crontab``. Every such program is started here, by ``run_command``, with an
argument list (never a shell), a timeout, captured output and nothing secret on the
command line: a secret travels on standard input only. ``System`` bundles the
runner with the platform facts the callers need, so tests replace all of it and
never touch a real keychain, launchd or crontab.
"""

from __future__ import annotations

import getpass
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "COMMAND_TIMEOUT_SECONDS",
    "CommandResult",
    "Runner",
    "System",
    "run_command",
]

COMMAND_TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True)
class CommandResult:
    """What a program returned. ``stdout`` may hold a secret and is never printed whole."""

    returncode: int
    stdout: str = field(default="", repr=False)
    stderr: str = ""


Runner = Callable[[Sequence[str], str | None], CommandResult]


def run_command(args: Sequence[str], stdin: str | None = None) -> CommandResult:
    """Run ``args`` without a shell and return its status and output.

    ``stdin`` is written to the program's standard input. The call never raises for
    a program that fails, cannot start or runs past the timeout: those come back as
    a status of 127 (not found or not startable) or 124 (timed out), so a caller
    has one shape to handle. Nothing in the result repeats the input.
    """
    try:
        done = subprocess.run(  # noqa: S603 (an argument list from regwatch, no shell)
            list(args),
            input=stdin,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return CommandResult(124, "", "timed out")
    except OSError as exc:
        return CommandResult(127, "", exc.strerror or "cannot start the program")
    return CommandResult(done.returncode, done.stdout or "", done.stderr or "")


def _uid() -> int:
    getuid = getattr(os, "getuid", None)
    return int(getuid()) if getuid is not None else 0


@dataclass(frozen=True)
class System:
    """The platform facts and the program runner that keys and schedules use."""

    runner: Runner = run_command
    platform: str = sys.platform
    which: Callable[[str], str | None] = shutil.which
    environ: Mapping[str, str] = field(default_factory=lambda: os.environ)
    home: Callable[[], Path] = Path.home
    uid: Callable[[], int] = _uid
    executable: str = sys.executable
    read_secret: Callable[[str], str] = getpass.getpass
    stdin_is_terminal: Callable[[], bool] = lambda: sys.stdin.isatty()

    @property
    def is_macos(self) -> bool:
        """True on macOS."""
        return self.platform == "darwin"

    @property
    def is_linux(self) -> bool:
        """True on Linux."""
        return self.platform.startswith("linux")
