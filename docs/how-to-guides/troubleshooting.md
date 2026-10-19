# troubleshooting

This guide collects known failure modes and their fixes, one problem per heading, so you can match the message you see and act on it. Every failure prints a line that starts with `error:` and exits with a status from the table in the [cli reference](../reference/cli.md). If your problem is not here, see [support](../../support.md) for where to ask.

## cannot-read-configuration-file

The command could not find `regwatch.toml`. By default regwatch looks for it in the current directory. Pass the path explicitly with `--config`, for example `regwatch --config ~/my-register/regwatch.toml validate`. The option goes before the subcommand.

## configuration-has-unknown-keys

regwatch rejects keys it does not know so a typo cannot silently change behaviour. The message names the table and the keys. Compare them with [configuration](../reference/configuration.md). A common cause is putting a key in `[fetch]` that belongs in `[ingest]`, or the reverse.

## the-register-has-validation-errors

Every command except `validate` refuses to run on an invalid register and tells you to run `regwatch validate`. That command prints one `ERROR` line per problem. The usual causes are a value outside its list of allowed values, a reference to a jurisdiction, category or source that is not defined, a date that is not `YYYY-MM-DD`, a URL that is not `https`, or an obligations row with a different number of cells than the header. [data files](../reference/data-files.md) lists the rule for each field.

## a-source-reports-error-fetch-failed

`check --fetch` and `capture` print the reason after `fetch failed`.

- `HTTP status 403` or `404`: the site refused the request or the address moved. Some sites block automated clients. Check the address in a browser; if the page works there but not for regwatch, change the source to `manual`.
- `request failed` followed by a name resolution or timeout message: the network is unreachable or slow. Raise `timeout_seconds` in `[fetch]` if the site is slow.
- `response is larger than the limit`: raise `max_bytes` in `[fetch]`, or choose a smaller source. regwatch never truncates silently.
- `URL scheme 'http' is not allowed`: regwatch only fetches `https` and `file` URLs. Use the `https` address.
- `host resolves to a non-public address`: the name resolves to a loopback, link-local, private or other internal address, which regwatch refuses so that a hostile redirect or record cannot aim it at your own network. If the source really is on your network, set `allow_private_hosts = true` in `[fetch]`.
- `total time limit of N seconds exceeded`: the server was too slow overall, even if each step was quick. Raise `total_timeout_seconds` in `[fetch]` if the source is legitimately slow.
- `file URLs are disabled` or `file is outside the allowed_file_roots directories`: `file` sources work only under directories listed in `allowed_file_roots` in `[fetch]`. List the directory, for example `allowed_file_roots = ["snapshots"]`. Only regular files are read.
- `certificate verify failed`: regwatch always verifies certificates and has no option to turn that off. Fix the certificate chain, or read the source by hand with `manual`.

## a-feed-reports-error-dtd-or-entity

`feed declares a DTD or entity, which is refused`. regwatch will not parse a feed that contains a `DOCTYPE` or `ENTITY` declaration, because that is how entity expansion attacks are written. Real RSS and Atom feeds do not need either. If a trusted feed does, use `html` or `email-list` for it, which hash the text without parsing it as XML.

## a-feed-reports-error-not-an-rss-or-atom-feed

The content is well-formed XML but its root element is not `rss`, `feed` or `rdf`. The stored snapshot is often an error page or a login page. Read the snapshot file, then recapture or change the mechanism.

## check-says-suspicious

`SUSPICIOUS` means the source's signal is empty, or is less than half the length of the last accepted one. A site that starts serving an error page, or a feed that has been emptied, looks like this. Open the source and the stored snapshot. If the shorter content is genuine, record it with `regwatch check --accept --accept-suspicious`; a plain `--accept` deliberately does not.

## check-exits-with-status-4

`check --exit-code` exits 4 when a source is `ERROR` or `MISSING`: regwatch could not read it, so it cannot vouch that nothing changed. Status 3 means a source is `NEW`, `CHANGED` or `SUSPICIOUS`. See the output above the exit status for which sources.

## check-says-missing

`MISSING` means there is no stored snapshot for the source and you did not pass `--fetch`. Run `regwatch capture --source ID`, or `check --fetch`.

## check-says-changed-every-day

The signal for that source contains something that changes on every request, such as a timestamp or a session token in the page text. Prefer an `rss` or `api` source for the same publisher. For a page, switch to a different page that lists only the items you care about.

## ingest-needs-fetch-or-from-file

`ingest` has no default source of data. Pass `--fetch` to call the API, or `--from-file PATH` to parse a response you saved earlier.

## refusing-to-overwrite-protected-file

You pointed an output option such as `--out`, `--csv` or `--json` at a file regwatch protects: one listed under `[register]`, `regwatch.toml` itself, or `seen.json` or `ingest-candidates.json` in the state directory. regwatch compares files by identity, so a hard link or a different spelling of the name (including a different case) does not get around it. Choose a different output path. A path inside the state or snapshots directory is refused with `is inside regwatch's state directory`.

## brief-says-name-may-contain-only-letters-digits

The `--name` of `brief` becomes a file name, so it may contain only letters, digits, dots, hyphens and underscores, at most 100 characters, and may not start with a dot or a hyphen. A name with a slash or a space is refused. Use `--out-dir` to choose the directory.

## render-says-not-a-valid-document-model

`render` reads the JSON model that `brief --out-dir` writes. The message names what is wrong, such as a missing title or a section level other than 2, 3 or 4. Regenerate the model with `brief`.

## the-word-document-will-not-open

The `.docx` is a zip of WordprocessingML parts built directly, without a document library. Check that it is a valid package:

```bash
python3 -c "import zipfile, xml.dom.minidom as m; z = zipfile.ZipFile('briefing.docx'); m.parseString(z.read('word/document.xml')); print('ok')"
```

If that prints `ok`, the file is valid and the problem is in the program you opened it with. Please file an issue with the program and version.
