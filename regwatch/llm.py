"""Generated copy: a language model writes short summaries from structured facts.

This is the optional stage the design decisions describe. It is off until the user
turns on premium features and ``[llm] enabled``, and names a provider. It keeps
these rules:

- the model is given only structured facts (changes, candidates, impacts and
  obligations), each with an id, and is told to use only those facts and to cite
  their ids;
- the answer is parsed as JSON, and a passage that cites an id it was not given, or
  cites none, is dropped and reported; every kept passage is cleaned like any other
  outside text and later escaped by the renderer;
- every passage is kept with the facts it cites, so the output shows each one next
  to what it was written from, under a plain "Generated" label;
- the provider key is read through ``regwatch.keys`` (the environment variable first,
  then the keychain) under a fixed name, sent only over https in the header the
  provider names, and never logged; the request goes through the one fetch client,
  so its address checks, size limit and deadline apply;
- each call is recorded in the state directory with the provider, the model, the
  token counts, the duration and the outcome, never a key and never a prompt.

The provider is pluggable: Anthropic by default, OpenAI, or a local Ollama model on
``127.0.0.1``, which needs ``allow_private_hosts`` because it is this machine.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from regwatch.check import SourceResult
from regwatch.config import Config, LlmSettings
from regwatch.document import GeneratedPassage
from regwatch.fetch import Credential, FetchError, SafeFetcher
from regwatch.impact import Impact
from regwatch.keys import PROVIDER_KEYS
from regwatch.register import ChangeEvent, Obligation
from regwatch.sanitize import clean_text

__all__ = [
    "ENDPOINTS",
    "KEY_IDS",
    "LLM_KEYS",
    "SECTIONS",
    "AnthropicProvider",
    "Completion",
    "Fact",
    "GenerationError",
    "GenerationResult",
    "OllamaProvider",
    "OpenAIProvider",
    "Poster",
    "Provider",
    "build_prompt",
    "candidate_facts",
    "change_facts",
    "event_facts",
    "generate",
    "impact_facts",
    "llm_fetcher",
    "obligation_facts",
    "parse_passages",
    "provider_for",
]

KEY_IDS = {"llm-anthropic": "anthropic", "llm-openai": "openai"}
"""The ids ``regwatch keys`` and the web app's key routes use for the provider keys."""
LLM_KEYS = {provider: PROVIDER_KEYS[key_id][0] for key_id, provider in KEY_IDS.items()}
"""The fixed key variable of each provider that needs a key. Ollama needs none."""
ENDPOINTS = {
    "anthropic": "https://api.anthropic.com/v1/messages",
    "openai": "https://api.openai.com/v1/chat/completions",
    "ollama": "http://127.0.0.1:11434/api/chat",
}
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_FALLBACK_BETA = "server-side-fallback-2026-07-01"
SECTIONS = ("opening", "changes", "candidates", "impacts", "obligations")
MAX_FACTS = 200
MAX_FACT_CHARACTERS = 400
MAX_PASSAGES = 20
MAX_PASSAGE_CHARACTERS = 1200
MAX_CITES = 20
FACT_ID_RE = re.compile(r"^[a-z]+:[A-Za-z0-9._/-]{1,120}$")

SYSTEM_PROMPT = (
    "You write short, plain copy for a regulatory monitoring newsletter or document. "
    "Use only the facts you are given. Do not add any fact, date, number, name, place or claim "
    "that is not in them, and do not guess. Do not give legal advice. Every passage must cite, "
    "in its cites list, the ids of the facts it draws on, exactly as they are written. "
    "Write plain sentences with no markup, links, headings or lists. "
    "Answer with one JSON object and nothing else, in this form: "
    '{"passages": [{"section": "opening", "text": "One to three sentences.", '
    '"cites": ["change:example-id"]}]}. '
    "The section is one of opening, changes, candidates, impacts or obligations. Write one passage "
    "for the opening and at most one for each other section that has facts."
)


class GenerationError(Exception):
    """Generated copy could not be written. The message holds no key and no prompt."""


@dataclass(frozen=True)
class Fact:
    """One structured fact a passage may be written from: an id, its section and its text."""

    fact_id: str
    section: str
    text: str

    @property
    def line(self) -> str:
        """The fact as a passage keeps it: ``id: text``."""
        return f"{self.fact_id}: {self.text}"


@dataclass(frozen=True)
class Completion:
    """What a provider answered: the text and the token counts it reported."""

    text: str
    input_tokens: int = 0
    output_tokens: int = 0


class Poster(Protocol):
    """Anything that can POST a JSON body: ``SafeFetcher`` or a test fake."""

    def post_json(
        self,
        url: str,
        payload: Mapping[str, object],
        *,
        credential: Credential | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> str:
        """Send ``payload`` and return the response body, or raise FetchError."""
        ...


class Provider(Protocol):
    """A language model behind one API."""

    name: str
    model: str

    def complete(self, system: str, prompt: str, max_tokens: int) -> Completion:
        """Answer ``prompt`` under ``system``, or raise GenerationError or FetchError."""
        ...


def _json(body: str, provider: str) -> dict[str, Any]:
    try:
        data = json.loads(body)
    except (ValueError, RecursionError) as exc:
        raise GenerationError(f"the {provider} answer was not JSON") from exc
    if not isinstance(data, dict):
        raise GenerationError(f"the {provider} answer was not a JSON object")
    return data


def _object(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _count(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


class AnthropicProvider:
    """The Anthropic Messages API, with the key in the ``x-api-key`` header.

    The request opts in to the server side fallback, so a request the model declines
    is answered by another model where the API can, and a final refusal is reported.
    """

    name = "anthropic"

    def __init__(self, poster: Poster, key: str, model: str) -> None:
        self.poster = poster
        self.credential = Credential("header", "x-api-key", key)
        self.model = model

    def complete(self, system: str, prompt: str, max_tokens: int) -> Completion:
        body = self.poster.post_json(
            ENDPOINTS["anthropic"],
            {
                "model": self.model,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
                "output_config": {"effort": "low"},
                "fallbacks": "default",
            },
            credential=self.credential,
            headers={
                "anthropic-version": ANTHROPIC_VERSION,
                "anthropic-beta": ANTHROPIC_FALLBACK_BETA,
            },
        )
        data = _json(body, self.name)
        if data.get("stop_reason") == "refusal":
            raise GenerationError("the anthropic model declined to write this copy")
        content = data.get("content")
        blocks = content if isinstance(content, list) else []
        text = "".join(
            str(block.get("text", ""))
            for block in blocks
            if isinstance(block, dict) and block.get("type") == "text"
        )
        usage = _object(data.get("usage"))
        return Completion(
            text, _count(usage.get("input_tokens")), _count(usage.get("output_tokens"))
        )


class OpenAIProvider:
    """The OpenAI Chat Completions API, with the key as a bearer token."""

    name = "openai"

    def __init__(self, poster: Poster, key: str, model: str) -> None:
        self.poster = poster
        self.credential = Credential("header", "Authorization", key, scheme="Bearer")
        self.model = model

    def complete(self, system: str, prompt: str, max_tokens: int) -> Completion:
        body = self.poster.post_json(
            ENDPOINTS["openai"],
            {
                "model": self.model,
                "max_completion_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
            credential=self.credential,
        )
        data = _json(body, self.name)
        choices = data.get("choices")
        first = choices[0] if isinstance(choices, list) and choices else {}
        message = first.get("message") if isinstance(first, dict) else None
        text = message.get("content") if isinstance(message, dict) else None
        if isinstance(message, dict) and message.get("refusal"):
            raise GenerationError("the openai model declined to write this copy")
        usage = _object(data.get("usage"))
        return Completion(
            text if isinstance(text, str) else "",
            _count(usage.get("prompt_tokens")),
            _count(usage.get("completion_tokens")),
        )


class OllamaProvider:
    """A local Ollama model on ``127.0.0.1``. It needs no key, and plain http stays on loopback."""

    name = "ollama"

    def __init__(self, poster: Poster, model: str) -> None:
        self.poster = poster
        self.model = model

    def complete(self, system: str, prompt: str, max_tokens: int) -> Completion:
        body = self.poster.post_json(
            ENDPOINTS["ollama"],
            {
                "model": self.model,
                "stream": False,
                "options": {"num_predict": max_tokens},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        data = _json(body, self.name)
        message = data.get("message")
        text = message.get("content") if isinstance(message, dict) else None
        return Completion(
            text if isinstance(text, str) else "",
            _count(data.get("prompt_eval_count")),
            _count(data.get("eval_count")),
        )


def llm_fetcher(config: Config) -> SafeFetcher:
    """The fetch client for a generated copy call: the fetch settings with the ``[llm]`` deadline.

    A model can take a while to answer, so the per-operation timeout and the total
    deadline are both ``[llm] timeout_seconds``; the size limit, the address checks
    and ``allow_private_hosts`` are the ones every fetch uses.
    """
    settings = config.fetch
    return SafeFetcher(
        config.llm.timeout_seconds,
        settings.max_bytes,
        settings.user_agent,
        total_timeout_seconds=config.llm.timeout_seconds,
        allow_private_hosts=settings.allow_private_hosts,
    )


def provider_for(
    settings: LlmSettings, poster: Poster, key_for: Callable[[str], str | None]
) -> Provider:
    """The provider ``[llm]`` names, with its key from ``key_for``.

    Raises GenerationError when a provider that needs a key has none, naming the
    command and the variable that supply one.
    """
    model = settings.effective_model
    if settings.provider == "ollama":
        return OllamaProvider(poster, model)
    key_env = LLM_KEYS[settings.provider]
    key = key_for(key_env)
    if not key:
        raise GenerationError(
            f"no {settings.provider} key is stored; run "
            f"'regwatch keys set llm-{settings.provider}' or set the environment variable {key_env}"
        )
    try:
        if settings.provider == "openai":
            return OpenAIProvider(poster, key, model)
        return AnthropicProvider(poster, key, model)
    except ValueError as exc:
        raise GenerationError(
            f"the stored {settings.provider} key cannot be sent; store it again"
        ) from exc


# --- facts ---------------------------------------------------------------------


def _fact(fact_id: str, section: str, text: str) -> Fact:
    return Fact(fact_id, section, clean_text(text, MAX_FACT_CHARACTERS))


def _id_part(value: str) -> str:
    """``value`` made safe for a fact id: letters, digits and . _ / - only."""
    return re.sub(r"[^A-Za-z0-9._/-]+", "-", value).strip("-")[:60] or "item"


def change_facts(results: Iterable[SourceResult], names: Mapping[str, str]) -> list[Fact]:
    """One fact per source that changed or needs attention."""
    return [
        _fact(
            f"change:{_id_part(r.source_id)}",
            "changes",
            f"{names.get(r.source_id, r.source_id)} is {r.status.lower()}"
            + (f" ({r.detail})" if r.detail else ""),
        )
        for r in results
        if r.flagged or r.needs_attention
    ]


def event_facts(events: Iterable[ChangeEvent]) -> list[Fact]:
    """One fact per recorded change log event."""
    return [
        _fact(
            f"event:{_id_part(e.date)}-{index}",
            "changes",
            f"{e.date}, {e.jurisdiction}: {e.headline}. {e.what_happened}",
        )
        for index, e in enumerate(events, start=1)
    ]


def candidate_facts(candidates: Iterable[Mapping[str, Any]]) -> list[Fact]:
    """One fact per unconfirmed ingest candidate. The candidates file is untrusted."""
    facts = []
    for index, candidate in enumerate(candidates, start=1):

        def text(key: str, item: Mapping[str, Any] = candidate) -> str:
            value = item.get(key)
            return clean_text(value, 300) if isinstance(value, str) else ""

        facts.append(
            _fact(
                f"candidate:{index}",
                "candidates",
                f"Unconfirmed, {text('date')}, {text('agency')}: {text('headline')}. "
                f"{text('what_happened')}",
            )
        )
    return facts


def impact_facts(impacts: Iterable[Impact]) -> list[Fact]:
    """One fact per candidate impact of an obligation on a product."""
    return [
        _fact(
            f"impact:{_id_part(i.product_id)}/{_id_part(i.obligation_id)}",
            "impacts",
            f"{i.product_name} may be affected by {i.obligation_title} ({i.jurisdiction}, "
            f"{i.status}, severity {i.severity}"
            + (f", effective {i.effective_date}" if i.effective_date else "")
            + ")",
        )
        for i in impacts
    ]


def obligation_facts(obligations: Iterable[Obligation]) -> list[Fact]:
    """One fact per obligation, for documents built from the register."""
    return [
        _fact(
            f"obligation:{_id_part(o.obligation_id)}",
            "obligations",
            f"{o.title} ({o.jurisdiction}, {o.status}"
            + (f", effective {o.effective_date}" if o.effective_date else "")
            + ")",
        )
        for o in obligations
    ]


# --- prompt and answer -----------------------------------------------------------


def build_prompt(purpose: str, facts: Sequence[Fact]) -> str:
    """The user message: what the copy is for and the facts, one per line, with their ids."""
    lines = [f"{f.fact_id} | {f.section} | {f.text}" for f in facts]
    return (
        f"Write the copy for {clean_text(purpose, 200)}.\n"
        "These are the only facts you may use, one per line as id | section | text:\n"
        + "\n".join(lines)
    )


@dataclass
class GenerationResult:
    """The passages that were kept, by section, and why any were dropped."""

    passages: dict[str, list[GeneratedPassage]] = field(default_factory=dict)
    dropped: list[str] = field(default_factory=list)
    provider: str = ""
    model: str = ""

    def section(self, name: str) -> list[GeneratedPassage]:
        """The passages for section ``name``; an empty list when there are none."""
        return list(self.passages.get(name, []))

    @property
    def count(self) -> int:
        """How many passages were kept."""
        return sum(len(items) for items in self.passages.values())


def _answer_object(text: str) -> dict[str, Any]:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise GenerationError("the answer held no JSON object; nothing was generated")
    try:
        data = json.loads(text[start : end + 1])
    except (ValueError, RecursionError) as exc:
        raise GenerationError("the answer was not valid JSON; nothing was generated") from exc
    if not isinstance(data, dict) or not isinstance(data.get("passages"), list):
        raise GenerationError("the answer had no list of passages; nothing was generated")
    return data


def parse_passages(
    text: str, facts: Sequence[Fact], provider: str = "", model: str = ""
) -> GenerationResult:
    """Keep the passages of a model's answer that cite only the facts it was given.

    A passage that cites an id not among ``facts``, cites nothing, has an unknown
    section or no text is dropped, and the reason is reported in ``dropped``. Kept
    text is cleaned of control and invisible characters and cut to length.
    """
    known = {f.fact_id: f for f in facts}
    result = GenerationResult(provider=provider, model=model)
    items = _answer_object(text)["passages"]
    for number, item in enumerate(items, start=1):
        if result.count >= MAX_PASSAGES:
            result.dropped.append(f"passage {number} and later: more than {MAX_PASSAGES} passages")
            break
        if not isinstance(item, dict):
            result.dropped.append(f"passage {number}: not an object")
            continue
        section = item.get("section")
        raw = item.get("text")
        body = clean_text(raw, MAX_PASSAGE_CHARACTERS) if isinstance(raw, str) else ""
        cites = item.get("cites")
        if section not in SECTIONS:
            result.dropped.append(f"passage {number}: unknown section")
            continue
        if not body:
            result.dropped.append(f"passage {number}: no text")
            continue
        if not isinstance(cites, list) or not cites or not all(isinstance(c, str) for c in cites):
            result.dropped.append(f"passage {number}: it cites no fact")
            continue
        unknown = [c for c in cites if c not in known]
        if unknown:
            shown = ", ".join(clean_text(c, 80) for c in unknown[:3])
            result.dropped.append(
                f"passage {number}: it cites {shown}, which is not one of the facts it was given"
            )
            continue
        cited = list(dict.fromkeys(cites))[:MAX_CITES]
        result.passages.setdefault(str(section), []).append(
            GeneratedPassage(
                text=body,
                cites=cited,
                facts=[known[c].line for c in cited],
                provider=provider,
                model=model,
            )
        )
    return result


def generate(
    provider: Provider,
    facts: Sequence[Fact],
    purpose: str,
    *,
    max_tokens: int,
    record: Callable[[dict[str, object]], None] | None = None,
    now: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.UTC),
    timer: Callable[[], float] = time.monotonic,
) -> GenerationResult:
    """Ask ``provider`` for copy written from ``facts`` and keep what cites them.

    ``record`` receives one dict per call with the provider, the model, the token
    counts, the duration and the outcome; never the prompt, the answer or a key.
    Raises GenerationError when there are no facts, the call fails or the answer
    cannot be read.
    """
    chosen = list(facts)[:MAX_FACTS]
    if not chosen:
        raise GenerationError("there are no facts in this period to write from")
    started = timer()
    entry: dict[str, object] = {
        "time": now().isoformat(timespec="seconds"),
        "provider": provider.name,
        "model": provider.model,
        "input_tokens": 0,
        "output_tokens": 0,
    }

    def finish(outcome: str, kept: int = 0, dropped: int = 0) -> None:
        if record is not None:
            entry.update(
                outcome=outcome,
                kept=kept,
                dropped=dropped,
                duration_ms=int((timer() - started) * 1000),
            )
            record(entry)

    try:
        completion = provider.complete(SYSTEM_PROMPT, build_prompt(purpose, chosen), max_tokens)
    except FetchError as exc:
        finish("error")
        raise GenerationError(f"the {provider.name} request failed: {exc}") from None
    except GenerationError:
        finish("refused")
        raise
    entry.update(input_tokens=completion.input_tokens, output_tokens=completion.output_tokens)
    try:
        result = parse_passages(completion.text, chosen, provider.name, provider.model)
    except GenerationError:
        finish("unreadable")
        raise
    finish("ok", result.count, len(result.dropped))
    return result
