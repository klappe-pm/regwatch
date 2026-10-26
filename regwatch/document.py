"""The document model shared by every brief and every renderer.

Synthesis and rendering are decoupled through one plain structure: a title, a
list of sections and a disclaimer. Every document carries the standard
disclaimer. It cannot be removed by a model file, because ``Document.from_dict``
always puts it back.

A section may also hold generated passages: text a language model wrote, each kept
with the facts it was written from and the ids it cites, so every renderer can mark
it as generated and show the facts next to it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from regwatch.register import parse_date
from regwatch.wording import MONTHS, long_date

__all__ = [
    "DISCLAIMER",
    "Document",
    "DocumentError",
    "GeneratedPassage",
    "Section",
    "make_disclaimer",
]

DISCLAIMER = (
    "Not legal advice. This document was produced by software that flags candidate changes and "
    "candidate impacts for human review. A qualified person must confirm every item against the "
    "primary source text and current facts before relying on it for any compliance, labeling or "
    "marketing decision."
)
MAX_SECTIONS = 2000
MAX_ITEMS = 5000
MAX_TEXT = 20000
MAX_PASSAGES = 200
GENERATED_LABEL = "Generated"


class DocumentError(ValueError):
    """A document model is malformed."""


def make_disclaimer(extra: str = "") -> str:
    """Return the standard disclaimer, followed by ``extra`` when it adds something."""
    extra = " ".join(extra.split())
    if not extra or extra.startswith(DISCLAIMER):
        return extra if extra else DISCLAIMER
    return f"{DISCLAIMER} {extra}"


@dataclass
class GeneratedPassage:
    """Text a language model wrote, with the facts it was written from.

    ``cites`` are the ids of the facts the passage names, and ``facts`` the lines of
    those facts as the model was given them (``id: text``), so a reader can check
    one against the other. ``provider`` and ``model`` say what wrote it.
    """

    text: str
    cites: list[str] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)
    provider: str = ""
    model: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable form of the passage."""
        return {
            "text": self.text,
            "cites": list(self.cites),
            "facts": list(self.facts),
            "provider": self.provider,
            "model": self.model,
        }


@dataclass
class Section:
    """A heading with paragraphs and bullets. ``level`` is 2 for a section, 3 for a subsection.

    ``generated`` holds the generated passages that open the section, if any.
    """

    heading: str
    level: int = 2
    paragraphs: list[str] = field(default_factory=list)
    bullets: list[str] = field(default_factory=list)
    generated: list[GeneratedPassage] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable form of the section."""
        data: dict[str, Any] = {
            "heading": self.heading,
            "level": self.level,
            "paragraphs": list(self.paragraphs),
            "bullets": list(self.bullets),
        }
        if self.generated:
            data["generated"] = [passage.to_dict() for passage in self.generated]
        return data


@dataclass
class Document:
    """A titled, dated list of sections with a disclaimer."""

    title: str
    generated: str
    subtitle: str = ""
    sections: list[Section] = field(default_factory=list)
    disclaimer: str = DISCLAIMER

    @property
    def date_line(self) -> str:
        """ "Prepared 15 November 2026.", or "" when the title or subtitle already says the date.

        A newsletter's subtitle names its period and a title format may carry the date,
        so a separate date line there only repeats it.
        """
        if not self.generated:
            return ""
        day = parse_date(self.generated)
        said = [self.generated]
        if day is not None:
            said += [long_date(day), f"{day.day} {MONTHS[day.month - 1]}"]
        heading = f"{self.title} {self.subtitle}"
        if any(form in heading for form in said):
            return ""
        return f"Prepared {long_date(day) if day is not None else self.generated}."

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable form of the document."""
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "generated": self.generated,
            "sections": [section.to_dict() for section in self.sections],
            "disclaimer": self.disclaimer,
        }

    @classmethod
    def from_dict(cls, data: object) -> Document:
        """Build a Document from parsed JSON, rejecting anything that is not the model shape."""
        if not isinstance(data, dict):
            raise DocumentError("a document model must be a JSON object")
        sections_raw = data.get("sections", [])
        if not isinstance(sections_raw, list) or len(sections_raw) > MAX_SECTIONS:
            raise DocumentError("'sections' must be a list of at most 2000 sections")
        sections = [_section(item) for item in sections_raw]
        return cls(
            title=_text(data, "title", required=True),
            generated=_text(data, "generated", required=True),
            subtitle=_text(data, "subtitle"),
            sections=sections,
            disclaimer=make_disclaimer(_text(data, "disclaimer")),
        )


def _text(data: dict[str, Any], key: str, required: bool = False) -> str:
    value = data.get(key, "")
    if value is None:
        value = ""
    if not isinstance(value, str) or len(value) > MAX_TEXT:
        raise DocumentError(f"'{key}' must be a string of at most {MAX_TEXT} characters")
    if required and not value.strip():
        raise DocumentError(f"'{key}' is required")
    return value


def _strings(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key, [])
    if not isinstance(value, list) or len(value) > MAX_ITEMS:
        raise DocumentError(f"'{key}' must be a list of at most {MAX_ITEMS} strings")
    if not all(isinstance(item, str) and len(item) <= MAX_TEXT for item in value):
        raise DocumentError(f"'{key}' must hold strings of at most {MAX_TEXT} characters")
    return list(value)


def _section(item: object) -> Section:
    if not isinstance(item, dict):
        raise DocumentError("each section must be a JSON object")
    level = item.get("level", 2)
    if type(level) is not int or level not in (2, 3, 4):
        raise DocumentError("section 'level' must be 2, 3 or 4")
    generated = item.get("generated", [])
    if not isinstance(generated, list) or len(generated) > MAX_PASSAGES:
        raise DocumentError(f"'generated' must be a list of at most {MAX_PASSAGES} passages")
    return Section(
        heading=_text(item, "heading", required=True),
        level=level,
        paragraphs=_strings(item, "paragraphs"),
        bullets=_strings(item, "bullets"),
        generated=[_passage(passage) for passage in generated],
    )


def _passage(item: object) -> GeneratedPassage:
    if not isinstance(item, dict):
        raise DocumentError("each generated passage must be a JSON object")
    return GeneratedPassage(
        text=_text(item, "text", required=True),
        cites=_strings(item, "cites"),
        facts=_strings(item, "facts"),
        provider=_text(item, "provider"),
        model=_text(item, "model"),
    )
