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

Optional table. regwatch writes its own state here and nowhere else apart from output paths you name.

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
