import { T } from "@klappe/design-system";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { useState } from "react";

import { useStatus } from "@/components/status";
import { Button, ButtonLink, ControlRow, ErrorNote, Field, Icon, Loading, Locked, Notice, PageHeader, Preview, Select, Tag } from "@/components/ui";
import { postJson, useApi } from "@/lib/api";
import { copyNotice, generateNotice } from "@/lib/generate-notice";
import { premiumView, viewQuery } from "@/lib/premium-view";
import { t } from "@/lib/text";
import type { Newsletter, Settings } from "@/lib/types";

const p = (key: string, vars?: Record<string, string>) => t(`pages.newsletters.${key}`, vars);
const muted = "var(--ds-role-on-surface-variant)";

const PERIODS: [string, string][] = ["7", "14", "30", "90"].map((days) => [days, p(`periods.${days}`)]);

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
    setNotice(p("notes.writing"));
    try {
      const result = await postJson<Newsletter>("/api/newsletter/generate", { since: Number(since) });
      setGenerated(true);
      setRound((value) => value + 1);
      setNotice(generateNotice(result));
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : p("notes.failed"));
    } finally {
      setBusy(false);
    }
  }

  async function copy(text: string, what: "HTML" | "text") {
    try {
      await navigator.clipboard.writeText(text);
      setNotice(copyNotice(what, data?.html ?? ""));
    } catch {
      setNotice(p("notes.copy-failed", { what }));
    }
  }

  const exportBase = `/api/newsletter/export?${query}`;
  return (
    <>
      <ControlRow end>
        <Box sx={{ width: { xs: "100%", sm: "210px" } }}>
          <Field label={p("controls.period")}>
            <Select value={since} onChange={choose} options={PERIODS} />
          </Field>
        </Box>
        <Button variant="primary" onClick={generate} disabled={!llmOn || busy}>
          {busy ? p("controls.generating") : p("controls.generate")}
        </Button>
        <Button onClick={() => data && copy(data.html, "HTML")} disabled={!data}>
          <Icon name="content_copy" size={18} />
          {p("controls.copy-html")}
        </Button>
        <Button onClick={() => data && copy(data.text, "text")} disabled={!data}>
          <Icon name="content_copy" size={18} />
          {p("controls.copy-text")}
        </Button>
      </ControlRow>
      <ControlRow>
        <Typography component="span" sx={{ typography: "small", color: muted }}>
          <T k="global.ui.actions.download" />
        </Typography>
        <ButtonLink href={`${exportBase}&format=eml`} download>
          <Icon name="download" size={18} />
          {p("controls.email")}
        </ButtonLink>
        <ButtonLink href={`${exportBase}&format=html`} download>
          <Icon name="download" size={18} />
          <T k="global.ui.actions.html" />
        </ButtonLink>
        <ButtonLink href={`${exportBase}&format=txt`} download>
          <Icon name="download" size={18} />
          <T k="global.ui.actions.text" />
        </ButtonLink>
      </ControlRow>
      {!llmOn ? (
        <Typography component="p" sx={{ mb: 4, typography: "small", color: muted }}>
          {p("notes.fixed")}
        </Typography>
      ) : null}
      <Notice message={notice} />
      {error ? <ErrorNote message={error} /> : null}
      {loading && !data ? <Loading /> : null}
      {data ? (
        <section aria-labelledby="preview-title">
          <Stack direction="row" sx={{ mb: 2, flexWrap: "wrap", alignItems: "center", gap: 2 }}>
            <Typography component="h2" id="preview-title" sx={{ minWidth: 0, typography: "section-title", overflowWrap: "anywhere" }}>
              {data.subject}
            </Typography>
            {data.generated ? (
              <Tag>
                <T k="global.ui.tag.generated" />
              </Tag>
            ) : null}
          </Stack>
          {data.logo_note ? (
            <Typography component="p" sx={{ mb: 2, typography: "small", color: muted }}>
              {data.logo_note}
            </Typography>
          ) : null}
          <Preview src={`/api/newsletter/preview?${query}`} title={p("notes.preview")} />
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
      <PageHeader title={p("header.title")} description={p("header.description")} />
      {view === "loading" ? <Loading /> : null}
      {view === "error" && error ? <ErrorNote message={error} /> : null}
      {view === "locked" ? <Locked feature={p("header.feature")} /> : null}
      {view === "open" ? <NewsletterView llmOn={Boolean(settings.data?.llm.enabled)} /> : null}
    </>
  );
}
