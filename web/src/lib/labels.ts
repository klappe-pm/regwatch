/** Display names for the values the server sends as identifiers. */

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
export function words(value: string): string {
  const text = value.replace(/[-_]+/g, " ").trim();
  return text ? text[0].toUpperCase() + text.slice(1) : "";
}
