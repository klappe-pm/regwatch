"""The release workflow pins its actions, splits build, test and publish, and installs hashes."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
from conftest import ROOT

from regwatch.system import CommandResult, run_command

pytestmark = pytest.mark.repo_only

WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
REQUIREMENTS = ROOT / "requirements"


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def jobs() -> dict[str, str]:
    """Split the workflow into its jobs: the text of each block under `jobs:`."""
    body = workflow_text().split("\njobs:\n", 1)[1]
    parts = re.split(r"^  ([a-z][a-z-]*):\n", body, flags=re.MULTILINE)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts), 2)}


def run_commands(block: str) -> list[str]:
    """The shell commands of a job, with a continued command joined onto one line."""
    text = re.sub(r"\\\n\s*", " ", block)
    return [line.strip() for line in text.splitlines() if "pip install" in line]


def test_only_the_release_and_web_workflows_exist() -> None:
    workflows = []
    git = shutil.which("git")
    if git is not None:
        result = run_command([git, "-C", str(ROOT), "ls-files", ".github/workflows"])
        if result.returncode == 0:
            workflows = sorted(
                line.rsplit("/", 1)[-1] for line in result.stdout.splitlines() if line
            )
    if not workflows:
        workflows = sorted(p.name for p in WORKFLOW.parent.iterdir())
    assert workflows == ["release.yml", "web.yml"]


def test_the_web_workflow_pins_its_actions_and_installs_from_the_locks() -> None:
    """The pull request checks hold the same line as the release: pinned actions, no kept
    credentials, read-only permissions, hash-pinned Python tools and the web lockfile."""
    text = (WORKFLOW.parent / "web.yml").read_text(encoding="utf-8")
    uses = re.findall(r"uses:\s*(\S+)", text)
    assert uses, "the web workflow uses no action"
    assert all(re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", ref) for ref in uses), uses
    assert text.count("persist-credentials: false") == text.count("actions/checkout@")
    assert "permissions:\n  contents: read" in text
    assert "id-token" not in text
    for line in run_commands(text):
        assert "--require-hashes" in line, line
    assert "npm --prefix web ci --include=dev --ignore-scripts" in text


def test_workflow_inventory_uses_resolved_git_and_the_program_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / ".github" / "workflows"
    folder.mkdir(parents=True)
    (folder / "release.yml").write_text("name: example\n", encoding="utf-8")
    (folder / "ignored.yml").write_text("name: ignored\n", encoding="utf-8")
    calls: list[list[str]] = []

    def run(args: list[str]) -> CommandResult:
        calls.append(args)
        return CommandResult(0, ".github/workflows/release.yml\n.github/workflows/web.yml\n")

    monkeypatch.setattr(f"{__name__}.ROOT", tmp_path)
    monkeypatch.setattr(f"{__name__}.WORKFLOW", folder / "release.yml")
    monkeypatch.setattr(shutil, "which", lambda name: "/synthetic/bin/git")
    monkeypatch.setattr(f"{__name__}.run_command", run, raising=False)

    test_only_the_release_and_web_workflows_exist()

    assert calls == [["/synthetic/bin/git", "-C", str(tmp_path), "ls-files", ".github/workflows"]]


def test_the_jobs_are_build_test_and_publish() -> None:
    assert list(jobs()) == ["build", "test", "publish"]


def test_every_action_is_pinned_to_a_full_commit() -> None:
    uses = re.findall(r"uses:\s*(\S+)", workflow_text())
    assert uses
    for ref in uses:
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", ref), ref
    for line in workflow_text().splitlines():
        if "uses:" in line:
            assert re.search(r"# v\d+\.\d+\.\d+$", line), f"no version comment: {line.strip()}"


def test_id_token_is_granted_only_to_the_publish_job() -> None:
    text = workflow_text()
    assert text.count("id-token") == 1
    assert "id-token: write" in jobs()["publish"]
    assert "environment: pypi" in jobs()["publish"]
    assert re.search(r"^permissions:\n  contents: read$", text, re.MULTILINE)


def test_publish_waits_for_the_build_and_the_test() -> None:
    assert re.search(r"needs: \[build, test\]", jobs()["publish"])
    assert "pip install" not in jobs()["publish"]


def test_checkout_does_not_keep_credentials() -> None:
    for name, block in jobs().items():
        if "actions/checkout" in block:
            assert "persist-credentials: false" in block, name


def test_every_pip_install_requires_hashes_or_installs_the_local_artifact() -> None:
    commands = [c for block in jobs().values() for c in run_commands(block)]
    assert commands
    for command in commands:
        if "--require-hashes" in command:
            assert re.search(r"-r requirements/(ci|build)\.txt\b", command), command
        else:
            assert "--no-deps" in command, command
            assert re.search(r"--no-deps (dist/\*\.whl|\.)(\s|$)", command), command


def test_build_and_test_steps_are_in_different_jobs() -> None:
    blocks = jobs()
    assert "python -m build" in blocks["build"]
    assert "pytest" not in blocks["build"]
    assert "pytest" in blocks["test"]
    assert "python -m build" not in blocks["test"]
    assert "python -m build" not in blocks["publish"]
    assert "pytest" not in blocks["publish"]


def test_the_build_uses_only_the_pinned_tools_and_no_isolated_download() -> None:
    build = jobs()["build"]
    assert "pip install --require-hashes -r requirements/build.txt" in build
    assert "python -m build --no-isolation" in build


def test_the_test_job_tests_the_wheel_the_build_job_made() -> None:
    test = jobs()["test"]
    assert "actions/download-artifact" in test
    assert "pip install --no-deps dist/*.whl" in test
    assert "pip install --require-hashes -r requirements/ci.txt" in test
    assert "rm -r regwatch" in test
    assert "site-packages" in test
    assert test.index("rm -r regwatch") < test.index("python -m pytest")


def test_the_build_checks_the_tag_against_the_version_and_against_main() -> None:
    build = jobs()["build"]
    assert "merge-base --is-ancestor" in build
    assert "origin/main" in build
    assert "fetch-depth: 0" in build
    assert re.search(r'test "v\$\{version\}" = "\$\{TAG\}"', build)


def test_the_build_writes_checksums_to_the_job_summary() -> None:
    build = jobs()["build"]
    assert "sha256sum dist/*" in build
    assert "GITHUB_STEP_SUMMARY" in build


@pytest.mark.parametrize("name", ["ci", "build"])
def test_each_lock_file_pins_every_requirement_with_hashes(name: str) -> None:
    assert (REQUIREMENTS / f"{name}.in").is_file()
    lock = (REQUIREMENTS / f"{name}.txt").read_text(encoding="utf-8")
    requirements = re.findall(r"^([A-Za-z0-9_.-]+)==\S+ \\$", lock, flags=re.MULTILINE)
    assert requirements
    entries = re.split(r"^(?=[A-Za-z0-9_.-]+==)", lock, flags=re.MULTILINE)[1:]
    assert len(entries) == len(requirements)
    for entry in entries:
        assert re.search(r"--hash=sha256:[0-9a-f]{64}", entry), entry.splitlines()[0]


def test_the_build_lock_pins_hatchling_exactly() -> None:
    lock = (REQUIREMENTS / "build.txt").read_text(encoding="utf-8")
    assert re.search(r"^hatchling==\d+\.\d+\.\d+ \\$", lock, flags=re.MULTILINE)
    assert re.search(r"^build==\d+\.\d+\.\d+ \\$", lock, flags=re.MULTILINE)


def test_the_test_lock_keeps_pytest_above_the_patched_release() -> None:
    lock = (REQUIREMENTS / "ci.txt").read_text(encoding="utf-8")
    match = re.search(r"^pytest==(\d+)\.(\d+)\.(\d+) \\$", lock, flags=re.MULTILINE)
    assert match
    assert tuple(int(part) for part in match.groups()) >= (9, 0, 3)
    pygments = re.search(r"^pygments==(\d+)\.(\d+)\.(\d+) \\$", lock, flags=re.MULTILINE)
    assert pygments
    assert tuple(int(part) for part in pygments.groups()) >= (2, 20, 0)


def test_the_build_backend_requirement_is_bounded() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires = ["hatchling>=1.27,<2"]' in pyproject


def test_the_extras_are_exactly_test_and_lint() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'test = ["pytest>=9.0.3", "pytest-cov>=7"]' in pyproject
    assert 'lint = ["ruff", "mypy"]' in pyproject
    section = pyproject.split("[project.optional-dependencies]", 1)[1].split("\n[", 1)[0]
    assert re.findall(r"^(\w+) =", section, flags=re.MULTILINE) == ["test", "lint"]


def test_every_sdist_include_is_anchored() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    section = pyproject.split("[tool.hatch.build.targets.sdist]", 1)[1].split("\n[", 1)[0]
    include = re.search(r"include = \[(.*?)\]", section, flags=re.DOTALL)
    assert include
    patterns = re.findall(r'"([^"]+)"', include.group(1))
    assert patterns
    assert all(pattern.startswith("/") for pattern in patterns), patterns


def test_the_build_job_builds_the_web_app_from_its_lockfile_before_the_wheel() -> None:
    build = jobs()["build"]
    assert "actions/setup-node@" in build
    assert "package-manager-cache: false" in build
    assert "npm --prefix web ci --ignore-scripts" in build
    assert "npm install" not in build
    assert build.index("npm --prefix web ci") < build.index("npm --prefix web run build")
    assert build.index("npm --prefix web run build") < build.index("python -m build")


def test_the_build_job_fails_when_the_committed_web_app_is_stale() -> None:
    build = jobs()["build"]
    assert "git diff --exit-code -- regwatch/web" in build
    assert "git status --porcelain -- regwatch/web" in build
    assert build.index("git diff --exit-code") < build.index("python -m build")
