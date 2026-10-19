# install

This guide covers every way to install regwatch, how to upgrade it and how to remove it. regwatch has no runtime dependencies, so an install adds only the package itself. Nothing is released yet, so every method below installs from the repository rather than from PyPI.

## requirements

- Python 3.11 or newer. The package uses `tomllib` and other parts of the 3.11 standard library.
- `git`, to install from the repository.

## install-with-pipx

`pipx` puts the command on your path and keeps its environment separate from your other tools:

```bash
pipx install git+https://github.com/klappe-pm/regwatch
```

Check it:

```bash
regwatch --version
```

## install-into-a-virtual-environment

```bash
python3 -m venv ~/.venvs/regwatch && ~/.venvs/regwatch/bin/pip install git+https://github.com/klappe-pm/regwatch
```

Run it with the full path, or add `~/.venvs/regwatch/bin` to your `PATH`:

```bash
~/.venvs/regwatch/bin/regwatch --version
```

## install-from-a-checkout-for-development

An editable install runs the code in your checkout, and the `dev` extra adds the test, lint and type checking tools:

```bash
git clone https://github.com/klappe-pm/regwatch ~/regwatch && python3 -m venv ~/regwatch/.venv && ~/regwatch/.venv/bin/pip install -e "$HOME/regwatch[dev]"
```

See [first contribution](../../developer-docs/tutorials/first-contribution.md) for the rest of the development setup.

## upgrade

With `pipx`:

```bash
pipx upgrade regwatch
```

With a virtual environment, install again with `--upgrade`:

```bash
~/.venvs/regwatch/bin/pip install --upgrade git+https://github.com/klappe-pm/regwatch
```

Read the [changelog](../../changelog.md) before you upgrade. Your register files are not part of the package and an upgrade never changes them.

## uninstall

```bash
pipx uninstall regwatch
```

Uninstalling removes the command and nothing else. Your register, snapshots and state directory stay where they are.

## check-the-install-worked

Run the command against the example register that ships in the repository. This needs a checkout:

```bash
regwatch --config ~/regwatch/examples/regwatch.toml validate
```

A healthy install prints `errors=0`. If it does not, see [troubleshooting](troubleshooting.md).
