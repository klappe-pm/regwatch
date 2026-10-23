"use client";

import { useState } from "react";

import { Icon } from "@/components/icon";
import { Button, ButtonLink, ErrorNote, Field, Loading, PageHeader, Select } from "@/components/ui";
import { useApi } from "@/lib/api";
import { TIERS } from "@/lib/labels";
import type { BriefingDocument } from "@/lib/types";

const KINDS: [string, string][] = [
  ["tiered", "Briefing"],
  ["daily", "Daily Brief"],
  ["weekly", "Weekly Synthesis"],
];

function Rendered({ document }: { document: BriefingDocument }) {
  return (
    <article className="border border-line bg-raised px-4 py-6 [overflow-wrap:anywhere] md:px-8">
      <h2 className="text-2xl font-semibold">{document.title}</h2>
      {document.subtitle ? <p className="mt-1 text-muted">{document.subtitle}</p> : null}
      <p className="numeric mt-1 text-sm text-muted">Generated {document.generated}</p>
      {document.sections.map((section, index) => {
        const Heading = section.level >= 3 ? "h4" : "h3";
        return (
          <section key={`${index}-${section.heading}`} className="mt-6 max-w-3xl">
            <Heading
              className={
                section.level >= 3
                  ? "text-base font-semibold"
                  : "border-b border-line pb-1 text-lg font-semibold"
              }
            >
              {section.heading}
            </Heading>
            {section.paragraphs.map((paragraph, i) => (
              <p key={i} className="mt-2">
                {paragraph}
              </p>
            ))}
            {section.bullets.length ? (
              <ul className="mt-2 list-disc pl-6">
                {section.bullets.map((bullet, i) => (
                  <li key={i}>{bullet}</li>
                ))}
              </ul>
            ) : null}
          </section>
        );
      })}
      <p className="mt-8 max-w-3xl border-t border-line pt-4 text-sm text-muted">{document.disclaimer}</p>
    </article>
  );
}

export default function BriefingsPage() {
  const [kind, setKind] = useState("tiered");
  const [tier, setTier] = useState("v2");
  const query = `kind=${kind}&tier=${tier}`;
  const { data, error, loading } = useApi<{ document: BriefingDocument }>(`/api/briefing?${query}`);

  return (
    <>
      <PageHeader
        title="Briefings"
        description="The briefings Regwatch builds from your register, rendered here and ready to export."
        actions={
          <>
            <ButtonLink href={`/api/briefing/export?${query}&format=md`} download>
              <Icon name="download" size={18} />
              Markdown
            </ButtonLink>
            <ButtonLink href={`/api/briefing/export?${query}&format=html`} download>
              <Icon name="download" size={18} />
              HTML
            </ButtonLink>
            <ButtonLink href={`/api/briefing/export?${query}&format=docx`} download>
              <Icon name="download" size={18} />
              Word
            </ButtonLink>
            <Button onClick={() => window.print()}>
              <Icon name="print" size={18} />
              Print or PDF
            </Button>
          </>
        }
      />
      <div className="no-print mb-4 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Briefing">
          <Select value={kind} onChange={setKind} options={KINDS} />
        </Field>
        <Field label="Detail">
          <Select value={tier} onChange={setTier} options={TIERS} disabled={kind !== "tiered"} />
        </Field>
      </div>
      {error ? <ErrorNote message={error} /> : null}
      {loading && !data ? <Loading /> : null}
      {data ? <Rendered document={data.document} /> : null}
    </>
  );
}
