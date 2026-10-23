# Source Catalogue

This page describes the source catalogue: the file that ships in `regwatch/data/source-catalogue.json`, every field of an entry with the rule the loader applies, the extra catalogue file a user can add, the search ranking, how a chosen entry becomes a line in the sources file, and what the shipped catalogue holds. The commands that read it are under [`sources`](cli.md#sources) in the CLI reference.

## What Ships

As of 2026-10-23 the catalogue holds 575 sources. 93 of them are marked `"verified": false`, because the publisher blocked automated checks or the address could not be confirmed; the `notes` field of each says which. `regwatch sources verify` checks addresses again on demand and never changes the file.

| category | sources |
| --- | --- |
| `regulation` | 386 |
| `policy-and-lobbying` | 59 |
| `industry-news` | 40 |
| `ingredients-supply` | 20 |
| `commodities-and-forecasts` | 18 |
| `packaging-materials` | 18 |
| `logistics-and-trade` | 13 |
| `manufacturing-and-chemicals` | 11 |
| `construction-and-facilities` | 10 |

| access | label shown | sources |
| --- | --- | --- |
| `free` | Free | 535 |
| `free-key` | Free Key | 19 |
| `paid` | Paid | 21 |

## The File

The file is a JSON object with exactly two keys: `version`, which is `1`, and `sources`, a list of entries. Any other top-level key, another version, or a `sources` value that is not a list is refused.

## Fields

Every entry has exactly these keys, in any order. A missing key or an unknown key is an error, and so is any value outside its rule. Text fields are trimmed and must not hold a control character or an invisible format character.

| field | rule |
| --- | --- |
| `source_id` | lowercase letters and digits in words joined by single hyphens, at most 80 characters, unique across the shipped file and the extra file; it becomes the snapshot file name when the source is chosen |
| `name` | non-empty text, at most 200 characters |
| `publisher` | non-empty text, at most 200 characters |
| `jurisdiction` | `intl`, `eu`, a two letter ISO 3166 country code in lower case such as `us`, or a subdivision such as `us-ca` or `ca-on` |
| `region` | `north-america`, `latin-america`, `europe`, `asia-pacific`, `middle-east-africa` or `global` |
| `kind` | `regulator`, `legislature`, `gazette`, `court`, `standards`, `recalls`, `data-portal`, `news`, `industry`, `aggregator`, `lobbying-disclosure`, `interest-group`, `supplier`, `market-data` or `forecast` |
| `category` | `regulation`, `policy-and-lobbying`, `ingredients-supply`, `packaging-materials`, `commodities-and-forecasts`, `manufacturing-and-chemicals`, `logistics-and-trade`, `construction-and-facilities` or `industry-news` |
| `mechanism` | `rss`, `api`, `html`, `email-list` or `manual`, as in a sources file |
| `url` | an `https` URL that passes the fetch client's checks: no space, control character or credentials, and a valid port |
| `homepage` | an `https` URL under the same checks |
| `access` | `free`, `free-key` or `paid` |
| `auth` | `null`, or an object with exactly `type` (`query` or `header`) and `name` (1 to 64 letters, digits, hyphens and underscores) |
| `key_env` | `null`, or an environment variable name in regwatch's namespace: `REGWATCH_KEY_` followed by 1 to 51 upper case letters, digits and underscores |
| `signup_url` | `null`, or an `https` URL under the same checks |
| `focus_areas` | a list of focus area ids from the focus catalogue, with no repeats; an empty list means every area |
| `language` | a two letter ISO 639-1 code such as `en` |
| `cadence` | `hourly`, `daily` or `weekly` |
| `description` | non-empty text, at most 160 characters |
| `verified` | `true` or `false` |
| `checked` | a date written `YYYY-MM-DD` |
| `notes` | `null`, or non-empty text of at most 300 characters |

Rules across fields:

- `auth` and `key_env` are both set or both `null`.
- A `free-key` entry has `auth`, `key_env` and `signup_url`.
- A `free` entry has no `auth`.
- Entries that name the same `key_env` have `url` values with the same host and port, so a key stored for one service is never sent to another.
- In the shipped file, an `api` entry's `url` is a data address: never a page ending in `.html`, `.htm` or `.aspx`, a documentation path such as `docs`, `swagger-ui` or `developers`, or the bare root of a site. A test checks this. A source whose API could not be confirmed is listed as `html` (its page is watched) or `manual` (read by hand), with a note saying why.

## The Extra Catalogue

`[catalogue] extra` in `regwatch.toml` names a file of your own in the same format, for sources the shipped catalogue lacks. Its entries follow every rule above, an id that the shipped file already uses is refused, and so is a `key_env` that a shipped entry uses for a different host. Its entries are listed after the shipped ones, and every `sources` action reads both. The focus ids an entry may name are those of the shipped focus catalogue and of the catalogue named in `[profile] catalogue`. The file is protected like the register: no output path may replace it.

## Search

One function, `rank` in `regwatch/catalogue.py`, orders search results everywhere: `regwatch sources search`, the search in `regwatch init` and the search box planned for the web app.

- The match ignores case and looks at the name, id, publisher, jurisdiction, kind, access label (`Free`, `Free Key` or `Paid`), region, category, focus areas and description. The id, jurisdiction, kind, region, category and focus areas are matched by their parts, so `us-ca` is the words `us` and `ca`. The publisher also matches its initials, so `fda` matches U.S. Food and Drug Administration and `efsa` matches European Food Safety Authority.
- British and American spellings are treated alike in both directions: `aluminium` and `aluminum`, `labelling` and `labeling`, `flavour` and `flavor`, `colour` and `color`, and the `-ise` forms of `organise`, `authorise`, `harmonise` and `standardise`, among others listed as `SPELLINGS` in `regwatch/catalogue.py`.
- The query is split into words of letters and digits, and every word must match somewhere in the entry. A word of one or two letters, such as `ca` or `eu`, matches only a whole word or a part of an id or code, so `ca` finds California and Canada sources but not every entry that mentions cancer.
- An entry whose id or jurisdiction equals the whole query comes first, and among those the official sources (regulators, legislatures, gazettes and courts) come first, then recall feeds, lobbying registers, data portals and standards bodies, then the rest.
- Otherwise a query word scores 3 when it equals a whole word of a field, 2 when it starts a word and 1 when it appears inside a word, and the best of these for each query word is added up; the highest total comes first, so a whole word always beats the start of a word. Among equal totals, the weighted sum of every field a word matches in decides: the name counts 4, the id and publisher 3, the jurisdiction, kind and access label 2, and the region, category, focus areas and description 1. A source whose name, id and publisher all name what you typed therefore comes before one that only mentions it.
- Equal scores put official sources first and otherwise keep catalogue order, and an empty query returns every entry in catalogue order.

## Choosing a Source

`regwatch sources add` copies an entry into your sources file. The entry becomes these fields:

| sources file field | value |
| --- | --- |
| `source_id`, `name`, `url`, `mechanism`, `cadence` | copied |
| `jurisdiction` | the catalogue code, or the id of a jurisdiction already in your register whose name matches the code's name |
| `method` | `subscribe` for an `email-list` source, otherwise `poll` |
| `notes` | the description |
| `auth`, `key_env` | only for a keyed source: `auth` written as `type:name`, such as `query:api_key` |

A jurisdiction the register does not have is added to the jurisdictions file as a `tracked` record named from `regwatch/data/jurisdiction-names.json`, with its parent added first for a subdivision. An unknown code is named by the code in upper case.
