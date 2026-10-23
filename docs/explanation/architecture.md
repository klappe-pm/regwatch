# Architecture

This page explains how regwatch is put together, for a contributor who needs the shape of the whole before changing a part. It describes the data flow from the register and the sources to a rendered briefing, the layering of the modules, and the four trust boundaries that the design is built around. The [source layout](../reference/source-layout.md) lists the modules; the [design](design.md) page explains the product reasoning.

## The Data Flow

```text
regwatch.toml
    |
    v
config --> register ---------------------------+
                                                |
sources --> fetch --> snapshots --> extract --> check --> SourceResult
                                                |
API response --> ingest --> candidates          |
                                                v
                              impact --> Impact, Finding
                                                |
                                                v
              synthesis, briefing --> Document (JSON model)
                                                |
                                                v
                                   render --> md, web, newsletter, docx
```

Every arrow between stages that matter is a file or an immutable value. `check` does not call `impact`, and `impact` does not call `render`. The command line connects them, and a script can connect them differently.

## Layering

The modules form layers, and each imports only from the ones below it.

1. `config`, `sanitize`, `extract`, `fetch`, `system`, `schedule`: no dependency on the rest of the package, except that `fetch` uses `sanitize` to clean its error messages. These are the modules that touch the outside world, and they are small on purpose.
2. `register`, `focus`, `catalogue`, `keys`, `state`: the data model, the focus catalogue and profile, the source catalogue with its one search ranking, and the one write path.
3. `check`, `ingest`, `impact`: the engine's analysis. They take loaded data and return values. `impact` ranks by the focus profile it is given and never drops a candidate.
4. `document`, `synthesis`, `briefing`, `render`, `export`: turning analysis into output. `synthesis` and `briefing` build a `Document`; `render` turns a `Document` into text or bytes.
5. `onboarding`, `settings`: the files `regwatch init` writes and the checks on its answers, and the change of one setting in `regwatch.toml`. The questions and the printing stay in `cli`.
6. `webapi`, `server`: the JSON interface over the same loaded data, and the local server that carries it and the built pages to the browser.
7. `cli`: the only module that prints, asks questions, parses arguments or sets an exit status.

Analysis and output functions are pure. They take loaded data and an explicit date and return a value, with no clock reads, no file access and no printing. That is what makes them testable with plain dataclasses and what lets a script call them.

## The Trust Boundaries

There are four places where data crosses from one trust level to another, and each has one owner.

- Network to process. `fetch.py` is the only module that opens a connection. It checks the scheme, the address, the size, the time and the redirect target, and returns text.
- Text to structure. `extract.py` and `ingest.py` are the only modules that parse fetched text. They return strings and plain dicts of bounded, type-checked values, and they never evaluate content. `sanitize.py` cleans every such value, and `render.py` escapes it again for the output format.
- Process to programs. `system.py` is the only module that starts a program: the keychain tools, `launchctl` and `crontab`. It passes an argument list with no shell and a timeout, and a key travels only on standard input.
- Process to disk. `state.py` is the only module that writes; `settings.py` hands it the edited configuration. It refuses the register files (apart from the one rewrite of the sources or jurisdictions file that `sources add` and `sources remove` ask for) and any output path that is a symbolic link, writes atomically, keeps an existing file's permissions and rejects a source id that is not a plain identifier.
- Browser to process. `server.py` is the only module that listens. It answers only on `127.0.0.1`, only to its own host name and origin, and only with the token, and serves only files inside the built web app.

A change that adds a way across one of these boundaries somewhere else is a change to the security model, and needs the justification described in [contributing](../../CONTRIBUTING.md).

## The Register Is Immutable

`register.py` reads the files, validates them, and builds frozen dataclasses. After `load_register` returns, nothing in the package can change a row, and nothing writes the files it came from. The only data regwatch keeps between runs is the state directory: stored snapshots, the accepted hashes and the latest ingest candidates. Deleting that directory loses no curated data.

## The Document Model

A `Document` is a title, a date, a list of sections and a disclaimer. Sections hold paragraphs and bullets, all plain strings. Briefings are built into this model and renderers read from it, which is why adding a new output format means adding one function to `render.py` and nothing to the analysis. The model is also written to JSON by `brief --out-dir` and read back by `render`, so a briefing can be built on one machine and rendered on another, or edited by a person between the two steps. Loading a model validates it and restores the disclaimer.

## Failure Handling

Expected failures are values or typed exceptions, never tracebacks.

- A source that cannot be fetched or parsed becomes an `ERROR` result, and the run continues with the other sources.
- Invalid register data raises `RegisterError` with every message at once.
- `main` maps `ConfigError`, `StateError`, `FetchError`, `IngestError`, `DocumentError`, `ValueError` and `OSError` to an `error:` line and exit status 2, and `RegisterError` to exit status 1.

Bugs are not caught. An unexpected exception shows a traceback, which is what a contributor wants to see.
