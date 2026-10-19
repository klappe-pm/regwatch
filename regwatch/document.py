"""The document model shared by every brief and every renderer.

Synthesis and rendering are decoupled through one plain structure: a title, a
list of sections and a disclaimer. Every document carries the standard
disclaimer. It cannot be removed by a model file, because ``Document.from_dict``
always puts it back.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["DISCLAIMER", "Document", "DocumentError", "Section", "make_disclaimer"]

DISCLAIMER = (
    "Not legal advice. This document was produced by software that flags candidate changes and "
    "candidate impacts for human review. A qualified person must confirm every item against the "
    "primary source text and current facts before relying on it for any compliance, labeling or "
    "marketing decision."
)
MAX_SECTIONS = 2000
MAX_ITEMS = 5000
MAX_TEXT = 20000


class DocumentError(ValueError):
    """A document model is malformed."""


def make_disclaimer(extra: str = "") -> str:
    """Return the standard disclaimer, followed by ``extra`` when it adds something."""
    extra = " ".join(extra.split())
    if not extra or extra.startswith(DISCLAIMER):
        return extra if extra else DISCLAIMER
    return f"{DISCLAIMER} {extra}"


@dataclass
class Section:
    """A heading with paragraphs and bullets. ``level`` is 2 for a section, 3 for a subsection."""

    heading: str
    level: int = 2
    paragraphs: list[str] = field(default_factory=list)
    bullets: list[str] = field(default_factory=list)


@dataclass
class Document:
    """A titled, dated list of sections with a disclaimer."""

    title: str
    generated: str
    subtitle: str = ""
    sections: list[Section] = field(default_factory=list)
    disclaimer: str = DISCLAIMER

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable form of the document."""
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "generated": self.generated,
            "sections": [
                {
                    "heading": s.heading,
                    "level": s.level,
                    "paragraphs": list(s.paragraphs),
                    "bullets": list(s.bullets),
                }
                for s in self.sections
            ],
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
    if isinstance(level, bool) or level not in (2, 3, 4):
        raise DocumentError("section 'level' must be 2, 3 or 4")
    return Section(
        heading=_text(item, "heading", required=True),
        level=level,
        paragraphs=_strings(item, "paragraphs"),
        bullets=_strings(item, "bullets"),
    )
