# Documentation

Regwatch watches regulatory sources, compares what it finds with a register of obligations that you keep, and renders a briefing that flags what a person should look at. These pages cover installing and using it, looking things up, and changing the code. They follow the four [Diátaxis](https://diataxis.fr/) quadrants, so the folder a page sits in tells you what kind of page it is.

Regwatch flags candidates for human review. It never edits your obligations or change log, and nothing it produces is legal advice. It changes your sources and jurisdictions only when you ask it to add or remove a source. A qualified person must confirm every flagged item against the primary source text before anyone relies on it.

## Tutorials

Lessons that take you through a task from start to finish. [Getting Started](tutorials/getting-started.md) goes from an install and `regwatch init` to a validated register, a first change check, flagged impacts focused on your business and a rendered briefing. [First Contribution](tutorials/first-contribution.md) goes from a fresh clone to a passing test suite and a pull request. Index: [Tutorials](tutorials/README.md).

## How-To Guides

Recipes for a specific goal, for someone who already knows the basics.

- Use: [Install](how-to-guides/install.md), [Set Your Focus Areas](how-to-guides/set-your-focus-areas.md), [Add a Source](how-to-guides/add-a-source.md), [Keep API Keys](how-to-guides/keep-api-keys.md), [Schedule Runs](how-to-guides/schedule-runs.md), [Review Flagged Changes](how-to-guides/review-flagged-changes.md), [Use the Web App](how-to-guides/use-the-web-app.md), [Send a Newsletter](how-to-guides/send-a-newsletter.md), [Turn On Generated Copy](how-to-guides/turn-on-generated-copy.md), [Troubleshooting](how-to-guides/troubleshooting.md).
- Contribute: [Run the Tests](how-to-guides/run-the-tests.md), [Add a Source Mechanism](how-to-guides/add-a-source-mechanism.md), [Change the Web App](how-to-guides/change-the-web-app.md), [Cut a Release](how-to-guides/cut-a-release.md).

Index: [How-To Guides](how-to-guides/README.md).

## Reference

Lookup pages that describe the machinery as it is. [CLI](reference/cli.md) lists every subcommand, option and exit status, [Configuration](reference/configuration.md) lists every key in `regwatch.toml`, [Data Files](reference/data-files.md) lists every field of every register file, [Source Catalogue](reference/source-catalogue.md) describes the sources you can choose from, [Focus Catalogue](reference/focus-catalogue.md) describes the focus areas and how candidates are matched, [Python API](reference/python-api.md) lists every public function and class, [Source Layout](reference/source-layout.md) describes every module, and [Package Data](reference/package-data.md) describes the packaged field rules, the catalogues and the built web app. Index: [Reference](reference/README.md).

## Explanation

Background and reasons, for a reader who wants to understand rather than act. [Design](explanation/design.md) explains what Regwatch is for and why it only flags, [Security Model](explanation/security-model.md) explains how fetched content and output files are handled, [Dependencies](explanation/dependencies.md) justifies the choice to have no runtime dependencies, [Architecture](explanation/architecture.md) explains how the modules fit together, [Design Decisions](explanation/design-decisions.md) records the choices that shaped the code, and [Workspace](explanation/workspace.md) plans the source catalogue, guided setup, keys, schedules, web app and premium features. Index: [Explanation](explanation/README.md).
