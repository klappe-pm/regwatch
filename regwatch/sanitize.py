"""Neutralise untrusted text before it is stored, printed or rendered.

Text that came from outside (an ingest response, a failed fetch, a saved
candidate file) is cleaned at every point where it enters a file or a terminal:

- control characters are removed: C0 (U+0000 to U+001F), DEL, C1 (U+0080 to
  U+009F) and therefore ESC, so a value cannot carry a terminal escape sequence;
- lone surrogates are replaced with U+FFFD, so the text can always be encoded;
- whitespace is collapsed to single spaces, so a value stays on one line;
- links are accepted only in a narrow https form.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

__all__ = ["MAX_URL_LENGTH", "clean_text", "escape_markdown", "safe_https_url"]

MAX_URL_LENGTH = 2000
_CONTROL = re.compile("[\x00-\x1f\x7f-\x9f]")
_SURROGATE = re.compile("[\ud800-\udfff]")
_URL_FORBIDDEN = re.compile("[\\s()\\[\\]<>`\"'\\\\{}|^]")
_MD_SPECIAL = re.compile(r"([\\`*_\[\]<>&#~|!])")
_BULLET_START = re.compile(r"^(\s*)([-+])(\s)")
_ORDERED_START = re.compile(r"^(\s*)(\d{1,9})([.)])(\s)")


def clean_text(text: str, limit: int | None = None) -> str:
    """Return ``text`` on one line without control characters or lone surrogates.

    When ``limit`` is given the result is cut to that many characters, ending in
    three dots if anything was removed.
    """
    text = _SURROGATE.sub("�", _CONTROL.sub(" ", text))
    text = " ".join(text.split())
    if limit is not None and len(text) > limit:
        return text[: limit - 3].rstrip() + "..."
    return text


def safe_https_url(value: object) -> str:
    """Return ``value`` if it is a plain https link, otherwise an empty string.

    A plain link is at most 2000 characters, starts with ``https://``, has a host
    and no credentials, and contains no whitespace, control character, quote,
    backslash, brace, bar, caret, backtick or any of ``()[]<>``. Such a link
    cannot close a Markdown link or an HTML attribute, and cannot be mistaken for
    a ``javascript:`` or ``data:`` URL.
    """
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text.lower().startswith("https://") or len(text) > MAX_URL_LENGTH:
        return ""
    if _CONTROL.search(text) or _SURROGATE.search(text) or _URL_FORBIDDEN.search(text):
        return ""
    try:
        parts = urlsplit(text)
        host = parts.hostname
    except ValueError:
        return ""
    if not host or "@" in parts.netloc:
        return ""
    return text


def escape_markdown(text: str) -> str:
    """Escape Markdown metacharacters in ``text`` so it renders as literal text.

    Backslash, backtick, asterisk, underscore, brackets, angle brackets,
    ampersand, hash, tilde, bar and exclamation mark are backslash-escaped, and a
    leading list marker is escaped, so a value can never become a link, an image,
    raw HTML, a heading or a list item.
    """
    escaped = _MD_SPECIAL.sub(r"\\\1", text)
    escaped = _BULLET_START.sub(r"\1\\\2\3", escaped)
    return _ORDERED_START.sub(r"\1\2\\\3\4", escaped)
