# Use the Web App

This guide opens the Regwatch web app for a project, finds your way around it, and changes the settings it can change. The web app is a local page in your browser that reads the same files as the command line and does what the commands do. Only Run now on the Automations page reaches the network; everything else works with no connection, and nothing is sent anywhere else. It assumes you already have a project with a `regwatch.toml`; if you do not, start with [getting started](../tutorials/getting-started.md).

## Open It

Run `regwatch ui` with your configuration file. It starts a small server on `127.0.0.1`, prints the address, and opens your browser at it.

```bash
regwatch --config ~/my-project/regwatch.toml ui
```

The address it prints carries a private token, for example `http://127.0.0.1:53817/?token=...`. The token works once. The first browser that opens the address trades it for a separate session cookie and the address bar drops it, so it is not left in your history; after that the printed address is refused, so a copy of it in your terminal, a shared log or the browser's command line is no use to anyone. Opening the address again in the same browser keeps you signed in. To use another browser, stop the server and start it again for a new address.

To choose the port, add `--port 8765`. To print the address without opening a browser, for example on a machine you reach over SSH with a forwarded port, add `--no-open` and open the address yourself. Press Ctrl+C in the terminal to stop the server; the browser tab stops working then.

## Find Your Way Around

The navigation rail on the left lists every page. The button at its foot collapses it to icons, and the browser remembers that choice. On a narrow screen the rail always shows icons.

The search box at the top of the rail searches your sources, the changes and your obligations at once. Type a name, a jurisdiction or a term, move through the results with the arrow keys, and press Enter to open one. Escape closes the results.

| page | what it shows |
| --- | --- |
| Overview | counts of new, changed, suspicious and failing sources, the next scheduled run, the highest priority regulatory changes, your supply chain sources (Ingredients Supply, Packaging Materials and Commodities and Forecasts) with their last status, the sources to review and what takes effect in the next 90 days |
| Changes | every candidate impact ranked by focus area, severity and date, with filters and a panel that says why a change was flagged, then the source changes and the unconfirmed candidates from `ingest` |
| Sources | the sources you watch with the status of each stored snapshot, and the source catalogue with type-ahead search, filters by category, region, kind and access, and an Add button for each source; with the search box empty the catalogue is grouped by category, and while you type it is one list with the best match first |
| Obligations | your register, read only, with the products each obligation may affect |
| Briefings | the tiered briefing, the daily brief and the weekly synthesis, rendered, with export to Markdown, HTML and Word, and to PDF through the browser's print dialog |
| Newsletters, Documents | premium features; see [premium features](#premium-features) |
| Automations | the installed schedule with its next run, the run history, and Run now |
| Keys | for each source you watch that needs a key, whether one is available and where from, with set and remove |
| Settings | your focus areas, the premium toggle, the document design and the language model provider |

The pages read the files every time they load, so after you run `regwatch capture`, `check --accept` or `ingest` in a terminal, reload the page to see the result. Status on the Overview, Changes and Sources pages comes from the stored snapshots, as `regwatch check` without `--fetch` reports it.

## Add Sources, Set Keys and Run

- Add a source: on the Sources page, search the catalogue (the ranking is the one `regwatch sources search` uses, shown as one list in that order, with each source's category beside its publisher), narrow it by category, region, kind and access, and choose Add. This runs `regwatch sources add`: the source is written to your sources file, with its jurisdiction when your register lacks it, and a source you already watch shows Watching. If the source needs a key, the page says so.
- Set a key: on the Keys page, paste the key and choose Set. It is stored in the system keychain, as `regwatch keys set` stores it, and the page never shows it again; it shows only whether a key is available and whether it comes from the keychain or an environment variable. Without a keychain tool (security on macOS, secret-tool on Linux), set the environment variable shown instead.
- Run now: on the Automations page, Run now does what `regwatch run` does: it captures every source, checks them and writes a run record. It runs in the background, one run at a time, and the page updates when it finishes. The schedule itself is installed with `regwatch schedule --install`; the page shows it and its next run.

## Change Settings

The Settings page writes to `regwatch.toml` and nothing else. It changes one line at a time and keeps every comment and every other setting in the file. If the file is written in a form the web app cannot change safely, such as a dotted key like `premium.enabled = true`, the page says so and leaves the file alone; change that setting in the file by hand.

- Focus areas: tick the areas that match your business and choose Save Focus Areas. This writes `[profile] focus_areas`, the same setting `regwatch init` writes. See [set your focus areas](set-your-focus-areas.md).
- Premium features: the switch writes `[premium] enabled`.
- Document design (premium): the title format, organisation, primary and accent colours, typeface, logo path, header, footer and page size, plus the line at the foot of each newsletter. A swatch beside the form shows the colours and typeface as you type, and a colour lighter than 4.5:1 against white gets a warning and cannot be saved. Save Design writes `[document]` and `[newsletter] footer` after the same checks `regwatch.toml` gets, so a logo outside the project folder, too large or not a PNG or a safe SVG is refused with the reason. See [build documents in your design](build-documents-in-your-design.md).
- Generated copy (premium): the switch, the provider (Anthropic, OpenAI or Ollama) and the model; leave the model empty for the provider's default. Save Provider writes `[llm]`. Beside it each provider key shows whether it is set and where from, with Set and Remove that store the key in the keychain as `regwatch keys set llm-anthropic` does; the page never shows a key. See [turn on generated copy](turn-on-generated-copy.md).

The web app never changes your register files. To add an obligation or a source, edit the register as before.

## Premium Features

Newsletters, document templates, generated copy and runs more often than once a day are premium features. While premium is off the web app shows them with a lock and a one-line note rather than hiding them. Turn premium on with the switch in Settings, or from a terminal:

```bash
regwatch --config ~/my-project/regwatch.toml premium on
```

`regwatch premium status` shows whether it is on, and `regwatch premium off` turns it off. Regwatch is MIT licensed, so the toggle is a product boundary, not a lock: anyone can turn it on.

With premium on:

- Newsletters: choose a period of 7, 14, 30 or 90 days. The page shows the newsletter as your readers will see it, in a frame that cannot run scripts. Copy HTML and Copy Text put either part on the clipboard for pasting into your mail tool, and the downloads give the `.eml`, `.html` and `.txt` files `regwatch newsletter` writes. Regwatch never sends it. See [send a newsletter](send-a-newsletter.md).
- Documents: choose a briefing, a register digest or a change and due report, and for a briefing its detail. The preview is the HTML in your design, and the downloads give HTML, Word or Markdown. To save a PDF, open the HTML download and print it.
- Generate: on both pages, when generated copy is on, Generate sends structured facts to your provider and writes the opening and summaries. Generated text is labelled Generated and followed by the facts it was written from; check it against them before you use it. The downloads then carry the same copy. Without Generate, the same places hold fixed sentences built from your data.

## If It Does Not Open

- `error: the web app is not built into this installation`: the installed package lacks the built pages. This happens only when running from a checkout where `regwatch/web/` was deleted; run `scripts/build-web.sh` as described in [change the web app](change-the-web-app.md), or install a released version.
- `error: cannot listen on 127.0.0.1:8765`: another program uses that port. Leave `--port` out to take a free one.
- A page that says the request has no valid token: open the exact address `regwatch ui` printed. A token belongs to one run of the server, so an address from an earlier run no longer works.
- A page that says the address has been used already: the token works once, and another browser or window opened it first. Stop `regwatch ui` with Ctrl+C and start it again for a new address. If you did not open it anywhere else, someone else may have, so stop the server first.
- A page that says the register is invalid: run `regwatch validate` for the list of problems, fix them, and reload.
