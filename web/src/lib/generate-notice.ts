// The line the Newsletters and Documents pages show after Generate. Kept free of
// React so node --test can check it.

export interface GenerateOutcome {
  dropped: string[];
  notice?: string;
}

/**
 * What to tell the reader after a Generate that the server answered. A notice from
 * the server (no request was sent, so the fixed sentences stand) wins over the rest.
 */
export function generateNotice(result: GenerateOutcome): string {
  if (result.notice) return result.notice;
  return result.dropped.length
    ? `Generated. ${result.dropped.length} passage(s) were left out because they cited facts they were not given.`
    : "Generated. Check each passage against the facts listed under it.";
}
