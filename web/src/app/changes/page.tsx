"use client";

import { useEffect, useMemo, useState } from "react";

import {
  CONTROL,
  EmptyState,
  ErrorNote,
  Field,
  Loading,
  PageHeader,
  Section,
  Select,
  SeverityLabel,
  StatusLabel,
  Table,
  Td,
  Th,
} from "@/components/ui";
import { useApi, useQueryParam } from "@/lib/api";
import { SEVERITY } from "@/lib/labels";
import type { Changes, Impact } from "@/lib/types";

function key(impact: Impact): string {
  return `${impact.obligation_id}|${impact.product_id}`;
}

function Detail({ impact }: { impact: Impact | null }) {
  if (!impact) {
    return <p className="text-sm text-muted">Select a change to see why it was flagged.</p>;
  }
  return (
    <div className="text-sm">
      <SeverityLabel severity={impact.severity} />
      <h3 className="mt-2 text-base font-semibold">{impact.obligation_title}</h3>
      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
        <dt className="text-muted">Product</dt>
        <dd>{impact.product_name}</dd>
        <dt className="text-muted">Jurisdiction</dt>
        <dd>{impact.jurisdiction}</dd>
        <dt className="text-muted">Status</dt>
        <dd>{impact.status}</dd>
        <dt className="text-muted">Effective</dt>
        <dd className="numeric">{impact.effective_date || "No date"}</dd>
        <dt className="text-muted">Focus</dt>
        <dd>{impact.in_focus ? impact.focus.join(", ") || "All areas" : "Outside your focus areas"}</dd>
        <dt className="text-muted">Obligation</dt>
        <dd className="font-mono text-xs leading-5">{impact.obligation_id}</dd>
      </dl>
      <h4 className="mt-4 text-xs font-semibold uppercase tracking-wide text-muted">Why It Was Flagged</h4>
      <ul className="mt-1 list-disc pl-4">
        {impact.reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>
    </div>
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

  const jurisdictions = useMemo(
    () => [...new Set((data?.impacts ?? []).map((i) => i.jurisdiction))].sort(),
    [data],
  );
  const chosen = impacts.find((i) => key(i) === selected) ?? null;
  const flagged = (data?.sources ?? []).filter((s) => s.flagged || s.needs_attention);

  return (
    <>
      <PageHeader
        title="Changes"
        description="Candidate impacts ranked by focus area, severity and date, then source changes and unconfirmed candidates from ingest."
      />
      {error ? <ErrorNote message={error} /> : null}
      {loading && !data ? <Loading /> : null}
      {data ? (
        <>
          <div className="no-print mb-4 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Filter">
              <input
                type="search"
                className={CONTROL}
                value={text}
                placeholder="Obligation, product or reason"
                onChange={(event) => setText(event.target.value)}
              />
            </Field>
            <Field label="Severity">
              <Select
                value={severity}
                onChange={setSeverity}
                options={[["", "All severities"], ...data.severities.map((s): [string, string] => [s, SEVERITY[s] ?? s])]}
              />
            </Field>
            <Field label="Focus">
              <Select
                value={scope}
                onChange={setScope}
                options={[
                  ["all", "All changes"],
                  ["focus", "In my focus areas"],
                ]}
              />
            </Field>
            <Field label="Jurisdiction">
              <Select
                value={jurisdiction}
                onChange={setJurisdiction}
                options={[["", "All jurisdictions"], ...jurisdictions.map((j): [string, string] => [j, j])]}
              />
            </Field>
          </div>

          <Section title={`Candidate Impacts (${impacts.length})`} id="impacts">
            {impacts.length === 0 ? (
              <EmptyState>No candidate impact matches these filters.</EmptyState>
            ) : (
              <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
                <Table label="Candidate impacts">
                  <thead>
                    <tr>
                      <Th>Severity</Th>
                      <Th>Obligation</Th>
                      <Th className="hidden sm:table-cell">Product</Th>
                      <Th numeric>Effective</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {impacts.map((impact) => {
                      const isSelected = key(impact) === selected;
                      return (
                        <tr
                          key={key(impact)}
                          className={isSelected ? "bg-selection" : "hover:bg-selection"}
                          aria-selected={isSelected}
                        >
                          <Td>
                            <SeverityLabel severity={impact.severity} />
                          </Td>
                          <Td>
                            <button
                              type="button"
                              className="text-left text-ink hover:text-structure hover:underline"
                              onClick={() => setSelected(key(impact))}
                            >
                              {impact.obligation_title}
                            </button>
                            <span className="block text-xs text-muted">
                              {impact.jurisdiction}
                              <span className="sm:hidden"> · {impact.product_name}</span>
                              {impact.in_focus ? "" : " · outside your focus areas"}
                            </span>
                          </Td>
                          <Td className="hidden sm:table-cell">{impact.product_name}</Td>
                          <Td numeric>{impact.effective_date || "No date"}</Td>
                        </tr>
                      );
                    })}
                  </tbody>
                </Table>
                <aside
                  aria-label="Selected change"
                  aria-live="polite"
                  className="self-start border border-line bg-raised p-4 lg:sticky lg:top-6"
                >
                  <Detail impact={chosen} />
                </aside>
              </div>
            )}
          </Section>

          <Section title="Source Changes" id="sources">
            {flagged.length === 0 ? (
              <EmptyState command="regwatch check">
                Every source matches its accepted baseline.
              </EmptyState>
            ) : (
              <Table label="Source changes">
                <thead>
                  <tr>
                    <Th>Source</Th>
                    <Th>Status</Th>
                    <Th>Detail</Th>
                  </tr>
                </thead>
                <tbody>
                  {flagged.map((source) => (
                    <tr key={source.source_id}>
                      <Td>
                        {source.name}
                        <span className="block font-mono text-xs text-muted">{source.source_id}</span>
                      </Td>
                      <Td>
                        <StatusLabel status={source.status} />
                      </Td>
                      <Td className="text-muted">{source.detail}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
          </Section>

          <Section title="Unconfirmed Candidates" id="candidates">
            {data.candidates.length === 0 ? (
              <EmptyState command="regwatch ingest --fetch">
                Documents from the Federal Register style feed that may affect your register will
                appear here for review.
              </EmptyState>
            ) : (
              <Table label="Unconfirmed candidates">
                <thead>
                  <tr>
                    <Th numeric>Date</Th>
                    <Th>Document</Th>
                    <Th>Agency</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.candidates.map((candidate) => (
                    <tr key={`${candidate.date}-${candidate.headline}`}>
                      <Td numeric>{candidate.date}</Td>
                      <Td>
                        {candidate.source_url ? (
                          <a
                            className="text-structure underline underline-offset-2"
                            href={candidate.source_url}
                            rel="noreferrer noopener"
                            target="_blank"
                          >
                            {candidate.headline}
                          </a>
                        ) : (
                          candidate.headline
                        )}
                        <span className="block text-xs text-muted">{candidate.what_happened}</span>
                      </Td>
                      <Td>{candidate.agency}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
          </Section>
        </>
      ) : null}
    </>
  );
}
