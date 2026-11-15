export interface AdapterComponent {
  id: string
  role: string
  states: string[]
  slots: string[]
  events: string[]
  tokenRoles: string[]
}
export interface DesignSystemAdapter {
  id: string
  version: string
  framework: string
  license?: { spdx: string; evidenceUrl: string }
  components: AdapterComponent[]
  tokens: { id: string; type: string; path: string }[]
}
export interface SwitchInput {
  schemaVersion: 1
  source: DesignSystemAdapter
  target: DesignSystemAdapter
  componentIds?: string[]
  mappings: { from: string; to: string; reviewed: boolean }[]
  allowedLicenses?: string[]
}
export interface SwitchPlan {
  schemaVersion: 1
  status: 'blocked' | 'ready-for-review'
  source: { id: string; version: string }
  target: { id: string; version: string }
  components: { from: string; to: string | null; candidates: string[] }[]
  tokens: { role: string; type: string; from: string; to: string }[]
  blockers: { code: string; componentId: string | null; detail: string }[]
}
export interface DesignImpactSnapshot {
  schemaVersion: 1
  projectId: string
  revision: string
  coverage: 'complete' | 'partial'
  components: { id: string; tokenRoles: string[] }[]
  usages: { componentId: string; flowId: string }[]
  experiments: { id: string; status: 'draft' | 'running' | 'completed' | 'stopped'; componentIds: string[]; flowIds: string[]; tokenRoles: string[] }[]
}
export interface DesignImpact {
  schemaVersion: 1
  projectId: string
  revision: string
  coverage: 'complete' | 'partial'
  componentIds: string[]
  flowIds: string[]
  unplacedComponentIds: string[]
  experiments: DesignImpactSnapshot['experiments']
  overlappingExperimentIds: string[]
  requiresImpactReview: boolean
}
export declare function planDesignSystemSwitch(input: SwitchInput): SwitchPlan
export declare function designChangeImpact(snapshot: DesignImpactSnapshot, change: { componentIds: string[]; tokenRoles: string[] }): DesignImpact
