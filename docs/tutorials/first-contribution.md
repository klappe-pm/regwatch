# First Contribution

This tutorial takes you from a fresh clone to a merge-ready pull request. You set up a development environment, run the test suite, make one small change, check it the way a reviewer will, and open the pull request. It follows one path and explains only what that path needs; [contributing](../../CONTRIBUTING.md) holds the guidelines it applies, and the [how-to guides](../how-to-guides/README.md) cover each step in more depth.

## What You Need

- Python 3.11 or newer.
- `git`, and a GitHub account if you intend to open the pull request.

## Clone and Install

```bash
git clone https://github.com/klappe-pm/regwatch ~/regwatch && python3 -m venv ~/regwatch/.venv && ~/regwatch/.venv/bin/pip install -e "$HOME/regwatch[dev]"
```

This installs regwatch as an editable package with `pytest`, `pytest-cov`, `ruff` and `mypy`. The package itself has no runtime dependencies.

## Run the Tests

```bash
~/regwatch/.venv/bin/python -m pytest ~/regwatch/tests
```

The suite runs in a few seconds, needs no network, and never reads your home directory or a real register: it works on a copy of `examples/` in a temporary directory. A fixture blocks every socket, so a test that tries to reach the network fails.

## Make a Change

Pick something small for a first change: a wording fix in a page under `docs/`, a missing edge case in `tests/`, a clearer error message in `regwatch/cli.py`. Before you edit, read the part of the user documentation that covers what you are changing, and the [source layout](../reference/source-layout.md) to find the module.

Four conventions catch newcomers.

- All network access goes through `regwatch/fetch.py`, and all writes go through `regwatch/state.py`. Do not call `urllib` or write a file from anywhere else.
- Fetched content is untrusted. Parse it only with the functions in `regwatch/extract.py` and `regwatch/ingest.py`.
- Package data is read through `importlib.resources`, never through a path built from `__file__`; see [package data](../reference/package-data.md).
- Filenames are lowercase kebab-case and Markdown headings use Title Case, with one line per paragraph and no dashes used as punctuation. A test enforces this for every Markdown file.

Write the test first. For a bug fix, write a test that fails without the fix, apply the fix, and watch it pass. A test that passes with and without the change guards nothing.

## Check It the Way a Reviewer Will

```bash
~/regwatch/.venv/bin/python -m pytest ~/regwatch/tests --cov=regwatch --cov-report=term-missing
```

```bash
~/regwatch/.venv/bin/ruff check ~/regwatch
```

```bash
~/regwatch/.venv/bin/ruff format --check ~/regwatch
```

```bash
~/regwatch/.venv/bin/mypy --config-file ~/regwatch/pyproject.toml ~/regwatch/regwatch
```

All four must pass, and coverage of the package should stay at or above 90 percent. [run the tests](../how-to-guides/run-the-tests.md) explains each.

## Commit and Open the Pull Request

Commit with a [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) message, for example `docs: clarify the check statuses` or `fix: refuse a snapshot id with a slash`. Add a line under Unreleased in [CHANGELOG.md](../../CHANGELOG.md) if the change is visible to a user. Never add an agent, assistant or model as an author or co-author.

Push your branch and open a pull request against `main`. Keep it to one change, say what it does and how you tested it, and make sure the checks above pass. A maintainer will review it from there.

## Next Steps

- Read [architecture](../explanation/architecture.md) before a change that touches more than one module.
- Read [add a source mechanism](../how-to-guides/add-a-source-mechanism.md) if you want regwatch to read a new kind of source.
- Read [design decisions](../explanation/design-decisions.md) before proposing a change to something they settle.
