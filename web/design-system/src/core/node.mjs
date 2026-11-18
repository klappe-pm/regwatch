// The ds commands as a library: read a project's config, build its outputs, write or check them, lint its sources and
// prepare a static export for a strict Content Security Policy. Node only (fs, child_process), so it lives in its own
// entry, 'regwatch-design/node'; the core entry stays free of Node imports because browsers load it.
// bin/ds.mjs is a thin wrapper around run().
//
// Config: ds.config.json in the project root, falling back to hub.config.json for designFile, cmsDir and src:
//   { "designFile": "DESIGN.md", "cmsDir": ".docs/content-management-system", "out": "design", "src": ["src", "app"],
//     "ignore": ["src/legacy"], "spacingUnit": "base", "hostVariables": ["--background-", "--text-"],
//     "files": { "spec": "design/spec.json", "css": "design/ds.css", "tailwind": "design/tailwind.css", "copy": "design/copy.json" },
//     "colorSchemeAttribute": "data-theme" }
// `src` entries are folders or files. `spacingUnit` names the theme spacing unit (a length or a spacing token name).
// `ignore` lists paths (relative to the project root) that are never read, for linting or for CSS custom properties.
// `hostVariables` lists prefixes of custom properties the host page defines; var() references to them are kept as
// written and never reported. `files` sets the path of each output (default: <out>/<name>).
// Build output folders (out, .next, dist, build, site, coverage) and whatever git ignores are skipped as well.
import { spawnSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { dirname, join, relative, resolve, sep } from 'node:path'
import YAML from 'yaml'
import { buildSpec, cssVariables, specErrors, specWarnings, tailwindTheme } from './spec.mjs'
import { copyMap } from './copy.mjs'
import { cspFindings, extractEmotionStyles } from './csp.mjs'
import { LINT_EXTENSIONS, lintSource } from './lint.mjs'
import { adapterFreshness, adapterMatrix } from './adapters.mjs'
import { init, missingReactPeers, nextSteps } from './init.mjs'

export { REACT_PEERS, init, missingReactPeers, nextSteps, starterCopy, starterDesign } from './init.mjs'

/** This package's own package.json (name, version, dependency pins). */
export function packageInfo() {
  return JSON.parse(readFileSync(new URL('../../package.json', import.meta.url), 'utf8'))
}

/**
 * The adapter matrix with freshness problems: certified evidence files that are missing from the package checkout
 * are reported too, when the test folder is present (it is not shipped in the tarball).
 */
export function adapters() {
  const pkg = packageInfo()
  const matrix = adapterMatrix(pkg)
  const problems = adapterFreshness(pkg)
  const testDir = new URL('../../test/', import.meta.url)
  if (existsSync(testDir)) {
    for (const a of matrix.adapters) for (const f of a.evidence) if (!existsSync(new URL(`../../${f}`, import.meta.url))) problems.push(`${a.id}: evidence ${f} does not exist`)
  }
  return { ...matrix, problems }
}

/** The output files ds writes, by kind, with their default names inside `out`. */
export const OUTPUT_FILES = { spec: 'spec.json', css: 'ds.css', tailwind: 'tailwind.css', copy: 'copy.json' }

const toPosix = (p) => p.split(sep).join('/')

/**
 * The project's ds config: ds.config.json, with designFile, cmsDir and src falling back to hub.config.json.
 * `overrides` (for example from command line flags) win over both.
 */
export function loadConfig(root = process.cwd(), overrides = {}) {
  const read = (f) => (existsSync(join(root, f)) ? JSON.parse(readFileSync(join(root, f), 'utf8')) : null)
  const ds = read('ds.config.json') ?? {}
  const hub = read('hub.config.json') ?? {}
  const cfg = {
    designFile: ds.designFile ?? hub.designFile ?? 'DESIGN.md',
    cmsDir: ds.cmsDir ?? hub.cmsDir ?? '.docs/content-management-system',
    out: ds.out ?? 'design',
    src: ds.src ?? hub.src ?? ['src', 'app', 'components'],
    ignore: ds.ignore ?? [],
    spacingUnit: ds.spacingUnit,
    hostVariables: ds.hostVariables ?? [],
    files: { ...(ds.files ?? {}) },
    colorSchemeAttribute: ds.colorSchemeAttribute,
  }
  for (const [k, v] of Object.entries(overrides)) {
    if (v === undefined) continue
    if (k === 'files') cfg.files = { ...cfg.files, ...v }
    else cfg[k] = v
  }
  return cfg
}

/** Where each output goes, relative to the root: `files.<kind>` when set, else `<out>/<default name>`. */
export function outputPaths(cfg) {
  const paths = {}
  for (const [kind, name] of Object.entries(OUTPUT_FILES)) {
    const set = cfg.files?.[kind]
    paths[kind] = set ? String(set) : join(cfg.out, name)
  }
  return paths
}

const BUILD_DIRS = /^(node_modules|\.next|\.vercel|dist|build|site|\.git|out|coverage|test-results|local)$/

// dir may also be a single file: it is included when it passes the test.
function walk(dir, test, out = []) {
  if (!existsSync(dir)) return out
  if (!statSync(dir).isDirectory()) {
    if (test(dir)) out.push(dir)
    return out
  }
  for (const name of readdirSync(dir)) {
    if (BUILD_DIRS.test(name)) continue
    const p = join(dir, name)
    if (statSync(p).isDirectory()) walk(p, test, out)
    else if (test(p)) out.push(p)
  }
  return out
}

// Paths git ignores under the project root (folders end in /), or none outside a git checkout.
function gitIgnored(root) {
  const r = spawnSync('git', ['ls-files', '--others', '--ignored', '--exclude-standard', '--directory', '-z'], { cwd: root, encoding: 'utf8' })
  return r.status === 0 ? r.stdout.split('\0').filter(Boolean) : []
}

// True when a file is an output, in the out folder, an `ignore` entry or a git-ignored path.
function skipper(root, cfg) {
  const strip = (p) => toPosix(p).replace(/^\.\//, '').replace(/\/+$/, '')
  const prefixes = [cfg.out, ...Object.values(outputPaths(cfg)), ...cfg.ignore, ...gitIgnored(root)].map(strip).filter(Boolean)
  return (file) => {
    const rel = toPosix(relative(root, file))
    return prefixes.some((p) => rel === p || rel.startsWith(`${p}/`))
  }
}

// Custom properties defined in the project's own CSS, so var() aliases in DESIGN.md resolve while a project migrates.
function cssVars(root, cfg) {
  const vars = new Map()
  const skip = skipper(root, cfg)
  for (const f of cfg.src.flatMap((dir) => walk(resolve(root, dir), (p) => p.endsWith('.css') && !skip(p)))) {
    for (const m of readFileSync(f, 'utf8').matchAll(/(--[a-zA-Z0-9-]+)\s*:\s*([^;}]+)[;}]/g)) if (!vars.has(m[1])) vars.set(m[1], m[2].trim())
  }
  return vars
}

/**
 * The generated files for a project, without writing them: `{ files: { 'design/spec.json': text, ... }, warnings,
 * errors }`. Keys are paths relative to the root. Errors (malformed DESIGN.md components) mean the outputs must not be
 * written.
 */
export function outputs({ root = process.cwd(), config } = {}) {
  const cfg = config ?? loadConfig(root)
  const paths = outputPaths(cfg)
  const files = {}
  const warnings = []
  const errors = []
  const designPath = resolve(root, cfg.designFile)
  if (existsSync(designPath)) {
    const fm = readFileSync(designPath, 'utf8').match(/^---\r?\n([\s\S]*?)\r?\n---/)
    if (!fm) warnings.push(`${cfg.designFile} has no YAML frontmatter, so there are no tokens to generate.`)
    else {
      const front = YAML.parse(fm[1]) ?? {}
      errors.push(...specErrors(front).map((e) => `${cfg.designFile}: ${e}`))
      const spec = buildSpec(front, { cssVars: cssVars(root, cfg), hostVariables: cfg.hostVariables, ...(cfg.spacingUnit !== undefined ? { spacingUnit: cfg.spacingUnit } : {}) })
      warnings.push(...specWarnings(spec, front, { hostVariables: cfg.hostVariables }))
      files[paths.spec] = `${JSON.stringify(spec, null, 2)}\n`
      files[paths.css] = cssVariables(spec, cfg.colorSchemeAttribute ? { attribute: cfg.colorSchemeAttribute } : {})
      files[paths.tailwind] = tailwindTheme(spec)
    }
  } else warnings.push(`No ${cfg.designFile}; tokens are not generated.`)
  const cms = resolve(root, cfg.cmsDir)
  if (existsSync(cms)) {
    const docs = walk(cms, (p) => p.endsWith('.md')).map((p) => ({ doc: toPosix(relative(cms, p)).replace(/\.md$/, ''), markdown: readFileSync(p, 'utf8') }))
    files[paths.copy] = `${JSON.stringify(copyMap(docs), null, 2)}\n`
  } else warnings.push(`No copy documents at ${cfg.cmsDir}.`)
  return { files, warnings, errors }
}

/** The outputs whose file is missing or differs from what ds would write. */
export function staleOutputs(root, files) {
  return Object.entries(files).filter(([rel, text]) => !existsSync(resolve(root, rel)) || readFileSync(resolve(root, rel), 'utf8') !== text).map(([rel]) => rel)
}

/** Write the outputs that changed. Nothing is written when DESIGN.md has errors. */
export function sync({ root = process.cwd(), config } = {}) {
  const { files, warnings, errors } = outputs({ root, config })
  if (errors.length) return { written: [], warnings, errors, files }
  const written = staleOutputs(root, files)
  for (const rel of written) {
    mkdirSync(dirname(resolve(root, rel)), { recursive: true })
    writeFileSync(resolve(root, rel), files[rel])
  }
  return { written, warnings, errors, files }
}

/** Compare the outputs on disk with what ds would write. `ok` is false when one is stale or DESIGN.md has errors. */
export function check({ root = process.cwd(), config } = {}) {
  const { files, warnings, errors } = outputs({ root, config })
  const stale = staleOutputs(root, files)
  return { ok: !stale.length && !errors.length, stale, warnings, errors, files }
}

/** Hardcoded colors and copy in the `src` files: `[{ file, line, kind, text }]`. Test files are skipped. */
export function lint({ root = process.cwd(), config } = {}) {
  const cfg = config ?? loadConfig(root)
  const problems = []
  const srcList = Array.isArray(cfg.src) ? cfg.src : [cfg.src]
  const skip = skipper(root, cfg)
  const files = [...new Set(srcList.flatMap((d) => walk(join(root, d), (p) => LINT_EXTENSIONS.test(p))))]
  for (const f of files) {
    const rel = relative(root, f)
    if (skip(f) || /\.(test|spec)\./.test(rel)) continue
    for (const p of lintSource(readFileSync(f, 'utf8'), f)) problems.push({ file: rel, ...p })
  }
  return problems
}

/**
 * A static export under a strict policy (style-src 'self', script-src 'self'): every page's Emotion styles go into one
 * style sheet file per distinct set, linked where the first <style> element was. Returns the pages, the sheets written
 * and what the policy would still block.
 */
export function csp({ root = process.cwd(), dir = 'out', cssDir = join('_next', 'static', 'css') } = {}) {
  const out = resolve(root, dir)
  if (!existsSync(out)) return { missing: true, pages: 0, sheets: 0, problems: [`no ${dir} folder; build the export first`] }
  const css = join(out, cssDir)
  mkdirSync(css, { recursive: true })
  const href = `/${toPosix(cssDir).replace(/^\/+|\/+$/g, '')}/`
  const pages = []
  const pageWalk = (d) => {
    for (const name of readdirSync(d)) {
      const p = join(d, name)
      if (statSync(p).isDirectory()) pageWalk(p)
      else if (name.endsWith('.html')) pages.push(p)
    }
  }
  pageWalk(out)
  const sheets = new Set()
  const problems = []
  for (const page of pages) {
    let html = readFileSync(page, 'utf8')
    const extracted = extractEmotionStyles(html, (text) => {
      const name = `emotion-${createHash('sha256').update(text).digest('hex').slice(0, 16)}.css`
      if (!sheets.has(name)) { writeFileSync(join(css, name), `${text}\n`); sheets.add(name) }
      return `${href}${name}`
    })
    if (extracted !== html) writeFileSync(page, (html = extracted))
    for (const f of cspFindings(html)) problems.push(`${relative(out, page)}: ${f}`)
  }
  return { missing: false, pages: pages.length, sheets: sheets.size, problems }
}

// --name=value or --name value. Returns the value and the arguments left.
function takeFlag(args, name) {
  const i = args.findIndex((a) => a === `--${name}` || a.startsWith(`--${name}=`))
  if (i < 0) return [undefined, args]
  const a = args[i]
  if (a.includes('=')) return [a.slice(a.indexOf('=') + 1), [...args.slice(0, i), ...args.slice(i + 1)]]
  const v = args[i + 1]
  if (v === undefined || v.startsWith('--')) throw new Error(`--${name} needs a value`)
  return [v, [...args.slice(0, i), ...args.slice(i + 2)]]
}

/** Output paths from command line flags: --out <dir>, --spec, --css, --tailwind and --copy <file>. */
export function outputFlags(args) {
  let rest = args
  const overrides = {}
  let v
  ;[v, rest] = takeFlag(rest, 'out')
  if (v !== undefined) overrides.out = v
  const files = {}
  for (const kind of Object.keys(OUTPUT_FILES)) {
    ;[v, rest] = takeFlag(rest, kind)
    if (v !== undefined) files[kind] = v
  }
  if (Object.keys(files).length) overrides.files = files
  return { overrides, rest }
}

export const USAGE = [
  'usage: ds <command> [options]',
  '  ds init [--react] [--force] [--name <name>] [--no-scripts] [--no-sync]',
  '              write a starter DESIGN.md, copy document and ds.config.json, then ds sync',
  '  ds sync     write the outputs (design/spec.json, ds.css, tailwind.css, copy.json)',
  '  ds diff     list outputs that would change',
  '  ds check    fail when an output is stale or DESIGN.md has errors',
  '  ds lint [--strict]                       report hardcoded colors and copy in src',
  '  ds csp [dir] [--css-dir=_next/static/css]  move a static export\'s Emotion styles into files',
  '  ds adapters [--check]                   print the adapter capability matrix as JSON; --check fails when it is stale',
  '  ds version                               print the package version',
  'output options (sync, diff, check): --out <dir>, --spec <file>, --css <file>, --tailwind <file>, --copy <file>',
].join('\n')

/**
 * Run one ds command, as the CLI does, and return its exit code. `io.log` and `io.error` receive the output lines.
 */
export function run(argv = [], { root = process.cwd(), log = console.log, error = console.error } = {}) {
  const [cmd = 'help', ...args] = argv
  try {
    switch (cmd) {
      case 'init': {
        let rest = args
        const opts = {}
        for (const k of ['name', 'design', 'cms', 'out']) {
          let v
          ;[v, rest] = takeFlag(rest, k)
          if (v !== undefined) opts[k === 'design' ? 'designFile' : k === 'cms' ? 'cmsDir' : k] = v
        }
        const react = rest.includes('--react')
        const r = init({ root, ...opts, force: rest.includes('--force'), scripts: !rest.includes('--no-scripts') })
        for (const f of r.created) log(`created ${f}`)
        for (const f of r.kept) log(`kept ${f} (already there; --force overwrites)`)
        for (const k of r.scripts) log(`added package.json script ${k}`)
        if (!rest.includes('--no-sync')) {
          const s = sync({ root, config: loadConfig(root) })
          for (const w of s.warnings) log(`warning: ${w}`)
          if (s.errors.length) { for (const e of s.errors) error(`error: ${e}`); return 1 }
          log(s.written.length ? `wrote ${s.written.join(', ')}` : 'outputs are current')
        }
        for (const line of nextSteps({ config: r.config, react, missingPeers: react ? missingReactPeers(root) : [] })) log(line)
        return 0
      }
      case 'version':
      case '--version':
      case '-v': {
        const pkg = packageInfo()
        log(`${pkg.name} ${pkg.version}`)
        return 0
      }
      case 'adapters': {
        const r = adapters()
        if (args.includes('--check')) {
          for (const p of r.problems) error(`stale: ${p}`)
          if (!r.problems.length) log(`adapter matrix is current for ${r.package} ${r.version}`)
          return r.problems.length ? 1 : 0
        }
        log(JSON.stringify(r, null, 2))
        return 0
      }
      case 'csp': {
        const [cssDir, rest] = takeFlag(args, 'css-dir')
        const dir = rest.find((a) => !a.startsWith('--')) ?? 'out'
        const r = csp({ root, dir, cssDir: cssDir ?? join('_next', 'static', 'css') })
        if (r.missing) { log(r.problems[0]); return 1 }
        if (r.problems.length) { error(`The export breaks a strict content security policy:\n${r.problems.join('\n')}`); return 1 }
        log(`Moved the Emotion styles of ${r.pages} pages into ${r.sheets} style sheet files; no inline style or script.`)
        return 0
      }
      case 'sync': {
        const { overrides } = outputFlags(args)
        const r = sync({ root, config: loadConfig(root, overrides) })
        for (const w of r.warnings) log(`warning: ${w}`)
        if (r.errors.length) {
          for (const e of r.errors) error(`error: ${e}`)
          error('Nothing was written. Fix DESIGN.md and run ds sync again.')
          return 1
        }
        log(r.written.length ? `wrote ${r.written.join(', ')}` : 'outputs are current')
        return 0
      }
      case 'diff':
      case 'check': {
        const { overrides } = outputFlags(args)
        const r = check({ root, config: loadConfig(root, overrides) })
        for (const w of r.warnings) log(`warning: ${w}`)
        for (const e of r.errors) error(`error: ${e}`)
        if (!r.stale.length) {
          if (!r.errors.length) log('outputs are current')
          return cmd === 'check' && r.errors.length ? 1 : 0
        }
        log(`stale: ${r.stale.join(', ')}${cmd === 'check' ? '\nRun ds sync and commit the result.' : ''}`)
        return cmd === 'check' ? 1 : 0
      }
      case 'lint': {
        const problems = lint({ root })
        for (const p of problems) log(`${p.file}:${p.line}  hardcoded ${p.kind}: ${p.text}`)
        const colors = problems.filter((p) => p.kind === 'color').length
        log(`${problems.length} finding${problems.length === 1 ? '' : 's'} (${colors} colors, ${problems.length - colors} copy). Colors belong in DESIGN.md; copy belongs in the copy documents. Mark a deliberate exception with a ds-lint-ignore comment.`)
        return args.includes('--strict') && problems.length ? 1 : 0
      }
      default:
        log(USAGE)
        return cmd === 'help' || cmd === '--help' || cmd === '-h' ? 0 : 1
    }
  } catch (e) {
    error(`ds ${cmd}: ${e instanceof Error ? e.message : String(e)}`)
    return 1
  }
}

