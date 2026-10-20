# python-api

This page lists every public function, class and constant in the `regwatch` package, module by module (the heading is the module name inside the `regwatch` package, for example `regwatch.config`), with its signature and what it does. The command line is a thin layer over these functions, and you can call them from your own scripts. A name is public when it appears in its module's `__all__`; everything else is internal and may change without notice. The package is typed, and `mypy --strict` passes on it.

Nothing the package produces is legal advice. Functions that produce documents always include the disclaimer.

## package

- `__version__: str`: the package version, `"0.1.0"`.

## config

Reads `regwatch.toml`. See [configuration](configuration.md) for the keys.

- `DEFAULT_CONFIG_NAME: str`: `"regwatch.toml"`.
- `load_config(path: Path) -> Config`: parse and validate a configuration file. Raises `ConfigError`.
- `ConfigError`: the configuration file is missing, unreadable or invalid.
- `Config`: frozen dataclass with `base_dir`, `register`, `state_dir`, `snapshots_dir`, `fetch`, `ingest`, `config_path` and `profile`, plus the properties `seen_path` and `candidates_path`. `protected_paths()` returns the register files, the configuration file, the two state files and the focus catalogue when one is configured, which a user-named output must never overwrite.
- `ProfileSettings`: frozen dataclass with `focus_areas`, `custom_terms` and `catalogue`, the `[profile]` table.
- `RegisterPaths`: frozen dataclass of the register file paths: `obligations`, `jurisdictions`, `categories`, `sources`, `portfolio`, and the optional `detail`, `changelog`, `enforcement` and `themes`. `all_paths()` returns every configured path, resolved, for write protection.
- `FetchSettings`: frozen dataclass with `timeout_seconds`, `total_timeout_seconds`, `max_bytes`, `user_agent`, `allow_private_hosts` and `allowed_file_roots`.
- `IngestSettings`: frozen dataclass with `api_url`, `agencies`, `types`, `cfr_title`, `cfr_parts`, `terms`, `jurisdiction` and `per_page`.

## fetch

The one network client. See the [security model](../explanation/security-model.md).

- `ALLOWED_SCHEMES: frozenset[str]`: `{"https", "file"}`.
- `MAX_REDIRECTS: int`: 5. `CHUNK_BYTES: int`: 16384, the largest single read.
- `check_url(url: str) -> str`: return the lower-cased scheme, or raise `FetchError` for a scheme that is not allowed, a URL that contains a space or a control character, carries credentials or has an invalid port, an `https` URL with no host, or a `file` URL that names a remote host.
- `is_public_address(address: str) -> bool`: true for a globally routable unicast IP address; false for loopback, link-local, private, unique local, shared, reserved, multicast and unspecified addresses, for the IPv4-mapped form of any of them, for an IPv6 address that embeds one (NAT64, 6to4 and Teredo addresses are judged by the IPv4 address inside), for the ranges `::/96`, `fec0::/10` and `64:ff9b:1::/48`, and for text that is not an address.
- `FetchError`: a fetch was refused or failed. The message is cleaned when the error is created, with control characters and invisible format characters removed and a length of at most 1,000 characters, so it is safe to show.
- `Fetcher`: a protocol with one method, `fetch(url: str) -> str`. Implement it to supply a fake client in tests.
- `SafeFetcher(timeout_seconds, max_bytes, user_agent, *, total_timeout_seconds=60.0, allow_private_hosts=False, allowed_file_roots=(), resolver=None, connector=None, wrapper=None)`: the real client. `fetch(url)` returns the body decoded as UTF-8 with undecodable bytes replaced. It vets every address a host resolves to, connects to the vetted address, verifies certificates, follows at most 5 redirects only to `https`, enforces a per-operation timeout and a total deadline, reads `file` URLs only from regular files under `allowed_file_roots`, and raises `FetchError` on any failure or when the body exceeds `max_bytes`. The resolver, connector and wrapper arguments replace name resolution, the TCP connection and the TLS handshake, so tests can run without a network.

## extract

Reduces untrusted content to a signal. Nothing here evaluates content.

- `extract_signal(mechanism: str, content: str) -> str`: the text that gets hashed, for the mechanisms `api`, `rss` and `html`; any other value is treated as plain text. Raises `ExtractError` for a feed that declares a DTD or entity, is not well-formed, or is not an RSS or Atom feed.
- `signal_hash(signal: str) -> str`: the SHA-256 hex digest of the signal.
- `ExtractError`: the content cannot be safely reduced to a signal.

## register

The data model, loading and validation. See [data files](data-files.md).

- `load_register(config: Config) -> Register`: read, validate and build the register. Raises `RegisterError` with every message in `errors`.
- `validate_register(config: Config) -> list[str]`: return every validation error, or an empty list. Raises `RegisterError` only when a file cannot be read or parsed at all.
- `load_schema() -> dict[str, Any]`: the packaged field rules from `regwatch/data/schema.json`.
- `parse_date(value: str) -> date | None`: parse an ISO date, or return `None`.
- `split_list(value: str, delimiter: str) -> list[str]`: split a delimited cell into trimmed, non-empty items.
- `ancestors(jurisdiction_id: str, parents: dict[str, str]) -> list[str]`: the parent chain, nearest first, stopping on a cycle.
- `RegisterError`: the register is unreadable, malformed or invalid; `errors` holds the messages.
- Frozen dataclasses: `Register`, `Jurisdiction`, `Category`, `Source`, `Obligation`, `Product`, `Portfolio`, `Citation`, `DetailRecord`, `ChangeEvent`, `EnforcementTheme`, `Enforcement` and `Theme`. Their fields match the columns and keys in [data files](data-files.md), with list fields as tuples.

## state

Snapshots, the last-seen state and the only write path.

- `safe_write_text(path: Path, text: str, protected: Iterable[Path]) -> None`: write UTF-8 text atomically, replacing any unencodable character. Raises `StateError` if `path` is a protected file, compared by identity with `os.path.samefile` when both exist and by case folded name otherwise, or if it is a directory.
- `safe_write_bytes(path: Path, data: bytes, protected: Iterable[Path]) -> None`: the same for bytes.
- `snapshot_path(snapshots_dir: Path, source_id: str) -> Path`: the snapshot file for a source id. Raises `StateError` for an id that does not match `SOURCE_ID_RE`, so an id can never escape the directory.
- `read_snapshot(snapshots_dir: Path, source_id: str) -> str | None`: the stored text, or `None`.
- `write_snapshot(snapshots_dir: Path, source_id: str, content: str, protected: Iterable[Path]) -> Path`: store content and return the path.
- `load_seen(path: Path) -> SeenState`: load the last-seen state; an empty state if the file does not exist. Raises `StateError` for a malformed file.
- `save_seen(path: Path, state: SeenState, protected: Iterable[Path]) -> None`: write the last-seen state.
- `SeenState`: the type `dict[str, dict[str, str]]`, keyed by source id.
- `SOURCE_ID_RE`: the compiled pattern `^[a-z0-9-]+$`.
- `StateError`: a state file is unreadable or a write was refused.

## check

Change detection.

- `SHRINK_RATIO: float` (0.5) and `MIN_PRIOR_LENGTH: int` (20): a signal shorter than `SHRINK_RATIO` times an accepted signal of at least `MIN_PRIOR_LENGTH` characters is `SUSPICIOUS`.
- `check_sources(sources, seen, snapshots_dir, fetcher=None) -> list[SourceResult]`: compare each source with its accepted hash. With a `fetcher` the content is fetched now; without one the snapshot is read. A fetch or parse failure becomes an `ERROR` result, not an exception. An empty or sharply shorter signal is `SUSPICIOUS`.
- `accept_results(seen, results, now, accept_suspicious=False) -> SeenState`: a copy of `seen` with the hash and signal length from `results` recorded. `SUSPICIOUS` results are skipped unless `accept_suspicious` is true. It does not write anything.
- `capture_sources(sources, fetcher, snapshots_dir, protected) -> list[CaptureResult]`: fetch each non-manual source and store the raw content.
- `SourceResult`: frozen dataclass with `source_id`, `status`, `origin`, `sha256`, `detail` and `signal_length`; the property `flagged` is true for `NEW`, `CHANGED` and `SUSPICIOUS`, and `needs_attention` is true for `ERROR` and `MISSING`.
- `CaptureResult`: frozen dataclass with `source_id`, `captured` and `detail`.

## ingest

Candidate events from a Federal Register style API response.

- `build_query_url(settings: IngestSettings, since: str) -> str`: the API URL for documents published on or after an ISO date. Raises `IngestError` for a bad date.
- `parse_candidates(json_text: str, settings: IngestSettings, today: date) -> list[dict[str, Any]]`: unconfirmed candidate events, newest first. Raises `IngestError` for a response that is not JSON or has no `results` list. Every field is type checked, stripped of control characters and truncated, a document number must be a plain identifier, and a link is kept only if `safe_https_url` accepts it.
- `candidates_document(candidates, today, origin) -> dict[str, Any]`: wrap candidates with provenance for writing to the state directory.
- `IngestError`: the response is not usable.

## impact

Candidate impact analysis.

- `SEVERITIES: tuple[str, ...]`: `("act-now", "high", "watch", "info")`, worst first.
- `assess_impacts(register: Register, today: date | None = None, focus: FocusProfile | None = None) -> list[Impact]`: flag every obligation and product pair that passes the exposure, scope and attribute gates. Pairs that match the focus profile come first, then the rest, and each group is worst first. Nothing is dropped: a pair that matches no focus area has `in_focus` false. With no profile, or an inactive one, every pair is in focus.
- `jurisdiction_applies(jurisdiction: str, markets: Iterable[str], parents: dict[str, str]) -> bool`: true when the jurisdiction and any market lie on one path of the jurisdiction tree.
- `scope_applies(obligation_scope: Iterable[str], product_scopes: Iterable[str]) -> bool`: true when the obligation has no scope limit or shares a scope with the product.
- `theme_findings(register: Register, impacts: Iterable[Impact], themes: Iterable[Theme]) -> list[Finding]`: apply each theme as a lens.
- `Impact`: frozen dataclass with `product_id`, `product_name`, `obligation_id`, `obligation_title`, `jurisdiction`, `status`, `effective_date`, `reasons`, `severity`, `focus` (the identifiers of the focus areas matched, `custom-terms` for custom terms) and `in_focus`.
- `Finding`: frozen dataclass with `key`, `title`, `why`, `action`, `affected_products` and `obligations`.

## document

The document model shared by every briefing and renderer.

- `DISCLAIMER: str`: the standard statement that nothing produced is legal advice.
- `make_disclaimer(extra: str = "") -> str`: the standard disclaimer followed by `extra`.
- `Section(heading, level=2, paragraphs=[], bullets=[])`: a heading with paragraphs and bullets. Level 2 is a section, 3 and 4 are subsections.
- `Document(title, generated, subtitle="", sections=[], disclaimer=DISCLAIMER)`: a titled, dated list of sections. `to_dict()` returns a JSON-serialisable form. `Document.from_dict(data)` builds one from parsed JSON, checks every field, and always restores the disclaimer. Raises `DocumentError`.
- `DocumentError`: a document model is malformed.

## synthesis

Deterministic briefings. They call no external service.

- `daily_brief(register, results, impacts, today) -> Document`: what changed, what is effective within 30 days, and the act-now and high candidates. Candidates with `in_focus` false are listed under `Flagged Outside Your Focus Areas`.
- `weekly_synthesis(register, impacts, findings, today) -> Document`: the full analysis of the register against the portfolio. Candidates with `in_focus` false are listed under `Candidate Impact Outside Your Focus Areas`.
- `upcoming_obligations(obligations, days, today) -> list[Obligation]`: obligations effective from today to `days` days ahead, soonest first.

## briefing

- `TIERS: tuple[str, ...]`: `("v1", "v2", "v3")`.
- `build_briefing(register, impacts, today, *, tier="v3", recent_count=8, since_days=None, candidates=(), focus=None) -> Document`: the tiered briefing. Raises `ValueError` for an unknown tier. Candidates appear only in `v3`, and are always labelled unconfirmed. With an active `focus` profile, obligations, dated items and candidates that match come first and the rest follow under an outside-your-focus-areas heading; see the [focus catalogue](focus-catalogue.md).

## sanitize

Cleaning of untrusted text. See the [security model](../explanation/security-model.md).

- `clean_text(text: str, limit: int | None = None) -> str`: one line with C0, C1, DEL and ESC characters and invisible format characters (category Cf) removed, line and paragraph separators turned into spaces, lone surrogates replaced and whitespace collapsed; cut to `limit` characters when given.
- `clean_line(text: str) -> str`: the same cleaning for a line to be printed, but whitespace is kept so columns stay aligned.
- `safe_https_url(value: object) -> str`: the link if it is a plain https link of at most `MAX_URL_LENGTH` (2000) characters with no whitespace, control character, invisible format character, quote, backslash or any of `()[]<>` and backtick, and with a plain ASCII host, otherwise an empty string.
- `escape_markdown(text: str) -> str`: backslash-escape every Markdown metacharacter and a leading list marker so the text renders literally; it also escapes a value made only of `-` or `=`, the colon of `://`, every `@` and every dot between a letter or digit and a letter, so a renderer that links bare text finds no link.
- `MAX_URL_LENGTH: int`: 2000.

## render

Delivery formats. HTML and Word output escape all text.

- `FORMATS: tuple[str, ...]`: `("md", "web", "newsletter", "docx")`.
- `TAG_RE`: the compiled pattern a web post tag must match.
- `render_markdown(doc: Document) -> str`: Markdown with every value cleaned and escaped.
- `render_webpost(doc: Document, tags: Sequence[str]) -> str`: Markdown with YAML front matter and `draft: true`. Raises `ValueError` for an invalid tag.
- `render_newsletter_html(doc: Document) -> str`: a self-contained HTML email.
- `render_newsletter_text(doc: Document) -> str`: the plain text alternative.
- `render_document_xml(doc: Document) -> str`: the `word/document.xml` part.
- `docx_bytes(doc: Document) -> bytes`: the bytes of a `.docx` file.

## export

- `RECORD_COLUMNS: tuple[str, ...]`: the export columns.
- `FORMULA_STARTS: tuple[str, ...]`: the characters that make a spreadsheet read a cell as a formula.
- `neutralise_cell(value: str) -> str`: prefix an apostrophe to a cell, and to each part of it that follows a `;`, a `,`, a tab or a line break, that starts with one of them, also after leading whitespace or invisible format characters and in the fullwidth forms.
- `build_records(register: Register) -> list[dict[str, str]]`: one normalized record per obligation.
- `records_csv(records: list[dict[str, str]]) -> str`: CSV text with a header row, every field quoted and formula cells neutralised.

## focus

Focus areas and profiles. See the [focus catalogue](focus-catalogue.md).

- `load_catalogue(path: Path | None = None) -> tuple[FocusArea, ...]`: read and validate a catalogue file, or the shipped one when `path` is `None`. Raises `FocusError`.
- `parse_catalogue(data: object, label: str = "the focus catalogue") -> tuple[FocusArea, ...]`: validate a decoded catalogue. Raises `FocusError`.
- `shipped_catalogue_text() -> str`: the shipped catalogue file, read through `importlib.resources`.
- `build_profile(settings: ProfileSettings) -> FocusProfile`: resolve the chosen identifiers against the catalogue. An empty `settings` gives an inactive profile. Raises `FocusError` for an unknown identifier.
- `FocusProfile(areas=(), custom_terms=())`: frozen dataclass. `active` is true when there is at least one area or term. `names()` lists the labels. `matches(*texts)` returns the identifiers of the areas whose terms appear in the texts, whole word, any case, one plural ending allowed. `match_obligation(obligation, detail=None)`, `match_product(product)` and `match_candidate(candidate)` apply it to the text of each kind of item.
- `FocusArea`: frozen dataclass with `focus_id`, `label`, `description` and `terms`.
- `CUSTOM_TERMS_KEY: str`: `"custom-terms"`, the identifier reported for a custom term.
- `FocusError`: the catalogue is unreadable or invalid, or the profile names an unknown area.

## onboarding

What `regwatch init` writes and the checks on its answers. Nothing here prints or asks a question.

- `SCAFFOLD_NAMES: tuple[str, ...]`: the files `init` writes, relative to the project folder.
- `CATALOGUE_NAME: str`: `"focus-areas.json"`.
- `InitPlan(directory, focus_areas=(), custom_terms=(), jurisdictions=(), file_roots=(), contact="")`: frozen dataclass of the answers.
- `scaffold_files(plan: InitPlan) -> dict[str, str]`: the text of every file, keyed by relative path. Raises `OnboardingError` if an answer cannot be stored in TOML.
- `parse_focus_choice(tokens, catalogue) -> tuple[str, ...]`: identifiers or one-based numbers to identifiers.
- `jurisdiction_records(names) -> tuple[dict[str, str], ...]`: tracked jurisdiction records with identifiers made from the names.
- `example_jurisdictions() -> tuple[dict[str, str], ...]`: the invented jurisdictions that `init --example` offers.
- `clean_value(value, what) -> str`, `clean_terms(values) -> tuple[str, ...]`, `check_contact(value) -> str`, `check_directory(value, home) -> Path` and `check_file_root(value, base, home) -> str`: validate one answer, each raising `OnboardingError` with a message that says what is wrong.
- `user_agent_for(contact: str) -> str`: the User-Agent header for a contact.
- `OnboardingError`: an answer is not usable. It is a `ValueError`.

## cli

- `main(argv=None, *, fetcher=None, today=None, now=None) -> int`: run the command line and return the exit status. `fetcher`, `today` and `now` let tests and embedders supply a fake network client and a fixed clock.
