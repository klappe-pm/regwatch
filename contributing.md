# contributing

Thank you for helping improve regwatch. Open an issue to discuss a change before writing a large pull request. This page holds the rules every contribution follows; the walkthroughs and reference live under [developer-docs](developer-docs/README.md), starting with [first contribution](developer-docs/tutorials/first-contribution.md).

## setup

```bash
git clone https://github.com/klappe-pm/regwatch && cd regwatch && python3 -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]'
```

## tests

Run the suite before every commit. [run the tests](developer-docs/how-to-guides/run-the-tests.md) covers coverage, lint, formatting and type checking, which a change must also pass.

```bash
python3 -m pytest
```

## guidelines

- Python 3.11 or newer, standard library only at runtime. `pytest`, `pytest-cov`, `ruff` and `mypy` are development dependencies. A new runtime dependency needs a written justification in [dependencies](docs/explanation/dependencies.md) and an issue agreed beforehand.
- Package data lives under `regwatch/data/` and is read through `importlib.resources`, never through a path built from `__file__`. See [package data](developer-docs/reference/package-data.md).
- Tests read fixtures only: never the live home directory, a real network or a real register. The test suite blocks sockets, so a test that tries to reach the network fails.
- Examples and fixtures are synthetic. Never add a real register, a real company or client name, or data copied from a private source.
- Network access goes through the one fetch client in `regwatch/fetch.py`. Do not call `urllib`, `socket` or a subprocess from anywhere else.
- Text from outside goes through `regwatch/sanitize.py` before it is stored, printed or rendered. A link is accepted only through `safe_https_url`.
- Fetched content is untrusted. Parse it with the functions in `regwatch/extract.py` and never with `eval`, `pickle` or an XML parser that resolves entities.
- regwatch never writes to a register file. Every write goes through `safe_write_text` or `safe_write_bytes` in `regwatch/state.py`.
- Filenames and Markdown headings are lowercase kebab-case. Reserved names such as `README.md` and `LICENSE` keep their spelling.
- Write one line per Markdown paragraph and list item; do not hard-wrap prose. Do not use dashes as punctuation.
- Documentation goes in `docs/` for people who use regwatch and `developer-docs/` for people who change it, in the folder the [documentation guide](docs/documentation-guide/README.md) names for its kind.
- Keep any list of private terms to check for (client names, project names) in a file outside the repository, and point `REGWATCH_FORBIDDEN_TERMS_FILE` at it when you run the tests. Never write such terms in the repository.
- Never commit a secret, credential, private key, `.env` file or `settings.local.json`. `.env.example` with placeholder values is allowed.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).

## public-repository

Everything committed here is visible to anyone, so treat every file, commit, pull request and comment as published.

- Never add `models`, `providers` or `session-link` keys to the frontmatter of any Markdown file, and never add a session link anywhere.
- Never credit an agent, assistant, model, model provider or agent runtime as author or contributor in files, commits, pull requests or comments. No co-author trailers and no "generated with" lines.
- Agent instruction files and runtime directories at the repository root (`AGENTS.md`, `CLAUDE.md`, `CODEX.md`, `GEMINI.md`, `.claude/` and the like) are gitignored and never tracked.
- Do not add GitHub Actions workflows. The checks run locally, as described in [run the tests](developer-docs/how-to-guides/run-the-tests.md).

## pull-requests

Keep each pull request to one change, describe what it does and how you tested it, and make sure the test suite passes. Add a line under `unreleased` in [changelog.md](changelog.md) for any user-visible change.

## license

By contributing, you agree that your contributions are licensed under the MIT license in [LICENSE](LICENSE).
