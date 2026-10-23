# Contributing

Thank you for helping improve Regwatch. Open an issue to discuss a change before writing a large pull request, so the effort goes where it will be merged. This page holds the rules every contribution follows; the walkthroughs and reference live under [docs](docs/README.md), starting with [First Contribution](docs/tutorials/first-contribution.md). Everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Setup

```bash
git clone https://github.com/klappe-pm/regwatch && cd regwatch && python3 -m venv .venv && . .venv/bin/activate && pip install -e '.[test,lint]'
```

## Tests

Run the suite before every commit. [Run the Tests](docs/how-to-guides/run-the-tests.md) covers the other checks.

```bash
python3 -m pytest
```

```bash
python3 -m pytest --cov=regwatch
```

## Guidelines

- Python 3.11 or newer, standard library only at runtime. `pytest` and `pytest-cov` are the `test` extra, and `ruff` and `mypy` are the `lint` extra.
- A new runtime dependency needs a written justification in [Dependencies](docs/explanation/dependencies.md) and an issue agreed beforehand.
- Package data lives under `regwatch/data/` and is read through `importlib.resources`, never through a path built from `__file__`. See [Package Data](docs/reference/package-data.md).
- Tests read fixtures only: never the live home directory, a real network or a real register. The test suite blocks sockets, so a test that tries to reach the network fails.
- Never add a real register or a real company. The register in `examples/` is invented.
- Network access goes through the one fetch client in `regwatch/fetch.py`. Do not call `urllib` or `socket` from anywhere else. A program is started only through `run_command` in `regwatch/system.py`, with an argument list and never a shell, and a secret only on standard input.
- Text from outside goes through `regwatch/sanitize.py` before it is stored, printed or rendered. A link is accepted only through `safe_https_url`.
- Fetched content is untrusted. Parse it with the functions in `regwatch/extract.py` and never with `eval`, `pickle` or an XML parser that resolves entities.
- Regwatch writes a register file only through `state.update_register_file`, and only the sources and jurisdictions files for `regwatch sources add` and `remove`. Every write goes through `regwatch/state.py`.
- Every security fix gets a test that fails without the fix. Revert the fix once to watch the test fail, then restore it.
- Documentation goes in `docs/`, in the folder for its kind: `tutorials/`, `how-to-guides/`, `reference/` or `explanation/`. Headings use Title Case, and each paragraph and list item is one line, not hard-wrapped. Filenames are lowercase kebab-case, apart from the community files and `README.md`.
- Do not use a dash as punctuation. Use a comma, colon, semicolon, period or parentheses, and write ranges as "3 to 5".
- The banner in `.github/` is made by `scripts/make-banner.py`, which needs `fonttools` and nothing else. `fonttools` is a script-only dependency and is not a dependency of the package.
- Everything committed here is public. Never add `models`, `providers` or `session-link` keys to the frontmatter of a Markdown file, never add a session link anywhere, and never credit an agent, model, model provider or agent runtime as author or contributor.
- Agent instruction files and runtime directories at the repository root are gitignored and never tracked.
- Do not copy anything from a private repository: no client names, personal paths, notes, plans or prompts. Examples and fixtures are synthetic.
- Keep any list of private terms to check for (client names, project names, private tool names) in a file outside the repository, and point `REGWATCH_FORBIDDEN_TERMS_FILE` at it when you run the tests. Never write such terms in the repository.
- Never commit a secret, credential, private key, `.env` file or `settings.local.json`. `.env.example` with placeholder values is allowed.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).

## Pull Requests

Keep each pull request to one change, describe what it does and how you tested it, and make sure the test suite, `ruff check`, `ruff format --check` and `mypy` pass. Add a line under Unreleased in [CHANGELOG.md](CHANGELOG.md) for any user-visible change.

## Roadmap

Open an issue before starting on one of these, so the approach can be agreed first.

- [ ] Publish the first release to PyPI
- [ ] Add source mechanisms for more kinds of source
- [ ] Add a running index of briefings, which the engine this was extracted from had
- [x] Add scheduled runs: `regwatch schedule` installs them with launchd or cron

## License

By contributing, you agree that your contributions are licensed under the MIT license in [LICENSE](LICENSE).
