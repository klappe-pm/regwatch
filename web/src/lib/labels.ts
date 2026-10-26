/** Display names for the values the server sends as identifiers. */

/** A language model provider's own name: Anthropic, OpenAI, Ollama. */
export const PROVIDERS: Record<string, string> = {
  anthropic: "Anthropic",
  openai: "OpenAI",
  ollama: "Ollama",
};

export function providerName(provider: string): string {
  return PROVIDERS[provider] ?? provider;
}

export const CATEGORIES: [string, string][] = [
  ["regulation", "Regulation"],
  ["policy-and-lobbying", "Policy and Lobbying"],
  ["ingredients-supply", "Ingredients Supply"],
  ["packaging-materials", "Packaging Materials"],
  ["commodities-and-forecasts", "Commodities and Forecasts"],
  ["manufacturing-and-chemicals", "Manufacturing and Chemicals"],
  ["logistics-and-trade", "Logistics and Trade"],
  ["construction-and-facilities", "Construction and Facilities"],
  ["industry-news", "Industry News"],
];

export const ACCESS: [string, string][] = [
  ["free", "Free"],
  ["free-key", "Free Key"],
  ["paid", "Paid"],
];

export const SEVERITY: Record<string, string> = {
  "act-now": "Act now",
  high: "High",
  watch: "Watch",
  info: "Info",
};

export const TIERS: [string, string][] = [
  ["v1", "Headlines"],
  ["v2", "Context and Citations"],
  ["v3", "Full Detail"],
];

export function label(pairs: [string, string][], value: string): string {
  return pairs.find(([id]) => id === value)?.[1] ?? value;
}

/** "free-key" or "act_now" as "Free key": the words of an identifier, capitalised once. */
/** "north-america" as "North America": every word capitalised, for place names. */
export function place(value: string): string {
  return value
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");
}

export function words(value: string): string {
  const text = value.replace(/[-_]+/g, " ").trim();
  return text ? text[0].toUpperCase() + text.slice(1) : "";
}

const CADENCE: Record<string, string> = { hourly: "Every hour", daily: "Every day", weekly: "Every week" };

export function cadence(value: string | null): string {
  return value ? (CADENCE[value] ?? words(value)) : "Unknown";
}

/** An ISO time as a short local date and time, or the fallback when there is none. */
export function when(value: string | null | undefined, fallback = "Not set"): string {
  if (!value) return fallback;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

/** What a run's exit status means, in the words `regwatch run` uses. */
export function outcome(code: number | undefined): string {
  if (code === 0) return "No changes";
  if (code === 3) return "Changes to review";
  if (code === 4) return "Needs attention";
  return code === undefined ? "" : `Exit ${code}`;
}
