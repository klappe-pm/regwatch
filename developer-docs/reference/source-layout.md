# source-layout

This page describes the repository tree and every module in the `regwatch` package: what it owns, what it imports from the rest of the package, and which rules apply to it. It is for a contributor looking for the right file to change. The user-facing behaviour of each module is in the [python api reference](../../docs/reference/python-api.md).

## repository-tree

```text
regwatch/
  README.md  LICENSE  changelog.md  contributing.md  security.md  support.md
  pyproject.toml  .editorconfig  .gitattributes  .gitignore
  regwatch/            the package
    data/schema.json   field rules, packaged data
    py.typed           marks the package as typed
  tests/               the test suite
    fixtures/          small hostile and ordinary inputs
  examples/            the synthetic register, snapshots and ingest response
  docs/                documentation for people who use regwatch
  developer-docs/      documentation for people who change it
```

## modules

Modules are listed from the bottom of the dependency order to the top. A module imports only from modules listed above it.

| module | owns |
| --- | --- |
| `config.py` | parsing and validating `regwatch.toml` into immutable settings; the list of register paths that must never be written |
| `fetch.py` | the one network client: scheme allowlist, address vetting and pinning, redirects, file roots, size limit, timeouts and total deadline; imports nothing else from the package |
| `sanitize.py` | cleaning of untrusted text, link validation and Markdown escaping; imports nothing else from the package |
| `extract.py` | reducing untrusted content to a signal and hashing it; imports nothing else from the package |
| `register.py` | the register data model, reading the files, validating them against `data/schema.json`, and building immutable objects |
| `state.py` | snapshots, the last-seen state, and `safe_write_text` and `safe_write_bytes`, the only functions that write files |
| `check.py` | change detection and capture, built from `fetch`, `extract`, `register` and `state` |
| `ingest.py` | building the API query and turning a response into unconfirmed candidates |
| `impact.py` | exposure, scope and attribute gates, severity scoring and theme findings |
| `document.py` | the document model and the standard disclaimer |
| `synthesis.py` | the daily and weekly briefings |
| `briefing.py` | the tiered briefing |
| `render.py` | Markdown, web post, newsletter and Word output from a document |
| `export.py` | flat records and CSV |
| `cli.py` | argument parsing, command handlers and exit statuses; the only module that prints |

## rules-by-module

- `fetch.py` is the only module that may import `socket`, `ssl`, `http.client` or `ipaddress`, and the only one that opens a connection. A test checks that it imports no subprocess, shell, pickle or ctypes module and calls no `os.system` or `os.popen`.
- `extract.py` and `ingest.py` are the only modules that parse fetched content. Neither may evaluate it.
- `state.py` is the only module that writes files. Every other module that needs a file written calls it.
- `register.py` and `config.py` are read only with respect to the register. Nothing in the package opens a register file for writing.
- `cli.py` is the only module that prints. The other modules return values and raise exceptions, which makes them usable from a script.
- Every module declares `__all__`. A name that is not in it is internal.
- Every module is typed and passes `mypy --strict`.

## tests-by-module

Each module has a test file named for it, apart from `synthesis.py` and `briefing.py`, which share `test_briefs.py`, and `fetch.py`, whose `https` path is tested through a fake opener. `test_hardening.py` holds the regression tests for the security review findings. `test_cli.py` runs every command through `main` with a fake fetcher and a fixed clock. `test_repository_hygiene.py` checks the whole tree. See [run the tests](../how-to-guides/run-the-tests.md).

## examples

`examples/regwatch.toml` is a complete configuration, `examples/register/` holds a synthetic register in every file format, `examples/snapshots/` holds stored source content so `check` works offline, and `examples/ingest-response.json` is a saved API response. The tests copy this directory to a temporary location and work on the copy, so a test can change files freely. Keep the example valid: `test_cli.py` and `test_register.py` depend on its exact contents.
