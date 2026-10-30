import Box from "@mui/material/Box";
import ButtonBase from "@mui/material/ButtonBase";
import TableBody from "@mui/material/TableBody";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import { useEffect, useMemo, useState } from "react";

import {
  ControlInput,
  DataTable,
  Details,
  EmptyState,
  ErrorNote,
  ExternalLink,
  Field,
  FilterRow,
  Loading,
  PageHeader,
  Piece,
  Section,
  Select,
  SeverityLabel,
  StatusLabel,
  Sub,
  Td,
  Th,
} from "@/components/ui";
import { useApi, useQueryParam } from "@/lib/api";
import { SEVERITY } from "@/lib/labels";
import { t } from "@/lib/text";
import type { Changes, Impact } from "@/lib/types";
import { NarrowOnly } from "@/views/overview";

const p = (key: string, vars?: Record<string, string | number>) => t(`pages.changes.${key}`, vars);
const muted = "var(--ds-role-on-surface-variant)";

function key(impact: Impact): string {
  return `${impact.obligation_id}|${impact.product_id}`;
}

function Detail({ impact }: { impact: Impact | null }) {
  if (!impact) {
    return (
      <Typography component="p" sx={{ typography: "small", color: muted }}>
        {p("detail.prompt")}
      </Typography>
    );
  }
  return (
    <Box sx={{ typography: "small" }}>
      <SeverityLabel severity={impact.severity} />
      <Typography component="h3" sx={{ mt: 2, fontSize: "15px", fontWeight: 600, lineHeight: "24px" }}>
        {impact.obligation_title}
      </Typography>
      <Details
        sx={{ mt: 2 }}
        rows={[
          [p("detail.product"), impact.product_name],
          [p("detail.jurisdiction"), impact.jurisdiction],
          [p("detail.status"), impact.status],
          [p("detail.effective"), <span className="numeric">{impact.effective_date || t("global.ui.state.no-date")}</span>],
          [p("detail.focus"), impact.in_focus ? impact.focus.join(", ") || p("detail.all-areas") : p("detail.outside")],
          [p("detail.obligation"), impact.obligation_id, true],
        ]}
      />
      <Typography component="h4" sx={{ mt: 4, typography: "overline", color: muted }}>
        {p("detail.why")}
      </Typography>
      <Box component="ul" sx={{ mt: 1, mb: 0, pl: 4 }}>
        {impact.reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </Box>
    </Box>
  );
}

export default function ChangesPage() {
  const { data, error, loading } = useApi<Changes>("/api/changes");
  const initial = useQueryParam("q");
  const [text, setText] = useState("");
  const [severity, setSeverity] = useState("");
  const [scope, setScope] = useState("all");
  const [jurisdiction, setJurisdiction] = useState("");
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => setText(initial), [initial]);

  // Arriving from search with an obligation id selects its first change, so its reasons show.
  useEffect(() => {
    const match = data?.impacts.find((i) => i.obligation_id === initial);
    if (match) setSelected(key(match));
  }, [data, initial]);

  const impacts = useMemo(() => {
    const query = text.trim().toLowerCase();
    return (data?.impacts ?? []).filter(
      (i) =>
        (!severity || i.severity === severity) &&
        (scope === "all" || i.in_focus) &&
        (!jurisdiction || i.jurisdiction === jurisdiction) &&
        (!query ||
          [i.obligation_id, i.obligation_title, i.product_name, i.jurisdiction, ...i.reasons]
            .join(" ")
            .toLowerCase()
            .includes(query)),
    );
  }, [data, text, severity, scope, jurisdiction]);

  const jurisdictions = useMemo(() => [...new Set((data?.impacts ?? []).map((i) => i.jurisdiction))].sort(), [data]);
  const chosen = impacts.find((i) => key(i) === selected) ?? null;
  const flagged = (data?.sources ?? []).filter((s) => s.flagged || s.needs_attention);

  return (
    <>
      <PageHeader title={p("header.title")} description={p("header.description")} />
      {error ? <ErrorNote message={error} /> : null}
      {loading && !data ? <Loading /> : null}
      {data ? (
        <>
          <FilterRow>
            <Field label={p("filters.filter")}>
              <ControlInput type="search" value={text} placeholder={p("filters.filter-placeholder")} onChange={(event) => setText(event.target.value)} />
            </Field>
            <Field label={p("filters.severity")}>
              <Select
                value={severity}
                onChange={setSeverity}
                options={[["", p("filters.all-severities")], ...data.severities.map((s): [string, string] => [s, SEVERITY[s] ?? s])]}
              />
            </Field>
            <Field label={p("filters.focus")}>
              <Select
                value={scope}
                onChange={setScope}
                options={[
                  ["all", p("filters.all-changes")],
                  ["focus", p("filters.in-focus")],
                ]}
              />
            </Field>
            <Field label={p("filters.jurisdiction")}>
              <Select
                value={jurisdiction}
                onChange={setJurisdiction}
                options={[["", p("filters.all-jurisdictions")], ...jurisdictions.map((j): [string, string] => [j, j])]}
              />
            </Field>
          </FilterRow>

          <Section title={p("impacts.title", { count: impacts.length })} id="impacts">
            {impacts.length === 0 ? (
              <EmptyState>{p("impacts.empty")}</EmptyState>
            ) : (
              <Box sx={{ display: "grid", alignItems: "start", gap: 4, gridTemplateColumns: { xs: "minmax(0, 1fr)", lg: "minmax(0, 1fr) 300px" } }}>
                <DataTable label={p("impacts.table")}>
                  <TableHead>
                    <TableRow>
                      <Th>{p("impacts.severity")}</Th>
                      <Th>{p("impacts.obligation")}</Th>
                      <Th hide="sm">{p("impacts.product")}</Th>
                      <Th numeric>{p("impacts.effective")}</Th>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {impacts.map((impact) => {
                      const isSelected = key(impact) === selected;
                      return (
                        <TableRow
                          key={key(impact)}
                          aria-selected={isSelected}
                          sx={{ bgcolor: isSelected ? "var(--ds-role-secondary-container)" : "transparent", "&:hover": { bgcolor: "var(--ds-role-secondary-container)" } }}
                        >
                          <Td>
                            <SeverityLabel severity={impact.severity} />
                          </Td>
                          <Td>
                            <ButtonBase
                              onClick={() => setSelected(key(impact))}
                              sx={{ display: "inline", verticalAlign: "baseline", textAlign: "left", font: "inherit", color: "var(--ds-role-on-surface)", "&:hover": { color: "var(--ds-role-primary)", textDecoration: "underline" } }}
                            >
                              {impact.obligation_title}
                            </ButtonBase>
                            <Sub>
                              {impact.jurisdiction}
                              <NarrowOnly> · {impact.product_name}</NarrowOnly>
                              {impact.in_focus ? "" : ` ${p("impacts.outside-focus")}`}
                            </Sub>
                          </Td>
                          <Td hide="sm">{impact.product_name}</Td>
                          <Td numeric>{impact.effective_date || t("global.ui.state.no-date")}</Td>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </DataTable>
                <Piece
                  name="panel"
                  component="aside"
                  aria-label={p("impacts.selected")}
                  aria-live="polite"
                  sx={{ alignSelf: "start", position: { lg: "sticky" }, top: { lg: "22.5px" } }}
                >
                  <Detail impact={chosen} />
                </Piece>
              </Box>
            )}
          </Section>

          <Section title={p("sources.title")} id="sources">
            {flagged.length === 0 ? (
              <EmptyState command="check">{p("sources.empty")}</EmptyState>
            ) : (
              <DataTable label={p("sources.table")}>
                <TableHead>
                  <TableRow>
                    <Th>{p("sources.source")}</Th>
                    <Th>{p("sources.status")}</Th>
                    <Th>{p("sources.detail")}</Th>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {flagged.map((source) => (
                    <TableRow key={source.source_id}>
                      <Td>
                        {source.name}
                        <Sub mono>{source.source_id}</Sub>
                      </Td>
                      <Td>
                        <StatusLabel status={source.status} />
                      </Td>
                      <Td muted>{source.detail}</Td>
                    </TableRow>
                  ))}
                </TableBody>
              </DataTable>
            )}
          </Section>

          <Section title={p("candidates.title")} id="candidates">
            {data.candidates.length === 0 ? (
              <EmptyState command="ingest">{p("candidates.empty")}</EmptyState>
            ) : (
              <DataTable label={p("candidates.table")}>
                <TableHead>
                  <TableRow>
                    <Th numeric>{p("candidates.date")}</Th>
                    <Th>{p("candidates.document")}</Th>
                    <Th>{p("candidates.agency")}</Th>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.candidates.map((candidate) => (
                    <TableRow key={`${candidate.date}-${candidate.headline}`}>
                      <Td numeric>{candidate.date}</Td>
                      <Td>
                        {candidate.source_url ? <ExternalLink href={candidate.source_url}>{candidate.headline}</ExternalLink> : candidate.headline}
                        <Sub>{candidate.what_happened}</Sub>
                      </Td>
                      <Td>{candidate.agency}</Td>
                    </TableRow>
                  ))}
                </TableBody>
              </DataTable>
            )}
          </Section>
        </>
      ) : null}
    </>
  );
}
