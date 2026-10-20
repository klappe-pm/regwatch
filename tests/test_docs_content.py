"""What the README says about regwatch keeps its shape: the same sections, in the same order."""

from __future__ import annotations

import pytest

from tests.conftest import ROOT
from tests.test_docs import headings

pytestmark = pytest.mark.repo_only


def test_the_readme_sections_are_exactly_these_in_this_order() -> None:
    sections = [text for _n, level, text in headings(ROOT / "README.md") if level == 2]
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
