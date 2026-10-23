# Data Files

This page describes every file in the register: what it holds, every field, and the rule the validator applies to it. The rules are packaged data in `regwatch/data/schema.json`, and `regwatch validate` applies them. The register is yours; regwatch reads these files, and writes only the sources and jurisdictions files, and only when you run `regwatch sources add` or `regwatch sources remove`. A synthetic copy of every file is in [examples/register](../../examples/register/README.md).

## Conventions

- List fields in the obligations CSV are separated by `;`. In JSON files they are arrays. A scalar field must not be given an array.
- Identifiers match `^[a-z0-9-]+$`: lowercase letters, digits and hyphens.
- Dates are ISO `YYYY-MM-DD`.
- The `source_url` column of the obligations CSV and the `url` of every citation or backlink must be an `https` URL. A source `url` may be `https` or `file`.
- A reference field must name an identifier defined in the file it refers to.
- Unknown fields in a JSON catalog are errors. Unknown or missing columns in the CSV header are errors, and so is a row with a different number of cells than the header.
- A byte order mark at the start of the CSV is ignored.
- Text must not hold a control character. A C0 control character other than tab, line feed and carriage return, DEL, or a C1 character in any field of any file is an error, because it could carry a terminal escape sequence. The error names the field and not the value.
- Each file may be at most 20,000,000 bytes.

## Obligations CSV

One row is one distinct obligation in one jurisdiction. The header must contain exactly these columns.

| column | required | rule |
| --- | --- | --- |
| `obligation_id` | yes | unique identifier |
| `jurisdiction` | yes | a `jurisdiction_id` |
| `instrument` | yes | one of `statute`, `bill`, `final-rule`, `proposed-rule`, `guidance`, `definition`, `list`, `program`, `waiver` |
| `citation` | no | free text |
| `title` | yes | free text |
| `categories` | no | list of `category_id` |
| `terms` | no | list of named items, such as ingredients, matched to a product's terms without regard to case |
| `claims` | no | list of claims the obligation affects, matched exactly to a product's claims |
| `scope` | no | list of scope tags; empty or `all` means no limit |
| `status` | yes | one of `enacted`, `proposed`, `finalized`, `voluntary`, `in-progress`, `monitoring` |
| `effective_date` | no | date |
| `key_date_note` | no | free text |
| `source_id` | yes | a `source_id` |
| `source_url` | no | `https` URL |
| `last_reviewed` | yes | date |
| `confidence` | yes | one of `high`, `medium`, `low`, `secondary` |
| `notes` | no | free text |

## Jurisdictions JSON

A top-level object with a `jurisdictions` list. The `parent` field builds a tree, and the tree decides which products are exposed to which obligations: a rule reaches a market when the two lie on the same path of the tree. A product sold in a region is exposed to its national rules, and a product sold nationally is exposed to every regional rule. A parent chain may not contain a cycle.

| field | required | rule |
| --- | --- | --- |
| `jurisdiction_id` | yes | unique identifier |
| `name` | yes | free text |
| `parent` | no | a `jurisdiction_id`, not the jurisdiction itself |
| `level` | no | free text, such as `national` or `regional` |
| `coverage` | yes | `confirmed` (has its own obligation rows), `tracked` (watched only through an aggregate row) or `aggregate` (the aggregate marker itself) |
| `notes` | no | free text |

## Categories JSON

A top-level object with a `categories` list. A category is a class of regulated attribute that obligations and products share, such as allergens or colorants.

| field | required | rule |
| --- | --- | --- |
| `category_id` | yes | unique identifier |
| `label` | yes | free text |
| `definition` | yes | free text |
| `examples` | no | list of strings |

## Sources JSON

A top-level object with a `sources` list. See [add a source](../how-to-guides/add-a-source.md) for choosing a mechanism.

| field | required | rule |
| --- | --- | --- |
| `source_id` | yes | unique identifier; also the snapshot file name |
| `jurisdiction` | yes | a `jurisdiction_id` |
| `name` | yes | free text |
| `url` | yes | `https` or `file` URL; a `file` URL is read only under a directory listed in `allowed_file_roots` |
| `method` | yes | `poll` (regwatch reads it on a cadence) or `subscribe` (the source pushes to you) |
| `mechanism` | yes | `api`, `rss`, `html`, `email-list` or `manual` |
| `cadence` | yes | free text, such as `daily`; informational |
| `notes` | no | free text |
| `auth` | no | where a keyed source takes its key: `query:NAME` for a query parameter or `header:NAME` for a request header, where `NAME` is 1 to 64 letters, digits, hyphens and underscores |
| `key_env` | no | the environment variable that can supply the key, and the keychain account it is stored under: `REGWATCH_KEY_` followed by 1 to 51 upper case letters, digits and underscores |

`auth` and `key_env` are given together or not at all, and a source with `auth` must have an `https` URL. Two sources that name the same `key_env` must have URLs with the same host and port. `regwatch sources add` writes both for a keyed catalogue source.

## Portfolio JSON

A top-level object with a `name`, an optional `disclaimer` and a `products` list. The name appears in every briefing title. The disclaimer is appended to the standard one on every briefing. Use it to state how reliable the product records are.

| field | required | rule |
| --- | --- | --- |
| `product_id` | yes | unique identifier |
| `name` | yes | free text |
| `kind` | no | free text |
| `categories` | no | list of `category_id` |
| `terms` | no | list of named items |
| `claims` | no | list of claims the product makes |
| `markets` | yes | list of `jurisdiction_id` the product is sold in |
| `scopes` | no | list of scope tags, such as a sales channel |
| `confidence` | yes | one of `internal-model`, `confirmed`, `secondary` |
| `notes` | no | free text |

## Detail JSON

Optional. A top-level object with an optional `topics_vocabulary` list and a `detail` object keyed by `obligation_id`. When a vocabulary is given, every topic must be in it. An obligation without a record is allowed; the briefing shows a placeholder for it.

| field | required | rule |
| --- | --- | --- |
| `summary` | yes | what the obligation says |
| `impacts` | yes | what it affects |
| `implications` | yes | what it means in practice |
| `action` | yes | what to do about it |
| `topics` | no | list of strings |
| `citations` | no | list of objects with `citation` (required) and `url` |
| `backlinks` | no | list of objects with `label` (required) and `url`; the first is used as the source link |

## Changelog JSON

Optional. A top-level object with an `events` list. This is your curated change log. Candidates from `ingest` are never added to it automatically.

| field | required | rule |
| --- | --- | --- |
| `date` | yes | date |
| `headline` | yes | free text |
| `jurisdiction` | no | a `jurisdiction_id` |
| `agency` | no | free text |
| `obligation_id` | no | an `obligation_id` |
| `what_happened` | no | free text |
| `citations` | no | list of objects with `citation` and `url` |
| `source_url` | no | free text |

## Enforcement JSON

Optional. A top-level object with an optional `reference_url` and a `themes` list of recurring enforcement themes. Shown in the `v2` and `v3` briefings.

| field | required | rule |
| --- | --- | --- |
| `theme` | yes | free text |
| `what_triggers` | yes | free text |
| `note` | no | free text, shown in `v3` |
| `citations` | no | list of objects with `citation` and `url`, shown in `v3` |

## Themes JSON

Optional. A top-level object with a `themes` list. A theme is a lens over the impacts. It matches the obligations that list any of its categories, and the products that both carry one of its categories and have an impact from such an obligation.

| field | required | rule |
| --- | --- | --- |
| `key` | yes | unique within the file |
| `title` | yes | free text |
| `categories` | yes | non-empty list of `category_id` |
| `why` | yes | why the theme matters |
| `action` | yes | what to do about it |

## State Files

regwatch writes these itself, in the state directory. You do not edit them.

| file | holds |
| --- | --- |
| `seen.json` | for each source id, the accepted `sha256`, where it came from, when it was accepted and the length of the accepted signal in characters (`signal_length`) |
| `ingest-candidates.json` | the latest ingest candidates, each with `needs_review` set and `confidence` set to `unconfirmed` |
| `snapshots/<source_id>.txt` | the raw content stored by `capture`; the body only, never the request URL or a key |
| `runs/run-<start>-<sequence>-<random>.json` | one record per `regwatch run`: `started`, `ended`, `sources`, `captured`, `capture_failed`, `counts` by status and `exit_code`. `<start>` is the start time to the microsecond and `<sequence>` counts records with the same start, so records sort in the order they were written. The newest 500 are kept. |
| `schedule.log` | the output of scheduled runs, appended by launchd or cron |
