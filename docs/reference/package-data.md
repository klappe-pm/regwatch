# Package Data

This page describes how non-Python files ship inside the package and how code finds them. Today there are five: the field rules in `regwatch/data/schema.json`, the focus catalogue in `regwatch/data/focus-areas.json`, the invented example jurisdictions in `regwatch/data/example-jurisdictions.json`, the source catalogue in `regwatch/data/source-catalogue.json`, and the jurisdiction names in `regwatch/data/jurisdiction-names.json`. It covers the rule for locating data, how the build includes it, and how to add another file. It is a reference page, so it states how things are and not how to change them.

## The Rule

Package data is read through `importlib.resources`, never through a path built from `__file__`. `regwatch/register.py` does it like this:

```python
from importlib import resources

text = resources.files("regwatch").joinpath("data/schema.json").read_text(encoding="utf-8")
```

A path built from `__file__` breaks when the package is installed from a zip, a wheel cache or a frozen bundle, and it hides the dependency from tools that inspect packages. `importlib.resources` works in all of those.

## What Ships

| file | read by | holds |
| --- | --- | --- |
| `regwatch/data/schema.json` | `register.load_schema` | the field rules for every register file: required fields, allowed values, patterns, types and references |
| `regwatch/data/focus-areas.json` | `focus.shipped_catalogue_text`, `focus.load_catalogue` | the shipped focus catalogue; `regwatch init` copies it into each project so the user can edit it. The format is in the [focus catalogue reference](focus-catalogue.md). |
| `regwatch/data/example-jurisdictions.json` | `onboarding.example_jurisdictions` | the invented jurisdictions that `regwatch init --example` offers; a valid `jurisdictions` list with every coverage set to `tracked` or `aggregate` so a new project has no empty confirmed jurisdiction |
| `regwatch/data/source-catalogue.json` | `catalogue.load_source_catalogue` | the source catalogue that `regwatch sources` reads; the format and the counts are in the [source catalogue reference](source-catalogue.md) |
| `regwatch/data/jurisdiction-names.json` | `catalogue.jurisdiction_name` | a readable name for each catalogue jurisdiction code, used when `sources add` adds a jurisdiction to a register |
| `regwatch/py.typed` | type checkers | marks the package as typed |

## How the Build Includes It

The wheel target in `pyproject.toml` lists `packages = ["regwatch"]`. The hatchling backend includes every file under the package directory that is not excluded by `.gitignore`, so every file under `data/` and `py.typed` ship without further configuration. Check a new data file from an installed wheel, as described below. The source distribution includes `regwatch`, `tests`, `examples`, `README.md`, `LICENSE` and `pyproject.toml`.

## The Schema Format

`schema.json` has a `version`, a `description`, a `list_delimiter` (the separator for list cells in the obligations CSV, `;`) and one object per file kind: `obligation_fields`, `source_fields`, `category_fields`, `jurisdiction_fields` and `product_fields`. Each maps a field name to a rule object with these keys.

| key | meaning |
| --- | --- |
| `required` | the field must be present and non-empty |
| `unique` | the field identifies the record; exactly one field per kind has it |
| `pattern` | the value must match the regular expression in full |
| `enum` | the value must be one of the listed strings |
| `type` | `date`, `date-or-empty`, `url-or-empty` (https only) or `fetch-url` (https or file) |
| `list` | the field holds several values |
| `ref` | each value must be defined in the named catalog: `jurisdictions`, `categories` or `sources` |

The sidecar files (detail, change log, enforcement and themes) are validated by code in `register.py` rather than by the schema, because their shape is nested.

## Adding a Data File

Put the file under `regwatch/data/`, read it with `resources.files("regwatch")`, and add a test that loads it through the same call. Before you rely on it, check it from an installed wheel and not only from the checkout: build the wheel, install it into a new virtual environment, and call the function that reads the file.
