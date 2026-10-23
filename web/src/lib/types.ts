/** Shapes of the JSON the local server returns. See regwatch/webapi.py. */

export interface Unavailable {
  available: false;
  command: string;
}

export interface SourceResult {
  source_id: string;
  name: string;
  status: string;
  origin: string;
  detail: string;
  flagged: boolean;
  needs_attention: boolean;
}

export interface Impact {
  product_id: string;
  product_name: string;
  obligation_id: string;
  obligation_title: string;
  jurisdiction: string;
  status: string;
  effective_date: string;
  severity: string;
  reasons: string[];
  focus: string[];
  in_focus: boolean;
}

export interface Candidate {
  date: string;
  jurisdiction: string;
  agency: string;
  headline: string;
  what_happened: string;
  type: string;
  source_url: string;
  confidence: string;
}

export interface Upcoming {
  obligation_id: string;
  title: string;
  jurisdiction: string;
  effective_date: string;
  status: string;
}

export interface Status {
  version: string;
  project: string;
  premium: boolean;
}

export interface Overview {
  generated: string;
  counts: { new: number; changed: number; suspicious: number; failing: number };
  sources: number;
  flagged: SourceResult[];
  priority: Impact[];
  upcoming: Upcoming[];
  schedule: Unavailable | { available: true; every?: string; next_run?: string };
  supply_chain:
    | Unavailable
    | { available: true; signals: { title: string; detail: string; date: string }[] };
}

export interface Changes {
  sources: SourceResult[];
  impacts: Impact[];
  candidates: Candidate[];
  severities: string[];
}

export interface MySource {
  source_id: string;
  name: string;
  jurisdiction: string;
  mechanism: string;
  cadence: string;
  url: string;
  status: string;
  detail: string;
}

export interface CatalogueEntry {
  source_id: string;
  name: string;
  publisher?: string;
  jurisdiction?: string;
  region?: string;
  category?: string;
  kind?: string;
  access?: string;
  description?: string;
}

export type Catalogue =
  | (Unavailable & { entries: CatalogueEntry[]; facets: Record<string, string[]> })
  | { available: true; entries: CatalogueEntry[]; facets: Record<string, string[]> };

export interface Obligation {
  obligation_id: string;
  title: string;
  jurisdiction: string;
  jurisdiction_name: string;
  instrument: string;
  citation: string;
  status: string;
  effective_date: string;
  categories: string[];
  source_url: string;
  impacts: Impact[];
}

export interface DocumentSection {
  heading: string;
  level: number;
  paragraphs: string[];
  bullets: string[];
}

export interface BriefingDocument {
  title: string;
  subtitle: string;
  generated: string;
  sections: DocumentSection[];
  disclaimer: string;
}

export interface Automations {
  premium: boolean;
  schedule: Unavailable | { available: true; every?: string; next_run?: string };
  runs:
    | (Unavailable & { records: RunRecord[] })
    | { available: true; records: RunRecord[] };
}

export interface RunRecord {
  started?: string;
  ended?: string;
  exit_code?: number;
  counts?: Record<string, number>;
}

export interface KeyRow {
  source_id: string;
  key_env: string;
  present: boolean;
}

export type Keys = (Unavailable & { keys: KeyRow[] }) | { available: true; keys: KeyRow[] };

export interface Settings {
  focus_areas: string[];
  custom_terms: string[];
  focus_catalogue: { id: string; label: string; description: string }[];
  premium: boolean;
  design: Unavailable;
  llm: Unavailable;
}

export interface SearchResults {
  query: string;
  sources: { source_id: string; name: string; jurisdiction: string; mine: boolean }[];
  changes: ((Impact & { kind: "impact" }) | (Candidate & { kind: "candidate" }))[];
  obligations: { obligation_id: string; title: string; jurisdiction: string; status: string }[];
}
