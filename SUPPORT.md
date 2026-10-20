# Support

This page says where to get help with Regwatch and where to file what. Regwatch is maintained in the open on GitHub and has no paid or private support channel; every question and report goes through the repository, where it is visible to the next person with the same problem. Regwatch is not a legal service, and no one here can tell you what a rule means for your business.

## Before You Ask

- Match your symptom against [Troubleshooting](docs/how-to-guides/troubleshooting.md).
- Check the [changelog](CHANGELOG.md) for what has shipped.
- Search the existing [issues](https://github.com/klappe-pm/regwatch/issues), open and closed.

## Where to File

| what you have | where it goes |
| --- | --- |
| a bug: Regwatch did something other than what the documentation says | a [bug report](https://github.com/klappe-pm/regwatch/issues/new?template=bug-report.yml) with the command you ran, what you expected, what happened and the output of `regwatch --version` |
| a question about using Regwatch | a [question](https://github.com/klappe-pm/regwatch/issues/new?template=question.yml) with what you are trying to do and what you tried |
| a request for a feature or a new source mechanism | a [feature request](https://github.com/klappe-pm/regwatch/issues/new?template=feature-request.yml) describing the need before any code; see [Contributing](CONTRIBUTING.md) |
| a suspected security vulnerability | a private report as described in [SECURITY.md](SECURITY.md); never a public issue |
| a mistake or gap in the documentation | an issue, or a pull request against the page; the [docs index](docs/README.md) shows where a page goes |

## What to Include

Paste command output as text inside a code fence rather than as a screenshot. Remove anything shaped like a credential, and do not attach your register: it may be confidential. A cut-down synthetic register that reproduces the problem is the most useful thing you can attach.

## Response Times

The project is maintained by one person alongside other work. Issues are read within a few days; fixes land as time allows and in order of impact.
