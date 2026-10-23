# Review Flagged Changes

This guide says what to do, in order, when regwatch flags something: a source whose content changed, an ingest candidate, or a candidate impact on a product. regwatch only detects and flags. Every step that changes your register or your change log is yours, and every conclusion is a person's. Nothing regwatch produces is legal advice.

## When a Source Changes

`check` reports `CHANGED` or `NEW` for a source. Do these in order:

1. Open the source itself, at the `url` in your sources file. Do not rely on the hash. If `check` says `SUSPICIOUS`, the content is empty or much shorter than before: treat that as a possible failure of the source, not as good news.
2. Find what changed. A stored copy from the last run is under your snapshots directory if you captured one.
3. Decide whether it matters. A new press release about an unrelated topic changes the signal and needs no action.
4. If it matters, read the primary text of the rule, not a summary of it.
5. Edit your own files by hand: add or revise the obligation row, add a change log event, and update the detail record. Set `last_reviewed` on the row to today.
6. Validate:

```bash
regwatch --config ~/my-register/regwatch.toml validate
```

7. Record the baseline so the same change is not reported again:

```bash
regwatch --config ~/my-register/regwatch.toml check --accept
```

Accepting is a statement that a person has looked at the change. Do not accept a change you have not read. A `SUSPICIOUS` source is not recorded by `--accept`; add `--accept-suspicious` only once you have confirmed that the shorter content is real.

## When an Ingest Candidate Looks Relevant

`ingest` writes candidates to `ingest-candidates.json` in your state directory, each marked `needs_review` with confidence `unconfirmed`. They also appear in the `v3` briefing under "Newly Detected, Unconfirmed".

1. Open the document at its `source_url` and read it.
2. Confirm the citations. The candidate lists the references the feed reported, and the feed can be wrong or incomplete.
3. If it belongs in your change log, copy the entry into your change log file by hand, set `obligation_id` if it relates to a row, and rewrite `what_happened` in your own words after reading the document.
4. Run `regwatch validate`.

The next `ingest` run replaces the candidates file, so work from a run you have already saved or copied.

## When an Impact Is Flagged

`impact` pairs an obligation with a product because they share a category, a term or a claim, and the product is exposed to the obligation's jurisdiction. The reasons are printed next to each pair.

1. Check that the product record is current. The pairing is only as good as the categories, terms, claims, markets and scopes you recorded for the product.
2. Read the obligation's source text and decide whether it reaches the product. A shared category is a reason to look, not a finding.
3. Record your conclusion where your organisation keeps decisions. regwatch has no field for it on purpose, because the conclusion is not regwatch's to make.
4. If the pairing is wrong because the product record is wrong, correct the product record and run `impact` again.

Severity orders the list by status and by how close the effective date is. It does not measure risk.

## What Regwatch Will Not Do

- It will not edit your obligations, change log, detail, enforcement or theme files.
- It will not decide that a rule applies, or that it does not.
- It will not send a notification. Read the output, or pass `--exit-code` to `check` and alert from your own job.

See [design](../explanation/design.md) for the reasoning.
