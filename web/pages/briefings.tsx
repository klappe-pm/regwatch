import { T } from "@klappe/design-system";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { useState } from "react";

import { Button, ButtonLink, ErrorNote, Field, FilterRow, Icon, Loading, PageHeader, Piece, Select } from "@/components/ui";
import { useApi } from "@/lib/api";
import { TIERS } from "@/lib/labels";
import { t } from "@/lib/text";
import type { BriefingDocument } from "@/lib/types";

const p = (key: string, vars?: Record<string, string>) => t(`pages.briefings.${key}`, vars);
const muted = "var(--ds-role-on-surface-variant)";

const KINDS: [string, string][] = ["tiered", "daily", "weekly"].map((kind) => [kind, p(`kinds.${kind}`)]);

function Rendered({ document }: { document: BriefingDocument }) {
  return (
    <Piece name="panel" component="article" sx={{ px: { xs: 4, md: 8 }, py: 6, overflowWrap: "anywhere" }}>
      <Typography component="h2" sx={{ fontSize: "24px", lineHeight: "32px", fontWeight: 600 }}>
        {document.title}
      </Typography>
      {document.subtitle ? (
        <Typography component="p" sx={{ mt: 1, color: muted }}>
          {document.subtitle}
        </Typography>
      ) : null}
      <Typography component="p" className="numeric" sx={{ mt: 1, typography: "small", color: muted }}>
        {p("document.generated", { date: document.generated })}
      </Typography>
      {document.sections.map((section, index) => {
        const minor = section.level >= 3;
        return (
          <Box component="section" key={`${index}-${section.heading}`} sx={{ mt: 6, maxWidth: "720px" }}>
            <Typography
              component={minor ? "h4" : "h3"}
              sx={
                minor
                  ? { fontSize: "15px", lineHeight: "24px", fontWeight: 600 }
                  : { borderBottom: "1px solid var(--ds-role-outline-variant)", pb: 1, typography: "section-title" }
              }
            >
              {section.heading}
            </Typography>
            {section.paragraphs.map((paragraph, i) => (
              <Typography component="p" key={i} sx={{ mt: 2 }}>
                {paragraph}
              </Typography>
            ))}
            {section.bullets.length ? (
              <Box component="ul" sx={{ mt: 2, mb: 0, pl: 6 }}>
                {section.bullets.map((bullet, i) => (
                  <li key={i}>{bullet}</li>
                ))}
              </Box>
            ) : null}
          </Box>
        );
      })}
      <Typography component="p" sx={{ mt: 8, maxWidth: "720px", borderTop: "1px solid var(--ds-role-outline-variant)", pt: 4, typography: "small", color: muted }}>
        {document.disclaimer}
      </Typography>
    </Piece>
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
        title={p("header.title")}
        description={p("header.description")}
        actions={
          <>
            <ButtonLink href={`/api/briefing/export?${query}&format=md`} download>
              <Icon name="download" size={18} />
              <T k="global.ui.actions.markdown" />
            </ButtonLink>
            <ButtonLink href={`/api/briefing/export?${query}&format=html`} download>
              <Icon name="download" size={18} />
              <T k="global.ui.actions.html" />
            </ButtonLink>
            <ButtonLink href={`/api/briefing/export?${query}&format=docx`} download>
              <Icon name="download" size={18} />
              <T k="global.ui.actions.word" />
            </ButtonLink>
            <Button onClick={() => window.print()}>
              <Icon name="print" size={18} />
              <T k="global.ui.actions.print" />
            </Button>
          </>
        }
      />
      <FilterRow>
        <Field label={p("filters.briefing")}>
          <Select value={kind} onChange={setKind} options={KINDS} />
        </Field>
        <Field label={p("filters.detail")}>
          <Select value={tier} onChange={setTier} options={TIERS} disabled={kind !== "tiered"} />
        </Field>
      </FilterRow>
      {error ? <ErrorNote message={error} /> : null}
      {loading && !data ? <Loading /> : null}
      {data ? <Rendered document={data.document} /> : null}
    </>
  );
}
