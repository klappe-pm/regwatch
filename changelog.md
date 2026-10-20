# changelog

All notable changes to this project are documented in this file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## unreleased

### added

- Package scaffold: `pyproject.toml` with the hatchling build backend and the `regwatch` console script. There are no runtime dependencies.
- The `regwatch` command with the subcommands `validate`, `coverage`, `list`, `portfolio`, `capture`, `check`, `ingest`, `impact`, `themes`, `brief`, `render`, `digest`, `report` and `export`, and later `init` and `config`. [cli reference](docs/reference/cli.md) documents each.
- A TOML configuration file that names the register files, the state directory, the fetch limits and the ingest filters. [configuration](docs/reference/configuration.md) lists every key.
- The register data model: obligations as CSV, and jurisdictions, categories, sources and a portfolio as JSON, with optional detail, change log, enforcement and theme files. Field rules ship as package data in `regwatch/data/schema.json`. [data files](docs/reference/data-files.md) describes each file.
- Change detection by content hash for `api`, `rss`, `html`, `email-list` and `manual` sources, with snapshots for repeatable offline checks and an explicit `--accept` step that records the baseline.
- One fetch client that allows only `https` and `file` URLs, refuses hosts that resolve to loopback, link-local, private or other non-public addresses and connects to the address it vetted, follows at most 5 redirects and only to `https`, always verifies certificates, enforces a per-operation timeout, a total deadline and a size limit, ignores proxy variables, reads `file` sources only from regular files under `allowed_file_roots`, and never starts a program.
- Cleaning of untrusted text: control and escape characters removed, links validated, Markdown output escaped, and CSV formula cells neutralised.
- Change detection that cannot be hidden: a `SUSPICIOUS` status for an empty or sharply shorter source, an `--accept-suspicious` flag, and exit status 4 from `check --exit-code` for a source in `ERROR` or `MISSING`.
- Write protection by file identity, covering `regwatch.toml` and the state files as well as the register.
- Defensive parsing of fetched content: JSON through `json`, HTML through the standard library tokenizer, and feeds through ElementTree after any DTD or entity declaration is refused.
- Candidate ingest from a Federal Register style API response, flagged unconfirmed.
- Candidate impact analysis that joins obligations to products by jurisdiction exposure, scope and shared categories, terms or claims, with severity scoring and optional themes.
- Daily, weekly and tiered briefings built as one document model, and renderers for Markdown, a web post, an HTML and plain text newsletter, and a Word document. Every output carries the disclaimer that nothing is legal advice.
- A synthetic example register, snapshots and ingest response under `examples/`.
- Documentation in two trees arranged by Diátaxis quadrant: `docs/` for people who use regwatch and `developer-docs/` for people who change it.
- A test suite that blocks the network and checks repository hygiene, with a coverage report.
- `regwatch init`, a configuration flow that scaffolds a project: `regwatch.toml`, an empty register that validates, and an editable copy of the focus catalogue. It asks on the terminal with plain prompts and no new dependency, every question has a flag, `--yes` takes the defaults so it can be scripted, and `--example` offers the invented example jurisdictions. It asks for the project folder (never assuming the home directory), focus areas and custom terms, jurisdictions, whether local file sources are allowed and from which folders (default none), and a User-Agent contact. It shows a summary and asks before writing, refuses to overwrite existing files without `--force`, never writes through a symbolic link, and refuses a file root that is a file system root or the home directory. [cli reference](docs/reference/cli.md) documents it.
- A shipped, editable focus catalogue in package data with eight areas: non-alcoholic beverages, alcoholic beverages, cannabis and hemp products, traditional foods, dietary supplements, infant food, pet food and cosmetics. [focus catalogue](docs/reference/focus-catalogue.md) describes the format and the matching rules.
- A `[profile]` table in `regwatch.toml` that records the chosen focus areas, custom terms and an optional catalogue path. Impact analysis, the tiered briefing and the daily and weekly briefs rank candidates that match a focus area first, and list the rest under an outside-your-focus-areas heading. Nothing is dropped.
- `regwatch config show`, which prints the effective configuration, including focus areas, the catalogue in use and the allowed file roots.
- A how-to guide, [set your focus areas](docs/how-to-guides/set-your-focus-areas.md), and a getting started tutorial that begins with `regwatch init`.

### security

- CSV export: every field is quoted, and a part of a cell that would run as a formula is neutralised after a `;`, a `,`, a tab or a line break, after leading whitespace or invisible format characters, and in the fullwidth forms, so a spreadsheet that splits on semicolons cannot be made to run a formula.
- Terminal output: every line regwatch prints goes through one function that removes control characters and invisible format characters, `FetchError` cleans its own message (a server controls part of it), and `regwatch validate` refuses control characters in register text. A hostile status line, register value or catalogue label can no longer clear the screen, set a window title or add a line.
- Text cleaning removes bidirectional overrides and isolates and zero-width characters, and a link whose host is not plain ASCII, or that holds an invisible format character, is refused.
