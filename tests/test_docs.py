"""The documentation and the repository layout stay linked, consistently styled and public safe.

These tests read repository files that a source distribution omits, so they carry the
``repo_only`` marker and skip when those files are missing.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from conftest import ROOT

pytestmark = pytest.mark.repo_only

DOCS = ROOT / "docs"
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
# Internal pages are gitignored and never published, so no test reads them.
INTERNAL = (DOCS / "documentation-guide",)
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
COMMUNITY_FILES = (
    "README.md",
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "SUPPORT.md",
)
RESERVED_NAMES = {*COMMUNITY_FILES, "LICENSE", "PULL_REQUEST_TEMPLATE.md"}
GITHUB_FILES = [
    "ISSUE_TEMPLATE/bug-report.yml",
    "ISSUE_TEMPLATE/config.yml",
    "ISSUE_TEMPLATE/feature-request.yml",
    "ISSUE_TEMPLATE/question.yml",
    "PULL_REQUEST_TEMPLATE.md",
    "regwatch-banner.svg",
    "workflows/release.yml",
]
QUADRANTS = ("tutorials", "how-to-guides", "reference", "explanation")

SMALL_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "but",
    "by",
    "for",
    "in",
    "nor",
    "of",
    "on",
    "or",
    "the",
    "to",
    "vs",
    "via",
    "with",
    "into",
    "from",
}
FENCE = re.compile(r"^\s*```")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HOME_PATH = re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+")
FORBIDDEN_KEYS = re.compile(r"^(models|providers|session-link)\s*:", re.MULTILINE)
ATTRIBUTION = re.compile(r"co-authored-by|generated with|claude-session|noreply@anthropic", re.I)
ROBOT = "\U0001f916"
EM, EN = chr(0x2014), chr(0x2013)


def text_files() -> list[Path]:
    found: list[Path] = []
    for directory, names, files in os.walk(ROOT):
        here = Path(directory)
        names[:] = [
            n
            for n in names
            if n not in SKIP_DIRS
            and not n.endswith(".egg-info")
            and here / n not in INTERNAL
            and not (here == ROOT / "docs" and n == "documentation-guide")
        ]
        found += [
            here / name
            for name in files
            if Path(name).suffix in TEXT_SUFFIXES or name in TEXT_NAMES
        ]
    return sorted(found)


def markdown_files() -> list[Path]:
    return [p for p in text_files() if p.suffix == ".md"]


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def headings(path: Path) -> list[tuple[int, int, str]]:
    found, fenced = [], False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if FENCE.match(line):
            fenced = not fenced
            continue
        match = None if fenced else HEADING.match(line)
        if match:
            found.append((number, len(match.group(1)), match.group(2)))
    return found


def prose_lines(path: Path) -> list[tuple[int, str]]:
    """Markdown lines outside code fences, with inline code removed."""
    lines, fenced = [], False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if FENCE.match(line):
            fenced = not fenced
            continue
        if not fenced:
            lines.append((number, re.sub(r"`[^`]*`", "", line)))
    return lines


def slug(text: str) -> str:
    text = re.sub(r"[`*]", "", text.lower())
    return re.sub(r"[^a-z0-9 _-]", "", text).strip().replace(" ", "-")


MARKDOWN = markdown_files()
IDS = [relative(p) for p in MARKDOWN]


def test_files_were_found() -> None:
    assert len(text_files()) > 40
    assert len(MARKDOWN) > 30


# The pull request template keeps the wording of its model and has no title.
PAGES = [p for p in MARKDOWN if ".github" not in p.parts]
PAGE_IDS = [relative(p) for p in PAGES]


@pytest.mark.parametrize("path", PAGES, ids=PAGE_IDS)
def test_every_heading_is_title_case(path: Path) -> None:
    bad = []
    for number, _level, text in headings(path):
        outside_code = re.sub(r"`[^`]*`", "", text)
        for index, word in enumerate(outside_code.split()):
            core = re.sub(r"^[^A-Za-z]*|[^A-Za-z]*$", "", word)
            if not core or core[0].isupper() or any(ch.isdigit() for ch in core):
                continue
            if core.lower() in SMALL_WORDS and index > 0:
                continue
            bad.append(f"{number}: {text}")
            break
    assert not bad, f"{relative(path)} has headings that are not Title Case: {bad}"


@pytest.mark.parametrize("path", PAGES, ids=PAGE_IDS)
def test_every_page_has_one_h1_and_it_comes_first(path: Path) -> None:
    found = headings(path)
    h1s = [text for _n, level, text in found if level == 1]
    if path == ROOT / "README.md":
        html_title = '<h1 align="center">Regwatch</h1>' in path.read_text(encoding="utf-8")
        assert html_title or h1s == ["Regwatch"]
        return
    assert len(h1s) == 1, f"{relative(path)} has {len(h1s)} H1 headings"
    assert found[0][1] == 1, f"{relative(path)} starts with a lower heading"


@pytest.mark.parametrize("path", MARKDOWN, ids=IDS)
def test_no_page_records_session_provenance(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    front = text.split("---", 2)[1] if text.startswith("---") else ""
    assert not FORBIDDEN_KEYS.search(front)
    assert ROBOT not in text, f"{relative(path)} has a robot byline"


def test_no_agent_attribution_in_markdown() -> None:
    # CONTRIBUTING.md states the rule, so it names the phrases.
    hits = [
        relative(p)
        for p in MARKDOWN
        if ATTRIBUTION.search(p.read_text(encoding="utf-8")) and p.name != "CONTRIBUTING.md"
    ]
    assert hits == []


def test_no_absolute_home_paths() -> None:
    hits = [relative(p) for p in text_files() if HOME_PATH.search(p.read_text(encoding="utf-8"))]
    assert hits == []


def test_no_em_or_en_dashes_anywhere() -> None:
    hits = [
        relative(p) for p in text_files() if EM in (t := p.read_text(encoding="utf-8")) or EN in t
    ]
    assert hits == []


def test_markdown_has_no_dash_punctuation() -> None:
    hits = []
    for path in MARKDOWN:
        for number, line in prose_lines(path):
            if re.fullmatch(r"\|[\s:|-]+\||-{3,}", line.strip()):
                continue
            body = re.sub(r"^\s*(- |\d+\. )", "", line)
            if " - " in body or "--" in body:
                hits.append(f"{relative(path)}:{number}")
    assert hits == []


def test_markdown_is_never_hard_wrapped() -> None:
    hits = []
    for path in MARKDOWN:
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


def test_every_code_fence_has_a_language() -> None:
    bad = []
    for path in MARKDOWN:
        opening = True
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if line.startswith("```"):
                if opening and line.strip() == "```":
                    bad.append(f"{relative(path)}:{number}")
                opening = not opening
        assert opening, f"{relative(path)} has an unclosed fence"
    assert bad == []


@pytest.mark.parametrize("path", MARKDOWN, ids=IDS)
def test_every_relative_link_resolves(path: Path) -> None:
    anchors_of: dict[Path, set[str]] = {}

    def anchors(target: Path) -> set[str]:
        if target not in anchors_of:
            anchors_of[target] = {slug(text) for _n, _l, text in headings(target)}
        return anchors_of[target]

    for _number, line in prose_lines(path):
        for target in LINK.findall(line):
            if re.match(r"^[a-z][a-z0-9+.-]*:", target):
                continue
            name, _, fragment = target.partition("#")
            resolved = (path.parent / name).resolve() if name else path
            assert resolved.exists(), f"{relative(path)} links to {target}, which does not exist"
            if fragment and resolved.suffix == ".md":
                assert fragment in anchors(resolved), (
                    f"{relative(path)} links to {target}, which has no such heading"
                )


README = ROOT / "README.md"
BADGE = re.compile(r"https://img\.shields\.io/[^\"]*")


def test_readme_links_are_absolute() -> None:
    """PyPI shows the README, so a relative link or image would break there."""
    text = README.read_text(encoding="utf-8")
    targets = [*LINK.findall(text), *re.findall(r'(?:href|src)="([^"]+)"', text)]
    assert targets
    bad = [t for t in targets if not t.startswith(("https://", "#"))]
    assert bad == []


def test_readme_follows_the_skeleton() -> None:
    text = README.read_text(encoding="utf-8")
    banner = "https://raw.githubusercontent.com/klappe-pm/regwatch/main/.github/regwatch-banner.svg"
    assert f'src="{banner}"' in text and 'width="760"' in text
    assert text.index(banner) < text.index('<h1 align="center">Regwatch</h1>') < text.index("---")
    badges = BADGE.findall(text)
    assert len(badges) == 6
    assert all("style=flat-square" in b and "labelColor=162233" in b for b in badges)
    colours = [re.search(r"(?:color=|-)([0-9a-f]{6})", b) for b in badges]
    assert [c.group(1) for c in colours if c] == ["3ddc84", "5aa9ff"] * 3
    sections = [t for _n, level, t in headings(README) if level == 2]
    assert sections == [
        "Why Regwatch?",
        "Who This Is For",
        "Highlights",
        "Installation",
        "Quick Start",
        "How It Works",
        "Commands",
        "Documentation",
        "Contributing",
        "Security",
        "License",
    ]


def test_every_folder_readme_lists_its_pages() -> None:
    missing = []
    for readme in MARKDOWN:
        if readme.name != "README.md" or readme.parent in (ROOT, DOCS):
            continue
        if "examples" in readme.parts or "tests" in readme.parts:
            continue
        text = readme.read_text(encoding="utf-8")
        for page in sorted(readme.parent.iterdir()):
            if page.suffix == ".md" and page.name != "README.md" and f"({page.name})" not in text:
                missing.append(f"{relative(readme)} does not link {page.name}")
    assert missing == []


def test_the_docs_readme_links_every_quadrant_and_page() -> None:
    text = (DOCS / "README.md").read_text(encoding="utf-8")
    missing = []
    for quadrant in QUADRANTS:
        for page in sorted((DOCS / quadrant).glob("*.md")):
            if f"({quadrant}/{page.name})" not in text:
                missing.append(f"{quadrant}/{page.name}")
    assert missing == []


def test_documentation_is_one_tree_with_the_four_quadrants() -> None:
    present = {p.name for p in DOCS.iterdir() if p.is_dir() and p.name != "documentation-guide"}
    assert present == set(QUADRANTS)
    assert not (ROOT / "developer-docs").exists()


# SECURITY.md, CODE_OF_CONDUCT.md and README.md follow their models, which start with a
# heading or markup instead of a purpose paragraph.
PURPOSE_PAGES = [
    p
    for p in PAGES
    if "examples" not in p.parts and p.name not in ("SECURITY.md", "CODE_OF_CONDUCT.md")
    if p != ROOT / "README.md"
]


@pytest.mark.parametrize("path", PURPOSE_PAGES, ids=lambda p: relative(p))
def test_every_page_opens_with_a_purpose_paragraph(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    rest = [line for line in lines[1:] if line.strip()]
    assert rest, relative(path)
    assert not rest[0].startswith(("#", "-", "`", "|")), relative(path)


def test_required_repository_files_exist() -> None:
    for name in (*COMMUNITY_FILES, "LICENSE", ".editorconfig", ".gitattributes", ".gitignore"):
        assert (ROOT / name).is_file(), name
    assert (ROOT / "pyproject.toml").is_file()
    assert (ROOT / "docs" / "README.md").is_file()
    assert "Copyright (c) 2026" in (ROOT / "LICENSE").read_text(encoding="utf-8")


def test_github_holds_only_the_allowed_files() -> None:
    github = ROOT / ".github"
    assert sorted(p.relative_to(github).as_posix() for p in github.rglob("*") if p.is_file()) == (
        GITHUB_FILES
    )


def test_filenames_are_lowercase_kebab_case() -> None:
    bad = []
    for path in text_files():
        name = path.name
        if name in RESERVED_NAMES or name.startswith(".") or name == "regwatch.toml":
            continue
        if re.fullmatch(r"_{0,2}[a-z0-9]+(_{1,2}[a-z0-9]+)*_{0,2}\.py", name):
            continue
        if not re.fullmatch(r"[a-z0-9]+([-.][a-z0-9]+)*", name):
            bad.append(relative(path))
    assert bad == []


@pytest.mark.parametrize("name", ["AGENTS.md", "CLAUDE.md", "CODEX.md", "GEMINI.md"])
def test_agent_instruction_files_are_not_in_the_repository_tree(name: str) -> None:
    assert not (ROOT / name).exists()
