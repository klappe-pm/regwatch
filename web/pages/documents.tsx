import { T } from "@klappe/design-system";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { useState } from "react";

import { useStatus } from "@/components/status";
import {
  Button,
  ButtonLink,
  ControlRow,
  ErrorNote,
  Field,
  FilterRow,
  Icon,
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
import { TIERS } from "@/lib/labels";
import { premiumView, viewQuery } from "@/lib/premium-view";
import { t } from "@/lib/text";
import type { DesignedDocument, Settings } from "@/lib/types";

const p = (key: string) => t(`pages.documents.${key}`);
const muted = "var(--ds-role-on-surface-variant)";

const KINDS: [string, string][] = ["briefing", "digest", "report"].map((kind) => [kind, p(`kinds.${kind}`)]);
const FORMATS: [string, string][] = [
  ["html", t("global.ui.actions.html")],
  ["docx", t("global.ui.actions.word")],
  ["md", t("global.ui.actions.markdown")],
];

function DocumentView({ llmOn }: { llmOn: boolean }) {
  const [kind, setKind] = useState("briefing");
  const [tier, setTier] = useState("v2");
  const [generated, setGenerated] = useState(false);
  const [round, setRound] = useState(0);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const query = viewQuery(`kind=${kind}&tier=${tier}`, generated, round);
  const { data, error, loading } = useApi<DesignedDocument>(`/api/document?${query}`);

  function reset() {
    setGenerated(false);
    setNotice(null);
  }

  async function generate() {
    setBusy(true);
    setNotice(p("notes.writing"));
    try {
      const result = await postJson<DesignedDocument>("/api/document/generate", { kind, tier });
      setGenerated(true);
      setRound((value) => value + 1);
      setNotice(generateNotice(result));
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : p("notes.failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <FilterRow>
        <Field label={p("controls.document")}>
          <Select
            value={kind}
            onChange={(value) => {
              setKind(value);
              reset();
            }}
            options={KINDS}
          />
        </Field>
        <Field label={p("controls.detail")}>
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
        <Stack direction="row" sx={{ alignItems: "flex-end" }}>
          <Button variant="primary" onClick={generate} disabled={!llmOn || busy}>
            {busy ? p("controls.generating") : p("controls.generate")}
          </Button>
        </Stack>
      </FilterRow>
      <ControlRow>
        <Typography component="span" sx={{ typography: "small", color: muted }}>
          <T k="global.ui.actions.download" />
        </Typography>
        {FORMATS.map(([format, name]) => (
          <ButtonLink key={format} href={`/api/document/export?${query}&format=${format}`} download>
            <Icon name="download" size={18} />
            {name}
          </ButtonLink>
        ))}
      </ControlRow>
      <Typography component="p" sx={{ mb: 4, typography: "small", color: muted }}>
        {p("notes.pdf")}
      </Typography>
      <Notice message={notice} />
      {error ? <ErrorNote message={error} /> : null}
      {loading && !data ? <Loading /> : null}
      {data ? (
        <section aria-labelledby="document-title">
          <Stack direction="row" sx={{ mb: 2, flexWrap: "wrap", alignItems: "center", gap: 2 }}>
            <Typography component="h2" id="document-title" sx={{ minWidth: 0, typography: "section-title", overflowWrap: "anywhere" }}>
              {data.title}
            </Typography>
            {data.generated ? (
              <Tag>
                <T k="global.ui.tag.generated" />
              </Tag>
            ) : null}
          </Stack>
          <Preview src={`/api/document/preview?${query}`} title={p("notes.preview")} />
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
      <PageHeader title={p("header.title")} description={p("header.description")} />
      {view === "loading" ? <Loading /> : null}
      {view === "error" && error ? <ErrorNote message={error} /> : null}
      {view === "locked" ? <Locked feature={p("header.feature")} /> : null}
      {view === "open" ? <DocumentView llmOn={Boolean(settings.data?.llm.enabled)} /> : null}
    </>
  );
}
