// How the Sources page lays out catalogue entries. Kept free of React and of the
// "@/" path alias so `node --test` can load it directly (web/tests/).

import { t } from "./text.ts";

export interface CatalogueGroup<T> {
  id: string;
  name: string;
  ranked: boolean;
  entries: T[];
}

export const RANKED_GROUP = "best-matches";

/**
 * The groups to show for `entries`, which the server returns already ranked for
 * `query` by the ranking `regwatch sources search` uses.
 *
 * While a search is typed the entries stay one flat list in that order, so the
 * best match is first. Only with an empty search box are they grouped by
 * category, in the order of `categories`; a category the page does not know is
 * listed last under its own id, so no entry is ever dropped.
 */
export function catalogueGroups<T extends { category: string }>(
  entries: T[],
  query: string,
  categories: [string, string][],
): CatalogueGroup<T>[] {
  if (query.trim() !== "") {
    return entries.length
      ? [{ id: RANKED_GROUP, name: t("global.labels.catalogue.best-matches"), ranked: true, entries }]
      : [];
  }
  const known = new Set(categories.map(([id]) => id));
  const extra = [...new Set(entries.map((e) => e.category).filter((c) => !known.has(c)))];
  return [...categories, ...extra.map((id): [string, string] => [id, id])]
    .map(([id, name]) => ({
      id,
      name,
      ranked: false,
      entries: entries.filter((e) => e.category === id),
    }))
    .filter((group) => group.entries.length > 0);
}
