"""The words the web app shows, and what the docs say about it, stay accurate and Title Case."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from conftest import ROOT
from test_docs import SMALL_WORDS

pytestmark = pytest.mark.repo_only

WEB = ROOT / "web"
PAGES = sorted([*(WEB / "src").rglob("*.tsx"), *(WEB / "pages").rglob("*.tsx")])
COPY = json.loads((WEB / "design" / "copy.json").read_text(encoding="utf-8"))
# The text of every element comes from the copy documents, so a heading is found by the copy key
# it shows: a heading element (or a Section or PageHeader title) whose first child is a lookup
# with a literal key, such as `<Typography component="h3" ...>{p("detail.why")}`. A page's `p`
# helper prefixes the key with the page's document, read from its definition.
PREFIX = re.compile(r"const p = \([^)]*\) => t\(`([\w.-]+)\.\$\{key\}`")
LOOKUP = r"\{(p|t)\(\"([\w.-]+)\""
HEADING = re.compile(
    r"component=\"h[1-4]\"[^>]*>\s*" + LOOKUP
    + r"|<Heading\b[^>]*>\s*" + LOOKUP
    + r"|<(?:Section|PageHeader)\s+title=" + LOOKUP
)
# Fragments of a display heading split over lines (the public pages' "title-1", "title-2" and
# "title-emphasis") are sentences, as the literal headings with <br/> inside them were.
FRAGMENT = re.compile(r"(^|[.-])title-(\d|emphasis)$|\.(aside|intro)-\d$|\.title-\d$")


def heading_keys(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    prefix = PREFIX.search(text)
    keys = []
    for match in HEADING.finditer(text):
        groups = [g for g in match.groups() if g is not None]
        helper, key = groups[0], groups[1]
        keys.append(f"{prefix.group(1)}.{key}" if helper == "p" and prefix else key)
    return keys


def headings(path: Path) -> list[str]:
    # A placeholder such as {count} is filled in at run time and is not a word of the heading.
    return [
        " ".join(re.sub(r"\{\w+\}", "", COPY[key]).split())
        for key in heading_keys(path)
        if not FRAGMENT.search(key)
    ]


def not_title_case(text: str) -> bool:
    for index, word in enumerate(text.split()):
        core = re.sub(r"^[^A-Za-z0-9]*|[^A-Za-z0-9]*$", "", word)
        if not core or any(ch.isupper() or ch.isdigit() for ch in core):
            continue
        if core.lower() in SMALL_WORDS and index > 0:
            continue
        return True
    return False


def test_the_pages_have_headings_to_check() -> None:
    # The headings are found by copy key, so a hub edit to their wording keeps this check.
    found = {key for path in PAGES for key in heading_keys(path)}
    for key in (
        "pages.changes.detail.why",
        "pages.obligations.detail.impacts",
        "pages.workspace.overview.setup-title",
    ):
        assert key in found, key


def test_every_heading_key_is_in_the_copy() -> None:
    missing = [key for path in PAGES for key in heading_keys(path) if key not in COPY]
    assert not missing, missing


@pytest.mark.parametrize("path", PAGES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_every_heading_is_title_case(path: Path) -> None:
    bad = [heading for heading in headings(path) if not_title_case(heading)]
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
