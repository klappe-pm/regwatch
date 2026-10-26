"""Correctness of the premium content: generated copy calls, the newsletter period and
email, the documents and the web app's handling of generated copy.

Every test here fails without the fix it names. The language model is a fake poster and
the keychain a FakeSystem, so nothing leaves the machine.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any

import pytest
from conftest import NOW, TODAY, FakeSystem
from test_design import SAFE_SVG
from test_fetch import make, web
from test_llm import FACTS, KEY, FakePoster, FakeProvider, answer
from test_newsletter import FakePoster as NewsletterPoster
from test_newsletter import append, make_png

import regwatch.cli
import regwatch.llm
import regwatch.webapi
from regwatch.check import SourceResult
from regwatch.cli import main
from regwatch.config import DocumentDesign, load_config
from regwatch.design import Logo
from regwatch.document import Document, GeneratedPassage, Section
from regwatch.fetch import Credential, FetchError
from regwatch.impact import Impact
from regwatch.llm import (
    ANTHROPIC_FALLBACK_BETA,
    ANTHROPIC_FALLBACK_MODELS,
    MAX_CITES,
    MAX_PROVIDER_MESSAGE,
    OLLAMA_CONTEXT,
    RETRY_DELAY_SECONDS,
    AnthropicProvider,
    Fact,
    GenerationError,
    OllamaProvider,
    OpenAIProvider,
    candidate_facts,
    generate,
    parse_passages,
    provider_message,
)
from regwatch.newsletter import (
    NEWSLETTER_SECTIONS,
    NOWRAP,
    NewsletterContent,
    _candidate_line,
    build_newsletter,
    newsletter_content,
    render_email_html,
)
from regwatch.register import load_register
from regwatch.render import docx_bytes, render_markdown
from regwatch.settings import set_llm, set_premium
from regwatch.webapi import Api, ApiError
from regwatch.wording import (
    count,
    date_range,
    join_clauses,
    long_date,
    number,
    prose_date,
    provider_name,
    severity_label,
    status_phrase,
)
from regwatch.workspace import NO_FACTS_NOTICE, SVG_LOGO_NOTE, document_plan

# --- C3: an answer cut off at max_tokens is a clear error -----------------------------

CUT_OFF = [
    (AnthropicProvider, {"stop_reason": "max_tokens", "content": [{"type": "text", "text": "{"}]}),
    (OpenAIProvider, {"choices": [{"message": {"content": "{"}, "finish_reason": "length"}]}),
    (OllamaProvider, {"message": {"content": "{"}, "done_reason": "length"}),
]


def provider(kind: Any, body: dict[str, Any]) -> Any:
    poster = FakePoster(json.dumps(body))
    return kind(poster, "m") if kind is OllamaProvider else kind(poster, KEY, "m")


@pytest.mark.parametrize(("kind", "body"), CUT_OFF)
def test_a_cut_off_answer_names_the_max_tokens_setting(kind: Any, body: dict[str, Any]) -> None:
    with pytest.raises(GenerationError) as caught:
        provider(kind, body).complete("S", "P", 321)
    message = str(caught.value)
    assert "cut off at 321 tokens" in message and "[llm] max_tokens" in message
    assert caught.value.outcome == "cut off"


def test_a_cut_off_call_is_recorded_as_cut_off() -> None:
    records: list[dict[str, object]] = []
    cut = GenerationError("cut off", outcome="cut off")
    with pytest.raises(GenerationError):
        generate(FakeProvider(cut), FACTS, "x", max_tokens=10, record=records.append)
    assert records[0]["outcome"] == "cut off"


def test_ollama_is_asked_for_json_with_a_large_context() -> None:
    poster = FakePoster(json.dumps({"message": {"content": "{}"}, "done_reason": "stop"}))
    OllamaProvider(poster, "llama3.2").complete("S", "P", 777)
    payload = poster.calls[0]["payload"]
    assert payload["format"] == "json"
    assert payload["options"] == {"num_predict": 777, "num_ctx": OLLAMA_CONTEXT}
    assert OLLAMA_CONTEXT == 16384


def test_a_complete_answer_is_not_taken_for_a_cut_off_one() -> None:
    done = [
        (AnthropicProvider, {"stop_reason": "end_turn", "content": []}),
        (OpenAIProvider, {"choices": [{"message": {"content": "x"}, "finish_reason": "stop"}]}),
        (OllamaProvider, {"message": {"content": "x"}, "done_reason": "stop"}),
    ]
    for kind, body in done:
        provider(kind, body).complete("S", "P", 10)
    assert answer() == json.dumps({"passages": []})


# --- C4: a period of N days is N days, today included --------------------------------


@pytest.mark.parametrize(
    ("since", "first_day"), [(1, "2026-10-19"), (7, "2026-10-13"), (30, "2026-09-20")]
)
def test_a_period_holds_exactly_its_days(project: Path, since: int, first_day: str) -> None:
    register = load_register(load_config(project))
    first = dt.date.fromisoformat(first_day)
    days = [(first - dt.timedelta(days=1)).isoformat(), first_day, "2026-10-19", "2026-10-20"]
    candidates = [{"date": day, "headline": day} for day in days]
    content = newsletter_content(register, [], [], candidates, TODAY, since)
    assert content.start == first and content.end == TODAY
    assert [c["date"] for c in content.candidates] == [first_day, "2026-10-19"]
    assert (content.end - content.start).days + 1 == since


# --- C5: a second Generate shows the new copy ----------------------------------------


class SwitchingPoster(NewsletterPoster):
    """Answers each Generate with the next of its openings."""

    def __init__(self, openings: list[str]) -> None:
        super().__init__([])
        self.openings = openings

    def post_json(self, url: str, payload: Any, **kwargs: Any) -> str:
        text = self.openings[len(self.payloads)]
        self.passages = [{"section": "opening", "text": text, "cites": ["change:nl-notices"]}]
        return super().post_json(url, payload, **kwargs)


def test_a_second_generate_replaces_the_copy_the_page_reloads(project: Path) -> None:
    set_premium(project, True)
    set_llm(project, enabled=True)
    fake = FakeSystem("linux")
    fake.environ["REGWATCH_KEY_ANTHROPIC"] = KEY
    poster = SwitchingPoster(["First take.", "Second take."])
    api = Api(project, lambda: TODAY, system=fake.system(), clock=lambda: NOW, poster=poster)
    for round_number, expected in ((1, "First take."), (2, "Second take.")):
        api.handle("POST", "/api/newsletter/generate", {}, {"since": 7})
        query = {"since": "7", "generated": "1", "round": str(round_number)}
        page = api.handle("GET", "/api/newsletter", query, {})[1]["html"]
        preview = api.handle("GET", "/api/newsletter/preview", query, {})[1].html
        assert expected in page and expected in preview
        assert "First take." not in page or round_number == 1


# --- C7: a passage citing more facts than can be shown is dropped, never cut ----------

MANY = [Fact(f"change:source-{n}", "changes", f"Source {n} content changed") for n in range(25)]


def test_a_passage_citing_more_than_the_limit_is_dropped_with_a_reason() -> None:
    ids = [f.fact_id for f in MANY]
    text = json.dumps({"passages": [{"section": "changes", "text": "Many moved.", "cites": ids}]})
    result = parse_passages(text, MANY)
    assert result.count == 0
    assert result.dropped == ["passage 1: it cites 25 facts; a passage may cite at most 20"]


def test_a_passage_citing_exactly_the_limit_keeps_every_fact() -> None:
    ids = [f.fact_id for f in MANY[:MAX_CITES]] + [MANY[0].fact_id]
    text = json.dumps({"passages": [{"section": "changes", "text": "Many moved.", "cites": ids}]})
    kept = parse_passages(text, MANY).section("changes")[0]
    assert len(kept.cites) == len(kept.facts) == MAX_CITES == 20


# --- C8: passages only for shown sections, each from its own section's facts --------


def passages(*items: tuple[str, list[str]]) -> str:
    return json.dumps(
        {"passages": [{"section": s, "text": "It moved.", "cites": c} for s, c in items]}
    )


def test_a_passage_for_a_section_the_output_does_not_show_is_dropped() -> None:
    text = passages(("obligations", ["change:us-fda-news"]), ("opening", ["change:us-fda-news"]))
    result = parse_passages(text, FACTS, sections=NEWSLETTER_SECTIONS)
    assert result.section("obligations") == [] and result.count == 1
    assert result.dropped == ["passage 1: this output has no obligations section"]
    assert NEWSLETTER_SECTIONS == ("opening", "changes", "candidates", "impacts")


def test_a_section_summary_must_cite_a_fact_of_its_own_section() -> None:
    text = passages(
        ("changes", ["impact:bar/us-sodium"]),
        ("impacts", ["impact:bar/us-sodium", "change:us-fda-news"]),
        ("opening", ["impact:bar/us-sodium"]),
    )
    result = parse_passages(text, FACTS)
    assert result.dropped == ["passage 1: it cites no fact of the changes section it summarises"]
    assert result.section("changes") == [] and result.count == 2


def test_the_prompt_names_only_the_shown_sections() -> None:
    provider = FakeProvider(passages(("obligations", ["change:us-fda-news"])))
    result = generate(provider, FACTS, "x", max_tokens=10, sections=NEWSLETTER_SECTIONS)
    prompt = provider.prompts[0][1]
    assert "only for these sections: opening, changes, candidates, impacts." in prompt
    assert result.count == 0 and "no obligations section" in result.dropped[0]


def test_the_newsletter_drops_a_passage_for_its_missing_section(project: Path) -> None:
    set_premium(project, True)
    set_llm(project, enabled=True)
    fake = FakeSystem("linux")
    fake.environ["REGWATCH_KEY_ANTHROPIC"] = KEY
    poster = NewsletterPoster(
        [{"section": "obligations", "text": "Due soon.", "cites": ["change:nl-notices"]}]
    )
    api = Api(project, lambda: TODAY, system=fake.system(), clock=lambda: NOW, poster=poster)
    data = api.handle("POST", "/api/newsletter/generate", {}, {"since": 7})[1]
    assert data["generated"] is False
    assert data["dropped"] == ["passage 1: this output has no obligations section"]


def test_the_newsletter_command_drops_a_passage_for_its_missing_section(
    project: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    set_premium(project, True)
    set_llm(project, enabled=True)
    fake = FakeSystem("linux")
    fake.environ["REGWATCH_KEY_ANTHROPIC"] = KEY
    poster = NewsletterPoster(
        [{"section": "obligations", "text": "Due soon.", "cites": ["change:nl-notices"]}]
    )
    args = ["--config", str(project), "newsletter", "--generate", "--out", str(tmp_path / "n")]
    code = main(args, today=TODAY, now=NOW, system=fake.system(), poster=poster)
    captured = capsys.readouterr()
    assert code == 0 and "no obligations section" in captured.err
    assert "fixed sentences" in captured.out
    assert "only for these sections: opening, changes, candidates, impacts" in json.dumps(
        poster.payloads[0]
    )


# --- C9: the Anthropic fallback only where it exists, one retry, the provider's reason --

DONE = json.dumps({"stop_reason": "end_turn", "content": [{"type": "text", "text": "ok"}]})


class SequencePoster(FakePoster):
    """Answers each POST with the next item: a body, or an error to raise."""

    def __init__(self, *items: str | Exception) -> None:
        super().__init__()
        self.items = list(items)

    def post_json(self, url: str, payload: Any, **kwargs: Any) -> str:
        self.answer = self.items[len(self.calls)]
        return super().post_json(url, payload, **kwargs)


@pytest.mark.parametrize("model", sorted(ANTHROPIC_FALLBACK_MODELS))
def test_a_fallback_model_is_sent_the_fallback_option_and_its_header(model: str) -> None:
    poster = FakePoster(DONE)
    AnthropicProvider(poster, KEY, model).complete("S", "P", 10)
    call = poster.calls[0]
    assert call["payload"]["fallbacks"] == "default"
    assert call["headers"]["anthropic-beta"] == ANTHROPIC_FALLBACK_BETA


@pytest.mark.parametrize("model", ["claude-haiku-5-5", "claude-sonnet-5", "m"])
def test_another_model_is_sent_neither_the_fallback_option_nor_its_header(model: str) -> None:
    poster = FakePoster(DONE)
    AnthropicProvider(poster, KEY, model).complete("S", "P", 10)
    call = poster.calls[0]
    assert "fallbacks" not in call["payload"]
    assert call["headers"] == {"anthropic-version": "2023-06-01"}
    assert call["payload"]["output_config"] == {"effort": "low"}


@pytest.mark.parametrize("status", [429, 500, 503, 599, 529])
def test_a_busy_or_failing_answer_is_retried_once_after_a_pause(status: int) -> None:
    pauses: list[float] = []
    busy = FetchError(f"HTTP status {status}", status=status)
    poster = SequencePoster(busy, DONE)
    completion = AnthropicProvider(poster, KEY, "m", sleep=pauses.append).complete("S", "P", 10)
    assert completion.text == "ok" and len(poster.calls) == 2
    assert pauses == [RETRY_DELAY_SECONDS] and RETRY_DELAY_SECONDS > 0
    assert poster.calls[0]["payload"] == poster.calls[1]["payload"]


def test_a_second_failure_is_not_retried_again() -> None:
    pauses: list[float] = []
    busy = FetchError("HTTP status 529", status=529)
    poster = SequencePoster(busy, busy, DONE)
    with pytest.raises(FetchError):
        AnthropicProvider(poster, KEY, "m", sleep=pauses.append).complete("S", "P", 10)
    assert len(poster.calls) == 2 and len(pauses) == 1


@pytest.mark.parametrize("error", [FetchError("HTTP status 400", status=400), FetchError("x")])
def test_a_request_error_or_a_failed_connection_is_not_retried(error: FetchError) -> None:
    pauses: list[float] = []
    poster = SequencePoster(error, DONE)
    with pytest.raises(FetchError):
        AnthropicProvider(poster, KEY, "m", sleep=pauses.append).complete("S", "P", 10)
    assert len(poster.calls) == 1 and pauses == []


def test_the_providers_reason_is_added_to_the_error_cleaned_and_cut() -> None:
    reason = "model: \x1b[31mnot found" + " and more" * 40
    body = json.dumps({"type": "error", "error": {"type": "not_found", "message": reason}})
    failure = FetchError("HTTP status 404", status=404, body=body)
    with pytest.raises(GenerationError) as caught:
        generate(FakeProvider(failure), FACTS, "x", max_tokens=10)
    message = str(caught.value)
    assert message.startswith("the fake request failed: HTTP status 404: model: [31mnot found")
    assert "\x1b" not in message
    detail = message.split("HTTP status 404: ", 1)[1]
    assert len(detail) <= MAX_PROVIDER_MESSAGE == 200


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ('{"error": {"message": "Overloaded"}}', "Overloaded"),
        ('{"error": "model llama9 not found"}', "model llama9 not found"),
        ('{"error": {"code": 5}}', ""),
        ("<html>bad gateway</html>", ""),
        ("[1]", ""),
        ("", ""),
    ],
)
def test_the_providers_reason_is_read_from_its_error_body(body: str, expected: str) -> None:
    assert provider_message(body) == expected


def test_an_error_without_a_reason_reads_as_before() -> None:
    with pytest.raises(GenerationError, match=r"^the fake request failed: HTTP status 502$"):
        generate(FakeProvider(FetchError("HTTP status 502", status=502)), FACTS, "x", max_tokens=1)


def test_a_post_error_keeps_its_status_and_body_without_the_key() -> None:
    credential = Credential("header", "x-api-key", KEY)
    reason = json.dumps({"error": {"message": f"bad key {KEY}"}}).encode()
    head = f"HTTP/1.1 401 Unauthorized\r\nContent-Length: {len(reason)}\r\n\r\n".encode()
    network = web(head + reason)
    with pytest.raises(FetchError) as caught:
        make(network).post_json("https://example.org/", {}, credential=credential)
    assert caught.value.status == 401
    assert KEY not in caught.value.body and provider_message(caught.value.body) == "bad key [key]"


@pytest.mark.parametrize("body", ["<html>busy</html>", "[1, 2]"])
@pytest.mark.parametrize("kind", [AnthropicProvider, OpenAIProvider, OllamaProvider])
def test_a_provider_answer_that_is_not_a_json_object_is_recorded_unreadable(
    kind: Any, body: str
) -> None:
    records: list[dict[str, object]] = []
    with pytest.raises(GenerationError, match="was not") as caught:
        generate(kind_provider(kind, body), FACTS, "x", max_tokens=10, record=records.append)
    assert caught.value.outcome == "unreadable"
    assert records[0]["outcome"] == "unreadable"


def test_a_refusal_is_still_recorded_as_refused() -> None:
    records: list[dict[str, object]] = []
    body = json.dumps({"stop_reason": "refusal", "content": []})
    with pytest.raises(GenerationError, match="declined"):
        generate(
            kind_provider(AnthropicProvider, body), FACTS, "x", max_tokens=1, record=records.append
        )
    assert records[0]["outcome"] == "refused"


def kind_provider(kind: Any, body: str) -> Any:
    poster = FakePoster(body)
    return kind(poster, "m") if kind is OllamaProvider else kind(poster, KEY, "m")


# --- C12: Generate on an empty period falls back to the fixed sentences --------------


class RefusingPoster(NewsletterPoster):
    """Fails the test if any request is sent."""

    def post_json(self, url: str, payload: Any, **kwargs: Any) -> str:
        raise AssertionError("no request may be sent for an empty period")


def generating(project: Path) -> FakeSystem:
    set_premium(project, True)
    set_llm(project, enabled=True)
    fake = FakeSystem("linux")
    fake.environ["REGWATCH_KEY_ANTHROPIC"] = KEY
    return fake


def no_facts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every period empty: no newsletter item and no document fact."""
    monkeypatch.setattr(NewsletterContent, "facts", lambda self: [])

    def plan(*args: Any) -> Any:
        return document_plan(*args)[0], []

    monkeypatch.setattr(regwatch.webapi, "document_plan", plan)
    monkeypatch.setattr(regwatch.cli, "document_plan", plan)


def test_generate_on_an_empty_period_uses_the_fixed_sentences_in_the_web_app(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = generating(project)
    no_facts(monkeypatch)
    api = Api(
        project, lambda: TODAY, system=fake.system(), clock=lambda: NOW, poster=RefusingPoster([])
    )
    status, data = api.handle("POST", "/api/newsletter/generate", {}, {"since": 7})
    assert status == 200 and data["generated"] is False and data["notice"] == NO_FACTS_NOTICE
    assert "html" in data and data["dropped"] == []
    status, data = api.handle("POST", "/api/document/generate", {}, {"kind": "briefing"})
    assert status == 200 and data["notice"] == NO_FACTS_NOTICE and data["generated"] is False


def test_generate_on_an_empty_period_uses_the_fixed_sentences_in_the_commands(
    project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = generating(project)
    no_facts(monkeypatch)
    for command in (["newsletter"], ["document", "--format", "md"]):
        out = str(tmp_path / command[0])
        args = ["--config", str(project), *command, "--generate", "--out", out]
        code = main(args, today=TODAY, now=NOW, system=fake.system(), poster=RefusingPoster([]))
        captured = capsys.readouterr()
        assert code == 0, captured.err
        assert NO_FACTS_NOTICE in captured.out
    assert not load_config(project).llm_calls_path.exists()


def test_a_failed_generate_is_a_409_not_a_server_error(project: Path) -> None:
    fake = generating(project)
    failure = FetchError("HTTP status 400", status=400)
    api = Api(
        project, lambda: TODAY, system=fake.system(), clock=lambda: NOW, poster=FakePoster(failure)
    )
    for path, body in (
        ("/api/newsletter/generate", {"since": 7}),
        ("/api/document/generate", {"kind": "briefing"}),
    ):
        with pytest.raises(ApiError) as caught:
            api.handle("POST", path, {}, body)
        assert caught.value.status == 409 and "request failed" in str(caught.value)


# --- C13: smaller corrections ----------------------------------------------------------

EMAIL_DOC = Document(
    "Pantry newsletter",
    "2026-10-19",
    subtitle="Changes from 2026-10-13 to 2026-10-19",
    sections=[Section("What Changed", bullets=["Due on 15 November 2026: label rules"])],
)
PNG_LOGO = Logo("png", b"\x89PNG", 120, 40)


def email(design: DocumentDesign, footer: str = "Reply to stop.", logo: Logo | None = None) -> str:
    return render_email_html(EMAIL_DOC, design, footer, logo=logo, logo_src="cid:logo@regwatch")


def test_the_unused_fact_id_pattern_is_gone() -> None:
    assert not hasattr(regwatch.llm, "FACT_ID_RE")


def test_the_email_header_line_runs_above_the_logo() -> None:
    page = email(DocumentDesign(header="Internal draft"), logo=PNG_LOGO)
    assert page.index("Internal draft") < page.index('<img src="cid:logo@regwatch"')


def test_dates_in_the_email_do_not_break_across_lines() -> None:
    page = email(DocumentDesign())
    assert f"{NOWRAP}2026-10-13</span> to {NOWRAP}2026-10-19</span>" in page
    assert f"Due on {NOWRAP}15 November 2026</span>: label rules" in page
    assert "<title>Pantry newsletter</title>" in page


def test_an_empty_footer_writes_no_empty_paragraph() -> None:
    page = email(DocumentDesign(footer=""), footer="")
    assert not re.search(r"<p [^>]*></p>", page)
    assert email(DocumentDesign(footer="1 Example Road")).count("1 Example Road") == 1


def test_a_markdown_fact_keeps_its_id_alone_in_a_code_span() -> None:
    passage = GeneratedPassage(
        "It moved.", ["change:us-fda-news"], ["change:us-fda-news: FDA *news*"]
    )
    doc = Document("T", "2026-10-19", sections=[Section("Changes", generated=[passage])])
    assert "- `change:us-fda-news`: FDA \\*news\\*" in render_markdown(doc)


def test_llm_status_without_a_keychain_tool_names_the_variable(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeSystem("linux")
    fake.tools.clear()
    code = main(["--config", str(project), "llm", "status"], today=TODAY, system=fake.system())
    out = capsys.readouterr().out
    assert code == 0
    assert "key REGWATCH_KEY_ANTHROPIC: unavailable; no keychain tool was found" in out
    assert "set the environment variable REGWATCH_KEY_ANTHROPIC" in out
    assert "keys set" not in out


def test_an_svg_logo_is_reported_as_missing_from_the_email(
    project: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (project.parent / "logo.svg").write_text(SAFE_SVG, encoding="utf-8")
    append(project, '[document]\nlogo = "logo.svg"\n')
    set_premium(project, True)
    args = ["--config", str(project), "newsletter", "--out", str(tmp_path / "n")]
    assert main(args, today=TODAY, now=NOW) == 0
    assert SVG_LOGO_NOTE in capsys.readouterr().out
    api = Api(project, lambda: TODAY, clock=lambda: NOW)
    assert api.handle("GET", "/api/newsletter", {"since": "7"}, {})[1]["logo_note"] == SVG_LOGO_NOTE


def test_a_png_logo_gives_no_logo_note(project: Path) -> None:
    (project.parent / "logo.png").write_bytes(make_png(240, 80))
    append(project, '[document]\nlogo = "logo.png"\n')
    set_premium(project, True)
    api = Api(project, lambda: TODAY, clock=lambda: NOW)
    assert api.handle("GET", "/api/newsletter", {"since": "7"}, {})[1]["logo_note"] == ""


# --- W1: plain wording -----------------------------------------------------------------

WEB_EXPORT = Path(regwatch.webapi.__file__).resolve().parent / "web"
PLURAL_HEDGE = re.compile(r"\b[a-z]{2,}\(s\)(?= [a-z]|\.(?:\s|$|\"|<))")


def test_count_writes_small_numbers_in_words_and_the_right_plural() -> None:
    assert count(1, "source") == "one source"
    assert count(4, "source") == "four sources"
    assert count(12, "source") == "12 sources"
    assert count(0, "item") == "no items"
    assert count(2, "body", "bodies") == "two bodies"
    assert number(0) == "none" and number(7) == "seven" and number(10) == "10"


def test_clauses_are_joined_with_commas_and_a_final_and() -> None:
    assert join_clauses(["a", "", "b", "c"]) == "a, b and c"
    assert join_clauses(["", "a", ""]) == "a"
    assert join_clauses(["a", "b"]) == "a and b"
    assert join_clauses([]) == ""


def test_dates_read_as_prose() -> None:
    day = dt.date
    assert long_date(day(2026, 11, 15)) == "15 November 2026"
    assert date_range(day(2026, 10, 20), day(2026, 10, 26)) == "20 to 26 October"
    assert date_range(day(2026, 9, 28), day(2026, 10, 4)) == "28 September to 4 October"
    assert date_range(day(2026, 12, 28), day(2027, 1, 3)) == "28 December 2026 to 3 January 2027"
    assert date_range(day(2026, 10, 19), day(2026, 10, 19)) == "19 October 2026"
    assert prose_date("2026-11-15") == "15 November 2026" and prose_date("soon") == "soon"


@pytest.mark.parametrize(
    ("status", "detail", "phrase"),
    [
        ("NEW", "", "first snapshot taken"),
        ("CHANGED", "", "content changed"),
        ("MISSING", "no snapshot; capture one", "no snapshot yet"),
        ("ERROR", "HTTP status 500", "could not be read (HTTP status 500)"),
        ("ERROR", "", "could not be read"),
        ("SUSPICIOUS", "signal is empty", "looks wrong (signal is empty)"),
    ],
)
def test_a_source_status_reads_as_words(status: str, detail: str, phrase: str) -> None:
    assert status_phrase(status, detail) == phrase


def test_severities_and_providers_have_display_names() -> None:
    assert severity_label("act-now") == "act now" and severity_label("info") == "information"
    assert [provider_name(p) for p in ("anthropic", "openai", "ollama")] == [
        "Anthropic",
        "OpenAI",
        "Ollama",
    ]


def test_the_opening_names_only_what_the_period_holds(project: Path) -> None:
    register = load_register(load_config(project))
    changed = SourceResult("nl-notices", "CHANGED", "snapshot", "a" * 64)
    content = newsletter_content(register, [changed], [], [], TODAY, 7)
    doc = build_newsletter(register, content, DocumentDesign())
    opening = doc.sections[0].paragraphs[0]
    assert opening == "From 13 to 19 October: one source change to look at."
    assert "unconfirmed" not in opening and "0" not in opening
    assert doc.sections[1].bullets[0] == "Northland regulator notices feed: content changed"
    assert doc.sections[1].paragraphs == ["In this period one source changed."]
    empty = newsletter_content(register, [], [], [], TODAY, 7)
    quiet = build_newsletter(register, empty, DocumentDesign()).sections[0].paragraphs[0]
    assert quiet == "Nothing changed and nothing new was found from 13 to 19 October."


def test_impacts_name_the_jurisdiction_and_the_severity(project: Path) -> None:
    config = load_config(project)
    register = load_register(config)
    impact = Impact("p", "Bar", "o", "Labels", "nl", "enacted", "2026-11-15", (), "act-now")
    content = newsletter_content(register, [], [impact], [], TODAY, 7)
    section = build_newsletter(register, content, DocumentDesign()).sections[-1]
    assert section.bullets == [
        "Bar: Labels (Northland, act now severity, effective 15 November 2026)"
    ]
    assert section.paragraphs == [
        "One candidate impact of act now or high severity; it needs a person to confirm it."
    ]


def test_a_candidate_with_empty_fields_has_no_stray_separators() -> None:
    facts = candidate_facts([{"headline": "Fee notice"}, {"agency": "FDA"}, {}])
    assert [f.text for f in facts] == [
        "Unconfirmed: Fee notice.",
        "Unconfirmed, FDA.",
        "Unconfirmed.",
    ]
    assert _candidate_line({"headline": "Fee notice"}) == "Fee notice"
    assert _candidate_line({"date": "2026-10-15", "agency": "FDA"}) == "15 October 2026, FDA"


def test_the_date_line_is_left_out_when_the_title_or_subtitle_says_it() -> None:
    assert Document("Brief", "2026-10-19").date_line == "Prepared 19 October 2026."
    assert Document("Brief (2026-10-19)", "2026-10-19").date_line == ""
    assert Document("News", "2026-10-19", subtitle="13 to 19 October").date_line == ""


def test_no_rendered_output_says_s_in_brackets(project: Path, tmp_path: Path) -> None:
    set_premium(project, True)
    out = tmp_path / "out"
    assert (
        main(
            ["--config", str(project), "newsletter", "--out", str(out / "n")], today=TODAY, now=NOW
        )
        == 0
    )
    for kind in ("briefing", "digest", "report"):
        for fmt in ("html", "md"):
            args = ["--config", str(project), "document", "--kind", kind, "--format", fmt]
            assert main([*args, "--out", str(out / kind)], today=TODAY, now=NOW) == 0
    for command in (["brief", "--kind", "daily"], ["brief", "--kind", "weekly"], ["report"]):
        assert (
            main(
                ["--config", str(project), *command, "--out", str(out / command[-1])],
                today=TODAY,
                now=NOW,
            )
            == 0
        )
    written = [p for p in out.iterdir() if p.suffix in (".html", ".md", ".txt", ".eml")]
    assert len(written) >= 9
    for path in written:
        assert "(s)" not in path.read_text(encoding="utf-8", errors="replace"), path.name
    for path in WEB_EXPORT.rglob("*"):
        if path.suffix in (".html", ".txt", ".js"):
            hits = PLURAL_HEDGE.findall(path.read_text(encoding="utf-8", errors="replace"))
            assert hits == [], f"{path.name}: {hits}"


# --- C11: Word prints the design footer once, in the page footer -----------------------


def test_word_writes_the_design_footer_only_in_the_page_footer() -> None:
    doc = Document("Briefing", "2026-10-19", sections=[Section("Changes", paragraphs=["x"])])
    footer = "Pantry Co, 1 Example Road"
    with zipfile.ZipFile(io.BytesIO(docx_bytes(doc, DocumentDesign(footer=footer)))) as archive:
        body = archive.read("word/document.xml").decode()
        page_footer = archive.read("word/footer1.xml").decode()
    assert footer not in body and page_footer.count(footer) == 1
    assert '<w:footerReference w:type="default" r:id="rIdFooter"/>' in body


def test_a_get_error_keeps_its_status_but_reads_no_body() -> None:
    network = web(b"HTTP/1.1 503 Busy\r\nContent-Length: 4\r\n\r\nbusy")
    with pytest.raises(FetchError) as caught:
        make(network).fetch("https://example.org/")
    assert caught.value.status == 503 and caught.value.body == ""
