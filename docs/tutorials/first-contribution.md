# First Contribution

This tutorial takes you from a fresh clone to a change that is ready for review. You set up a development environment, run the test suite, make one small change and check it. It follows one path and explains only what that path needs; [Contributing](../../CONTRIBUTING.md) holds the guidelines it applies, and the [how-to guides](../how-to-guides/README.md) cover each step in more depth.

## What You Need

- Python 3.11 or newer.
- `git`, and a GitHub account if you intend to open a pull request.

The commands use `/path/to/regwatch` for your clone. Replace it with the real location.

## Clone and Install

```bash
git clone https://github.com/klappe-pm/regwatch /path/to/regwatch && python3 -m venv /path/to/regwatch/.venv && /path/to/regwatch/.venv/bin/pip install -e '/path/to/regwatch[test,lint]'
```

This installs Regwatch as an editable package with the `test` extra (`pytest` and `pytest-cov`) and the `lint` extra (`ruff` and `mypy`). The package itself has no runtime dependencies.

## Run the Tests

```bash
/path/to/regwatch/.venv/bin/python -P -m pytest /path/to/regwatch/tests
```

The suite runs in a few seconds, needs no network, and never reads your home directory or a real register: it works on a copy of `examples/` in a temporary directory. A fixture blocks every socket, so a test that tries to reach the network fails. See [Run the Tests](../how-to-guides/run-the-tests.md) for the other checks.

## Make a Change

Pick something small for a first change: a wording fix in a page under `docs/`, a missing edge case in `tests/`, a clearer error message in `regwatch/cli.py`. Before you edit, read the part of the user documentation that covers what you are changing, and the [Source Layout](../reference/source-layout.md) to find the module.

Four conventions catch newcomers.

- All network access goes through `regwatch/fetch.py`, and all writes go through `regwatch/state.py`. Do not call `urllib` or write a file from anywhere else.
- Fetched content is untrusted. Parse it only with the functions in `regwatch/extract.py` and `regwatch/ingest.py`.
- Package data is read through `importlib.resources`, never through a path built from `__file__`; see [Package Data](../reference/package-data.md).
- Filenames are lowercase kebab-case and Markdown headings use Title Case, with one line per paragraph and no dashes used as punctuation. A test enforces this for every Markdown file.

Write the test first. For a bug fix, write a test that fails without the fix, apply the fix, and watch it pass. A test that passes with and without the change guards nothing.

## Check It

```bash
/path/to/regwatch/.venv/bin/python -P -m pytest /path/to/regwatch/tests --cov=regwatch --cov-report=term-missing
```

```bash
/path/to/regwatch/.venv/bin/ruff check /path/to/regwatch && /path/to/regwatch/.venv/bin/ruff format --check /path/to/regwatch && /path/to/regwatch/.venv/bin/mypy --config-file /path/to/regwatch/pyproject.toml /path/to/regwatch/regwatch
```

All of them must pass, and coverage of the package should stay at or above 90 percent.

## Commit

Commit with a [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) message, for example `docs: clarify the check statuses` or `fix: refuse a snapshot id with a slash`. Add a line under Unreleased in [the changelog](../../CHANGELOG.md) if the change is visible to a user. Keep the change to one thing, and say in the pull request what it does and how you tested it.

## Next Steps

- Read [Architecture](../explanation/architecture.md) before a change that touches more than one module.
- Read [Add a Source Mechanism](../how-to-guides/add-a-source-mechanism.md) to see how Regwatch learns to read a new kind of source.
- Read [Design Decisions](../explanation/design-decisions.md) before proposing a change to something they settle.
