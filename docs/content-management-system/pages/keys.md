# keys

The Keys page of the local application: whether each source that needs a key has one, and where it is kept.

## `header`

- `title`: Keys
- `description-keychain`: Keys for the sources you watch that need one, kept in {keychain}. This page shows only whether a key is available, never the key.
- `description`: Keys for the sources you watch that need one. This page shows only whether a key is available, never the key.

## `empty`

- `before`: None of your sources needs a key. Sources marked Free Key or Paid in the
- `link`: catalogue
- `after`: appear here once you add them.

## `no-keychain`

- `before`: No keychain tool was found on this computer (security on macOS, secret-tool from libsecret on Linux), so keys cannot be stored here. Set each key in the environment variable shown under its source instead, before starting
- `command`: regwatch ui
- `after`: or a scheduled run.

## `table`

- `label`: Keys
- `source`: Source
- `key`: Key
- `set`: Set or Replace
- `get-key`: Get a key
- `key-for`: Key for {source}
- `paste`: Paste the key
- `replace`: Replace
- `set-button`: Set
- `remove`: Remove
- `remove-label`: Remove the key for {source}
- `environment`: An environment variable with the name shown overrides the keychain, for a scheduled job or a container.

## `messages`

- `stored`: Stored a key for {source}.
- `store-failed`: The key could not be stored.
- `removed-env`: Removed the stored key for {source}. The environment variable {env} still supplies one.
- `removed`: Removed the key for {source}.
- `none-stored`: No key was stored for {source}.
- `remove-failed`: The key could not be removed.
