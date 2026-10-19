# package-data

This page describes how non-Python files ship inside the package and how code finds them. Today there is one: the field rules in `regwatch/data/schema.json`. It covers the rule for locating data, how the build includes it, and how to add another file. It is a reference page, so it states how things are and not how to change them.

## the-rule

Package data is read through `importlib.resources`, never through a path built from `__file__`. `regwatch/register.py` does it like this:

```python
from importlib import resources

text = resources.files("regwatch").joinpath("data/schema.json").read_text(encoding="utf-8")
```

A path built from `__file__` breaks when the package is installed from a zip, a wheel cache or a frozen bundle, and it hides the dependency from tools that inspect packages. `importlib.resources` works in all of those.

## what-ships

| file | read by | holds |
| --- | --- | --- |
| `regwatch/data/schema.json` | `register.load_schema` | the field rules for every register file: required fields, allowed values, patterns, types and references |
| `regwatch/py.typed` | type checkers | marks the package as typed |

## how-the-build-includes-it

The wheel target in `pyproject.toml` lists `packages = ["regwatch"]`. The hatchling backend includes every file under the package directory that is not excluded by `.gitignore`, so `data/schema.json` and `py.typed` ship without further configuration. The source distribution includes `regwatch`, `tests`, `examples`, `README.md`, `LICENSE` and `pyproject.toml`.

## the-schema-format

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

## adding-a-data-file

Put the file under `regwatch/data/`, read it with `resources.files("regwatch")`, and add a test that loads it through the same call. Before you rely on it, check it from an installed wheel and not only from the checkout: build the wheel, install it into a new virtual environment, and call the function that reads the file.
