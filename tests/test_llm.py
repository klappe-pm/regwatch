"""Generated copy: provider calls, the facts, the parsing of answers and what is recorded.

Every provider talks to a fake poster, so no test reaches a network or a real model.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from conftest import NOW, TODAY, FakeSystem

from regwatch.check import SourceResult
from regwatch.cli import main
from regwatch.config import Config, LlmSettings, load_config
from regwatch.fetch import Credential, FetchError
from regwatch.impact import Impact
from regwatch.llm import (
    ENDPOINTS,
    KEY_IDS,
    LLM_KEYS,
    SYSTEM_PROMPT,
    AnthropicProvider,
    Completion,
    Fact,
    GenerationError,
    OllamaProvider,
    OpenAIProvider,
    build_prompt,
    candidate_facts,
    change_facts,
    event_facts,
    generate,
    impact_facts,
    llm_fetcher,
    obligation_facts,
    parse_passages,
    provider_for,
)
from regwatch.register import Register
from regwatch.state import append_call_record

KEY = "fake" + "-model-" + "key-3391"


class FakePoster:
    """Records each POST and answers with a fixed body, or raises a given error."""

    def __init__(self, answer: str | Exception = "{}") -> None:
        self.answer = answer
        self.calls: list[dict[str, Any]] = []

    def post_json(
        self,
        url: str,
        payload: Mapping[str, object],
        *,
        credential: Credential | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> str:
        self.calls.append(
            {"url": url, "payload": payload, "credential": credential, "headers": headers}
        )
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


class FakeProvider:
    name = "fake"
    model = "fake-model-1"

    def __init__(self, text: str | Exception, tokens: tuple[int, int] = (120, 40)) -> None:
        self.text = text
        self.tokens = tokens
        self.prompts: list[tuple[str, str, int]] = []

    def complete(self, system: str, prompt: str, max_tokens: int) -> Completion:
        self.prompts.append((system, prompt, max_tokens))
        if isinstance(self.text, Exception):
            raise self.text
        return Completion(self.text, *self.tokens)


FACTS = [
    Fact("change:us-fda-news", "changes", "FDA news is changed"),
    Fact("impact:bar/us-sodium", "impacts", "Bar may be affected by sodium labels"),
]


def answer(*passages: dict[str, Any]) -> str:
    return json.dumps({"passages": list(passages)})


# --- providers ---------------------------------------------------------------------


def test_anthropic_sends_the_messages_request_with_the_key_in_its_header() -> None:
    poster = FakePoster(
        json.dumps(
            {
                "content": [
                    {"type": "thinking", "thinking": ""},
                    {"type": "text", "text": "Hello "},
                    {"type": "text", "text": "there"},
                ],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 11, "output_tokens": 7},
            }
        )
    )
    completion = AnthropicProvider(poster, KEY, "claude-opus-5-5").complete("S", "P", 900)
    assert completion == Completion("Hello there", 11, 7)
    call = poster.calls[0]
    assert call["url"] == ENDPOINTS["anthropic"] == "https://api.anthropic.com/v1/messages"
    assert call["credential"] == Credential("header", "x-api-key", KEY)
    assert call["headers"]["anthropic-version"] == "2023-06-01"
    payload = call["payload"]
    assert payload["model"] == "claude-opus-5-5" and payload["max_tokens"] == 900
    assert payload["system"] == "S" and payload["messages"] == [{"role": "user", "content": "P"}]
    assert KEY not in json.dumps(payload)


def test_an_anthropic_refusal_is_an_error() -> None:
    poster = FakePoster(json.dumps({"stop_reason": "refusal", "content": []}))
    with pytest.raises(GenerationError, match="declined"):
        AnthropicProvider(poster, KEY, "m").complete("S", "P", 10)


def test_openai_sends_a_bearer_key_and_reads_the_choice() -> None:
    poster = FakePoster(
        json.dumps(
            {
                "choices": [{"message": {"content": "Hi"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2},
            }
        )
    )
    assert OpenAIProvider(poster, KEY, "gpt-x").complete("S", "P", 50) == Completion("Hi", 5, 2)
    call = poster.calls[0]
    assert call["url"] == "https://api.openai.com/v1/chat/completions"
    assert call["credential"].header_value == f"Bearer {KEY}"
    assert call["payload"]["messages"][0] == {"role": "system", "content": "S"}
    refused = FakePoster(json.dumps({"choices": [{"message": {"refusal": "no"}}]}))
    with pytest.raises(GenerationError, match="declined"):
        OpenAIProvider(refused, KEY, "gpt-x").complete("S", "P", 50)


def test_ollama_runs_on_loopback_without_a_key() -> None:
    poster = FakePoster(
        json.dumps({"message": {"content": "Local"}, "prompt_eval_count": 3, "eval_count": 1})
    )
    assert OllamaProvider(poster, "llama3.2").complete("S", "P", 10) == Completion("Local", 3, 1)
    call = poster.calls[0]
    assert call["url"] == "http://127.0.0.1:11434/api/chat" and call["credential"] is None
    assert call["payload"]["stream"] is False


@pytest.mark.parametrize("body", ["not json", "[1]", json.dumps({"content": "x"})])
def test_an_odd_answer_is_an_error_or_empty_text(body: str) -> None:
    provider = AnthropicProvider(FakePoster(body), KEY, "m")
    if body == "not json" or body == "[1]":
        with pytest.raises(GenerationError):
            provider.complete("S", "P", 10)
    else:
        assert provider.complete("S", "P", 10) == Completion("", 0, 0)


def test_a_provider_that_needs_a_key_without_one_names_the_command() -> None:
    settings = LlmSettings(enabled=True, provider="anthropic")
    with pytest.raises(GenerationError) as caught:
        provider_for(settings, FakePoster(), lambda name: None)
    assert "regwatch keys set llm-anthropic" in str(caught.value)
    assert "REGWATCH_KEY_ANTHROPIC" in str(caught.value)


def test_the_provider_gets_its_key_by_its_fixed_name() -> None:
    asked: list[str] = []

    def key_for(name: str) -> str:
        asked.append(name)
        return KEY

    openai = provider_for(LlmSettings(provider="openai"), FakePoster(), key_for)
    assert isinstance(openai, OpenAIProvider) and openai.model == "gpt-5-mini"
    anthropic = provider_for(LlmSettings(model="claude-x"), FakePoster(), key_for)
    assert isinstance(anthropic, AnthropicProvider) and anthropic.model == "claude-x"
    assert asked == ["REGWATCH_KEY_OPENAI", "REGWATCH_KEY_ANTHROPIC"]
    ollama = provider_for(LlmSettings(provider="ollama"), FakePoster(), key_for)
    assert isinstance(ollama, OllamaProvider) and len(asked) == 2
    assert LLM_KEYS == {"anthropic": "REGWATCH_KEY_ANTHROPIC", "openai": "REGWATCH_KEY_OPENAI"}
    assert set(KEY_IDS) == {"llm-anthropic", "llm-openai"}


def test_an_unsendable_stored_key_is_an_error_without_the_key() -> None:
    with pytest.raises(GenerationError) as caught:
        provider_for(LlmSettings(), FakePoster(), lambda name: "has space")
    assert "has space" not in str(caught.value)


def test_the_llm_fetcher_uses_the_llm_deadline_and_the_fetch_limits(config: Config) -> None:
    fetcher = llm_fetcher(config)
    assert fetcher.total_timeout_seconds == config.llm.timeout_seconds == 180.0
    assert fetcher.max_bytes == config.fetch.max_bytes
    assert fetcher.allow_private_hosts is False and fetcher.allowed_file_roots == ()


# --- facts and prompt -------------------------------------------------------------


def test_facts_carry_ids_and_clean_text(register: Register) -> None:
    results = [
        SourceResult("us-fda-news", "CHANGED", "snapshot", "a" * 64),
        SourceResult("quiet", "UNCHANGED", "snapshot", "b" * 64),
        SourceResult("broken", "ERROR", "fetch", None, detail="HTTP status 500"),
    ]
    changes = change_facts(results, {"us-fda-news": "FDA news"})
    assert [f.fact_id for f in changes] == ["change:us-fda-news", "change:broken"]
    assert changes[0].text == "FDA news is changed"
    assert "HTTP status 500" in changes[1].text
    candidates = candidate_facts([{"headline": "Rule\x1b[2J one", "date": "2026-10-01"}, {}])
    assert [f.fact_id for f in candidates] == ["candidate:1", "candidate:2"]
    assert "\x1b" not in candidates[0].text and candidates[0].text.startswith("Unconfirmed")
    impact = Impact("p 1", "Bar", "o:2", "Labels", "us", "proposed", "2027-01-01", (), "high")
    assert impact_facts([impact])[0].fact_id == "impact:p-1/o-2"
    assert "effective 2027-01-01" in impact_facts([impact])[0].text
    obligations = obligation_facts(register.obligations[:2])
    assert all(f.fact_id.startswith("obligation:") for f in obligations)
    events = event_facts(register.changelog[:1])
    assert events and events[0].fact_id.endswith("-1") and events[0].section == "changes"
    assert len(Fact("x:y", "changes", "t").line) == len("x:y: t")


def test_the_prompt_holds_only_the_facts_and_the_rules() -> None:
    prompt = build_prompt("a newsletter", FACTS)
    facts = json.loads(prompt[prompt.index("[") :])
    assert facts[0] == {
        "id": "change:us-fda-news",
        "section": "changes",
        "text": "FDA news is changed",
    }
    assert "Use only the facts you are given" in SYSTEM_PROMPT
    assert "cite" in SYSTEM_PROMPT and "legal advice" in SYSTEM_PROMPT


# --- parsing answers -----------------------------------------------------------------


def test_a_passage_citing_given_facts_is_kept_with_those_facts() -> None:
    text = "Here it is: " + answer(
        {"section": "opening", "text": "Two things moved.", "cites": FACTS_IDS()},
        {"section": "impacts", "text": "Bar\x07 is affected.", "cites": ["impact:bar/us-sodium"]},
    )
    result = parse_passages(text, FACTS, "fake", "m")
    opening = result.section("opening")[0]
    assert opening.text == "Two things moved." and opening.cites == FACTS_IDS()
    assert opening.facts == [f.line for f in FACTS]
    assert (opening.provider, opening.model) == ("fake", "m")
    assert result.section("impacts")[0].text == "Bar is affected."
    assert result.count == 2 and result.dropped == [] and result.section("changes") == []


def FACTS_IDS() -> list[str]:
    return [f.fact_id for f in FACTS]


def test_a_passage_citing_an_unknown_id_is_dropped_and_reported() -> None:
    text = answer(
        {"section": "opening", "text": "Invented.", "cites": ["change:made-up"]},
        {"section": "opening", "text": "Mixed.", "cites": ["change:us-fda-news", "event:x"]},
        {"section": "changes", "text": "Real.", "cites": ["change:us-fda-news"]},
    )
    result = parse_passages(text, FACTS)
    assert [p.text for p in result.section("changes")] == ["Real."]
    assert result.section("opening") == []
    assert len(result.dropped) == 2
    assert "change:made-up" in result.dropped[0] and "not one of the facts" in result.dropped[0]


@pytest.mark.parametrize(
    ("item", "reason"),
    [
        ({"section": "opening", "text": "No cites."}, "cites no fact"),
        ({"section": "opening", "text": "Empty.", "cites": []}, "cites no fact"),
        ({"section": "opening", "text": "Bad.", "cites": [3]}, "cites no fact"),
        ({"section": "elsewhere", "text": "x", "cites": ["change:us-fda-news"]}, "section"),
        ({"section": "opening", "text": "  ", "cites": ["change:us-fda-news"]}, "no text"),
        ("just a string", "not an object"),
    ],
)
def test_malformed_passages_are_dropped_with_a_reason(item: object, reason: str) -> None:
    result = parse_passages(json.dumps({"passages": [item]}), FACTS)
    assert result.count == 0 and reason in result.dropped[0]


@pytest.mark.parametrize("text", ["no object here", "{not json}", '{"passages": "x"}'])
def test_an_unreadable_answer_is_an_error(text: str) -> None:
    with pytest.raises(GenerationError, match="nothing was generated"):
        parse_passages(text, FACTS)


def test_passages_beyond_the_limit_are_dropped() -> None:
    item = {"section": "changes", "text": "x", "cites": ["change:us-fda-news"]}
    result = parse_passages(json.dumps({"passages": [item] * 25}), FACTS)
    assert result.count == 20 and "more than 20" in result.dropped[0]


# --- generate and the call record ----------------------------------------------------


def test_generate_records_only_the_provider_model_tokens_and_duration() -> None:
    records: list[dict[str, object]] = []
    clock = iter([10.0, 10.25])
    provider = FakeProvider(answer({"section": "opening", "text": "Ok.", "cites": FACTS_IDS()}))
    result = generate(
        provider,
        FACTS,
        "a newsletter",
        max_tokens=500,
        record=records.append,
        now=lambda: NOW,
        timer=lambda: next(clock),
    )
    assert result.count == 1 and provider.prompts[0][2] == 500
    assert records == [
        {
            "time": "2026-10-19T12:00:00+00:00",
            "provider": "fake",
            "model": "fake-model-1",
            "input_tokens": 120,
            "output_tokens": 40,
            "outcome": "ok",
            "kept": 1,
            "dropped": 0,
            "duration_ms": 250,
        }
    ]
    assert "FDA" not in json.dumps(records)


def test_a_failed_call_is_recorded_and_reported_without_the_key() -> None:
    records: list[dict[str, object]] = []
    credential = Credential("header", "x-api-key", KEY)
    provider = FakeProvider(FetchError(f"HTTP status 401 {KEY}", redact=credential.redact))
    with pytest.raises(GenerationError) as caught:
        generate(provider, FACTS, "x", max_tokens=10, record=records.append)
    assert KEY not in str(caught.value) and "fake request failed" in str(caught.value)
    assert records[0]["outcome"] == "error" and KEY not in json.dumps(records)
    refusing = FakeProvider(GenerationError("declined"))
    with pytest.raises(GenerationError):
        generate(refusing, FACTS, "x", max_tokens=10, record=records.append)
    unreadable = FakeProvider("no json at all")
    with pytest.raises(GenerationError):
        generate(unreadable, FACTS, "x", max_tokens=10, record=records.append)
    assert [r["outcome"] for r in records] == ["error", "refused", "unreadable"]


def test_generate_needs_facts() -> None:
    with pytest.raises(GenerationError, match="no facts"):
        generate(FakeProvider("{}"), [], "x", max_tokens=10)


def test_the_call_log_keeps_the_newest_lines_and_drops_hand_edits(tmp_path: Path) -> None:
    path = tmp_path / "llm-calls.jsonl"
    path.write_text("not json\n[1]\n", encoding="utf-8")
    for number in range(5):
        append_call_record(path, {"n": number}, [], keep=3)
    assert [json.loads(line)["n"] for line in path.read_text().splitlines()] == [2, 3, 4]


# --- configuration and the command ---------------------------------------------------


def write_config(project: Path, extra: str) -> None:
    project.write_text(project.read_text(encoding="utf-8") + extra, encoding="utf-8")


@pytest.mark.parametrize(
    ("table", "message"),
    [
        ('[llm]\nenabled = "yes"\n', "enabled must be true or false"),
        ('[llm]\nprovider = "other"\n', "provider must be one of"),
        ('[llm]\nmodel = "bad model"\n', "model must be"),
        ("[llm]\nmax_tokens = 10\n", "max_tokens must be an integer"),
        ("[llm]\ntimeout_seconds = 0\n", "timeout_seconds must be"),
        ('[llm]\nkey = "x"\n', "unknown keys"),
    ],
)
def test_bad_llm_settings_are_refused(project: Path, table: str, message: str) -> None:
    from regwatch.config import ConfigError

    write_config(project, "\n" + table)
    with pytest.raises(ConfigError, match=message):
        load_config(project)


def test_the_llm_is_off_by_default(config: Config) -> None:
    assert config.llm == LlmSettings()
    assert config.llm.enabled is False and config.llm.effective_model == "claude-opus-5-5"
    assert config.llm_calls_path == config.state_dir / "llm-calls.jsonl"


def run(
    project: Path, capsys: pytest.CaptureFixture[str], *args: str, fake: FakeSystem | None = None
) -> tuple[int, str, str]:
    code = main(
        ["--config", str(project), *args],
        today=TODAY,
        now=NOW,
        system=(fake or FakeSystem("linux")).system(),
    )
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_changing_the_llm_needs_premium(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    for args in (("llm", "on"), ("llm", "off"), ("llm", "use", "openai")):
        code, _out, err = run(project, capsys, *args)
        assert code == 2 and "regwatch premium on" in err and "premium feature" in err
    assert load_config(project).llm == LlmSettings()
    code, out, _err = run(project, capsys, "llm", "status")
    assert code == 0 and "regwatch llm: off, anthropic, claude-opus-5-5" in out
    assert "regwatch premium on" in out


def test_the_llm_command_sets_the_provider_model_and_switch(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run(project, capsys, "premium", "on")
    code, out, _err = run(project, capsys, "llm", "use", "openai", "--model", "gpt-test")
    assert code == 0 and "openai, gpt-test" in out
    assert "regwatch keys set llm-openai" in out
    code, out, _err = run(project, capsys, "llm", "on")
    assert code == 0 and "regwatch llm: on" in out
    settings = load_config(project).llm
    assert (settings.enabled, settings.provider, settings.model) == (True, "openai", "gpt-test")
    code, out, _err = run(project, capsys, "llm", "use", "ollama")
    assert "allow_private_hosts" in out and load_config(project).llm.model == ""
    code, _out, err = run(project, capsys, "llm", "use")
    assert code == 2 and "name a provider" in err
    code, out, _err = run(project, capsys, "config", "show")
    assert "[llm]" in out and 'provider = "ollama"' in out


def test_a_provider_key_is_kept_like_a_source_key(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeSystem("linux")
    fake.secret = KEY
    code, out, _err = run(project, capsys, "keys", "set", "llm-anthropic", fake=fake)
    assert code == 0 and fake.keychain == {"REGWATCH_KEY_ANTHROPIC": KEY}
    assert "console.anthropic.com" in out and KEY not in out
    assert all(KEY not in " ".join(call) for call in fake.calls)
    run(project, capsys, "premium", "on")
    code, out, _err = run(project, capsys, "llm", "status", fake=fake)
    assert "REGWATCH_KEY_ANTHROPIC: keychain" in out
    code, out, _err = run(project, capsys, "keys", "remove", "llm-anthropic", fake=fake)
    assert code == 0 and fake.keychain == {}


def test_the_timestamp_is_utc_iso(config: Config) -> None:
    records: list[dict[str, object]] = []
    later = dt.datetime(2026, 10, 20, 8, 30, tzinfo=dt.UTC)
    generate(
        FakeProvider(answer({"section": "opening", "text": "x", "cites": FACTS_IDS()})),
        FACTS,
        "x",
        max_tokens=10,
        record=records.append,
        now=lambda: later,
    )
    assert records[0]["time"] == "2026-10-20T08:30:00+00:00"
