// The contrast check behind the design specification's colour fields, the same
// WCAG 2.2 formula regwatch.toml is checked with. Kept free of React so node --test
// can check it.

/** True for a colour written #rrggbb. */
export function isHexColor(value: string): boolean {
  return /^#[0-9a-fA-F]{6}$/.test(value);
}

function channel(value: number): number {
  const c = value / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

/** The contrast ratio of #rrggbb against white, from 1 to 21; null for any other text. */
export function contrastWithWhite(value: string): number | null {
  if (!isHexColor(value)) return null;
  const [red, green, blue] = [1, 3, 5].map((i) => parseInt(value.slice(i, i + 2), 16));
  const luminance = 0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue);
  return 1.05 / (luminance + 0.05);
}

/** The text needs 4.5:1 against white to meet WCAG 2.2 AA. */
export const AA_CONTRAST = 4.5;

/** A warning for a colour that is not #rrggbb or is too light for text, or null when it is fine. */
export function colorWarning(label: string, value: string): string | null {
  const ratio = contrastWithWhite(value);
  if (ratio === null) return `${label} must be a colour written #rrggbb.`;
  if (ratio < AA_CONTRAST) {
    return `${label} has a contrast of ${ratio.toFixed(2)}:1 against white; text needs at least ${AA_CONTRAST}:1, so choose a darker colour.`;
  }
  return null;
}
