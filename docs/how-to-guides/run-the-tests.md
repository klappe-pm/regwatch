# Run the Tests

This guide lists every check a change must pass and how to run it. It assumes the development install from [First Contribution](../tutorials/first-contribution.md), and its commands use `/path/to/regwatch` for your clone, which is also where the virtual environment lives. There is no CI service for changes, so these commands are the gate: a change that passes them all is ready for review. The release workflow runs the suite once more, against the built wheel, before it publishes.

## Test Suite

```bash
/path/to/regwatch/.venv/bin/python -P -m pytest /path/to/regwatch/tests
```

Install the `test` and `lint` extras first: `pip install -e '/path/to/regwatch[test,lint]'`. `pytest` and `pytest-cov` are the `test` extra, with `pytest` at 9.0.3 or newer because earlier releases carry CVE-2025-71176, and `ruff` and `mypy` are the `lint` extra. The `-P` option stops Python from putting the current directory on the import path, so the commands work from any directory, including the clone of another package whose `tests` folder would otherwise be imported instead.

## Coverage

```bash
/path/to/regwatch/.venv/bin/python -P -m pytest /path/to/regwatch/tests --cov=regwatch --cov-report=term-missing
```

The target is at least 90 percent line coverage of the package. The report lists the lines that no test reached. Report the real number in the pull request.

## Lint and Format

```bash
/path/to/regwatch/.venv/bin/ruff check /path/to/regwatch
```

```bash
/path/to/regwatch/.venv/bin/ruff format --check /path/to/regwatch
```

The configuration is in `pyproject.toml`: line length 100, target Python 3.11, and the rule sets `E`, `F`, `I`, `UP`, `B`, `SIM`, `W`, `S` and `RUF`. The `S` rules are the security rules, and a `noqa` for one must say why it is safe. To fix formatting, run `ruff format` without `--check`.

## Type Checking

```bash
/path/to/regwatch/.venv/bin/mypy --config-file /path/to/regwatch/pyproject.toml /path/to/regwatch/regwatch
```

The configuration runs `mypy --strict` on the `regwatch` package. Tests are not type checked.

## Source Distribution

The source distribution leaves out `.github/`, `docs/` and the community files. Tests marked `repo_only` read those files, so they skip themselves when the files are missing, and the tests that ship in the sdist pass when run from an extracted copy. To check that, build the distributions, extract the sdist, install the wheel and run the tests there with the source package out of the way, so that the wheel is what gets imported. The `tests` folder is not a package, so a test module imports a helper module of that folder by its plain name (`from conftest import ROOT`, `from test_docs import headings`) and never as `tests.conftest`; `tests.conftest` resolves only from a source checkout, and a test checks that no module uses it:

```bash
cd /path/to/regwatch && python3 -m build --outdir /path/to/dist
```

```bash
tar -xzf /path/to/dist/regwatch-<version>.tar.gz -C /path/to/sdist && python3 -m venv /path/to/venv && /path/to/venv/bin/pip install /path/to/dist/regwatch-<version>-py3-none-any.whl pytest && rm -r /path/to/sdist/regwatch-<version>/regwatch && cd /path/to/sdist/regwatch-<version> && /path/to/venv/bin/python -m pytest
```

## Repository Tests

Three modules check the repository around the code.

- `tests/test_docs.py` checks the documentation and the files beside it: Title Case headings in every Markdown file, including the pull request template, one H1 per page, a purpose paragraph under each title, no frontmatter or provenance keys, no agent credit, no home directory in any page, a language tag on every code fence, relative links that resolve, absolute links in the README and its skeleton, one line per paragraph, no dash used as punctuation, no em or en dash in any text file, a final newline, the Keep a Changelog shape of the changelog, lowercase kebab-case filenames, no agent instruction files, the required community files, and a `.github` folder that holds only the templates, the banner and the release workflow.
- `tests/test_no_personal_terms.py` reads every tracked file and rejects the owner's login, email and name, tracker ticket codes and absolute home paths. Private tool and project names are never written in the repository, not even in the test. To check them, put one term per line in a text file outside the repository and name it in `REGWATCH_FORBIDDEN_TERMS_FILE`; the test skips when the variable is not set, which is the case on GitHub, so the release guide runs it locally before every release.
- `tests/test_release_workflow.py` checks that every action is pinned to a full commit, that the build, test and publish jobs are separate, that only the publish job can request an identity token, that every `pip install` in the workflow uses hashes or installs the local artifact with `--no-deps`, and that the lock files pin every requirement with hashes. It also checks the packaging metadata.

`test_docs.py` and `test_release_workflow.py` carry the `repo_only` marker.

## The Banner

`.github/regwatch-banner.svg` is written by `scripts/make-banner.py`, which needs `fonttools` and the DejaVu Sans Mono font files. `fonttools` is a script-only dependency and is not a dependency of the package. Edit the script, never the SVG:

```bash
cd /path/to/regwatch && python3 -m pip install fonttools && python3 scripts/make-banner.py
```

## Fixtures and the Network

Tests read only the synthetic register in `examples/`, which the `project` fixture copies into a temporary directory, and the files under `tests/fixtures/`. They never use the real home directory, a real register or the network. An autouse fixture replaces `socket.socket.connect` and `socket.create_connection` with a function that raises, so any test that reaches for the network fails with a clear message.

The fetch client is tested without a network in three ways: the URL checks are plain functions, `file` URLs read a temporary directory, and the `https` path runs the real client code against fakes. `SafeFetcher` takes a resolver, a connector and a TLS wrapper, and `tests/test_fetch.py` supplies a fake name server and socket pairs with a server thread on the far end, so the tests exercise address vetting, pinning, redirects, size limits and the total deadline, including a server that sends one byte at a time. Everything above the client uses `FakeFetcher` from `tests/conftest.py`.

## Proving a Test Matters

One line in `config.py` carries a `pragma: no cover` because it is an unreachable guard for a type checker; any other uncovered line is a missing test.

Coverage measures lines, not behaviour. For a security check, prove the test matters by breaking the code it covers and watching the test fail. For example, remove the DTD check in `regwatch/extract.py` and confirm `test_extract.py` fails, then restore it.
