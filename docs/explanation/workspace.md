# Workspace

This page describes the Regwatch workspace: the source catalogue, the guided setup that builds a register from it, how API keys are kept, how runs are scheduled, the local web app, and the premium features. It explains what each part does and why it is built this way. It is the plan the work is built against, so each section also says which increment delivers it.

## What Changes for a User

Today a user writes a sources file by hand, then runs `capture` and `check`. The workspace replaces the hand-written file with a choice from a curated catalogue, keeps the keys some sources need, sets up the schedule, and adds a browser view of the results.

1. `regwatch init` asks for focus areas and jurisdictions, then shows the catalogue sources that match, each with a short description and whether it is free, needs a free key or is paid.
2. The user ticks the sources to watch, searching as they type, and adds any source the catalogue lacks.
3. For each chosen source that needs a key, setup says where to get one and stores it in the operating system keychain.
4. Setup offers to schedule `capture` and `check` with launchd on macOS or cron elsewhere, and runs them once so the first results exist.
5. `regwatch ui` opens the local web app in the browser, reading the same files.

Every step is also a command, so each one can be redone or scripted on its own.

## The Source Catalogue

The catalogue is package data, `regwatch/data/source-catalogue.json`, a list of sources worldwide that a team watching foods, beverages, supplements, cannabis and hemp, pet food or cosmetics would follow: regulators, legislatures, gazettes, official APIs, recall feeds, standards bodies, trade press and paid intelligence services. Each entry records:

| field | meaning |
| --- | --- |
| `source_id` | unique id, which becomes the snapshot file name when the source is chosen |
| `name`, `publisher` | what it is and who publishes it |
| `jurisdiction`, `region` | where it applies, as an ISO code such as `us`, `us-ca`, `eu`, `gb` or `jp`, and a region for grouping |
| `kind` | regulator, legislature, gazette, court, standards, recalls, data portal, news, industry, aggregator, lobbying disclosure, interest group, supplier, market data or forecast |
| `category` | what the source is about, for grouping: regulation, policy and lobbying, ingredients supply, packaging materials, commodities and forecasts, manufacturing and chemicals, logistics and trade, construction and facilities, or industry news |
| `mechanism`, `url` | how Regwatch reads it and the exact address, as in a sources file |
| `access` | `free`, `free-key` or `paid` |
| `auth`, `key_env`, `signup_url` | for keyed sources, where the key goes in the request, the environment variable that overrides the keychain, and where to get a key |
| `focus_areas` | the focus areas it serves; empty means all |
| `language`, `cadence` | content language and a suggested check frequency |
| `description` | one sentence on what it publishes |
| `verified`, `checked` | whether the address was confirmed live, and when |

Choosing a source copies its entry into the user's own sources file, which stays the single list `capture` and `check` read. The catalogue is never read during a run, so a catalogue update cannot change what a register watches until the user chooses again. A test confirms every entry is valid against the schema and that every `url` passes the same scheme and address checks as the fetch client. Addresses move, so the catalogue records when each was checked, and `regwatch sources verify` rechecks them on demand.

## Search

`regwatch sources search TEXT` ranks entries by how well the text matches the id, name, publisher, jurisdiction, region, kind, category and description, with an exact jurisdiction or id match first. The same ranking serves three places: the search command, the type-ahead in the setup questions (completion through `readline` where the terminal supports it, otherwise a numbered list after each query), and the search box in the web app, which calls the same function through the local server. One ranking function means a source found in one place is found the same way in the others.

## API Keys

Keys are kept in the operating system keychain, never in a configuration file, a sources file, a snapshot, a log or an export.

- macOS: the login keychain, through the `security` command, under the service name `regwatch` and the source's `key_env` as the account.
- Linux: the Secret Service, through the `secret-tool` command from libsecret.
- An environment variable named by the source's `key_env` overrides the keychain, so a scheduled job or a container can supply the key without a keychain. A `key_env` must start with `REGWATCH_KEY_`, so a source cannot name an unrelated variable, and sources that share one must share a host.
- `regwatch keys set SOURCE_ID` prompts for the key without echoing it and stores it. `regwatch keys list` shows which keys are stored, never their values. `regwatch keys remove SOURCE_ID` deletes one. The web app's key page calls the same functions and only ever receives whether a key is present.

Using the system commands keeps Regwatch free of runtime dependencies. A key is added to the request only for its own source, only over `https`, and only in the place its `auth` entry names; a redirect to another host drops it. A key is never written to an error message: the fetch client reports the source and the failure, not the URL with its query.

This replaces the earlier position that Regwatch reads no credential. It still reads none unless a chosen source needs one.

## Automations

`regwatch schedule` installs, shows or removes a recurring run of `capture` and then `check --exit-code`.

- On macOS it writes a launchd agent in `~/Library/LaunchAgents`, loads it with `launchctl bootstrap`, and points it at the interpreter that runs Regwatch now, by absolute path.
- Elsewhere it prints the crontab line and, with `--install`, adds it to the user's crontab between marker comments it can later find and remove.
- The cadence is the most frequent cadence among the chosen sources unless `--every` sets one.
- Each run writes a run record to the state directory: when it started and ended, the counts by status and the exit code. The web app's activity view reads these records.

Nothing is scheduled without the user saying yes, and `regwatch schedule --remove` takes it all out again.

## The Web App

`regwatch ui` starts a local server and opens the browser at it. The server is the standard library's `http.server`, bound to `127.0.0.1` on a free port. The command puts a random token in the URL it opens; the token works once, and the first browser to present it gets a separate session cookie that every later request must carry. It serves the built pages and a small JSON interface over the same files the command line reads and writes. Nothing is sent anywhere else, and the pages load no remote font, script or image.

The pages are built with Next.js and Tailwind CSS as a static export, and the build output ships inside the wheel, so a user needs no Node. Contributors need Node to change the pages; the release workflow builds them before it builds the wheel.

### Layout

- A left navigation rail that collapses to icons, with a search box at the top that searches sources, changes and obligations at once.
- Pages: Overview, Changes, Sources, Obligations, Briefings, Newsletters, Documents, Automations, Keys and Settings.
- Material Design components and spacing, in light blues with a warm accent, with enough contrast for WCAG 2.2 AA in both light and dark mode.
- A sans serif typeface from the system stack, with no text smaller than 11.5 pixels and body text at 15.
- Title Case headings, and labels that say what a control does in plain words.

### What Each Page Does

| page | what it shows or does |
| --- | --- |
| Overview | counts of new, changed, suspicious and failing sources, the next scheduled run, and the highest priority changes |
| Changes | every change and ingest candidate, ranked by focus area, severity and date, with filters and a detail panel |
| Sources | the user's sources with their last status, plus the catalogue with search, filters by region, kind and access, and a button to add one |
| Obligations | the register, read only, with the impacts of recent changes |
| Briefings | the briefings Regwatch already builds, rendered, with export to Markdown, HTML, Word and PDF through the print view |
| Newsletters | a send ready newsletter assembled from the period's changes, as HTML email with a plain text part, ready to paste into a mail tool |
| Documents | documents built from a template that follows a design specification: headings, colours, typeface and logo set once in Settings |
| Automations | the schedule, the run history, and buttons to run a capture and check now |
| Keys | which keyed sources have a key, with set and remove |
| Settings | focus areas, jurisdictions, the document design specification, the language model provider, and the premium toggle |

Regwatch does not send email. A newsletter is a file the user reviews and sends from their own mail tool.

## Generated Copy

A language model can write summaries of changes, the opening of a briefing, and newsletter copy. The stage keeps the conditions recorded in the design decisions: it is off until the user turns it on and names a provider, it reads the provider key from the keychain like any other key, it never logs the key, and its output passes through the same escaping and disclaimer as everything else. Every generated passage is marked as generated in the output and kept next to the facts it was written from, so a reader can check one against the other. The provider is pluggable: Anthropic by default, OpenAI or a local Ollama model by setting. The calls go through the same fetch client, so the address checks and limits apply; a local Ollama model on `127.0.0.1` needs `allow_private_hosts`, which setup explains.

## Premium Features

Some features sit behind a premium toggle so they can later be sold as a bundle: generated copy, newsletters, document templates, and scheduled automations beyond one run a day. The toggle is a setting, `[premium] enabled`, and `regwatch premium on` or `off`; the web app shows locked features with a short note instead of hiding them. Regwatch is MIT licensed, so the toggle is a product boundary, not a lock: anyone can turn it on. Charging for the bundle would come from a hosted web version or a paid support plan, which this page does not design.

## Security

- The catalogue is data reviewed in pull requests; a chosen source still goes through every fetch check.
- The local server listens on loopback only, accepts its launch token once and then requires the session cookie on every request, refuses requests whose `Host` or `Origin` is not its own, and never serves a file outside its build folder and the configured data files.
- Keys stay in the keychain; the JSON interface has no route that returns one.
- Generated text is untrusted like fetched text and is escaped before it reaches any output.

## Increments

Each increment is one pull request with its tests and documentation.

1. The source catalogue and `regwatch sources` (list, search, show, add, verify).
2. Keys in the keychain and keyed fetches, then `regwatch schedule` with run records.
3. The guided setup in `regwatch init`, built from the first two.
4. The local server and the web app pages that read data: Overview, Changes, Sources, Obligations, Briefings, Automations, Keys, Settings.
5. The premium toggle, the generated copy stage, newsletters and document templates.
