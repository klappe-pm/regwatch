#!/usr/bin/env node
// ds: keep a project's generated design and copy outputs in step with its sources. Sources are DESIGN.md (frontmatter)
// and the copy documents; outputs are replaced on every sync.
//
//   ds sync     write the outputs (--out <dir>, --spec, --css, --tailwind, --copy <file> set where they go)
//   ds diff     show which outputs would change
//   ds check    fail when an output is stale or DESIGN.md has errors (for CI and pre-commit)
//   ds lint     report hardcoded colors and copy in source files (add --strict to fail on them)
//   ds csp [dir] move the Emotion <style> elements of a static export (default: out) into style sheet files and fail on
//               any inline style or inline executable script left, for a strict Content Security Policy
//
// The logic lives in 'regwatch-design/node' (src/core/node.mjs): sync(), check(), outputs(), lint(), csp() and
// run(). This file only runs the command line, and only when it is executed; importing it runs nothing.
import { realpathSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { run } from '../src/core/node.mjs'

export { check, csp, lint, loadConfig, outputPaths, outputs, run, sync } from '../src/core/node.mjs'

const self = (() => {
  try { return realpathSync(fileURLToPath(import.meta.url)) } catch { return null }
})()
const invoked = (() => {
  try { return Boolean(process.argv[1]) && realpathSync(process.argv[1]) === self } catch { return false }
})()

if (invoked) {
  process.exitCode = run(process.argv.slice(2))
}
