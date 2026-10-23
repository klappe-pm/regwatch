# CLI

This page describes the `regwatch` command: its global options, every subcommand with its options, what each one reads and writes, and the exit statuses. It is a reference, so it states facts without instruction. For a guided path see [getting started](../tutorials/getting-started.md).

regwatch flags candidates for human review. It never edits the register or the change log, and nothing it produces is legal advice. The help text of every command ends with that statement.

## Synopsis

```text
regwatch [--version] [--config PATH] <command> [options]
```

## Global Options

| option | meaning |
| --- | --- |
| `--version` | print the version and exit |
| `--config PATH` | the configuration file; default `regwatch.toml` in the current directory. It goes before the subcommand. |
| `-h`, `--help` | print help and exit |

## Exit Statuses

| status | meaning |
| --- | --- |
| 0 | success |
| 1 | the register is invalid, or `capture` stored nothing |
| 2 | a usage, configuration, network, state or file error; the message starts with `error:` |
| 3 | `check --exit-code` found a source that is `NEW`, `CHANGED` or `SUSPICIOUS` |
| 4 | `check --exit-code` found a source that is `ERROR` or `MISSING`; this wins over 3 |

Argument errors detected by the parser also exit with status 2.

## What Gets Written

Commands read the register and never write it. Writes go to exactly these places. `premium` and the Settings page of `ui` change one setting in `regwatch.toml` through the same atomic writer, keep every comment and every other line, and refuse a file they cannot change safely. A path you name is refused if it is a register file, `regwatch.toml`, `seen.json`, `ingest-candidates.json`, or anything inside the state or snapshots directory, whatever its case or links. Paths are compared by identity, not by name.

| command | writes |
| --- | --- |
| `init` | the seven scaffold files, listed under [init](#init), in the project folder |
| `capture` | one file per source in the snapshots directory |
| `check --accept` | `seen.json` in the state directory |
| `ingest` | `ingest-candidates.json` in the state directory |
| `brief --out-dir` | `<name>.md` and `<name>.json` in the directory you name |
| `render` | the rendered files in the directory you name |
| `digest --out`, `report --out`, `report --json`, `export --csv`, `export --json` | the path you name |
| `premium on`, `premium off` | one line in `regwatch.toml`: `[premium] enabled` |
| `ui` | through its Settings page only, one line in `regwatch.toml`: `[profile] focus_areas` or `[premium] enabled` |

## `init`

Creates a project: `regwatch.toml`, an empty register that validates, and a copy of the focus catalogue. It asks its questions on the terminal with plain prompts and needs no other program. Every question has a flag, a question whose flag is given is not asked, and `--yes` takes the default for every question that has no flag, so the command can run without a terminal. It ignores the global `--config` option: the configuration file is always `regwatch.toml` in the project folder.

| option | meaning |
| --- | --- |
| `--dir PATH` | the project folder, created if needed. Without it the current folder is the default answer, and `--yes` takes it. In your home directory the folder is asked for, or with `--yes` the command stops, and the home directory itself is always refused. |
| `--focus ID` | a focus area, by id or by its number in the list; repeat for more. Default none. |
| `--term TERM` | a custom term that counts as a focus; repeat for more. Default none. |
| `--jurisdiction NAME` | a jurisdiction to watch; repeat for more. Its id is made from the name. Default none. |
| `--allow-file-root FOLDER` | allow `file` sources under this folder; repeat for more. Default none, so local files are refused. The root of a file system, your home directory and any parent of it are refused. A relative folder is relative to the project folder. |
| `--contact TEXT` | an email address or web page, 1 to 200 printable ASCII characters, written into the User-Agent header as `regwatch/<version> (+TEXT)`. Default: the standard header. |
| `--example` | offer the invented example jurisdictions (Northland, Southvale and their regions) as the default answer. They are never offered otherwise. |
| `--yes` | take the default for every question without a flag and do not ask to confirm |
| `--force` | replace files that already exist |

Interactive answers are separated by commas. A flag value is one item, so a name that contains a comma is possible only as a flag. An unusable answer is explained and asked again. A closed input stream stops the command with `error:` and a hint to use flags or `--yes`.

Files written, all inside the project folder:

| file | holds |
| --- | --- |
| `regwatch.toml` | the register paths, the state directory, the `[profile]` table and, only when answered, `[fetch]` |
| `register/obligations.csv` | the header row only |
| `register/jurisdictions.json` | one tracked jurisdiction per name |
| `register/categories.json`, `register/sources.json` | empty lists |
| `register/portfolio.json` | the name `My portfolio` and no products |
| `focus-areas.json` | a copy of the shipped catalogue, for you to edit |

Before asking anything but the folder, `init` lists the files that already exist. Without `--force` it stops, exits 2 and changes nothing. It also refuses, even with `--force`, to write through a symbolic link, and it prints a summary and asks for confirmation before writing unless `--yes` is given; declining exits 2 and writes nothing. `init` looks at the folder again right before it writes, and without `--force` it creates each file exclusively, so a file or link that appears while it is asking is left alone and the command exits 2. With `--force` each file is written atomically. The finished project validates with `errors=0`.

## `config`

`regwatch config show` prints the effective configuration: every setting after defaults and path resolution, in the form of the configuration file. Paths are absolute. It prints the register files, the state and snapshots directories, the fetch limits with the User-Agent and `allowed_file_roots` (a comment says when the list is empty and every file source is refused), the ingest filters, and the profile with the catalogue in use, one comment line for each focus area with its label and number of terms, then `[premium] enabled`. It does not read the register. It exits 2 if the configuration is invalid or names an unknown focus area.

```text
regwatch config show
```

## `validate`

Checks every register file against the field rules and prints one `ERROR` line per problem. Exits 1 when there is any error.

```text
regwatch validate
```

## `coverage`

Lists each jurisdiction with its coverage level and the number of obligation rows. Prints a `WARN` line for a jurisdiction marked `confirmed` that has no rows.

```text
regwatch coverage
```

## `list`

Lists obligations with their effective date, jurisdiction, status and title.

| option | meaning |
| --- | --- |
| `--jurisdiction ID` | only this jurisdiction |
| `--category ID` | only obligations that list this category |
| `--status STATUS` | only this status |
| `--upcoming N` | only obligations effective from today to N days ahead, soonest first |

## `portfolio`

Lists the products that obligations are matched against, with their categories and markets.

## `capture`

Fetches non-manual sources and stores the raw content as snapshots. A `manual` source is skipped. Exits 1 if no source was stored.

| option | meaning |
| --- | --- |
| `--source ID` | only this source; exits 2 if the id is not in the register |

## `check`

Reduces each source to a signal, hashes it and compares the hash with the last accepted one. Without `--fetch` it reads the stored snapshot, so the result is repeatable offline.

| option | meaning |
| --- | --- |
| `--fetch` | fetch each source now instead of reading its snapshot |
| `--accept` | record the current hashes as the new baseline |
| `--accept-suspicious` | with `--accept`, also record sources reported `SUSPICIOUS`; without it they are not recorded |
| `--exit-code` | exit with status 3 when any source is `NEW`, `CHANGED` or `SUSPICIOUS`, and with status 4 when any source is `ERROR` or `MISSING` |
| `--source ID` | only this source |

Each line shows a status, the source id, where the content came from (`snapshot`, `live` or `manual`) and the first 12 characters of the hash.

| status | meaning |
| --- | --- |
| `NEW` | no accepted hash exists yet |
| `CHANGED` | the hash differs from the accepted one |
| `UNCHANGED` | the hash matches |
| `MISSING` | no snapshot exists and `--fetch` was not given |
| `MANUAL` | the source is read by hand and is never fetched |
| `SUSPICIOUS` | the signal is empty, or is shorter than half of the accepted signal (when that was at least 20 characters); the reason follows. It is reported even if the hash also changed. |
| `ERROR` | the fetch failed or the content could not be parsed safely; the reason follows |

`NEW`, `CHANGED` and `SUSPICIOUS` are changes for `--exit-code` (status 3), and `ERROR` and `MISSING` are unverified sources (status 4). `--accept` records the hash and the signal length of every source that produced one, except `SUSPICIOUS` sources unless `--accept-suspicious` is also given.

## `ingest`

Parses a Federal Register style API response into candidate change log events and writes them, flagged unconfirmed, to the state directory. It needs `--fetch` or `--from-file`; with neither it exits 2 and writes nothing.

| option | meaning |
| --- | --- |
| `--fetch` | call the API configured in `[ingest]` |
| `--from-file PATH` | parse a saved response instead |
| `--since DAYS` | look back this many days; default 365 |

## `impact`

Flags candidate impacts of obligations on products, worst first. Each pair is printed with the reasons it matched. With focus areas set, pairs that match a focus area are printed first, each with a `focus:` reason, then a blank line, the heading `Outside your focus areas` and the rest in the same order. Nothing is left out. The last line then adds how many pairs fall in each group.

| option | meaning |
| --- | --- |
| `--product ID` | only this product |
| `--severity LEVEL` | only `act-now`, `high`, `watch` or `info` |

## `themes`

Reads the impacts through the themes in your themes file and prints one finding per theme that matches an obligation or a product.

## `brief`

Builds a briefing document. With focus areas set, items that match them come first and the rest follow under an `Outside Your Focus Areas` heading; see the [focus catalogue](focus-catalogue.md). Without `--out-dir` it prints Markdown to standard output. With it, it writes `<name>.md` and `<name>.json`, where the JSON is the document model that `render` reads.

| option | meaning |
| --- | --- |
| `--kind KIND` | `tiered` (default), `daily` or `weekly` |
| `--tier TIER` | for `tiered`: `v1` headlines, `v2` adds context and citations, `v3` (default) adds actions, affected products and unconfirmed candidates |
| `--since-days N` | for `tiered`: window the recent developments section to N days |
| `--recent N` | for `tiered`: how many recent events to show; default 8 |
| `--fetch` | for `daily`: fetch sources instead of reading snapshots |
| `--out-dir DIR` | write the files here instead of printing |
| `--name STEM` | the file stem; default `regwatch-briefing-<tier>`, `regwatch-daily-brief` or `regwatch-weekly-brief`; 1 to 100 letters, digits, dots, hyphens and underscores, not starting with a dot or hyphen, so it cannot contain a path separator |

## `render`

Renders a saved document model into delivery formats. It does not need a register, and works even when the configuration file does not exist.

| option | meaning |
| --- | --- |
| `MODEL` | path to the JSON model written by `brief` |
| `--formats LIST` | comma list of `md`, `web`, `newsletter`, `docx`; default all |
| `--out-dir DIR` | where to write; default the current directory |
| `--tags LIST` | tags for the web post front matter; letters, digits, hyphens and underscores only; default `regulatory` |

| format | files |
| --- | --- |
| `md` | `<stem>.md` |
| `web` | `<stem>-webpost.md`, Markdown with front matter and `draft: true` |
| `newsletter` | `<stem>-newsletter.html` and `<stem>-newsletter.txt` |
| `docx` | `<stem>.docx` |

Every format ends with the disclaimer, whatever the model contains. Markdown and web output backslash-escape every Markdown metacharacter, HTML and Word output escape all text, and every value loses its control characters first.

## `digest`

Writes a Markdown digest of the register: obligations effective soon, then every obligation grouped by jurisdiction.

| option | meaning |
| --- | --- |
| `--window N` | upcoming horizon in days; default 365 |
| `--out PATH` | write here instead of printing |

## `report`

Writes a change-and-due alert: sources flagged `NEW` or `CHANGED`, sources missing a snapshot, sources in error, and obligations effective within the window.

| option | meaning |
| --- | --- |
| `--window N` | upcoming horizon in days; default 365 |
| `--fetch` | fetch sources instead of reading snapshots |
| `--out PATH` | write the Markdown here instead of printing |
| `--json PATH` | also write the machine-readable report |

## `export`

Writes one flat record per obligation, joined with its detail record when there is one.

| option | meaning |
| --- | --- |
| `--csv PATH` | required; the CSV output path |
| `--json PATH` | also write the records as JSON |

Every CSV field is quoted. A cell, or any part of a cell after a `;`, a `,`, a tab or a line break, that begins with `=`, `+`, `-`, `@`, a tab, a carriage return or a line feed (also after leading whitespace, and in the fullwidth forms) gets a leading apostrophe in the CSV so a spreadsheet does not run it as a formula; the JSON is unchanged. The columns are `obligation_id`, `jurisdiction`, `status`, `effective_date`, `topics`, `summary`, `impacts`, `implications`, `action`, `source_url` and `citations`.

## `ui`

Starts the local web app and opens it in the browser. The server is the standard library's `ThreadingHTTPServer`, bound to `127.0.0.1` only, and runs until Ctrl+C. It reads the project named by `--config` the same way the other commands do, checks the configuration before it starts, and fetches nothing. See [use the web app](../how-to-guides/use-the-web-app.md) and the [security model](../explanation/security-model.md#the-local-server).

| option | meaning |
| --- | --- |
| `--port N` | the port on `127.0.0.1`, 0 to 65535; default 0, a free port chosen by the system |
| `--no-open` | print the address but do not open a browser |

It prints `regwatch ui: serving <project folder> at http://127.0.0.1:<port>/?token=<token>`. The token is 43 random URL-safe characters from `secrets.token_urlsafe`, new for each run. The command exits 0 when stopped, and 2 when the configuration is invalid, the port is taken or out of range, or the installation lacks the built pages.

```text
regwatch ui --port 8765 --no-open
```

The JSON interface the pages use is under `/api/`. Every route needs the token, and a route that changes something needs a JSON body and a same-origin `Origin` header.

| route | method | answers |
| --- | --- | --- |
| `/api/status` | GET | the version, the project folder name and whether premium is on |
| `/api/overview` | GET | source counts by status, the sources to review, the highest priority impacts, obligations effective within 90 days, the schedule and supply chain signals |
| `/api/changes` | GET | every source result, every candidate impact and the unconfirmed ingest candidates, cleaned again |
| `/api/sources` | GET | the sources in the register with the status of each stored snapshot |
| `/api/catalogue` | GET | catalogue entries for `q`, filtered by `category`, `region`, `kind` and `access`, with the values present for each filter |
| `/api/catalogue/add` | POST | adds `source_id` from the catalogue to the sources file |
| `/api/obligations` | GET | every obligation with its candidate impacts |
| `/api/briefing` | GET | the document model for `kind` (`tiered`, `daily` or `weekly`) and `tier` (`v1`, `v2` or `v3`) |
| `/api/briefing/export` | GET | the same briefing as a download in `format` `md`, `html` or `docx` |
| `/api/automations` | GET | whether premium is on, the schedule and the run records |
| `/api/automations/run` | POST | runs a capture and a check now |
| `/api/keys` | GET | for each keyed source, its id, its environment variable and whether a key is stored; never a key |
| `/api/keys/set` | POST | stores `key` for `source_id`; answers only whether one is stored |
| `/api/keys/remove` | POST | removes the key for `source_id` |
| `/api/settings` | GET | the focus areas, the focus catalogue and whether premium is on |
| `/api/settings/focus` | POST | sets `[profile] focus_areas` to `focus_areas`, ids from the catalogue |
| `/api/settings/premium` | POST | sets `[premium] enabled` to `enabled`, true or false |
| `/api/search` | GET | up to 8 sources, changes and obligations each that match `q` |

A route whose feature has not shipped (the catalogue, keys, the schedule, run records and supply chain signals) answers `{"available": false, "command": ...}`, naming the command that will fill it. An error is a JSON object with one short `error` message that never holds file contents: 400 for a bad request, 403 for a refused host, origin or token, 404 for an unknown route or file, 405 for a wrong method, 409 for a setting that cannot be saved, 413 for a body over 65,536 bytes, 415 for a body that is not JSON, 422 for an invalid register, and 500 otherwise.

## `premium`

Turns the premium features on or off, or shows whether they are on: newsletters, document templates, generated copy and runs more often than once a day. While premium is off the web app shows these features with a lock and a note instead of hiding them. Regwatch is MIT licensed, so this is a product boundary, not a lock.

| argument | meaning |
| --- | --- |
| `on` | set `[premium] enabled = true` in `regwatch.toml` |
| `off` | set `[premium] enabled = false` |
| `status` | change nothing |

Each prints `regwatch premium: on` or `regwatch premium: off`, and while off, the features that are locked. The change keeps every comment and every other line of the file. A file whose `[premium]` setting is written in a form the command cannot change safely, such as the dotted key `premium.enabled`, exits 2 and is left unchanged.

```text
regwatch premium on
```
