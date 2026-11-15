// Planning only. Renderers and repository runtimes own code changes, checks and approval.
const text = (value, label) => {
  if (typeof value !== 'string' || !value.trim() || value.length > 512) throw new TypeError(`${label} must be a nonempty string of at most 512 characters`)
  return value
}
const list = (value, label) => {
  if (!Array.isArray(value) || value.length > 10000) throw new TypeError(`${label} must be an array of at most 10000 items`)
  return value
}
const strings = (value, label) => {
  const values = list(value, label).map(v => text(v, label))
  if (new Set(values).size !== values.length) throw new TypeError(`${label} contains duplicates`)
  return values
}
const index = (rows, label) => {
  const out = new Map()
  for (const row of list(rows, label)) {
    const id = text(row?.id, `${label}.id`)
    if (out.has(id)) throw new TypeError(`${label} contains duplicate id ${id}`)
    out.set(id, row)
  }
  return out
}
const sorted = values => [...new Set(values)].sort()

function adapter(value, label) {
  text(value?.id, `${label}.id`)
  text(value.version, `${label}.version`)
  text(value.framework, `${label}.framework`)
  const components = index(value.components, `${label}.components`)
  for (const component of components.values()) {
    text(component.role, `${label}.component.role`)
    for (const field of ['states', 'slots', 'events', 'tokenRoles']) strings(component[field], `${label}.component.${field}`)
  }
  const tokens = index(value.tokens, `${label}.tokens`)
  for (const token of tokens.values()) {
    text(token.type, `${label}.token.type`)
    text(token.path, `${label}.token.path`)
  }
  return { components, tokens }
}

/** Create a deterministic compatibility proposal from version-pinned adapter manifests. */
export function planDesignSystemSwitch(input) {
  if (input?.schemaVersion !== 1) throw new TypeError('schemaVersion must be 1')
  const source = adapter(input.source, 'source')
  const target = adapter(input.target, 'target')
  const selected = strings(input.componentIds ?? [...source.components.keys()], 'componentIds')
  if (!selected.length) throw new TypeError('Select at least one component')
  for (const id of selected) if (!source.components.has(id)) throw new TypeError(`Unknown source component ${id}`)
  const mappings = new Map()
  for (const mapping of list(input.mappings, 'mappings')) {
    if (!source.components.has(mapping?.from) || !target.components.has(mapping?.to)) throw new TypeError('Mapping references an unknown component')
    if (mappings.has(mapping.from)) throw new TypeError(`Duplicate mapping for ${mapping.from}`)
    if (typeof mapping.reviewed !== 'boolean') throw new TypeError('Mapping reviewed must be a boolean')
    mappings.set(mapping.from, mapping)
  }
  const blockers = []
  const block = (code, componentId, detail) => blockers.push({ code, componentId, detail })
  const license = input.target.license
  // This is the caller's license policy and supplied evidence, not legal certification.
  const allowed = strings(input.allowedLicenses ?? ['MIT'], 'allowedLicenses')
  let evidence = false
  try { evidence = ['http:', 'https:'].includes(new URL(license?.evidenceUrl).protocol) } catch {}
  if (!license || !allowed.includes(license.spdx) || !evidence) block('license-review-required', null, 'Supply a policy-allowed license and its source URL for this adapter release.')
  if (input.source.framework !== input.target.framework) block('framework-adapter-required', null, 'Changing frameworks requires a separate renderer migration adapter.')
  const components = []
  const tokenRoles = new Set()
  for (const id of selected.slice().sort()) {
    const from = source.components.get(id)
    const mapping = mappings.get(id)
    const candidates = [...target.components.values()].filter(c => c.role === from.role).map(c => c.id).sort()
    for (const role of from.tokenRoles) tokenRoles.add(role)
    const to = mapping && target.components.get(mapping.to)
    components.push({ from: id, to: to?.id ?? null, candidates })
    if (!mapping) {
      block(candidates.length > 1 ? 'ambiguous-mapping' : 'mapping-required', id, 'Review an explicit mapping. A shared role is only a candidate match.')
      continue
    }
    if (!mapping.reviewed) block('mapping-review-required', id, 'The explicit mapping has not been reviewed.')
    if (from.role !== to.role) block('role-mismatch', id, `${from.role} cannot automatically replace ${to.role}.`)
    for (const field of ['states', 'slots', 'events', 'tokenRoles']) {
      const missing = from[field].filter(v => !to[field].includes(v)).sort()
      if (missing.length) block(`missing-${field}`, id, missing.join(', '))
    }
  }
  const tokens = []
  for (const role of [...tokenRoles].sort()) {
    const from = source.tokens.get(role)
    const to = target.tokens.get(role)
    if (!from || !to) block('token-binding-required', null, role)
    else if (from.type !== to.type) block('token-type-mismatch', null, role)
    else tokens.push({ role, type: from.type, from: from.path, to: to.path })
  }
  return {
    schemaVersion: 1,
    status: blockers.length ? 'blocked' : 'ready-for-review',
    source: { id: input.source.id, version: input.source.version },
    target: { id: input.target.id, version: input.target.version },
    components, tokens, blockers,
  }
}

/** Find shared-token impact and previous/overlapping experiments in one project snapshot. */
export function designChangeImpact(snapshot, change) {
  if (snapshot?.schemaVersion !== 1) throw new TypeError('schemaVersion must be 1')
  text(snapshot.projectId, 'projectId')
  text(snapshot.revision, 'revision')
  if (!['complete', 'partial'].includes(snapshot.coverage)) throw new TypeError('coverage must be complete or partial')
  const components = index(snapshot.components, 'components')
  for (const c of components.values()) strings(c.tokenRoles, 'component.tokenRoles')
  const selected = strings(change?.componentIds, 'change.componentIds')
  const roles = strings(change.tokenRoles, 'change.tokenRoles')
  if (!selected.length && !roles.length) throw new TypeError('Select at least one component or token role')
  for (const id of selected) if (!components.has(id)) throw new TypeError(`Unknown component ${id}`)
  const knownRoles = new Set([...components.values()].flatMap(c => c.tokenRoles))
  for (const role of roles) if (!knownRoles.has(role)) throw new TypeError(`Unknown token role ${role}`)
  const affected = new Set(selected)
  for (const c of components.values()) if (c.tokenRoles.some(role => roles.includes(role))) affected.add(c.id)
  const usages = list(snapshot.usages, 'usages')
  for (const u of usages) {
    if (!components.has(u?.componentId)) throw new TypeError('Usage references an unknown component')
    text(u.flowId, 'usage.flowId')
  }
  const flowIds = sorted(usages.filter(u => affected.has(u.componentId)).map(u => u.flowId))
  const experiments = index(snapshot.experiments, 'experiments')
  const history = []
  for (const e of experiments.values()) {
    if (!['draft', 'running', 'completed', 'stopped'].includes(e.status)) throw new TypeError('Unknown experiment status')
    strings(e.componentIds, 'experiment.componentIds')
    strings(e.flowIds, 'experiment.flowIds')
    strings(e.tokenRoles, 'experiment.tokenRoles')
    for (const id of e.componentIds) if (!components.has(id)) throw new TypeError('Experiment references an unknown component')
    for (const role of e.tokenRoles) if (!knownRoles.has(role)) throw new TypeError('Experiment references an unknown token role')
    const sharedComponents = sorted(e.componentIds.filter(id => affected.has(id)))
    const sharedFlows = sorted(e.flowIds.filter(id => flowIds.includes(id)))
    const sharedTokens = sorted(e.tokenRoles.filter(role => roles.includes(role) || [...affected].some(id => components.get(id).tokenRoles.includes(role))))
    if (sharedComponents.length || sharedFlows.length || sharedTokens.length) history.push({ id: e.id, status: e.status, componentIds: sharedComponents, flowIds: sharedFlows, tokenRoles: sharedTokens })
  }
  history.sort((a, b) => a.id.localeCompare(b.id, 'en'))
  const unplacedComponentIds = [...affected].filter(id => !usages.some(u => u.componentId === id)).sort()
  return {
    schemaVersion: 1, projectId: snapshot.projectId, revision: snapshot.revision,
    coverage: snapshot.coverage, componentIds: [...affected].sort(), flowIds,
    unplacedComponentIds, experiments: history,
    overlappingExperimentIds: history.filter(e => e.status === 'running').map(e => e.id),
    requiresImpactReview: snapshot.coverage !== 'complete' || unplacedComponentIds.length > 0 || history.some(e => e.status === 'running'),
  }
}
