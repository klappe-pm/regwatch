/** Display names for the values the server sends as identifiers, from the copy documents. */
import { t } from "./text.ts";

const L = "global.labels";

/** A language model provider's own name: Anthropic, OpenAI, Ollama. */
export function providerName(provider: string): string {
  return ["anthropic", "openai", "ollama"].includes(provider) ? t(`${L}.providers.${provider}`) : provider;
}

const pairs = (group: string, ids: string[]): [string, string][] => ids.map((id) => [id, t(`${L}.${group}.${id}`)]);

export const CATEGORIES: [string, string][] = pairs("categories", [
  "regulation",
  "policy-and-lobbying",
  "ingredients-supply",
  "packaging-materials",
  "commodities-and-forecasts",
  "manufacturing-and-chemicals",
  "logistics-and-trade",
  "construction-and-facilities",
  "industry-news",
]);

export const ACCESS: [string, string][] = pairs("access", ["free", "free-key", "paid"]);

export const SEVERITY: Record<string, string> = Object.fromEntries(pairs("severity", ["act-now", "high", "watch", "info"]));

export const TIERS: [string, string][] = pairs("tiers", ["v1", "v2", "v3"]);

export function label(pairs: [string, string][], value: string): string {
  return pairs.find(([id]) => id === value)?.[1] ?? value;
}

/** "north-america" as "North America": every word capitalised, for place names. */
export function place(value: string): string {
  return value
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");
}

/** "free-key" or "act_now" as "Free key": the words of an identifier, capitalised once. */
export function words(value: string): string {
  const text = value.replace(/[-_]+/g, " ").trim();
  return text ? text[0].toUpperCase() + text.slice(1) : "";
}

export function cadence(value: string | null): string {
  if (!value) return t(`${L}.cadence.unknown`);
  return ["hourly", "daily", "weekly"].includes(value) ? t(`${L}.cadence.${value}`) : words(value);
}

/** An ISO time as a short local date and time, or the fallback when there is none. */
export function when(value: string | null | undefined, fallback = t(`${L}.time.not-set`)): string {
  if (!value) return fallback;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

/** What a run's exit status means, in the words `regwatch run` uses. */
export function outcome(code: number | undefined): string {
  if (code === 0) return t(`${L}.outcome.none`);
  if (code === 3) return t(`${L}.outcome.changes`);
  if (code === 4) return t(`${L}.outcome.attention`);
  return code === undefined ? "" : t(`${L}.outcome.exit`, { code });
}
