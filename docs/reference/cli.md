# CLI

This page describes the `regwatch` command: its global options, every subcommand with its options, what each one reads and writes, and the exit statuses. It is a reference, so it states facts without instruction. For a guided path see [getting started](../tutorials/getting-started.md).

regwatch flags candidates for human review. It never edits your obligations or the change log, and nothing it produces is legal advice. The help text of every command ends with that statement.

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
| 3 | `check --exit-code` or `run` found a source that is `NEW`, `CHANGED` or `SUSPICIOUS` |
| 4 | `check --exit-code` or `run` found a source that is `ERROR` or `MISSING`, `run` could not capture a source, or `sources verify` could not fetch an address; this wins over 3 |

Argument errors detected by the parser also exit with status 2.

## What Gets Written

Commands read the register. Only `sources add` and `sources remove` write it, and only the sources and jurisdictions files. Writes go to exactly these places. A path you name is refused if it is a register file, `regwatch.toml`, `seen.json`, `ingest-candidates.json`, or anything inside the state or snapshots directory, whatever its case or links. Paths are compared by identity, not by name.

| command | writes |
| --- | --- |
| `init` | the seven scaffold files, listed under [init](#init), in the project folder |
| `sources add`, `sources remove` | the sources file, and for `add` the jurisdictions file when a jurisdiction is missing |
| `capture` | one file per source in the snapshots directory |
| `check --accept` | `seen.json` in the state directory |
| `ingest` | `ingest-candidates.json` in the state directory |
| `brief --out-dir` | `<name>.md` and `<name>.json` in the directory you name |
| `render` | the rendered files in the directory you name |
| `digest --out`, `report --out`, `report --json`, `export --csv`, `export --json` | the path you name |
| `run` | snapshots, and one run record in `runs/` in the state directory |
| `schedule --install`, `schedule --remove` | on macOS `~/Library/LaunchAgents/io.github.klappe-pm.regwatch.plist`; elsewhere your crontab, between regwatch's marker lines only |

`keys set` and `keys remove` change the system keychain, never a file.

## `init`

Creates a project: `regwatch.toml`, a register that validates with the sources you choose, and a copy of the focus catalogue, then offers to store keys, schedule runs and run once. It asks its questions on the terminal with plain prompts and needs no other program. Every question has a flag, a question whose flag is given is not asked, and `--yes` takes the default for every question that has no flag, so the command can run without a terminal. It ignores the global `--config` option: the configuration file is always `regwatch.toml` in the project folder.

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
| `--sources ID,ID` | catalogue sources to watch, separated by commas; an empty value chooses none. Without it the sources are chosen interactively, and `--yes` chooses none. An id not in the catalogue exits 2 and writes nothing. |
| `--schedule`, `--no-schedule` | after writing, install a recurring run as `schedule --install` does, or do not ask. Without either the question is asked, and `--yes` does not schedule. |
| `--first-run`, `--no-first-run` | after writing, run `regwatch run` once, or do not ask. Without either the question is asked when sources were chosen, and `--yes` does not run. With a first run, the exit status is that of `run`. |

The questions come in this order: the project folder, focus areas, custom terms, jurisdictions, sources, local file roots, the contact, and the confirmation. After the files are written come the keys of chosen keyed sources, the schedule and the first run. A closed input stream after the files are written counts as no.

Choosing sources: `init` lists the catalogue sources that fit the chosen focus areas and jurisdictions, grouped by category and then region, each numbered with its name, `Free`, `Free Key` or `Paid`, id and description. An entry fits a focus area when it lists the area or lists none, and fits a jurisdiction when its code, the country above a subdivision, or the name of either matches the jurisdiction's id or name; international entries always fit. At the prompt, numbers or ids separated by commas or spaces select a source or unselect a selected one, any other words search the whole catalogue with the [one ranking](source-catalogue.md#search) and print the best 20 results numbered (the numbers then refer to that list), `+` asks for the fields of a source the catalogue lacks and checks them like a catalogue entry, and Enter finishes. When standard input is a terminal, Tab completes catalogue ids and names.

Keys: for each chosen source that needs a key, `init` prints where to get one and, unless `--yes` is given or no keychain tool exists, asks whether to store it now and reads it without echo, as `keys set` does. Otherwise it prints the `keys set` command and the environment variable to use.

Interactive answers are separated by commas. A flag value is one item, so a name that contains a comma is possible only as a flag. An unusable answer is explained and asked again. A closed input stream stops the command with `error:` and a hint to use flags or `--yes`.

Files written, all inside the project folder:

| file | holds |
| --- | --- |
| `regwatch.toml` | the register paths, the state directory, the `[profile]` table and, only when answered, `[fetch]` |
| `register/obligations.csv` | the header row only |
| `register/jurisdictions.json` | one tracked jurisdiction per name, and a tracked jurisdiction for each chosen source whose jurisdiction is not among them |
| `register/sources.json` | the chosen sources, as `sources add` writes them |
| `register/categories.json` | an empty list |
| `register/portfolio.json` | the name `My portfolio` and no products |
| `focus-areas.json` | a copy of the shipped catalogue, for you to edit |

Before asking anything but the folder, `init` lists the files that already exist. Without `--force` it stops, exits 2 and changes nothing. It also refuses, even with `--force`, to write through a symbolic link, and it prints a summary and asks for confirmation before writing unless `--yes` is given; declining exits 2 and writes nothing. `init` looks at the folder again right before it writes, and without `--force` it creates each file exclusively, so a file or link that appears while it is asking is left alone and the command exits 2. With `--force` each file is written atomically. The finished project validates with `errors=0`.

## `config`

`regwatch config show` prints the effective configuration: every setting after defaults and path resolution, in the form of the configuration file. Paths are absolute. It prints the register files, the state and snapshots directories, the fetch limits with the User-Agent and `allowed_file_roots` (a comment says when the list is empty and every file source is refused), the ingest filters, and the profile with the catalogue in use, one comment line for each focus area with its label and number of terms. It does not read the register. It exits 2 if the configuration is invalid or names an unknown focus area.

```text
regwatch config show
```

## `sources`

Reads the [source catalogue](source-catalogue.md): the file shipped with regwatch, followed by the file named in `[catalogue] extra` when there is one. `list`, `search`, `show` and `verify` work without a configuration file and then read the shipped catalogue only. Each source is shown with its access as `Free`, `Free Key` or `Paid`.

| action | meaning |
| --- | --- |
| `list` | one line per entry: id, access, jurisdiction, category and name, in catalogue order |
| `search TEXT` | the entries that match `TEXT`, best match first, ranked as the source catalogue page describes |
| `show ID` | every field of one entry |
| `add ID [ID ...]` | copy entries into your sources file, adding any jurisdiction they need |
| `remove ID` | remove a source from your sources file |
| `verify [ID ...]` | fetch the address of each entry, every entry when no id is given, and print `ok` with the size or `failed` with the reason |

| option | applies to | meaning |
| --- | --- | --- |
| `--region REGION` | `list` | only this region |
| `--jurisdiction CODE` | `list` | only this jurisdiction and its subdivisions, so `us` also lists `us-ca` |
| `--kind KIND` | `list` | only this kind |
| `--category CATEGORY` | `list` | only this category |
| `--access ACCESS` | `list` | only `free`, `free-key` or `paid` |
| `--focus ID` | `list` | entries for this focus area, including entries that list no area, which serve every area |
| `--chosen` | `list` | only entries whose id is in your sources file |
| `--json` | `list`, `search`, `show` | print JSON instead of lines: an object with `count` and `sources`, or for `show` one entry. Each entry has every catalogue field and `access_label`. |

`add` never overwrites a different entry: when the sources file already has the id with other content, it exits 2 and writes nothing. An entry already present unchanged is reported `present`. `add` and `remove` need a configuration file. `remove` refuses a source that an obligation row cites, and leaves its snapshot and accepted hash in the state directory. `verify` uses the fetch client with the `[fetch]` settings, or the defaults without a configuration, exits 4 when any address fails, and never changes the catalogue. An id that is not in the catalogue exits 2.

```text
regwatch sources search "food recalls"
```

```text
regwatch sources add us-fda-recalls-rss gb-fsa-food-alerts-api
```

## `keys`

Keeps the keys that keyed sources need in the system keychain: the macOS login keychain through `security`, or the Secret Service on Linux through `secret-tool`. An environment variable named by the source's `key_env` overrides the keychain. No action ever prints a key. The [security model](../explanation/security-model.md#api-keys) explains how a key is kept off command lines.

| action | meaning |
| --- | --- |
| `set SOURCE_ID` | print where to get a key, prompt for it without echo, store it and read it back to confirm |
| `list` | each keyed source with `stored`, `set in the environment`, `missing` or `missing (no keychain tool)`; with a configuration the keyed sources of your sources file, without one the keyed catalogue sources |
| `remove SOURCE_ID` | delete the stored key; says so when the environment variable still supplies one |

`SOURCE_ID` is a keyed source in your sources file or in the catalogue. A source that needs no key, a key with a space, quote, backslash or non-ASCII character, or a machine with neither keychain tool exits 2; the last names the environment variable to use instead.

## `run`

Captures every source, then checks every source against its snapshot, as `capture` followed by `check --exit-code` would, and writes a run record to `runs/` in the state directory: the start and end times, the number of sources, how many were captured, how many failed to capture, the counts by status and the exit status. The newest 500 records are kept. It does not accept a baseline. Exit status 3 means a change to review, and 4 means a source could not be captured or verified. This is the command a schedule runs.

```text
regwatch run
```

## `schedule`

Installs, shows or removes a recurring `regwatch run`. On macOS it is a launchd agent with the label `io.github.klappe-pm.regwatch`, loaded with `launchctl bootout` then `launchctl bootstrap gui/<uid>`. Elsewhere it is a block in your crontab between marker comments, so it can be found and removed later; every other line of the crontab is kept. The job runs `<python> -m regwatch --config <this config> run` from the project folder, with the interpreter that runs regwatch now named by absolute path, and appends its output to `schedule.log` in the state directory. With no action it shows the schedule.

| option | meaning |
| --- | --- |
| `--install` | install the schedule, replacing an earlier one |
| `--remove` | remove the schedule |
| `--show` | show whether it is installed and what it runs; the default |
| `--every CADENCE` | `hourly`, `daily` or `weekly`; default the most frequent cadence among your sources, or `daily` |
| `--dry-run` | print the file or the crontab block and the commands, and change nothing |

Cron times are a minute past the start of the period: `17 * * * *`, `17 6 * * *` and `17 6 * * 1`. A launchd agent repeats every 3,600, 86,400 or 604,800 seconds. A crontab that cannot be read for a reason other than there being none is left unchanged and the command exits 2.

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
