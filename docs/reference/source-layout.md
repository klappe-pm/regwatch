# Source Layout

This page describes the repository tree and every module in the `regwatch` package: what it owns, what it imports from the rest of the package, and which rules apply to it. It is for a contributor looking for the right file to change. The user-facing behaviour of each module is in the [python api reference](python-api.md).

## Repository Tree

```text
regwatch/
  README.md  LICENSE  CHANGELOG.md  CONTRIBUTING.md  CODE_OF_CONDUCT.md  SECURITY.md  SUPPORT.md
  pyproject.toml  .editorconfig  .gitattributes  .gitignore
  .github/             issue and pull request templates, the banner, workflows/release.yml
  scripts/             make-banner.py, which draws the README banner
  regwatch/            the package
    data/              packaged data: schema.json, focus-areas.json, example-jurisdictions.json,
                       source-catalogue.json, jurisdiction-names.json
    py.typed           marks the package as typed
  tests/               the test suite
    fixtures/          small hostile and ordinary inputs
  examples/            the synthetic register, snapshots and ingest response
  docs/                documentation, one tree in the four Diátaxis quadrants
```

## Modules

Modules are listed from the bottom of the dependency order to the top. A module imports only from modules listed above it.

| module | owns |
| --- | --- |
| `config.py` | parsing and validating `regwatch.toml` into immutable settings; the list of register paths that must never be written |
| `sanitize.py` | cleaning of untrusted text, link validation and Markdown escaping; imports nothing else from the package |
| `fetch.py` | the one network client: scheme allowlist, address vetting and pinning, redirects, file roots, size limit, timeouts and total deadline; imports only `sanitize` |
| `extract.py` | reducing untrusted content to a signal and hashing it; imports nothing else from the package |
| `register.py` | the register data model, reading the files, validating them against `data/schema.json`, and building immutable objects |
| `focus.py` | the focus catalogue, focus profiles and whole-word matching of candidate text; imports `config` and `register` |
| `catalogue.py` | the source catalogue: loading and validating the shipped and extra files, the one search ranking, filters, and turning a chosen entry into a sources file entry; imports `fetch` for its URL checks |
| `state.py` | snapshots, the last-seen state, and `safe_write_text`, `safe_write_bytes`, `update_register_file` and `write_tree`, the only functions that write files |
| `check.py` | change detection and capture, built from `fetch`, `extract`, `register` and `state` |
| `ingest.py` | building the API query and turning a response into unconfirmed candidates |
| `impact.py` | exposure, scope and attribute gates, severity scoring, focus ranking and theme findings |
| `document.py` | the document model and the standard disclaimer |
| `synthesis.py` | the daily and weekly briefings |
| `briefing.py` | the tiered briefing |
| `render.py` | Markdown, web post, newsletter and Word output from a document |
| `export.py` | flat records and CSV |
| `onboarding.py` | the files `regwatch init` writes and the checks on its answers, as pure functions; it asks and prints nothing |
| `cli.py` | argument parsing, command handlers and exit statuses; the only module that prints |

## Rules by Module

- `fetch.py` is the only module that may import `socket`, `ssl`, `http.client` or `ipaddress`, and the only one that opens a connection. A test checks that it imports no subprocess, shell, pickle or ctypes module and calls no `os.system` or `os.popen`.
- `extract.py` and `ingest.py` are the only modules that parse fetched content. Neither may evaluate it.
- `state.py` is the only module that writes files. Every other module that needs a file written calls it.
- `register.py` and `config.py` are read only with respect to the register. The one write to a register file is `state.update_register_file`, which `cli.py` calls for `sources add` and `sources remove`, on the sources and jurisdictions files only, with every other register file still protected.
- `cli.py` is the only module that prints. The other modules return values and raise exceptions, which makes them usable from a script.
- Every module declares `__all__`. A name that is not in it is internal.
- Every module is typed and passes `mypy --strict`.

## Tests by Module

Each module has a test file named for it, apart from `synthesis.py` and `briefing.py`, which share `test_briefs.py`, and `fetch.py`, whose `https` path is tested through a fake opener. `test_focus.py` covers the catalogue, matching, ranking and the focus split in every briefing, and `test_catalogue.py` covers the catalogue rules, the shipped file, the ranking, the filters and the merge into a sources file, and `test_sources_cli.py` covers every `regwatch sources` action. `test_onboarding.py` covers `regwatch init`, `regwatch config show` and the profile table, driving the real prompts through a scripted `input`. `test_hardening.py` and `test_security_review.py` hold the regression tests for the findings of the two security reviews. `test_cli.py` runs every command through `main` with a fake fetcher and a fixed clock. `test_docs.py` checks the documentation and the repository layout, and `test_no_personal_terms.py` checks every tracked file for private terms. See [run the tests](../how-to-guides/run-the-tests.md).

## Examples

`examples/regwatch.toml` is a complete configuration, `examples/register/` holds a synthetic register in every file format, `examples/snapshots/` holds stored source content so `check` works offline, and `examples/ingest-response.json` is a saved API response. The tests copy this directory to a temporary location and work on the copy, so a test can change files freely. Keep the example valid: `test_cli.py` and `test_register.py` depend on its exact contents.
