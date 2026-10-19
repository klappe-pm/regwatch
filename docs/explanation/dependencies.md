# dependencies

This page justifies regwatch's dependencies, one by one, for a reader deciding whether to trust it or considering adding something. The short version is that there are no runtime dependencies at all: the package needs only the Python 3.11 standard library. Development tools are separate and are listed at the end.

## runtime-dependencies

None. The `dependencies` list in `pyproject.toml` is empty. Each capability that might have called for a package is covered by the standard library, as follows.

| need | standard library module | why no package |
| --- | --- | --- |
| read configuration | `tomllib` | TOML parsing is in the standard library from Python 3.11, which is why that is the minimum version |
| fetch over https | `socket`, `ssl`, `http.client`, `ipaddress` | one small client that vets the address it connects to, with a timeout, a total deadline, a size limit and a scheme allowlist, is easier to audit than a general purpose HTTP library, and it needs no certificate bundle of its own because it uses the system store |
| parse JSON | `json` | no alternative is needed |
| parse HTML | `html.parser` | only the visible text is needed, not a tree |
| parse feeds | `xml.etree.ElementTree` | made safe by refusing any DTD or entity declaration; see the [security model](security-model.md) |
| read the register | `csv`, `json` | the register is a CSV file and JSON files |
| hash content | `hashlib` | no alternative is needed |
| build a Word document | `zipfile` and string building | a `.docx` file is a zip of XML parts; the document model is plain, so a document library would add far more code than it saves |
| escape output | `html`, `xml.sax.saxutils`, `re` | no alternative is needed |
| read packaged data | `importlib.resources` | no alternative is needed |
| command line | `argparse` | no alternative is needed |

## why-this-matters-here

regwatch fetches and parses content from the outside world, and it is meant to run on machines that hold a confidential register. Every dependency would be code that runs in that position, with its own releases and its own vulnerabilities. Keeping the list empty keeps the part that needs auditing to the size of this repository, and keeps `pipx install` from pulling in anything else.

## what-the-choice-costs

- Feeds that declare a DTD are refused rather than parsed with a hardened library.
- The Word output is plain: headings, paragraphs and bullets, with no styles or tables.
- There is no retry logic or connection pooling. A failed fetch is reported and the next run tries again.
- There is no HTML tree, so a source cannot be narrowed to one element of a page. Choose a page, a feed or an API that lists only what you care about.

## the-bar-for-a-new-dependency

A runtime dependency is added only when all of these hold: the standard library cannot do the job reasonably, the package is widely used and actively maintained, it has no dependencies of its own that matter, and an issue has been opened and agreed first. The justification is then written here, in the table above, before the change merges. See [contributing](../../contributing.md).

## development-dependencies

These are installed with `pip install -e '.[dev]'` and are not needed to run regwatch.

| package | used for |
| --- | --- |
| `pytest` | the test runner |
| `pytest-cov` | the coverage report |
| `ruff` | linting and formatting |
| `mypy` | strict type checking of the package |
