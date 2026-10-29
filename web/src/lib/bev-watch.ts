// The public preview's data: the workspace schema kept in browser storage, the sources and the
// synthetic updates. The stored values (categories, markets, source ids) are the schema and stay
// fixed; what the pages show for them comes from the copy documents.
import { t } from "./text.ts";

const DATA = "global.preview-data";

export const BRAND = t(`${DATA}.brand.name`);
export const WORKSPACE_STORAGE = "bev-watch.workspace.v1";
export function isPublicPage(pathname: string): boolean {
  if (process.env.NEXT_PUBLIC_BEV_WATCH_MODE === "hosted-preview") return true;
  const normalized = pathname.replace(/\/?$/, "/");
  return ["/pricing/", "/onboarding/", "/workspace/", "/privacy/"].includes(normalized);
}

/** Stored category values, with the copy key that names each one. */
const CATEGORY_KEYS: [string, string][] = [
  ["Non-alcoholic beverages", "non-alcoholic"],
  ["Beer & cider", "beer-cider"],
  ["Wine", "wine"],
  ["Spirits", "spirits"],
  ["Functional beverages", "functional"],
  ["Cannabis & hemp beverages", "cannabis-hemp"],
];
const MARKET_KEYS: [string, string][] = [
  ["United States", "us"],
  ["Canada", "ca"],
  ["United Kingdom", "uk"],
  ["European Union", "eu"],
  ["Australia & New Zealand", "anz"],
];
export const CATEGORIES = CATEGORY_KEYS.map(([value]) => value);
export const MARKETS = MARKET_KEYS.map(([value]) => value);

function named(pairs: [string, string][], group: string, value: string): string {
  const key = pairs.find(([stored]) => stored === value)?.[1];
  return key ? t(`${DATA}.${group}.${key}`) : value;
}
export const categoryName = (value: string): string => named(CATEGORY_KEYS, "categories", value);
export const marketName = (value: string): string => named(MARKET_KEYS, "markets", value);

export interface Source { id: string; name: string; short: string; market: string; topic: string; url: string }
const source = (id: string, market: string, url: string): Source => ({
  id,
  market,
  url,
  name: t(`${DATA}.sources.${id}.name`),
  short: t(`${DATA}.sources.${id}.short`),
  topic: t(`${DATA}.sources.${id}.topic`),
});
export const SOURCES: Source[] = [
  source("fda", "United States", "https://www.fda.gov/food"),
  source("ttb", "United States", "https://www.ttb.gov/"),
  source("fr", "United States", "https://www.federalregister.gov/"),
  source("hc", "Canada", "https://www.canada.ca/en/health-canada.html"),
  source("fsa", "United Kingdom", "https://www.food.gov.uk/"),
  source("eu", "European Union", "https://eur-lex.europa.eu/"),
  source("fsanz", "Australia & New Zealand", "https://www.foodstandards.gov.au/"),
];
export interface Product { id: string; name: string; category: string; ingredients: string; markets: string[] }
export interface Workspace { version: 1; company: string; categories: string[]; markets: string[]; sources: string[]; cadence: "Daily" | "Weekly"; products: Product[]; reviewed: string[]; saved: string[]; completed: boolean }
export function emptyWorkspace(): Workspace {
  return { version: 1, company: "", categories: [], markets: [], sources: [], cadence: "Weekly", products: [], reviewed: [], saved: [], completed: false };
}
/** Browser storage and imports are untrusted input. */
export function parseWorkspace(value: unknown): Workspace | null {
  if (!value || typeof value !== "object") return null;
  const w = value as Record<string, unknown>;
  const strings = (v: unknown): v is string[] => Array.isArray(v) && v.every(x => typeof x === "string");
  if (w.version !== 1 || typeof w.company !== "string" || !strings(w.categories) || !strings(w.markets) || !strings(w.sources) || !strings(w.reviewed) || !strings(w.saved) || !Array.isArray(w.products) || !["Daily", "Weekly"].includes(String(w.cadence)) || typeof w.completed !== "boolean") return null;
  if (!w.products.every(p => p && typeof p === "object" && typeof p.id === "string" && typeof p.name === "string" && typeof p.category === "string" && typeof p.ingredients === "string" && strings(p.markets))) return null;
  const products = w.products as Product[];
  if (!w.categories.every(x=>CATEGORIES.includes(x)) || !w.markets.every(x=>MARKETS.includes(x)) || !w.sources.every(id=>SOURCES.some(s=>s.id===id))) return null;
  if (new Set(products.map(p=>p.id)).size !== products.length || products.some(p=>!p.id || !p.name.trim() || !CATEGORIES.includes(p.category) || !p.markets.length || p.markets.some(m=>!MARKETS.includes(m)))) return null;
  return w as unknown as Workspace;
}
export function loadWorkspace(): Workspace {
  try { return parseWorkspace(JSON.parse(localStorage.getItem(WORKSPACE_STORAGE) || "null")) || emptyWorkspace(); } catch { return emptyWorkspace(); }
}
export class WorkspaceConflict extends Error {
  constructor() { super(t(`${DATA}.messages.conflict`)); }
}
/** Ordinary saves check their loaded snapshot; an explicit import can replace it. */
export function saveWorkspace(workspace: Workspace, expected?: Workspace): boolean {
  try {
    if (expected) {
      const raw = localStorage.getItem(WORKSPACE_STORAGE);
      const current = raw === null ? emptyWorkspace() : parseWorkspace(JSON.parse(raw));
      if (current === null || JSON.stringify(current) !== JSON.stringify(expected)) throw new WorkspaceConflict();
    }
    localStorage.setItem(WORKSPACE_STORAGE, JSON.stringify(workspace));
    return true;
  } catch (reason) {
    if (reason instanceof WorkspaceConflict) throw reason;
    return false;
  }
}
export function toggleValue(values: string[], value: string): string[] { return values.includes(value) ? values.filter(x => x !== value) : [...values, value]; }
/** Undo must preserve an imported product with the same identity. */
export function restoreProduct(products: Product[], product: Product): Product[] {
  return products.some(p=>p.id===product.id) ? products : [...products,product];
}
export interface SampleUpdate { id: string; title: string; source: string; market: string; category: string; priority: string; first: boolean; summary: string; action: string; url: string }
const update = (id: string, sourceId: string, market: string, first: boolean, url: string): SampleUpdate => ({
  id,
  market,
  first,
  url,
  source: t(`${DATA}.sources.${sourceId}.short`),
  priority: t(`${DATA}.priorities.${first ? "first" : "watch"}`),
  title: t(`${DATA}.updates.${id}.title`),
  category: t(`${DATA}.updates.${id}.category`),
  summary: t(`${DATA}.updates.${id}.summary`),
  action: t(`${DATA}.updates.${id}.action`),
});
export const SAMPLE_UPDATES: SampleUpdate[] = [
  update("label", "fda", "United States", true, "https://www.fda.gov/food/food-labeling-nutrition"),
  update("ingredient", "fr", "United States", false, "https://www.federalregister.gov/"),
  update("alcohol", "ttb", "United States", true, "https://www.ttb.gov/"),
  update("canada", "hc", "Canada", false, "https://www.canada.ca/en/health-canada.html"),
];
export const PLAN_FEATURES = ["1-workspace", "2-markets", "3-queue", "4-export", "5-decisions"].map((key) => t(`${DATA}.plan-features.${key}`));
export function briefingText(workspace: Workspace): string {
  const b = (key: string, vars?: Record<string, string>) => t(`${DATA}.briefing-export.${key}`, vars);
  return [
    b("heading", { brand: BRAND, company: workspace.company || b("your-workspace") }),
    b("intro"),
    b("markets", { markets: workspace.markets.map(marketName).join(", ") || b("not-selected") }),
    b("products", { products: workspace.products.map(p => p.name).join(", ") || b("no-products") }),
    ...SAMPLE_UPDATES.map(u => `${u.title}\n${u.summary}\n${b("suggested", { action: u.action })}\n${b("source", { url: u.url })}`),
    b("closing"),
  ].join("\n\n");
}
export function downloadText(filename: string, content: string, type = "text/plain") {
  const url = URL.createObjectURL(new Blob([content], { type })); const a = document.createElement("a");
  a.href = url; a.download = filename; a.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
