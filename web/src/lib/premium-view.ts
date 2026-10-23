// What a page behind the premium toggle shows, from the shared status request.
// Kept free of React so node --test can check it.

export type PremiumView = "loading" | "error" | "locked" | "open";

/**
 * The state of a premium page. A failed status request is an error, never
 * "loading", so the page cannot wait forever; a status that did arrive wins
 * over a later failed refresh.
 */
export function premiumView(
  status: { premium: boolean } | null,
  error: string | null,
): PremiumView {
  if (status) return status.premium ? "open" : "locked";
  return error ? "error" : "loading";
}
