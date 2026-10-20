"""Neutralise untrusted text before it is stored, printed or rendered.

Text that came from outside (an ingest response, a failed fetch, a saved
candidate file) is cleaned at every point where it enters a file or a terminal:

- control characters are removed: C0 (U+0000 to U+001F), DEL, C1 (U+0080 to
  U+009F) and therefore ESC, so a value cannot carry a terminal escape sequence;
- invisible format characters (Unicode category Cf, which includes the bidirectional
  overrides and isolates and the zero-width characters) are removed, and the line
  and paragraph separators (Zl, Zp) become spaces, so a value cannot reorder or
  hide the text around it;
- lone surrogates are replaced with U+FFFD, so the text can always be encoded;
- whitespace is collapsed to single spaces, so a value stays on one line;
- links are accepted only in a narrow https form.
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit

__all__ = ["MAX_URL_LENGTH", "clean_line", "clean_text", "escape_markdown", "safe_https_url"]

MAX_URL_LENGTH = 2000
_CONTROL = re.compile("[\x00-\x1f\x7f-\x9f]")
_SURROGATE = re.compile("[\ud800-\udfff]")
_URL_FORBIDDEN = re.compile("[\\s()\\[\\]<>`\"'\\\\{}|^]")
_MD_SPECIAL = re.compile(r"([\\`*_\[\]<>&#~|!])")
_BULLET_START = re.compile(r"^(\s*)([-+])(\s)")
_ORDERED_START = re.compile(r"^(\s*)(\d{1,9})([.)])(\s)")
# A renderer that links bare text turns "https://host", "www.host", "host.com" and
# "name@host" into links. Escaping the colon of "://", every "@", and every dot
# between a letter or digit and a letter breaks all of those without changing how
# the text reads.
_AUTOLINK_COLON = re.compile(r":(?=//)")
_AUTOLINK_DOT = re.compile(r"(?<=[A-Za-z0-9])\.(?=[A-Za-z])")
_RULE_ONLY = re.compile(r"[-=\s]+")


def _drop_invisible(text: str) -> str:
    """Remove format characters (Cf) and turn line and paragraph separators into spaces."""
    if text.isascii():
        return text
    kept: list[str] = []
    for char in text:
        category = unicodedata.category(char)
        if category == "Cf":
            continue
        kept.append(" " if category in ("Zl", "Zp") else char)
    return "".join(kept)


def _has_invisible(text: str) -> bool:
    return not text.isascii() and any(
        unicodedata.category(char) in ("Cf", "Zl", "Zp") for char in text
    )


def clean_line(text: str) -> str:
    """Return ``text`` made safe to print on a terminal, keeping its spacing.

    Control characters (and so every line break), line and paragraph separators
    become spaces, invisible format characters are removed and lone surrogates are
    replaced. Unlike ``clean_text`` the runs of spaces that align columns are kept.
    """
    return _drop_invisible(_SURROGATE.sub("�", _CONTROL.sub(" ", text)))


def clean_text(text: str, limit: int | None = None) -> str:
    """Return ``text`` on one line without control characters or lone surrogates.

    Invisible format characters (such as a right-to-left override or a zero-width
    space) are removed too. When ``limit`` is given the result is cut to that many
    characters, ending in three dots if anything was removed.
    """
    text = " ".join(clean_line(text).split())
    if limit is not None and len(text) > limit:
        return text[: limit - 3].rstrip() + "..."
    return text


def safe_https_url(value: object) -> str:
    """Return ``value`` if it is a plain https link, otherwise an empty string.

    A plain link is at most 2000 characters, starts with ``https://``, has a host
    and no credentials, and contains no whitespace, control character, invisible
    format character, quote, backslash, brace, bar, caret, backtick or any of
    ``()[]<>``. Its host is plain ASCII: a host written in other scripts is
    refused, because a look-alike letter would let it pass for another site. Such
    a link cannot close a Markdown link or an HTML attribute, and cannot be
    mistaken for a ``javascript:`` or ``data:`` URL.
    """
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text.lower().startswith("https://") or len(text) > MAX_URL_LENGTH:
        return ""
    if _CONTROL.search(text) or _SURROGATE.search(text) or _URL_FORBIDDEN.search(text):
        return ""
    if _has_invisible(text):
        return ""
    try:
        parts = urlsplit(text)
        host = parts.hostname
    except ValueError:
        return ""
    if not host or "@" in parts.netloc or not host.isascii():
        return ""
    return text


def escape_markdown(text: str) -> str:
    """Escape Markdown metacharacters in ``text`` so it renders as literal text.

    Backslash, backtick, asterisk, underscore, brackets, angle brackets,
    ampersand, hash, tilde, bar and exclamation mark are backslash-escaped, and a
    leading list marker is escaped, so a value can never become a link, an image,
    raw HTML, a heading or a list item. A value made only of hyphens or equals
    signs (which would be a horizontal rule) has them escaped. The colon of ``://``,
    every ``@`` and every dot between a letter or digit and a letter are escaped
    too, so a renderer that links bare text cannot turn a web address, a ``www.``
    name, a bare domain or an email address in a value into a link.
    """
    escaped = _MD_SPECIAL.sub(r"\\\1", text)
    if _RULE_ONLY.fullmatch(text):
        escaped = escaped.replace("-", "\\-").replace("=", "\\=")
    escaped = _AUTOLINK_COLON.sub(r"\\:", escaped)
    escaped = _AUTOLINK_DOT.sub(r"\\.", escaped)
    escaped = escaped.replace("@", "\\@")
    escaped = _BULLET_START.sub(r"\1\\\2\3", escaped)
    return _ORDERED_START.sub(r"\1\2\\\3\4", escaped)
