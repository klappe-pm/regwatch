import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { type FormEvent, type ReactNode, useEffect, useState } from "react";

import { useStatus } from "@/components/status";
import { Button, ControlInput, ErrorNote, ExternalLink, Field, Loading, Locked, Notice, PageHeader, Piece, Section, Select } from "@/components/ui";
import { designSpec } from "@/design";
import { postJson, useApi } from "@/lib/api";
import { colorWarning, contrastWithWhite } from "@/lib/contrast";
import { sampleTitle } from "@/lib/design-title";
import { providerName } from "@/lib/labels";
import { t } from "@/lib/text";
import type { DesignSettings, LlmSettings, ProviderKey, Settings } from "@/lib/types";

const p = (key: string, vars?: Record<string, string>) => t(`pages.settings.${key}`, vars);
const muted = "var(--ds-role-on-surface-variant)";

type Saved = (message: string) => void;

const DESIGN_FIELDS = [
  "title_format",
  "organisation",
  "primary_color",
  "accent_color",
  "font",
  "logo",
  "header",
  "footer",
  "page_size",
  "newsletter_footer",
] as const;
type DesignField = (typeof DESIGN_FIELDS)[number];
type DesignValues = Record<DesignField, string>;

const FONT_PREVIEW: Record<string, string> = {
  system: "system-ui, sans-serif",
  Georgia: "Georgia, serif",
  "Times New Roman": "'Times New Roman', serif",
  Garamond: "Garamond, Georgia, serif",
  "Courier New": "'Courier New', monospace",
};

function designValues(design: DesignSettings): DesignValues {
  return Object.fromEntries(DESIGN_FIELDS.map((key) => [key, design[key]])) as DesignValues;
}

function Hint({ children, alert = false }: { children: ReactNode; alert?: boolean }) {
  return (
    <Box component="span" role={alert ? "alert" : undefined} sx={{ typography: "caption", color: alert ? "var(--ds-role-error)" : muted }}>
      {children}
    </Box>
  );
}

function TextField({ label, value, onChange, hint, placeholder }: { label: string; value: string; onChange: (value: string) => void; hint?: ReactNode; placeholder?: string }) {
  return (
    <Field label={label}>
      <ControlInput value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} sx={{ width: "100%" }} />
      {hint ? <Hint>{hint}</Hint> : null}
    </Field>
  );
}

function ColorField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  const ratio = contrastWithWhite(value);
  const warning = colorWarning(label, value);
  return (
    <Field label={label}>
      <Stack direction="row" sx={{ alignItems: "center", gap: 2 }}>
        <ControlInput
          type="color"
          inputProps={{ "aria-label": p("design.picker", { label }) }}
          value={ratio === null ? designSpec.colors.black : value.toLowerCase()}
          onChange={(event) => onChange(event.target.value)}
          sx={{ height: "30px", width: "37.5px", flexShrink: 0, cursor: "pointer", p: "1.875px", "& input": { p: 0, height: "100%", cursor: "pointer" } }}
        />
        <ControlInput
          value={value}
          inputProps={{ spellCheck: false }}
          onChange={(event) => onChange(event.target.value)}
          sx={{ width: "105px", "& input": { typography: "mono", fontSize: "13px" } }}
        />
        <Box component="span" className="numeric" sx={{ typography: "caption", color: muted }}>
          {ratio === null ? "" : p("design.ratio", { ratio: ratio.toFixed(2) })}
        </Box>
      </Stack>
      {warning ? <Hint alert>{warning}</Hint> : null}
    </Field>
  );
}

/** The design specification form, with a live swatch of the colours and the font. */
function DesignForm({ design, onSaved }: { design: DesignSettings; onSaved: Saved }) {
  const [values, setValues] = useState<DesignValues>(designValues(design));
  useEffect(() => setValues(designValues(design)), [design]);
  const changed = DESIGN_FIELDS.some((key) => values[key] !== design[key]);
  const warnings = [colorWarning(p("design.primary-warning"), values.primary_color), colorWarning(p("design.accent-warning"), values.accent_color)].filter(Boolean);

  function set(key: DesignField) {
    return (value: string) => setValues((current) => ({ ...current, [key]: value }));
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    const changes = Object.fromEntries(DESIGN_FIELDS.filter((key) => values[key] !== design[key]).map((key) => [key, values[key]]));
    try {
      await postJson("/api/settings/design", { design: changes });
      onSaved(p("design.saved"));
    } catch (reason) {
      onSaved(reason instanceof Error ? reason.message : p("design.failed"));
    }
  }

  const today = new Date().toISOString().slice(0, 10);
  const previewTitle = sampleTitle(values.title_format, today, values.organisation);
  const swatchPrimary = warnings.length ? design.primary_color : values.primary_color;
  const swatchAccent = warnings.length ? design.accent_color : values.accent_color;
  const documentMuted = "var(--ds-color-muted)";

  return (
    <Piece name="panel" component="form" onSubmit={save} sx={{ p: 4 }}>
      <Box sx={{ display: "grid", gap: 4, gridTemplateColumns: { xs: "minmax(0, 1fr)", lg: "minmax(0, 1fr) minmax(0, 330px)" } }}>
        <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "minmax(0, 1fr)", sm: "repeat(2, minmax(0, 1fr))" } }}>
          <TextField label={p("design.title-format")} value={values.title_format} onChange={set("title_format")} hint={p("design.title-format-hint")} />
          <TextField label={p("design.organisation")} value={values.organisation} onChange={set("organisation")} />
          <ColorField label={p("design.primary-color")} value={values.primary_color} onChange={set("primary_color")} />
          <ColorField label={p("design.accent-color")} value={values.accent_color} onChange={set("accent_color")} />
          <Field label={p("design.font")}>
            <Select value={values.font} onChange={set("font")} options={design.fonts.map((font) => [font, font === "system" ? p("design.system-font") : font])} />
          </Field>
          <Field label={p("design.page-size")}>
            <Select value={values.page_size} onChange={set("page_size")} options={design.page_sizes.map((size) => [size, size === "a4" ? p("design.a4") : p("design.letter")])} />
          </Field>
          <TextField label={p("design.logo")} value={values.logo} onChange={set("logo")} placeholder={p("design.logo-placeholder")} hint={p("design.logo-hint")} />
          <TextField label={p("design.header-line")} value={values.header} onChange={set("header")} />
          <TextField label={p("design.footer-line")} value={values.footer} onChange={set("footer")} />
          <TextField label={p("design.newsletter-footer")} value={values.newsletter_footer} onChange={set("newsletter_footer")} hint={p("design.newsletter-footer-hint")} />
        </Box>
        <Piece name="document-preview" aria-label={p("design.preview")} sx={{ alignSelf: "start" }}>
          <Typography component="p" sx={{ mb: 2, typography: "overline", color: documentMuted }}>
            {p("design.preview-label")}
          </Typography>
          <Box sx={{ fontFamily: FONT_PREVIEW[values.font] ?? `${values.font}, sans-serif` }}>
            {values.header ? (
              <Box component="p" sx={{ m: 0, mb: 2, fontSize: "12px", lineHeight: "16px", color: documentMuted }}>
                {values.header}
              </Box>
            ) : null}
            <Box
              component="p"
              sx={{ m: 0, pb: 2, fontSize: "20px", fontWeight: 600, lineHeight: 1.25, overflowWrap: "anywhere", color: swatchPrimary, borderBottom: `3px solid ${swatchPrimary}` }}
            >
              {previewTitle}
            </Box>
            <Box component="p" sx={{ m: 0, mt: 3, pb: 1, fontWeight: 600, color: swatchPrimary, borderBottom: `2px solid ${swatchAccent}` }}>
              {p("design.preview-heading")}
            </Box>
            <Box component="p" sx={{ m: 0, mt: 2, fontSize: "13px", lineHeight: "20px" }}>
              {p("design.preview-body")}
            </Box>
            {values.footer ? (
              <Box component="p" sx={{ m: 0, mt: 3, fontSize: "12px", lineHeight: "16px", color: documentMuted }}>
                {values.footer}
              </Box>
            ) : null}
          </Box>
        </Piece>
      </Box>
      <Stack direction="row" sx={{ mt: 4, flexWrap: "wrap", alignItems: "center", gap: 2 }}>
        <Button variant="primary" type="submit" disabled={!changed || warnings.length > 0}>
          {p("design.save")}
        </Button>
        {warnings.length ? (
          <Typography component="span" sx={{ typography: "small", color: muted }}>
            {p("design.fix-colours")}
          </Typography>
        ) : null}
      </Stack>
    </Piece>
  );
}

function ProviderKeyRow({ row, onSaved }: { row: ProviderKey; onSaved: Saved }) {
  const [value, setValue] = useState("");
  const provider = providerName(row.provider);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!value) return;
    const key = value;
    setValue("");
    try {
      await postJson("/api/keys/set", { source_id: row.id, key });
      onSaved(p("llm.stored", { provider }));
    } catch (reason) {
      onSaved(reason instanceof Error ? reason.message : p("llm.store-failed"));
    }
  }

  async function remove() {
    try {
      await postJson("/api/keys/remove", { source_id: row.id });
      onSaved(p("llm.removed", { provider }));
    } catch (reason) {
      onSaved(reason instanceof Error ? reason.message : p("llm.remove-failed"));
    }
  }

  return (
    <Stack direction="row" sx={{ flexWrap: "wrap", alignItems: "center", gap: 2, borderTop: "1px solid var(--ds-role-outline-variant)", pt: 3 }}>
      <Typography component="span" sx={{ minWidth: 0, typography: "small" }}>
        <Box component="span" sx={{ typography: "mono", fontSize: "13px" }}>
          {row.key_env}
        </Box>
        : {row.where}
      </Typography>
      <Box component="form" onSubmit={submit} sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 2 }}>
        <ControlInput
          type="password"
          autoComplete="off"
          inputProps={{ spellCheck: false, "aria-label": p("llm.key-for", { provider }) }}
          placeholder={p("llm.paste")}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          sx={{ width: "180px" }}
        />
        <Button type="submit" disabled={!value}>
          {row.present ? p("llm.replace") : p("llm.set")}
        </Button>
      </Box>
      {row.where.startsWith("Stored") ? <Button onClick={remove}>{p("llm.remove")}</Button> : null}
      {row.signup_url ? <ExternalLink href={row.signup_url}>{p("llm.get-key")}</ExternalLink> : null}
    </Stack>
  );
}

/** An on and off switch, labelled by the text beside it. */
function Toggle({ checked, labelledBy, disabled = false, onChange }: { checked: boolean; labelledBy: string; disabled?: boolean; onChange: () => void }) {
  return (
    <Piece
      name="switch"
      unlabeled
      size="small"
      checked={checked}
      disabled={disabled}
      onChange={onChange}
      slotProps={{ input: { role: "switch", "aria-labelledby": labelledBy } }}
      sx={{ flexShrink: 0 }}
    />
  );
}

/** The language model provider form: on or off, the provider, the model and its key. */
function LlmForm({ llm, onSaved }: { llm: LlmSettings; onSaved: Saved }) {
  const [provider, setProvider] = useState(llm.provider);
  const [model, setModel] = useState(llm.model);
  useEffect(() => {
    setProvider(llm.provider);
    setModel(llm.model);
  }, [llm]);
  const changed = provider !== llm.provider || model !== llm.model;
  const key = llm.keys.find((row) => row.provider === llm.provider);

  async function save(body: Record<string, unknown>, message: string) {
    try {
      await postJson("/api/settings/llm", body);
      onSaved(message);
    } catch (reason) {
      onSaved(reason instanceof Error ? reason.message : p("llm.failed"));
    }
  }

  return (
    <Piece name="panel" sx={{ p: 4 }}>
      <Stack direction="row" sx={{ mb: 4, flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 4 }}>
        <Box sx={{ maxWidth: "640px" }}>
          <Typography component="p" id="llm-label" sx={{ fontWeight: 500 }}>
            {p("llm.label")}
          </Typography>
          <Typography component="p" sx={{ typography: "small", color: muted }}>
            {p("llm.intro")}
          </Typography>
        </Box>
        <Toggle checked={llm.enabled} labelledBy="llm-label" onChange={() => save({ enabled: !llm.enabled }, llm.enabled ? p("llm.off") : p("llm.on"))} />
      </Stack>
      <Box
        component="form"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          void save({ provider, model }, p("llm.saved"));
        }}
        sx={{ mb: 3, display: "grid", alignItems: "end", gap: 3, gridTemplateColumns: { xs: "minmax(0, 1fr)", sm: "repeat(3, minmax(0, 1fr))" } }}
      >
        <Field label={p("llm.provider")}>
          <Select
            value={provider}
            onChange={setProvider}
            options={llm.providers.map((name) => [name, name === "ollama" ? t("global.labels.providers.ollama-local") : providerName(name)])}
          />
        </Field>
        <TextField label={p("llm.model")} value={model} onChange={setModel} placeholder={llm.default_models[provider] ?? ""} />
        <div>
          <Button type="submit" disabled={!changed}>
            {p("llm.save")}
          </Button>
        </div>
      </Box>
      {llm.provider === "ollama" ? (
        <Typography component="p" sx={{ borderTop: "1px solid var(--ds-role-outline-variant)", pt: 3, typography: "small", color: muted }}>
          {p("llm.ollama")}
        </Typography>
      ) : key ? (
        <ProviderKeyRow row={key} onSaved={onSaved} />
      ) : null}
    </Piece>
  );
}

function FocusAreas({ settings, onSaved }: { settings: Settings; onSaved: Saved }) {
  const [chosen, setChosen] = useState<string[]>(settings.focus_areas);
  useEffect(() => setChosen(settings.focus_areas), [settings.focus_areas]);
  const changed = chosen.join(",") !== settings.focus_areas.join(",");

  function toggle(id: string) {
    setChosen((value) => (value.includes(id) ? value.filter((v) => v !== id) : [...value, id]));
  }

  async function save() {
    try {
      const ordered = settings.focus_catalogue.map((a) => a.id).filter((id) => chosen.includes(id));
      await postJson("/api/settings/focus", { focus_areas: ordered });
      onSaved(p("focus.saved"));
    } catch (reason) {
      onSaved(reason instanceof Error ? reason.message : p("focus.failed"));
    }
  }

  return (
    <Section
      title={p("focus.title")}
      id="focus"
      actions={
        <Button variant="primary" onClick={save} disabled={!changed}>
          {p("focus.save")}
        </Button>
      }
    >
      <Typography component="p" sx={{ mb: 2, typography: "small", color: muted }}>
        {p("focus.intro")}
      </Typography>
      <Piece name="panel" component="fieldset" sx={{ m: 0, p: 0, minWidth: 0 }}>
        <Box component="legend" sx={{ position: "absolute", width: "1px", height: "1px", overflow: "hidden", clip: "rect(0,0,0,0)" }}>
          {p("focus.legend")}
        </Box>
        {settings.focus_catalogue.map((area) => (
          <Box
            component="label"
            key={area.id}
            sx={{
              display: "flex",
              cursor: "pointer",
              alignItems: "flex-start",
              gap: 2,
              borderBottom: "1px solid var(--ds-role-outline-variant)",
              px: 4,
              py: 2,
              "&:last-of-type": { borderBottom: 0 },
              "&:hover": { bgcolor: "var(--ds-role-secondary-container)" },
            }}
          >
            <Box
              component="input"
              type="checkbox"
              checked={chosen.includes(area.id)}
              onChange={() => toggle(area.id)}
              sx={{ m: 0, mt: 1, width: "15px", height: "15px", flexShrink: 0, accentColor: "var(--ds-role-primary)" }}
            />
            <span>
              <Box component="span" sx={{ display: "block", fontWeight: 500 }}>
                {area.label}
              </Box>
              <Box component="span" sx={{ display: "block", typography: "small", color: muted }}>
                {area.description}
              </Box>
            </span>
          </Box>
        ))}
      </Piece>
    </Section>
  );
}

function Premium({ enabled, onSaved }: { enabled: boolean; onSaved: Saved }) {
  const [busy, setBusy] = useState(false);

  async function flip() {
    setBusy(true);
    try {
      const result = await postJson<{ premium: boolean }>("/api/settings/premium", { enabled: !enabled });
      onSaved(result.premium ? p("premium.on") : p("premium.off"));
    } catch (reason) {
      onSaved(reason instanceof Error ? reason.message : p("premium.failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section title={p("premium.title")} id="premium">
      <Piece name="panel" sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 4, p: 4 }}>
        <Box sx={{ maxWidth: "640px" }}>
          <Typography component="p" id="premium-label" sx={{ fontWeight: 500 }}>
            {p("premium.label")}
          </Typography>
          <Typography component="p" sx={{ typography: "small", color: muted }}>
            {p("premium.intro")}{" "}
            <Box component="code" sx={{ typography: "mono", fontSize: "13px" }}>
              {p("premium.setting")}
            </Box>{" "}
            {p("premium.intro-after")}
          </Typography>
        </Box>
        <Toggle checked={enabled} labelledBy="premium-label" disabled={busy} onChange={flip} />
      </Piece>
    </Section>
  );
}

export default function SettingsPage() {
  const { data, error, loading, reload } = useApi<Settings>("/api/settings");
  const { refresh } = useStatus();
  const [notice, setNotice] = useState<string | null>(null);

  function saved(message: string) {
    setNotice(message);
    reload();
    refresh();
  }

  return (
    <>
      <PageHeader title={p("header.title")} description={p("header.description")} />
      <Notice message={notice} />
      {error ? <ErrorNote message={error} /> : null}
      {loading && !data ? <Loading /> : null}
      {data ? (
        <>
          <FocusAreas settings={data} onSaved={saved} />
          <Premium enabled={data.premium} onSaved={saved} />
          <Section title={p("design.title")} id="design">
            {data.premium ? <DesignForm design={data.design} onSaved={saved} /> : <Locked feature={p("design.feature")} onSettings />}
          </Section>
          <Section title={p("llm.title")} id="llm">
            {data.premium ? <LlmForm llm={data.llm} onSaved={saved} /> : <Locked feature={p("llm.feature")} onSettings />}
          </Section>
        </>
      ) : null}
    </>
  );
}
