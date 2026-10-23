"""Scheduled runs: the launchd agent on macOS and the crontab block elsewhere.

A schedule runs ``regwatch run`` (a capture, then a check with ``--exit-code``) at
a fixed cadence, with the interpreter that runs regwatch now, named by absolute
path, so the job does not depend on a shell's ``PATH``. Everything here builds
text or bytes; installing it (writing the file, calling ``launchctl`` or
``crontab``) belongs to the command line, through the injected system runner.
"""

from __future__ import annotations

import plistlib
import re
import shlex
from collections.abc import Iterable, Sequence
from pathlib import Path

__all__ = [
    "CADENCES",
    "CRON_TIMES",
    "INTERVAL_SECONDS",
    "LABEL",
    "ScheduleError",
    "cron_block",
    "installed_block",
    "plist_bytes",
    "plist_path",
    "program_arguments",
    "replace_block",
    "schedule_cadence",
]

LABEL = "io.github.klappe-pm.regwatch"
CADENCES = ("hourly", "daily", "weekly")
INTERVAL_SECONDS = {"hourly": 3600, "daily": 86400, "weekly": 604800}
# A minute past the hour that is not :00, so many machines do not all start at once.
CRON_TIMES = {"hourly": "17 * * * *", "daily": "17 6 * * *", "weekly": "17 6 * * 1"}
BEGIN = f"# BEGIN {LABEL} (managed by regwatch schedule; do not edit)"
END = f"# END {LABEL}"
_BLOCK = re.compile(re.escape(BEGIN) + r"\n.*?" + re.escape(END) + r"\n?", re.DOTALL)


class ScheduleError(Exception):
    """A schedule cannot be built or installed. The message says why."""


def schedule_cadence(cadences: Iterable[str]) -> str:
    """The most frequent cadence among ``cadences``; ``daily`` when none is recognised."""
    found = {c.strip().lower() for c in cadences} & set(CADENCES)
    for cadence in CADENCES:
        if cadence in found:
            return cadence
    return "daily"


def program_arguments(executable: str, config_path: Path) -> list[str]:
    """The command a schedule runs: this interpreter, ``-m regwatch``, the config and ``run``."""
    if not Path(executable).is_absolute():
        raise ScheduleError(f"the interpreter path {executable} is not absolute")
    return [executable, "-m", "regwatch", "--config", str(config_path.resolve()), "run"]


def plist_path(home: Path) -> Path:
    """Where the launchd agent lives."""
    return home / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def plist_bytes(arguments: Sequence[str], every: str, working_dir: Path, log_path: Path) -> bytes:
    """The launchd agent property list for a run every ``every``."""
    if every not in INTERVAL_SECONDS:
        raise ScheduleError(f"unknown cadence {every}; use {', '.join(CADENCES)}")
    agent = {
        "Label": LABEL,
        "ProgramArguments": list(arguments),
        "StartInterval": INTERVAL_SECONDS[every],
        "RunAtLoad": False,
        "WorkingDirectory": str(working_dir),
        "StandardOutPath": str(log_path),
        "StandardErrorPath": str(log_path),
        "ProcessType": "Background",
    }
    return plistlib.dumps(agent, sort_keys=False)


def cron_block(arguments: Sequence[str], every: str, working_dir: Path, log_path: Path) -> str:
    """The crontab lines, between marker comments, for a run every ``every``.

    Every argument is quoted for the shell cron uses. A ``%`` or a line break in a
    path would be read by cron itself, so such a path is refused.
    """
    if every not in CRON_TIMES:
        raise ScheduleError(f"unknown cadence {every}; use {', '.join(CADENCES)}")
    parts = [*arguments, str(working_dir), str(log_path)]
    if any("%" in part or "\n" in part or "\r" in part for part in parts):
        raise ScheduleError("a path holds % or a line break, which cron cannot run")
    command = " ".join(shlex.quote(part) for part in arguments)
    line = (
        f"{CRON_TIMES[every]} cd {shlex.quote(str(working_dir))} && {command} "
        f">> {shlex.quote(str(log_path))} 2>&1"
    )
    return f"{BEGIN}\n{line}\n{END}\n"


def installed_block(crontab: str) -> str | None:
    """The regwatch block in a crontab, or None when there is none."""
    match = _BLOCK.search(crontab)
    return match.group(0) if match else None


def replace_block(crontab: str, block: str | None) -> str:
    """``crontab`` with the regwatch block replaced by ``block``, or removed when it is None.

    Every other line stays as it was.
    """
    without = _BLOCK.sub("", crontab)
    if block is None:
        return without
    if without and not without.endswith("\n"):
        without += "\n"
    return without + block
