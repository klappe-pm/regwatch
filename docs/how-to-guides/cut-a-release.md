# Cut a Release

This guide is for a maintainer releasing a new version of Regwatch: bumping the version, settling the changelog, tagging and publishing the package. It publishes to PyPI through trusted publishing and as a GitHub release. It assumes a clean checkout of `main` with the test suite green. [Stratarc](https://github.com/klappe-pm/stratarc) releases by running `twine upload` by hand with a PyPI token; Regwatch instead publishes from a pinned, approval gated workflow with trusted publishing, so no PyPI token exists on a maintainer's machine, in the repository or in GitHub settings.

## Where the Version Lives

The version is `__version__` in `regwatch/__init__.py`. `pyproject.toml` declares the version as dynamic and reads it from that file through hatchling, so it is set in one place. The project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## One-Time Setup

Do this once, before the first release.

1. On PyPI, open your account's publishing settings and add a pending trusted publisher with project name `regwatch`, owner `klappe-pm`, repository `regwatch`, workflow `release.yml` and environment `pypi`.
2. On GitHub, open the repository settings and create an environment named `pypi`. Add yourself as a required reviewer, so every upload waits for your approval. Add a deployment rule that allows only the tag pattern `v*`, and turn off the option that lets administrators bypass the protection rules.
3. In the repository's rulesets, add a tag ruleset that targets `v*` and restricts who can create, update and delete those tags. Only the maintainer should be able to push a release tag.

## Steps

1. Decide the new version from the Unreleased section of [the changelog](../../CHANGELOG.md): a breaking change bumps the major version, a new capability bumps the minor, a fix bumps the patch. A version number that was ever uploaded to PyPI can never be reused, even after it is deleted.
2. Set `__version__` in `regwatch/__init__.py`.
3. In the changelog, rename Unreleased to the version and the date, written as `## 0.1.0 (2026-10-20)` with no dash, and open a new empty Unreleased section above it.
4. Run the gates from [Run the Tests](run-the-tests.md): the suite with coverage, `ruff check`, `ruff format --check` and `mypy --strict`. Also run the private terms test, which skips on GitHub because the list of terms never leaves your machine:

```bash
REGWATCH_FORBIDDEN_TERMS_FILE=/path/to/private-terms.txt python3 -m pytest /path/to/regwatch/tests/test_no_personal_terms.py
```

5. Build the distributions and check them. The project page on PyPI shows the README, so every link in it must be absolute, and the page text of a published version can never be changed; a fix ships as a new version:

```bash
python3 -m pip install build twine && python3 -m build --outdir /path/to/regwatch/dist /path/to/regwatch && python3 -m twine check /path/to/regwatch/dist/*
```

6. Commit as `chore: release <version>` and merge it through a pull request like any other change.
7. Tag the merge commit `v<version>` and push the tag:

```bash
git -C /path/to/regwatch tag -a v<version> -m "regwatch <version>"
```

```bash
git -C /path/to/regwatch push origin v<version>
```

8. Open the workflow run on GitHub. When the build and test jobs have passed, approve the `pypi` environment. The publish job uploads the distributions that the build job made and the test job tested.
9. Create a GitHub release on the tag with the changelog section as its notes.

## What the Workflow Does

The workflow in `.github/workflows/release.yml` runs on a pushed `v*` tag and has three jobs.

- `build` checks that the tagged commit is an ancestor of `origin/main` and that the tag equals `v` plus the package version, so a mistyped tag or a tag on a side branch never reaches PyPI. It installs only `build` and `hatchling` from the hash-pinned `requirements/build.txt`, builds the sdist and the wheel, writes `sha256sum dist/*` to the job summary and uploads `dist/`.
- `test` installs the hash-pinned `requirements/ci.txt` and the wheel that `build` made, checks that the installed copy and not the checkout is what gets imported, and runs the suite against it, so the tests exercise the artifact that ships.
- `publish` needs both, runs in the `pypi` environment and uploads with trusted publishing.

## What the Workflow Is Allowed to Do

Every action is pinned to a full commit hash, and `tests/test_release_workflow.py` fails if one is not. The workflow can read the repository and nothing else, except the publish job, which alone holds the `id-token: write` permission that trusted publishing needs. Checkout does not keep the GitHub token on disk. Every `pip install` in the workflow either uses `--require-hashes` or installs a local wheel with `--no-deps`, and the same test checks that too.

## Refreshing the Lock Files

`requirements/build.txt` and `requirements/ci.txt` are compiled, with hashes, from the small `.in` files beside them. Regenerate them on Python 3.11 on Linux, the platform the workflow runs on, with pip-tools:

```bash
cd /path/to/regwatch && python3.11 -m pip install pip-tools && python3.11 -m piptools compile --generate-hashes --strip-extras --output-file=requirements/build.txt requirements/build.in && python3.11 -m piptools compile --generate-hashes --strip-extras --output-file=requirements/ci.txt requirements/ci.in
```

Review the diff before committing it. The `test` extra in `pyproject.toml` sets a floor of `pytest` 9.0.3; see [Dependencies](../explanation/dependencies.md) for why.

## After the Release

Confirm that `pipx install regwatch==<version>` works, that `regwatch init` scaffolds a project, and that the project page on pypi.org renders the README with working links.
