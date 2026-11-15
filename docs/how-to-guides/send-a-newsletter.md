# Send a Newsletter

This guide builds a newsletter from the last weeks of changes, checks it, and sends it from your own mail program. Regwatch writes the newsletter; it never sends email. It assumes you already have a project with a `regwatch.toml` and have run `capture` and `check` at least once, so there are snapshots to compare; see [schedule runs](schedule-runs.md). Newsletters are a premium feature.

## Turn On Premium Features

```bash
regwatch --config ~/my-register/regwatch.toml premium on
```

## Set the Look and the Closing Line

The newsletter follows the same design specification as your documents: the title format, the organisation, two colours, a font and a logo. Set them on the Settings page of `regwatch ui`, or in `regwatch.toml`. Both colours must reach a contrast of 4.5:1 against white, and the logo must be a PNG or an SVG inside the project folder; email shows a PNG logo only, so with an SVG logo the email has none, and the command and the Newsletters page say so. The design's `header` line runs above the logo. The `[newsletter] footer` line ends every issue; use it to say how to reply or unsubscribe.

```toml
[document]
title_format = "{organisation} regulatory update, {date}"
organisation = "Example Pantry Co."
primary_color = "#1d5a92"
accent_color = "#a8481a"
font = "Georgia"
logo = "brand/logo.png"
footer = "Example Pantry Co., 1 Example Road"

[newsletter]
footer = "Reply to this message to stop receiving these updates."
```

[configuration](../reference/configuration.md#document) lists every key and its limits.

## Build the Newsletter

Choose the period in days. The newsletter covers the sources that changed or could not be read, the developments in your change log, the unconfirmed items from the ingest feed and the candidate impacts of act now or high severity.

```bash
regwatch --config ~/my-register/regwatch.toml newsletter --since 14 --out ~/newsletters/issue-12
```

That writes `issue-12.eml`, `issue-12.html` and `issue-12.txt`. Add `--generate` to have the language model write the opening and the section summaries; see [turn on generated copy](turn-on-generated-copy.md). Each generated passage is labelled Generated and followed by the facts it was written from, so read those passages against their facts before you send.

## Check and Send

- Open `issue-12.html` in a browser to read the newsletter as it will look.
- Open `issue-12.eml` in your mail program. It has a subject and both parts but no recipient; many programs open it as a draft. Add the recipients and send it.
- Or paste the HTML into your mail tool's HTML editor, and the text into its plain text part. The HTML carries the logo inline, and mail programs drop it from pasted HTML; open the `.eml` file to keep it.

The Newsletters page of `regwatch ui` does the same: choose the period, preview the newsletter, press Generate for generated copy, copy the HTML or the text, or download the `.eml`, `.html` or `.txt` file.

Every item in the newsletter is a candidate for a person to confirm, and the newsletter ends with the statement that nothing in it is legal advice. Keep that statement when you edit the copy.
