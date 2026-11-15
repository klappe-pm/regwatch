// What a page behind the premium toggle shows, from the shared status request.
// Kept free of React so node --test can check it.

export type PremiumView = "loading" | "error" | "locked" | "open";

/**
 * The state of a premium page. A failed status request is an error, never
 * "loading", so the page cannot wait forever; a status that did arrive wins
 * over a later failed refresh.
 */
/**
 * The query a newsletter or document page loads its data and its preview with.
 * ``round`` counts the successful Generate presses: it is part of the query once copy
 * is generated, so a second Generate loads the new copy and the preview frame again
 * even though the rest of the query has not changed.
 */
export function viewQuery(base: string, generated: boolean, round: number): string {
  return generated ? `${base}&generated=1&round=${round}` : base;
}

export function premiumView(
  status: { premium: boolean } | null,
  error: string | null,
): PremiumView {
  if (status) return status.premium ? "open" : "locked";
  return error ? "error" : "loading";
}
