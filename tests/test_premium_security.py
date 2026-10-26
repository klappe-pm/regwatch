"""Security checks on the premium content: generated copy, the design logo, the provider
keys, the previews and the cache of generated copy.

Every test here fails without the check it names. Nothing reaches a network or a real
keychain: the language model is a fake poster and the keychain a FakeSystem.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import NOW, TODAY

from regwatch.config import DocumentDesign, load_config
from regwatch.document import Document, Section
from regwatch.llm import Fact, candidate_facts, parse_passages
from regwatch.newsletter import (
    build_newsletter,
    email_bytes,
    newsletter_content,
    render_email_html,
    render_email_text,
)
from regwatch.register import load_register
from regwatch.sanitize import defang_links, link_like

FACTS = [Fact("change:nl-notices", "changes", "Northland notices content changed")]


def answer(
    text: str, section: str = "opening", cites: tuple[str, ...] = ("change:nl-notices",)
) -> str:
    return json.dumps({"passages": [{"section": section, "text": text, "cites": list(cites)}]})


# --- S1: generated copy carries no link ---------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Confirm your listing at https://verify-nl-notices.example/login today.",
        "See nl-notices-portal.com/renew today.",
        "Visit www.example for the form.",
        "Write to desk@example to ask.",
        "Open mailto:desk to ask.",
        "Use xmpp:desk now.",
        "Look at hxxp://bad today.",
    ],
)
def test_a_generated_passage_that_holds_a_link_is_dropped_and_reported(text: str) -> None:
    result = parse_passages(answer(text), FACTS)
    assert result.count == 0
    assert "web address, an email address or a domain name" in result.dropped[0]


@pytest.mark.parametrize(
    "text",
    ["Northland notices changed on 19 October.", "The fee rose 2.5 percent.", "Act now: read it."],
)
def test_plain_sentences_are_not_taken_for_links(text: str) -> None:
    assert not link_like(text)


def test_an_address_in_the_candidates_never_reaches_the_email_as_a_link() -> None:
    candidate = {
        "date": "2026-10-15",
        "agency": "Agency at agency.example",
        "headline": "Renew at nl-notices-portal.com/renew or write to desk@example.org",
        "what_happened": "See https://phish.example/x and www.phish.example",
    }
    facts = candidate_facts([candidate])
    text = facts[0].text
    for address in ("nl-notices-portal.com", "desk@example.org", "https://phish", "www.phish"):
        assert address not in text
    assert "nl-notices-portal[.]com/renew" in text and "desk[@]example[.]org" in text
    assert "https[:]//phish[.]example/x" in text


def test_the_only_link_in_a_candidate_bullet_is_its_checked_source(project: Path) -> None:
    config = load_config(project)
    register = load_register(config)
    candidate = {
        "date": "2026-10-15",
        "agency": "agency.example",
        "headline": "Renew at nl-notices-portal.com/renew",
        "source_url": "https://www.example.gov/notice",
    }
    content = newsletter_content(register, [], [], [candidate], TODAY, 30)
    doc = build_newsletter(register, content, DocumentDesign())
    page = render_email_html(doc, DocumentDesign(), "bye")
    assert "nl-notices-portal.com" not in page and "nl-notices-portal[.]com/renew" in page
    assert "agency[.]example" in page and "(https://www.example.gov/notice)" in page


def test_a_linked_passage_never_reaches_the_email() -> None:
    result = parse_passages(answer("Act now: see nl-notices-portal.com/renew today."), FACTS)
    doc = Document(
        "t", "2026-10-19", "s", [Section("In This Issue", generated=result.section("opening"))], "d"
    )
    design = DocumentDesign()
    raw = email_bytes(
        "t", render_email_text(doc, design, "bye"), render_email_html(doc, design, "bye"), NOW
    )
    assert b"nl-notices-portal.com/renew" not in raw


def test_defang_leaves_plain_words_alone() -> None:
    assert defang_links("Rule 2.5 changed, see agency.gov") == "Rule 2.5 changed, see agency[.]gov"
    assert defang_links("") == ""
