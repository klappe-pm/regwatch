# automations

The Automations page of the local application: the schedule that runs capture and then check, and the record of each run.

## `header`

- `title`: Automations
- `description`: The schedule that runs capture and then check, and the record of each run. Run now does what regwatch run does.
- `run-now`: Run now
- `running`: Running

## `notes`

- `started`: Capture and check are running. This page updates when the run finishes.
- `finished`: The run finished; its result is at the top of the run history.
- `failed`: The run could not start.

## `schedule`

- `title`: Schedule
- `runs`: Runs
- `next-run`: Next run
- `after-first`: After the first scheduled run
- `not-known`: Not known
- `installed-with`: Installed with
- `note`: Note
- `empty`: Nothing is scheduled. Install a schedule to run capture and check every hour, day or week with {tool}.
- `empty-note`: ({note}.)

## `frequent`

- `title`: More Than Once a Day
- `available`: Runs every hour are available. Set them with
- `after`: .
- `feature`: Running more often than once a day

## `history`

- `title`: Run History
- `table`: Run history
- `started`: Started
- `result`: Result
- `captured`: Captured
- `statuses`: Statuses
- `failed`: {count} failed
- `empty`: No run has been recorded yet. Each scheduled run, each regwatch run and each Run now is listed here with its result.
