# Source Layout

This page describes the repository tree and every module in the `regwatch` package: what it owns, what it imports from the rest of the package, and which rules apply to it. It is for a contributor looking for the right file to change. The user-facing behaviour of each module is in the [python api reference](python-api.md).

## Repository Tree

```text
regwatch/
  README.md  LICENSE  CHANGELOG.md  CONTRIBUTING.md  CODE_OF_CONDUCT.md  SECURITY.md  SUPPORT.md
  pyproject.toml  .editorconfig  .gitattributes  .gitignore
  .github/             issue and pull request templates, the banner, workflows/release.yml
  scripts/             make-banner.py, which draws the README banner, and build-web.sh
  regwatch/            the package
    data/              packaged data: schema.json, focus-areas.json, example-jurisdictions.json
    web/               the built web app, made by scripts/build-web.sh and committed
    py.typed           marks the package as typed
  web/                 the source of the web app: Next.js, Tailwind CSS, package-lock.json
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
| `state.py` | snapshots, the last-seen state, and `safe_write_text`, `safe_write_bytes` and `write_tree`, the only functions that write files |
| `check.py` | change detection and capture, built from `fetch`, `extract`, `register` and `state` |
| `ingest.py` | building the API query and turning a response into unconfirmed candidates |
| `impact.py` | exposure, scope and attribute gates, severity scoring, focus ranking and theme findings |
| `document.py` | the document model and the standard disclaimer |
| `synthesis.py` | the daily and weekly briefings |
| `briefing.py` | the tiered briefing |
| `render.py` | Markdown, web post, newsletter and Word output from a document |
| `export.py` | flat records and CSV |
| `onboarding.py` | the files `regwatch init` writes and the checks on its answers, as pure functions; it asks and prints nothing |
| `settings.py` | changing one setting in `regwatch.toml` while keeping the rest of the file, checked by parsing before it is written through `state` |
| `webapi.py` | the JSON interface behind `regwatch ui`: routes over the configuration, the register and the state, and the adapter functions for the catalogue, keys and schedule |
| `server.py` | the local server behind `regwatch ui`: loopback only, the host, origin and token checks, file containment, the security headers |
| `cli.py` | argument parsing, command handlers and exit statuses; the only module that prints |

## Rules by Module

- `fetch.py` is the only module that may import `socket`, `ssl`, `http.client` or `ipaddress`, and the only one that opens a connection. A test checks that it imports no subprocess, shell, pickle or ctypes module and calls no `os.system` or `os.popen`.
- `extract.py` and `ingest.py` are the only modules that parse fetched content. Neither may evaluate it.
- `state.py` is the only module that writes files. Every other module that needs a file written calls it.
- `register.py` and `config.py` are read only with respect to the register. Nothing in the package opens a register file for writing.
- `server.py` is the only module that listens for connections, and it binds `127.0.0.1` only. Every check it makes has a test that fails without it.
- `webapi.py` reaches the source catalogue, keys and the schedule only through its adapter functions, and no route returns a key.
- `cli.py` is the only module that prints. The other modules return values and raise exceptions, which makes them usable from a script.
- Every module declares `__all__`. A name that is not in it is internal.
- Every module is typed and passes `mypy --strict`.

## Tests by Module

Each module has a test file named for it, apart from `synthesis.py` and `briefing.py`, which share `test_briefs.py`, and `fetch.py`, whose `https` path is tested through a fake opener. `test_focus.py` covers the catalogue, matching, ranking and the focus split in every briefing, and `test_onboarding.py` covers `regwatch init`, `regwatch config show` and the profile table, driving the real prompts through a scripted `input`. `test_hardening.py` and `test_security_review.py` hold the regression tests for the findings of the two security reviews. `test_server.py` drives the local server through socket pairs, without a browser or a connection, `test_webapi.py` covers every route of the JSON interface, `test_settings.py` covers the settings editor and `regwatch premium`, `test_ui_command.py` covers `regwatch ui`, and `test_web_build.py` checks that the built web app has every page and refers to no other origin. `test_cli.py` runs every command through `main` with a fake fetcher and a fixed clock. `test_docs.py` checks the documentation and the repository layout, and `test_no_personal_terms.py` checks every tracked file for private terms. See [run the tests](../how-to-guides/run-the-tests.md).

## Examples

`examples/regwatch.toml` is a complete configuration, `examples/register/` holds a synthetic register in every file format, `examples/snapshots/` holds stored source content so `check` works offline, and `examples/ingest-response.json` is a saved API response. The tests copy this directory to a temporary location and work on the copy, so a test can change files freely. Keep the example valid: `test_cli.py` and `test_register.py` depend on its exact contents.
