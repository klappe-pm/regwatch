<p align="center">
  <a href="https://github.com/klappe-pm/regwatch"><img src="https://raw.githubusercontent.com/klappe-pm/regwatch/main/.github/regwatch-banner.svg" alt="A terminal window: regwatch check is typed, the regwatch wordmark appears, and each watched source reports changed or unchanged" width="760"></a>
</p>

<h1 align="center">Regwatch</h1>

<p align="center">
  Watch regulatory sources and flag what changes for your products, for a person to review.
</p>

<p align="center">
  <a href="https://pypi.org/project/regwatch/"><img src="https://img.shields.io/pypi/v/regwatch?style=flat-square&color=3ddc84&labelColor=162233&label=PyPI" alt="PyPI version"></a>
  <a href="https://pypi.org/project/regwatch/"><img src="https://img.shields.io/pypi/pyversions/regwatch?style=flat-square&color=5aa9ff&labelColor=162233&label=Python" alt="Python versions"></a>
  <a href="https://github.com/klappe-pm/regwatch/releases"><img src="https://img.shields.io/github/v/release/klappe-pm/regwatch?style=flat-square&color=3ddc84&labelColor=162233&label=release" alt="Latest release"></a>
  <a href="https://github.com/klappe-pm/regwatch/blob/main/LICENSE"><img src="https://img.shields.io/github/license/klappe-pm/regwatch?style=flat-square&color=5aa9ff&labelColor=162233&label=license" alt="MIT license"></a>
  <a href="https://github.com/klappe-pm/regwatch/blob/main/pyproject.toml"><img src="https://img.shields.io/badge/dependencies-none-3ddc84?style=flat-square&labelColor=162233" alt="No runtime dependencies"></a>
  <a href="https://github.com/klappe-pm/regwatch/blob/main/docs/README.md"><img src="https://img.shields.io/badge/focus%20areas-8-5aa9ff?style=flat-square&labelColor=162233" alt="Eight shipped focus areas"></a>
</p>

<p align="center">
  <a href="#installation">Installation</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#how-it-works">How It Works</a> ·
  <a href="#commands">Commands</a> ·
  <a href="https://github.com/klappe-pm/regwatch/blob/main/docs/README.md">Docs</a> ·
  <a href="#contributing">Contributing</a>
</p>

---

If you sell regulated goods such as food, drinks or cosmetics, you already know the problem. The rules that touch your products change in official feeds, agency pages, gazettes and mailing list archives. Reading all of them every day is tedious work that people skip, and a change you miss is a change you hear about late.

Regwatch does the tedious part. It reads the sources you list, notices when one has changed, compares what you know about your products with what you know about the rules, and puts the likely matches at the top of a short briefing. It stops there: it flags candidates for human review, it never edits your register, and nothing it produces is legal advice.

## Why Regwatch?

| Without Regwatch | With Regwatch |
| --- | --- |
| Open every feed, agency page and gazette by hand, every day | List the sources once; `check` hashes each one and says which changed |
| An empty or truncated page reads as "no news" | A source that turns empty or much shorter is reported `SUSPICIOUS`, and a baseline is recorded only when you accept it |
| Work out in your head which products a rule touches | Impact analysis joins obligations to products by jurisdiction, scope and shared categories, terms or claims, ranked by severity |
| A tool that rewrites the register you curated | The register is yours; Regwatch never writes it, and candidates from a feed stay unconfirmed in a separate state directory |
| Write each briefing from scratch | Build a daily, weekly or tiered briefing from your own data and render it as Markdown, a web post, a newsletter or a Word document |

## Who This Is For

- People who track rules such as food ingredient and labeling law for a product line.
- Small teams that keep a register of obligations and want a short, repeatable briefing.
- Anyone who needs a record of what changed and when, that can be checked again offline from stored snapshots.
- Anyone who wants a tool that flags candidates and leaves the decision to a qualified person.

## Highlights

- **Change detection that cannot be hidden.** Each source is reduced to a signal, hashed and compared with the last accepted hash. An empty or sharply shorter source is `SUSPICIOUS`, and `--accept` is always an explicit step.
- **Candidate impacts, ranked by your focus areas.** Eight shipped focus areas, plus words of your own, move the matches that matter to you to the top. Nothing is dropped; the rest is listed after them.
- **A register you own.** Obligations are a CSV file and the rest are JSON catalogs, checked against field rules by `validate`. Regwatch reads them and never writes them.
- **Four output formats.** One document model renders to Markdown, a web post, an HTML and plain text newsletter, and a Word document. Every output ends with the disclaimer.
- **A careful network client.** Only `https` and `file` URLs, no non-public addresses, certificates always verified, and a total deadline, size limit and redirect cap on every fetch. See the [Security Model](https://github.com/klappe-pm/regwatch/blob/main/docs/explanation/security-model.md).
- **Safe output.** Text from outside is cleaned before it is stored, printed or rendered, Markdown is escaped, and CSV cells a spreadsheet would run as formulas are neutralised.
- **Nothing to install but Python.** Pure standard library at runtime, no dependencies.

## Installation

Regwatch needs Python 3.11 or newer. [pipx](https://pipx.pypa.io/) is the easiest way to get a command-line tool onto your path:

```bash
pipx install regwatch
```

Nothing is published to PyPI yet. Until the first release, install from GitHub:

```bash
pipx install git+https://github.com/klappe-pm/regwatch
```

Then check that it runs:

```bash
regwatch --version
```

## Quick Start

Set up your own project. `regwatch init` asks where it lives, which focus areas apply to your business (non-alcoholic beverages, alcoholic beverages, cannabis and hemp products, traditional foods, dietary supplements, infant food, pet food, cosmetics), which jurisdictions to watch, whether local files may be read as sources, and a contact for the User-Agent header:

```bash
regwatch init --dir ~/my-regwatch
```

Check the new project and see the configuration Regwatch will use:

```bash
regwatch --config ~/my-regwatch/regwatch.toml validate
```

```bash
regwatch --config ~/my-regwatch/regwatch.toml config show
```

Then describe your products in `register/portfolio.json`, list your rules in `register/obligations.csv` and your sources in `register/sources.json`. The [Getting Started](https://github.com/klappe-pm/regwatch/blob/main/docs/tutorials/getting-started.md) tutorial walks through every step, and the [synthetic example register](https://github.com/klappe-pm/regwatch/tree/main/examples) in the repository lets you see the engine work before you have a register of your own. Every jurisdiction, rule, source and product in it is invented.

## How It Works

A project is an ordinary folder. This is what `regwatch init` gives you:

```text
my-regwatch/
├── regwatch.toml            the configuration: register paths, fetch limits, focus areas
├── focus-areas.json         an editable copy of the focus catalogue
└── register/
    ├── obligations.csv      one row per obligation in one jurisdiction
    ├── jurisdictions.json   the places you watch, as a tree
    ├── categories.json      the topics obligations and products share
    ├── sources.json         the feeds, pages and APIs to watch
    └── portfolio.json       your products
```

A run is a series of stages. Each reads the output of the one before it from files, so you can run any stage alone, in any order, and repeat it:

| Stage | Command | What it does |
| --- | --- | --- |
| Validate | `validate` | Checks the register against the field rules, so an analysis never runs on a dangling reference. |
| Capture | `capture` | Fetches sources into stored snapshots. The only stage that needs the network, and optional. |
| Check | `check` | Reduces each source to a signal, hashes it and compares it with the last accepted hash. |
| Ingest | `ingest` | Turns a Federal Register style response into candidate events, flagged unconfirmed. |
| Impact | `impact` | Matches obligations against products and ranks the matches by severity and focus. |
| Brief | `brief` | Builds a daily, weekly or tiered briefing as one document model. |
| Render | `render` | Turns a saved briefing into Markdown, a web post, a newsletter or a Word document. |

Regwatch flags candidates for human review. A qualified person must confirm each flagged item against the primary source text and current facts before anyone relies on it.

## Commands

| Command | What it does |
| --- | --- |
| `regwatch init` | Creates a project: configuration, an empty register and your focus areas. |
| `regwatch config show` | Prints the effective configuration, including focus areas and allowed file roots. |
| `regwatch validate` | Checks the register files against the field rules. |
| `regwatch coverage` | Reports how much of each jurisdiction the register covers. |
| `regwatch list` | Lists obligations, optionally filtered by jurisdiction, category, status or upcoming effective date. |
| `regwatch portfolio` | Lists the products obligations are matched against. |
| `regwatch capture` | Fetches sources into stored snapshots. |
| `regwatch check` | Detects changes in sources since the last accepted run. |
| `regwatch ingest` | Turns a Federal Register style response into unconfirmed candidates. |
| `regwatch impact` | Flags candidate impacts of obligations on products. |
| `regwatch themes` | Reads the impacts through the themes you configured. |
| `regwatch brief` | Builds a daily, weekly or tiered briefing. |
| `regwatch render` | Renders a saved briefing model into delivery formats. |
| `regwatch digest` | Writes a Markdown digest of the register. |
| `regwatch report` | Writes a change-and-due alert. |
| `regwatch export` | Writes one flat record per obligation as CSV and JSON. |

Every command accepts `--help`. The [CLI reference](https://github.com/klappe-pm/regwatch/blob/main/docs/reference/cli.md) covers every option, what each command reads and writes, and the exit statuses.

## Documentation

The docs live in one tree under `docs/`, following the [Diátaxis](https://diataxis.fr/) layout: tutorials, how-to guides, reference and explanation.

- **Using it:** start with [Getting Started](https://github.com/klappe-pm/regwatch/blob/main/docs/tutorials/getting-started.md), then browse the rest of [docs](https://github.com/klappe-pm/regwatch/blob/main/docs/README.md). [Set Your Focus Areas](https://github.com/klappe-pm/regwatch/blob/main/docs/how-to-guides/set-your-focus-areas.md) explains how the ranking works.
- **Hacking on it:** start with [First Contribution](https://github.com/klappe-pm/regwatch/blob/main/docs/tutorials/first-contribution.md), which sits in the same tree.
- **What ships:** the [changelog](https://github.com/klappe-pm/regwatch/blob/main/CHANGELOG.md).

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](https://github.com/klappe-pm/regwatch/blob/main/CONTRIBUTING.md) first; it will save you a round trip. If you are stuck or have found a bug, [SUPPORT.md](https://github.com/klappe-pm/regwatch/blob/main/SUPPORT.md) says where to ask and where to file an issue.

## Security

Please report vulnerabilities privately as described in [SECURITY.md](https://github.com/klappe-pm/regwatch/blob/main/SECURITY.md) rather than opening a public issue.

## License

Regwatch is released under the [MIT License](https://github.com/klappe-pm/regwatch/blob/main/LICENSE).
