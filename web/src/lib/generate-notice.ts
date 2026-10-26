// The line the Newsletters and Documents pages show after Generate. Kept free of
// React so node --test can check it.

export interface GenerateOutcome {
  dropped: string[];
  notice?: string;
}

/**
 * What to tell the reader after copying the newsletter's HTML or text. The HTML
 * carries its logo as a data address, which mail programs drop from pasted HTML.
 */
export function copyNotice(what: "HTML" | "text", html: string): string {
  if (what === "HTML" && html.includes('src="data:image/')) {
    return "Copied the HTML. A mail program drops the logo from pasted HTML; open the .eml download to keep it.";
  }
  return `Copied the ${what}.`;
}

/**
 * What to tell the reader after a Generate that the server answered. A notice from
 * the server (no request was sent, so the fixed sentences stand) wins over the rest.
 */
export function generateNotice(result: GenerateOutcome): string {
  if (result.notice) return result.notice;
  const left = result.dropped.length;
  if (!left) return "Generated. Check each passage against the facts listed under it.";
  const what = left === 1 ? "One passage was" : `${left} passages were`;
  // Each reason says why: a fact it was not given, a number or link it made up, a
  // section the output does not show, and so on.
  return `Generated. ${what} left out: ${result.dropped.join("; ")}. Check the rest against the facts listed under each.`;
}
