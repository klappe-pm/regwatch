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
import { generateNotice } from "@/lib/generate-notice";
import { premiumView, viewQuery } from "@/lib/premium-view";
import type { Newsletter, Settings } from "@/lib/types";

const PERIODS: [string, string][] = [
  ["7", "Last 7 days"],
  ["14", "Last 14 days"],
  ["30", "Last 30 days"],
  ["90", "Last 90 days"],
];

function NewsletterView({ llmOn }: { llmOn: boolean }) {
  const [since, setSince] = useState("7");
  const [generated, setGenerated] = useState(false);
  const [round, setRound] = useState(0);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const query = viewQuery(`since=${since}`, generated, round);
  const { data, error, loading } = useApi<Newsletter>(`/api/newsletter?${query}`);

  function choose(value: string) {
    setSince(value);
    setGenerated(false);
    setNotice(null);
  }

  async function generate() {
    setBusy(true);
    setNotice("Writing the opening and summaries. This can take a minute.");
    try {
      const result = await postJson<Newsletter>("/api/newsletter/generate", { since: Number(since) });
      setGenerated(true);
      setRound((value) => value + 1);
      setNotice(generateNotice(result));
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : "The copy could not be generated.");
    } finally {
      setBusy(false);
    }
  }

  async function copy(text: string, what: string) {
    try {
      await navigator.clipboard.writeText(text);
      setNotice(`Copied the ${what}.`);
    } catch {
      setNotice(`The ${what} could not be copied; download it instead.`);
    }
  }

  const exportBase = `/api/newsletter/export?${query}`;
  return (
    <>
      <div className="no-print mb-4 flex flex-wrap items-end gap-2">
        <div className="w-full sm:w-56">
          <Field label="Period">
            <Select value={since} onChange={choose} options={PERIODS} />
          </Field>
        </div>
        <Button variant="primary" onClick={generate} disabled={!llmOn || busy}>
          {busy ? "Generating" : "Generate"}
        </Button>
        <Button onClick={() => data && copy(data.html, "HTML")} disabled={!data}>
          <Icon name="content_copy" size={18} />
          Copy HTML
        </Button>
        <Button onClick={() => data && copy(data.text, "text")} disabled={!data}>
          <Icon name="content_copy" size={18} />
          Copy Text
        </Button>
      </div>
      <div className="no-print mb-4 flex flex-wrap items-center gap-2">
        <span className="text-sm text-muted">Download</span>
        <ButtonLink href={`${exportBase}&format=eml`} download>
          <Icon name="download" size={18} />
          Email (.eml)
        </ButtonLink>
        <ButtonLink href={`${exportBase}&format=html`} download>
          <Icon name="download" size={18} />
          HTML
        </ButtonLink>
        <ButtonLink href={`${exportBase}&format=txt`} download>
          <Icon name="download" size={18} />
          Text
        </ButtonLink>
      </div>
      {!llmOn ? (
        <p className="mb-4 text-sm text-muted">
          The opening and summaries are fixed sentences built from your data. Turn on generated copy
          in Settings to have a language model write them.
        </p>
      ) : null}
      <Notice message={notice} />
      {error ? <ErrorNote message={error} /> : null}
      {loading && !data ? <Loading /> : null}
      {data ? (
        <section aria-labelledby="preview-title">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <h2 id="preview-title" className="min-w-0 text-lg font-semibold [overflow-wrap:anywhere]">
              {data.subject}
            </h2>
            {data.generated ? <Tag>Generated</Tag> : null}
          </div>
          <Preview src={`/api/newsletter/preview?${query}`} title="Newsletter preview" />
        </section>
      ) : null}
    </>
  );
}

export default function NewslettersPage() {
  const { status, error } = useStatus();
  const view = premiumView(status, error);
  const settings = useApi<Settings>(view === "open" ? "/api/settings" : null);
  return (
    <>
      <PageHeader
        title="Newsletters"
        description="A send-ready newsletter assembled from the period's changes, as HTML email with a plain text part. Regwatch does not send email; you review it and send it from your own mail tool."
      />
      {view === "loading" ? <Loading /> : null}
      {view === "error" && error ? <ErrorNote message={error} /> : null}
      {view === "locked" ? <Locked feature="Newsletters" /> : null}
      {view === "open" ? <NewsletterView llmOn={Boolean(settings.data?.llm.enabled)} /> : null}
    </>
  );
}
