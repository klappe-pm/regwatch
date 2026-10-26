"""The document design specification: colours, fonts, the title format and the logo checks."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from conftest import TODAY
from test_newsletter import make_png

from regwatch.config import (
    AA_CONTRAST,
    FONTS,
    ConfigError,
    DocumentDesign,
    check_color,
    contrast_with_white,
    load_config,
)
from regwatch.design import MAX_LOGO_BYTES, DesignError, clean_svg, load_logo
from regwatch.register import load_register
from regwatch.synthesis import digest_document, report_document


def append(project: Path, text: str) -> None:
    project.write_text(project.read_text(encoding="utf-8") + "\n" + text, encoding="utf-8")


# --- the specification ---------------------------------------------------------------


def test_the_default_design_meets_aa_and_reads_like_the_web_app(project: Path) -> None:
    design = load_config(project).document
    assert design == DocumentDesign()
    assert contrast_with_white(design.primary_color) >= AA_CONTRAST
    assert contrast_with_white(design.accent_color) >= AA_CONTRAST
    assert design.title("T", "2026-01-01") == "T"


def test_contrast_is_the_wcag_ratio() -> None:
    assert contrast_with_white("#000000") == pytest.approx(21.0)
    assert contrast_with_white("#ffffff") == pytest.approx(1.0)
    assert contrast_with_white("#767676") == pytest.approx(4.54, abs=0.01)


@pytest.mark.parametrize(
    ("table", "message"),
    [
        ('primary_color = "#ffff00"', "contrast of 1.07:1"),
        ('accent_color = "#77aaff"', "accent_color"),
        ('primary_color = "blue"', "#rrggbb"),
        ('primary_color = "#12345"', "#rrggbb"),
        ('font = "Comic Sans MS"', "font must be one of"),
        ('page_size = "a5"', "page_size must be one of"),
        ('title_format = "{title} {secret}"', "may use only"),
        ('title_format = "{title"', "unmatched brace"),
        ('title_format = ""', "title_format must be"),
        ('header = "a\\u001bb"', "control characters"),
        ('organisation = "' + "x" * 121 + '"', "at most 120"),
        ("logo = 3", "logo must be a path"),
        ('colour = "#000000"', "unknown keys"),
    ],
)
def test_a_bad_design_is_refused(project: Path, table: str, message: str) -> None:
    append(project, f"[document]\n{table}\n")
    with pytest.raises(ConfigError, match=message):
        load_config(project)


def test_a_full_design_is_read(project: Path) -> None:
    append(
        project,
        '[document]\ntitle_format = "{organisation} | {title} | {date}"\norganisation = "Org"\n'
        'primary_color = "#0B3D2E"\naccent_color = "#5A2D82"\nfont = "Verdana"\n'
        'logo = "brand/logo.svg"\nheader = "H"\nfooter = "F"\npage_size = "letter"\n',
    )
    design = load_config(project).document
    assert design.primary_color == "#0b3d2e" and design.font_stack == FONTS["Verdana"]
    assert design.logo == project.parent / "brand" / "logo.svg"
    assert design.title("Digest", "2026-10-19") == "Org | Digest | 2026-10-19"
    assert design.page_size == "letter"


@pytest.mark.parametrize(
    ("title_format", "organisation", "title", "expected"),
    [
        (
            "{organisation}: {title}",
            "Example Pantry Co.",
            "Example Pantry Co. regulatory newsletter",
            "Example Pantry Co.: Regulatory newsletter",
        ),
        (
            "{organisation} | {title}",
            "example pantry co",
            "Example Pantry Co. register digest",
            "example pantry co | Register digest",
        ),
        # Not a whole word: "Pantry" is not taken off "Pantryhouse".
        ("{organisation}: {title}", "Pantry", "Pantryhouse digest", "Pantry: Pantryhouse digest"),
        # Another organisation, or a format without {organisation}, keeps the title whole.
        ("{organisation}: {title}", "Other Ltd", "Pantry digest", "Other Ltd: Pantry digest"),
        ("{title} ({date})", "Pantry", "Pantry digest", "Pantry digest (2026-10-19)"),
        # A title that is only the name is kept.
        ("{organisation}: {title}", "Pantry", "Pantry", "Pantry: Pantry"),
    ],
)
def test_the_organisation_is_not_named_twice_in_a_title(
    title_format: str, organisation: str, title: str, expected: str
) -> None:
    design = DocumentDesign(title_format=title_format, organisation=organisation)
    assert design.title(title, "2026-10-19") == expected


def test_digest_and_report_titles_name_the_portfolio(project: Path) -> None:
    config = load_config(project)
    register = load_register(config)
    assert digest_document(register, TODAY, 30).title == "Example Pantry Co. register digest"
    assert report_document(register, [], TODAY, 30).title == (
        "Example Pantry Co. change and due alert"
    )


def test_check_color_returns_lower_case() -> None:
    assert check_color("#1D5A92", "primary_color") == "#1d5a92"


def test_the_newsletter_footer_defaults_and_is_bounded(project: Path) -> None:
    assert "Reply to this message" in load_config(project).newsletter.footer
    append(project, '[newsletter]\nfooter = "' + "x" * 301 + '"\n')
    with pytest.raises(ConfigError, match="at most 300"):
        load_config(project)


# --- the logo -------------------------------------------------------------------------


def test_no_logo_is_none(tmp_path: Path) -> None:
    assert load_logo(None, [tmp_path]) is None


def test_a_png_logo_is_read_with_its_size(tmp_path: Path) -> None:
    (tmp_path / "logo.png").write_bytes(make_png(300, 90))
    logo = load_logo(tmp_path / "logo.png", [tmp_path])
    assert logo is not None and (logo.kind, logo.width, logo.height) == ("png", 300, 90)
    assert logo.data_uri.startswith("data:image/png;base64,iVBOR")


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"GIF89a" + b"\x00" * 30, "does not start like a PNG"),
        (make_png(5000, 10), "at most 4000 by 4000"),
        (make_png(0, 10), "0 by 10"),
    ],
)
def test_a_bad_png_is_refused(tmp_path: Path, data: bytes, message: str) -> None:
    (tmp_path / "logo.png").write_bytes(data)
    with pytest.raises(DesignError, match=message):
        load_logo(tmp_path / "logo.png", [tmp_path])


def test_a_logo_outside_the_roots_or_through_a_link_is_refused(tmp_path: Path) -> None:
    project, outside = tmp_path / "project", tmp_path / "outside"
    project.mkdir()
    outside.mkdir()
    (outside / "logo.png").write_bytes(make_png())
    with pytest.raises(DesignError, match="inside the project folder"):
        load_logo(outside / "logo.png", [project])
    (project / "logo.png").symlink_to(outside / "logo.png")
    with pytest.raises(DesignError, match="symbolic link"):
        load_logo(project / "logo.png", [project])
    (project / "dots.png").write_bytes(make_png())
    with pytest.raises(DesignError, match="inside the project folder"):
        load_logo(project / ".." / "outside" / "logo.png", [project])
    assert load_logo(outside / "logo.png", [project, outside]) is not None


def test_a_logo_that_is_big_missing_a_folder_or_another_type_is_refused(tmp_path: Path) -> None:
    (tmp_path / "big.png").write_bytes(make_png() + b"\x00" * MAX_LOGO_BYTES)
    with pytest.raises(DesignError, match="larger than"):
        load_logo(tmp_path / "big.png", [tmp_path])
    with pytest.raises(DesignError, match="not found"):
        load_logo(tmp_path / "missing.png", [tmp_path])
    (tmp_path / "logo.gif").write_bytes(b"GIF")
    with pytest.raises(DesignError, match=r"\.png or \.svg"):
        load_logo(tmp_path / "logo.gif", [tmp_path])
    (tmp_path / "folder.png").mkdir()
    with pytest.raises(DesignError, match="regular file"):
        load_logo(tmp_path / "folder.png", [tmp_path])
    os.mkfifo(tmp_path / "pipe.png")
    with pytest.raises(DesignError, match="regular file"):
        load_logo(tmp_path / "pipe.png", [tmp_path])


SAFE_SVG = (
    '<?xml version="1.0"?><!-- a comment --><svg xmlns="http://www.w3.org/2000/svg" '
    'viewBox="0 0 10 10"><defs><linearGradient id="g"><stop offset="0" stop-color="#000"/>'
    '</linearGradient></defs><rect width="10" height="10" fill="url(#g)"/>'
    "<title>Logo</title></svg>"
)


def test_a_safe_svg_is_written_out_again_without_comments(tmp_path: Path) -> None:
    (tmp_path / "logo.svg").write_text(SAFE_SVG, encoding="utf-8")
    logo = load_logo(tmp_path / "logo.svg", [tmp_path])
    assert logo is not None and logo.kind == "svg" and logo.media_type == "image/svg+xml"
    assert b"comment" not in logo.data and b'fill="url(#g)"' in logo.data
    assert logo.data.startswith(b"<svg") or logo.data.startswith(b"<?xml")


@pytest.mark.parametrize(
    ("svg", "message"),
    [
        ('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', "script"),
        ('<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>', "onload"),
        (
            '<svg xmlns="http://www.w3.org/2000/svg" xmlns:x="http://www.w3.org/1999/xlink">'
            '<image x:href="https://evil.example/a.png"/></svg>',
            "image",
        ),
        (
            '<svg xmlns="http://www.w3.org/2000/svg"><rect fill="url(https://evil.example/)"/></svg>',
            "outside the drawing",
        ),
        ('<svg xmlns="http://www.w3.org/2000/svg"><rect fill="javascript:x"/></svg>', "script"),
        (
            '<svg xmlns="http://www.w3.org/2000/svg"><foreignObject><p>x</p></foreignObject></svg>',
            "foreignobject",
        ),
        ('<svg xmlns="http://www.w3.org/2000/svg"><style>*{}</style></svg>', "style"),
        ('<svg xmlns="http://www.w3.org/2000/svg" style="fill:red"/>', "style"),
        ('<!DOCTYPE svg [<!ENTITY a "b">]><svg>&a;</svg>', "DTD"),
        ("<html/>", "not an SVG"),
        ("<svg", "well-formed"),
    ],
)
def test_an_unsafe_svg_is_refused(svg: str, message: str) -> None:
    with pytest.raises(DesignError, match=message):
        clean_svg(svg)


def test_an_svg_that_is_not_utf8_is_refused(tmp_path: Path) -> None:
    (tmp_path / "logo.svg").write_bytes(b"\xff\xfe<svg/>")
    with pytest.raises(DesignError, match="UTF-8"):
        load_logo(tmp_path / "logo.svg", [tmp_path])
