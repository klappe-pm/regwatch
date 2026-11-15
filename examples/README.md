# Examples

This directory holds a complete, working regwatch project built from synthetic data, so you can run every command without a register of your own. Every jurisdiction, rule, source, product and company in it is invented, and the `.example` addresses are reserved names that never resolve. None of it describes a real rule, and nothing here is legal advice. The tests copy this directory and run against the copy, so keep it valid when you change it.

## Contents

| path | what it is |
| --- | --- |
| `regwatch.toml` | the configuration; every path in it is relative to this directory |
| `register/` | the register files, one of each kind; see [register](register/README.md) |
| `snapshots/` | stored copies of four of the five sources, so `check` works offline |
| `ingest-response.json` | a saved response in the shape of the Federal Register API, with three invented documents |

The jurisdictions form two small trees. Northland is a country with three regions, one of them tracked only through an aggregate marker. Southvale is a second country. The example company, Example Pantry Co., sells three invented products into them.

## Try It

Each command names the configuration file, so it runs from any directory. Replace `~/regwatch` with the path of your checkout.

```bash
regwatch --config ~/regwatch/examples/regwatch.toml validate
```

```bash
regwatch --config ~/regwatch/examples/regwatch.toml check
```

```bash
regwatch --config ~/regwatch/examples/regwatch.toml impact
```

```bash
regwatch --config ~/regwatch/examples/regwatch.toml brief --tier v2
```

Commands that write, such as `check --accept` and `ingest`, create a `state/` directory here. It is ignored by git. To start over, delete it.

The [getting started tutorial](../docs/tutorials/getting-started.md) walks through all of this step by step, using a copy of this directory so the originals stay untouched.
