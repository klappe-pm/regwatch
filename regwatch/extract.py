"""Reduce untrusted fetched content to a stable change signal.

Fetched pages, feeds and API responses are untrusted input. This module never
evaluates anything: JSON goes through ``json``, HTML through the standard
library tokenizer, and XML through ElementTree only after a document that
declares a DTD or an entity is refused outright. Refusing every DOCTYPE and
ENTITY declaration removes the whole class of entity expansion attacks without
a third-party dependency, because legitimate RSS and Atom feeds do not need
either. The documentation explains this choice.

The signal is what gets hashed. Reducing content to a signal keeps the hash
from changing when only page furniture, markup or ordering changes.
"""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import Any

__all__ = ["ExtractError", "extract_signal", "signal_hash"]

_DTD_RE = re.compile(r"<!\s*(doctype|entity)", re.IGNORECASE)
_SKIPPED_HTML_TAGS = frozenset({"script", "style", "template"})
_FEED_ROOTS = frozenset({"rss", "feed", "rdf"})
_ITEM_TAGS = frozenset({"item", "entry"})


class ExtractError(Exception):
    """The content cannot be safely reduced to a signal."""


def signal_hash(signal: str) -> str:
    """Return the SHA-256 hex digest of ``signal`` encoded as UTF-8."""
    return hashlib.sha256(signal.encode("utf-8")).hexdigest()


def extract_signal(mechanism: str, content: str) -> str:
    """Reduce ``content`` fetched by ``mechanism`` to the text that gets hashed.

    ``api`` expects JSON, ``rss`` expects an RSS or Atom feed, ``html`` expects
    a web page. Any other mechanism is treated as plain text with trailing
    whitespace removed. Raises ExtractError only for an unsafe or malformed feed.
    """
    if mechanism == "api":
        return _api_signal(content)
    if mechanism == "rss":
        return _feed_signal(content)
    if mechanism == "html":
        return _html_signal(content)
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines).strip()


def _api_signal(content: str) -> str:
    try:
        data = json.loads(content)
    except (ValueError, RecursionError):
        return content.strip()
    if isinstance(data, dict):
        results = data.get("results")
        if isinstance(results, list) and results and all(isinstance(r, dict) for r in results):
            rows = [
                "\t".join(
                    str(item.get(key, ""))
                    for key in ("publication_date", "document_number", "title")
                )
                for item in results
            ]
            return "\n".join(sorted(rows))
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _local_name(tag: Any) -> str:
    text = str(tag)
    return text.rsplit("}", 1)[-1].lower()


def _feed_signal(content: str) -> str:
    if _DTD_RE.search(content):
        raise ExtractError("feed declares a DTD or entity, which is refused")
    try:
        # DOCTYPE and ENTITY declarations were refused above, so no entity can expand.
        root = ET.fromstring(content)  # noqa: S314
    except (ET.ParseError, ValueError, RecursionError) as exc:
        raise ExtractError(f"feed is not well-formed XML: {exc}") from exc
    if _local_name(root.tag) not in _FEED_ROOTS:
        raise ExtractError("document is not an RSS or Atom feed")
    rows: list[str] = []
    for element in root.iter():
        if _local_name(element.tag) not in _ITEM_TAGS:
            continue
        fields = {"title": "", "link": "", "id": "", "date": ""}
        for child in element:
            name = _local_name(child.tag)
            text = " ".join((child.text or "").split())
            if name == "title":
                fields["title"] = text
            elif name == "link":
                fields["link"] = child.get("href") or text
            elif name in ("guid", "id"):
                fields["id"] = text
            elif name in ("pubdate", "updated", "published", "date"):
                fields["date"] = text
        rows.append("\t".join((fields["date"], fields["id"], fields["link"], fields["title"])))
    return "\n".join(sorted(rows))


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIPPED_HTML_TAGS:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIPPED_HTML_TAGS and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def _html_signal(content: str) -> str:
    parser = _TextExtractor()
    parser.feed(content)
    parser.close()
    return " ".join(" ".join(parser.parts).split())
