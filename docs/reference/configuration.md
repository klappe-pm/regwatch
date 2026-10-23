# Configuration

This page lists every key in `regwatch.toml`, the file that tells regwatch where your register is and how to behave. Every path is resolved relative to the directory that holds the file; an absolute path is used as written and a leading `~` is expanded. Unknown tables, unknown keys and values of the wrong type are rejected with an `error:` message, so a typo never silently changes behaviour. The file must be smaller than 256,000 bytes.

The configuration holds no API keys, tokens or credentials. A source that needs a key gets it from the system keychain or from the environment variable its entry names, never from this file; see [keep API keys](../how-to-guides/keep-api-keys.md). No setting comes from the environment, and proxy environment variables are ignored on purpose; see the [security model](../explanation/security-model.md).

A complete working file is [examples/regwatch.toml](../../examples/regwatch.toml).

## Register

Required table. The first five keys are required; the last four are optional. regwatch reads these files, and writes only two of them, the sources and jurisdictions files, and only when you run `regwatch sources add` or `regwatch sources remove`.

| key | type | meaning |
| --- | --- | --- |
| `obligations` | path | the obligations CSV |
| `jurisdictions` | path | the jurisdictions JSON |
| `categories` | path | the categories JSON |
| `sources` | path | the sources JSON |
| `portfolio` | path | the portfolio JSON |
| `detail` | path, optional | per-obligation detail used by the tiered briefing and the export |
| `changelog` | path, optional | your curated change log |
| `enforcement` | path, optional | recurring enforcement themes for the tiered briefing |
| `themes` | path, optional | impact themes for `themes` and the weekly brief |

The format of each file is in [data files](data-files.md).

## State

Optional table. regwatch writes its own state here and nowhere else apart from output paths you name and the two settings that `regwatch premium` and the web app's Settings page change in this file.

| key | type | default | meaning |
| --- | --- | --- | --- |
| `dir` | path | `state` | directory for `seen.json` and `ingest-candidates.json` |
| `snapshots` | path | `<dir>/snapshots` | directory for stored source content, one `<source_id>.txt` per source |

Neither may be a register file.

## Fetch

Optional table. Limits that apply to every fetch.

| key | type | default | meaning |
| --- | --- | --- | --- |
| `timeout_seconds` | number | 20 | seconds allowed for each socket operation; above 0 and at most 3600 |
| `total_timeout_seconds` | number | 60 | seconds allowed for a whole fetch, including every redirect; above 0 and at most 3600 |
| `max_bytes` | integer | 2000000 | largest response accepted; 1 to 100000000 |
| `user_agent` | string | `regwatch/0.1 (+https://github.com/klappe-pm/regwatch)` | the `User-Agent` header sent with every request |
| `allow_private_hosts` | boolean | false | when true, a host may resolve to a loopback, link-local, private or other non-public address; leave it false unless a source is on your own network |
| `allowed_file_roots` | list of paths | none | directories that `file` sources may read from; with none listed, every `file` source is refused. A file system root, the home directory, `~` and any parent of the home directory are refused with `too broad`, as `regwatch init` refuses them |

## Profile

Optional table, written by `regwatch init`. It records what matters to your business so that results can be ranked by relevance; see [set your focus areas](../how-to-guides/set-your-focus-areas.md).

| key | type | default | meaning |
| --- | --- | --- | --- |
| `focus_areas` | list of strings | none | identifiers from the focus catalogue, each lowercase letters, digits and hyphens; repeats are dropped. An id that is not in the catalogue is an error when a command uses the profile. |
| `custom_terms` | list of strings | none | extra words that count as a focus, matched without regard to case; repeats are dropped |
| `catalogue` | path, optional | the catalogue shipped with regwatch | a catalogue file that replaces the shipped one; see [focus catalogue](focus-catalogue.md). It is never overwritten by an output path you name. |

With no areas and no custom terms nothing is ranked and every candidate counts as in focus.

## Catalogue

Optional table. A source catalogue of your own, read after the one shipped with regwatch, for sources the shipped catalogue lacks; see [source catalogue](source-catalogue.md).

| key | type | default | meaning |
| --- | --- | --- | --- |
| `extra` | path, optional | none | a catalogue file in the shipped format. Every entry follows the shipped rules, and an id the shipped catalogue uses is refused. It is never overwritten by an output path you name. |

## Ingest

Optional table. Filters for `ingest`, which reads a Federal Register style API.

| key | type | default | meaning |
| --- | --- | --- | --- |
| `api_url` | string | the public Federal Register documents endpoint | the API address; the fetch client accepts only `https` and `file` URLs |
| `agencies` | list of strings | none | agency slugs to request |
| `types` | list of strings | `RULE`, `PRORULE`, `NOTICE` | document types to request |
| `cfr_title` | integer, optional | none | restrict CFR part matching to this title |
| `cfr_parts` | list of integers | none | a document that amends one of these parts is relevant |
| `terms` | list of strings | none | a document whose title or abstract contains one of these, in any case, is relevant |
| `jurisdiction` | string | empty | the jurisdiction id stamped on every candidate |
| `per_page` | integer | 100 | page size requested, 1 to 1000 |

When both `cfr_parts` and `terms` are empty, every returned document is a candidate. Otherwise a document is a candidate if it matches either filter.

## Premium

Optional table, written by `regwatch premium` and the Settings page of `regwatch ui`.

| key | type | default | meaning |
| --- | --- | --- | --- |
| `enabled` | boolean | false | turns on the premium features: newsletters, document templates, generated copy and runs more often than once a day. While it is false, the web app shows them with a lock and a note. |

## LLM

Optional table, written by `regwatch llm` and the Settings page of `regwatch ui`. It configures generated copy, the stage that asks a language model to write the opening and the summaries of a newsletter or a document from the structured facts regwatch already has. It is off by default and works only while premium features are on; see [turn on generated copy](../how-to-guides/turn-on-generated-copy.md). The table holds no key: the Anthropic key is `REGWATCH_KEY_ANTHROPIC` and the OpenAI key `REGWATCH_KEY_OPENAI`, kept in the system keychain with `regwatch keys set llm-anthropic` or `regwatch keys set llm-openai`, or set in the environment.

| key | type | default | meaning |
| --- | --- | --- | --- |
| `enabled` | boolean | false | turns generated copy on |
| `provider` | string | `"anthropic"` | `anthropic` (the Messages API), `openai` (Chat Completions) or `ollama` (a local model on `127.0.0.1:11434`, which needs `allow_private_hosts = true` under `[fetch]`) |
| `model` | string | `""` | the model name, letters, digits and `. _ : / -`, at most 100 characters; empty means the provider's default: `claude-opus-5-5`, `gpt-5-mini` or `llama3.2` |
| `max_tokens` | integer | 4000 | the most tokens one answer may use, 256 to 32000 |
| `timeout_seconds` | number | 180 | the deadline of one call, above 0 and at most 600; it replaces the `[fetch]` timeouts for this call only |

Each call is recorded in `llm-calls.jsonl` in the state directory: the time, the provider, the model, the token counts, the duration, the outcome and how many passages were kept and dropped. The prompt, the answer and the key are never recorded.

## Document

Optional table: the design specification that newsletters and documents follow. The Settings page of `regwatch ui` writes it. Every value is checked when the file is loaded, apart from the logo, which is checked each time a newsletter or a document is built.

| key | type | default | meaning |
| --- | --- | --- | --- |
| `title_format` | string | `"{title}"` | the title of every newsletter and document, 1 to 200 characters; it may use `{title}`, `{date}` and `{organisation}` and no other braces |
| `organisation` | string | `""` | your organisation's name, at most 120 characters; also the logo's alternative text |
| `primary_color` | string | `"#1d5a92"` | headings and the title band, written `#rrggbb`; it must reach a contrast of 4.5:1 against white (WCAG 2.2 AA) |
| `accent_color` | string | `"#a8481a"` | rules under headings, written `#rrggbb`, with the same 4.5:1 contrast |
| `font` | string | `"system"` | one of `system`, `Arial`, `Helvetica`, `Verdana`, `Tahoma`, `Trebuchet MS`, `Georgia`, `Times New Roman`, `Garamond` and `Courier New`, each rendered with its fallbacks |
| `logo` | string | none | a `.png` or `.svg` file of at most 300,000 bytes inside the project folder or one of `allowed_file_roots`, and not a symbolic link. A PNG may be at most 4,000 by 4,000 pixels. An SVG is refused when it holds a script, a style, an event attribute, an image, a link or any element or attribute outside a short drawing list; see the [security model](../explanation/security-model.md#the-design-specification-and-its-logo). Email uses a PNG logo only. |
| `header` | string | `""` | a line above the title, at most 200 characters |
| `footer` | string | `""` | a closing line, such as an address, at most 300 characters |
| `page_size` | string | `"a4"` | `a4` or `letter`, for printed and Word documents |

Text values may not hold control characters.

## Newsletter

Optional table.

| key | type | default | meaning |
| --- | --- | --- | --- |
| `footer` | string | `"You receive this newsletter because you asked for it. Reply to this message to stop."` | the reply or unsubscribe line at the end of every newsletter, at most 300 characters |
