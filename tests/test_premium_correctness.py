"""Correctness of the premium content: generated copy calls, the newsletter period and
email, the documents and the web app's handling of generated copy.

Every test here fails without the fix it names. The language model is a fake poster and
the keychain a FakeSystem, so nothing leaves the machine.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import pytest
from conftest import TODAY
from test_llm import FACTS, KEY, FakePoster, FakeProvider, answer

from regwatch.config import load_config
from regwatch.llm import (
    OLLAMA_CONTEXT,
    AnthropicProvider,
    GenerationError,
    OllamaProvider,
    OpenAIProvider,
    generate,
)
from regwatch.newsletter import newsletter_content
from regwatch.register import load_register

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
