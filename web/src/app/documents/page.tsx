"use client";

import { useState } from "react";

import { Icon } from "@/components/icon";
import { useStatus } from "@/components/status";
import {
  Button,
  ButtonLink,
  ErrorNote,
  Field,
  Loading,
  Locked,
  Notice,
  PageHeader,
  Preview,
  Select,
  Tag,
} from "@/components/ui";
import { postJson, useApi } from "@/lib/api";
import { TIERS } from "@/lib/labels";
import { premiumView } from "@/lib/premium-view";
import type { DesignedDocument, Settings } from "@/lib/types";

const KINDS: [string, string][] = [
  ["briefing", "Briefing"],
  ["digest", "Register Digest"],
  ["report", "Change and Due Report"],
];

const FORMATS: [string, string][] = [
  ["html", "HTML"],
  ["docx", "Word"],
  ["md", "Markdown"],
];

function DocumentView({ llmOn }: { llmOn: boolean }) {
  const [kind, setKind] = useState("briefing");
  const [tier, setTier] = useState("v2");
  const [generated, setGenerated] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const query = `kind=${kind}&tier=${tier}${generated ? "&generated=1" : ""}`;
  const { data, error, loading } = useApi<DesignedDocument>(`/api/document?${query}`);

  function reset() {
    setGenerated(false);
    setNotice(null);
  }

  async function generate() {
    setBusy(true);
    setNotice("Writing the summary. This can take a minute.");
    try {
      const result = await postJson<DesignedDocument>("/api/document/generate", { kind, tier });
      setGenerated(true);
      setNotice(
        result.dropped.length
          ? `Generated. ${result.dropped.length} passage(s) were left out because they cited facts they were not given.`
          : "Generated. Check each passage against the facts listed under it.",
      );
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : "The summary could not be generated.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="no-print mb-4 grid grid-cols-1 items-end gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Document">
          <Select
            value={kind}
            onChange={(value) => {
              setKind(value);
              reset();
            }}
            options={KINDS}
          />
        </Field>
        <Field label="Detail">
          <Select
            value={tier}
            onChange={(value) => {
              setTier(value);
              reset();
            }}
            options={TIERS}
            disabled={kind !== "briefing"}
          />
        </Field>
        <div>
          <Button variant="primary" onClick={generate} disabled={!llmOn || busy}>
            {busy ? "Generating" : "Generate Summary"}
          </Button>
        </div>
      </div>
      <div className="no-print mb-4 flex flex-wrap items-center gap-2">
        <span className="text-sm text-muted">Download</span>
        {FORMATS.map(([format, label]) => (
          <ButtonLink key={format} href={`/api/document/export?${query}&format=${format}`} download>
            <Icon name="download" size={18} />
            {label}
          </ButtonLink>
        ))}
      </div>
      <p className="mb-4 text-sm text-muted">
        To save a PDF, download the HTML, open it in your browser and print it. The page size comes
        from your design.
      </p>
      <Notice message={notice} />
      {error ? <ErrorNote message={error} /> : null}
      {loading && !data ? <Loading /> : null}
      {data ? (
        <section aria-labelledby="document-title">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <h2 id="document-title" className="min-w-0 text-lg font-semibold [overflow-wrap:anywhere]">
              {data.title}
            </h2>
            {data.generated ? <Tag>Generated</Tag> : null}
          </div>
          <Preview src={`/api/document/preview?${query}`} title="Document preview" />
        </section>
      ) : null}
    </>
  );
}

export default function DocumentsPage() {
  const { status, error } = useStatus();
  const view = premiumView(status, error);
  const settings = useApi<Settings>(view === "open" ? "/api/settings" : null);
  return (
    <>
      <PageHeader
        title="Documents"
        description="Documents built from a template that follows your design specification: headings, colours, typeface and logo, set once in Settings."
      />
      {view === "loading" ? <Loading /> : null}
      {view === "error" && error ? <ErrorNote message={error} /> : null}
      {view === "locked" ? <Locked feature="Documents" /> : null}
      {view === "open" ? <DocumentView llmOn={Boolean(settings.data?.llm.enabled)} /> : null}
    </>
  );
}
