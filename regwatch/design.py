"""The logo of the document design specification, read and checked before it is used.

The rest of the specification (title format, organisation, colours, font, header,
footer and page size) is checked when ``regwatch.toml`` is loaded, in
``regwatch.config``. The logo is a file, so it is checked here, each time a
document or a newsletter is built:

- it must lie under the project folder or under one of ``allowed_file_roots``,
  after links and ``..`` are resolved, and the file itself may not be a link; it is
  opened without following one and must be the very file that was checked;
- it must be a regular file of at most 300,000 bytes;
- a PNG must start with the PNG signature and an ``IHDR`` chunk naming a size of
  at most 4,000 by 4,000 pixels;
- an SVG is refused when it declares a DTD or an entity, when it nests elements
  more than 64 deep, when it holds any element
  or attribute outside a short list of drawing elements and presentation
  attributes, or when a value points anywhere but inside the drawing (only
  ``url(#id)`` is allowed). An SVG that passes is written out again from the parsed
  tree, so comments and processing instructions are dropped. Nothing in an
  accepted SVG can run a script or load anything.
"""

from __future__ import annotations

import base64
import os
import re
import stat
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "MAX_LOGO_BYTES",
    "MAX_LOGO_PIXELS",
    "MAX_SVG_DEPTH",
    "DesignError",
    "Logo",
    "clean_svg",
    "load_logo",
]

MAX_LOGO_BYTES = 300_000
MAX_LOGO_PIXELS = 4000
MAX_SVG_DEPTH = 64
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SVG_NS = "http://www.w3.org/2000/svg"
_DTD_RE = re.compile(r"<!\s*(doctype|entity)", re.IGNORECASE)
_SVG_ELEMENTS = frozenset(
    {
        "svg",
        "g",
        "path",
        "rect",
        "circle",
        "ellipse",
        "line",
        "polyline",
        "polygon",
        "title",
        "desc",
        "defs",
        "lineargradient",
        "radialgradient",
        "stop",
        "clippath",
        "text",
        "tspan",
    }
)
_SVG_ATTRIBUTES = frozenset(
    {
        "id",
        "version",
        "viewbox",
        "preserveaspectratio",
        "width",
        "height",
        "x",
        "y",
        "x1",
        "y1",
        "x2",
        "y2",
        "cx",
        "cy",
        "r",
        "rx",
        "ry",
        "fx",
        "fy",
        "d",
        "points",
        "transform",
        "fill",
        "fill-rule",
        "fill-opacity",
        "stroke",
        "stroke-width",
        "stroke-linecap",
        "stroke-linejoin",
        "stroke-miterlimit",
        "stroke-opacity",
        "stroke-dasharray",
        "opacity",
        "clip-path",
        "clip-rule",
        "clippathunits",
        "offset",
        "stop-color",
        "stop-opacity",
        "gradientunits",
        "gradienttransform",
        "spreadmethod",
        "font-family",
        "font-size",
        "font-weight",
        "text-anchor",
        "dx",
        "dy",
    }
)
_LOCAL_URL = re.compile(r"^\s*url\(\s*#[A-Za-z0-9_.-]{1,100}\s*\)\s*$")


class DesignError(ValueError):
    """The logo cannot be used. The message says why and holds none of the file."""


@dataclass(frozen=True)
class Logo:
    """A checked logo: ``png`` or ``svg``, its bytes and its size in pixels when known."""

    kind: str
    data: bytes
    width: int = 0
    height: int = 0

    @property
    def media_type(self) -> str:
        """The media type of the logo."""
        return "image/png" if self.kind == "png" else "image/svg+xml"

    @property
    def data_uri(self) -> str:
        """The logo as a ``data:`` address, for a page that carries its images inline."""
        return f"data:{self.media_type};base64,{base64.b64encode(self.data).decode('ascii')}"


def _local(tag: str) -> tuple[str, str]:
    """The namespace and the lower case local name of an element or attribute."""
    if tag.startswith("{"):
        namespace, _, name = tag[1:].partition("}")
        return namespace, name.lower()
    return "", tag.lower()


def clean_svg(text: str) -> bytes:
    """Return ``text`` written out again as a safe SVG, or raise DesignError saying why.

    Every element and attribute must be on the allow list, in the SVG namespace or
    none, and a value may point only inside the drawing.
    """
    if _DTD_RE.search(text):
        raise DesignError("the SVG logo declares a DTD or an entity, which is refused")
    try:
        # DOCTYPE and ENTITY declarations were refused above, so no entity can expand.
        root = ET.fromstring(text)  # noqa: S314
    except (ET.ParseError, ValueError, RecursionError) as exc:
        raise DesignError("the SVG logo is not well-formed XML") from exc
    if _local(root.tag) != (SVG_NS, "svg") and _local(root.tag) != ("", "svg"):
        raise DesignError("the logo is not an SVG drawing")
    # Walk with an explicit stack and a depth limit: writing a deeply nested tree out
    # again would otherwise recurse past Python's limit.
    stack = [(root, 1)]
    while stack:
        element, depth = stack.pop()
        if depth > MAX_SVG_DEPTH:
            raise DesignError(
                f"the SVG logo nests elements more than {MAX_SVG_DEPTH} deep, which is refused"
            )
        stack.extend((child, depth + 1) for child in element)
        namespace, name = _local(str(element.tag))
        if namespace not in ("", SVG_NS) or name not in _SVG_ELEMENTS:
            raise DesignError(f"the SVG logo holds a <{name[:40]}> element, which is refused")
        for attribute, value in element.attrib.items():
            attr_namespace, attr_name = _local(attribute)
            if attr_namespace or attr_name not in _SVG_ATTRIBUTES:
                raise DesignError(
                    f"the SVG logo has a {attr_name[:40]} attribute, which is refused"
                )
            lowered = value.lower()
            if "url(" in lowered and not _LOCAL_URL.fullmatch(value):
                raise DesignError("the SVG logo points outside the drawing, which is refused")
            if any(word in lowered for word in ("javascript:", "data:", "expression(")):
                raise DesignError("the SVG logo holds a script or an address, which is refused")
    ET.register_namespace("", SVG_NS)
    try:
        return bytes(ET.tostring(root, encoding="utf-8"))
    except RecursionError as exc:
        raise DesignError("the SVG logo is nested too deeply to write out") from exc


def _png_size(data: bytes) -> tuple[int, int]:
    if not data.startswith(PNG_SIGNATURE) or data[12:16] != b"IHDR" or len(data) < 24:
        raise DesignError("the PNG logo does not start like a PNG file")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    if not (0 < width <= MAX_LOGO_PIXELS and 0 < height <= MAX_LOGO_PIXELS):
        raise DesignError(
            f"the PNG logo is {width} by {height} pixels; it may be at most "
            f"{MAX_LOGO_PIXELS} by {MAX_LOGO_PIXELS}"
        )
    return width, height


def _read(path: Path, roots: Iterable[Path]) -> bytes:
    """The bytes of ``path``, checked to lie under a root and to be a small regular file."""
    if path.is_symlink():
        raise DesignError("the logo file is a symbolic link, which is refused")
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise DesignError("the logo file was not found") from exc
    allowed = [Path(root).resolve() for root in roots]
    if not any(resolved.is_relative_to(root) for root in allowed):
        raise DesignError(
            "the logo must be inside the project folder or a folder in allowed_file_roots"
        )
    descriptor = -1
    try:
        vetted = os.stat(resolved)
        descriptor = os.open(
            resolved, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
        )
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (vetted.st_dev, vetted.st_ino):
            raise DesignError("the logo file changed while it was being opened")
        if not stat.S_ISREG(opened.st_mode):
            raise DesignError("the logo must be a regular file")
        if opened.st_size > MAX_LOGO_BYTES:
            raise DesignError(f"the logo is larger than {MAX_LOGO_BYTES} bytes")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            data = handle.read(MAX_LOGO_BYTES + 1)
    except OSError as exc:
        raise DesignError("the logo file cannot be read") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if len(data) > MAX_LOGO_BYTES:
        raise DesignError(f"the logo is larger than {MAX_LOGO_BYTES} bytes")
    return data


def load_logo(path: Path | None, roots: Iterable[Path]) -> Logo | None:
    """The checked logo at ``path``, or None when no logo is set.

    ``roots`` are the folders the logo may lie under: the project folder and the
    allowed file roots. Raises DesignError saying why a logo is refused.
    """
    if path is None:
        return None
    suffix = path.suffix.lower()
    if suffix not in (".png", ".svg"):
        raise DesignError("the logo must be a .png or .svg file")
    data = _read(path, roots)
    if suffix == ".png":
        width, height = _png_size(data)
        return Logo("png", data, width, height)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DesignError("the SVG logo is not UTF-8 text") from exc
    return Logo("svg", clean_svg(text))
