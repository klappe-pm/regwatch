"use client";

import { useState } from "react";

import { Icon } from "@/components/icon";
import {
  Button,
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
import type { Automations } from "@/lib/types";

export default function AutomationsPage() {
  const { data, error, loading, reload } = useApi<Automations>("/api/automations");
  const [notice, setNotice] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  async function runNow() {
    setRunning(true);
    try {
      const result = await postJson<{ available: boolean }>("/api/automations/run", {});
      setNotice(result.available ? "The run finished." : "Running from here is not available yet.");
      reload();
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : "The run failed.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Automations"
        description="The schedule that runs capture and then check, and the record of each run."
        actions={
          <Button variant="primary" onClick={runNow} disabled={running || !data?.runs.available}>
            <Icon name="play_arrow" size={18} />
            Run now
          </Button>
        }
      />
      {notice ? (
        <p role="status" className="mb-4 text-sm">
          {notice}
        </p>
      ) : null}
      {error ? <ErrorNote message={error} /> : null}
      {loading && !data ? <Loading /> : null}
      {data ? (
        <>
          <Section title="Schedule" id="schedule">
            {data.schedule.available ? (
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 border border-line bg-raised p-4 text-sm">
                <dt className="text-muted">Runs</dt>
                <dd>{data.schedule.every ?? "Not set"}</dd>
                <dt className="text-muted">Next run</dt>
                <dd className="numeric">{data.schedule.next_run ?? "Not set"}</dd>
              </dl>
            ) : (
              <EmptyState command={data.schedule.command}>
                Your schedule will appear here: how often capture and check run, and when the next run
                is. Nothing is scheduled until you set it up.
              </EmptyState>
            )}
          </Section>
          <Section title="More Than Once a Day" id="frequent">
            {data.premium ? (
              <p className="text-sm text-muted">
                Runs more often than daily are available. Set the frequency with{" "}
                <code className="font-mono">regwatch schedule --every</code>.
              </p>
            ) : (
              <Locked feature="Running more often than once a day" />
            )}
          </Section>
          <Section title="Run History" id="history">
            {data.runs.available && data.runs.records.length > 0 ? (
              <Table label="Run history">
                <thead>
                  <tr>
                    <Th>Started</Th>
                    <Th>Ended</Th>
                    <Th numeric>Exit Code</Th>
                    <Th>Results</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.runs.records.map((record, index) => (
                    <tr key={`${record.started ?? index}`}>
                      <Td className="numeric">{record.started ?? ""}</Td>
                      <Td className="numeric">{record.ended ?? ""}</Td>
                      <Td numeric>{record.exit_code ?? ""}</Td>
                      <Td>
                        {Object.entries(record.counts ?? {})
                          .map(([name, count]) => `${name.toLowerCase()} ${count}`)
                          .join(", ")}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            ) : data.runs.available ? (
              <EmptyState>No run has been recorded yet.</EmptyState>
            ) : (
              <EmptyState command={data.runs.command}>
                Each scheduled or manual run will be listed here with its start and end, its results by
                status and its exit code.
              </EmptyState>
            )}
          </Section>
        </>
      ) : null}
    </>
  );
}
