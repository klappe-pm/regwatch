# Reference

Reference pages describe the machinery: the commands, the configuration keys, the register files, the Python interface and the codebase. They are for looking something up while you work, so they are organised around the thing described, they state facts without instruction, and they aim to be complete rather than friendly. A reference page says what an option does; the how-to guides say when to reach for it.

## Pages

- [CLI](cli.md): every subcommand of the `regwatch` command with its options, what it reads and writes, and its exit statuses.
- [Configuration](configuration.md): every key in `regwatch.toml`, with its type, default and meaning.
- [Data Files](data-files.md): every register file and every field in it, with the rules the validator applies.
- [Focus Catalogue](focus-catalogue.md): the shipped focus areas, the catalogue file format, how a profile is built and exactly how candidates are matched and ranked.
- [Python API](python-api.md): every public function, class and constant in the `regwatch` package.
- [Source Layout](source-layout.md): the repository tree, and what every module in the `regwatch` package owns and imports.
- [Package Data](package-data.md): how the field rules under `regwatch/data/` are packaged and resolved through `importlib.resources`.
