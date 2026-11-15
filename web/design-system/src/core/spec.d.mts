import type { DesignSpec } from './types.mjs'
export interface BuildSpecOptions {
  /** Custom properties found in the project's CSS, to resolve var() aliases. */
  cssVars?: Map<string, string>
  /** 'var' (default): component color references become var(--ds-role-*) so they follow dark mode. 'value': the resolved value. */
  colorRefs?: 'var' | 'value'
  /** Theme spacing unit (a length or a spacing token name, `unit` included); overrides DESIGN.md spacing.unit. */
  spacingUnit?: string | number
  /** Prefixes of custom properties the host page defines (for example '--background-'): kept as written, never resolved. */
  hostVariables?: string[]
}
export interface CssVariablesOptions {
  /** The element the tokens are defined on. Default ':root'. */
  selector?: string
  /** 'self' (default): the color-scheme attribute is on that element. 'ancestor': it is on an element around it. */
  colorSchemeTarget?: 'self' | 'ancestor'
  /** The color-scheme attribute (default 'data-theme'), or a full selector with %s for the scheme name. */
  attribute?: string
}
export declare const M3_ROLES: string[]
export declare const COMPONENT_META_KEYS: string[]
export declare function isNestedRule(key: string): boolean
export declare function guessMaterial(name: string): string
export declare function buildSpec(front: Record<string, any>, opts?: BuildSpecOptions): DesignSpec
export declare function specWarnings(spec: DesignSpec, front: Record<string, any>, opts?: { hostVariables?: string[] }): string[]
/** Malformed DESIGN.md components (objects that are not nested rules, broken selectors or values); `ds check` fails on them. */
export declare function specErrors(front: Record<string, any>): string[]
export declare function cssVariables(spec: DesignSpec, opts?: CssVariablesOptions): string
export declare function tailwindTheme(spec: DesignSpec): string
