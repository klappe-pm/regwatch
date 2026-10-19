# design

This page explains what regwatch is for and why it is built the way it is. It covers the stages of a run, the choice to flag candidates and never decide, how exposure and severity are worked out, and what regwatch leaves to people on purpose. It is explanation, not procedure: for steps see the [how-to guides](../how-to-guides/README.md), and for exact behaviour see the [reference](../reference/README.md).

regwatch flags candidates for human review. Nothing it produces is legal advice.

## the-problem

A business that sells regulated goods has to notice when a rule changes, work out which of its products the rule touches, and tell the right people. The sources are scattered: official feeds, agency pages, gazettes, mailing list archives. Reading all of them every day is tedious work that people skip, and the one day they skip is the day something is published.

regwatch does the tedious part. It reads the sources you list, notices when one changed, compares what you know about your products with what you know about the rules, and puts the likely matches at the top of a short briefing. It stops there.

## the-stages-of-a-run

1. Validate. The register is checked against field rules before anything else, so an analysis never runs on data with a dangling reference.
2. Capture. Sources are fetched into stored snapshots. This is the only stage that needs the network, and it is optional.
3. Check. Each source is reduced to a signal, hashed and compared with the last accepted hash. The result is `NEW`, `CHANGED`, `UNCHANGED`, `SUSPICIOUS`, `MISSING`, `MANUAL` or `ERROR`.
4. Ingest. A Federal Register style response is turned into candidate events, flagged unconfirmed.
5. Impact. Obligations are matched against products and ranked.
6. Brief. A document model is built: daily, weekly or tiered.
7. Render. The document model is turned into Markdown, a web post, a newsletter or a Word document.

Each stage reads the output of the one before it from files, so you can run any stage alone, in any order, and repeat it.

## why-regwatch-only-flags

The register is the expensive thing: someone read primary text, decided what it means, and wrote it down. If software edited it, you would not know which rows a person had stood behind. A change log that fills itself is no longer a record of what was decided.

So regwatch has no code path that writes the register. The write protection is enforced, not promised: every write goes through one function that refuses a register path, and a test runs every command and checks that the register files are byte for byte unchanged.

The same reasoning is why `check` needs an explicit `--accept`. Recording a baseline is a statement that a person looked at the change. If it happened automatically, the first flag would silence itself.

Ingest candidates follow the same rule. They are labelled unconfirmed in the file, in the briefing and in the feed, and they live in the state directory, away from your change log. A person copies a candidate across after reading the document.

## what-the-matching-means

Impact analysis has three gates, and a pair is flagged only when all three pass.

- Exposure. Jurisdictions form a tree through the `parent` field. A rule and a market are related when they lie on one path of the tree. A product sold in a region is subject to its national rules, and a product sold nationally is exposed to every regional rule. Siblings are unrelated.
- Scope. An obligation can be limited to a scope such as a sales channel. It applies to a product only if the product lists that scope.
- Attribute match. The obligation and the product must share a category, a named term or a claim.

The gates are deliberately simple and explainable. When a pair is flagged, the output says which category, term or claim matched, so a reader can see in a second whether the match is meaningful. They are also deliberately generous: a missed match is worse than an extra one, because a person can dismiss an extra one in a minute.

Severity is a score built from the obligation's status, how soon it takes effect, and whether a named term matched. It orders the list so the first screen is the one to read. It is not a measure of legal risk, and the documentation never presents it as one.

## snapshots-and-repeatability

By default `check` reads a stored snapshot instead of the network. This has three effects. A run is repeatable: the same snapshots give the same result. It works offline, which makes it testable and usable on a locked-down machine. And it separates fetching from comparing, so you can fetch on one schedule and compare on another, or capture with a tool of your own and hand regwatch the file.

`check --fetch` skips the snapshot and fetches now, for a one-off look.

## briefings-are-assembled-not-written

The briefings are built by code from structured data. They contain only text that is in your register files or is a fixed sentence in the program. There is no language model in the loop, so a briefing cannot contain a statement that nobody wrote. If you want a model to draft a summary, do that outside regwatch and keep the result as a human-reviewed detail record. The reasons are in [design decisions](../../developer-docs/explanation/design-decisions.md).

## what-regwatch-leaves-to-people

- Deciding that a rule applies, or does not.
- Reading primary text. The hash tells you a page changed, not what changed or whether it matters.
- Keeping product records accurate. The analysis is only as good as the categories, terms, claims, markets and scopes you record.
- Scheduling. regwatch runs when you run it.
- Telling anyone. It prints and writes files; it sends nothing.
