# Build Documents in Your Design

This guide sets your organisation's design once and then writes briefings, digests and reports in it, as a web page to print to PDF or as a Word document. It assumes you already have a project with a `regwatch.toml`; if you do not, start with [getting started](../tutorials/getting-started.md). Documents are a premium feature.

## Turn On Premium Features

```bash
regwatch --config ~/my-register/regwatch.toml premium on
```

## Set the Design Specification

Set the design on the Settings page of `regwatch ui`, which shows a preview swatch and warns when a colour is too light, or write the `[document]` table yourself. Both colours must reach a contrast of 4.5:1 against white, so text in them stays readable. The font is one of ten that every computer has. The logo is a PNG or an SVG inside the project folder.

```toml
[document]
title_format = "{organisation}: {title}"
organisation = "Example Pantry Co."
primary_color = "#0b3d2e"
accent_color = "#7a2e0b"
font = "Georgia"
logo = "brand/logo.png"
header = "Internal review copy"
footer = "Example Pantry Co., 1 Example Road"
page_size = "letter"
```

An SVG logo must be plain drawing: Regwatch refuses one that holds a script, a style, an embedded image or a link, and says which part it refused. Word documents and email use a PNG logo only, so a PNG is the safer choice. [configuration](../reference/configuration.md#document) lists every key and its limits.

## Write a Document

Choose the kind and the format.

```bash
regwatch --config ~/my-register/regwatch.toml document --kind briefing --format html --out ~/reports/briefing
```

```bash
regwatch --config ~/my-register/regwatch.toml document --kind report --format docx --out ~/reports/report
```

A briefing is the tiered briefing (`--tier v1`, `v2` or `v3`), a digest lists the register by jurisdiction, and a report is the change and due alert. Add `--generate` to open the document with a short summary the language model writes from the same facts; see [turn on generated copy](turn-on-generated-copy.md).

## Save a PDF

Open the HTML file in a browser and print it, choosing Save as PDF. The print stylesheet sets the page size from `page_size` and keeps headings with the text that follows them.

The Documents page of `regwatch ui` does the same: choose the kind and the format, preview the document, and download it.

Every document ends with the statement that nothing in it is legal advice. Keep it when you edit or forward the document.
