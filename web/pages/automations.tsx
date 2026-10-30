import Box from "@mui/material/Box";
import TableBody from "@mui/material/TableBody";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import { useEffect, useState } from "react";

import {
  Button,
  Command,
  DataTable,
  Details,
  EmptyState,
  ErrorNote,
  Icon,
  Loading,
  Locked,
  Notice,
  PageHeader,
  Piece,
  Section,
  Td,
  Th,
} from "@/components/ui";
import { postJson, useApi } from "@/lib/api";
import { cadence, outcome, when } from "@/lib/labels";
import { t } from "@/lib/text";
import type { Automations } from "@/lib/types";

const p = (key: string, vars?: Record<string, string | number>) => t(`pages.automations.${key}`, vars);
const muted = "var(--ds-role-on-surface-variant)";

export default function AutomationsPage() {
  const { data, error, loading, reload } = useApi<Automations>("/api/automations");
  const [notice, setNotice] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const running = starting || data?.running === true;

  // While a run is in progress, look again every two seconds.
  useEffect(() => {
    if (data && !data.running && notice === p("notes.started")) setNotice(p("notes.finished"));
    if (!data?.running) return;
    const timer = window.setTimeout(reload, 2000);
    return () => window.clearTimeout(timer);
  }, [data, notice, reload]);

  async function runNow() {
    setStarting(true);
    try {
      await postJson("/api/automations/run", {});
      setNotice(p("notes.started"));
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : p("notes.failed"));
    } finally {
      setStarting(false);
      reload();
    }
  }

  const schedule = data?.schedule;
  const records = data?.runs.records ?? [];
  const tool = schedule?.via === "launchd" ? "launchd" : "cron";

  return (
    <>
      <PageHeader
        title={p("header.title")}
        description={p("header.description")}
        actions={
          <Button variant="primary" onClick={runNow} disabled={running || !data}>
            <Icon name="play_arrow" size={18} />
            {running ? p("header.running") : p("header.run-now")}
          </Button>
        }
      />
      <Notice message={notice} />
      {data?.last_error ? <ErrorNote message={data.last_error} /> : null}
      {error ? <ErrorNote message={error} /> : null}
      {loading && !data ? <Loading /> : null}
      {data && schedule ? (
        <>
          <Section title={p("schedule.title")} id="schedule">
            {schedule.installed ? (
              <Piece name="panel">
                <Details
                  rows={[
                    [p("schedule.runs"), cadence(schedule.every)],
                    [
                      p("schedule.next-run"),
                      <span className="numeric">
                        {when(schedule.next_run, schedule.via === "launchd" ? p("schedule.after-first") : p("schedule.not-known"))}
                      </span>,
                    ],
                    [p("schedule.installed-with"), tool],
                    ...(schedule.note ? ([[p("schedule.note"), schedule.note]] as [string, string][]) : []),
                  ]}
                />
              </Piece>
            ) : (
              <EmptyState command="schedule-install">
                {p("schedule.empty", { tool })}
                {schedule.note ? ` ${p("schedule.empty-note", { note: `${schedule.note[0].toUpperCase()}${schedule.note.slice(1)}` })}` : ""}
              </EmptyState>
            )}
          </Section>
          <Section title={p("frequent.title")} id="frequent">
            {data.premium ? (
              <Typography component="p" sx={{ typography: "small", color: muted }}>
                {p("frequent.available")} <Command>{t("global.ui.commands.schedule-hourly")}</Command>
                {p("frequent.after")}
              </Typography>
            ) : (
              <Locked feature={p("frequent.feature")} />
            )}
          </Section>
          <Section title={p("history.title")} id="history">
            {records.length > 0 ? (
              <DataTable label={p("history.table")}>
                <TableHead>
                  <TableRow>
                    <Th>{p("history.started")}</Th>
                    <Th>{p("history.result")}</Th>
                    <Th numeric>{p("history.captured")}</Th>
                    <Th hide="sm">{p("history.statuses")}</Th>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {records.map((record, index) => (
                    <TableRow key={`${record.started ?? ""}-${index}`}>
                      <Td sx={{ whiteSpace: "nowrap" }}>
                        <span className="numeric">{when(record.started, "")}</span>
                      </Td>
                      <Td>
                        <Box
                          component="span"
                          sx={{ color: record.exit_code === 4 ? "var(--ds-role-error)" : record.exit_code === 3 ? "var(--ds-role-primary)" : muted }}
                        >
                          {outcome(record.exit_code)}
                        </Box>
                      </Td>
                      <Td numeric>
                        {record.captured ?? 0}/{record.sources ?? 0}
                        {record.capture_failed ? (
                          <Box component="span" sx={{ display: "block", typography: "caption", color: "var(--ds-role-error)" }}>
                            {p("history.failed", { count: record.capture_failed })}
                          </Box>
                        ) : null}
                      </Td>
                      <Td hide="sm" muted>
                        {Object.entries(record.counts ?? {})
                          .map(([name, count]) => `${name.toLowerCase()} ${count}`)
                          .join(", ")}
                      </Td>
                    </TableRow>
                  ))}
                </TableBody>
              </DataTable>
            ) : (
              <EmptyState command="run">{p("history.empty")}</EmptyState>
            )}
          </Section>
        </>
      ) : null}
    </>
  );
}
