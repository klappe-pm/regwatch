// Static exports under a strict Content Security Policy (style-src 'self', script-src 'self'). Plain string functions
// with no Node imports; `ds csp` walks the export and writes the files.

const EMOTION_STYLE = /<style data-emotion="[^"]*"[^>]*>([\s\S]*?)<\/style>/g

/**
 * Replace a page's Emotion <style> elements with one <link rel="stylesheet">, where the first one was. `sheet(css)`
 * receives the page's Emotion CSS, stores it (once per distinct text) and returns the href to link. A page without
 * Emotion styles comes back unchanged.
 */
export function extractEmotionStyles(html, sheet) {
  const css = [...html.matchAll(EMOTION_STYLE)].map((m) => m[1]).join('\n')
  if (!css) return html
  const href = sheet(css)
  let first = true
  return html.replace(EMOTION_STYLE, () => {
    if (!first) return ''
    first = false
    return `<link rel="stylesheet" href="${href}"/>`
  })
}

/** What a strict policy would block in a page: inline <style> elements, style attributes, inline executable scripts. */
export function cspFindings(html) {
  const out = []
  if (/<style[\s>]/.test(html)) out.push('an inline <style> element')
  if (/<[a-z][^>]*\sstyle\s*=/i.test(html)) out.push('a style attribute')
  for (const m of html.matchAll(/<script(?![^>]*\bsrc=)([^>]*)>/g)) {
    if (!/type="application\/(?:ld\+)?json"/.test(m[1])) out.push('an inline executable script')
  }
  return out
}
