"""Repository-wide checks: nothing internal ships, and the writing rules hold."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from conftest import ROOT

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
}
TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".json",
    ".toml",
    ".csv",
    ".txt",
    ".xml",
    ".html",
    ".yaml",
    ".yml",
    ".cfg",
    ".ini",
}
TEXT_NAMES = {"LICENSE", ".gitignore", ".gitattributes", ".editorconfig"}

# Absolute home directories of any user, on macOS or Linux.
HOME_PATH = re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+")
TERMS_FILE_VARIABLE = "REGWATCH_FORBIDDEN_TERMS_FILE"
FORBIDDEN_KEYS = ("models:", "providers:", "session-link:")
EM, EN = chr(0x2014), chr(0x2013)


def text_files() -> list[Path]:
    found: list[Path] = []
    for directory, names, files in os.walk(ROOT):
        names[:] = [n for n in names if n not in SKIP_DIRS and not n.endswith(".egg-info")]
        for name in files:
            path = Path(directory) / name
            if path.suffix in TEXT_SUFFIXES or name in TEXT_NAMES:
                found.append(path)
    return sorted(found)


def markdown_files() -> list[Path]:
    return [p for p in text_files() if p.suffix == ".md"]


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def test_files_were_found() -> None:
    assert len(text_files()) > 40
    assert len(markdown_files()) > 20


def test_no_absolute_home_paths() -> None:
    hits = [relative(p) for p in text_files() if HOME_PATH.search(p.read_text(encoding="utf-8"))]
    assert hits == []


def test_no_extra_forbidden_terms() -> None:
    """Check a private list of terms kept outside the repository.

    The list is a text file, one term per line, named by REGWATCH_FORBIDDEN_TERMS_FILE.
    The repository itself never records the terms.
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
    for path in text_files():
        text = path.read_text(encoding="utf-8").lower()
        hits += [
            f"{relative(path)}: line {i}"
            for i, line in enumerate(text.splitlines(), 1)
            if any(t in line for t in terms)
        ]
    assert hits == []


def test_no_em_or_en_dashes_anywhere() -> None:
    hits = [
        relative(p) for p in text_files() if EM in (t := p.read_text(encoding="utf-8")) or EN in t
    ]
    assert hits == []


def test_no_agent_attribution_or_provenance_keys() -> None:
    hits = []
    pattern = re.compile(
        r"co-authored-by|generated with|claude-session|noreply@anthropic", re.IGNORECASE
    )
    # contributing.md states the rule and this file defines it, so both name the phrases.
    states_the_rule = {ROOT / "contributing.md", Path(__file__).resolve()}
    for path in text_files():
        text = path.read_text(encoding="utf-8")
        if pattern.search(text) and path not in states_the_rule:
            hits.append(relative(path))
        if path.suffix == ".md" and text.startswith("---"):
            hits.append(relative(path) + " has frontmatter")
        if path.suffix == ".md" and any(
            line.startswith(FORBIDDEN_KEYS) for line in text.splitlines()
        ):
            hits.append(relative(path) + " has a provenance key")
    assert hits == []


def prose_lines(path: Path) -> list[tuple[int, str]]:
    """Markdown lines outside code fences, with inline code removed."""
    lines, in_fence = [], False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            lines.append((number, re.sub(r"`[^`]*`", "", line)))
    return lines


def test_markdown_has_no_dash_punctuation() -> None:
    hits = []
    for path in markdown_files():
        for number, line in prose_lines(path):
            if re.fullmatch(r"\|[\s:|-]+\|", line.strip()):
                continue
            body = re.sub(r"^\s*(- |\d+\. )", "", line)
            if " - " in body or " -- " in body or "--" in body:
                hits.append(f"{relative(path)}:{number}")
    assert hits == []


def test_markdown_is_never_hard_wrapped() -> None:
    hits = []
    for path in markdown_files():
        previous_is_prose = False
        for number, line in prose_lines(path):
            stripped = line.strip()
            structural = (
                not stripped
                or stripped.startswith(("#", "- ", "|", ">", "<"))
                or re.match(r"^\d+\. ", stripped) is not None
            )
            if structural:
                previous_is_prose = False
                continue
            if previous_is_prose:
                hits.append(f"{relative(path)}:{number}")
            previous_is_prose = True
    assert hits == []


def test_headings_are_kebab_case_and_h1_matches_the_file() -> None:
    bad = []
    for path in markdown_files():
        in_fence = False
        h1s = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("```"):
                in_fence = not in_fence
            if in_fence or not line.startswith("#"):
                continue
            match = re.match(r"^(#+) (.*)$", line)
            assert match, f"{relative(path)}: {line}"
            level, text = len(match.group(1)), match.group(2)
            if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", text):
                bad.append(f"{relative(path)}: heading '{text}'")
            if level == 1:
                h1s.append(text)
        expected = path.parent.name if path.name == "README.md" else path.stem
        if path == ROOT / "README.md":
            expected = "regwatch"
        if h1s != [expected]:
            bad.append(f"{relative(path)}: H1 {h1s}, expected {expected}")
    assert bad == []


def test_every_code_fence_has_a_language() -> None:
    bad = []
    for path in markdown_files():
        opening = True
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if line.startswith("```"):
                if opening and line.strip() == "```":
                    bad.append(f"{relative(path)}:{number}")
                opening = not opening
        assert opening, f"{relative(path)} has an unclosed fence"
    assert bad == []


def test_relative_links_resolve() -> None:
    bad = []
    for path in markdown_files():
        for number, line in prose_lines(path):
            for target in re.findall(r"\]\(([^)]+)\)", line):
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                if not (path.parent / target.split("#")[0]).exists():
                    bad.append(f"{relative(path)}:{number} -> {target}")
    assert bad == []


def test_every_folder_readme_lists_its_pages() -> None:
    missing = []
    for readme in markdown_files():
        if readme.name != "README.md" or readme.parent in (
            ROOT,
            ROOT / "docs",
            ROOT / "developer-docs",
        ):
            continue
        if "examples" in readme.parts or "tests" in readme.parts:
            continue
        text = readme.read_text(encoding="utf-8")
        for page in sorted(readme.parent.iterdir()):
            if page.suffix == ".md" and page.name != "README.md" and f"({page.name})" not in text:
                missing.append(f"{relative(readme)} does not link {page.name}")
            if page.is_dir() and not (page / "README.md").exists():
                missing.append(f"{relative(page)} has no README.md")
    assert missing == []


def test_every_page_opens_with_a_purpose_paragraph() -> None:
    bad = []
    for path in markdown_files():
        if "examples" in path.parts:
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        rest = [line for line in lines[1:] if line.strip()]
        if path == ROOT / "security.md":
            continue  # follows the reference repository, which starts with a heading
        if not rest or rest[0].startswith(("#", "-", "`", "|")):
            bad.append(relative(path))
    assert bad == []


def test_documentation_tree_has_the_diataxis_quadrants() -> None:
    for tree, quadrants in (
        ("docs", {"tutorials", "how-to-guides", "reference", "explanation", "documentation-guide"}),
        ("developer-docs", {"tutorials", "how-to-guides", "reference", "explanation"}),
    ):
        present = {p.name for p in (ROOT / tree).iterdir() if p.is_dir()}
        assert quadrants <= present, tree


def test_required_repository_files_exist() -> None:
    for name in (
        "README.md",
        "LICENSE",
        "contributing.md",
        "security.md",
        "support.md",
        "changelog.md",
        ".editorconfig",
        ".gitattributes",
        ".gitignore",
        "pyproject.toml",
    ):
        assert (ROOT / name).is_file(), name
    assert "Copyright (c) 2026 Kevin Lappe" in (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert not (ROOT / ".github").exists()


def test_filenames_are_lowercase_kebab_case() -> None:
    reserved = {"README.md", "LICENSE"}
    bad = []
    for path in text_files():
        if path.name in reserved or path.name.startswith(".") or path.name == "py.typed":
            continue
        if not re.fullmatch(r"[a-z0-9]+([-.][a-z0-9]+)*|[a-z0-9]+(_[a-z0-9]+)*\.py", path.name):
            bad.append(relative(path))
    assert [b for b in bad if not b.endswith((".py", "regwatch.toml"))] == []


@pytest.mark.parametrize("name", ["AGENTS.md", "CLAUDE.md", "CODEX.md", "GEMINI.md"])
def test_agent_instruction_files_are_not_in_the_repository_tree(name: str) -> None:
    assert not (ROOT / name).exists()
