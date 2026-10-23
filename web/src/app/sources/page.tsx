"use client";

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
import { ACCESS, CATEGORIES, label, words } from "@/lib/labels";
import type { Catalogue, CatalogueEntry, MySource } from "@/lib/types";

function Mine() {
  const { data, error, loading } = useApi<{ sources: MySource[] }>("/api/sources");
  const initial = useQueryParam("q");
  const [text, setText] = useState("");
  useEffect(() => setText(initial), [initial]);

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
          {text ? "No source matches this filter." : "The sources you watch will appear here."}
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

function CatalogueSection() {
  const initial = useQueryParam("catalogue");
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState({ category: "", region: "", kind: "", access: "" });
  const [data, setData] = useState<Catalogue | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

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
  }, [query, filters]);

  const available = data?.available === true;
  const facets = data?.facets ?? {};
  const choices = (name: string, all: string, known?: [string, string][]): [string, string][] => [
    ["", all],
    ...(known ?? (facets[name] ?? []).map((value): [string, string] => [value, words(value)])),
  ];

  async function add(entry: CatalogueEntry) {
    try {
      const result = await postJson<{ available: boolean }>("/api/catalogue/add", {
        source_id: entry.source_id,
      });
      setNotice(result.available ? `Added ${entry.name} to your sources.` : "Adding sources is not available yet.");
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : "The source could not be added.");
    }
  }

  const grouped = CATEGORIES.map(([id, name]) => ({
    id,
    name,
    entries: (data?.entries ?? []).filter((e) => (e.category ?? "") === id),
  })).filter((group) => group.entries.length > 0);
  const other = (data?.entries ?? []).filter(
    (e) => !CATEGORIES.some(([id]) => id === (e.category ?? "")),
  );
  if (other.length) grouped.push({ id: "other", name: "Other", entries: other });

  return (
    <Section title="Catalogue" id="catalogue">
      <div className="no-print mb-4 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-5">
        <Field label="Search the catalogue">
          <input
            type="search"
            className={CONTROL}
            placeholder="Name, publisher or jurisdiction"
            value={query}
            disabled={data !== null && !available}
            onChange={(event) => setQuery(event.target.value)}
          />
        </Field>
        <Field label="Category">
          <Select
            value={filters.category}
            disabled={!available}
            onChange={(category) => setFilters({ ...filters, category })}
            options={choices("category", "All categories", CATEGORIES)}
          />
        </Field>
        <Field label="Region">
          <Select
            value={filters.region}
            disabled={!available}
            onChange={(region) => setFilters({ ...filters, region })}
            options={choices("region", "All regions")}
          />
        </Field>
        <Field label="Kind">
          <Select
            value={filters.kind}
            disabled={!available}
            onChange={(kind) => setFilters({ ...filters, kind })}
            options={choices("kind", "All kinds")}
          />
        </Field>
        <Field label="Access">
          <Select
            value={filters.access}
            disabled={!available}
            onChange={(access) => setFilters({ ...filters, access })}
            options={choices("access", "Any access", ACCESS)}
          />
        </Field>
      </div>
      {notice ? (
        <p role="status" className="mb-2 text-sm">
          {notice}
        </p>
      ) : null}
      {error ? <ErrorNote message={error} /> : null}
      {data && !available ? (
        <EmptyState command={data.available ? undefined : data.command}>
          The source catalogue will appear here: regulators, legislatures, gazettes, supply and
          commodity sources and trade press, grouped by category, with filters by region, kind and
          access and a button to add each one to your sources.
        </EmptyState>
      ) : null}
      {available && grouped.length === 0 ? <EmptyState>No catalogue source matches.</EmptyState> : null}
      {grouped.map((group) => (
        <div key={group.id} className="mb-4">
          <h3 className="mb-1 text-sm font-semibold">
            {group.name} <span className="numeric font-normal text-muted">({group.entries.length})</span>
          </h3>
          <Table label={`${group.name} sources`}>
            <thead>
              <tr>
                <Th>Source</Th>
                <Th>Region</Th>
                <Th>Kind</Th>
                <Th>Access</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {group.entries.map((entry) => (
                <tr key={entry.source_id}>
                  <Td>
                    {entry.name}
                    <span className="block text-xs text-muted">
                      {[entry.publisher, entry.description].filter(Boolean).join(". ")}
                    </span>
                  </Td>
                  <Td>{entry.region ? words(entry.region) : entry.jurisdiction}</Td>
                  <Td>{entry.kind ? words(entry.kind) : ""}</Td>
                  <Td>{entry.access ? label(ACCESS, entry.access) : ""}</Td>
                  <Td numeric>
                    <Button onClick={() => add(entry)} label={`Add ${entry.name}`}>
                      <Icon name="add" size={18} />
                      Add
                    </Button>
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
  return (
    <>
      <PageHeader
        title="Sources"
        description="The sources you watch, with their status from the last stored snapshot, and the catalogue to choose more from."
      />
      <Mine />
      <CatalogueSection />
    </>
  );
}
