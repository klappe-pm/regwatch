// The adapter capability matrix: which stacks the package certifies, with which exact versions, what each adapter
// does and does not do, and the tests that are its evidence. Token and copy generation (framework neutral files) is
// separate from rendering (a component library adapter). A stack that can read CSS custom properties can use the
// tokens, but that is not a certified rendering adapter: no state, keyboard or accessibility behavior is claimed for it.
// Plain ESM with no Node imports.

/** Certification levels, from strongest to weakest. */
export const ADAPTER_STATUS = ['certified', 'tokens-only', 'unsupported']

/**
 * Every adapter. `verifiedWith` pins the exact versions the evidence ran against (it must match the package's
 * devDependencies, see adapterFreshness). `evidence` names the test files in this repository that certify it.
 */
export const ADAPTERS = [
  {
    id: 'spec-json',
    layer: 'tokens',
    status: 'certified',
    output: 'spec.json',
    entry: 'regwatch-design/node',
    capabilities: ['colors', 'roles', 'roles-dark', 'typography', 'spacing', 'radii', 'components', 'component-states', 'nested-rules'],
    unsupported: ['round-trip from spec.json back to DESIGN.md'],
    verifiedWith: {},
    evidence: ['test/core.test.mjs', 'test/init.test.mjs', 'test/consumer.test.mjs'],
  },
  {
    id: 'css-variables',
    layer: 'tokens',
    status: 'certified',
    output: 'ds.css',
    entry: 'regwatch-design/node',
    capabilities: ['--ds-color-*', '--ds-role-*', '--ds-font-*', '--ds-space-*', '--ds-radius-*', 'prefers-color-scheme', 'color-scheme attribute'],
    unsupported: ['component styles (only tokens are written)', 'round-trip from CSS back to DESIGN.md'],
    verifiedWith: {},
    evidence: ['test/core.test.mjs', 'test/init.test.mjs', 'test/consumer.test.mjs'],
  },
  {
    id: 'tailwind-v4',
    layer: 'tokens',
    status: 'certified',
    output: 'tailwind.css',
    entry: 'regwatch-design/node',
    capabilities: ['@theme inline colors', 'text sizes', 'fonts', 'spacing', 'radii'],
    unsupported: ['Tailwind v3 JavaScript config', 'component classes'],
    verifiedWith: {},
    evidence: ['test/core.test.mjs', 'test/init.test.mjs'],
  },
  {
    id: 'copy-json',
    layer: 'copy',
    status: 'certified',
    output: 'copy.json',
    entry: 'regwatch-design/node',
    capabilities: ['flat key map from copy documents', 'createCopy with {var} interpolation'],
    unsupported: ['plurals', 'locales', 'rich text'],
    verifiedWith: {},
    evidence: ['test/core.test.mjs', 'test/init.test.mjs', 'test/consumer.test.mjs'],
  },
  {
    id: 'react-mui',
    layer: 'rendering',
    status: 'certified',
    entry: 'regwatch-design',
    capabilities: ['Material UI theme', 'Part renderers', 'useParts', 'copy runtime (T, useCopy)', 'dark mode', 'scoped providers', 'strict CSP Emotion cache', 'disabled states'],
    unsupported: ['React 18', 'Material UI 5 to 8', 'non-Emotion style engines'],
    verifiedWith: { react: '19.3.1', 'react-dom': '19.3.1', '@mui/material': '9.5.0', '@emotion/react': '11.14.0', '@emotion/styled': '11.14.1', '@emotion/cache': '11.14.0' },
    evidence: ['test/fixes.test.mjs', 'test/release-015.test.mjs', 'test/release-016.test.mjs', 'test/attribution.test.mjs', 'test/consumer.test.mjs'],
  },
  ...['shadcn', 'vue', 'angular', 'svelte', 'web-components'].map((id) => ({
    id,
    layer: 'rendering',
    status: 'tokens-only',
    entry: null,
    capabilities: ['reads ds.css custom properties', 'reads copy.json'],
    unsupported: ['component renderers', 'state, keyboard and accessibility behavior', 'theme objects'],
    verifiedWith: {},
    evidence: [],
  })),
  ...['swiftui', 'compose', 'flutter'].map((id) => ({
    id,
    layer: 'rendering',
    status: 'unsupported',
    entry: null,
    capabilities: ['reads spec.json and copy.json as data'],
    unsupported: ['native token export', 'component renderers', 'state, keyboard and accessibility behavior'],
    verifiedWith: {},
    evidence: [],
  })),
]

/** The matrix as published by `ds adapters`: the package name and version, and every adapter. */
export function adapterMatrix(pkg, adapters = ADAPTERS) {
  return { package: pkg?.name ?? null, version: pkg?.version ?? null, adapters }
}

const major = (v) => String(v ?? '').match(/(\d+)/)?.[1]

/**
 * Freshness problems of the matrix against the package manifest: a certified adapter verified against a version
 * other than the devDependencies pin (the dependency moved without new evidence), a pin outside the peer range's
 * major, a certified adapter without evidence, or an uncertified one that claims evidence or a version. `[]` means
 * the matrix is current.
 */
export function adapterFreshness(pkg, adapters = ADAPTERS) {
  const problems = []
  const dev = pkg?.devDependencies ?? {}
  const peers = pkg?.peerDependencies ?? {}
  const ids = new Set()
  for (const a of adapters) {
    if (ids.has(a.id)) problems.push(`${a.id}: listed twice`)
    ids.add(a.id)
    if (!ADAPTER_STATUS.includes(a.status)) problems.push(`${a.id}: unknown status ${a.status}`)
    if (a.status !== 'certified') {
      if (a.evidence.length || Object.keys(a.verifiedWith).length) problems.push(`${a.id}: only a certified adapter carries evidence or verified versions`)
      continue
    }
    if (!a.evidence.length) problems.push(`${a.id}: certified without evidence`)
    for (const [dep, version] of Object.entries(a.verifiedWith)) {
      if (dev[dep] === undefined) problems.push(`${a.id}: ${dep} is not a devDependency, so nothing verifies ${version}`)
      else if (dev[dep] !== version) problems.push(`${a.id}: verified with ${dep} ${version}, but the tests now run ${dev[dep]}; rerun the evidence and update verifiedWith`)
      if (peers[dep] !== undefined && major(peers[dep]) !== major(version)) problems.push(`${a.id}: ${dep} ${version} is outside the peer range ${peers[dep]}`)
    }
  }
  return problems
}
