"use client";

import { type FormEvent, type ReactNode, useEffect, useState } from "react";

import { useStatus } from "@/components/status";
import {
  Button,
  CONTROL,
  ErrorNote,
  Field,
  Loading,
  Locked,
  PageHeader,
  Section,
  Select,
} from "@/components/ui";
import { postJson, useApi } from "@/lib/api";
import { colorWarning, contrastWithWhite } from "@/lib/contrast";
import { sampleTitle } from "@/lib/design-title";
import type { DesignSettings, LlmSettings, ProviderKey, Settings } from "@/lib/types";

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

function TextField({
  label,
  value,
  onChange,
  hint,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  hint?: ReactNode;
  placeholder?: string;
}) {
  return (
    <Field label={label}>
      <input
        className={`${CONTROL} w-full`}
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
      {hint ? <span className="text-xs text-muted">{hint}</span> : null}
    </Field>
  );
}

function ColorField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const ratio = contrastWithWhite(value);
  const warning = colorWarning(label, value);
  return (
    <Field label={label}>
      <span className="flex items-center gap-2">
        <input
          type="color"
          aria-label={`${label} picker`}
          className="h-8 w-10 shrink-0 cursor-pointer rounded-sm border border-control bg-raised p-0.5"
          value={ratio === null ? "#000000" : value.toLowerCase()}
          onChange={(event) => onChange(event.target.value)}
        />
        <input
          className={`${CONTROL} w-28 font-mono`}
          value={value}
          spellCheck={false}
          onChange={(event) => onChange(event.target.value)}
        />
        <span className="numeric text-xs text-muted">
          {ratio === null ? "" : `${ratio.toFixed(2)}:1 on white`}
        </span>
      </span>
      {warning ? (
        <span role="alert" className="text-xs text-accent">
          {warning}
        </span>
      ) : null}
    </Field>
  );
}

/** The design specification form, with a live swatch of the colours and the font. */
function DesignForm({ design, onSaved }: { design: DesignSettings; onSaved: Saved }) {
  const [values, setValues] = useState<DesignValues>(designValues(design));
  useEffect(() => setValues(designValues(design)), [design]);
  const changed = DESIGN_FIELDS.some((key) => values[key] !== design[key]);
  const warnings = [
    colorWarning("The primary colour", values.primary_color),
    colorWarning("The accent colour", values.accent_color),
  ].filter(Boolean);

  function set(key: DesignField) {
    return (value: string) => setValues((current) => ({ ...current, [key]: value }));
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    const changes = Object.fromEntries(
      DESIGN_FIELDS.filter((key) => values[key] !== design[key]).map((key) => [key, values[key]]),
    );
    try {
      await postJson("/api/settings/design", { design: changes });
      onSaved("Saved the design specification in regwatch.toml.");
    } catch (reason) {
      onSaved(reason instanceof Error ? reason.message : "The design could not be saved.");
    }
  }

  const today = new Date().toISOString().slice(0, 10);
  const previewTitle = sampleTitle(values.title_format, today, values.organisation);
  const swatchPrimary = warnings.length ? design.primary_color : values.primary_color;
  const swatchAccent = warnings.length ? design.accent_color : values.accent_color;

  return (
    <form onSubmit={save} className="border border-line bg-raised px-4 py-4">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <TextField
            label="Title format"
            value={values.title_format}
            onChange={set("title_format")}
            hint="Use {title}, {date} and {organisation}."
          />
          <TextField label="Organisation" value={values.organisation} onChange={set("organisation")} />
          <ColorField label="Primary colour" value={values.primary_color} onChange={set("primary_color")} />
          <ColorField label="Accent colour" value={values.accent_color} onChange={set("accent_color")} />
          <Field label="Font">
            <Select
              value={values.font}
              onChange={set("font")}
              options={design.fonts.map((font) => [font, font === "system" ? "System" : font])}
            />
          </Field>
          <Field label="Page size">
            <Select
              value={values.page_size}
              onChange={set("page_size")}
              options={design.page_sizes.map((size) => [size, size === "a4" ? "A4" : "Letter"])}
            />
          </Field>
          <TextField
            label="Logo file"
            value={values.logo}
            onChange={set("logo")}
            placeholder="brand/logo.png"
            hint="A PNG or SVG inside the project folder. Email and Word use a PNG only."
          />
          <TextField label="Header line" value={values.header} onChange={set("header")} />
          <TextField label="Footer line" value={values.footer} onChange={set("footer")} />
          <TextField
            label="Newsletter closing line"
            value={values.newsletter_footer}
            onChange={set("newsletter_footer")}
            hint="How to reply or unsubscribe."
          />
        </div>
        <div aria-label="Design preview" className="self-start border border-line bg-white p-4 text-[#17212b]">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[#4b5866]">Preview</p>
          <div style={{ fontFamily: FONT_PREVIEW[values.font] ?? `${values.font}, sans-serif` }}>
            {values.header ? <p className="mb-2 text-xs text-[#4b5866]">{values.header}</p> : null}
            <p
              className="pb-2 text-xl font-semibold leading-tight [overflow-wrap:anywhere]"
              style={{ color: swatchPrimary, borderBottom: `3px solid ${swatchPrimary}` }}
            >
              {previewTitle}
            </p>
            <p
              className="mt-3 pb-1 font-semibold"
              style={{ color: swatchPrimary, borderBottom: `2px solid ${swatchAccent}` }}
            >
              What Changed
            </p>
            <p className="mt-2 text-sm">Two sources changed since the last accepted check.</p>
            {values.footer ? <p className="mt-3 text-xs text-[#4b5866]">{values.footer}</p> : null}
          </div>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button variant="primary" type="submit" disabled={!changed || warnings.length > 0}>
          Save Design
        </Button>
        {warnings.length ? (
          <span className="text-sm text-muted">Fix the colours to save.</span>
        ) : null}
      </div>
    </form>
  );
}

function ProviderKeyRow({ row, onSaved }: { row: ProviderKey; onSaved: Saved }) {
  const [value, setValue] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!value) return;
    const key = value;
    setValue("");
    try {
      await postJson("/api/keys/set", { source_id: row.id, key });
      onSaved(`Stored the ${row.provider} key in the keychain.`);
    } catch (reason) {
      onSaved(reason instanceof Error ? reason.message : "The key could not be stored.");
    }
  }

  async function remove() {
    try {
      await postJson("/api/keys/remove", { source_id: row.id });
      onSaved(`Removed the ${row.provider} key from the keychain.`);
    } catch (reason) {
      onSaved(reason instanceof Error ? reason.message : "The key could not be removed.");
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-line pt-3">
      <span className="min-w-0 text-sm">
        <span className="font-mono">{row.key_env}</span>: {row.where}
      </span>
      <form onSubmit={submit} className="flex flex-wrap items-center gap-2">
        <input
          type="password"
          autoComplete="off"
          spellCheck={false}
          aria-label={`Key for ${row.provider}`}
          placeholder="Paste the key"
          className={`${CONTROL} w-48`}
          value={value}
          onChange={(event) => setValue(event.target.value)}
        />
        <Button type="submit" disabled={!value}>
          {row.present ? "Replace" : "Set"}
        </Button>
      </form>
      {row.where.startsWith("Stored") ? <Button onClick={remove}>Remove</Button> : null}
      {row.signup_url ? (
        <a className="text-sm text-structure underline underline-offset-2" href={row.signup_url} rel="noreferrer" target="_blank">
          Get a key
        </a>
      ) : null}
    </div>
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
      onSaved(reason instanceof Error ? reason.message : "The setting could not be saved.");
    }
  }

  return (
    <div className="border border-line bg-raised px-4 py-4">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
        <div className="max-w-2xl">
          <p id="llm-label" className="font-medium">
            Generated copy
          </p>
          <p className="text-sm text-muted">
            A language model writes the opening and summaries of newsletters and documents from your
            facts only. Every passage is marked Generated and shown with the facts it cites.
          </p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={llm.enabled}
          aria-labelledby="llm-label"
          onClick={() =>
            save({ enabled: !llm.enabled }, llm.enabled ? "Generated copy is off." : "Generated copy is on.")
          }
          className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border transition-colors ${
            llm.enabled ? "border-structure bg-structure" : "border-control bg-surface"
          }`}
        >
          <span
            aria-hidden="true"
            className={`inline-block h-4 w-4 rounded-full transition-transform ${
              llm.enabled ? "translate-x-6 bg-on-structure" : "translate-x-1 bg-control"
            }`}
          />
        </button>
      </div>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void save({ provider, model }, "Saved the provider and the model.");
        }}
        className="mb-3 grid grid-cols-1 items-end gap-3 sm:grid-cols-3"
      >
        <Field label="Provider">
          <Select
            value={provider}
            onChange={setProvider}
            options={llm.providers.map((name) => [
              name,
              name === "anthropic" ? "Anthropic" : name === "openai" ? "OpenAI" : "Ollama (this machine)",
            ])}
          />
        </Field>
        <TextField
          label="Model"
          value={model}
          onChange={setModel}
          placeholder={llm.default_models[provider] ?? ""}
        />
        <div>
          <Button type="submit" disabled={!changed}>
            Save Provider
          </Button>
        </div>
      </form>
      {llm.provider === "ollama" ? (
        <p className="border-t border-line pt-3 text-sm text-muted">
          Ollama runs on this machine at 127.0.0.1:11434 and needs no key. Regwatch reaches that one
          address and no other address on this machine.
        </p>
      ) : key ? (
        <ProviderKeyRow row={key} onSaved={onSaved} />
      ) : null}
    </div>
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
      onSaved("Saved your focus areas in regwatch.toml.");
    } catch (reason) {
      onSaved(reason instanceof Error ? reason.message : "The focus areas could not be saved.");
    }
  }

  return (
    <Section
      title="Focus Areas"
      id="focus"
      actions={
        <Button variant="primary" onClick={save} disabled={!changed}>
          Save Focus Areas
        </Button>
      }
    >
      <p className="mb-2 text-sm text-muted">
        Changes that mention a focus area are listed first. Nothing outside them is hidden.
      </p>
      <fieldset className="border border-line bg-raised">
        <legend className="sr-only">Focus areas</legend>
        {settings.focus_catalogue.map((area) => (
          <label
            key={area.id}
            className="flex cursor-pointer items-start gap-2 border-b border-line px-4 py-2 last:border-b-0 hover:bg-selection"
          >
            <input
              type="checkbox"
              className="mt-1 h-4 w-4 accent-[var(--structure)]"
              checked={chosen.includes(area.id)}
              onChange={() => toggle(area.id)}
            />
            <span>
              <span className="block font-medium">{area.label}</span>
              <span className="block text-sm text-muted">{area.description}</span>
            </span>
          </label>
        ))}
      </fieldset>
    </Section>
  );
}

function Premium({ enabled, onSaved }: { enabled: boolean; onSaved: Saved }) {
  const [busy, setBusy] = useState(false);

  async function flip() {
    setBusy(true);
    try {
      const result = await postJson<{ premium: boolean }>("/api/settings/premium", { enabled: !enabled });
      onSaved(result.premium ? "Premium features are on." : "Premium features are off.");
    } catch (reason) {
      onSaved(reason instanceof Error ? reason.message : "The setting could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section title="Premium Features" id="premium">
      <div className="flex flex-wrap items-center justify-between gap-4 border border-line bg-raised px-4 py-4">
        <div className="max-w-2xl">
          <p id="premium-label" className="font-medium">
            Premium features
          </p>
          <p className="text-sm text-muted">
            Newsletters, document templates, generated copy and runs more often than once a day. Saved
            as <code className="font-mono">[premium] enabled</code> in regwatch.toml.
          </p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          aria-labelledby="premium-label"
          disabled={busy}
          onClick={flip}
          className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border transition-colors disabled:opacity-60 ${
            enabled ? "border-structure bg-structure" : "border-control bg-surface"
          }`}
        >
          <span
            aria-hidden="true"
            className={`inline-block h-4 w-4 rounded-full transition-transform ${
              enabled ? "translate-x-6 bg-on-structure" : "translate-x-1 bg-control"
            }`}
          />
        </button>
      </div>
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
      <PageHeader
        title="Settings"
        description="Settings saved in this project's regwatch.toml. Comments and other settings in the file are kept."
      />
      {notice ? (
        <p role="status" className="mb-4 text-sm">
          {notice}
        </p>
      ) : null}
      {error ? <ErrorNote message={error} /> : null}
      {loading && !data ? <Loading /> : null}
      {data ? (
        <>
          <FocusAreas settings={data} onSaved={saved} />
          <Premium enabled={data.premium} onSaved={saved} />
          <Section title="Document Design" id="design">
            {data.premium ? (
              <DesignForm design={data.design} onSaved={saved} />
            ) : (
              <Locked feature="Document design" onSettings />
            )}
          </Section>
          <Section title="Language Model Provider" id="llm">
            {data.premium ? (
              <LlmForm llm={data.llm} onSaved={saved} />
            ) : (
              <Locked feature="Generated copy" onSettings />
            )}
          </Section>
        </>
      ) : null}
    </>
  );
}
