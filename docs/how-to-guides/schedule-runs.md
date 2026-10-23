# Schedule Runs

This guide shows how to have regwatch capture and check your sources on its own, every hour, day or week, with launchd on macOS or cron elsewhere, and how to see what the runs found. It assumes a project with sources; see [add a source](add-a-source.md).

## Try One Run

`regwatch run` is what the schedule runs: a capture of every source, then a check against the snapshots, and a run record in the state directory.

```bash
regwatch --config ~/my-register/regwatch.toml run
```

Exit status 3 means there are changes to review and 4 means a source could not be captured or checked. Review changes as [review flagged changes](review-flagged-changes.md) describes, then accept them with `check --accept`.

## Install the Schedule

Look at what would be installed first, then install it. Without `--every` the cadence is the most frequent one among your sources.

```bash
regwatch --config ~/my-register/regwatch.toml schedule --install --every daily --dry-run
```

```bash
regwatch --config ~/my-register/regwatch.toml schedule --install --every daily
```

The job runs the Python that runs regwatch now. If you later reinstall regwatch into another environment, install the schedule again so it points at the new one. A keyed source in a scheduled run gets its key from the keychain, or from its environment variable; see [keep API keys](keep-api-keys.md).

## Check and Remove It

```bash
regwatch --config ~/my-register/regwatch.toml schedule --show
```

```bash
regwatch --config ~/my-register/regwatch.toml schedule --remove
```

Each run appends its output to `schedule.log` and writes a record to `runs/`, both in the state directory. The newest 500 records are kept.
