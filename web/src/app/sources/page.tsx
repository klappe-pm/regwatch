"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Icon } from "@/components/icon";
import {
  Button,
  CONTROL,
  EmptyState,
  ErrorNote,
  Field,
  Loading,
  PageHeader,
  Section,
  Select,
  StatusLabel,
  Table,
  Td,
  Th,
} from "@/components/ui";
import { getJson, postJson, useApi, useQueryParam } from "@/lib/api";
import { catalogueGroups } from "@/lib/catalogue-view";
import { ACCESS, CATEGORIES, label, place, words } from "@/lib/labels";
import type { AddResult, Catalogue, CatalogueEntry, MySource } from "@/lib/types";

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
    return (data?.sources ?? []).filter(
      (s) => !query || [s.source_id, s.name, s.jurisdiction].join(" ").toLowerCase().includes(query),
    );
  }, [data, text]);

  return (
    <Section
      title="Your Sources"
      id="mine"
      actions={
        <input
          type="search"
          aria-label="Filter your sources"
          className={`${CONTROL} no-print w-56`}
          placeholder="Filter"
          value={text}
          onChange={(event) => setText(event.target.value)}
        />
      }
    >
      {error ? <ErrorNote message={error} /> : null}
      {loading && !data ? <Loading /> : null}
      {data && rows.length === 0 ? (
        <EmptyState command="regwatch sources add">
          {text ? "No source matches this filter." : "Add sources from the catalogue below."}
        </EmptyState>
      ) : null}
      {data && rows.length > 0 ? (
        <Table label="Your sources">
          <thead>
            <tr>
              <Th>Source</Th>
              <Th>Jurisdiction</Th>
              <Th className="hidden sm:table-cell">Mechanism</Th>
              <Th className="hidden sm:table-cell">Cadence</Th>
              <Th>Last Status</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((source) => (
              <tr key={source.source_id}>
                <Td>
                  {source.name}
                  <span className="block font-mono text-xs text-muted">{source.source_id}</span>
                </Td>
                <Td>{source.jurisdiction}</Td>
                <Td className="hidden sm:table-cell">{source.mechanism}</Td>
                <Td className="hidden sm:table-cell">{source.cadence}</Td>
                <Td>
                  <StatusLabel status={source.status} />
                  {source.detail ? <span className="block text-xs text-muted">{source.detail}</span> : null}
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      ) : null}
    </Section>
  );
}

const ACCESS_STYLE: Record<string, string> = {
  free: "text-muted",
  "free-key": "text-structure",
  paid: "text-ink font-medium",
};

function CatalogueSection({ onAdded }: { onAdded: () => void }) {
  const initial = useQueryParam("catalogue");
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState({ category: "", region: "", kind: "", access: "" });
  const [round, setRound] = useState(0);
  const [data, setData] = useState<Catalogue | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
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
          if (live) setError(reason instanceof Error ? reason.message : "The request failed.");
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
    ...(known ??
      (facets[name] ?? []).map((value): [string, string] => [
        value,
        name === "region" ? place(value) : words(value),
      ])),
  ];

  async function add(entry: CatalogueEntry) {
    setBusy(entry.source_id);
    try {
      const result = await postJson<AddResult>("/api/catalogue/add", { source_id: entry.source_id });
      const parts = [
        result.added.length ? `Added ${entry.name} to your sources.` : `${entry.name} is already in your sources.`,
      ];
      if (result.added_jurisdictions.length) {
        parts.push(`Added the jurisdiction ${result.added_jurisdictions.join(", ")} to your register.`);
      }
      if (result.needs_key) parts.push("It needs a key; set one on the Keys page.");
      setNotice(parts.join(" "));
      setRound((value) => value + 1);
      onAdded();
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : "The source could not be added.");
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
      title="Catalogue"
      id="catalogue"
      actions={
        data ? (
          <p className="numeric text-sm text-muted" aria-live="polite">
            {entries.length} of {data.total} {data.total === 1 ? "source" : "sources"}
          </p>
        ) : null
      }
    >
      <div className="no-print mb-4 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-5">
        <Field label="Search the catalogue">
          <input
            type="search"
            className={CONTROL}
            placeholder="Name, publisher or jurisdiction"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </Field>
        <Field label="Category">
          <Select
            value={filters.category}
            onChange={(category) => setFilters({ ...filters, category })}
            options={choices("category", "All categories", CATEGORIES)}
          />
        </Field>
        <Field label="Region">
          <Select
            value={filters.region}
            onChange={(region) => setFilters({ ...filters, region })}
            options={choices("region", "All regions")}
          />
        </Field>
        <Field label="Kind">
          <Select
            value={filters.kind}
            onChange={(kind) => setFilters({ ...filters, kind })}
            options={choices("kind", "All kinds")}
          />
        </Field>
        <Field label="Access">
          <Select
            value={filters.access}
            onChange={(access) => setFilters({ ...filters, access })}
            options={choices("access", "Any access", ACCESS)}
          />
        </Field>
      </div>
      {notice ? (
        <p role="status" className="mb-2 text-sm">
          {notice}{" "}
          {notice.includes("Keys page") ? (
            <Link className="text-structure underline underline-offset-2" href="/keys/">
              Open Keys
            </Link>
          ) : null}
        </p>
      ) : null}
      {error ? <ErrorNote message={error} /> : null}
      {!data && !error ? <Loading /> : null}
      {data && grouped.length === 0 ? (
        <EmptyState>No catalogue source matches this search and these filters.</EmptyState>
      ) : null}
      {grouped.map((group) => (
        <div key={group.id} className="mb-4">
          <h3 className="mb-1 text-sm font-semibold">
            {group.name} <span className="numeric font-normal text-muted">({group.entries.length})</span>
          </h3>
          <Table label={group.ranked ? "Catalogue search results" : `${group.name} sources`}>
            <thead>
              <tr>
                <Th>Source</Th>
                <Th className="hidden md:table-cell">Jurisdiction</Th>
                <Th className="hidden md:table-cell">Kind</Th>
                <Th>Access</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {group.entries.map((entry) => (
                <tr key={entry.source_id}>
                  <Td>
                    <span className="font-medium">{entry.name}</span>
                    <span className="block text-xs text-muted">
                      {entry.publisher}
                      {group.ranked ? ` · ${label(CATEGORIES, entry.category)}` : null}
                      <span className="md:hidden">
                        {" "}
                        · {entry.jurisdiction} · {words(entry.kind)}
                      </span>
                    </span>
                    {searching || group.entries.length <= 12 ? (
                      <span className="mt-0.5 block text-xs text-muted">{entry.description}</span>
                    ) : null}
                  </Td>
                  <Td className="hidden md:table-cell">
                    {entry.jurisdiction}
                    <span className="block text-xs text-muted">{place(entry.region)}</span>
                  </Td>
                  <Td className="hidden md:table-cell">{words(entry.kind)}</Td>
                  <Td className={ACCESS_STYLE[entry.access] ?? ""}>
                    {entry.access_label || label(ACCESS, entry.access)}
                  </Td>
                  <Td numeric>
                    {entry.chosen ? (
                      <span className="inline-flex items-center gap-1 text-sm text-ok">
                        <Icon name="check_circle" size={16} />
                        Watching
                      </span>
                    ) : (
                      <Button
                        onClick={() => add(entry)}
                        disabled={busy !== null}
                        label={`Add ${entry.name}`}
                      >
                        <Icon name="add" size={18} />
                        Add
                      </Button>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      ))}
    </Section>
  );
}

export default function SourcesPage() {
  const [round, setRound] = useState(0);
  return (
    <>
      <PageHeader
        title="Sources"
        description="The sources you watch, with their status from the last stored snapshot, and the catalogue to choose more from. Adding a source writes it to your sources file, as regwatch sources add does."
      />
      <Mine round={round} />
      <CatalogueSection onAdded={() => setRound((value) => value + 1)} />
    </>
  );
}
