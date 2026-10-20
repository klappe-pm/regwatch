"""The published tree names no private tool, personal path or work item code.

The patterns are built from fragments so this file does not match itself. A private
list of further terms can be supplied from outside the repository, so the repository
itself never records them.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest
from conftest import ROOT

pytestmark = pytest.mark.repo_only

TERMS_FILE_VARIABLE = "REGWATCH_FORBIDDEN_TERMS_FILE"

FORBIDDEN = {
    "owner login": "kl" + "appe" + r"(?!-pm\b)",
    "owner email": "kevin" + r"\d+",
    "owner name": "Kevin" + r"\s+Lap" + "pe",
    "work item code": r"\bW" + r"I-\d+",
    "work item term": "work" + r"[- ]item",
    "absolute home path": r"/(?:Users|home)/[A-Za-z0-9._-]+",
}

# The published author and the repository owner appear where a licence and a package need them.
ALLOWED = {"owner name": {"LICENSE", "pyproject.toml"}}


def tracked_files() -> list[Path]:
    try:
        result = subprocess.run(  # noqa: S603
            ["git", "-C", str(ROOT), "ls-files", "-z"],  # noqa: S607
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("this is not a git checkout")
    names = [name for name in result.stdout.decode().split("\0") if name]
    me = Path(__file__).resolve()
    return [
        ROOT / name for name in names if (ROOT / name).is_file() and (ROOT / name).resolve() != me
    ]


def read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def test_no_tracked_file_names_a_private_term() -> None:
    compiled = {label: re.compile(pattern, re.IGNORECASE) for label, pattern in FORBIDDEN.items()}
    hits = []
    for path in tracked_files():
        text = read(path)
        if text is None:
            continue
        relative = path.relative_to(ROOT).as_posix()
        for label, pattern in compiled.items():
            if relative in ALLOWED.get(label, ()):
                continue
            if pattern.search(relative):
                hits.append(f"{relative}: path ({label})")
            hits += [
                f"{relative}:{number}: {label}"
                for number, line in enumerate(text.splitlines(), 1)
                if pattern.search(line)
            ]
    assert not hits, "\n".join(hits[:400])


def test_no_extra_forbidden_terms() -> None:
    """Check a private list of terms kept outside the repository.

    The list is a text file, one term per line, named by REGWATCH_FORBIDDEN_TERMS_FILE.
    The test skips when the variable is not set, which is the case on GitHub, so the
    release guide runs it locally before every release.
    """
    location = os.environ.get(TERMS_FILE_VARIABLE)
    if not location:
        pytest.skip(f"{TERMS_FILE_VARIABLE} is not set")
    terms = [
        t.strip().lower()
        for t in Path(location).read_text(encoding="utf-8").splitlines()
        if t.strip()
    ]
    hits = []
    for path in tracked_files():
        text = read(path)
        if text is None:
            continue
        relative = path.relative_to(ROOT).as_posix()
        hits += [
            f"{relative}: line {number}"
            for number, line in enumerate(text.lower().splitlines(), 1)
            if any(term in line for term in terms)
        ]
    assert hits == []
