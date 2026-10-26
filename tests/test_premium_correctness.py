"""Correctness of the premium content: generated copy calls, the newsletter period and
email, the documents and the web app's handling of generated copy.

Every test here fails without the fix it names. The language model is a fake poster and
the keychain a FakeSystem, so nothing leaves the machine.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from test_llm import FACTS, KEY, FakePoster, FakeProvider, answer

from regwatch.llm import (
    OLLAMA_CONTEXT,
    AnthropicProvider,
    GenerationError,
    OllamaProvider,
    OpenAIProvider,
    generate,
)

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
