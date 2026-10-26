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

export interface ScheduleState {
  available: true;
  via: "launchd" | "cron";
  installed: boolean;
  every: string | null;
  next_run: string | null;
  note: string;
}

export interface SupplySource {
  source_id: string;
  name: string;
  category: string;
  jurisdiction: string;
  status: string;
  detail: string;
}

export interface Overview {
  generated: string;
  counts: { new: number; changed: number; suspicious: number; failing: number };
  sources: number;
  flagged: SourceResult[];
  priority: Impact[];
  upcoming: Upcoming[];
  schedule: ScheduleState;
  supply_chain: { available: true; sources: SupplySource[]; categories: string[] };
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
  publisher: string;
  jurisdiction: string;
  region: string;
  category: string;
  kind: string;
  access: string;
  access_label: string;
  cadence: string;
  description: string;
  homepage: string;
  signup_url: string;
  chosen: boolean;
}

export interface Catalogue {
  available: true;
  total: number;
  entries: CatalogueEntry[];
  facets: Record<string, string[]>;
  categories: string[];
}

export interface AddResult {
  available: true;
  source_id: string;
  added: string[];
  present: string[];
  added_jurisdictions: string[];
  needs_key: boolean;
}

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
  schedule: ScheduleState;
  runs: { available: true; records: RunRecord[] };
  running: boolean;
  last_error: string;
}

export interface RunRecord {
  started?: string;
  ended?: string;
  sources?: number;
  captured?: number;
  capture_failed?: number;
  exit_code?: number;
  counts?: Record<string, number>;
}

export interface KeyRow {
  source_id: string;
  key_env: string;
  present: boolean;
  where: string;
  signup_url: string;
}

export interface Keys {
  available: true;
  keychain: string;
  keychain_available: boolean;
  keys: KeyRow[];
}

export interface DesignSettings {
  available: true;
  title_format: string;
  organisation: string;
  primary_color: string;
  accent_color: string;
  font: string;
  logo: string;
  header: string;
  footer: string;
  page_size: string;
  newsletter_footer: string;
  fonts: string[];
  page_sizes: string[];
}

export interface ProviderKey {
  id: string;
  provider: string;
  key_env: string;
  present: boolean;
  where: string;
  signup_url: string;
}

export interface LlmSettings {
  available: true;
  enabled: boolean;
  provider: string;
  model: string;
  providers: string[];
  default_models: Record<string, string>;
  keys: ProviderKey[];
}

export interface Settings {
  focus_areas: string[];
  custom_terms: string[];
  focus_catalogue: { id: string; label: string; description: string }[];
  premium: boolean;
  design: DesignSettings;
  llm: LlmSettings;
}

export interface Newsletter {
  available: true;
  since: number;
  periods: number[];
  subject: string;
  html: string;
  text: string;
  generated: boolean;
  dropped: string[];
  notice: string;
}

export interface DesignedDocument {
  available: true;
  kind: string;
  tier: string;
  kinds: string[];
  formats: string[];
  title: string;
  html: string;
  generated: boolean;
  dropped: string[];
  notice: string;
}

export interface SearchResults {
  query: string;
  sources: { source_id: string; name: string; jurisdiction: string; mine: boolean }[];
  changes: ((Impact & { kind: "impact" }) | (Candidate & { kind: "candidate" }))[];
  obligations: { obligation_id: string; title: string; jurisdiction: string; status: string }[];
}
