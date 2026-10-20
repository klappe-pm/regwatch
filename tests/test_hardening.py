"""Regression tests for the findings of the adversarial security review."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest
from conftest import NOW, TODAY, FakeFetcher

from regwatch.briefing import build_briefing
from regwatch.check import MIN_PRIOR_LENGTH, accept_results, check_sources
from regwatch.config import Config, IngestSettings, load_config
from regwatch.document import Document, Section
from regwatch.export import FORMULA_STARTS, neutralise_cell, records_csv
from regwatch.fetch import FetchError
from regwatch.ingest import parse_candidates
from regwatch.register import Register
from regwatch.render import (
    docx_bytes,
    render_document_xml,
    render_markdown,
    render_newsletter_html,
    render_newsletter_text,
    render_webpost,
)
from regwatch.sanitize import clean_text, escape_markdown, safe_https_url
from regwatch.state import StateError, safe_write_text

ESC = chr(0x1B)
HOSTILE_TITLE = (
    f"label {ESC}[31mred{ESC}]0;owned\x07 [click](javascript:alert(1)) "
    "![pixel](https://tracker.example/p.png) <script>alert(1)</script> `code` \x9b2J"
)


def hostile_response(**overrides: object) -> str:
    document: dict[str, object] = {
        "title": HOSTILE_TITLE,
        "abstract": HOSTILE_TITLE,
        "publication_date": "2026-10-01",
        "html_url": "https://www.example.gov/documents/1",
        "document_number": "2026-1",
        "type": f"Rule{ESC}[2J",
        "agencies": [{"name": f"Agency{ESC}[0m"}],
    }
    document.update(overrides)
    return json.dumps({"results": [document]})


# --- 1. untrusted text ---------------------------------------------------------


def test_clean_text_removes_c0_c1_esc_del_and_surrogates() -> None:
    text = f"a{ESC}[31mb\x00c\x07d\x7fe\x9bf\u0085g\ud800h\nx\ty"
    assert clean_text(text) == "a [31mb c d e f g�h x y"
    assert not any(ord(c) < 0x20 or 0x7F <= ord(c) <= 0x9F for c in clean_text(text))


def test_clean_text_limit() -> None:
    assert clean_text("x" * 50, 10) == "xxxxxxx..."
    assert clean_text("short", 10) == "short"


@pytest.mark.parametrize(
    "value",
    [
        "https://example.org/a)[x](javascript:alert(1)",
        "https://example.org/a b",
        "https://example.org/a`b",
        "https://example.org/<b>",
        "https://example.org/a]b",
        'https://example.org/a"onmouseover="x',
        "https://example.org/a'b",
        "https://example.org/a\\b",
        "https://example.org/a\nb",
        f"https://example.org/{ESC}[2J",
        "https://user:pass@example.org/",
        "https:///nohost",
        "http://example.org/",
        "javascript:alert(1)",
        "data:text/html,x",
        "//example.org/",
        "https://example.org/" + "a" * 2000,
        "",
        None,
        5,
    ],
)
def test_unsafe_urls_are_rejected(value: object) -> None:
    assert safe_https_url(value) == ""


@pytest.mark.parametrize(
    "value",
    [
        "https://example.org/a",
        "HTTPS://Example.org/a?b=1&c=2#frag",
        "  https://example.org:8443/x  ",
    ],
)
def test_plain_https_urls_are_accepted(value: str) -> None:
    assert safe_https_url(value) == value.strip()


def test_escape_markdown_neutralises_links_images_html_and_blocks() -> None:
    assert escape_markdown("[a](b) ![i](u) <b>x</b> `c` *e* _u_ ~s~ # h | t &amp;") == (
        "\\[a\\](b) \\!\\[i\\](u) \\<b\\>x\\</b\\> \\`c\\` \\*e\\* \\_u\\_ \\~s\\~ \\# h \\| t \\&amp;"
    )
    assert escape_markdown("- item") == "\\- item"
    assert escape_markdown("+ item") == "\\+ item"
    assert escape_markdown("1. item") == "1\\. item"
    assert escape_markdown("12) item") == "12\\) item"
    assert escape_markdown("plain text.") == "plain text."


def test_ingest_strips_escape_sequences_and_validates_links() -> None:
    [candidate] = parse_candidates(hostile_response(), IngestSettings(), TODAY)
    for key in ("headline", "what_happened", "agency", "type"):
        value = candidate[key]
        assert ESC not in value and "\x07" not in value and "\x9b" not in value, key
    assert candidate["source_url"] == "https://www.example.gov/documents/1"


@pytest.mark.parametrize(
    "link",
    [
        "javascript:alert(1)",
        "https://e.example/a)[x](javascript:alert(1)",
        "https://e.example/a b",
        "https://e.example/`x`",
        "https://e.example/<script>",
        f"https://e.example/{ESC}[31m",
    ],
)
def test_ingest_drops_unsafe_source_urls(link: str) -> None:
    [candidate] = parse_candidates(hostile_response(html_url=link), IngestSettings(), TODAY)
    assert candidate["source_url"] == ""


@pytest.mark.parametrize(
    "number", ["2026-1) [x](javascript:1", "a b", f"{ESC}[2J", "x" * 41, ["list"]]
)
def test_ingest_restricts_document_numbers(number: object) -> None:
    [candidate] = parse_candidates(
        hostile_response(document_number=number), IngestSettings(), TODAY
    )
    assert candidate["document_number"] == ""


def hostile_candidate() -> dict[str, object]:
    return {
        "date": f"2026-10-01{ESC}[2J",
        "headline": HOSTILE_TITLE,
        "what_happened": HOSTILE_TITLE,
        "citations": [{"citation": HOSTILE_TITLE}, "bad"],
        "source_url": "https://e.example/a)[x](javascript:alert(1)",
        "document_number": HOSTILE_TITLE,
    }


def test_briefing_cleans_candidates_read_from_an_edited_state_file(register: Register) -> None:
    doc = build_briefing(register, [], TODAY, tier="v3", candidates=[hostile_candidate()])
    item = next(s for s in doc.sections if "label" in s.heading)
    text = "\n".join([item.heading, *item.paragraphs])
    assert ESC not in text and "\x07" not in text
    assert not any(p.startswith("Source.") for p in item.paragraphs)


def test_briefing_survives_non_list_citations(register: Register) -> None:
    bad = hostile_candidate() | {"citations": "not a list", "source_url": 5, "date": 7}
    build_briefing(register, [], TODAY, tier="v3", candidates=[bad])


def test_markdown_and_web_output_render_hostile_candidates_as_literal_text(
    register: Register,
) -> None:
    good = hostile_candidate() | {"source_url": "https://e.example/ok"}
    doc = build_briefing(register, [], TODAY, tier="v3", candidates=[good])
    for output in (render_markdown(doc), render_webpost(doc, ["regulatory"])):
        assert ESC not in output and "\x07" not in output
        assert "<script>" not in output
        # A word with a "scheme:" prefix is shown whole in a code span, where nothing is linked.
        assert "`[click](javascript:alert(1))`" in output
        assert "`![pixel](https://tracker.example/p.png)`" in output
        body = "\n".join(line for line in output.splitlines() if not line.startswith("> "))
        body = re.sub(r"(?<!\\)`.*?(?<!\\)`", "", body)  # code spans link nothing
        assert not re.search(r"(?<!\\)[\[\]<>`]", body)  # every other bracket and tag is escaped
        assert not re.search(r"(?<!\\)!\\\[", body)
        assert "\\<script\\>" in output


def test_html_text_and_docx_output_of_hostile_text() -> None:
    doc = Document("T", "g", sections=[Section("H", bullets=[HOSTILE_TITLE])])
    assert ESC not in render_newsletter_html(doc) and "<script>" not in render_newsletter_html(doc)
    assert ESC not in render_newsletter_text(doc)
    assert ESC not in render_document_xml(doc)
    assert docx_bytes(doc)


def test_check_detail_with_escape_sequences_is_not_printed_raw(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from regwatch.cli import main

    fetcher = FakeFetcher(
        {"https://regulator.nl.example/notices.xml": FetchError(f"boom {ESC}[2J")}
    )
    main(["--config", str(project), "check", "--fetch", "--source", "nl-notices"], fetcher=fetcher)
    assert ESC not in capsys.readouterr().out


# --- 6. csv formulas -------------------------------------------------------------


@pytest.mark.parametrize("prefix", list(FORMULA_STARTS))
def test_formula_cells_are_prefixed_with_an_apostrophe(prefix: str) -> None:
    assert neutralise_cell(f"{prefix}HYPERLINK(1)") == f"'{prefix}HYPERLINK(1)"


def test_ordinary_cells_are_unchanged() -> None:
    assert neutralise_cell("Plain, text") == "Plain, text"
    assert neutralise_cell("") == ""
    assert neutralise_cell("a=b") == "a=b"


def test_csv_output_neutralises_every_formula_cell() -> None:
    from regwatch.export import RECORD_COLUMNS

    row = {column: '=cmd|" /C calc"!A0' for column in RECORD_COLUMNS}
    text = records_csv([row])
    assert text.splitlines()[1].startswith('"\'=cmd|"" /C calc""!A0"')
    assert "\n=" not in text and ",=" not in text


# --- 7. suppressed change detection -------------------------------------------------


def test_empty_signal_is_suspicious_even_on_first_sight(config: Config, register: Register) -> None:
    (config.snapshots_dir / "sv-subscription.txt").write_text("   \n", encoding="utf-8")
    results = {r.source_id: r for r in check_sources(register.sources, {}, config.snapshots_dir)}
    assert results["sv-subscription"].status == "SUSPICIOUS"
    assert results["sv-subscription"].detail == "signal is empty"
    assert results["sv-subscription"].flagged


def test_a_source_that_is_emptied_is_suspicious_not_unchanged_or_changed(
    config: Config, register: Register
) -> None:
    seen = accept_results({}, check_sources(register.sources, {}, config.snapshots_dir), NOW)
    (config.snapshots_dir / "sv-register-api.txt").write_text("{}", encoding="utf-8")
    results = {r.source_id: r for r in check_sources(register.sources, seen, config.snapshots_dir)}
    assert results["sv-register-api"].status == "SUSPICIOUS"
    assert "shrank from" in results["sv-register-api"].detail


def test_shrinking_to_half_is_suspicious_but_not_slightly_shorter(
    config: Config, register: Register
) -> None:
    path = config.snapshots_dir / "sv-subscription.txt"
    path.write_text("x" * 100, encoding="utf-8")
    seen = accept_results({}, check_sources(register.sources, {}, config.snapshots_dir), NOW)
    assert seen["sv-subscription"]["signal_length"] == "100"
    path.write_text("x" * 51, encoding="utf-8")
    status = {
        r.source_id: r.status for r in check_sources(register.sources, seen, config.snapshots_dir)
    }
    assert status["sv-subscription"] == "CHANGED"
    path.write_text("x" * 49, encoding="utf-8")
    status = {
        r.source_id: r.status for r in check_sources(register.sources, seen, config.snapshots_dir)
    }
    assert status["sv-subscription"] == "SUSPICIOUS"


def test_a_short_baseline_is_not_judged_by_shrinkage(config: Config, register: Register) -> None:
    path = config.snapshots_dir / "sv-subscription.txt"
    path.write_text("x" * (MIN_PRIOR_LENGTH - 1), encoding="utf-8")
    seen = accept_results({}, check_sources(register.sources, {}, config.snapshots_dir), NOW)
    path.write_text("x", encoding="utf-8")
    status = {
        r.source_id: r.status for r in check_sources(register.sources, seen, config.snapshots_dir)
    }
    assert status["sv-subscription"] == "CHANGED"


def test_a_suspicious_result_is_not_accepted_as_the_baseline_unless_asked(
    config: Config, register: Register
) -> None:
    good = accept_results({}, check_sources(register.sources, {}, config.snapshots_dir), NOW)
    (config.snapshots_dir / "sv-register-api.txt").write_text("{}", encoding="utf-8")
    results = check_sources(register.sources, good, config.snapshots_dir)
    assert accept_results(good, results, NOW)["sv-register-api"] == good["sv-register-api"]
    forced = accept_results(good, results, NOW, accept_suspicious=True)
    assert forced["sv-register-api"]["sha256"] != good["sv-register-api"]["sha256"]


def test_old_state_without_a_length_still_loads(config: Config, register: Register) -> None:
    seen = {"nl-notices": {"sha256": "0" * 64, "origin": "snapshot", "checked": "x"}}
    results = {r.source_id: r for r in check_sources(register.sources, seen, config.snapshots_dir)}
    assert results["nl-notices"].status == "CHANGED"


# --- 8. write protection on case-insensitive file systems ----------------------------


def test_a_differently_cased_name_for_a_protected_file_is_refused(tmp_path: Path) -> None:
    protected = tmp_path / "Obligations.csv"
    protected.write_text("keep", encoding="utf-8")
    protected.unlink()  # the target does not exist, so the comparison is by folded name
    with pytest.raises(StateError, match="protected"):
        safe_write_text(tmp_path / "OBLIGATIONS.CSV", "clobber", [protected])
    assert not (tmp_path / "OBLIGATIONS.CSV").exists()


def test_a_hard_link_to_a_protected_file_is_refused(tmp_path: Path) -> None:
    protected = tmp_path / "obligations.csv"
    protected.write_text("keep", encoding="utf-8")
    link = tmp_path / "other-name.csv"
    os.link(protected, link)
    with pytest.raises(StateError, match="protected"):
        safe_write_text(link, "clobber", [protected])
    assert protected.read_text(encoding="utf-8") == "keep"


def test_existing_files_are_compared_by_identity_not_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protected, other = tmp_path / "a.csv", tmp_path / "b.csv"
    protected.write_text("a", encoding="utf-8")
    other.write_text("b", encoding="utf-8")
    seen: list[tuple[Path, Path]] = []
    real = os.path.samefile

    def spy(first: Path, second: Path) -> bool:
        seen.append((Path(first), Path(second)))
        return real(first, second)

    monkeypatch.setattr(os.path, "samefile", spy)
    safe_write_text(other, "changed", [protected])
    assert seen == [(other.resolve(), protected.resolve())]


# --- surrogates ----------------------------------------------------------------------


def test_lone_surrogates_cannot_break_encoding(tmp_path: Path) -> None:
    doc = Document(
        "T\ud800", "g", sections=[Section("H\udfff", paragraphs=["p\ud83d"], bullets=["b\ud800"])]
    )
    assert docx_bytes(doc)
    assert "\ud800" not in render_markdown(doc)
    assert "\ud800" not in render_newsletter_html(doc)
    safe_write_text(tmp_path / "out.txt", "a\ud800b", [])
    assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "a?b"


# --- config for the fetch hardening ---------------------------------------------------


def test_fetch_hardening_options_parse(project: Path) -> None:
    text = project.read_text(encoding="utf-8").replace(
        "[fetch]\n",
        '[fetch]\ntotal_timeout_seconds = 45\nallow_private_hosts = true\nallowed_file_roots = ["snapshots", "/srv/feeds"]\n',
    )
    project.write_text(text, encoding="utf-8")
    fetch = load_config(project).fetch
    assert fetch.total_timeout_seconds == 45.0
    assert fetch.allow_private_hosts is True
    assert fetch.allowed_file_roots == (project.parent.resolve() / "snapshots", Path("/srv/feeds"))


def test_config_refuses_a_file_root_that_is_a_parent_of_home(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from regwatch.config import ConfigError

    home = tmp_path / "home" / "user"
    home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    for root in (home.parent, home, tmp_path):
        project.write_text(
            project.read_text(encoding="utf-8").replace(
                "[fetch]\n", f'[fetch]\nallowed_file_roots = ["{root}"]\n'
            ),
            encoding="utf-8",
        )
        with pytest.raises(ConfigError, match="too broad"):
            load_config(project)
        project.write_text(
            project.read_text(encoding="utf-8").replace(f'allowed_file_roots = ["{root}"]\n', ""),
            encoding="utf-8",
        )


def test_fetch_hardening_defaults_are_the_safe_ones(tmp_path: Path) -> None:
    from regwatch.config import FetchSettings

    defaults = FetchSettings()
    assert defaults.total_timeout_seconds == 60.0
    assert defaults.allow_private_hosts is False
    assert defaults.allowed_file_roots == ()


@pytest.mark.parametrize(
    "snippet",
    [
        "allow_private_hosts = 1",
        'allow_private_hosts = "yes"',
        "total_timeout_seconds = 0",
        "total_timeout_seconds = 99999",
        "allowed_file_roots = [1]",
        'allowed_file_roots = "snapshots"',
    ],
)
def test_fetch_hardening_options_are_validated(project: Path, snippet: str) -> None:
    from regwatch.config import ConfigError

    project.write_text(
        project.read_text(encoding="utf-8").replace("[fetch]\n", f"[fetch]\n{snippet}\n"),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_config(project)


def test_protected_paths_include_the_config_and_state_files(config: Config) -> None:
    protected = set(config.protected_paths())
    assert config.config_path in protected
    assert config.seen_path.resolve() in protected
    assert config.candidates_path.resolve() in protected
    assert set(config.register.all_paths()) <= protected
