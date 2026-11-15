// The title a document gets from the design's title format, the same rule as
// DocumentDesign.title in regwatch/config.py. Kept free of React so node --test can
// check it.

import { t } from "./text.ts";

function withoutLeading(title: string, name: string): string {
  if (!title.toLowerCase().startsWith(name.toLowerCase())) return title;
  let rest = title.slice(name.length);
  if (/^[\p{L}\p{N}]/u.test(rest)) return title;
  rest = rest.replace(/^[ .,:;]+/, "");
  return rest ? rest[0].toUpperCase() + rest.slice(1) : title;
}

/**
 * ``format`` filled in with the title, the date and the organisation. When the format
 * names {organisation}, a leading organisation name is taken off the title first, so
 * the organisation is not named twice.
 */
export function designTitle(format: string, title: string, date: string, organisation: string): string {
  const name = organisation.trim();
  const own = name && format.includes("{organisation}") ? withoutLeading(title, name) : title;
  const filled = format
    .replaceAll("{title}", own)
    .replaceAll("{date}", date)
    .replaceAll("{organisation}", organisation)
    .trim();
  return filled || own;
}

/** The title the Settings preview shows: a briefing as the real documents name one. */
export function sampleTitle(format: string, date: string, organisation: string): string {
  const name = organisation.trim() || t("global.labels.design-title.your-organisation");
  const title = t("global.labels.design-title.sample-title", { organisation: name });
  return designTitle(format, title, date, organisation.trim() ? organisation : name);
}
