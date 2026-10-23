# Explanation

Explanation pages give background and reasons. They are for reading away from the keyboard, when you want to understand why Regwatch behaves and is built as it is rather than how to make it do something. They discuss tradeoffs and alternatives, which the tutorials, how-to guides and reference pages leave out on purpose.

## Pages

- [Design](design.md): what Regwatch is for, the stages of a run, why it only flags, and what it deliberately leaves to people.
- [Security Model](security-model.md): how fetched content is treated as untrusted, what the fetch client allows, how files are written, and what Regwatch trusts.
- [Dependencies](dependencies.md): why Regwatch has no runtime dependencies, what that choice costs, and the bar a future dependency must clear.
- [Architecture](architecture.md): how the modules fit together, which way data flows, and where the trust boundaries sit.
- [Design Decisions](design-decisions.md): the choices that shaped the code, with the alternative each one rejected, including what was deliberately not built.
