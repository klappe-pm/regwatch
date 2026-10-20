# Security Policy

## Reporting a Vulnerability

Report vulnerabilities privately through GitHub security advisories: open the repository's Security tab and choose "Report a vulnerability", or go to <https://github.com/klappe-pm/regwatch/security/advisories/new>. Do not open a public issue, pull request or discussion for a suspected vulnerability.

Include the affected version or commit, the steps to reproduce, and the impact you observed. You will receive an acknowledgement, and the fix and disclosure are coordinated with you through the advisory.

## Scope

- The `regwatch` command and the Python package.
- The fetch client in `regwatch/fetch.py`: any way to reach a URL scheme other than `https` and `file`, to reach a loopback, link-local, private or other non-public address without `allow_private_hosts`, to read a file outside `allowed_file_roots` or one that is not a regular file, to outlast the total deadline, to read more than the configured size limit, or to start a program.
- The content parsers in `regwatch/extract.py` and `regwatch/ingest.py`: any input that makes them evaluate content, expand an XML entity, or use unbounded time or memory.
- The renderers in `regwatch/render.py` and the cleaning in `regwatch/sanitize.py`: any input that produces output that is not escaped, keeps a terminal escape sequence, or becomes a link, image or raw HTML in Markdown output; and the CSV export, for any cell a spreadsheet would run as a formula.
- The write path in `regwatch/state.py`: any way to make Regwatch overwrite a register file or write outside the paths you name.

Weaknesses in the sources you choose to monitor, and in the software you open the rendered files with, are out of scope. How Regwatch treats untrusted content and what it trusts is described in the [Security Model](docs/explanation/security-model.md).

## Supported Versions

Only the latest release and the `main` branch receive security fixes. Until the first release, only `main` does.
