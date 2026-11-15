// The shape of design/spec.json, written by `ds sync` from DESIGN.md. Shared by the core entry and the React entry.

/**
 * A component's style: CSS properties (plus textColor, rounded and typography) and nested rules such as
 * `"& .label": {...}` or `"@media (max-width: 600px)": {...}`, which reach sx as they are.
 */
interface SpecStyle {
  [key: string]: string | number | SpecStyle
}

interface SpecComponent {
  material: string
  label: string | null
  /** CSS selector the component was extracted from (documentation only; never emitted as CSS). */
  selector?: string | null
  /** True when DESIGN.md opts in with `scope: global` or `material-default: true`: the component then styles every
   * instance of its Material UI component through the theme. Otherwise it styles only Part and componentSx. */
  global?: boolean
  /** True for a modifier (`modifier: true`), such as a size variant combined with a base part. A modifier gets no
   * disabled defaults of its own and never becomes the global look of its Material UI component. */
  modifier?: boolean
  state: string | null
  base: string | null
  raw: SpecStyle
  style: SpecStyle
}

interface DesignSpec {
  $schema: 'design-spec/1'
  name: string | null
  description: string | null
  roles: Record<string, string>
  rolesDark: Record<string, string> | null
  colors: Record<string, string>
  typography: Record<string, Record<string, string | number>>
  spacing: Record<string, string>
  /** Theme spacing unit named by ds.config.json spacingUnit or DESIGN.md spacing.unit; null falls back to spacing.base, then 8px. */
  spacingUnit?: string | null
  rounded: Record<string, string>
  components: Record<string, SpecComponent>
}

type CopyMap = Record<string, string>
type Translate = (key: string, vars?: Record<string, string | number>) => string
/** What a missing copy key does: 'key' returns the key, 'throw' throws, a function returns its own fallback. */
type OnMissing = 'key' | 'throw' | ((key: string) => string)

export type { CopyMap, DesignSpec, OnMissing, SpecComponent, SpecStyle, Translate };
