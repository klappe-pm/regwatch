"use client";

import { Fragment, useEffect, useMemo, useState } from "react";

import { Icon } from "@/components/icon";
import {
  CONTROL,
  EmptyState,
  ErrorNote,
  Field,
  Loading,
  PageHeader,
  Select,
  SeverityLabel,
  Table,
  Td,
  Th,
} from "@/components/ui";
import { useApi, useQueryParam } from "@/lib/api";
import type { Obligation } from "@/lib/types";

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

  const all = data?.obligations ?? [];
  const jurisdictions = useMemo(
    () =>
      [...new Map(all.map((o) => [o.jurisdiction, o.jurisdiction_name])).entries()].sort((a, b) =>
        a[1].localeCompare(b[1]),
      ),
    [all],
  );
  const rows = useMemo(() => {
    const query = text.trim().toLowerCase();
    return all.filter(
      (o) =>
        (!jurisdiction || o.jurisdiction === jurisdiction) &&
        (!query ||
          [o.obligation_id, o.title, o.citation, o.instrument, o.jurisdiction_name]
            .join(" ")
            .toLowerCase()
            .includes(query)),
    );
  }, [all, text, jurisdiction]);

  return (
    <>
      <PageHeader
        title="Obligations"
        description="Your register, read only, with the products each obligation may affect. Edit the register files to change it."
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
                placeholder="Title, citation or id"
                value={text}
                onChange={(event) => setText(event.target.value)}
              />
            </Field>
            <Field label="Jurisdiction">
              <Select
                value={jurisdiction}
                onChange={setJurisdiction}
                options={[["", "All jurisdictions"], ...jurisdictions]}
              />
            </Field>
          </div>
          {rows.length === 0 ? (
            <EmptyState command="regwatch list">No obligation matches these filters.</EmptyState>
          ) : (
            <Table label="Obligations">
              <thead>
                <tr>
                  <Th>Obligation</Th>
                  <Th>Jurisdiction</Th>
                  <Th>Status</Th>
                  <Th numeric>Effective</Th>
                  <Th numeric>Impacts</Th>
                </tr>
              </thead>
              <tbody>
                {rows.map((o) => {
                  const expanded = open === o.obligation_id;
                  return (
                    <Fragment key={o.obligation_id}>
                      <tr className={expanded ? "bg-selection" : undefined}>
                        <Td>
                          <button
                            type="button"
                            aria-expanded={expanded}
                            className="flex items-start gap-1 text-left text-ink hover:text-structure"
                            onClick={() => setOpen(expanded ? null : o.obligation_id)}
                          >
                            <Icon
                              name="chevron_right"
                              size={18}
                              className={`mt-0.5 text-muted ${expanded ? "rotate-90" : ""}`}
                            />
                            <span>{o.title}</span>
                          </button>
                        </Td>
                        <Td>{o.jurisdiction_name}</Td>
                        <Td>{o.status}</Td>
                        <Td numeric>{o.effective_date || "No date"}</Td>
                        <Td numeric>{o.impacts.length}</Td>
                      </tr>
                      {expanded ? (
                        <tr className="bg-surface">
                          <td colSpan={5} className="border-b border-line px-4 py-4">
                            <dl className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[auto_1fr]">
                              <dt className="text-muted">Id</dt>
                              <dd className="font-mono text-xs leading-5">{o.obligation_id}</dd>
                              <dt className="text-muted">Instrument</dt>
                              <dd>{o.instrument}</dd>
                              <dt className="text-muted">Citation</dt>
                              <dd>
                                {o.source_url ? (
                                  <a
                                    className="text-structure underline underline-offset-2"
                                    href={o.source_url}
                                    target="_blank"
                                    rel="noreferrer noopener"
                                  >
                                    {o.citation}
                                  </a>
                                ) : (
                                  o.citation
                                )}
                              </dd>
                              <dt className="text-muted">Categories</dt>
                              <dd>{o.categories.join(", ") || "None"}</dd>
                            </dl>
                            <h3 className="mt-4 text-xs font-semibold uppercase tracking-wide text-muted">
                              Impacts on your products
                            </h3>
                            {o.impacts.length === 0 ? (
                              <p className="text-sm text-muted">None of your products is affected.</p>
                            ) : (
                              <ul className="mt-1 text-sm">
                                {o.impacts.map((impact) => (
                                  <li key={impact.product_id} className="flex flex-wrap items-center gap-2 py-1">
                                    <SeverityLabel severity={impact.severity} />
                                    <span>{impact.product_name}</span>
                                    <span className="text-muted">{impact.reasons.join("; ")}</span>
                                  </li>
                                ))}
                              </ul>
                            )}
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  );
                })}
              </tbody>
            </Table>
          )}
        </>
      ) : null}
    </>
  );
}
