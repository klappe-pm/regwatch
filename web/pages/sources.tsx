import Box from "@mui/material/Box";
import TableBody from "@mui/material/TableBody";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import { useEffect, useMemo, useState } from "react";

import {
  Button,
  ControlInput,
  DataTable,
  EmptyState,
  ErrorNote,
  Field,
  FilterRow,
  Icon,
  Loading,
  PageHeader,
  Section,
  Select,
  StatusLabel,
  Sub,
  Td,
  TextLink,
  Th,
} from "@/components/ui";
import { getJson, postJson, useApi, useQueryParam } from "@/lib/api";
import { catalogueGroups } from "@/lib/catalogue-view";
import { ACCESS, CATEGORIES, label, place, words } from "@/lib/labels";
import { t } from "@/lib/text";
import type { AddResult, Catalogue, CatalogueEntry, MySource } from "@/lib/types";
import { NarrowOnly } from "@/views/overview";

const p = (key: string, vars?: Record<string, string | number>) => t(`pages.sources.${key}`, vars);
const muted = "var(--ds-role-on-surface-variant)";

function Mine({ round }: { round: number }) {
  const { data, error, loading, reload } = useApi<{ sources: MySource[] }>("/api/sources");
  const initial = useQueryParam("q");
  const [text, setText] = useState("");
  useEffect(() => setText(initial), [initial]);
  useEffect(() => {
    if (round > 0) reload();
  }, [round, reload]);

  const rows = useMemo(() => {
    const query = text.trim().toLowerCase();
    return (data?.sources ?? []).filter((s) => !query || [s.source_id, s.name, s.jurisdiction].join(" ").toLowerCase().includes(query));
  }, [data, text]);

  return (
    <Section
      title={p("mine.title")}
      id="mine"
      actions={
        <ControlInput
          type="search"
          className="no-print"
          inputProps={{ "aria-label": p("mine.filter-label") }}
          placeholder={p("mine.filter-placeholder")}
          value={text}
          onChange={(event) => setText(event.target.value)}
          sx={{ width: "210px" }}
        />
      }
    >
      {error ? <ErrorNote message={error} /> : null}
      {loading && !data ? <Loading /> : null}
      {data && rows.length === 0 ? <EmptyState command="sources-add">{text ? p("mine.no-match") : p("mine.empty")}</EmptyState> : null}
      {data && rows.length > 0 ? (
        <DataTable label={p("mine.table")}>
          <TableHead>
            <TableRow>
              <Th>{p("mine.source")}</Th>
              <Th>{p("mine.jurisdiction")}</Th>
              <Th hide="sm">{p("mine.mechanism")}</Th>
              <Th hide="sm">{p("mine.cadence")}</Th>
              <Th>{p("mine.last-status")}</Th>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((source) => (
              <TableRow key={source.source_id}>
                <Td>
                  {source.name}
                  <Sub mono>{source.source_id}</Sub>
                </Td>
                <Td>{source.jurisdiction}</Td>
                <Td hide="sm">{source.mechanism}</Td>
                <Td hide="sm">{source.cadence}</Td>
                <Td>
                  <StatusLabel status={source.status} />
                  {source.detail ? <Sub>{source.detail}</Sub> : null}
                </Td>
              </TableRow>
            ))}
          </TableBody>
        </DataTable>
      ) : null}
    </Section>
  );
}

const ACCESS_STYLE: Record<string, object> = {
  free: { color: muted },
  "free-key": { color: "var(--ds-role-primary)" },
  paid: { color: "var(--ds-role-on-surface)", fontWeight: 500 },
};

function CatalogueSection({ onAdded }: { onAdded: () => void }) {
  const initial = useQueryParam("catalogue");
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState({ category: "", region: "", kind: "", access: "" });
  const [round, setRound] = useState(0);
  const [data, setData] = useState<Catalogue | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ text: string; key: boolean } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => setQuery(initial), [initial]);

  useEffect(() => {
    let live = true;
    const params = new URLSearchParams({ q: query.trim(), ...filters });
    const timer = window.setTimeout(() => {
      getJson<Catalogue>(`/api/catalogue?${params.toString()}`)
        .then((value) => {
          if (live) {
            setData(value);
            setError(null);
          }
        })
        .catch((reason: unknown) => {
          if (live) setError(reason instanceof Error ? reason.message : t("global.ui.state.request-failed"));
        });
    }, 150);
    return () => {
      live = false;
      window.clearTimeout(timer);
    };
  }, [query, filters, round]);

  const facets = data?.facets ?? {};
  const choices = (name: string, all: string, known?: [string, string][]): [string, string][] => [
    ["", all],
    ...(known ?? (facets[name] ?? []).map((value): [string, string] => [value, name === "region" ? place(value) : words(value)])),
  ];

  async function add(entry: CatalogueEntry) {
    setBusy(entry.source_id);
    try {
      const result = await postJson<AddResult>("/api/catalogue/add", { source_id: entry.source_id });
      const parts = [result.added.length ? p("messages.added", { name: entry.name }) : p("messages.already", { name: entry.name })];
      if (result.added_jurisdictions.length) parts.push(p("messages.jurisdiction", { jurisdictions: result.added_jurisdictions.join(", ") }));
      if (result.needs_key) parts.push(p("messages.needs-key"));
      setNotice({ text: parts.join(" "), key: result.needs_key });
      setRound((value) => value + 1);
      onAdded();
    } catch (reason) {
      setNotice({ text: reason instanceof Error ? reason.message : p("messages.add-failed"), key: false });
    } finally {
      setBusy(null);
    }
  }

  const entries = data?.entries ?? [];
  // While a search is typed the server's ranking is kept as one list, best first;
  // with an empty box the catalogue is grouped by category.
  const grouped = catalogueGroups(entries, query, CATEGORIES);
  const searching = query.trim() !== "";

  return (
    <Section
      title={p("catalogue.title")}
      id="catalogue"
      actions={
        data ? (
          <Typography component="p" className="numeric" aria-live="polite" sx={{ typography: "small", color: muted }}>
            {p(data.total === 1 ? "catalogue.count-one" : "catalogue.count-many", { shown: entries.length, total: data.total })}
          </Typography>
        ) : null
      }
    >
      <FilterRow columns={5}>
        <Field label={p("catalogue.search")}>
          <ControlInput type="search" placeholder={p("catalogue.search-placeholder")} value={query} onChange={(event) => setQuery(event.target.value)} />
        </Field>
        <Field label={p("catalogue.category")}>
          <Select value={filters.category} onChange={(category) => setFilters({ ...filters, category })} options={choices("category", p("catalogue.all-categories"), CATEGORIES)} />
        </Field>
        <Field label={p("catalogue.region")}>
          <Select value={filters.region} onChange={(region) => setFilters({ ...filters, region })} options={choices("region", p("catalogue.all-regions"))} />
        </Field>
        <Field label={p("catalogue.kind")}>
          <Select value={filters.kind} onChange={(kind) => setFilters({ ...filters, kind })} options={choices("kind", p("catalogue.all-kinds"))} />
        </Field>
        <Field label={p("catalogue.access")}>
          <Select value={filters.access} onChange={(access) => setFilters({ ...filters, access })} options={choices("access", p("catalogue.any-access"), ACCESS)} />
        </Field>
      </FilterRow>
      {notice ? (
        <Typography component="p" role="status" sx={{ mb: 2, typography: "small" }}>
          {notice.text} {notice.key ? <TextLink href="/keys/">{p("catalogue.open-keys")}</TextLink> : null}
        </Typography>
      ) : null}
      {error ? <ErrorNote message={error} /> : null}
      {!data && !error ? <Loading /> : null}
      {data && grouped.length === 0 ? <EmptyState>{p("catalogue.empty")}</EmptyState> : null}
      {grouped.map((group) => (
        <Box key={group.id} sx={{ mb: 4 }}>
          <Typography component="h3" sx={{ mb: 1, typography: "small", fontWeight: 600 }}>
            {group.name}{" "}
            <Box component="span" className="numeric" sx={{ fontWeight: 400, color: muted }}>
              ({group.entries.length})
            </Box>
          </Typography>
          <DataTable label={group.ranked ? p("catalogue.results") : p("catalogue.group-table", { group: group.name })}>
            <TableHead>
              <TableRow>
                <Th>{p("catalogue.source")}</Th>
                <Th hide="md">{p("mine.jurisdiction")}</Th>
                <Th hide="md">{p("catalogue.kind")}</Th>
                <Th>{p("catalogue.access")}</Th>
                <Th />
              </TableRow>
            </TableHead>
            <TableBody>
              {group.entries.map((entry) => (
                <TableRow key={entry.source_id}>
                  <Td>
                    <Box component="span" sx={{ fontWeight: 500 }}>
                      {entry.name}
                    </Box>
                    <Sub>
                      {entry.publisher}
                      {group.ranked ? ` · ${label(CATEGORIES, entry.category)}` : null}
                      <NarrowOnly at="md">
                        {" "}
                        · {entry.jurisdiction} · {words(entry.kind)}
                      </NarrowOnly>
                    </Sub>
                    {searching || group.entries.length <= 12 ? (
                      <Box component="span" sx={{ mt: "1.875px", display: "block", typography: "caption", color: muted }}>
                        {entry.description}
                      </Box>
                    ) : null}
                  </Td>
                  <Td hide="md">
                    {entry.jurisdiction}
                    <Sub>{place(entry.region)}</Sub>
                  </Td>
                  <Td hide="md">{words(entry.kind)}</Td>
                  <Td sx={ACCESS_STYLE[entry.access] ?? {}}>{entry.access_label || label(ACCESS, entry.access)}</Td>
                  <Td numeric>
                    {entry.chosen ? (
                      <Box component="span" sx={{ display: "inline-flex", alignItems: "center", gap: 1, typography: "small", color: "var(--ds-role-tertiary)" }}>
                        <Icon name="check_circle" size={16} />
                        {p("catalogue.watching")}
                      </Box>
                    ) : (
                      <Button onClick={() => add(entry)} disabled={busy !== null} label={p("catalogue.add-label", { name: entry.name })}>
                        <Icon name="add" size={18} />
                        {p("catalogue.add")}
                      </Button>
                    )}
                  </Td>
                </TableRow>
              ))}
            </TableBody>
          </DataTable>
        </Box>
      ))}
    </Section>
  );
}

export default function SourcesPage() {
  const [round, setRound] = useState(0);
  return (
    <>
      <PageHeader title={p("header.title")} description={p("header.description")} />
      <Mine round={round} />
      <CatalogueSection onAdded={() => setRound((value) => value + 1)} />
    </>
  );
}
