# regwatch

regwatch watches regulatory sources for changes, compares what it finds with a register of obligations that you keep, flags the obligations and products that a person should look at, and renders a briefing. It is an engine for people who track rules such as food ingredient and labeling law, it ships as a Python package with a `regwatch` command, it needs only the Python 3.11 standard library at runtime, and nothing it produces is legal advice.

## status

regwatch flags candidates for human review. It never edits the register or the change log that you curate, and it never decides anything for you. Nothing it produces is legal advice, and every briefing it renders says so. A qualified person must confirm each flagged item against the primary source text and current facts before anyone relies on it.

The engine was extracted from a private repository. Nothing is released yet, so the package is not on PyPI and there is no tagged version; install it from a checkout. The commands `validate`, `coverage`, `list`, `portfolio`, `capture`, `check`, `ingest`, `impact`, `themes`, `brief`, `render`, `digest`, `report` and `export` are implemented. [changelog.md](changelog.md) records changes.

## quickstart

Install from a checkout into a virtual environment:

```bash
git clone https://github.com/klappe-pm/regwatch && cd regwatch && python3 -m venv .venv && . .venv/bin/activate && pip install -e .
```

Run the engine on the synthetic example register that ships in `examples/`. Every jurisdiction, rule, source and product in it is invented.

```bash
cd examples && regwatch validate
```

```bash
cd examples && regwatch check
```

```bash
cd examples && regwatch impact
```

```bash
cd examples && regwatch brief --tier v2
```

To use regwatch on your own rules, copy `examples/` as a starting point, replace the register files with yours, and edit `regwatch.toml` so it points at them. The [getting started tutorial](docs/tutorials/getting-started.md) walks through every step.

## documentation

Two trees, one per audience, each arranged by [Diátaxis](https://diataxis.fr/) quadrant: tutorials, how-to guides, reference and explanation.

- I use regwatch, where do I start: [getting started](docs/tutorials/getting-started.md), then the rest of [docs](docs/README.md).
- I change regwatch, where do I start: [first contribution](developer-docs/tutorials/first-contribution.md), then the rest of [developer-docs](developer-docs/README.md).

## support-and-contributing

[support.md](support.md) says where to ask for help and where to file an issue. [contributing.md](contributing.md) holds the contribution guidelines. Report vulnerabilities privately as described in [security.md](security.md).

## license

MIT. See [LICENSE](LICENSE).
