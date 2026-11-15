import type { CopyMap, OnMissing, Translate } from './types.mjs'
export { planDesignSystemSwitch, designChangeImpact, type AdapterComponent, type DesignSystemAdapter, type SwitchInput, type SwitchPlan, type DesignImpactSnapshot, type DesignImpact } from './migration.mjs'
export type { CopyMap, DesignSpec, OnMissing, SpecComponent, SpecStyle, Translate } from './types.mjs'
export { COMPONENT_META_KEYS, M3_ROLES, buildSpec, cssVariables, guessMaterial, isNestedRule, specErrors, specWarnings, tailwindTheme, type BuildSpecOptions, type CssVariablesOptions } from './spec.mjs'
export declare function createCopy(copy: CopyMap, opts?: { onMissing?: OnMissing }): Translate
export declare function scanDoc(markdown: string): { key: string; value: string }[]
export declare function copyMap(docs: { doc: string; markdown: string }[]): Record<string, string>
export declare function extractEmotionStyles(html: string, sheet: (css: string) => string): string
export declare function cspFindings(html: string): string[]
export declare const LINT_EXTENSIONS: RegExp
export declare function colorFindings(line: string): string[]
export declare function copyFindings(line: string): string[]
/** Hardcoded copy in string attributes (aria-label, placeholder, title, alt, label) and in template literals in JSX. */
export declare function attributeCopyFindings(line: string): string[]
/** Lines carrying `ds-lint-ignore`, following `ds-lint-ignore-next-line`, or in a file with `ds-lint-ignore-file` are skipped. */
export declare function lintSource(text: string, file: string): { line: number; kind: 'color' | 'copy'; text: string }[]
export { ADAPTERS, ADAPTER_STATUS, adapterFreshness, adapterMatrix, type AdapterEntry, type AdapterMatrix, type AdapterStatus } from './adapters.mjs'
