# How-To Guides

How-to guides are recipes. Each one solves a specific problem for a reader who already knows what Regwatch is and wants the steps, with the minimum of explanation along the way. They assume more than a tutorial and promise less: a guide gets you to one outcome, and links to the reference pages for the details it skips.

## Use

- [Install](install.md): every supported way to install, upgrade and uninstall the command.
- [Set Your Focus Areas](set-your-focus-areas.md): choose the focus areas that match your business, add words of your own, and read results ranked by relevance.
- [Add a Source](add-a-source.md): watch a new feed, web page, API or mailing list archive, and choose its mechanism.
- [Keep API Keys](keep-api-keys.md): store the key a keyed source needs in the system keychain, or supply it from the environment.
- [Schedule Runs](schedule-runs.md): capture and check on a schedule with launchd or cron, and read the run records.
- [Review Flagged Changes](review-flagged-changes.md): what to do, in order, when Regwatch flags a source change, an ingest candidate or a candidate impact.
- [Use the Web App](use-the-web-app.md): open the local web app, find your way around it, change settings and turn premium features on.
- [Turn On Generated Copy](turn-on-generated-copy.md): choose a language model provider, store its key and have it write the opening and summaries of newsletters and documents.
- [Troubleshooting](troubleshooting.md): known failure modes matched to their fixes.

## Contribute

- [Run the Tests](run-the-tests.md): the test suite, the coverage report, and the lint, format and type checks a change must pass.
- [Add a Source Mechanism](add-a-source-mechanism.md): teach `check` to read a new kind of source, with the tests it needs.
- [Change the Web App](change-the-web-app.md): change the pages behind `regwatch ui`, build them reproducibly and commit the build.
- [Cut a Release](cut-a-release.md): bump the version, tag and publish to PyPI through trusted publishing.
