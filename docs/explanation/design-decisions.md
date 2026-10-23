# Design Decisions

This page records the choices that shaped regwatch, each with the alternative it rejected and the cost it accepts. It is for a contributor who is about to propose a change to one of them: read the reasoning first, and if you still disagree, open an issue that answers it. It also records what was deliberately not built, so that the absence is not mistaken for an oversight.

The engine was extracted from a private repository where it served one organisation. The decisions below are the ones that turned a single-purpose script into a general engine.

## No Language Model Stage

The engine contains no language model call, no prompt, and no API key handling. Briefings are assembled by code from structured data. The alternative was an optional synthesis stage that asks a model to write summaries. It was left out because the source engine did not have one, because a stage that can write sentences nobody reviewed works against the position that every statement in a briefing traces to a register file or a fixed sentence, and because it would add a credential to a tool designed to read none. Anyone who wants model-written text can produce it outside regwatch and keep it as a detail record, where it is reviewed like any other record.

If a pluggable stage is added later, it must be off by default, it must read a key only from an environment variable whose name is configured, it must never log the key, and it must pass through the same disclaimer and escaping as everything else.

The [workspace](workspace.md) plan adds that stage as a premium feature under these conditions, with one change: the key is read from the operating system keychain, and the environment variable remains as an override.

The stage now exists, in `regwatch/llm.py`, and keeps those conditions. It is off unless premium features are on and `[llm] enabled` is set, and it runs only when a newsletter or a document is asked for with `--generate`. The key is read under a fixed name per provider, `REGWATCH_KEY_ANTHROPIC` or `REGWATCH_KEY_OPENAI`, so no setting can point it at another variable. The model is given only structured facts with ids and must cite them; a passage that cites anything else is dropped and reported. Kept text is escaped like everything else, labelled Generated in every format, and shown next to the facts it cites, so the position that every statement traces to a register file or a fixed sentence becomes: every statement traces to a register file, a fixed sentence, or a labelled passage with its facts beside it. Without `--generate` the same newsletters and documents use fixed sentences built from the data. The alternative, letting the model write freely from the whole briefing, was rejected because nothing could then be checked against a source. The cost is copy that reads more stiffly than a free summary would, and a call that is spent when the model cites a fact it was not given. The call goes through the fetch client's new POST, which follows no redirect and allows plain http only to a loopback IP literal; that exception exists so a local Ollama model can be used without sending the facts anywhere.

## Domain-Neutral Vocabulary

The source engine spoke in terms of one industry: ingredient functions, a company's product lines, two countries and their retail channels. The general engine uses neutral terms. An ingredient function became a category, a named ingredient became a term, a channel became a market, and the hard-coded jurisdiction logic became a tree built from the `parent` field. The alternative was to keep the food vocabulary. The neutral terms cost a little clarity in the food case and make the engine usable for any regulated attribute. The matching rules and the severity scoring are unchanged in substance.

The sidecar that held industry-specific lenses over the impacts became the optional themes file, so the lenses are data you write and not code you edit.

## Snapshots Are Read by Default

`check` reads a stored snapshot unless `--fetch` is given. The source engine behaved differently: a snapshot, when present, always won over a live fetch, so `--live` silently did nothing for any source that had one. Making the choice explicit means `check --fetch` always looks at the live source, and `check` always looks at the stored one. The cost is one extra step, `capture`, to refresh the stored copy.

## Accepting Is Explicit

`check` never records a baseline unless `--accept` is passed. This matches the source engine. See [design](design.md) for why.

## No Unverified TLS Fallback

The source engine retried without certificate verification when a government site served an incomplete chain. regwatch does not, and has no option to. An unverified fetch can be answered by anyone on the path, and the whole point of the tool is to trust what it reads. A site with a broken chain reports `ERROR`, and the documented remedy is the `manual` mechanism. The cost is that some sites cannot be fetched automatically.

## Proxies Are Ignored

The fetch client connects directly and ignores `HTTPS_PROXY`. A proxy resolves the host name itself, so regwatch could not check which address the request reaches, and the private address check would be decorative. The alternative was to honour the proxy and skip the check when one is set. The cost is that a machine that reaches the internet only through a proxy cannot use `--fetch`; it can run `check` on snapshots captured another way.

## The Fetch Client Owns Its Sockets

The first version used `urllib`, which resolves the name again when it connects. That left a gap between checking an address and using it. The client now opens the socket to the address it vetted and wraps it for TLS using the original host name, so the certificate is still checked against the name. The cost is about 100 more lines in `fetch.py` than a thin wrapper, in the one module that already carries the burden of the security argument. Resolver, connector and TLS wrapper are injectable so the whole path is tested without a network.

## File Sources Are Off by Default

`allowed_file_roots` is empty by default, so every `file` source is refused until you list a directory. The alternative was to default the root to the directory of `regwatch.toml`. That is more convenient, but a register entry could then copy any file under it, including the register itself, into the snapshots. See the [security model](security-model.md).

## Suspicious Is a Status, Not a Heuristic Hidden in Changed

An emptied or sharply shortened source is reported as its own status, `SUSPICIOUS`, and is not recorded by `--accept` without `--accept-suspicious`. Folding it into `CHANGED` would let a hostile page replace the baseline with an empty one after a single flag. The thresholds are a signal under half of the accepted length when that was at least 20 characters; they are constants in `check.py`.

## Markdown Output Escapes Instead of Trusting

Markdown and web post output escape every metacharacter in every value. The alternative was to escape only the fields that come from ingest. Briefings mix register text and candidate text in one string, so a field-by-field rule would be easy to get wrong the next time a section is added. Escaping everything costs readability of the raw Markdown and none of the rendered result.

## No Browser User Agent

The source engine sent a browser user agent string to get past sites that reject other clients. regwatch sends an honest, configurable `User-Agent`. A site that blocks it is read by hand with `manual`.

## XML Is Refused, Not Hardened

Feeds that declare a DTD or entity are refused instead of being parsed with a hardened library. See the [security model](security-model.md) for the reasoning and the tradeoff. The alternative, `defusedxml`, would add a dependency to the one part of the package that parses hostile input.

## One Document Model for Every Briefing

In the source engine the tiered briefing produced Markdown directly while the daily and weekly briefs produced a document model. In regwatch all three build a `Document`, so `render` can produce any format from any briefing and `brief --out-dir` always writes a model next to the Markdown. The cost is that the tiered briefing lost the nested bold formatting of its source version, because the model holds plain paragraphs and bullets.

## Commands That Were Consolidated or Not Ported

- `scan`, `capture` and the `--live` flag became `check`, `capture` and `--fetch`, with the snapshot behaviour above.
- `briefing` and `brief` became one `brief` command with a `--kind` option.
- The Word, newsletter and web post renderers became the separate `render` command, which works from a saved model.
- The `newsletter` command, which wrote a running index of records that linked to sibling report files by name, was not ported. It depended on a rollout directory layout specific to one project. `digest`, `report` and `export` cover the general cases.
- Scheduled workflows were not ported. There is no CI in this repository, and scheduling is left to the user. The how-to guide on [adding a source](../how-to-guides/add-a-source.md) shows the commands to schedule.
- A fixed set of industry lenses became the themes file. A fixed file of one agency's warning letter themes became the enforcement file.

## Detail Records Are Optional

The source engine required a detail record for every obligation and failed validation without one. regwatch allows an obligation to have none, and the tiered briefing shows a placeholder that says detail is pending. A required record forces a new user to write prose before they can run anything. The cost is that a register can quietly lack detail; `export` shows which obligations have none, since their summary column is empty.

## One GitHub Actions Workflow

The only workflow in the repository publishes a release when a version tag is pushed; see [Cut a Release](../how-to-guides/cut-a-release.md). There is no continuous integration workflow. The checks in [Run the Tests](../how-to-guides/run-the-tests.md) are run locally before a change is committed, and the release workflow runs the suite once more against the built wheel before anything is uploaded.
