"use client";

import Link from "next/link";

import {
  EmptyState,
  ErrorNote,
  Figures,
  Loading,
  PageHeader,
  Section,
  SeverityLabel,
  StatusLabel,
  Table,
  Td,
  Th,
} from "@/components/ui";
import { useApi } from "@/lib/api";
import { CATEGORIES, cadence, label, when } from "@/lib/labels";
import type { Overview } from "@/lib/types";

export default function OverviewPage() {
  const { data, error, loading } = useApi<Overview>("/api/overview");

  return (
    <>
      <PageHeader
        title="Overview"
        description={data ? `Source checks against stored snapshots, as of ${data.generated}.` : undefined}
      />
      {error ? <ErrorNote message={error} /> : null}
      {loading && !data ? <Loading /> : null}
      {data ? (
        <>
          <Figures
            items={[
              { label: "New", value: data.counts.new },
              { label: "Changed", value: data.counts.changed },
              { label: "Suspicious", value: data.counts.suspicious, urgent: data.counts.suspicious > 0 },
              { label: "Failing", value: data.counts.failing, urgent: data.counts.failing > 0 },
              {
                label: "Next Run",
                value: (
                  <span className="text-base font-medium">
                    {data.schedule.installed
                      ? data.schedule.next_run
                        ? when(data.schedule.next_run)
                        : cadence(data.schedule.every)
                      : "Not scheduled"}
                  </span>
                ),
              },
            ]}
          />

          <div className="grid gap-8 xl:grid-cols-2">
            <Section title="Regulatory Changes" id="regulatory">
              {data.priority.length === 0 ? (
                <EmptyState command="regwatch impact">
                  No obligation touches a product in your portfolio yet.
                </EmptyState>
              ) : (
                <Table label="Highest priority changes">
                  <thead>
                    <tr>
                      <Th>Severity</Th>
                      <Th>Obligation</Th>
                      <Th className="hidden sm:table-cell">Product</Th>
                      <Th numeric>Effective</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.priority.map((impact) => (
                      <tr key={`${impact.obligation_id}-${impact.product_id}`}>
                        <Td>
                          <SeverityLabel severity={impact.severity} />
                        </Td>
                        <Td>
                          <Link
                            className="text-ink hover:text-structure hover:underline"
                            href={`/changes/?q=${encodeURIComponent(impact.obligation_id)}`}
                          >
                            {impact.obligation_title}
                          </Link>
                          <span className="block text-xs text-muted">
                            {impact.jurisdiction}
                            <span className="sm:hidden"> · {impact.product_name}</span>
                          </span>
                        </Td>
                        <Td className="hidden sm:table-cell">{impact.product_name}</Td>
                        <Td numeric>{impact.effective_date || "No date"}</Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              )}
            </Section>

            <Section title="Supply Chain" id="supply">
              {data.supply_chain.sources.length === 0 ? (
                <EmptyState command="regwatch sources add">
                  Input cost and packaging sources you watch will appear here with their last status.
                  Choose them on the{" "}
                  <Link className="text-structure underline underline-offset-2" href="/sources/">
                    Sources
                  </Link>{" "}
                  page from the Ingredients Supply, Packaging Materials and Commodities and Forecasts
                  categories.
                </EmptyState>
              ) : (
                <Table label="Supply chain sources">
                  <thead>
                    <tr>
                      <Th>Source</Th>
                      <Th className="hidden sm:table-cell">Category</Th>
                      <Th>Last Status</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.supply_chain.sources.map((source) => (
                      <tr key={source.source_id}>
                        <Td>
                          {source.name}
                          <span className="block text-xs text-muted">
                            {source.jurisdiction}
                            <span className="sm:hidden"> · {label(CATEGORIES, source.category)}</span>
                          </span>
                        </Td>
                        <Td className="hidden sm:table-cell">{label(CATEGORIES, source.category)}</Td>
                        <Td>
                          <StatusLabel status={source.status} />
                        </Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              )}
              <p className="mt-2 text-xs text-muted">Prices and forecasts are not read yet; each source shows whether it changed.</p>
            </Section>
          </div>

          <div className="grid gap-8 xl:grid-cols-2">
            <Section title="Sources Needing Review" id="review">
              {data.flagged.length === 0 ? (
                <EmptyState>
                  All {data.sources} sources match their accepted baseline.
                </EmptyState>
              ) : (
                <Table label="Sources needing review">
                  <thead>
                    <tr>
                      <Th>Source</Th>
                      <Th>Status</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.flagged.map((source) => (
                      <tr key={source.source_id}>
                        <Td>
                          {source.name}
                          {source.detail ? (
                            <span className="block text-xs text-muted">{source.detail}</span>
                          ) : null}
                        </Td>
                        <Td>
                          <StatusLabel status={source.status} />
                        </Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              )}
            </Section>

            <Section title="Effective Within 90 Days" id="upcoming">
              {data.upcoming.length === 0 ? (
                <EmptyState>No obligation takes effect in the next 90 days.</EmptyState>
              ) : (
                <Table label="Obligations effective within 90 days">
                  <thead>
                    <tr>
                      <Th numeric>Date</Th>
                      <Th>Obligation</Th>
                      <Th>Status</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.upcoming.map((item) => (
                      <tr key={item.obligation_id}>
                        <Td numeric>{item.effective_date}</Td>
                        <Td>
                          {item.title}
                          <span className="block text-xs text-muted">{item.jurisdiction}</span>
                        </Td>
                        <Td>{item.status}</Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              )}
            </Section>
          </div>
        </>
      ) : null}
    </>
  );
}
