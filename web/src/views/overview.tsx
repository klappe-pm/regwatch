import Box from "@mui/material/Box";
import TableBody from "@mui/material/TableBody";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import type { ReactNode } from "react";

import {
  DataTable,
  EmptyState,
  ErrorNote,
  Figures,
  Loading,
  PageHeader,
  Section,
  SeverityLabel,
  StatusLabel,
  Sub,
  Td,
  TextLink,
  Th,
} from "@/components/ui";
import { useApi } from "@/lib/api";
import { CATEGORIES, cadence, label, when } from "@/lib/labels";
import { t } from "@/lib/text";
import type { Overview } from "@/lib/types";

const p = (key: string, vars?: Record<string, string | number>) => t(`pages.overview.${key}`, vars);

/** Two sections side by side on wide screens. */
export function Pair({ children }: { children: ReactNode }) {
  return <Box sx={{ display: "grid", gap: 8, gridTemplateColumns: { xs: "minmax(0, 1fr)", xl: "repeat(2, minmax(0, 1fr))" } }}>{children}</Box>;
}

/** Text shown only below the small breakpoint, where its column is hidden. */
export function NarrowOnly({ children, at = "sm" }: { children: ReactNode; at?: "sm" | "md" }) {
  return (
    <Box component="span" sx={{ display: { xs: "inline", [at]: "none" } }}>
      {children}
    </Box>
  );
}

export function OverviewView() {
  const { data, error, loading } = useApi<Overview>("/api/overview");

  return (
    <>
      <PageHeader title={p("header.title")} description={data ? p("header.description", { generated: data.generated }) : undefined} />
      {error ? <ErrorNote message={error} /> : null}
      {loading && !data ? <Loading /> : null}
      {data ? (
        <>
          <Figures
            items={[
              { label: p("figures.new"), value: data.counts.new },
              { label: p("figures.changed"), value: data.counts.changed },
              { label: p("figures.suspicious"), value: data.counts.suspicious, urgent: data.counts.suspicious > 0 },
              { label: p("figures.failing"), value: data.counts.failing, urgent: data.counts.failing > 0 },
              {
                label: p("figures.next-run"),
                value: (
                  <Box component="span" sx={{ fontSize: "15px", lineHeight: "24px", fontWeight: 500 }}>
                    {data.schedule.installed
                      ? data.schedule.next_run
                        ? when(data.schedule.next_run)
                        : cadence(data.schedule.every)
                      : p("figures.not-scheduled")}
                  </Box>
                ),
              },
            ]}
          />

          <Pair>
            <Section title={p("regulatory.title")} id="regulatory">
              {data.priority.length === 0 ? (
                <EmptyState command="impact">{p("regulatory.empty")}</EmptyState>
              ) : (
                <DataTable label={p("regulatory.table")}>
                  <TableHead>
                    <TableRow>
                      <Th>{p("regulatory.severity")}</Th>
                      <Th>{p("regulatory.obligation")}</Th>
                      <Th hide="sm">{p("regulatory.product")}</Th>
                      <Th numeric>{p("regulatory.effective")}</Th>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {data.priority.map((impact) => (
                      <TableRow key={`${impact.obligation_id}-${impact.product_id}`}>
                        <Td>
                          <SeverityLabel severity={impact.severity} />
                        </Td>
                        <Td>
                          <TextLink
                            href={`/changes/?q=${encodeURIComponent(impact.obligation_id)}`}
                            quiet
                          >
                            {impact.obligation_title}
                          </TextLink>
                          <Sub>
                            {impact.jurisdiction}
                            <NarrowOnly> · {impact.product_name}</NarrowOnly>
                          </Sub>
                        </Td>
                        <Td hide="sm">{impact.product_name}</Td>
                        <Td numeric>{impact.effective_date || t("global.ui.state.no-date")}</Td>
                      </TableRow>
                    ))}
                  </TableBody>
                </DataTable>
              )}
            </Section>

            <Section title={p("supply.title")} id="supply">
              {data.supply_chain.sources.length === 0 ? (
                <EmptyState command="sources-add">
                  {p("supply.empty-before")} <TextLink href="/sources/">{p("supply.empty-link")}</TextLink> {p("supply.empty-after")}
                </EmptyState>
              ) : (
                <DataTable label={p("supply.table")}>
                  <TableHead>
                    <TableRow>
                      <Th>{p("supply.source")}</Th>
                      <Th hide="sm">{p("supply.category")}</Th>
                      <Th>{p("supply.last-status")}</Th>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {data.supply_chain.sources.map((source) => (
                      <TableRow key={source.source_id}>
                        <Td>
                          {source.name}
                          <Sub>
                            {source.jurisdiction}
                            <NarrowOnly> · {label(CATEGORIES, source.category)}</NarrowOnly>
                          </Sub>
                        </Td>
                        <Td hide="sm">{label(CATEGORIES, source.category)}</Td>
                        <Td>
                          <StatusLabel status={source.status} />
                        </Td>
                      </TableRow>
                    ))}
                  </TableBody>
                </DataTable>
              )}
              <Typography component="p" sx={{ mt: 2, typography: "caption", color: "var(--ds-role-on-surface-variant)" }}>
                {p("supply.note")}
              </Typography>
            </Section>
          </Pair>

          <Pair>
            <Section title={p("review.title")} id="review">
              {data.flagged.length === 0 ? (
                <EmptyState>{p("review.empty", { count: data.sources })}</EmptyState>
              ) : (
                <DataTable label={p("review.table")}>
                  <TableHead>
                    <TableRow>
                      <Th>{p("review.source")}</Th>
                      <Th>{p("review.status")}</Th>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {data.flagged.map((source) => (
                      <TableRow key={source.source_id}>
                        <Td>
                          {source.name}
                          {source.detail ? <Sub>{source.detail}</Sub> : null}
                        </Td>
                        <Td>
                          <StatusLabel status={source.status} />
                        </Td>
                      </TableRow>
                    ))}
                  </TableBody>
                </DataTable>
              )}
            </Section>

            <Section title={p("upcoming.title")} id="upcoming">
              {data.upcoming.length === 0 ? (
                <EmptyState>{p("upcoming.empty")}</EmptyState>
              ) : (
                <DataTable label={p("upcoming.table")}>
                  <TableHead>
                    <TableRow>
                      <Th numeric>{p("upcoming.date")}</Th>
                      <Th>{p("upcoming.obligation")}</Th>
                      <Th>{p("upcoming.status")}</Th>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {data.upcoming.map((item) => (
                      <TableRow key={item.obligation_id}>
                        <Td numeric>{item.effective_date}</Td>
                        <Td>
                          {item.title}
                          <Sub>{item.jurisdiction}</Sub>
                        </Td>
                        <Td>{item.status}</Td>
                      </TableRow>
                    ))}
                  </TableBody>
                </DataTable>
              )}
            </Section>
          </Pair>
        </>
      ) : null}
    </>
  );
}
