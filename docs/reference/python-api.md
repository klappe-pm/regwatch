# Python API

This page lists every public function, class and constant in the `regwatch` package, module by module (the heading is the module name inside the `regwatch` package, for example `regwatch.config`), with its signature and what it does. The command line is a thin layer over these functions, and you can call them from your own scripts. A name is public when it appears in its module's `__all__`; everything else is internal and may change without notice. The package is typed, and `mypy --strict` passes on it.

Nothing the package produces is legal advice. Functions that produce documents always include the disclaimer.

## Package

- `__version__: str`: the package version, `"0.1.0"`.

## `config`

Reads `regwatch.toml`. See [configuration](configuration.md) for the keys.

- `DEFAULT_CONFIG_NAME: str`: `"regwatch.toml"`.
- `load_config(path: Path) -> Config`: parse and validate a configuration file. Raises `ConfigError`.
- `ConfigError`: the configuration file is missing, unreadable or invalid.
- `Config`: frozen dataclass with `base_dir`, `register`, `state_dir`, `snapshots_dir`, `fetch`, `ingest`, `config_path`, `profile`, `catalogue`, `premium` and `llm`, plus the properties `seen_path`, `candidates_path` and `llm_calls_path`. `LlmSettings` holds `enabled`, `provider`, `model`, `max_tokens` and `timeout_seconds`, and `effective_model` is the model a call names. `protected_paths()` returns the register files, the configuration file, the two state files, and the focus catalogue and the extra source catalogue when they are configured, which a user-named output must never overwrite.
- `CatalogueSettings`: frozen dataclass with `extra`, the `[catalogue]` table.
- `ProfileSettings`: frozen dataclass with `focus_areas`, `custom_terms` and `catalogue`, the `[profile]` table.
- `PremiumSettings`: frozen dataclass with `enabled`, the `[premium]` table; false unless the file turns it on.
- `RegisterPaths`: frozen dataclass of the register file paths: `obligations`, `jurisdictions`, `categories`, `sources`, `portfolio`, and the optional `detail`, `changelog`, `enforcement` and `themes`. `all_paths()` returns every configured path, resolved, for write protection.
- `FetchSettings`: frozen dataclass with `timeout_seconds`, `total_timeout_seconds`, `max_bytes`, `user_agent`, `allow_private_hosts` and `allowed_file_roots`.
- `IngestSettings`: frozen dataclass with `api_url`, `agencies`, `types`, `cfr_title`, `cfr_parts`, `terms`, `jurisdiction` and `per_page`.

## `fetch`

The one network client. See the [security model](../explanation/security-model.md).

- `ALLOWED_SCHEMES: frozenset[str]`: `{"https", "file"}`.
- `MAX_REDIRECTS: int`: 5. `CHUNK_BYTES: int`: 16384, the largest single read.
- `check_url(url: str) -> str`: return the lower-cased scheme, or raise `FetchError` for a scheme that is not allowed, a URL that contains a space or a control character, carries credentials or has an invalid port, an `https` URL with no host, or a `file` URL that names a remote host.
- `is_public_address(address: str) -> bool`: true for a globally routable unicast IP address; false for loopback, link-local, private, unique local, shared, reserved, multicast and unspecified addresses, for the IPv4-mapped form of any of them, for an IPv6 address that embeds one (NAT64 `/96`, 6to4, Teredo and ISATAP addresses are judged by the IPv4 address inside, and every embedded address must be public when there is more than one), for the ranges `::/8`, `fec0::/10` and `64:ff9b::/32` apart from its `/96`, and for text that is not an address.
- `FetchError(message="", redact=None, *, status=None, body="")`: a fetch was refused or failed. The message is cleaned when the error is created, with control characters and invisible format characters removed and a length of at most 1,000 characters, so it is safe to show. `redact`, a function such as `Credential.redact`, removes a secret before the message is cleaned and cut and again after cleaning, and from `body`. `raw` holds the message before it was cut, for rebuilding the error with a `redact` function; it is never shown. `status` is the HTTP status of an answer that was not a success, and `body` the first 16,384 bytes of the error body a POST received; `body` is not cleaned and is never shown as it is.
- `Fetcher`: a protocol with one method, `fetch(url: str, *, credential: Credential | None = None) -> str`. Implement it to supply a fake client in tests. `credential` is given only for a source that needs a key.
- `Credential(placement, name, value, scheme="")`: frozen dataclass for a key and where it goes, `query` or `header`; `scheme` is a word of letters sent before a header key, such as `Bearer`, and `header_value` is what the header carries; the value is hidden from `repr`, and an unsafe value or a reserved header name raises `ValueError` without repeating the value. `Credential.from_auth(auth, value)` builds one from a sources file `auth` value such as `query:api_key`, and `redact(text)` replaces the key in `text` with `[key]`, as written, percent-encoded, HTML-escaped and JSON-escaped.
- `SafeFetcher(timeout_seconds, max_bytes, user_agent, *, total_timeout_seconds=60.0, allow_private_hosts=False, allowed_file_roots=(), loopback_post_url=None, resolver=None, connector=None, wrapper=None)`: the real client. `fetch(url, *, credential=None)` returns the body decoded as UTF-8 with undecodable bytes replaced. With a credential the URL must be `https`, the key goes only to the host and port of the URL it was given for, a redirect to another host or port drops it, every `FetchError` is cleaned of it with its cause dropped, and the returned body has the key replaced with `[key]` wherever the server echoed it. It vets every address a host resolves to, connects to the vetted address, verifies certificates, follows at most 5 redirects only to `https`, enforces a per-operation timeout and a total deadline, reads `file` URLs only from regular files under `allowed_file_roots`, and raises `FetchError` on any failure or when the body exceeds `max_bytes`. The resolver, connector and wrapper arguments replace name resolution, the TCP connection and the TLS handshake, so tests can run without a network. `post_json(url, payload, *, credential=None, headers=None)` sends a JSON body with the same checks and limits, follows no redirect, and allows plain `http` only to a loopback IP literal with no key, and only with `allow_private_hosts` set or to exactly `loopback_post_url`, a plain `http` loopback address (anything else raises `ValueError`) that this one client may POST to without opening private addresses to every fetch.

## `extract`

Reduces untrusted content to a signal. Nothing here evaluates content.

- `extract_signal(mechanism: str, content: str) -> str`: the text that gets hashed, for the mechanisms `api`, `rss` and `html`; any other value is treated as plain text. Raises `ExtractError` for a feed that declares a DTD or entity, is not well-formed, or is not an RSS or Atom feed.
- `signal_hash(signal: str) -> str`: the SHA-256 hex digest of the signal.
- `ExtractError`: the content cannot be safely reduced to a signal.

## `register`

The data model, loading and validation. See [data files](data-files.md).

- `load_register(config: Config) -> Register`: read, validate and build the register. Raises `RegisterError` with every message in `errors`.
- `validate_register(config: Config) -> list[str]`: return every validation error, or an empty list. Raises `RegisterError` only when a file cannot be read or parsed at all.
- `load_schema() -> dict[str, Any]`: the packaged field rules from `regwatch/data/schema.json`.
- `parse_date(value: str) -> date | None`: parse an ISO date, or return `None`.
- `split_list(value: str, delimiter: str) -> list[str]`: split a delimited cell into trimmed, non-empty items.
- `ancestors(jurisdiction_id: str, parents: dict[str, str]) -> list[str]`: the parent chain, nearest first, stopping on a cycle.
- `read_json_list(path: Path, key: str, label: str) -> tuple[dict[str, Any], list[dict[str, Any]]]`: read a register JSON file and the list of objects under `key`, with the whole object so a rewrite keeps the other keys. Raises `RegisterError`.
- `obligations_citing_source(config: Config, source_id: str) -> list[str]`: the ids of obligation rows that cite a source.
- `RegisterError`: the register is unreadable, malformed or invalid; `errors` holds the messages.
- Frozen dataclasses: `Register`, `Jurisdiction`, `Category`, `Source`, `Obligation`, `Product`, `Portfolio`, `Citation`, `DetailRecord`, `ChangeEvent`, `EnforcementTheme`, `Enforcement` and `Theme`. Their fields match the columns and keys in [data files](data-files.md), with list fields as tuples.

## `catalogue`

The source catalogue. See [source catalogue](source-catalogue.md).

- `load_source_catalogue(focus_ids: Iterable[str], extra: Path | None = None) -> tuple[CatalogueEntry, ...]`: the shipped entries followed by those of the extra file. Raises `CatalogueError`.
- `parse_source_catalogue(data: object, focus_ids: Iterable[str], label: str = ...) -> tuple[CatalogueEntry, ...]`: validate a decoded catalogue file. Raises `CatalogueError` naming every invalid entry.
- `entry_from_dict(data: object, focus_ids: Iterable[str], where: str = "entry") -> CatalogueEntry`: validate and build one entry.
- `rank(entries: Sequence[CatalogueEntry], text: str) -> list[CatalogueEntry]`: the one search ranking, best match first, as the [source catalogue](source-catalogue.md#search) describes. `SEARCH_WEIGHTS` holds the field weights and `SPELLINGS` the British word starts and their American forms.
- `filter_entries(entries, *, region=None, jurisdiction=None, kind=None, category=None, access=None, focus=None, chosen=None) -> list[CatalogueEntry]`: the entries that pass every filter given. `jurisdiction` matches in any case and also matches its subdivisions.
- `entry_to_source(entry: CatalogueEntry, jurisdiction_id: str | None = None) -> dict[str, str]`: the sources file entry for a chosen catalogue entry.
- `merge_sources(sources, jurisdictions, entries) -> MergeResult`: add entries to a sources list with the jurisdictions they need. Raises `CatalogueError`, changing nothing, when an id is already used by a different entry.
- `jurisdiction_name(code: str) -> str`: a readable name for a jurisdiction code.
- `CatalogueEntry`: frozen dataclass with every catalogue field, `auth` as an `Auth` or `None`, plus `access_label`, `keyed` and `to_dict()`.
- `Auth`: frozen dataclass with `type` and `name`; `to_text()` gives `type:name`.
- `MergeResult`: frozen dataclass with `sources`, `jurisdictions`, `added`, `present` and `added_jurisdictions`.
- `CatalogueError`: the catalogue is unreadable or invalid, or a choice cannot be applied.
- Constants: `FIELDS`, `REGIONS`, `KINDS`, `CATEGORIES`, `MECHANISMS`, `ACCESS`, `CADENCES` and `ACCESS_LABELS`.

## `system`

The one place that starts a program.

- `run_command(args, stdin=None) -> CommandResult`: run an argument list without a shell, with `stdin` on standard input and a 15 second timeout. It never raises for a failed program: one that cannot start returns status 127 and one that runs too long returns 124.
- `CommandResult`: frozen dataclass with `returncode`, `stdout` (hidden from `repr`) and `stderr`.
- `System`: frozen dataclass with `runner`, `platform`, `which`, `environ`, `home`, `uid`, `executable`, `read_secret` and `stdin_is_terminal`, plus `is_macos` and `is_linux`. `regwatch.cli.main(..., system=...)` takes one, so tests replace every program regwatch would start.

## `keys`

Keys in the system keychain. See the [security model](../explanation/security-model.md#api-keys).

- `KeyStore(system=None)`: `set(key_env, value)` stores a key and reads it back to confirm it, `get(key_env)` returns the environment variable when set and otherwise the stored key, `stored(key_env)` reads the keychain only, `status(key_env)` returns a `KeyStatus`, and `delete(key_env)` returns true when a key was removed. `backend` is `macos`, `linux` or None, and `backend_label` names it in words.
- `KeyStatus`: frozen dataclass with `key_env` and `source` (`environment`, `keychain`, `missing` or `unavailable`), and the property `present`.
- `check_key(value: str) -> str`: return a usable key or raise `KeyStoreError` without repeating it.
- `KeyStoreError`: a key could not be stored, read or removed; the message never holds a key. Every method raises it for a `key_env` that does not match `KEY_ENV_RE`.
- `shared_key_errors(sources) -> list[str]`: messages for key variables that sources at different hosts share; `sources` holds `(source_id, key_env, url)` tuples.
- Constants: `SERVICE` (`regwatch`), `MAX_KEY_LENGTH` (4096), `SECURITY_LINE_BYTES` (4095, the longest line `set` writes to `security -i`, line feed included; a longer one raises `KeyStoreError`), `KEY_ENV_RE` (`^REGWATCH_KEY_[A-Z0-9_]{1,51}$`) and `KEY_ENV_RULE`, the same rule in words.

## `schedule`

Builders for the launchd agent and the crontab block.

- `program_arguments(executable, config_path) -> list[str]`: the command a schedule runs, `<executable> -m regwatch --config <config> run`. Raises `ScheduleError` for a relative interpreter path.
- `plist_bytes(arguments, every, working_dir, log_path) -> bytes` and `plist_path(home) -> Path`: the launchd agent and where it lives.
- `cron_block(arguments, every, working_dir, log_path) -> str`: the crontab lines between marker comments, every part quoted for the shell; a path with `%` or a line break raises `ScheduleError`.
- `installed_block(crontab) -> str | None` and `replace_block(crontab, block) -> str`: find, replace or (with None) remove the block, keeping every other line.
- `schedule_cadence(cadences) -> str`: the most frequent of `hourly`, `daily` and `weekly` among the given cadences, `daily` when none is recognised.
- Constants: `LABEL` (`io.github.klappe-pm.regwatch`), `CADENCES`, `INTERVAL_SECONDS` and `CRON_TIMES`.
- `ScheduleError`: a schedule cannot be built or installed.

## `state`

Snapshots, the last-seen state and the only write path.

- `safe_write_text(path: Path, text: str, protected: Iterable[Path]) -> None`: write UTF-8 text atomically, replacing any unencodable character. Raises `StateError` if `path` is a protected file, compared by identity with `os.path.samefile` when both exist and by case folded name otherwise, or if it is a directory.
- `safe_write_bytes(path: Path, data: bytes, protected: Iterable[Path]) -> None`: the same for bytes.
- `write_run_record(state_dir, record, started, protected, keep=500) -> Path`: write one run record as `runs/run-<started>-<sequence>-<random>.json` under the state directory, where `started` is `YYYYMMDDTHHMMSSffffffZ` (with microseconds) or `YYYYMMDDTHHMMSSZ` and `sequence` is four digits counting the records already written with the same start, and remove the oldest records beyond `keep`. The record just written always sorts last, so it is never the one removed.
- `list_run_records(state_dir) -> list[Path]`: the run records, oldest first, ordered by start time, then sequence. Records named in the earlier `run-<YYYYMMDDTHHMMSSZ>-<random>.json` form are still listed.
- `remove_file(path, protected) -> bool`: delete a file, refusing a protected one; true when there was one.
- `update_register_file(path: Path, text: str, register_paths: Iterable[Path]) -> None`: rewrite one register file atomically while every other register file stays protected. Only `sources add` and `sources remove` call it.
- `snapshot_path(snapshots_dir: Path, source_id: str) -> Path`: the snapshot file for a source id. Raises `StateError` for an id that does not match `SOURCE_ID_RE`, so an id can never escape the directory.
- `read_snapshot(snapshots_dir: Path, source_id: str) -> str | None`: the stored text, or `None`.
- `write_snapshot(snapshots_dir: Path, source_id: str, content: str, protected: Iterable[Path]) -> Path`: store content and return the path.
- `load_seen(path: Path) -> SeenState`: load the last-seen state; an empty state if the file does not exist. Raises `StateError` for a malformed file.
- `save_seen(path: Path, state: SeenState, protected: Iterable[Path]) -> None`: write the last-seen state.
- `SeenState`: the type `dict[str, dict[str, str]]`, keyed by source id.
- `SOURCE_ID_RE`: the compiled pattern `^[a-z0-9-]+$`.
- `StateError`: a state file is unreadable or a write was refused.

## `check`

Change detection.

- `SHRINK_RATIO: float` (0.5) and `MIN_PRIOR_LENGTH: int` (20): a signal shorter than `SHRINK_RATIO` times an accepted signal of at least `MIN_PRIOR_LENGTH` characters is `SUSPICIOUS`.
- `fetch_source(source, fetcher, key_for=None) -> str`: fetch one source, adding its key when its entry has `auth`. `key_for` maps a `key_env` name to a key or None; a keyed source without a key raises `FetchError` naming the variable and `regwatch keys set`, and a keyed source whose `key_env` does not start with `REGWATCH_KEY_` raises `FetchError` before `key_for` is called. For a keyed source the returned body and any `FetchError` have the key replaced with `[key]`, whichever fetcher is used.
- `KeyLookup`: the type of `key_for`, `Callable[[str], str | None]`.
- `check_sources(sources, seen, snapshots_dir, fetcher=None, key_for=None) -> list[SourceResult]`: compare each source with its accepted hash. With a `fetcher` the content is fetched now, keyed sources with their key from `key_for`; without one the snapshot is read. A fetch or parse failure becomes an `ERROR` result, not an exception. An empty or sharply shorter signal is `SUSPICIOUS`.
- `accept_results(seen, results, now, accept_suspicious=False) -> SeenState`: a copy of `seen` with the hash and signal length from `results` recorded. `SUSPICIOUS` results are skipped unless `accept_suspicious` is true. It does not write anything.
- `capture_sources(sources, fetcher, snapshots_dir, protected, key_for=None) -> list[CaptureResult]`: fetch each non-manual source and store the raw content. A snapshot holds the body only, never the request URL, so a key in a query parameter is not stored.
- `SourceResult`: frozen dataclass with `source_id`, `status`, `origin`, `sha256`, `detail` and `signal_length`; the property `flagged` is true for `NEW`, `CHANGED` and `SUSPICIOUS`, and `needs_attention` is true for `ERROR` and `MISSING`.
- `CaptureResult`: frozen dataclass with `source_id`, `captured` and `detail`.

## `ingest`

Candidate events from a Federal Register style API response.

- `build_query_url(settings: IngestSettings, since: str) -> str`: the API URL for documents published on or after an ISO date. Raises `IngestError` for a bad date.
- `parse_candidates(json_text: str, settings: IngestSettings, today: date) -> list[dict[str, Any]]`: unconfirmed candidate events, newest first. Raises `IngestError` for a response that is not JSON or has no `results` list. Every field is type checked, stripped of control characters and truncated, a document number must be a plain identifier, and a link is kept only if `safe_https_url` accepts it.
- `candidates_document(candidates, today, origin) -> dict[str, Any]`: wrap candidates with provenance for writing to the state directory.
- `IngestError`: the response is not usable.

## `impact`

Candidate impact analysis.

- `SEVERITIES: tuple[str, ...]`: `("act-now", "high", "watch", "info")`, worst first.
- `assess_impacts(register: Register, today: date | None = None, focus: FocusProfile | None = None) -> list[Impact]`: flag every obligation and product pair that passes the exposure, scope and attribute gates. Pairs that match the focus profile come first, then the rest, and each group is worst first. Nothing is dropped: a pair that matches no focus area has `in_focus` false. With no profile, or an inactive one, every pair is in focus.
- `jurisdiction_applies(jurisdiction: str, markets: Iterable[str], parents: dict[str, str]) -> bool`: true when the jurisdiction and any market lie on one path of the jurisdiction tree.
- `scope_applies(obligation_scope: Iterable[str], product_scopes: Iterable[str]) -> bool`: true when the obligation has no scope limit or shares a scope with the product.
- `theme_findings(register: Register, impacts: Iterable[Impact], themes: Iterable[Theme]) -> list[Finding]`: apply each theme as a lens.
- `Impact`: frozen dataclass with `product_id`, `product_name`, `obligation_id`, `obligation_title`, `jurisdiction`, `status`, `effective_date`, `reasons`, `severity`, `focus` (the identifiers of the focus areas matched, `custom-terms` for custom terms) and `in_focus`.
- `Finding`: frozen dataclass with `key`, `title`, `why`, `action`, `affected_products` and `obligations`.

## `document`

The document model shared by every briefing and renderer.

- `DISCLAIMER: str`: the standard statement that nothing produced is legal advice.
- `make_disclaimer(extra: str = "") -> str`: the standard disclaimer followed by `extra`.
- `Section(heading, level=2, paragraphs=[], bullets=[], generated=[])`: a heading with paragraphs, bullets and generated passages. Level 2 is a section, 3 and 4 are subsections.
- `GeneratedPassage(text, cites=[], facts=[], provider="", model="")`: text a language model wrote, the ids it cites, the text of the facts behind them in the same order, and what wrote it. HTML, plain text and Word show the facts' text only; Markdown puts each fact's id in a code span before its text. A section's `generated` key is present in `to_dict()` only when it holds a passage.
- `Document(title, generated, subtitle="", sections=[], disclaimer=DISCLAIMER)`: a titled, dated list of sections. `date_line` is "Prepared 15 November 2026." for the renderers, or empty when the title or the subtitle already says the date. `to_dict()` returns a JSON-serialisable form. `Document.from_dict(data)` builds one from parsed JSON, checks every field, and always restores the disclaimer. Raises `DocumentError`.
- `DocumentError`: a document model is malformed.

## `wording`

Plain wording for the sentences regwatch builds.

- `count(n, one, many=None) -> str`: `n` with the noun in the right number, zero to nine in words: "one source", "four sources", "12 sources". `number(n)` is the number alone.
- `join_clauses(clauses) -> str`: the non-empty clauses joined with commas and a final "and". Every summary sentence is built from its non-zero clauses only.
- `long_date(day)`, `prose_date(value)` and `date_range(start, end)`: "15 November 2026", and a period as "20 to 26 October" or "28 September to 4 October", with the years when it crosses one.
- `status_phrase(status, detail="")`: what a source check found in words: "first snapshot taken", "content changed", "no snapshot yet", "could not be read (detail)", "looks wrong (detail)".
- `severity_label(severity)` ("act now" for `act-now`) and `provider_name(provider)` (Anthropic, OpenAI, Ollama).

## `design`

The logo of the design specification; the rest of `[document]` is checked in `config` (`DocumentDesign`, `check_color`, `contrast_with_white`, `check_title_format`, `FONTS`).

- `load_logo(path: Path | None, roots) -> Logo | None`: the checked logo, or None when none is set. Raises `DesignError` for a logo outside `roots`, a link, a file that is not regular or larger than 300,000 bytes, a bad PNG, or an SVG that is not plain drawing.
- `clean_svg(text: str) -> bytes`: the SVG written out again from its parsed tree, or `DesignError` naming the element or attribute that is refused.
- `Logo(kind, data, width=0, height=0)`: `kind` is `png` or `svg`; `media_type` and `data_uri` give it as an image.

## `newsletter`

- `newsletter_content(register, results, impacts, candidates, today, since_days) -> NewsletterContent`: the period's changed sources, change log events, candidates and act now or high severity impacts, with the source names (`names`) and the jurisdiction names (`places`); `facts()` gives them as facts for generated copy.
- `build_newsletter(register, content, design, generated=None) -> Document`: the newsletter as a document, with generated passages in place of the fixed sentences they cover.
- `render_email_html(doc, design, footer, *, logo=None, logo_src="") -> str`, `render_email_text(doc, design, footer) -> str` and `email_bytes(subject, text, html_body, now, logo=None) -> bytes`: the HTML email, the text part and the `.eml` file.

## `llm`

Generated copy. See [the language model stage](../explanation/security-model.md#the-language-model-stage).

- `Fact(fact_id, section, text)`: one structured fact with its id; `line` is `id: text`.
- `change_facts(results, names)`, `event_facts(events, places=None)`, `candidate_facts(candidates)`, `impact_facts(impacts, places=None)`, `obligation_facts(obligations, places=None) -> list[Fact]`: facts from check results, change log events, ingest candidates, impacts and obligations, each cleaned and cut to 400 characters. They read as plain sentences: a source by its name and what was found ("FDA news: content changed"), dates in prose, a jurisdiction by its name from `places` (jurisdiction names by id), a severity by its label, and no separator left behind by an empty field.
- `Provider`: a protocol with `name`, `model` and `complete(system, prompt, max_tokens) -> Completion`. `AnthropicProvider(poster, key, model)`, `OpenAIProvider(poster, key, model)` and `OllamaProvider(poster, model)` implement it over any `Poster`, an object with `post_json`. An answer the provider cut off at `max_tokens` (Anthropic `stop_reason` `max_tokens`, OpenAI `finish_reason` `length`, Ollama `done_reason` `length`) raises `GenerationError` naming `[llm] max_tokens`. Ollama is asked for `format` `json` with `num_predict` set to `max_tokens` and `num_ctx` 16384. `AnthropicProvider(poster, key, model, sleep=time.sleep)` sends `fallbacks` `default` and the `anthropic-beta` header `ANTHROPIC_FALLBACK_BETA` only for a model in `ANTHROPIC_FALLBACK_MODELS` (`claude-fable-5-1`, `claude-opus-5-5`, `claude-opus-5` and `claude-sonnet-5-5`), and sends a request answered with status 429, 500 to 599 or 529 once more after `RETRY_DELAY_SECONDS` (2 seconds).
- `provider_message(body: str) -> str`: the provider's own reason in an error body (`{"error": {"message": ...}}` or `{"error": "..."}`), cleaned and cut to 200 characters, or an empty string.
- `GenerationError(message, outcome="refused")`: generated copy could not be written; `outcome` is what the call record says (`refused`, `cut off`, `unreadable` or `error`).
- `provider_for(settings: LlmSettings, poster, key_for) -> Provider`: the provider `[llm]` names, with its key from `key_for(key_env)`. Raises `GenerationError` when a key is missing.
- `llm_fetcher(config: Config) -> SafeFetcher`: the fetch client for a call, with the `[llm]` deadline.
- `generate(provider, facts, purpose, *, max_tokens, record=None, sections=SECTIONS) -> GenerationResult`: one call for the output whose generated sections are `sections` (`NEWSLETTER_SECTIONS` in `regwatch.newsletter` for a newsletter, which has no obligations section); `record` receives the provider, the model, the token counts, the duration and the outcome. Raises `GenerationError`; when the request failed, its message ends with the provider's own reason from `provider_message`, if the error body gave one.
- `parse_passages(text, facts, provider="", model="", sections=SECTIONS) -> GenerationResult`: the passages that cite only the given facts, by section, with the reasons any were dropped. A passage for a section not in `sections`, or for a section other than the opening that cites no fact of that section, is dropped.
- `GenerationResult`: `passages` by section, `dropped`, `provider`, `model`, `notice` (why no request was sent, when none was), `section(name)` and `count`.
- `LLM_KEYS`: the fixed key variable of each provider; `KEY_IDS`: the ids `regwatch keys` uses for them.

## `synthesis`

Deterministic briefings. They call no external service.

- `daily_brief(register, results, impacts, today) -> Document`: what changed, what is effective within 30 days, and the act-now and high candidates. Candidates with `in_focus` false are listed under `Flagged Outside Your Focus Areas`.
- `weekly_synthesis(register, impacts, findings, today) -> Document`: the full analysis of the register against the portfolio. Candidates with `in_focus` false are listed under `Candidate Impact Outside Your Focus Areas`.
- `upcoming_obligations(obligations, days, today) -> list[Obligation]`: obligations effective from today to `days` days ahead, soonest first.
- `digest_document(register, today, window) -> Document`: the register digest that `regwatch digest` prints.
- `report_document(register, results, today, window) -> Document`: the change and due alert that `regwatch report` prints.

## `briefing`

- `TIERS: tuple[str, ...]`: `("v1", "v2", "v3")`.
- `build_briefing(register, impacts, today, *, tier="v3", recent_count=8, since_days=None, candidates=(), focus=None) -> Document`: the tiered briefing. Raises `ValueError` for an unknown tier. Candidates appear only in `v3`, and are always labelled unconfirmed. With an active `focus` profile, obligations, dated items and candidates that match come first and the rest follow under an outside-your-focus-areas heading; see the [focus catalogue](focus-catalogue.md).

## `sanitize`

Cleaning of untrusted text. See the [security model](../explanation/security-model.md).

- `clean_text(text: str, limit: int | None = None) -> str`: one line with C0, C1, DEL and ESC characters and invisible format characters (category Cf) removed, line and paragraph separators turned into spaces, lone surrogates replaced and whitespace collapsed; cut to `limit` characters when given.
- `clean_line(text: str) -> str`: the same cleaning for a line to be printed, but whitespace is kept so columns stay aligned.
- `safe_https_url(value: object) -> str`: the link if it is a plain https link of at most `MAX_URL_LENGTH` (2000) characters with no whitespace, control character, invisible format character, quote, backslash or any of `()[]<>` and backtick, and with a plain ASCII host, otherwise an empty string.
- `escape_markdown(text: str) -> str`: backslash-escape every Markdown metacharacter and a leading list marker (also a value that is only a marker, such as `2027.`) so the text renders literally; it also escapes a value made only of `-` or `=`, the colon of `://`, every `@` and every dot that is followed by a non-space character, so a renderer that links bare text finds no link.
- `MAX_URL_LENGTH: int`: 2000.

## `render`

Delivery formats. HTML and Word output escape all text.

- `FORMATS: tuple[str, ...]`: `("md", "web", "newsletter", "docx")`.
- `TAG_RE`: the compiled pattern a web post tag must match.
- `render_markdown(doc: Document) -> str`: Markdown with every value cleaned and escaped.
- `render_webpost(doc: Document, tags: Sequence[str]) -> str`: Markdown with YAML front matter and `draft: true`. Raises `ValueError` for an invalid tag.
- `render_newsletter_html(doc: Document) -> str`: a self-contained HTML email.
- `render_newsletter_text(doc: Document) -> str`: the plain text alternative.
- `passage_html(passage, tag_color="#4b5866") -> str`: one generated passage with inline styles, for email.
- `render_document_html(doc, design=None, logo=None) -> str`: a standalone HTML page in the design, with a print stylesheet that sets the page size, and the logo inline.
- `render_styles_xml(design=None) -> str`: the `word/styles.xml` part with the design's font and colours.
- `render_document_xml(doc, design=None, logo=None) -> str`: the `word/document.xml` part, with paragraphs in named styles, the page size, header and footer references and a PNG logo.
- `docx_bytes(doc, design=None, logo=None) -> bytes`: the bytes of a `.docx` file with its styles part, and a header, a footer and a PNG logo when the design has them.

## `export`

- `RECORD_COLUMNS: tuple[str, ...]`: the export columns.
- `FORMULA_STARTS: tuple[str, ...]`: the characters that make a spreadsheet read a cell as a formula.
- `neutralise_cell(value: str) -> str`: prefix an apostrophe to a cell, and to each part of it that follows a `;`, a `,`, a tab or a line break, that starts with one of them, also after leading whitespace or invisible format characters and in the fullwidth forms.
- `build_records(register: Register) -> list[dict[str, str]]`: one normalized record per obligation.
- `records_csv(records: list[dict[str, str]]) -> str`: CSV text with a header row, every field quoted and formula cells neutralised.

## `focus`

Focus areas and profiles. See the [focus catalogue](focus-catalogue.md).

- `load_catalogue(path: Path | None = None) -> tuple[FocusArea, ...]`: read and validate a catalogue file, or the shipped one when `path` is `None`. Raises `FocusError`.
- `parse_catalogue(data: object, label: str = "the focus catalogue") -> tuple[FocusArea, ...]`: validate a decoded catalogue. Raises `FocusError`.
- `shipped_catalogue_text() -> str`: the shipped catalogue file, read through `importlib.resources`.
- `build_profile(settings: ProfileSettings) -> FocusProfile`: resolve the chosen identifiers against the catalogue. An empty `settings` gives an inactive profile. Raises `FocusError` for an unknown identifier.
- `FocusProfile(areas=(), custom_terms=())`: frozen dataclass. `active` is true when there is at least one area or term. `names()` lists the labels. `matches(*texts)` returns the identifiers of the areas whose terms appear in the texts, whole word, any case, one plural ending allowed. `match_obligation(obligation, detail=None)`, `match_product(product)` and `match_candidate(candidate)` apply it to the text of each kind of item.
- `FocusArea`: frozen dataclass with `focus_id`, `label`, `description` and `terms`.
- `CUSTOM_TERMS_KEY: str`: `"custom-terms"`, the identifier reported for a custom term.
- `FocusError`: the catalogue is unreadable or invalid, or the profile names an unknown area.

## `onboarding`

What `regwatch init` writes and the checks on its answers. Nothing here prints or asks a question.

- `SCAFFOLD_NAMES: tuple[str, ...]`: the files `init` writes, relative to the project folder.
- `CATALOGUE_NAME: str`: `"focus-areas.json"`.
- `InitPlan(directory, focus_areas=(), custom_terms=(), jurisdictions=(), file_roots=(), contact="", sources=())`: frozen dataclass of the answers; `sources` holds the chosen `CatalogueEntry` values.
- `matching_entries(entries, focus_areas, jurisdictions) -> list[CatalogueEntry]`: the catalogue entries that fit the chosen focus areas and jurisdictions, as `init` lists them.
- `scaffold_files(plan: InitPlan) -> dict[str, str]`: the text of every file, keyed by relative path, with the chosen sources and the jurisdictions they need. Raises `OnboardingError` if an answer cannot be stored in TOML.
- `parse_focus_choice(tokens, catalogue) -> tuple[str, ...]`: identifiers or one-based numbers to identifiers.
- `jurisdiction_records(names) -> tuple[dict[str, str], ...]`: tracked jurisdiction records with identifiers made from the names.
- `example_jurisdictions() -> tuple[dict[str, str], ...]`: the invented jurisdictions that `init --example` offers.
- `clean_value(value, what) -> str`, `clean_terms(values) -> tuple[str, ...]`, `check_contact(value) -> str`, `check_directory(value, home) -> Path` and `check_file_root(value, base, home) -> str`: validate one answer, each raising `OnboardingError` with a message that says what is wrong.
- `user_agent_for(contact: str) -> str`: the User-Agent header for a contact.
- `OnboardingError`: an answer is not usable. It is a `ValueError`.

## `settings`

Changes one setting in `regwatch.toml` and keeps the rest of the file.

- `edit_setting(text: str, table: str, key: str, value: bool | int | str | list[str]) -> str`: the text with `[table] key` set, replacing its line (or every line of a value that spans several) or adding it. Raises `SettingsError` unless the result parses to the old settings with exactly that value changed.
- `set_setting(config_path: Path, table: str, key: str, value: bool | int | str | list[str]) -> None`: load and validate the configuration, edit it and write it atomically through `state.safe_write_text`, with the register files protected.
- `set_premium(config_path: Path, enabled: bool) -> None`: set `[premium] enabled`.
- `set_llm(config_path: Path, *, enabled=None, provider=None, model=None) -> None`: set `[llm] enabled`, `provider` and `model`; each one left as None is kept. A provider must be `anthropic`, `openai` or `ollama`.
- `set_focus_areas(config_path: Path, focus_areas, known) -> None`: set `[profile] focus_areas` to ids that are in `known`, without repeats. Raises `SettingsError` for any other id.
- `SettingsError`: the setting could not be changed and the file was left as it was. It is a `ValueError`.

## `workspace`

The operations `regwatch sources`, `keys` and `run` share with the web app. Nothing here prints or asks.

- `source_catalogue(config: Config | None) -> tuple[CatalogueEntry, ...]`: the shipped catalogue, plus `[catalogue] extra` when a configuration names one.
- `focus_area_ids(config: Config | None) -> list[str]`: the shipped focus area ids, then those of the focus catalogue a configuration names, without repeats.
- `chosen_ids(config: Config) -> list[str]`: the ids in the sources file.
- `find_entries(catalogue, ids) -> list[CatalogueEntry]`: the entries for `ids`, without repeats. Raises `WorkspaceError` for an unknown id.
- `add_sources(config: Config, entries) -> MergeResult`: `regwatch sources add`: writes the sources file, and the jurisdictions file when a jurisdiction was added. Raises `CatalogueError` when a different source already has an id.
- `KeyedSource`: frozen dataclass with `source_id`, `key_env` and `signup_url`.
- `keyed_sources(config: Config | None, catalogue) -> list[KeyedSource]`: the keyed sources in the sources file, or with no configuration every keyed catalogue entry. `keyed_source(config, catalogue, source_id) -> KeyedSource` finds one, or raises `WorkspaceError`.
- `key_lookup(store: KeyStore) -> Callable[[str], str | None]`: a lookup that answers None when no key can be read.
- `fetcher_for(settings: FetchSettings) -> Fetcher`: the fetch client for the settings.
- `run_once(config, fetcher, key_for, clock, register=None) -> RunOutcome`: `regwatch run`: captures, checks and writes a run record. `RunOutcome` holds the captures, the results, the failed captures, the counts, the code (0, 3 or 4), the record and its path. `RUN_OK`, `RUN_CHANGES` and `RUN_UNVERIFIED` name the codes.
- `read_run_records(config: Config, limit: int = 50) -> list[dict]`: the newest run records first, with only their known fields; an unreadable record is skipped.
- `schedule_state(config: Config, system: System, now: datetime) -> ScheduleState`: the installed schedule, read without changing anything. `ScheduleState` has `via` (`launchd` or `cron`), `installed`, `every`, `next_run` (exact for cron; for launchd the last run plus the interval) and `note`.
- `premium_refusal(feature: str) -> str`: the message for a premium feature used while premium is off; it names `regwatch premium on`.
- `read_candidates(config: Config) -> list[dict]`: the ingest candidates as stored, or none when the file is missing or unreadable.
- `generated_copy(config, facts, purpose, key_for, poster=None, now=..., sections=SECTIONS) -> GenerationResult`: one generated copy call with the configured provider, recorded in `llm-calls.jsonl`. With no facts no request is sent and nothing is recorded: the result is empty, with `NO_FACTS_NOTICE` as its `notice`, so the fixed sentences stand. Raises `WorkspaceError` when `[llm]` is off.
- `logo_for(config: Config) -> Logo | None`: the checked logo, under the project folder or an allowed file root.
- `newsletter_plan(config, today, since_days) -> tuple[Register, NewsletterContent]`: the register and the period's items, with sources checked against their snapshots. The period is 1 to 366 days.
- `newsletter_files(config, register, content, now, generated=None) -> NewsletterFiles`: the newsletter as `subject`, `html` (with the logo inline), `text` and `eml` bytes, with `generated`, the `dropped` reasons and the `notice` of the generation result, and `logo_note`, which is `SVG_LOGO_NOTE` when the logo is an SVG and so is left out of the email.
- `document_plan(config, today, kind, tier="v2") -> tuple[Document, list[Fact]]`: the `briefing`, `digest` or `report` with the design's title format, and the facts generated copy may use.
- `with_summary(doc, generated) -> Document`: the document opened by a Summary section of every kept passage.
- `document_bytes(config, doc, fmt) -> bytes`: the document as `html`, `docx` or `md`, in the design with its logo.
- `WorkspaceError`: a request the user can fix. It is a `ValueError`.

## `webapi`

The JSON interface behind `regwatch ui`. It never prints, and only a run started with `/api/automations/run` fetches.

- `Api(config_path: Path, today=datetime.date.today, *, system=None, fetcher=None, clock=None)`: the routes over one configuration file, with the same seams as `cli.main`. `handle(method, path, query, body) -> tuple[int, dict | Download]` answers one request and raises `ApiError` for a refusal. `running` is true while a run started by the interface is in progress, and `wait_for_run(timeout)` waits for it. The routes are listed in the [CLI reference](cli.md#ui).
- `ApiError(status: int, message: str)`: a refused request; `message` is short and holds no file contents.
- `Download`: frozen dataclass with `filename`, `content_type` and `data`, a file the browser saves.
- `SUPPLY_CATEGORIES: tuple[str, ...]`: the catalogue categories the Overview's Supply Chain section lists: `ingredients-supply`, `packaging-materials` and `commodities-and-forecasts`.

## `server`

The local server behind `regwatch ui`. See the [security model](../explanation/security-model.md#the-local-server).

- `LocalServer(api: Api, root: Path, port: int = 0, token: str | None = None)`: a `ThreadingHTTPServer` bound to `127.0.0.1` that serves the files under `root` and the routes of `api`. `url` is the address to open, with the launch token. `exchange(value)` trades the unspent launch token for a new session value once and returns None for every other value and every later call; `session` holds that value (None before the exchange), `launch_spent` says whether it happened, and `session_matches(value)` checks a cookie. A connection that makes no progress for `HANDLER_TIMEOUT_SECONDS` (30) is closed, and at most `MAX_CONNECTIONS` (32) are handled at once; a further connection is closed unread. Raises `ServerError` when it cannot listen.
- `web_root() -> Path`: the built web app shipped in the package. Raises `ServerError` when it is missing.
- `content_security_policy(script_hashes: list[str]) -> str`: the policy sent with every response.
- `ServerError`: the server cannot start.

## `cli`

- `main(argv=None, *, fetcher=None, today=None, now=None, system=None) -> int`: run the command line and return the exit status. `fetcher`, `today`, `now` and `system` let tests and embedders supply a fake network client, a fixed clock, and a `System` whose runner stands in for the keychain tools, `launchctl` and `crontab`.
