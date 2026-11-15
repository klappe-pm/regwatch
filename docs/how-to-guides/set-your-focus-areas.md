# Set Your Focus Areas

This guide shows how to tell regwatch which parts of the regulatory world matter to your business, so that the candidates it flags are ranked by relevance to you. You choose focus areas from a catalogue, add words of your own, and check the result. Nothing is ever hidden: a candidate that matches none of your focus areas is still listed, after the ones that do, under an "outside your focus areas" heading. It assumes you have a project; if you do not, run `regwatch init` as described in [getting started](../tutorials/getting-started.md).

## What a Focus Area Is

A focus area is a named set of words, such as the words that describe one kind of product. The catalogue that ships with regwatch has eight: non-alcoholic beverages, alcoholic beverages, cannabis and hemp products, traditional foods, dietary supplements, infant food, pet food and cosmetics. A candidate is in focus when its text mentions one of the words of a chosen area, or one of your own custom terms. The candidate is an obligation with its product, an obligation in a briefing, or an unconfirmed ingest candidate. [focus catalogue](../reference/focus-catalogue.md) gives the exact matching rules.

## Choose Areas When You Create a Project

`regwatch init` asks which areas apply. Answer with numbers or ids separated by commas, or give them as flags, which skips the question:

```bash
regwatch init --dir ~/my-regwatch --focus pet-food --focus dietary-supplements --term "freeze dried"
```

## Change the Areas Later

Edit the `[profile]` table in your `regwatch.toml`:

```toml
[profile]
focus_areas = ["pet-food", "dietary-supplements"]
custom_terms = ["freeze dried"]
catalogue = "focus-areas.json"
```

`focus_areas` lists identifiers from the catalogue, in the order you want them reported. `custom_terms` lists extra words. Leave both empty to switch the ranking off, in which case every candidate counts as in focus.

## Add an Area or Change Its Words

`regwatch init` copies the shipped catalogue next to your configuration as `focus-areas.json`, and `catalogue` points at the copy. Open it, change the `terms` of an area, or add an entry:

```json
{
  "focus_id": "specialty-tea",
  "label": "Specialty tea",
  "description": "Loose leaf and blended teas sold to consumers.",
  "terms": ["loose leaf", "tea blend", "matcha"]
}
```

Then add `specialty-tea` to `focus_areas`. If your project has no `catalogue` key, regwatch uses the shipped catalogue and you cannot edit it; add the key and a copy of the file to change it. Do not edit the copy inside the installed package, because an upgrade replaces it.

## Check What Regwatch Will Use

```bash
regwatch --config ~/my-regwatch/regwatch.toml config show
```

Under `[profile]` the output lists your focus areas, your custom terms and the catalogue file, followed by one line per area with its label and the number of words. A misspelt area id stops the command with `unknown focus areas` and names the ids the catalogue offers.

## Read the Ranked Results

```bash
regwatch --config ~/my-regwatch/regwatch.toml impact
```

Candidates in your focus areas come first, worst severity first. A blank line and the heading `Outside your focus areas` follow, then the rest in the same order. Each in-focus line says which area matched, for example `focus: pet-food`. The last line counts both groups. Briefings follow the same rule: the tiered briefing lists matching obligations first and puts the others under `Outside Your Focus Areas`, and the daily and weekly briefs put them under their own headings.

## Tune the Words

Matching is by whole word without regard to case, and a plural ending is allowed, so `soda` matches `sodas` but `tea` does not match `steam`. If too much is in focus, remove a general word from the area in your copy of the catalogue. If something you care about is listed outside, add its word as a custom term. A match is a hint for ordering, not a legal conclusion, so review the outside list occasionally.
