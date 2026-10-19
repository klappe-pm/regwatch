# developer-docs

Documentation for people who change regwatch: you clone the repository, run its tests, add a source mechanism or fix a bug, and open a pull request. It uses the same four [Diátaxis](https://diataxis.fr/) quadrants as the user documentation under [docs](../docs/README.md), so the folder a page sits in tells you what kind of page it is. Nothing here is needed to use regwatch; everything here assumes you have read the user documentation for the part you are changing.

## tutorials

Lessons that take you through a task from start to finish, for someone new to the codebase. Start with [first contribution](tutorials/first-contribution.md), which goes from a fresh clone to a passing test suite and a pull request. Index: [tutorials](tutorials/README.md).

## how-to-guides

Recipes for a specific development goal. [run the tests](how-to-guides/run-the-tests.md) covers the suite, coverage, lint, formatting and type checking, and [add a source mechanism](how-to-guides/add-a-source-mechanism.md) covers teaching `check` to read a new kind of source. Index: [how-to guides](how-to-guides/README.md).

## reference

Lookup pages that describe the codebase as it is. [source layout](reference/source-layout.md) describes every module and what it owns, and [package data](reference/package-data.md) describes how the field rules under `regwatch/data/` are packaged and read through `importlib.resources`. Index: [reference](reference/README.md).

## explanation

Discussion of why regwatch is built the way it is. [architecture](explanation/architecture.md) explains how the modules fit together and which way data flows, and [design decisions](explanation/design-decisions.md) records the choices that shaped the code, including what was deliberately not built. Index: [explanation](explanation/README.md).
