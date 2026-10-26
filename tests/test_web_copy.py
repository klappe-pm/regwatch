"""The words the web app shows, and what the docs say about it, stay accurate and Title Case."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from conftest import ROOT
from test_docs import SMALL_WORDS

pytestmark = pytest.mark.repo_only

PAGES = sorted((ROOT / "web" / "src").rglob("*.tsx"))
# A heading element whose content is literal text, not an expression.
HEADING = re.compile(r"<h([1-6])\b[^>]*>([^<{]+)</h\1>")


def literal_headings(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [" ".join(match.group(2).split()) for match in HEADING.finditer(text)]


def not_title_case(text: str) -> bool:
    for index, word in enumerate(text.split()):
        core = re.sub(r"^[^A-Za-z0-9]*|[^A-Za-z0-9]*$", "", word)
        if not core or any(ch.isupper() or ch.isdigit() for ch in core):
            continue
        if core.lower() in SMALL_WORDS and index > 0:
            continue
        return True
    return False


def test_the_pages_have_literal_headings_to_check() -> None:
    found = [heading for path in PAGES for heading in literal_headings(path)]
    assert "Why It Was Flagged" in found
    assert "Impacts on Your Products" in found


@pytest.mark.parametrize("path", PAGES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_every_literal_heading_is_title_case(path: Path) -> None:
    bad = [heading for heading in literal_headings(path) if not_title_case(heading)]
    assert not bad, f"{path.relative_to(ROOT)} has headings that are not Title Case: {bad}"


def test_the_ui_reference_says_run_now_fetches() -> None:
    text = " ".join((ROOT / "docs" / "reference" / "cli.md").read_text("utf-8").split())
    assert "fetches nothing" not in text
    assert "Run now on the Automations page does what `regwatch run` does" in text
    assert "Generate on the Newsletters and Documents pages sends structured facts" in text


def test_the_catalogue_reference_does_not_call_the_web_search_planned() -> None:
    text = (ROOT / "docs" / "reference" / "source-catalogue.md").read_text("utf-8")
    assert "planned for the web app" not in text
    assert "catalogue search on the Sources page" in text
