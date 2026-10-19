# run-the-tests

This guide covers every check a change must pass: the test suite and its coverage report, linting, formatting and strict type checking. There is no CI service, so these commands are the only gate; a change that passes them all is ready for review. It assumes the editable install from [first contribution](../tutorials/first-contribution.md).

## the-test-suite

```bash
~/regwatch/.venv/bin/python -m pytest ~/regwatch/tests
```

Tests live under `tests/` and read only the synthetic register in `examples/`, which the `project` fixture copies into a temporary directory, and the files under `tests/fixtures/`. They never use the real home directory, a real register or the network. An autouse fixture replaces `socket.socket.connect` and `socket.create_connection` with a function that raises, so any test that reaches for the network fails with a clear message.

The fetch client is tested without a network in three ways: the URL checks are plain functions, `file` URLs read a temporary directory, and the `https` path runs the real client code against fakes. `SafeFetcher` takes a resolver, a connector and a TLS wrapper, and `tests/test_fetch.py` supplies a fake name server and socket pairs with a server thread on the far end, so the tests exercise address vetting, pinning, redirects, size limits and the total deadline, including a server that sends one byte at a time. Everything above the client uses `FakeFetcher` from `tests/conftest.py`.

## coverage

```bash
~/regwatch/.venv/bin/python -m pytest ~/regwatch/tests --cov=regwatch --cov-report=term-missing
```

The target is at least 90 percent of the lines in the package. The report lists the lines that no test reaches. One line in `config.py` carries a `pragma: no cover` because it is an unreachable guard for a type checker; any other uncovered line is a missing test.

Coverage measures lines, not behaviour. For a security check, prove the test matters by breaking the code it covers and watching the test fail. For example, remove the DTD check in `regwatch/extract.py` and confirm `test_extract.py` fails, then restore it.

## lint-and-format

```bash
~/regwatch/.venv/bin/ruff check ~/regwatch
```

```bash
~/regwatch/.venv/bin/ruff format --check ~/regwatch
```

The configuration is in `pyproject.toml`: line length 100, target Python 3.11, and the rule sets `E`, `F`, `W`, `I`, `B`, `UP`, `S`, `SIM` and `RUF`. The `S` rules are the security rules, and any `noqa` for one must say why it is safe. The line length rule `E501` is turned off because the formatter wraps code but cannot split a long string. To fix formatting, run `ruff format` without `--check`.

## type-checking

```bash
~/regwatch/.venv/bin/mypy --config-file ~/regwatch/pyproject.toml ~/regwatch/regwatch
```

The package passes `mypy --strict`. New public functions need complete annotations. Tests are not type checked.

## the-repository-hygiene-test

`tests/test_repository_hygiene.py` checks the whole tree and fails on:

- an absolute home directory path (`/Users/<name>` or `/home/<name>`) in any text file;
- when the environment variable `REGWATCH_FORBIDDEN_TERMS_FILE` names a text file of terms, one per line, any of those terms in any text file. The check is skipped when the variable is unset. Keep that file outside the repository; the repository never lists the terms itself;
- an em dash or an en dash anywhere, or a dash used as punctuation in a Markdown file;
- a hard-wrapped Markdown paragraph;
- a Markdown heading that is not lowercase kebab-case, or an H1 that does not match its file;
- a code fence with no language tag, or a relative link that does not resolve;
- a folder README that does not list every page beside it;
- frontmatter, or an agent attribution, in a Markdown file;
- a `.github` directory.

When it fails it names the file and line.

## before-you-commit

Run all four commands, and add a line under `unreleased` in [changelog.md](../../changelog.md) for any change a user can see.
