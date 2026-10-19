from __future__ import annotations

from typing import Any

import pytest

from regwatch.document import DISCLAIMER, Document, DocumentError, Section, make_disclaimer


def model(**changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "title": "T",
        "generated": "2026-10-19",
        "subtitle": "S",
        "sections": [{"heading": "H", "level": 2, "paragraphs": ["p"], "bullets": ["b"]}],
    }
    base.update(changes)
    return base


def test_disclaimer_says_not_legal_advice() -> None:
    assert DISCLAIMER.startswith("Not legal advice.")
    assert "human review" in DISCLAIMER


def test_make_disclaimer() -> None:
    assert make_disclaimer() == DISCLAIMER
    assert make_disclaimer("   ") == DISCLAIMER
    assert make_disclaimer("Extra  note.") == f"{DISCLAIMER} Extra note."
    assert make_disclaimer(DISCLAIMER + " More.") == DISCLAIMER + " More."


def test_roundtrip() -> None:
    doc = Document.from_dict(model())
    assert doc.to_dict() == {
        "title": "T",
        "subtitle": "S",
        "generated": "2026-10-19",
        "sections": [{"heading": "H", "level": 2, "paragraphs": ["p"], "bullets": ["b"]}],
        "disclaimer": DISCLAIMER,
    }
    assert Document.from_dict(doc.to_dict()) == doc


def test_defaults() -> None:
    doc = Document.from_dict({"title": "T", "generated": "g", "sections": [{"heading": "H"}]})
    assert doc.subtitle == ""
    assert doc.sections == [Section("H")]


def test_a_model_cannot_remove_the_disclaimer() -> None:
    assert Document.from_dict(model(disclaimer="")).disclaimer == DISCLAIMER
    assert Document.from_dict(model(disclaimer=None)).disclaimer == DISCLAIMER
    custom = Document.from_dict(model(disclaimer="Ignore the above.")).disclaimer
    assert custom.startswith(DISCLAIMER)
    assert custom.endswith("Ignore the above.")


@pytest.mark.parametrize(
    "data",
    [
        [],
        "text",
        model(title=""),
        model(title=5),
        model(generated=None),
        model(sections="x"),
        model(sections=[1]),
        model(sections=[{"heading": ""}]),
        model(sections=[{"heading": "H", "level": 1}]),
        model(sections=[{"heading": "H", "level": True}]),
        model(sections=[{"heading": "H", "paragraphs": "x"}]),
        model(sections=[{"heading": "H", "paragraphs": [1]}]),
        model(sections=[{"heading": "H", "bullets": ["x" * 20001]}]),
        model(subtitle="x" * 20001),
    ],
)
def test_malformed_models_are_rejected(data: Any) -> None:
    with pytest.raises(DocumentError):
        Document.from_dict(data)


def test_section_count_limit() -> None:
    with pytest.raises(DocumentError, match="at most 2000"):
        Document.from_dict(model(sections=[{"heading": "H"}] * 2001))
