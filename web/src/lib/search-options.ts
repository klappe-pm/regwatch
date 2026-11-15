// The options of the global search in the navigation rail. Kept free of React and of
// the "@/" path alias so `node --test` can load it directly (web/tests/).

import { t } from "./text.ts";
import type { SearchResults } from "./types";

const S = "global.labels.search";

export interface SearchOption {
  id: string;
  group: string;
  text: string;
  detail: string;
  href: string;
}

/** The groups the options fall in, in the order the panel lists them. */
export const SEARCH_GROUPS = ["sources", "changes", "obligations"] as const;

export function searchGroupName(group: string): string {
  return t(`${S}.group-${group}`);
}

/**
 * One option per result. A watched source opens the user's list and a catalogue
 * source opens the catalogue search, both by id, so the link finds that one source
 * even when its name is shared or long.
 */
export function searchOptions(results: SearchResults | null): SearchOption[] {
  if (!results) return [];
  const found: SearchOption[] = [];
  results.sources.forEach((s, i) =>
    found.push({
      id: `s${i}`,
      group: "sources",
      text: s.name,
      detail: t(s.mine ? `${S}.watched` : `${S}.catalogue`, { jurisdiction: s.jurisdiction }),
      href: s.mine
        ? `/sources/?q=${encodeURIComponent(s.source_id)}`
        : `/sources/?catalogue=${encodeURIComponent(s.source_id)}`,
    }),
  );
  results.changes.forEach((c, i) =>
    found.push(
      c.kind === "impact"
        ? {
            id: `c${i}`,
            group: "changes",
            text: c.obligation_title,
            detail: t(`${S}.impact`, { product: c.product_name, jurisdiction: c.jurisdiction }),
            href: `/changes/?q=${encodeURIComponent(c.obligation_id)}`,
          }
        : {
            id: `c${i}`,
            group: "changes",
            text: c.headline,
            detail: t(`${S}.unconfirmed`, { date: c.date }),
            href: `/changes/?q=${encodeURIComponent(c.headline)}`,
          },
    ),
  );
  results.obligations.forEach((o, i) =>
    found.push({
      id: `o${i}`,
      group: "obligations",
      text: o.title,
      detail: t(`${S}.obligation`, { jurisdiction: o.jurisdiction, status: o.status }),
      href: `/obligations/?q=${encodeURIComponent(o.obligation_id)}`,
    }),
  );
  return found;
}

/** The note the search panel shows instead of options, or null when it shows options. */
export function searchNote(query: string, count: number, error: string | null): string | null {
  if (query.trim() === "") return t(`${S}.empty`);
  if (error) return t(`${S}.failed`, { error });
  if (count === 0) return t(`${S}.no-matches`);
  return null;
}
