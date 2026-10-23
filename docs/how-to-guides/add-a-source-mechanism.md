# Add a Source Mechanism

This guide shows how to teach `check` to read a new kind of source, such as a different feed format. A mechanism is a name in the `mechanism` field of a source and a function that reduces fetched content to a stable signal. The work touches the field rules, the extractor, the documentation and the tests. Because fetched content is untrusted, the extractor is the part to get right.

## Decide Whether You Need One

A new mechanism is worth adding when the existing ones produce a signal that changes for reasons a reader does not care about, and no existing one can be told apart by the content alone. If the content is plain text, `email-list` already covers it. If it is JSON, `api` covers it. Open an issue first; see [contributing](../../CONTRIBUTING.md).

## Add the Name to the Field Rules

Add the name to the `enum` of `mechanism` in `source_fields` in `regwatch/data/schema.json`. The validator rejects any name that is not listed, so this is what makes the mechanism usable in a register.

## Write the Extractor

In `regwatch/extract.py`, add a branch to `extract_signal` that calls a new private function. Follow these rules:

- Take a `str` and return a `str`. The caller hashes the result.
- Never evaluate the content: no `eval`, `exec`, `pickle`, `yaml.load` or `shell` anywhere.
- If the format is XML, refuse any document that declares a DTD or entity, as `_feed_signal` does, rather than relying on the parser to cope.
- Sort the rows, so a reordering of the same items gives the same signal.
- Drop everything that changes without meaning: timestamps of the request, session tokens, markup.
- Raise `ExtractError` for content that is not the format you expect, so the source reports `ERROR` with a reason instead of hashing garbage.
- Keep it bounded. The fetch client has already limited the size, but the function should not be quadratic in it.

## Add the Tests

Add tests to `tests/test_extract.py` for each of these, and write them before the code:

- a normal document produces the expected signal;
- the same items in a different order, or with different markup, produce the same signal;
- a real change produces a different signal;
- malformed input raises `ExtractError`;
- hostile input is refused or harmless: an entity expansion document, deeply nested input, and content that looks like code.

Add a fixture to `tests/fixtures/` if the input is long. Add one end-to-end case to `tests/test_check.py` that stores a snapshot, accepts it, changes it and sees `CHANGED`.

Then prove the tests matter. Break the part of the extractor that guards against bad input, run the tests, and confirm one of them fails. Restore it.

## Document It

Add a row for the mechanism to the table in [add a source](add-a-source.md), update the `mechanism` row in [data files](../reference/data-files.md), and add a line under Unreleased in [CHANGELOG.md](../../CHANGELOG.md). If the mechanism parses a new format, describe how it is made safe in the [security model](../explanation/security-model.md).
