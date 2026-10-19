# support

This page says where to get help with regwatch and where to file what. regwatch is maintained in the open on GitHub and has no paid or private support channel; every question and report goes through the repository, where it is visible to the next person with the same problem. regwatch is not a legal service, and no one here can tell you what a rule means for your business.

## before-you-ask

- Match your symptom against [troubleshooting](docs/how-to-guides/troubleshooting.md).
- Check the [changelog](changelog.md) for what has shipped.
- Search the existing [issues](https://github.com/klappe-pm/regwatch/issues), open and closed.

## where-to-file

| what you have | where it goes |
| --- | --- |
| a bug: regwatch did something other than what the documentation says | an [issue](https://github.com/klappe-pm/regwatch/issues/new) with the command you ran, what you expected, what happened and the output of `regwatch --version` |
| a question about using regwatch | an [issue](https://github.com/klappe-pm/regwatch/issues/new) with what you are trying to do and what you tried |
| a request for a feature or a new source mechanism | an [issue](https://github.com/klappe-pm/regwatch/issues/new) describing the need before any code; see [contributing](contributing.md) |
| a suspected security vulnerability | a private report as described in [security.md](security.md); never a public issue |
| a mistake or gap in the documentation | an issue, or a pull request against the page; the [documentation guide](docs/documentation-guide/README.md) says where a page goes |

## what-to-include

Paste command output as text inside a code fence rather than as a screenshot. Remove anything shaped like a credential, and do not attach your register: it may be confidential. A cut-down synthetic register that reproduces the problem is the most useful thing you can attach.

## response-times

The project is maintained by one person alongside other work. Issues are read within a few days; fixes land as time allows and in order of impact.
