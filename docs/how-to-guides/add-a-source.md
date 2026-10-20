# Add a Source

This guide shows how to watch a new source: a feed, a web page, an API, a mailing list archive or a page you will read by hand. You add one entry to your sources file, capture its content once, and let `check` compare later runs against it. It assumes a working register; see [getting started](../tutorials/getting-started.md) if you do not have one.

## Choose a Mechanism

The `mechanism` field tells regwatch how to reduce the content to a signal before hashing it. The signal is what gets compared, so a mechanism that ignores page furniture avoids false alarms.

| mechanism | use it for | the signal is |
| --- | --- | --- |
| `rss` | an RSS or Atom feed | one row per item (date, id, link, title), sorted |
| `api` | a JSON API | for a response with a `results` list, one row per document (publication date, document number, title), sorted; otherwise the canonical JSON |
| `html` | a web page | the visible text, with scripts, styles and markup removed and whitespace collapsed |
| `email-list` | a plain text archive | the text with trailing whitespace removed |
| `manual` | a page that blocks automated clients | none; regwatch lists it as `MANUAL` so you remember to read it |

Prefer `rss` or `api` when the publisher offers one. A feed or API changes only when something is published, while a page can change for reasons that do not matter.

## Add the Entry

Add an object to the `sources` list in your sources file. The `jurisdiction` must already exist in your jurisdictions file, and the `source_id` must be lowercase letters, digits and hyphens because it becomes a file name.

```json
{
  "source_id": "sv-newsroom-feed",
  "jurisdiction": "sv",
  "name": "Southvale newsroom feed",
  "url": "https://news.sv.example/feed.xml",
  "method": "poll",
  "mechanism": "rss",
  "cadence": "daily",
  "notes": "Press releases."
}
```

The `url` must use `https`, or `file` for content you keep on disk. regwatch refuses every other scheme. A `file` source is read only if its directory is listed in `allowed_file_roots` in the `[fetch]` table of `regwatch.toml`, and only if it is a regular file. An `https` source must resolve to a public address unless you set `allow_private_hosts`. Then confirm the register is still valid:

```bash
regwatch --config ~/my-register/regwatch.toml validate
```

## Capture the First Copy

`capture` fetches the source and stores the raw content under your snapshots directory:

```bash
regwatch --config ~/my-register/regwatch.toml capture --source sv-newsroom-feed
```

Read the stored file once to confirm it is what you expected. A login page or an error page stored as a snapshot will hash the same every day and hide real changes.

## Record the Baseline

Check the new source and accept the result as the baseline:

```bash
regwatch --config ~/my-register/regwatch.toml check --source sv-newsroom-feed --accept
```

From now on `check` reports `CHANGED` when the signal differs from this baseline.

## Schedule the Check

regwatch runs when you run it and does not install a scheduler. To check on a schedule, run `capture` and then `check` from your own scheduler, such as cron. Add `--exit-code` to `check` so the job can alert on exit status 3:

```bash
regwatch --config ~/my-register/regwatch.toml capture
```

```bash
regwatch --config ~/my-register/regwatch.toml check --exit-code
```

Capturing replaces the stored copy. If you want to compare the old and new text when a source changes, copy the snapshots directory to a dated archive of your own before each capture.

## Check the Live Fetch Without Storing

`check --fetch` fetches each source now instead of reading its snapshot. It records nothing unless you also pass `--accept`:

```bash
regwatch --config ~/my-register/regwatch.toml check --fetch --source sv-newsroom-feed
```

## Limits

Every fetch has a timeout and a size limit, set in the `[fetch]` table of `regwatch.toml`; see [configuration](../reference/configuration.md). A source larger than the limit is reported as `ERROR`, not truncated. If a source needs a login, a cookie or a script to render, use `manual`.
