# Use the Web App

This guide opens the Regwatch web app for a project, finds your way around it, and changes the settings it can change. The web app is a local page in your browser that reads the same files as the command line: nothing is sent anywhere else, and it works with no network connection. It assumes you already have a project with a `regwatch.toml`; if you do not, start with [getting started](../tutorials/getting-started.md).

## Open It

Run `regwatch ui` with your configuration file. It starts a small server on `127.0.0.1`, prints the address, and opens your browser at it.

```bash
regwatch --config ~/my-project/regwatch.toml ui
```

The address it prints carries a private token, for example `http://127.0.0.1:53817/?token=...`. The browser keeps the token as a cookie and the address bar drops it, so the token is not left in your history. Keep the printed address to yourself: anyone on this machine who has it can read your register through the server while it runs.

To choose the port, add `--port 8765`. To print the address without opening a browser, for example on a machine you reach over SSH with a forwarded port, add `--no-open` and open the address yourself. Press Ctrl+C in the terminal to stop the server; the browser tab stops working then.

## Find Your Way Around

The navigation rail on the left lists every page. The button at its foot collapses it to icons, and the browser remembers that choice. On a narrow screen the rail always shows icons.

The search box at the top of the rail searches your sources, the changes and your obligations at once. Type a name, a jurisdiction or a term, move through the results with the arrow keys, and press Enter to open one. Escape closes the results.

| page | what it shows |
| --- | --- |
| Overview | counts of new, changed, suspicious and failing sources, the next scheduled run, the highest priority regulatory changes, supply chain signals, the sources to review and what takes effect in the next 90 days |
| Changes | every candidate impact ranked by focus area, severity and date, with filters and a panel that says why a change was flagged, then the source changes and the unconfirmed candidates from `ingest` |
| Sources | the sources you watch with the status of each stored snapshot, and the source catalogue with search and filters by category, region, kind and access |
| Obligations | your register, read only, with the products each obligation may affect |
| Briefings | the tiered briefing, the daily brief and the weekly synthesis, rendered, with export to Markdown, HTML and Word, and to PDF through the browser's print dialog |
| Newsletters, Documents | premium features; see [premium features](#premium-features) |
| Automations | the schedule, the run history and a button to run capture and check now |
| Keys | which sources that need a key have one stored |
| Settings | your focus areas, the premium toggle, the document design and the language model provider |

The pages read the files every time they load, so after you run `regwatch capture`, `check --accept` or `ingest` in a terminal, reload the page to see the result. Status on the Overview, Changes and Sources pages comes from the stored snapshots, as `regwatch check` without `--fetch` reports it; the web app never fetches a source.

A page whose feature has not arrived yet says what it will show and which command fills it. The catalogue, keys, schedule and run history work this way until those parts of Regwatch ship.

## Change Settings

The Settings page writes to `regwatch.toml` and nothing else. It changes one line at a time and keeps every comment and every other setting in the file. If the file is written in a form the web app cannot change safely, such as a dotted key like `premium.enabled = true`, the page says so and leaves the file alone; change that setting in the file by hand.

- Focus areas: tick the areas that match your business and choose Save Focus Areas. This writes `[profile] focus_areas`, the same setting `regwatch init` writes. See [set your focus areas](set-your-focus-areas.md).
- Premium features: the switch writes `[premium] enabled`.

The web app never changes your register files. To add an obligation or a source, edit the register as before.

## Premium Features

Newsletters, document templates, generated copy and runs more often than once a day are premium features. While premium is off the web app shows them with a lock and a one-line note rather than hiding them. Turn premium on with the switch in Settings, or from a terminal:

```bash
regwatch --config ~/my-project/regwatch.toml premium on
```

`regwatch premium status` shows whether it is on, and `regwatch premium off` turns it off. Regwatch is MIT licensed, so the toggle is a product boundary, not a lock: anyone can turn it on.

## If It Does Not Open

- `error: the web app is not built into this installation`: the installed package lacks the built pages. This happens only when running from a checkout where `regwatch/web/` was deleted; run `scripts/build-web.sh` as described in [change the web app](change-the-web-app.md), or install a released version.
- `error: cannot listen on 127.0.0.1:8765`: another program uses that port. Leave `--port` out to take a free one.
- A page that says the request has no valid token: open the exact address `regwatch ui` printed. A token belongs to one run of the server, so an address from an earlier run no longer works.
- A page that says the register is invalid: run `regwatch validate` for the list of problems, fix them, and reload.
