// DESIGN.md frontmatter -> the design spec every output is generated from (spec.json, CSS variables, Tailwind theme, MUI theme).
// Plain ESM with no Node imports: the CLI, the hub and browsers all use it.

export const M3_ROLES = [
  'primary', 'on-primary', 'primary-container', 'on-primary-container',
  'secondary', 'on-secondary', 'secondary-container', 'on-secondary-container',
  'tertiary', 'on-tertiary', 'tertiary-container', 'on-tertiary-container',
  'error', 'on-error', 'error-container', 'on-error-container',
  'background', 'on-background',
  'surface', 'on-surface', 'surface-variant', 'on-surface-variant',
  'surface-container-lowest', 'surface-container-low', 'surface-container', 'surface-container-high', 'surface-container-highest',
  'outline', 'outline-variant', 'inverse-surface', 'inverse-on-surface', 'inverse-primary', 'scrim', 'shadow',
]

// Material UI component a DESIGN.md component renders as, unless it names one with `material:`.
export function guessMaterial(name) {
  const n = name.toLowerCase()
  if (/button|cta/.test(n)) return /outline/.test(n) ? 'Button:outlined' : /text|ghost/.test(n) ? 'Button:text' : 'Button:contained'
  if (/link/.test(n)) return 'Link'
  if (/input|field|textarea/.test(n)) return 'TextField:outlined'
  if (/tab/.test(n)) return 'Tab'
  if (/chip|tag|pill|badge/.test(n)) return 'Chip'
  if (/checkbox/.test(n)) return 'Checkbox'
  if (/switch|toggle/.test(n)) return 'Switch'
  if (/footer|header|app-?bar|nav-?bar/.test(n)) return 'AppBar'
  if (/card|document|panel|finding|art/.test(n)) return 'Card'
  if (/list|row|item/.test(n)) return 'ListItemButton'
  return 'none'
}

const STATE = /-(hover|active|focus|selected|disabled|pressed)$/

// Component keys that describe a component rather than style it. They never reach CSS.
export const COMPONENT_META_KEYS = ['material', 'label', 'selector', 'scope', 'material-default', 'materialDefault', 'color-refs', 'colorRefs', 'modifier', 'description', 'note', 'notes']

// A nested rule inside a component: a selector relative to the component (`& .label`, `&:first-of-type`, `.label`,
// `> li`) or an at-rule (`@media (max-width: 600px)`, `@container`, `@supports`). Material UI's sx takes them as is.
const NESTED_KEY = /^(?:&|@media\b|@container\b|@supports\b|:|\[|\.|>|\+|~|\*)/
export const isNestedRule = (key) => NESTED_KEY.test(String(key).trim()) || String(key).includes('&')
const plainObject = (v) => Boolean(v) && typeof v === 'object' && !Array.isArray(v)

// A modifier (`modifier: true`, for example a size variant like `button-small`) is combined with a base part. It gets no
// disabled defaults and never becomes the global look of its Material UI component.
const isModifier = (props) => props?.modifier === true || String(props?.modifier ?? '').toLowerCase() === 'true'

// A component keeps its fixed colors (no role variables) with `color-refs: value`; one reference does with `{colors.x!}`.
// A state component (`-hover`) follows its base unless it says otherwise.
const colorRefsOf = (props) => props?.['color-refs'] ?? props?.colorRefs
const fixedColors = (components, name) => {
  const own = colorRefsOf(components[name])
  const base = STATE.test(name) ? colorRefsOf(components[name.replace(STATE, '')]) : undefined
  return String(own ?? base ?? '').toLowerCase() === 'value'
}
const FIXED_REF = /\{((?:colors|roles)\.[^}!]+)!\}/g

// A component styles every instance of its Material UI component (theme styleOverrides) only when it opts in with
// `scope: global` or `material-default: true`. Otherwise it styles only what renders through Part or componentSx.
const isGlobal = (props) => {
  const flag = props['material-default'] ?? props.materialDefault
  return String(props.scope ?? '').toLowerCase() === 'global' || flag === true || String(flag).toLowerCase() === 'true'
}

// Which Material role a component property should follow when its color maps to several roles.
const ROLE_PREFERENCE = {
  text: ['on-surface', 'on-background', 'on-surface-variant', 'on-primary', 'on-primary-container', 'on-secondary', 'on-secondary-container', 'on-tertiary', 'on-tertiary-container', 'on-error', 'on-error-container', 'inverse-on-surface'],
  border: ['outline', 'outline-variant'],
  fill: ['surface', 'background', 'primary', 'secondary', 'tertiary', 'error', 'primary-container', 'secondary-container', 'tertiary-container', 'error-container', 'surface-variant', 'surface-container-lowest', 'surface-container-low', 'surface-container', 'surface-container-high', 'surface-container-highest', 'inverse-surface', 'inverse-primary'],
}
const propKind = (prop) => {
  if (/border|outline|stroke|divider|rule/i.test(prop)) return 'border'
  if (/background|fill|^bg/i.test(prop)) return 'fill'
  if (/^(color|textColor|caretColor|accentColor|textDecorationColor)$/.test(prop)) return 'text'
  return 'fill'
}

// Resolve {group.name} references; a reference to a group (typography.body) resolves to an object.
function resolver(front) {
  const get = (path) => path.split('.').reduce((n, k) => (n && typeof n === 'object' ? n[k] : undefined), front)
  const resolve = (value, seen = new Set()) => {
    if (typeof value !== 'string') return value
    const whole = value.match(/^\{([^}]+)\}$/)
    if (whole) {
      if (seen.has(whole[1])) return value
      const hit = get(whole[1])
      if (hit === undefined) return value
      if (hit && typeof hit === 'object') return Object.fromEntries(Object.entries(hit).map(([k, v]) => [k, resolve(v, new Set([...seen, whole[1]]))]))
      return resolve(String(hit), new Set([...seen, whole[1]]))
    }
    return value.replace(/\{([^}]+)\}/g, (all, p) => {
      const hit = get(p)
      return hit === undefined || typeof hit === 'object' ? all : String(resolve(String(hit), new Set([...seen, p])))
    })
  }
  return resolve
}

const mapValues = (o, f) => Object.fromEntries(Object.entries(o || {}).map(([k, v]) => [k, f(v, k)]))

// Prefixes of custom properties the host page defines (Obsidian's --background-primary, --text-normal and so on).
// They are kept as written and never reported.
const hostMatcher = (prefixes) => {
  const list = (Array.isArray(prefixes) ? prefixes : prefixes ? [prefixes] : []).map((p) => String(p).trim()).filter(Boolean).map((p) => (p.startsWith('--') ? p : `--${p}`))
  return (name) => list.some((p) => name.startsWith(p))
}

/**
 * @param {Record<string, any>} front  parsed DESIGN.md frontmatter
 * @param {{ cssVars?: Map<string,string>, colorRefs?: 'var' | 'value', spacingUnit?: string | number, hostVariables?: string[] }} [opts]
 *   cssVars: custom properties found in the project's CSS, to resolve var() aliases.
 *   colorRefs: 'var' (default) writes component color references as var(--ds-role-*) so they follow dark mode;
 *   'value' writes the resolved value.
 *   spacingUnit: the theme spacing unit (a length or a spacing token name), overriding DESIGN.md spacing.unit.
 *   hostVariables: prefixes of custom properties the host page defines; var() references to them are kept as written.
 *
 * A var() with a fallback (`var(--x, #fff)`) is kept as written: it is a runtime reference, not an alias to resolve.
 * A var() without one resolves from cssVars, unless it names a host variable.
 */
export function buildSpec(front, opts = {}) {
  const vars = opts.cssVars ?? new Map()
  const colorRefs = opts.colorRefs ?? 'var'
  const isHost = hostMatcher(opts.hostVariables)
  const unvar = (v, seen = new Set()) => (typeof v === 'string'
    ? v.replace(/var\((--[a-zA-Z0-9-]+)(?:\s*,\s*([^)]+))?\)/g, (all, n, fb) => {
      if (seen.has(n) || fb !== undefined || isHost(n)) return all
      const hit = vars.get(n)
      return hit ? unvar(hit, new Set([...seen, n])) : all
    })
    : v)
  const resolve = resolver(front)
  const value = (v) => {
    const r = resolve(v)
    return r && typeof r === 'object' ? mapValues(r, (x) => unvar(x)) : unvar(r)
  }
  const colors = mapValues(front.colors, (v) => String(value(v)))
  const pickRoles = (src) => {
    if (src && typeof src === 'object') return mapValues(src, (v) => String(value(v)))
    return Object.fromEntries(Object.entries(colors).filter(([k]) => M3_ROLES.includes(k)))
  }
  const typography = mapValues(front.typography, (t) => mapValues(t, (v) => (typeof v === 'number' ? v : String(value(v)))))
  const roles = pickRoles(front.roles)

  // {colors.x} and {roles.x} in a component become var(--ds-role-*) (or var(--ds-color-*)) with the value as fallback,
  // so component styles follow the color scheme. A color follows the role that DESIGN.md maps to it.
  const rolesOfColor = new Map()
  if (front.roles && typeof front.roles === 'object') {
    for (const [role, ref] of Object.entries(front.roles)) {
      const m = typeof ref === 'string' && ref.match(/^\{colors\.([^}]+)\}$/)
      if (m) rolesOfColor.set(m[1], [...(rolesOfColor.get(m[1]) ?? []), role])
    }
  } else for (const k of Object.keys(roles)) rolesOfColor.set(k, [k])
  const colorVar = (group, name, prop) => {
    if (group === 'roles') return roles[name] !== undefined ? `var(--ds-role-${kebab(name)}, ${roles[name]})` : null
    if (colors[name] === undefined) return null
    const candidates = rolesOfColor.get(name) ?? []
    const role = ROLE_PREFERENCE[propKind(prop)].find((r) => candidates.includes(r)) ?? candidates.find((r) => !r.startsWith('on-')) ?? candidates[0]
    return role ? `var(--ds-role-${kebab(role)}, ${colors[name]})` : `var(--ds-color-${kebab(name)}, ${colors[name]})`
  }
  const styleValue = (v, prop, fixed = false) => {
    if (typeof v !== 'string') return value(v)
    if (colorRefs !== 'var' || fixed) return value(v.replace(FIXED_REF, '{$1}'))
    const held = []
    const marked = v.replace(/\{(colors|roles)\.([^}]+)\}/g, (all, group, rawName) => {
      // {colors.x!}: the fixed value, never a role variable.
      const pinned = rawName.endsWith('!')
      const name = pinned ? rawName.slice(0, -1) : rawName
      const out = pinned ? value(`{${group}.${name}}`) : colorVar(group, name, prop)
      if (pinned && out === `{${group}.${name}}`) return all
      if (!out) return all
      held.push(out)
      return `\u0000${held.length - 1}\u0000`
    })
    if (!held.length) return value(v)
    return String(value(marked)).replace(/\u0000(\d+)\u0000/g, (all, i) => held[Number(i)])
  }

  // Style keys of one component, with nested rules (`& .label`, `@media (...)`) kept as nested objects. Objects that
  // are not nested rules (other than an inline typography style) are left out here and reported by specErrors.
  const styleOf = (props, fixed, top) => {
    const raw = {}
    const style = {}
    for (const [k, v] of Object.entries(props || {})) {
      if (top && COMPONENT_META_KEYS.includes(k)) continue
      if (plainObject(v)) {
        if (isNestedRule(k)) {
          const inner = styleOf(v, fixed, false)
          raw[k] = inner.raw
          style[k] = inner.style
        } else if (k === 'typography') {
          raw[k] = mapValues(v, (x) => String(x))
          style[k] = mapValues(v, (x) => (typeof x === 'number' ? x : String(value(x))))
        }
        continue
      }
      if (Array.isArray(v) || v === null || v === undefined) continue
      raw[k] = String(v)
      style[k] = styleValue(String(v), k, fixed)
    }
    return { raw, style }
  }

  const components = {}
  for (const [name, props] of Object.entries(front.components || {})) {
    const meta = mapValues(Object.fromEntries(Object.entries(props || {}).filter(([k, v]) => COMPONENT_META_KEYS.includes(k) && !plainObject(v))), (v) => String(v))
    const { raw, style } = styleOf(props, fixedColors(front.components, name), true)
    components[name] = {
      material: meta.material || guessMaterial(name.replace(STATE, '')),
      label: meta.label || null,
      selector: meta.selector || null,
      global: isGlobal(props || {}),
      ...(isModifier(props) ? { modifier: true } : {}),
      state: name.match(STATE)?.[1] ?? null,
      base: STATE.test(name) ? name.replace(STATE, '') : null,
      raw,
      style,
    }
  }

  // The theme spacing unit: the config's spacingUnit, else DESIGN.md spacing.unit (a length or the name of another
  // spacing token). Without either the theme uses spacing.base, then 8px. A name is looked up among every spacing
  // token, `unit` included, before `unit` is left out of the emitted tokens, so `spacingUnit: "unit"` works.
  const allSpacing = mapValues(front.spacing, (v) => String(value(v)))
  const { unit: _unit, ...spacing } = allSpacing
  const unitRaw = opts.spacingUnit ?? front.spacing?.unit
  let spacingUnit = null
  if (unitRaw !== undefined && unitRaw !== null && unitRaw !== '') {
    let u = typeof unitRaw === 'number' ? `${unitRaw}px` : String(value(unitRaw))
    const seen = new Set()
    while (Object.hasOwn(allSpacing, u) && !seen.has(u)) {
      seen.add(u)
      u = allSpacing[u]
    }
    spacingUnit = u
  }
  return {
    $schema: 'design-spec/1',
    name: front.name ?? null,
    description: front.description ?? null,
    roles,
    rolesDark: front.rolesDark ? pickRoles(front.rolesDark) : null,
    colors,
    typography,
    spacing,
    spacingUnit,
    rounded: mapValues(front.rounded, (v) => String(value(v))),
    components,
  }
}

// What a project's spec still lacks before the shared components can theme it properly. A var() with a fallback, and
// a var() naming a host variable (opts.hostVariables prefixes), is intentional and not reported.
export function specWarnings(spec, front, opts = {}) {
  const w = []
  const isHost = hostMatcher(opts.hostVariables)
  for (const role of ['primary', 'on-primary', 'surface', 'on-surface']) if (!spec.roles[role]) w.push(`No ${role} role. Add roles.${role} to DESIGN.md (for example "{colors.pine}").`)
  const alias = (text) => [...String(text).matchAll(/var\((--[a-zA-Z0-9-]+)\s*(,)?/g)].some((m) => !m[2] && !isHost(m[1]))
  const scan = (o, path) => {
    for (const [k, v] of Object.entries(o || {})) {
      if (v && typeof v === 'object') scan(v, `${path}.${k}`)
      else if (alias(v)) w.push(`${path}.${k} is a var() alias. Write the value itself so every app gets it, add a fallback (var(--x, value)), or list its prefix in ds.config.json hostVariables when the host page defines it.`)
    }
  }
  for (const g of ['colors', 'roles', 'typography', 'spacing', 'rounded']) scan(front[g], g)
  return w
}

// Problems that make DESIGN.md components unusable, for `ds check` and `ds sync` to fail on: objects that are not nested
// rules, nested rules that are malformed, and values that would end a CSS rule early.
export function specErrors(front) {
  const errors = []
  const BREAKS = /[{};]|\/\*|<\//
  const scanRule = (props, path, depth) => {
    for (const [k, v] of Object.entries(props || {})) {
      const at = `${path}.${k}`
      if (depth === 0 && COMPONENT_META_KEYS.includes(k)) {
        if (plainObject(v) || Array.isArray(v)) errors.push(`${at} must be a single value.`)
        continue
      }
      if (depth > 0 && COMPONENT_META_KEYS.includes(k) && !['note', 'notes', 'description'].includes(k)) errors.push(`${at}: ${k} describes a component and only works at its top level, not inside a nested rule.`)
      if (Array.isArray(v)) { errors.push(`${at} is a list; style values are single values.`); continue }
      if (plainObject(v)) {
        if (k === 'typography' && depth === 0) continue
        if (!isNestedRule(k)) { errors.push(`${at} is an object. Nested rules start with &, :, ., [, >, @media, @container or @supports (for example "& .label" or "@media (max-width: 600px)").`); continue }
        if (/[{};]/.test(k)) errors.push(`${at}: the selector may not contain {, } or ;.`)
        if (/^@(media|container|supports)\s*$/.test(k.trim())) errors.push(`${at}: the at-rule needs a condition, for example "@media (max-width: 600px)".`)
        else if (/^@(media|supports)\b/.test(k.trim()) && !/\(.+\)/.test(k)) errors.push(`${at}: write the condition in parentheses, for example "@media (max-width: 600px)".`)
        if (depth >= 3) { errors.push(`${at} nests more than three rules deep.`); continue }
        if (!Object.keys(v).length) errors.push(`${at} is an empty rule.`)
        scanRule(v, at, depth + 1)
        continue
      }
      // References ({colors.x}) are braces too; take them out before looking for characters that would break the rule.
      if (BREAKS.test(String(v ?? '').replace(/\{[^{}]+\}/g, ''))) errors.push(`${at} contains {, }, ; or a comment, which would end the CSS rule early.`)
    }
  }
  for (const [name, props] of Object.entries(front?.components || {})) {
    if (!plainObject(props)) { errors.push(`components.${name} must be a map of style keys.`); continue }
    scanRule(props, `components.${name}`, 0)
  }
  return errors
}

// ---- outputs -------------------------------------------------------------------------------------

const kebab = (s) => String(s).replace(/([a-z0-9])([A-Z])/g, '$1-$2').replace(/[^a-zA-Z0-9]+/g, '-').toLowerCase()
const TYPE_PROPS = { fontFamily: 'family', fontSize: 'size', fontWeight: 'weight', lineHeight: 'line-height', letterSpacing: 'letter-spacing' }
const HEADER = (what) => `/* Generated from DESIGN.md (${what}) by web/design-system. Edit DESIGN.md, then run ds sync. */\n`

/**
 * Where the token variables and their dark roles apply.
 *   selector: the element the tokens are defined on (default :root).
 *   colorSchemeTarget: 'self' (default) when the color-scheme attribute is on that element, 'ancestor' when it is on
 *     an element around it (the page root, for a scoped preview).
 *   attribute: the color-scheme attribute (default data-theme), or a selector with %s for the scheme name.
 */
function darkSelectors({ selector = ':root', colorSchemeTarget = 'self', attribute = 'data-theme' } = {}) {
  if (attribute.includes('%s')) return { dark: attribute.replace(/%s/g, 'dark'), media: null }
  const on = (scheme) => `[${attribute}='${scheme}']`
  if (selector === ':root') return { dark: on('dark'), media: `:root:not(${on('light')})` }
  if (colorSchemeTarget === 'ancestor') return { dark: `${on('dark')} ${selector}`, media: `:root:not(${on('light')}) ${selector}` }
  return { dark: `${selector}${on('dark')}`, media: `${selector}:not(${on('light')})` }
}

// Every token as a CSS custom property: --ds-color-*, --ds-role-*, --ds-font-<style>-*, --ds-space-*, --ds-radius-*.
// opts: { selector, colorSchemeTarget, attribute } (see darkSelectors); without them the tokens go on :root.
export function cssVariables(spec, opts = {}) {
  const lines = []
  for (const [k, v] of Object.entries(spec.colors)) lines.push(`  --ds-color-${kebab(k)}: ${v};`)
  for (const [k, v] of Object.entries(spec.roles)) lines.push(`  --ds-role-${kebab(k)}: ${v};`)
  for (const [name, t] of Object.entries(spec.typography)) {
    for (const [p, v] of Object.entries(t)) if (TYPE_PROPS[p]) lines.push(`  --ds-font-${kebab(name)}-${TYPE_PROPS[p]}: ${v};`)
  }
  for (const [k, v] of Object.entries(spec.spacing)) lines.push(`  --ds-space-${kebab(k)}: ${v};`)
  for (const [k, v] of Object.entries(spec.rounded)) lines.push(`  --ds-radius-${kebab(k)}: ${v};`)
  const root = opts.selector ?? ':root'
  let css = `${HEADER('tokens')}${root} {\n${lines.join('\n')}\n}\n`
  if (spec.rolesDark) {
    const dark = Object.entries(spec.rolesDark).map(([k, v]) => `  --ds-role-${kebab(k)}: ${v};`).join('\n')
    const sel = darkSelectors(opts)
    if (sel.media) css += `\n@media (prefers-color-scheme: dark) {\n  ${sel.media} {\n${dark.replace(/^/gm, '  ')}\n  }\n}\n`
    css += `\n${sel.dark} {\n${dark}\n}\n`
  }
  return css
}

// Tailwind v4 theme that points at the CSS variables, so utilities (bg-primary, text-display, p-regular) follow the tokens.
export function tailwindTheme(spec) {
  const lines = []
  for (const k of Object.keys(spec.roles)) lines.push(`  --color-${kebab(k)}: var(--ds-role-${kebab(k)});`)
  for (const k of Object.keys(spec.colors)) if (!(k in spec.roles)) lines.push(`  --color-${kebab(k)}: var(--ds-color-${kebab(k)});`)
  for (const [name, t] of Object.entries(spec.typography)) {
    const n = kebab(name)
    if (t.fontFamily) lines.push(`  --font-${n}: var(--ds-font-${n}-family);`)
    if (t.fontSize) {
      lines.push(`  --text-${n}: var(--ds-font-${n}-size);`)
      if (t.lineHeight) lines.push(`  --text-${n}--line-height: var(--ds-font-${n}-line-height);`)
      if (t.letterSpacing) lines.push(`  --text-${n}--letter-spacing: var(--ds-font-${n}-letter-spacing);`)
      if (t.fontWeight) lines.push(`  --text-${n}--font-weight: var(--ds-font-${n}-weight);`)
    }
  }
  for (const k of Object.keys(spec.spacing)) lines.push(`  --spacing-${kebab(k)}: var(--ds-space-${kebab(k)});`)
  for (const k of Object.keys(spec.rounded)) lines.push(`  --radius-${kebab(k)}: var(--ds-radius-${kebab(k)});`)
  return `${HEADER('Tailwind theme')}@theme inline {\n${lines.join('\n')}\n}\n`
}
