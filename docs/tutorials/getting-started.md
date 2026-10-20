# getting-started

This tutorial takes a new user from an install to a first briefing. You install the command, set up your own project with `regwatch init`, which asks what your business cares about, then use the synthetic example register to validate a register, check sources for changes, flag candidate impacts, focus the results on a business, and render a briefing in several formats. It is a lesson rather than a reference: it follows one path and explains only what that path needs. For every option see the [cli reference](../reference/cli.md), and for every file the engine reads see [data files](../reference/data-files.md).

regwatch flags candidates for human review. Nothing it produces is legal advice, and the example register is entirely invented. Do not treat any output in this tutorial as a statement about a real rule.

## what-you-need

- Python 3.11 or newer.
- `pipx`, or a virtual environment you are willing to install into.
- A checkout of the repository, because the example register lives in its `examples/` directory.

## install-the-command

Until the package is released, install it from the repository:

```bash
pipx install git+https://github.com/klappe-pm/regwatch
```

Confirm the command is on your path:

```bash
regwatch --version
```

The [install guide](../how-to-guides/install.md) covers other install methods and upgrading.

## create-your-project

`regwatch init` sets up a project folder: a configuration file, an empty register and your focus areas. Run it and answer the questions. Press Enter to skip any question; the defaults are the safe ones.

```bash
regwatch init
```

It asks, in order:

- Where the project lives. It offers the current folder. If you run it from your home directory it asks for a folder instead of assuming one, for example `~/my-regwatch`.
- Which focus areas apply to your business. It prints a numbered list: non-alcoholic beverages, alcoholic beverages, cannabis and hemp products, traditional foods, dietary supplements, infant food, pet food and cosmetics. Answer with numbers or ids separated by commas, then add any extra words of your own.
- Which jurisdictions to watch. These are free text; regwatch makes an identifier from each name.
- Whether regwatch may read local files as sources, and from which folders. The default is no.
- A contact, such as an email address, that is sent in the User-Agent header so site owners can see who is reading their pages.

It then shows a summary and asks before it writes anything. It never overwrites a file that exists unless you add `--force`. To skip the questions, give every answer as a flag, which also makes the command usable in a script:

```bash
regwatch init --dir ~/my-regwatch --focus pet-food --term "freeze dried" --jurisdiction Westmark --contact me@example.com --yes
```

Check the new project:

```bash
regwatch --config ~/my-regwatch/regwatch.toml validate
```

```text
regwatch validate: 0 obligations, 0 sources, 0 categories, 1 jurisdictions, 0 products; errors=0
```

The register is valid and empty. Your next steps are to describe your products in `register/portfolio.json`, add the rules you track to `register/obligations.csv`, and add sources as the [add a source guide](../how-to-guides/add-a-source.md) describes. Print what regwatch will use at any time with `regwatch --config ~/my-regwatch/regwatch.toml config show`. The rest of this tutorial uses the synthetic example, which already has a register to work on.

## copy-the-example

Clone the repository and copy the example into a directory of your own, so the files you change are not part of the checkout:

```bash
git clone https://github.com/klappe-pm/regwatch ~/regwatch && cp -r ~/regwatch/examples ~/regwatch-demo
```

The directory holds `regwatch.toml`, the register files under `register/`, stored source content under `snapshots/`, and a saved API response, `ingest-response.json`. Every other command in this tutorial names the configuration file explicitly, so it runs from any directory.

## validate-the-register

Validation checks every register file against the field rules and reports every problem at once:

```bash
regwatch --config ~/regwatch-demo/regwatch.toml validate
```

```text
regwatch validate: 7 obligations, 5 sources, 5 categories, 6 jurisdictions, 3 products; errors=0
```

Every other command validates first and refuses to run on an invalid register, so you will see this check again. To see an error, change a jurisdiction in `register/obligations.csv` to a name that is not in `register/jurisdictions.json` and run the command again. Change it back afterwards.

## check-the-sources

A source is a place regwatch reads to see whether something changed. The example stores a copy of each source under `snapshots/`, so the check works without a network:

```bash
regwatch --config ~/regwatch-demo/regwatch.toml check
```

```text
NEW        nl-notices                   snapshot  43d9772d8117
NEW        nl-east-gazette              snapshot  f315a839dbc1
NEW        sv-register-api              snapshot  29a425500135
NEW        sv-subscription              snapshot  0e83ce99e10c
MANUAL     sv-newsroom                  manual  review by hand
```

Nothing has been seen before, so every source is `NEW`. The fifth source is marked manual in the register because it blocks automated clients; regwatch lists it so you remember to read it yourself. Accept this run as the baseline:

```bash
regwatch --config ~/regwatch-demo/regwatch.toml check --accept
```

Now simulate a change by adding a line to one of the stored sources, and check again:

```bash
echo "2026-10-19  A new item." >> ~/regwatch-demo/snapshots/sv-subscription.txt
```

```bash
regwatch --config ~/regwatch-demo/regwatch.toml check
```

```text
UNCHANGED  nl-notices                   snapshot  43d9772d8117
UNCHANGED  nl-east-gazette              snapshot  f315a839dbc1
UNCHANGED  sv-register-api              snapshot  29a425500135
CHANGED    sv-subscription              snapshot  0466114ca6f0
MANUAL     sv-newsroom                  manual  review by hand
```

The changed source is flagged for a person to read. regwatch has not changed your register and will not. The [review flagged changes guide](../how-to-guides/review-flagged-changes.md) says what to do next.

## flag-candidate-impacts

Impact analysis joins each obligation to each product in the portfolio and flags the pairs a person should look at:

```bash
regwatch --config ~/regwatch-demo/regwatch.toml impact --severity act-now
```

```text
act-now  cinnamon-cereal          nl-west        2026-11-15  West Region School Food Rule
         category: sweeteners; term: sucralose
act-now  berry-spread             nl             2026-12-31  Voluntary Colorant Phase-Out
         category: colorants; term: carmine
act-now  oat-bar                  nl             2027-03-01  Allergen Declaration Order
         category: allergens; term: milk, peanut
```

Each line says why the pair was flagged: the shared category and term. The severity depends on the obligation's status and how soon it takes effect, so it changes as the example dates pass. Severity is a way to order the list for a reader. It is not an assessment of legal risk.

## focus-the-results-on-your-business

Some of those candidates are about sweeteners, colorants and school food, which may mean little to the business you run. A focus profile ranks candidates by relevance without hiding any. Add a profile to the example configuration. This one names a custom term and no catalogue area, which is enough to see the effect:

```bash
printf '\n[profile]\ncustom_terms = ["allergen"]\n' >> ~/regwatch-demo/regwatch.toml
```

```bash
regwatch --config ~/regwatch-demo/regwatch.toml impact
```

```text
act-now  oat-bar                  nl             2027-03-01  Allergen Declaration Order
         category: allergens; term: milk, peanut; focus: custom-terms
watch    oat-bar                  sv             no date     Nutrition Claims Regulation
         claim: high-fiber; focus: custom-terms

Outside your focus areas (5, listed after the items above):
act-now  cinnamon-cereal          nl-west        2026-11-15  West Region School Food Rule
         category: sweeteners; term: sucralose
act-now  berry-spread             nl             2026-12-31  Voluntary Colorant Phase-Out
         category: colorants; term: carmine
watch    berry-spread             nl-east        no date     East Region Sweetener Labeling Bill
         category: sweeteners
watch    cinnamon-cereal          nl-east        no date     East Region Sweetener Labeling Bill
         category: sweeteners; term: sucralose
watch    cinnamon-cereal          sv-multi       no date     Regional Sweetener Bills (aggregate)
         category: sweeteners; term: sucralose
regwatch impact: 7 candidate impacts across 3 products; 2 in your focus areas, 5 outside
```

The two candidates for the oat bar now come first, because the bar's category and the obligation both mention allergens, even though candidates with the same or a higher severity exist. All seven are still listed. The briefing later in this tutorial follows the same rule, so its obligations are split the same way. The [set your focus areas guide](../how-to-guides/set-your-focus-areas.md) shows how to choose catalogue areas and edit their words.

## ingest-candidate-events

`ingest` turns a response from a Federal Register style API into candidate events. The example includes a saved response, so no network is needed:

```bash
regwatch --config ~/regwatch-demo/regwatch.toml ingest --from-file ~/regwatch-demo/ingest-response.json
```

Two of the three invented documents match the filters in `regwatch.toml`. They are written to `state/ingest-candidates.json`, each flagged unconfirmed. Nothing is added to your change log. You decide which candidates are real and copy them there yourself.

## build-and-render-a-briefing

A briefing combines the change log, what is coming due, the register and the candidates. Write the full version and its document model to a directory:

```bash
regwatch --config ~/regwatch-demo/regwatch.toml brief --tier v3 --out-dir ~/regwatch-demo/out
```

Then render the saved model in every delivery format:

```bash
regwatch --config ~/regwatch-demo/regwatch.toml render ~/regwatch-demo/out/regwatch-briefing-v3.json --out-dir ~/regwatch-demo/out
```

The directory now holds Markdown, a web post, an HTML newsletter with a plain text alternative, and a Word document. Open any of them and look at the last lines: each ends with the statement that it is not legal advice.

## next-steps

- Choose and tune your focus areas: [set your focus areas](../how-to-guides/set-your-focus-areas.md).
- Watch your own feed or page: [add a source](../how-to-guides/add-a-source.md).
- Understand what each command does and writes: [cli reference](../reference/cli.md).
- Understand why regwatch only flags: [design](../explanation/design.md).
- See how fetched content is handled: [security model](../explanation/security-model.md).
