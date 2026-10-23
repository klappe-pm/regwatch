# Keep API Keys

This guide shows how to give regwatch the key that a Free Key or keyed Paid source needs, check which keys are in place, and remove one. It assumes the source is already in your sources file; see [add a source](add-a-source.md). Keys go in the system keychain, never in a file.

## Store a Key

Ask regwatch where to get the key, then paste it at the prompt. Nothing is echoed and nothing is printed back.

```bash
regwatch --config ~/my-register/regwatch.toml keys set us-regulations-gov-api
```

On macOS the key goes into your login keychain. On Linux it goes into the Secret Service keyring through `secret-tool`, which is in the `libsecret-tools` package on Debian and Ubuntu and in `libsecret` on Fedora.

## Supply a Key From the Environment

A scheduled job or a container may have no keychain. Set the variable the source names instead; `regwatch sources show ID` prints it as the key variable. The variable wins over the keychain.

```bash
export REGWATCH_KEY_REGULATIONS_GOV="paste-the-key-here"
```

## Check and Remove Keys

`keys list` shows, for each keyed source, whether its key is stored, set in the environment or missing, and never the key itself.

```bash
regwatch --config ~/my-register/regwatch.toml keys list
```

```bash
regwatch --config ~/my-register/regwatch.toml keys remove us-regulations-gov-api
```

A keyed source with no key is reported as an error by `capture`, `check --fetch` and `run`, with the command that fixes it.
