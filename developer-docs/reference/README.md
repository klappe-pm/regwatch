# reference

Reference pages describe the codebase as it is: what each module owns, and how packaged data is found. They are for looking something up while you change the code, so they are organised around the thing described, state facts without instruction, and aim to be complete. The how-to guides say what to do with these facts.

## pages

- [source layout](source-layout.md): the repository tree, and what every module in the `regwatch` package owns and imports.
- [package data](package-data.md): how the field rules under `regwatch/data/` are packaged and resolved through `importlib.resources`.
