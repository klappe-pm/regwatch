// What `ds lint` reports: hardcoded colors and copy in source files. Plain ESM with no Node imports so it can be tested
// and reused; the CLI walks the files and feeds each one in.
//
// A deliberate exception is marked with a comment: `ds-lint-ignore` on the line itself, `ds-lint-ignore-next-line` on
// the line before, or `ds-lint-ignore-file` anywhere in the file.

export const LINT_EXTENSIONS = /\.(tsx|jsx|ts|js|mjs|cjs|css|scss|html|htm)$/

// A hex color: 3, 4, 6 or 8 hex digits, not glued to other identifier characters (#add-rule, #fade-in, #abcdefg).
const HEX = /#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![\w-])/g
const FUNC = /\brgba?\(\s*\d/g

// Places a #token is a link, id or selector rather than a color.
const NOT_COLOR_BEFORE = [
  /\b(?:href|xlink:href|src|action|for|id|name|to|hash|target|aria-[\w-]+)\s*=\s*\{?\s*["'`]?[^"'`\s]*$/i, // href="#add", to={'#top'}
  /(?:querySelector(?:All)?|closest|matches|getElementById|scrollIntoView|\$\$?)\(\s*["'`][^"'`]*$/, // querySelector('#add')
  /(?:location\.)?hash\s*(?:===?|!==?)\s*["'`]$/, // location.hash === '#add'
  /url\(\s*["']?$/, // url(#gradient) in SVG
]
// A hex in a color context: a declaration or property value, an attribute or assignment, a string, a list or call argument.
const COLOR_BEFORE = [/:[^;{}]*$/, /\([^()]*$/, /=\s*\{?\s*["'`]?\s*$/, /["'`]\s*$/, /,\s*$/]
// Followed by `{` before any `;` or quote: a CSS selector (`#fade {`, `a:hover #add {`).
const SELECTOR_AFTER = /^[^;{}"'`]*\{/

export function colorFindings(line) {
  const out = []
  for (const m of line.matchAll(HEX)) {
    const before = line.slice(0, m.index)
    const after = line.slice(m.index + m[0].length)
    if (/[\w&#$/.-]$/.test(before)) continue // foo#abc, &#123;, /page#top, a.#b
    if (NOT_COLOR_BEFORE.some((r) => r.test(before))) continue
    if (!COLOR_BEFORE.some((r) => r.test(before))) continue
    if (SELECTOR_AFTER.test(after)) continue
    out.push(m[0])
  }
  for (const m of line.matchAll(FUNC)) out.push(m[0])
  return out
}

// JSX text between a tag's `>` and the next `<`. The `>` must close a tag (not `=>`, `->`, `>=`, `>>` or a comparison
// with a space before it), and a `<` glued to an identifier (Promise<T>, get<T>(), Array<string>) is a generic, not a tag.
const JSX_TEXT = /(?<=[\w"'}\/\]])>(?![=>])\s*([A-Za-z][^<>{}]*[A-Za-z.!?])(\s*)<(?!=)/g

// Attributes whose string value is visible or announced text.
const COPY_ATTRS = 'aria-label|aria-description|aria-placeholder|aria-roledescription|aria-valuetext|placeholder|title|alt|label'
// attr="text", attr='text', attr={"text"}, attr={'text'}; the attribute name must start the token (not data-title=).
const ATTR_STRING = new RegExp(`(?<![\\w-])(${COPY_ATTRS})=(?:"([^"]*)"|'([^']*)'|\\{\\s*"([^"]*)"\\s*\\}|\\{\\s*'([^']*)'\\s*\\})`, 'g')
// attr={`text ${x}`}
const ATTR_TEMPLATE = new RegExp(`(?<![\\w-])(${COPY_ATTRS})=\\{\\s*\`([^\`]*)\`\\s*\\}`, 'g')
// { 'aria-label': 'Close' } and { "aria-label": "Close" } in slotProps, inputProps and the like.
const ARIA_KEY = /["'](aria-label|aria-description)["']\s*:\s*(?:"([^"]*)"|'([^']*)')/g
// {`Showing ${n} results`} as a JSX child: after a tag's `>`, after another expression's `}`, or opening a line.
const CHILD_TEMPLATE = /(?:^|(?<![=-])>|\})\s*\{\s*`([^`]*)`\s*\}/g

// Text that is not copy: keys (pages.home.title), URLs and paths, ids and class-like tokens (kebab or snake case with no
// spaces), and anything without a word.
function looksLikeCopy(text) {
  const t = text.trim()
  if (!/[A-Za-z]{2,}/.test(t)) return false
  if (/^(?:[a-z][\w-]*)(?:\.[\w-]+)+$/i.test(t)) return false // a copy key or dotted path
  if (/^(?:https?:|mailto:|tel:|\/|\.\/|#)/i.test(t)) return false // URL, path, anchor
  if (/^[a-z0-9]+(?:[-_][a-z0-9]+)*$/.test(t)) return false // lower-case id, key or class name: "email", "close-button"
  if (/^[A-Z0-9_]+$/.test(t) && t.includes('_')) return false // CONSTANT_NAME
  return /\s/.test(t) || /^[A-Z]/.test(t) || /[.!?:]$/.test(t)
}

// The static text of a template literal (its ${} expressions removed) when it reads as copy.
function templateCopy(body) {
  const fixed = body.replace(/\$\{[^}]*\}/g, ' ')
  if (/^(?:https?:|mailto:|\/|#)/.test(body.trim())) return null
  // Two words next to each other, or a capitalized word: "Showing results", "Saved".
  if (!/[A-Za-z]{2,}\s+[A-Za-z]{2,}/.test(fixed) && !/(?:^|\s)[A-Z][a-z]{2,}\b/.test(fixed)) return null
  if (/[{};]|:\s*[\w#-]+\s*;|\b\d+(?:px|rem|em|%)\b/.test(fixed)) return null // CSS, not copy
  return body
}

export function copyFindings(line) {
  const out = []
  for (const m of line.matchAll(JSX_TEXT)) {
    const text = m[1]
    const next = line[m.index + m[0].length] ?? ''
    if (!m[2] && /[\w$]$/.test(text) && next !== '/') continue // generic: Promise<T>, Map<K, V>
    if (/=>|;|\)\s*\{|\bextends\b|\bkeyof\b/.test(text)) continue // a line of code, not copy
    out.push(text.slice(0, 60))
  }
  return out
}

/** Hardcoded copy in string attributes (aria-label, placeholder, title, alt, label) and template literals in JSX. */
export function attributeCopyFindings(line) {
  const out = []
  for (const m of line.matchAll(ATTR_STRING)) {
    const text = m[2] ?? m[3] ?? m[4] ?? m[5] ?? ''
    if (looksLikeCopy(text)) out.push(`${m[1]}="${text.slice(0, 60)}"`)
  }
  for (const m of line.matchAll(ATTR_TEMPLATE)) {
    const text = templateCopy(m[2])
    if (text) out.push(`${m[1]}={\`${text.slice(0, 60)}\`}`)
  }
  for (const m of line.matchAll(ARIA_KEY)) {
    const text = m[2] ?? m[3] ?? ''
    if (looksLikeCopy(text)) out.push(`${m[1]}: "${text.slice(0, 60)}"`)
  }
  for (const m of line.matchAll(CHILD_TEMPLATE)) {
    if (/=>\s*\{\s*`/.test(m[0])) continue
    const text = templateCopy(m[1])
    if (text) out.push(`\`${text.slice(0, 60)}\``)
  }
  return out
}

const COMMENT = /^\s*(\/\/|\*|\/\*|<!--)/
const IGNORE_LINE = /ds-lint-ignore(?!-next-line|-file)\b/
const IGNORE_NEXT = /ds-lint-ignore-next-line\b/
const IGNORE_FILE = /ds-lint-ignore-file\b/

// text: a file's contents; file: its path (the extension decides which checks run).
export function lintSource(text, file) {
  const problems = []
  if (IGNORE_FILE.test(text)) return problems
  const jsx = /\.(tsx|jsx)$/.test(file)
  const lines = text.split('\n')
  lines.forEach((line, i) => {
    if (IGNORE_LINE.test(line) || (i > 0 && IGNORE_NEXT.test(lines[i - 1]))) return
    if (COMMENT.test(line)) return
    for (const c of colorFindings(line)) problems.push({ line: i + 1, kind: 'color', text: c })
    if (jsx) {
      for (const c of copyFindings(line)) problems.push({ line: i + 1, kind: 'copy', text: c })
      for (const c of attributeCopyFindings(line)) problems.push({ line: i + 1, kind: 'copy', text: c })
    }
  })
  return problems
}
