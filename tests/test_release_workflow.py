"""The release workflow pins every action, splits build, test and publish, and confines the publish permission."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.repo_only

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
RAW = WORKFLOW.read_text(encoding="utf-8") if WORKFLOW.exists() else ""
# The same text without the full-line comments, which describe the workflow in words.
TEXT = "\n".join(line for line in RAW.splitlines() if not line.lstrip().startswith("#")) + "\n"


def job(name: str) -> str:
    """The text of one job: from its header to the next job or the end of the file."""
    match = re.search(rf"^  {name}:\n(.*?)(?=^  [a-z-]+:\n|\Z)", TEXT, re.MULTILINE | re.DOTALL)
    assert match, f"no job named {name}"
    return match.group(1)


def pip_installs() -> list[str]:
    return [line.strip() for line in TEXT.splitlines() if "pip install" in line]


def test_only_the_release_workflow_exists() -> None:
    workflows = sorted(p.name for p in WORKFLOW.parent.iterdir())
    assert workflows == ["release.yml"]


def test_the_workflow_has_three_jobs() -> None:
    assert re.findall(r"^  ([a-z-]+):\n", TEXT.split("\njobs:\n", 1)[1], re.MULTILINE) == [
        "build",
        "test",
        "publish",
    ]


def test_every_action_is_pinned_to_a_full_commit() -> None:
    uses = re.findall(r"uses:\s*(\S+)", TEXT)
    assert uses
    for ref in uses:
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", ref), ref
    for line in TEXT.splitlines():
        if "uses:" in line:
            assert re.search(r"# v\d+\.\d+\.\d+$", line), f"no version comment on: {line.strip()}"


def test_id_token_is_granted_only_to_the_publish_job() -> None:
    assert TEXT.count("id-token") == 1
    assert "id-token: write" in job("publish")
    assert "environment: pypi" in job("publish")
    assert re.search(r"^permissions:\n  contents: read$", TEXT, re.MULTILINE)


def test_every_checkout_drops_its_credentials() -> None:
    checkouts = TEXT.count("actions/checkout@")
    assert checkouts >= 1
    assert TEXT.count("persist-credentials: false") == checkouts


def test_every_pip_install_uses_hashes_or_installs_the_local_wheel_without_dependencies() -> None:
    installs = pip_installs()
    assert installs
    for line in installs:
        assert "--require-hashes" in line or "--no-deps" in line, line
    local = [line for line in installs if "--no-deps" in line]
    assert all("dist/" in line and ".whl" in line for line in local)


def test_the_build_job_installs_only_the_pinned_build_tools() -> None:
    installs = [line for line in job("build").splitlines() if "pip install" in line]
    assert len(installs) == 1
    assert "--require-hashes" in installs[0] and "requirements/build.txt" in installs[0]
    assert "--no-isolation" in job("build")


def test_the_test_job_installs_the_pinned_test_tools_and_the_built_wheel() -> None:
    text = job("test")
    assert "--require-hashes -r requirements/ci.txt" in text
    assert "actions/download-artifact@" in text
    assert "pip install --no-deps dist/*.whl" in text
    assert "python -P -m pytest" in text


def test_building_and_testing_are_in_different_jobs() -> None:
    assert "pytest" not in job("build")
    assert "python -m build" not in job("test")
    assert "pytest" in job("test")
    assert "python -m build" in job("build")
    assert "pytest" not in job("publish") and "python -m build" not in job("publish")
    assert "needs: build" in job("test")
    assert "needs: [build, test]" in job("publish")


def test_the_build_job_checks_the_tag_and_writes_checksums() -> None:
    text = job("build")
    assert "merge-base --is-ancestor HEAD origin/main" in text
    assert "fetch-depth: 0" in text
    assert 'test "v${version}" = "${TAG}"' in text
    assert "sha256sum dist/*" in text and "GITHUB_STEP_SUMMARY" in text


def test_the_lock_files_carry_hashes_and_come_from_input_files() -> None:
    for name in ("build", "ci"):
        source = ROOT / "requirements" / f"{name}.in"
        lock = (ROOT / "requirements" / f"{name}.txt").read_text(encoding="utf-8")
        assert source.is_file()
        pins = re.findall(r"^([A-Za-z0-9._-]+)==\S+ \\$", lock, re.MULTILINE)
        assert pins
        hashed = re.split(r"^[A-Za-z0-9._-]+==", lock, flags=re.MULTILINE)[1:]
        assert all("--hash=sha256:" in block for block in hashed), name
    assert "hatchling" in (ROOT / "requirements" / "build.txt").read_text(encoding="utf-8")
