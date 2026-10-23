# Turn On Generated Copy

This guide turns on generated copy: a language model writes the opening and the short summaries of a newsletter or a document from the facts Regwatch already has. It assumes you already have a project with a `regwatch.toml`; if you do not, start with [getting started](../tutorials/getting-started.md). Generated copy is a premium feature and is off until you turn it on.

Every generated passage is labelled Generated in the output and is followed by the facts it was written from, with their ids, so a reader can check one against the other. The model is given only those facts and told to cite them; a passage that cites a fact it was not given is left out and reported. Read [the language model stage](../explanation/security-model.md#the-language-model-stage) for what is sent and what is kept.

## Turn On Premium Features

```bash
regwatch --config ~/my-register/regwatch.toml premium on
```

## Choose a Provider

Anthropic is the default. Choose OpenAI or a local Ollama model instead, and name a model if you do not want the provider's default.

```bash
regwatch --config ~/my-register/regwatch.toml llm use anthropic
```

```bash
regwatch --config ~/my-register/regwatch.toml llm use openai --model gpt-5-mini
```

## Store the Provider Key

Anthropic and OpenAI need a key. Regwatch prints where to get one, then reads it without echoing it and stores it in the system keychain, exactly as it stores a source key; see [keep API keys](keep-api-keys.md).

```bash
regwatch --config ~/my-register/regwatch.toml keys set llm-anthropic
```

A scheduled job or a container can set `REGWATCH_KEY_ANTHROPIC` or `REGWATCH_KEY_OPENAI` in the environment instead. The variable wins over the keychain.

## Use a Local Ollama Model

Ollama runs on your own machine and needs no key. Regwatch refuses every address on your own machine unless you allow private hosts, so add this to `regwatch.toml` first:

```toml
[fetch]
allow_private_hosts = true
```

Then choose it. Regwatch speaks plain http only to `127.0.0.1:11434`, never to a host name, and never sends a key there.

```bash
regwatch --config ~/my-register/regwatch.toml llm use ollama --model llama3.2
```

## Turn It On and Check

```bash
regwatch --config ~/my-register/regwatch.toml llm on
```

`regwatch llm status` prints whether generated copy is on, the provider, the model and where the key comes from. Then add `--generate` to `regwatch newsletter` or `regwatch document`, or press Generate on the Newsletters or Documents page of `regwatch ui`. The Settings page of the web app holds the same settings.

## Read What It Cost

Each call adds one line to `llm-calls.jsonl` in the state directory with the provider, the model, the input and output token counts, the duration and the outcome. The prompt, the answer and the key are never written there.

## Turn It Off

```bash
regwatch --config ~/my-register/regwatch.toml llm off
```

```bash
regwatch --config ~/my-register/regwatch.toml keys remove llm-anthropic
```
