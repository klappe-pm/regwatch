"use client";

import { useEffect, useState } from "react";

import { Icon } from "@/components/icon";
import {
  Button,
  Command,
  EmptyState,
  ErrorNote,
  Loading,
  Locked,
  PageHeader,
  Section,
  Table,
  Td,
  Th,
} from "@/components/ui";
import { postJson, useApi } from "@/lib/api";
import { cadence, outcome, when } from "@/lib/labels";
import type { Automations } from "@/lib/types";

export default function AutomationsPage() {
  const { data, error, loading, reload } = useApi<Automations>("/api/automations");
  const [notice, setNotice] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const running = starting || data?.running === true;

  // While a run is in progress, look again every two seconds.
  useEffect(() => {
    if (data && !data.running && notice?.startsWith("Capture and check are running")) {
      setNotice("The run finished; its result is at the top of the run history.");
    }
    if (!data?.running) return;
    const timer = window.setTimeout(reload, 2000);
    return () => window.clearTimeout(timer);
  }, [data, notice, reload]);

  async function runNow() {
    setStarting(true);
    try {
      await postJson("/api/automations/run", {});
      setNotice("Capture and check are running. This page updates when the run finishes.");
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : "The run could not start.");
    } finally {
      setStarting(false);
      reload();
    }
  }

  const schedule = data?.schedule;
  const records = data?.runs.records ?? [];

  return (
    <>
      <PageHeader
        title="Automations"
        description="The schedule that runs capture and then check, and the record of each run. Run now does what regwatch run does."
        actions={
          <Button variant="primary" onClick={runNow} disabled={running || !data}>
            <Icon name="play_arrow" size={18} />
            {running ? "Running" : "Run now"}
          </Button>
        }
      />
      {notice ? (
        <p role="status" className="mb-4 text-sm">
          {notice}
        </p>
      ) : null}
      {data?.last_error ? <ErrorNote message={data.last_error} /> : null}
      {error ? <ErrorNote message={error} /> : null}
      {loading && !data ? <Loading /> : null}
      {data && schedule ? (
        <>
          <Section title="Schedule" id="schedule">
            {schedule.installed ? (
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 border border-line bg-raised p-4 text-sm">
                <dt className="text-muted">Runs</dt>
                <dd>{cadence(schedule.every)}</dd>
                <dt className="text-muted">Next run</dt>
                <dd className="numeric">
                  {when(
                    schedule.next_run,
                    schedule.via === "launchd" ? "After the first scheduled run" : "Not known",
                  )}
                </dd>
                <dt className="text-muted">Installed with</dt>
                <dd>{schedule.via === "launchd" ? "launchd" : "cron"}</dd>
                {schedule.note ? (
                  <>
                    <dt className="text-muted">Note</dt>
                    <dd>{schedule.note}</dd>
                  </>
                ) : null}
              </dl>
            ) : (
              <EmptyState command="regwatch schedule --install">
                Nothing is scheduled. Install a schedule to run capture and check every hour, day or
                week with {schedule.via === "launchd" ? "launchd" : "cron"}.
                {schedule.note ? ` (${schedule.note[0].toUpperCase()}${schedule.note.slice(1)}.)` : ""}
              </EmptyState>
            )}
          </Section>
          <Section title="More Than Once a Day" id="frequent">
            {data.premium ? (
              <p className="text-sm text-muted">
                Runs every hour are available. Set them with <Command>regwatch schedule --install --every hourly</Command>.
              </p>
            ) : (
              <Locked feature="Running more often than once a day" />
            )}
          </Section>
          <Section title="Run History" id="history">
            {records.length > 0 ? (
              <Table label="Run history">
                <thead>
                  <tr>
                    <Th>Started</Th>
                    <Th>Result</Th>
                    <Th numeric>Captured</Th>
                    <Th className="hidden sm:table-cell">Statuses</Th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((record, index) => (
                    <tr key={`${record.started ?? ""}-${index}`}>
                      <Td className="numeric whitespace-nowrap">{when(record.started, "")}</Td>
                      <Td>
                        <span
                          className={
                            record.exit_code === 4
                              ? "text-accent"
                              : record.exit_code === 3
                                ? "text-structure"
                                : "text-muted"
                          }
                        >
                          {outcome(record.exit_code)}
                        </span>
                      </Td>
                      <Td numeric>
                        {record.captured ?? 0}/{record.sources ?? 0}
                        {record.capture_failed ? (
                          <span className="block text-xs text-accent">{record.capture_failed} failed</span>
                        ) : null}
                      </Td>
                      <Td className="hidden text-muted sm:table-cell">
                        {Object.entries(record.counts ?? {})
                          .map(([name, count]) => `${name.toLowerCase()} ${count}`)
                          .join(", ")}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            ) : (
              <EmptyState command="regwatch run">
                No run has been recorded yet. Each scheduled run, each regwatch run and each Run now
                is listed here with its result.
              </EmptyState>
            )}
          </Section>
        </>
      ) : null}
    </>
  );
}
