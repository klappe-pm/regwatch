"use client";

import { useEffect, useState } from "react";

import { useStatus } from "@/components/status";
import { Button, EmptyState, ErrorNote, Loading, Locked, PageHeader, Section } from "@/components/ui";
import { postJson, useApi } from "@/lib/api";
import type { Settings } from "@/lib/types";

function FocusAreas({ settings, onSaved }: { settings: Settings; onSaved: (message: string) => void }) {
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

function Premium({ enabled, onSaved }: { enabled: boolean; onSaved: (message: string) => void }) {
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
              <EmptyState>
                The design your documents follow will be set here in a later release: headings,
                colours, typeface and logo.
              </EmptyState>
            ) : (
              <Locked feature="Document design" onSettings />
            )}
          </Section>
          <Section title="Language Model Provider" id="llm">
            {data.premium ? (
              <EmptyState>
                The provider that writes summaries and newsletter copy will be chosen here in a later
                release: Anthropic, OpenAI or a local Ollama model. It stays off until you choose one.
              </EmptyState>
            ) : (
              <Locked feature="Generated copy" onSettings />
            )}
          </Section>
        </>
      ) : null}
    </>
  );
}
