export type OutputKind = 'spec' | 'css' | 'tailwind' | 'copy'

export interface DsConfig {
  /** DESIGN.md path, relative to the root. */
  designFile: string
  /** Folder of copy documents. */
  cmsDir: string
  /** Folder the outputs go to unless `files` names a path. Default 'design'. */
  out: string
  /** Folders or files `ds lint` reads. */
  src: string | string[]
  /** Paths never read, for linting or for CSS custom properties. */
  ignore: string[]
  /** Theme spacing unit: a length or a spacing token name (`unit` included). */
  spacingUnit?: string | number
  /** Prefixes of custom properties the host page defines (for example '--background-'). Kept as written, never reported. */
  hostVariables: string[]
  /** Path of each output, relative to the root. */
  files: Partial<Record<OutputKind, string>>
  /** The color-scheme attribute design/ds.css switches the dark roles on. Default 'data-theme'. */
  colorSchemeAttribute?: string
}

export interface OutputsResult {
  /** Generated text by path relative to the root. */
  files: Record<string, string>
  warnings: string[]
  /** Malformed DESIGN.md components. Outputs are not written while there are errors. */
  errors: string[]
}

export interface LintProblem { file: string; line: number; kind: 'color' | 'copy'; text: string }

export declare const OUTPUT_FILES: Record<OutputKind, string>
export declare const USAGE: string
export declare function loadConfig(root?: string, overrides?: Partial<DsConfig>): DsConfig
export declare function outputPaths(cfg: DsConfig): Record<OutputKind, string>
export declare function outputs(opts?: { root?: string; config?: DsConfig }): OutputsResult
export declare function staleOutputs(root: string, files: Record<string, string>): string[]
export declare function sync(opts?: { root?: string; config?: DsConfig }): OutputsResult & { written: string[] }
export declare function check(opts?: { root?: string; config?: DsConfig }): OutputsResult & { ok: boolean; stale: string[] }
export declare function lint(opts?: { root?: string; config?: DsConfig }): LintProblem[]
export declare function csp(opts?: { root?: string; dir?: string; cssDir?: string }): { missing: boolean; pages: number; sheets: number; problems: string[] }
export declare function outputFlags(args: string[]): { overrides: Partial<DsConfig>; rest: string[] }
/** Run one ds command as the CLI does; returns the exit code. */
export declare function run(argv?: string[], io?: { root?: string; log?: (line: string) => void; error?: (line: string) => void }): number

export interface InitOptions {
  root?: string
  /** Project name in the starter DESIGN.md and copy (default: package.json name, else the folder name). */
  name?: string
  designFile?: string
  cmsDir?: string
  out?: string
  src?: string | string[]
  /** Overwrite existing files. */
  force?: boolean
  /** Add design:sync and design:check to package.json when it exists (default true). */
  scripts?: boolean
}
export interface InitResult { created: string[]; kept: string[]; config: Partial<DsConfig>; scripts: string[] }

/** The React entry's peer dependencies; the CLI, core entry and CSS outputs need none of them. */
export declare const REACT_PEERS: string[]
/** Write a starter DESIGN.md, copy document and ds.config.json. Existing files are kept unless `force` is set. */
export declare function init(opts?: InitOptions): InitResult
export declare function starterDesign(name?: string): string
export declare function starterCopy(name?: string): string
/** React peer dependencies that `root` cannot resolve. */
export declare function missingReactPeers(root?: string): string[]
export declare function nextSteps(opts: { config: Partial<DsConfig>; react?: boolean; missingPeers?: string[] }): string[]
/** This package's package.json. */
export declare function packageInfo(): { name: string; version: string; [key: string]: unknown }
/** The adapter capability matrix and its freshness problems ([] when current). */
export declare function adapters(): import('./adapters.mjs').AdapterMatrix & { problems: string[] }
