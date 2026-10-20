# Focus Catalogue

This page describes the focus catalogue: the shipped set of focus areas, the file format that defines them, how a profile is built from it, and exactly how a candidate is matched. It is a reference, so it states facts without instruction. To choose areas and tune them, see [set your focus areas](../how-to-guides/set-your-focus-areas.md).

## Shipped Areas

The catalogue ships as package data in `regwatch/data/focus-areas.json`. `regwatch init` copies it into the project as `focus-areas.json`.

| id | label |
| --- | --- |
| `non-alcoholic-beverages` | Non-alcoholic beverages |
| `alcoholic-beverages` | Alcoholic beverages |
| `cannabis-and-hemp-products` | Cannabis and hemp products |
| `traditional-foods` | Traditional foods |
| `dietary-supplements` | Dietary supplements |
| `infant-food` | Infant food |
| `pet-food` | Pet food |
| `cosmetics` | Cosmetics |

The words of each area are generic regulatory vocabulary. They name no company, product or brand.

## File Format

A JSON object with an optional `version` and `description`, and a `focus_areas` list. Unknown keys in an entry are errors. The file must be smaller than 1,000,000 bytes.

| key | required | rule |
| --- | --- | --- |
| `focus_id` | yes | unique identifier of lowercase letters, digits and hyphens |
| `label` | yes | non-empty text shown in summaries and briefings |
| `description` | no | text shown in the `regwatch init` list |
| `terms` | yes | non-empty list of non-empty strings; stored lower case, repeats dropped |

## The Profile

The `[profile]` table in `regwatch.toml` chooses areas by id and adds custom terms; see [configuration](configuration.md). The profile is active when it names at least one area or custom term. An inactive profile matches nothing, and every candidate counts as in focus. A chosen id that is not in the catalogue is an error that names the ids on offer.

## Matching

- Text is lower-cased. A term matches when it appears as whole words: the characters before and after it must not be letters or digits. One plural ending, `s` or `es`, is allowed after the term.
- A term may hold several words and hyphens, and is matched literally; it is not a pattern.
- An area matches when any of its terms matches. A custom term reports as `custom-terms`.

What is read for each kind of candidate:

| candidate | text matched |
| --- | --- |
| impact (an obligation and a product) | the obligation's title, citation, notes, categories, terms and claims, its detail summary, impacts and topics when it has a detail record, and the product's name, kind, categories, terms and claims |
| obligation in a briefing | the same obligation text |
| unconfirmed ingest candidate | the headline and the text of what happened |

## Ranking

Candidates in focus come first. Within each group the existing order applies: worst severity first, then earliest effective date, then product id. A candidate in focus carries a `focus:` reason that lists the areas it matched. A candidate outside is never removed.

## Where the Result Appears

| output | in focus | outside |
| --- | --- | --- |
| `impact` | listed first | after the heading `Outside your focus areas` |
| tiered briefing `v1` | `Key Items` | `Key Items Outside Your Focus Areas` |
| tiered briefing `v2` and `v3` | `Obligations: <jurisdiction>` sections | `Outside Your Focus Areas`, then the same sections |
| tiered briefing, coming due | `Coming Due` | `Coming Due Outside Your Focus Areas` |
| tiered briefing `v3`, ingest candidates | `Newly Detected, Unconfirmed` | `Newly Detected Outside Your Focus Areas, Unconfirmed` |
| daily brief | `Flagged For Review` | `Flagged Outside Your Focus Areas` |
| weekly synthesis | `Candidate Impact By Product` | `Candidate Impact Outside Your Focus Areas` |

The recent developments section of the tiered briefing and the `themes`, `digest`, `report` and `export` commands do not use the profile.
