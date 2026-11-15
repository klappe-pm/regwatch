// ds init: write the starting sources for a project that adopts the design system (DESIGN.md, one copy document and
// ds.config.json), then generate the outputs. Existing files are kept unless `force` is set, so running it again in a
// project that already adopted the package changes nothing. Node only; node.mjs re-exports it.
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join, resolve } from 'node:path'

/** The peer dependencies the React entry needs. The CLI, the core entry and the CSS outputs need none of them. */
export const REACT_PEERS = ['react@^19', 'react-dom@^19', '@mui/material@^9', '@emotion/react@^11', '@emotion/styled@^11', '@emotion/cache@^11']

const yamlString = (s) => JSON.stringify(String(s))

/** The starter DESIGN.md: a light and dark palette from Material 3 roles, type, spacing, radii and one button. */
export function starterDesign(name = 'Project') {
  return `---
name: ${yamlString(name)}
description: "Design tokens for ${String(name).replace(/"/g, '')}. Edit this frontmatter, then run ds sync."
colors:
  ink: "#1b1d1f"
  paper: "#fbfbf9"
  accent: "#2f5d8a"
  accent-soft: "#dce7f2"
  line: "#c9ced3"
roles:
  primary: "{colors.accent}"
  on-primary: "{colors.paper}"
  primary-container: "{colors.accent-soft}"
  on-primary-container: "{colors.ink}"
  surface: "{colors.paper}"
  on-surface: "{colors.ink}"
  outline: "{colors.line}"
rolesDark:
  primary: "#a9c8ec"
  on-primary: "#0f2a44"
  primary-container: "#24476b"
  on-primary-container: "#dce7f2"
  surface: "#131517"
  on-surface: "#e3e5e8"
  outline: "#5b6168"
typography:
  body-medium: { fontFamily: "system-ui, sans-serif", fontSize: "1rem", fontWeight: 400, lineHeight: 1.5 }
  title-large: { fontFamily: "system-ui, sans-serif", fontSize: "1.375rem", fontWeight: 600, lineHeight: 1.3 }
  label-medium: { fontFamily: "system-ui, sans-serif", fontSize: "0.875rem", fontWeight: 500, lineHeight: 1.4 }
spacing:
  unit: "8px"
  small: "8px"
  regular: "16px"
  large: "32px"
rounded:
  small: "4px"
  medium: "8px"
components:
  button-primary:
    material: Button:contained
    label: site.actions.primary
    backgroundColor: "{roles.primary}"
    textColor: "{roles.on-primary}"
    typography: "{typography.label-medium}"
    rounded: "{rounded.medium}"
    padding: "8px 16px"
  button-primary-hover:
    backgroundColor: "{roles.on-primary-container}"
---

# ${String(name)} design

The frontmatter above is the source of every token. \`ds sync\` turns it into \`design/spec.json\`, \`design/ds.css\` (CSS custom properties: \`--ds-role-*\`, \`--ds-color-*\`, \`--ds-font-*\`, \`--ds-space-*\`, \`--ds-radius-*\`) and \`design/tailwind.css\`. Run \`ds check\` in CI so the outputs never go stale.
`
}

/** The starter copy document: `site.md` gives the keys `site.title`, `site.tagline` and `site.actions.primary`. */
export function starterCopy(name = 'Project') {
  return `# site

- \`title\`: ${String(name)}
- \`tagline\`: Describe what this project does in one sentence.

## \`actions\`

- \`primary\`: Get started
`
}

// The lint folders a project already has, or src when it has none of them.
function detectSrc(root) {
  const found = ['src', 'app', 'components', 'pages', 'web'].filter((d) => existsSync(join(root, d)))
  return found.length ? found : ['src']
}

const readJson = (file) => {
  try { return JSON.parse(readFileSync(file, 'utf8')) } catch { return null }
}

/**
 * Write the starting sources into `root`. Returns `{ created, kept, config, scripts }`: the files written, the files
 * left as they were, the ds.config.json content in effect and the package.json scripts added.
 *   name: the project name in DESIGN.md and the copy (default: package.json name, else the folder name).
 *   designFile, cmsDir, out, src: override the defaults (hub.config.json values are used when present).
 *   force: overwrite existing files.
 *   scripts: add design:sync and design:check to package.json when it exists (default true; existing keys are kept).
 */
export function init({ root = process.cwd(), name, designFile, cmsDir, out, src, force = false, scripts = true } = {}) {
  const hub = readJson(join(root, 'hub.config.json')) ?? {}
  const pkgPath = join(root, 'package.json')
  const pkg = existsSync(pkgPath) ? readJson(pkgPath) : null
  const existing = readJson(join(root, 'ds.config.json'))
  const projectName = name ?? pkg?.name?.replace(/^@[^/]+\//, '') ?? (resolve(root).split(/[\\/]/).pop() || 'Project')
  const config = existing && !force
    ? existing
    : {
        designFile: designFile ?? hub.designFile ?? 'DESIGN.md',
        cmsDir: cmsDir ?? hub.cmsDir ?? 'docs/content-management-system',
        out: out ?? 'design',
        src: src ?? hub.src ?? detectSrc(root),
      }
  const effective = { designFile: 'DESIGN.md', cmsDir: '.docs/content-management-system', out: 'design', ...hub, ...config }
  const created = []
  const kept = []
  const put = (rel, text) => {
    const abs = resolve(root, rel)
    if (existsSync(abs) && !force) { kept.push(rel); return }
    mkdirSync(dirname(abs), { recursive: true })
    writeFileSync(abs, text)
    created.push(rel)
  }
  put('ds.config.json', `${JSON.stringify(config, null, 2)}\n`)
  put(effective.designFile, starterDesign(projectName))
  // A copy folder that already holds documents is the project's own; add nothing to it.
  const copyDoc = join(effective.cmsDir, 'site.md')
  if (existsSync(resolve(root, effective.cmsDir)) && !existsSync(resolve(root, copyDoc)) && !force) kept.push(effective.cmsDir)
  else put(copyDoc, starterCopy(projectName))
  const added = []
  if (scripts && pkg && typeof pkg === 'object') {
    pkg.scripts ??= {}
    for (const [k, v] of Object.entries({ 'design:sync': 'ds sync', 'design:check': 'ds check' })) {
      if (pkg.scripts[k] === undefined) { pkg.scripts[k] = v; added.push(k) }
    }
    if (added.length) {
      const indent = readFileSync(pkgPath, 'utf8').match(/^[ \t]+(?=")/m)?.[0] ?? '  '
      writeFileSync(pkgPath, `${JSON.stringify(pkg, null, indent)}\n`)
    }
  }
  return { created, kept, config: effective, scripts: added }
}

/** Peer dependencies of the React entry that `root` cannot resolve. */
export function missingReactPeers(root = process.cwd()) {
  const req = createRequire(join(resolve(root), 'package.json'))
  return REACT_PEERS.filter((spec) => {
    const id = spec.replace(/@[^@/]*$/, '')
    try { req.resolve(`${id}/package.json`); return false } catch { return true }
  })
}

/** The lines `ds init` prints after writing, for a plain CSS project or a React one. */
export function nextSteps({ config, react = false, missingPeers = [] }) {
  const out = config.out ?? 'design'
  const lines = ['', 'Next steps:']
  if (react) {
    if (missingPeers.length) lines.push(`  npm install ${missingPeers.join(' ')}`)
    lines.push(
      `  import spec from './${out}/spec.json'`,
      `  import copy from './${out}/copy.json'`,
      `  import './${out}/ds.css'`,
      "  import { DesignSystemProvider, Part } from '../../dist/index.js'",
      '  <DesignSystemProvider spec={spec} copy={copy}><Part name="button-primary" /></DesignSystemProvider>',
    )
  } else {
    lines.push(
      `  <link rel="stylesheet" href="${out}/ds.css">   (or @import "./${out}/ds.css"; Tailwind v4: @import "./${out}/tailwind.css";)`,
      '  .button { background: var(--ds-role-primary); color: var(--ds-role-on-primary); border-radius: var(--ds-radius-medium); }',
      `  Copy is in ${out}/copy.json as { "site.title": "..." }.`,
    )
  }
  lines.push('  Edit DESIGN.md and the copy documents, run ds sync, and run ds check in CI.')
  return lines
}
