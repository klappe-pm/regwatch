# docs

Documentation for people who use regwatch: you keep a register of regulatory obligations, point regwatch at the sources you follow, and read the briefings it renders. It is arranged by the four [Diátaxis](https://diataxis.fr/) quadrants, so the folder a page sits in tells you what kind of page it is. If you change regwatch itself, the same shape exists under [developer-docs](../developer-docs/README.md).

regwatch flags candidates for human review. It never edits your register or change log, and nothing it produces is legal advice. A qualified person must confirm every flagged item against the primary source text before anyone relies on it.

## tutorials

Lessons that take you through a task from start to finish, for someone who has not done it before. Start with [getting started](tutorials/getting-started.md), which goes from an install to a validated register, a first change check, flagged impacts and a rendered briefing. Index: [tutorials](tutorials/README.md).

## how-to-guides

Recipes for a specific goal, for someone who already knows the basics and wants the steps. [install](how-to-guides/install.md) covers every install method, [add a source](how-to-guides/add-a-source.md) covers watching a new feed, page or API, [review flagged changes](how-to-guides/review-flagged-changes.md) covers what to do with a change that regwatch flags, and [troubleshooting](how-to-guides/troubleshooting.md) matches a failure to its fix. Index: [how-to guides](how-to-guides/README.md).

## reference

Lookup pages that describe the machinery as it is, with no instruction attached. [cli](reference/cli.md) lists every subcommand, option and exit status, [configuration](reference/configuration.md) lists every key in `regwatch.toml`, [data files](reference/data-files.md) lists every field of every register file, and [python api](reference/python-api.md) lists every public function and class. Index: [reference](reference/README.md).

## explanation

Discussion that gives background and reasons, for a reader who wants to understand rather than act. [design](explanation/design.md) explains what regwatch is for and why it only flags, [security model](explanation/security-model.md) explains how fetched content and output files are handled, and [dependencies](explanation/dependencies.md) justifies the choice to have no runtime dependencies. Index: [explanation](explanation/README.md).

## documentation-guide

How this documentation is organised and how to add to it. [documentation guide](documentation-guide/README.md) says which folder a new page belongs in, and [feature documentation template](documentation-guide/feature-documentation-template.md) is the outline for a page that documents one feature end to end.
