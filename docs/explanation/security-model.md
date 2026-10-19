# security-model

This page explains what regwatch protects against and how, for a reader deciding whether to run it on a machine that holds a confidential register. Every claim below matches the code, and every limit is given with its number. It covers the fetch client, the parsing of untrusted content, the cleaning of text, the escaping of output, the detection of suppressed changes, the write path, and what regwatch trusts. It is explanation, not procedure: it says why the pieces exist and what they do not cover. To report a vulnerability, see [security.md](../../security.md).

## what-regwatch-trusts

regwatch trusts your configuration file and your register files. They are yours, and regwatch reads them as written. It does not trust anything that arrives from outside: feed contents, web pages, API responses, the file you pass to `ingest --from-file`, and the candidates file in the state directory, which a person or another program may have edited. Each is handled as described below.

It reads no secret. There are no API keys, tokens or passwords anywhere in the configuration, and no setting comes from the environment. Proxy environment variables such as `HTTPS_PROXY` are deliberately ignored; see below.

## the-fetch-client

All network access goes through one class, `SafeFetcher` in `regwatch/fetch.py`. It opens sockets itself and has these properties.

- Only two schemes are accepted, `https` and `file`. `http`, `ftp`, `data`, `javascript` and a bare path are refused before any connection is made. A URL that contains a space, a control character (U+0000 to U+0020, U+007F to U+009F), credentials, or an invalid port is refused.
- `file` URLs are off by default. They work only for files under a directory listed in `allowed_file_roots`, after symbolic links and `..` segments are resolved. Only regular files are read: a named pipe, a device and a directory are refused, and the file is opened without blocking so a pipe cannot hang the run. See [why file sources are opt in](#why-file-sources-are-opt-in).
- A host name is resolved once, and every resulting address must be globally routable. Loopback (127.0.0.0/8, ::1), link-local (169.254.0.0/16, fe80::/10), private (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16), unique local (fc00::/7), shared (100.64.0.0/10), reserved, multicast and unspecified addresses are all refused, and so is an IPv4-mapped IPv6 address of any of them. One bad address in the answer refuses the host. The check applies to IP literals in URLs too, and to every redirect. Setting `allow_private_hosts = true` turns it off, for sources on your own network.
- The connection goes to the address that was vetted, not to a second lookup of the name, so a DNS answer that changes between the check and the connection cannot redirect the request. The TLS handshake still verifies the certificate against the original host name.
- Certificates are always verified. There is no fallback to an unverified connection.
- A redirect may only lead to another `https` URL, and at most 5 redirects are followed. Each hop is vetted like the first request.
- Time is limited three ways. Each socket operation has a timeout, default 20 seconds. The whole fetch, including every redirect, has a total deadline, default 60 seconds. The deadline is enforced by checking the clock before every read of at most 16,384 bytes, and by a watchdog timer that shuts the socket down when the deadline passes, so a server that sends one byte at a time, or never answers, cannot hold the run past it. The one step the deadline cannot interrupt is the operating system's name lookup.
- The body is limited to `max_bytes`, default 2,000,000 and at most 100,000,000. A response larger than the limit is an error, never a truncation, because a truncated page would hash differently and look like a change. A declared `Content-Length` over the limit is refused before the body is read.
- Proxy environment variables are ignored. A proxy would resolve the host itself, which would defeat the address check, so regwatch connects directly. A machine that can reach the internet only through a proxy cannot use `--fetch`; it can capture snapshots with another tool and run `check` on them.
- No shell, subprocess or external program is ever started. A test checks the module's imports and calls.

The fetch client is a protocol with one method, and the class takes a resolver, a connector and a TLS wrapper as arguments. Tests pass fakes built on socket pairs, and a fixture blocks every real socket for the whole suite, so a test cannot reach the network by accident.

### why-file-sources-are-opt-in

A `file` source copies a local file into the snapshots directory, where later commands print and render pieces of it. If a register could name any path, a single wrong or hostile source entry would copy a private key or a password file into a place that is easy to publish by accident. regwatch could instead have defaulted the root to the directory holding `regwatch.toml`, which is convenient but still exposes everything under it, including the register. It chose the stricter default: no file roots at all. You name each directory deliberately, as in `allowed_file_roots = ["snapshots"]`.

## parsing-untrusted-content

Four kinds of content are parsed, and none is evaluated.

- JSON goes through the standard `json` module. Input nested so deeply that the parser fails is caught and treated as an error.
- HTML goes through the standard library tokenizer, which collects visible text and skips script, style and template content. It builds no tree and runs nothing.
- Feeds go through ElementTree, but only after the content is checked for a `DOCTYPE` or `ENTITY` declaration. A document that contains either is refused outright, before it is parsed.
- API responses for `ingest` are JSON, and every field is type checked and cleaned as described next. At most 1,000 documents are read. Numbers that become part of a URL must be 1 to 4 digits.

### why-not-defusedxml

The usual advice for untrusted XML is to use the `defusedxml` package. regwatch takes a narrower route that needs no dependency. Entity expansion attacks, such as the billion laughs attack and external entity resolution, all require a declaration in the document type definition. RSS and Atom feeds do not need one. Refusing every document that contains a `DOCTYPE` or an `ENTITY` declaration removes the whole class of attack, and the check is a single pattern match that runs before the parser sees the document.

The tradeoff is that a feed that legitimately declares a DTD is refused. In practice that is rare, and the failure is visible and safe: the source reports `ERROR` with the reason. The documented fallback is to treat that source as `html` or `email-list`, which hash the text without parsing XML. A test feeds the parser a classic entity expansion document and checks that it is refused quickly.

## cleaning-text

Text that came from outside is cleaned in `regwatch/sanitize.py` wherever it enters a file, the terminal or a rendered document.

- Control characters are removed: C0 (U+0000 to U+001F), DEL (U+007F) and C1 (U+0080 to U+009F). That includes ESC (U+001B), so a value cannot carry a terminal escape sequence, and the 8-bit forms of those sequences. Lone surrogates become U+FFFD, so text can always be encoded. Whitespace is collapsed, so a value stays on one line.
- Ingest fields are cut to fixed lengths: 200 characters for a title, 320 for the summary, 120 for the agency, 40 for the document type. A document number must match `[A-Za-z0-9._-]{1,40}` or it is dropped.
- A link is kept only if it is a plain https link: at most 2,000 characters, with a host and no credentials, and with no whitespace, control character, quote, backslash, brace, bar, caret, backtick, or any of `()[]<>`. Such a link cannot close a Markdown link or an HTML attribute, and cannot be a `javascript:` or `data:` URL. The same rule is applied again when a briefing reads the candidates file, because that file may have been edited.
- Messages from failed fetches are cleaned before they are printed, written to a report, or shown in an error line.

## escaping-output

Rendered output is meant to be opened by other people, so it is treated as an attack surface.

- Markdown and web post output backslash-escapes every Markdown metacharacter in every value: backslash, backtick, asterisk, underscore, square brackets, angle brackets, ampersand, hash, tilde, bar and exclamation mark, plus a leading list marker. A value therefore renders as literal text and cannot become a link, an image, raw HTML, a heading or a list item. The cost is that raw Markdown looks busier than the rendered page.
- HTML output escapes every piece of text, so a page title with markup in it appears as text.
- Word output escapes text and strips characters that are invalid in XML, so the file stays a valid package whatever it contains.
- Web post front matter writes titles as quoted strings, and a tag must match `[A-Za-z0-9_-]{1,40}`.
- CSV and JSON exports: any CSV cell that begins with `=`, `+`, `-`, `@`, a tab or a carriage return gets a leading apostrophe, so a spreadsheet shows text instead of running a formula. The apostrophe is visible to a program that reads the CSV; JSON output is not changed.
- Every format ends with the disclaimer. A document model cannot remove it, because loading a model always restores it. A model is limited to 2,000 sections, 5,000 items per list and 20,000 characters per value.

## change-detection-that-cannot-be-hidden

A hash comparison can be defeated by the content itself: a source that starts serving an empty page, or a short error page, is reported as "changed" once and then quietly becomes the baseline. regwatch treats that as the attack it may be.

- A source whose signal is empty is reported `SUSPICIOUS`, even on first sight.
- A source whose signal is shorter than half of the accepted signal, when the accepted signal was at least 20 characters, is reported `SUSPICIOUS` even though its hash changed.
- `check --accept` does not record a `SUSPICIOUS` result. It takes `--accept-suspicious` as well, so a person has to say that the shorter content is expected.
- `check --exit-code` exits with 3 when a source is `NEW`, `CHANGED` or `SUSPICIOUS`, and with 4 when a source is in `ERROR` or `MISSING`, because a source regwatch cannot read is a source it cannot vouch for. Exit status 4 wins over 3.

## the-write-path

regwatch writes only to its state directory and to paths you name on the command line. Every write goes through one function that writes to a temporary file in the same directory and renames it into place, so an interrupted run never leaves a half-written file.

A path you name is refused if it is any of these: a register file, `regwatch.toml`, `seen.json`, `ingest-candidates.json`, or anything inside the state directory or the snapshots directory. The comparison is by identity: when both files exist they are compared with `os.path.samefile`, which sees through symbolic links, hard links and case-insensitive file systems, and when the target does not exist yet the resolved names are compared with case folded. regwatch's own state files are protected from the register paths only, so `check --accept` and `ingest` can still write them.

A source id becomes a file name only if it matches `^[a-z0-9-]+$`, so an id cannot point outside the snapshots directory. `brief --name` must match `[A-Za-z0-9_][A-Za-z0-9._-]{0,99}`, so it cannot contain a path separator. Register files and state files are read only up to 20,000,000 bytes, and the configuration file only up to 256,000.

## what-regwatch-does-not-protect-against

- A compromised source. If a publisher serves misleading content over a valid certificate, regwatch reports the change faithfully. A person has to read it.
- A hostile register. regwatch assumes your own files are well-meant. It bounds their size, but it is not a sandbox for files from a stranger.
- The programs you open the output with. regwatch makes the output safe to read as data, but a vulnerability in a word processor, a spreadsheet or an email client is out of scope.
- The name lookup. The operating system's resolver is called before the deadline watchdog starts and cannot be interrupted. It also sees the host names you monitor.
- A change between the check and the read of a local file. regwatch checks a `file` source's type on the open file, but a person with write access to an allowed root can still swap the file's content.
- Confidentiality of the machine. Snapshots, state and rendered files are ordinary files with the permissions of your account.
