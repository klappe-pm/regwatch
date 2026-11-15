import Box from "@mui/material/Box";
import ButtonBase from "@mui/material/ButtonBase";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import { Fragment, useEffect, useMemo, useState } from "react";

import {
  ControlInput,
  DataTable,
  Details,
  EmptyState,
  ErrorNote,
  ExternalLink,
  Field,
  FilterRow,
  Icon,
  Loading,
  PageHeader,
  Select,
  SeverityLabel,
  Td,
  Th,
} from "@/components/ui";
import { useApi, useQueryParam } from "@/lib/api";
import { t } from "@/lib/text";
import type { Obligation } from "@/lib/types";

const p = (key: string) => t(`pages.obligations.${key}`);
const muted = "var(--ds-role-on-surface-variant)";

export default function ObligationsPage() {
  const { data, error, loading } = useApi<{ obligations: Obligation[] }>("/api/obligations");
  const initial = useQueryParam("q");
  const [text, setText] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    setText(initial);
    if (initial) setOpen(initial);
  }, [initial]);

  const all = useMemo(() => data?.obligations ?? [], [data]);
  const jurisdictions = useMemo(
    () => [...new Map(all.map((o) => [o.jurisdiction, o.jurisdiction_name])).entries()].sort((a, b) => a[1].localeCompare(b[1])),
    [all],
  );
  const rows = useMemo(() => {
    const query = text.trim().toLowerCase();
    return all.filter(
      (o) =>
        (!jurisdiction || o.jurisdiction === jurisdiction) &&
        (!query || [o.obligation_id, o.title, o.citation, o.instrument, o.jurisdiction_name].join(" ").toLowerCase().includes(query)),
    );
  }, [all, text, jurisdiction]);

  return (
    <>
      <PageHeader title={p("header.title")} description={p("header.description")} />
      {error ? <ErrorNote message={error} /> : null}
      {loading && !data ? <Loading /> : null}
      {data ? (
        <>
          <FilterRow>
            <Field label={p("filters.filter")}>
              <ControlInput type="search" placeholder={p("filters.filter-placeholder")} value={text} onChange={(event) => setText(event.target.value)} />
            </Field>
            <Field label={p("filters.jurisdiction")}>
              <Select value={jurisdiction} onChange={setJurisdiction} options={[["", p("filters.all-jurisdictions")], ...jurisdictions]} />
            </Field>
          </FilterRow>
          {rows.length === 0 ? (
            <EmptyState command="list">{p("table.empty")}</EmptyState>
          ) : (
            <DataTable label={p("table.label")}>
              <TableHead>
                <TableRow>
                  <Th>{p("table.obligation")}</Th>
                  <Th>{p("table.jurisdiction")}</Th>
                  <Th>{p("table.status")}</Th>
                  <Th numeric>{p("table.effective")}</Th>
                  <Th numeric>{p("table.impacts")}</Th>
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((o) => {
                  const expanded = open === o.obligation_id;
                  return (
                    <Fragment key={o.obligation_id}>
                      <TableRow sx={{ bgcolor: expanded ? "var(--ds-role-secondary-container)" : "transparent" }}>
                        <Td>
                          <ButtonBase
                            aria-expanded={expanded}
                            onClick={() => setOpen(expanded ? null : o.obligation_id)}
                            sx={{ display: "flex", alignItems: "flex-start", gap: 1, textAlign: "left", font: "inherit", color: "var(--ds-role-on-surface)", "&:hover": { color: "var(--ds-role-primary)" } }}
                          >
                            <Icon name="chevron_right" size={18} sx={{ mt: "2px", color: muted, transform: expanded ? "rotate(90deg)" : "none" }} />
                            <span>{o.title}</span>
                          </ButtonBase>
                        </Td>
                        <Td>{o.jurisdiction_name}</Td>
                        <Td>{o.status}</Td>
                        <Td numeric>{o.effective_date || t("global.ui.state.no-date")}</Td>
                        <Td numeric>{o.impacts.length}</Td>
                      </TableRow>
                      {expanded ? (
                        <TableRow sx={{ bgcolor: "var(--ds-role-surface)" }}>
                          <TableCell colSpan={5} sx={{ borderBottom: "1px solid var(--ds-role-outline-variant)", px: 4, py: 4 }}>
                            <Details
                              sx={{ gridTemplateColumns: { xs: "minmax(0, 1fr)", sm: "auto 1fr" } }}
                              rows={[
                                [p("detail.id"), o.obligation_id, true],
                                [p("detail.instrument"), o.instrument],
                                [p("detail.citation"), o.source_url ? <ExternalLink href={o.source_url}>{o.citation}</ExternalLink> : o.citation],
                                [p("detail.categories"), o.categories.join(", ") || p("detail.no-categories")],
                              ]}
                            />
                            <Typography component="h3" sx={{ mt: 4, typography: "overline", color: muted }}>
                              {p("detail.impacts")}
                            </Typography>
                            {o.impacts.length === 0 ? (
                              <Typography component="p" sx={{ typography: "small", color: muted }}>
                                {p("detail.no-impacts")}
                              </Typography>
                            ) : (
                              <Box component="ul" sx={{ mt: 1, mb: 0, p: 0, listStyle: "none", typography: "small" }}>
                                {o.impacts.map((impact) => (
                                  <Box component="li" key={impact.product_id} sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 2, py: 1 }}>
                                    <SeverityLabel severity={impact.severity} />
                                    <span>{impact.product_name}</span>
                                    <Box component="span" sx={{ color: muted }}>
                                      {impact.reasons.join("; ")}
                                    </Box>
                                  </Box>
                                ))}
                              </Box>
                            )}
                          </TableCell>
                        </TableRow>
                      ) : null}
                    </Fragment>
                  );
                })}
              </TableBody>
            </DataTable>
          )}
        </>
      ) : null}
    </>
  );
}
