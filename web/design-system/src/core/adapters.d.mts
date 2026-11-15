export type AdapterStatus = 'certified' | 'tokens-only' | 'unsupported'

export interface AdapterEntry {
  id: string
  layer: 'tokens' | 'copy' | 'rendering'
  status: AdapterStatus
  /** The generated file, for token and copy adapters. */
  output?: string
  /** The package entry that provides it, or null when the package provides none. */
  entry: string | null
  capabilities: string[]
  unsupported: string[]
  /** Exact versions the evidence ran against. */
  verifiedWith: Record<string, string>
  /** Test files in this repository that certify the adapter. */
  evidence: string[]
}

export interface AdapterMatrix { package: string | null; version: string | null; adapters: AdapterEntry[] }

export declare const ADAPTER_STATUS: AdapterStatus[]
export declare const ADAPTERS: AdapterEntry[]
export declare function adapterMatrix(pkg: { name?: string; version?: string } | null, adapters?: AdapterEntry[]): AdapterMatrix
/** Problems that make the matrix stale against the package manifest; [] when it is current. */
export declare function adapterFreshness(pkg: { devDependencies?: Record<string, string>; peerDependencies?: Record<string, string> } | null, adapters?: AdapterEntry[]): string[]
