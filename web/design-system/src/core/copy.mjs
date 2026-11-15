// Copy documents (Markdown with a key per entry) -> a flat { 'doc.key': 'text' } map apps load at build time.
//   # title
//   ## `group`
//   - `key`: The visible text.
const KEY_LINE = /^- `([^`]+)`:(?: (.*))?$/
const HEADING = /^(#{2,6}) `([^`]+)`\s*$/

export function scanDoc(markdown) {
  const out = []
  const stack = [{ level: 1, name: null }]
  for (const line of markdown.split(/\r?\n/)) {
    const h = line.match(HEADING)
    if (h) {
      const level = h[1].length
      while (stack.length && stack[stack.length - 1].level >= level) stack.pop()
      stack.push({ level, name: h[2] })
      continue
    }
    const k = line.match(KEY_LINE)
    if (k) out.push({ key: [...stack.map((s) => s.name).filter(Boolean), k[1]].join('.'), value: k[2] ?? '' })
  }
  return out
}

// The copy runtime without React, for node, server code, plain modules and tests. The React entry builds on it.
// onMissing: 'key' returns the key, 'throw' throws, a function returns its own fallback.
export function createCopy(copy, { onMissing = 'key' } = {}) {
  return (key, vars) => {
    const text = copy[key]
    if (text === undefined) {
      if (onMissing === 'throw') throw new Error(`Missing copy: ${key}`)
      if (typeof onMissing === 'function') return onMissing(key)
      return key
    }
    return vars ? text.replace(/\{(\w+)\}/g, (all, name) => (name in vars ? String(vars[name]) : all)) : text
  }
}

// docs: [{ doc: 'pages/home', markdown }] -> { 'pages.home.title': '...' }, sorted for stable output.
export function copyMap(docs) {
  const map = {}
  for (const { doc, markdown } of docs) for (const e of scanDoc(markdown)) map[`${doc.replace(/\//g, '.')}.${e.key}`] = e.value
  return Object.fromEntries(Object.entries(map).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)))
}
