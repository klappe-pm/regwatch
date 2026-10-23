// The options of the global search in the navigation rail. Kept free of React and of
// the "@/" path alias so `node --test` can load it directly (web/tests/).

import type { SearchResults } from "./types";

export interface SearchOption {
  id: string;
  group: string;
  text: string;
  detail: string;
  href: string;
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
      group: "Sources",
      text: s.name,
      detail: s.mine ? `${s.jurisdiction} · watched` : `${s.jurisdiction} · catalogue`,
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
            group: "Changes",
            text: c.obligation_title,
            detail: `${c.product_name} · ${c.jurisdiction}`,
            href: `/changes/?q=${encodeURIComponent(c.obligation_id)}`,
          }
        : {
            id: `c${i}`,
            group: "Changes",
            text: c.headline,
            detail: `Unconfirmed · ${c.date}`,
            href: `/changes/?q=${encodeURIComponent(c.headline)}`,
          },
    ),
  );
  results.obligations.forEach((o, i) =>
    found.push({
      id: `o${i}`,
      group: "Obligations",
      text: o.title,
      detail: `${o.jurisdiction} · ${o.status}`,
      href: `/obligations/?q=${encodeURIComponent(o.obligation_id)}`,
    }),
  );
  return found;
}

/** The note the search panel shows instead of options, or null when it shows options. */
export function searchNote(query: string, count: number, error: string | null): string | null {
  if (query.trim() === "") return "Type a name, a jurisdiction or a term.";
  if (error) return `The search failed: ${error}`;
  if (count === 0) return "No matches.";
  return null;
}
