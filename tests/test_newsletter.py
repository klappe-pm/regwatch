"""`regwatch newsletter`: a send-ready email built from the period's changes, never sent.

The language model is a fake poster and the keychain a FakeSystem, so nothing leaves the
machine.
"""

from __future__ import annotations

import email
import email.policy
import json
import struct
import zlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from conftest import NOW, TODAY, FakeSystem

from regwatch.cli import main
from regwatch.config import DocumentDesign, load_config
from regwatch.fetch import Credential
from regwatch.llm import change_facts
from regwatch.newsletter import EMAIL_WIDTH, LOGO_CID, build_newsletter, newsletter_content
from regwatch.register import load_register

KEY = "fake" + "-letter-" + "key-5150"


def make_png(width: int = 120, height: int = 40) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    pixels = zlib.compress(b"\x00" + b"\x00\x00\x00" * width)
    return (
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", pixels) + chunk(b"IEND", b"")
    )


class FakePoster:
    def __init__(self, passages: list[dict[str, Any]]) -> None:
        self.passages = passages
        self.payloads: list[Mapping[str, object]] = []

    def post_json(
        self,
        url: str,
        payload: Mapping[str, object],
        *,
        credential: Credential | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> str:
        self.payloads.append(payload)
        text = json.dumps({"passages": self.passages})
        return json.dumps(
            {
                "content": [{"type": "text", "text": text}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 900, "output_tokens": 120},
            }
        )


class Runner:
    def __init__(self, project: Path, capsys: pytest.CaptureFixture[str]) -> None:
        self.project = project
        self.capsys = capsys
        self.fake = FakeSystem("linux")

    def __call__(self, *args: str, poster: Any = None) -> tuple[int, str, str]:
        code = main(
            ["--config", str(self.project), *args],
            today=TODAY,
            now=NOW,
            system=self.fake.system(),
            poster=poster,
        )
        captured = self.capsys.readouterr()
        return code, captured.out, captured.err


@pytest.fixture
def run(project: Path, capsys: pytest.CaptureFixture[str]) -> Runner:
    return Runner(project, capsys)


def append(project: Path, text: str) -> None:
    project.write_text(project.read_text(encoding="utf-8") + "\n" + text, encoding="utf-8")


def test_a_newsletter_needs_premium(run: Runner, tmp_path: Path) -> None:
    code, _out, err = run("newsletter", "--out", str(tmp_path / "n"))
    assert code == 2 and "premium feature" in err and "regwatch premium on" in err
    assert not list(tmp_path.glob("n.*"))


def test_the_newsletter_is_written_three_ways_and_never_sent(run: Runner, tmp_path: Path) -> None:
    run("premium", "on")
    code, out, _err = run("newsletter", "--since", "60", "--out", str(tmp_path / "issue.eml"))
    assert code == 0 and "does not send email" in out and "fixed sentences" in out
    raw = (tmp_path / "issue.eml").read_bytes()
    message = email.message_from_bytes(raw, policy=email.policy.default)
    assert message.get_content_type() == "multipart/alternative"
    assert message["To"] is None and message["From"] is None and message["Cc"] is None
    assert message["X-Unsent"] == "1"
    assert message["Subject"] == "Example Pantry Co. regulatory newsletter"
    parts = [part.get_content_type() for part in message.iter_parts()]
    assert parts == ["text/plain", "text/html"]
    page = (tmp_path / "issue.html").read_text(encoding="utf-8")
    text = (tmp_path / "issue.txt").read_text(encoding="utf-8")
    assert f'width="{EMAIL_WIDTH}"' in page and "<script" not in page and "<style" not in page
    # The table shrinks to a narrow screen instead of being 600 pixels plus the padding.
    assert f'style="width:100%;max-width:{EMAIL_WIDTH}px;' in page
    assert f'style="width:{EMAIL_WIDTH}px' not in page
    assert "<link" not in page and "class=" not in page
    assert "In This Issue" in page and "Reply to this message to stop." in page
    assert "Not legal advice." in page and "Not legal advice." in text
    assert "IN THIS ISSUE" in text and "Allergen Declaration Order published" in text


def test_the_newsletter_follows_the_design_and_the_closing_line(
    run: Runner, project: Path, tmp_path: Path
) -> None:
    append(
        project,
        '[document]\nprimary_color = "#123456"\naccent_color = "#7A2E0B"\nfont = "Georgia"\n'
        'title_format = "{organisation}: {title} ({date})"\norganisation = "Pantry & Co"\n'
        'header = "Internal <only>"\nfooter = "Pantry, 1 Road"\n'
        '[newsletter]\nfooter = "Write to news@example.com to stop."\n',
    )
    run("premium", "on")
    assert run("newsletter", "--out", str(tmp_path / "n"))[0] == 0
    page = (tmp_path / "n.html").read_text(encoding="utf-8")
    assert "background:#123456" in page and "border-bottom:2px solid #7a2e0b" in page
    assert "Georgia, &#x27;Times New Roman&#x27;, serif" in page
    assert "Pantry &amp; Co: Example Pantry Co. regulatory newsletter (2026-10-19)" in page
    assert "Internal &lt;only&gt;" in page and "Write to news@example.com to stop." in page
    text = (tmp_path / "n.txt").read_text(encoding="utf-8")
    assert text.startswith("Internal <only>") and "Pantry, 1 Road" in text


def test_a_png_logo_is_inline_in_the_page_and_related_in_the_eml(
    run: Runner, project: Path, tmp_path: Path
) -> None:
    (project.parent / "logo.png").write_bytes(make_png())
    append(project, '[document]\nlogo = "logo.png"\n')
    run("premium", "on")
    assert run("newsletter", "--out", str(tmp_path / "n"))[0] == 0
    page = (tmp_path / "n.html").read_text(encoding="utf-8")
    assert 'src="data:image/png;base64,' in page and 'width="120"' in page
    message = email.message_from_bytes(
        (tmp_path / "n.eml").read_bytes(), policy=email.policy.default
    )
    related = list(message.iter_parts())[1]
    assert related.get_content_type() == "multipart/related"
    # RFC 2387: the related part names the type of its root, and the logo is inline.
    assert related.get_param("type") == "text/html"
    image = list(related.iter_parts())[1]
    assert image["Content-ID"] == f"<{LOGO_CID}>" and image.get_content() == make_png()
    assert image.get_content_disposition() == "inline" and not image.is_attachment()
    assert f"cid:{LOGO_CID}" in next(iter(related.iter_parts())).get_content()


def test_a_refused_logo_stops_the_newsletter(run: Runner, project: Path, tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "logo.png").write_bytes(make_png())
    append(project, f'[document]\nlogo = "{outside / "logo.png"}"\n')
    run("premium", "on")
    code, _out, err = run("newsletter", "--out", str(tmp_path / "n"))
    assert code == 2 and "inside the project folder" in err
    assert not (tmp_path / "n.eml").exists()


def test_generate_needs_the_language_model_turned_on(run: Runner, tmp_path: Path) -> None:
    run("premium", "on")
    code, _out, err = run("newsletter", "--generate", "--out", str(tmp_path / "n"))
    assert code == 2 and "regwatch llm on" in err


def test_generated_copy_is_labelled_kept_with_its_facts_and_recorded(
    run: Runner, project: Path, tmp_path: Path
) -> None:
    run("premium", "on")
    run("llm", "on")
    run.fake.keychain["REGWATCH_KEY_ANTHROPIC"] = KEY
    poster = FakePoster(
        [
            {
                "section": "opening",
                "text": "Four <b>sources</b> moved this month.",
                "cites": ["change:nl-notices"],
            },
            {"section": "changes", "text": "Made up.", "cites": ["change:no-such-source"]},
        ]
    )
    code, out, err = run("newsletter", "--generate", "--out", str(tmp_path / "n"), poster=poster)
    assert code == 0 and "opening and summaries: generated" in out
    assert "left out a generated passage" in err and "change:no-such-source" in err
    page = (tmp_path / "n.html").read_text(encoding="utf-8")
    assert ">Generated</span>Four &lt;b&gt;sources&lt;/b&gt; moved this month." in page
    assert "<li>Northland regulator notices feed: first snapshot taken</li>" in page
    assert "change:nl-notices" not in page
    # The section whose passage was dropped keeps its fixed sentence.
    assert "In this period four sources changed." in page and "(s)" not in page
    text = (tmp_path / "n.txt").read_text(encoding="utf-8")
    assert "[Generated] Four <b>sources</b> moved this month." in text
    prompt = json.dumps(poster.payloads[0])
    assert KEY not in prompt and "change:nl-notices" in prompt
    log = load_config(project).llm_calls_path.read_text(encoding="utf-8").splitlines()
    record = json.loads(log[0])
    assert record["provider"] == "anthropic" and record["model"] == "claude-opus-5-5"
    assert (record["input_tokens"], record["output_tokens"], record["kept"]) == (900, 120, 1)
    assert "Northland" not in log[0] and KEY not in log[0]


def test_untrusted_candidates_are_escaped_and_cleaned(
    run: Runner, project: Path, tmp_path: Path
) -> None:
    config = load_config(project)
    config.state_dir.mkdir(parents=True, exist_ok=True)
    config.candidates_path.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "date": "2026-10-15",
                        "agency": "Agency\x1b[31m",
                        "headline": "<img src=x onerror=alert(1)>",
                        "source_url": "javascript:alert(1)",
                    },
                    {"date": "2020-01-01", "headline": "Too old to include"},
                ]
            }
        ),
        encoding="utf-8",
    )
    run("premium", "on")
    assert run("newsletter", "--since", "30", "--out", str(tmp_path / "n"))[0] == 0
    page = (tmp_path / "n.html").read_text(encoding="utf-8")
    assert "<img src=x" not in page and "&lt;img src=x onerror=alert(1)&gt;" in page
    assert "javascript:" not in page and "Too old" not in page
    text = (tmp_path / "n.txt").read_text(encoding="utf-8")
    assert "\x1b" not in text and "Agency [31m" in text


def test_the_period_bounds_and_the_default_name(
    run: Runner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run("premium", "on")
    for days in ("0", "367"):
        code, _out, err = run("newsletter", "--since", days)
        assert code == 2 and "1 to 366 days" in err
    monkeypatch.chdir(tmp_path)
    assert run("newsletter")[0] == 0
    assert sorted(p.name for p in tmp_path.glob("regwatch-*")) == [
        "regwatch-newsletter-2026-10-19.eml",
        "regwatch-newsletter-2026-10-19.html",
        "regwatch-newsletter-2026-10-19.txt",
    ]


def test_the_content_keeps_only_the_period(project: Path) -> None:
    config = load_config(project)
    register = load_register(config)
    content = newsletter_content(register, [], [], [{"date": "bad"}], TODAY, 30)
    assert [e.date for e in content.events] == ["2026-10-01"]
    assert content.candidates == () and content.changes == () and content.impacts == ()
    doc = build_newsletter(register, content, DocumentDesign())
    # Thirty days ending today, today included.
    assert doc.subtitle == "20 September to 19 October"
    assert "No candidate impact" in doc.sections[-1].paragraphs[0]
    assert change_facts([], {}) == []
