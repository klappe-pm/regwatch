"""The web app's own logic tests, in web/tests/, run with Node's built-in test runner.

They need Node 22.18 or newer, which loads the TypeScript modules they test by
stripping their types, so they run from a checkout with Node and are skipped
elsewhere (the installed wheel carries the built pages, not their source).
"""

from __future__ import annotations

import shutil
import subprocess

import pytest
from conftest import ROOT

WEB_TESTS = ROOT / "web" / "tests"


def _node() -> str | None:
    node = shutil.which("node")
    if node is None:
        return None
    probe = subprocess.run(  # noqa: S603 (an argument list, the node found on the path)
        [node, "-e", "process.exit(process.features.typescript ? 0 : 1)"],
        capture_output=True,
        timeout=30,
        check=False,
    )
    return node if probe.returncode == 0 else None


@pytest.mark.repo_only
def test_the_web_logic_tests_pass() -> None:
    node = _node()
    if node is None:
        pytest.skip("Node 22.18 or newer is needed to run web/tests/")
    files = sorted(str(path) for path in WEB_TESTS.glob("*.test.mjs"))
    assert files, "web/tests/ holds no test file"
    result = subprocess.run(  # noqa: S603 (an argument list of repository test files)
        [node, "--test", *files],
        cwd=ROOT / "web",
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-2000:]
    assert "# fail 0" in result.stdout
