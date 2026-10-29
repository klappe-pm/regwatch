# settings

The Settings page of the local application: focus areas, premium features, document design and the language model provider, all saved in the project's regwatch.toml.

## `header`

- `title`: Settings
- `description`: Settings saved in this project's regwatch.toml. Comments and other settings in the file are kept.

## `focus`

- `title`: Focus Areas
- `save`: Save Focus Areas
- `intro`: Changes that mention a focus area are listed first. Nothing outside them is hidden.
- `legend`: Focus areas
- `saved`: Saved your focus areas in regwatch.toml.
- `failed`: The focus areas could not be saved.

## `premium`

- `title`: Premium Features
- `label`: Premium features
- `intro`: Newsletters, document templates, generated copy and runs more often than once a day. Saved as
- `setting`: [premium] enabled
- `intro-after`: in regwatch.toml.
- `on`: Premium features are on.
- `off`: Premium features are off.
- `failed`: The setting could not be saved.

## `design`

- `title`: Document Design
- `feature`: Document design
- `title-format`: Title format
- `title-format-hint`: Use {title}, {date} and {organisation}.
- `organisation`: Organisation
- `primary-color`: Primary colour
- `accent-color`: Accent colour
- `primary-warning`: The primary colour
- `accent-warning`: The accent colour
- `picker`: {label} picker
- `ratio`: {ratio}:1 on white
- `font`: Font
- `system-font`: System
- `page-size`: Page size
- `a4`: A4
- `letter`: Letter
- `logo`: Logo file
- `logo-placeholder`: brand/logo.png
- `logo-hint`: A PNG or SVG inside the project folder. Email and Word use a PNG only.
- `header-line`: Header line
- `footer-line`: Footer line
- `newsletter-footer`: Newsletter closing line
- `newsletter-footer-hint`: How to reply or unsubscribe.
- `preview`: Design preview
- `preview-label`: Preview
- `preview-heading`: What Changed
- `preview-body`: Two sources changed since the last accepted check.
- `save`: Save Design
- `fix-colours`: Fix the colours to save.
- `saved`: Saved the design specification in regwatch.toml.
- `failed`: The design could not be saved.

## `llm`

- `title`: Language Model Provider
- `feature`: Generated copy
- `label`: Generated copy
- `intro`: A language model writes the opening and summaries of newsletters and documents from your facts only. Every passage is marked Generated and shown with the facts it cites.
- `on`: Generated copy is on.
- `off`: Generated copy is off.
- `provider`: Provider
- `model`: Model
- `save`: Save Provider
- `saved`: Saved the provider and the model.
- `failed`: The setting could not be saved.
- `ollama`: Ollama runs on this machine at 127.0.0.1:11434 and needs no key. Bev Watch reaches that one address and no other address on this machine.
- `key-for`: Key for {provider}
- `paste`: Paste the key
- `replace`: Replace
- `set`: Set
- `remove`: Remove
- `get-key`: Get a key
- `stored`: Stored the {provider} key in the keychain.
- `store-failed`: The key could not be stored.
- `removed`: Removed the {provider} key from the keychain.
- `remove-failed`: The key could not be removed.
