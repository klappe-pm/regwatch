# Run the Tests

This guide covers every check a change must pass: the test suite and its coverage report, linting, formatting and strict type checking. There is no CI service for changes, so these commands are the gate; a change that passes them all is ready for review. The release workflow runs the suite once more, against the built wheel, before it publishes. It assumes the editable install from [first contribution](../tutorials/first-contribution.md).

## The Test Suite

```bash
~/regwatch/.venv/bin/python -m pytest ~/regwatch/tests
```

Tests live under `tests/` and read only the synthetic register in `examples/`, which the `project` fixture copies into a temporary directory, and the files under `tests/fixtures/`. They never use the real home directory, a real register or the network. An autouse fixture replaces `socket.socket.connect` and `socket.create_connection` with a function that raises, so any test that reaches for the network fails with a clear message.

The fetch client is tested without a network in three ways: the URL checks are plain functions, `file` URLs read a temporary directory, and the `https` path runs the real client code against fakes. `SafeFetcher` takes a resolver, a connector and a TLS wrapper, and `tests/test_fetch.py` supplies a fake name server and socket pairs with a server thread on the far end, so the tests exercise address vetting, pinning, redirects, size limits and the total deadline, including a server that sends one byte at a time. Everything above the client uses `FakeFetcher` from `tests/conftest.py`.

## The Source Distribution

The source distribution ships `tests/` and `examples/` but not `docs/`, `.github/` or the community files. A test that reads those carries the `repo_only` marker and skips when they are missing, so the shipped tests pass from an extracted sdist. To check that, build the distributions, extract the sdist, install the wheel in a fresh virtual environment and run pytest from the extracted tree:

```bash
cd /path/to/extracted/regwatch-0.1.0 && /path/to/venv/bin/python -P -m pytest -q
```

## Coverage

```bash
~/regwatch/.venv/bin/python -m pytest ~/regwatch/tests --cov=regwatch --cov-report=term-missing
```

The target is at least 90 percent of the lines in the package. The report lists the lines that no test reaches. One line in `config.py` carries a `pragma: no cover` because it is an unreachable guard for a type checker; any other uncovered line is a missing test.

Coverage measures lines, not behaviour. For a security check, prove the test matters by breaking the code it covers and watching the test fail. For example, remove the DTD check in `regwatch/extract.py` and confirm `test_extract.py` fails, then restore it.

## Lint and Format

```bash
~/regwatch/.venv/bin/ruff check ~/regwatch
```

```bash
~/regwatch/.venv/bin/ruff format --check ~/regwatch
```

The configuration is in `pyproject.toml`: line length 100, target Python 3.11, and the rule sets `E`, `F`, `W`, `I`, `B`, `UP`, `S`, `SIM` and `RUF`. The `S` rules are the security rules, and any `noqa` for one must say why it is safe. The line length rule `E501` is turned off because the formatter wraps code but cannot split a long string. To fix formatting, run `ruff format` without `--check`.

## Type Checking

```bash
~/regwatch/.venv/bin/mypy --config-file ~/regwatch/pyproject.toml ~/regwatch/regwatch
```

The package passes `mypy --strict`. New public functions need complete annotations. Tests are not type checked.

## The Documentation and Repository Tests

`tests/test_docs.py` checks the documentation and the repository layout and fails on:

- a Markdown heading that is not in Title Case, a page with no H1, or a Markdown file with frontmatter that carries `models`, `providers` or `session-link`;
- an absolute home directory path (`/Users/<name>` or `/home/<name>`) in any text file;
- an em dash or an en dash anywhere, or a dash used as punctuation in a Markdown file;
- a hard-wrapped Markdown paragraph;
- a code fence with no language tag, or a relative link that does not resolve;
- a link in `README.md` that is not absolute, because PyPI shows the README and a relative link breaks there;
- a folder README that does not list every page beside it, or a docs README that does not link every quadrant;
- an agent attribution in a Markdown file;
- a missing community file, or a `.github` directory that holds anything other than the issue and pull request templates, the banner and `workflows/release.yml`.

`tests/test_no_personal_terms.py` reads every tracked file and fails on the owner email, private tool names, tracker ticket codes and absolute home paths. When the environment variable `REGWATCH_FORBIDDEN_TERMS_FILE` names a text file of terms, one per line, any of those terms in any tracked text file also fails the test. The check is skipped when the variable is unset. Keep that file outside the repository; the repository never lists the terms itself.

Both files carry the `repo_only` marker, so they skip when the repository files they read are missing, as they are in an extracted source distribution. When a test fails it names the file and line.

## Before You Commit

Run all four commands, and add a line under Unreleased in [CHANGELOG.md](../../CHANGELOG.md) for any change a user can see.
