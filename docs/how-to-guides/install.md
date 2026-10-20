# Install

This guide covers every way to install regwatch, how to upgrade it and how to remove it. regwatch has no runtime dependencies, so an install adds only the package itself. Nothing is released yet, so every method below installs from the repository rather than from PyPI.

## Requirements

- Python 3.11 or newer. The package uses `tomllib` and other parts of the 3.11 standard library.
- `git`, to install from the repository.

## Install with `pipx`

`pipx` puts the command on your path and keeps its environment separate from your other tools:

```bash
pipx install git+https://github.com/klappe-pm/regwatch
```

Check it:

```bash
regwatch --version
```

## Install into a Virtual Environment

```bash
python3 -m venv ~/.venvs/regwatch && ~/.venvs/regwatch/bin/pip install git+https://github.com/klappe-pm/regwatch
```

Run it with the full path, or add `~/.venvs/regwatch/bin` to your `PATH`:

```bash
~/.venvs/regwatch/bin/regwatch --version
```

## Install from a Checkout for Development

An editable install runs the code in your checkout, and the `test` and `lint` extras add the test, lint and type checking tools:

```bash
git clone https://github.com/klappe-pm/regwatch ~/regwatch && python3 -m venv ~/regwatch/.venv && ~/regwatch/.venv/bin/pip install -e "$HOME/regwatch[test,lint]"
```

See [first contribution](../tutorials/first-contribution.md) for the rest of the development setup.

## Upgrade

With `pipx`:

```bash
pipx upgrade regwatch
```

With a virtual environment, install again with `--upgrade`:

```bash
~/.venvs/regwatch/bin/pip install --upgrade git+https://github.com/klappe-pm/regwatch
```

Read the [changelog](../../CHANGELOG.md) before you upgrade. Your register files are not part of the package and an upgrade never changes them.

## Uninstall

```bash
pipx uninstall regwatch
```

Uninstalling removes the command and nothing else. Your register, snapshots and state directory stay where they are.

## Check the Install Worked

Run the command against the example register that ships in the repository. This needs a checkout:

```bash
regwatch --config ~/regwatch/examples/regwatch.toml validate
```

A healthy install prints `errors=0`. If it does not, see [troubleshooting](troubleshooting.md).
