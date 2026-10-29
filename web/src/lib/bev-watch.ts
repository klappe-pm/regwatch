import { t, type CopyKey } from "./copy.generated.ts";

export const BRAND = t("global.preview.bev-watch");
export const WORKSPACE_STORAGE = "bev-watch.workspace.v1";
export function isPublicPage(pathname: string): boolean {
  if (process.env.NEXT_PUBLIC_BEV_WATCH_MODE === "hosted-preview") return true;
  const normalized = pathname.replace(/\/?$/, "/");
  return ["/pricing/", "/onboarding/", "/workspace/", "/privacy/"].includes(normalized);
}
export const CATEGORIES = ["Non-alcoholic beverages", "Beer & cider", "Wine", "Spirits", "Functional beverages", "Cannabis & hemp beverages"];
export const MARKETS = ["United States", "Canada", "United Kingdom", "European Union", "Australia & New Zealand"];
const SOURCE_COPY = [
  { id: "fda", nameCopy: "global.preview.food-drug-administration", shortCopy: "global.preview.fda", market: "United States", topicCopy: "global.preview.ingredients-labeling-food-safety", url: "https://www.fda.gov/food" },
  { id: "ttb", nameCopy: "global.preview.alcohol-and-tobacco-tax-and-trade-bureau", shortCopy: "global.preview.ttb", market: "United States", topicCopy: "global.preview.alcohol-labeling-formulas-permits", url: "https://www.ttb.gov/" },
  { id: "fr", nameCopy: "global.preview.federal-register", shortCopy: "global.preview.fr", market: "United States", topicCopy: "global.preview.proposed-and-final-federal-rules", url: "https://www.federalregister.gov/" },
  { id: "hc", nameCopy: "global.preview.health-canada", shortCopy: "global.preview.hc", market: "Canada", topicCopy: "global.preview.food-standards-product-labeling", url: "https://www.canada.ca/en/health-canada.html" },
  { id: "fsa", nameCopy: "global.preview.food-standards-agency", shortCopy: "global.preview.fsa", market: "United Kingdom", topicCopy: "global.preview.food-safety-guidance-alerts", url: "https://www.food.gov.uk/" },
  { id: "eu", nameCopy: "global.preview.eur-lex", shortCopy: "global.preview.eu", market: "European Union", topicCopy: "global.preview.european-union-legislation", url: "https://eur-lex.europa.eu/" },
  { id: "fsanz", nameCopy: "global.preview.food-standards-australia-new-zealand", shortCopy: "global.preview.fsanz", market: "Australia & New Zealand", topicCopy: "global.preview.food-standards-consultations", url: "https://www.foodstandards.gov.au/" },
] as const;
export const SOURCES = SOURCE_COPY.map(source => ({ ...source, name: t(source.nameCopy), short: t(source.shortCopy), topic: t(source.topicCopy) }));
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
export class ManagedError extends Error {
  readonly copyKey: CopyKey;
  constructor(copyKey: CopyKey) { super(t(copyKey)); this.copyKey = copyKey; }
}
export class WorkspaceConflict extends ManagedError {
  constructor() { super("global.preview.this-workspace-changed-in-another-tab-reload"); }
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
const UPDATE_COPY = [
  { id: "label", titleCopy: "global.preview.a-labeling-proposal-appears-in-your-market", sourceCopy: "global.preview.fda", market: "United States", categoryCopy: "global.preview.labeling", priority: "Review first", summaryCopy: "global.preview.an-illustrative-proposal-would-change-how-a", actionCopy: "global.preview.review-affected-labels-and-record-a-decision", url: "https://www.fda.gov/food/food-labeling-nutrition" },
  { id: "ingredient", titleCopy: "global.preview.an-ingredient-consultation-opens-for-comment", sourceCopy: "global.preview.fr", market: "United States", categoryCopy: "global.preview.ingredients", priority: "Watch", summaryCopy: "global.preview.this-sample-consultation-demonstrates-how-an-ingredient", actionCopy: "global.preview.check-whether-the-ingredient-is-used-in", url: "https://www.federalregister.gov/" },
  { id: "alcohol", titleCopy: "global.preview.alcohol-label-guidance-is-revised", sourceCopy: "global.preview.ttb", market: "United States", categoryCopy: "global.preview.alcohol", priority: "Review first", summaryCopy: "global.preview.an-invented-guidance-change-shows-how-alcohol", actionCopy: "global.preview.compare-your-label-approval-workflow-with-the", url: "https://www.ttb.gov/" },
  { id: "canada", titleCopy: "global.preview.a-food-standard-changes-in-a-second", sourceCopy: "global.preview.hc", market: "Canada", categoryCopy: "global.preview.standards", priority: "Watch", summaryCopy: "global.preview.this-synthetic-example-illustrates-cross-market-monitoring", actionCopy: "global.preview.assign-a-reviewer-for-products-sold-in", url: "https://www.canada.ca/en/health-canada.html" },
] as const;
export const SAMPLE_UPDATES = UPDATE_COPY.map(update => ({ ...update, title: t(update.titleCopy), source: t(update.sourceCopy), category: t(update.categoryCopy), summary: t(update.summaryCopy), action: t(update.actionCopy) }));
export const PLAN_FEATURES = ["global.preview.a-workspace-for-your-beverage-portfolio", "global.preview.market-and-source-selection", "global.preview.a-prioritized-review-queue", "global.preview.briefing-export", "global.preview.saved-review-decisions"] as const;
export function briefingText(workspace: Workspace): string {
  return [`${BRAND} | ${workspace.company || t("global.preview.your-workspace")}`, t("global.preview.preview-briefing-all-regulatory-updates-below-are"), `${t("global.preview.briefing-markets")} ${workspace.markets.map(publicLabel).join(", ") || t("global.preview.not-selected")}`, `${t("global.preview.briefing-products")} ${workspace.products.map(p => p.name).join(", ") || t("global.preview.no-products-added")}`, ...SAMPLE_UPDATES.map(u => `${u.title}\n${u.summary}\n${t("global.preview.briefing-review")} ${u.action}\n${t("global.preview.briefing-source")} ${u.url}`), t("global.preview.for-human-review-not-legal-advice-no")].join("\n\n");
}
export function downloadText(filename: string, content: string, type = "text/plain") {
  const url = URL.createObjectURL(new Blob([content], { type })); const a = document.createElement("a");
  a.href = url; a.download = filename; a.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const LABEL_KEYS: Record<string, CopyKey> = {
  "Non-alcoholic beverages": "global.preview.non-alcoholic-beverages",
  "Beer & cider": "global.preview.beer-cider",
  "Wine": "global.preview.wine",
  "Spirits": "global.preview.spirits",
  "Functional beverages": "global.preview.functional-beverages",
  "Cannabis & hemp beverages": "global.preview.cannabis-hemp-beverages",
  "United States": "global.preview.united-states",
  "Canada": "global.preview.canada",
  "United Kingdom": "global.preview.united-kingdom",
  "European Union": "global.preview.european-union",
  "Australia & New Zealand": "global.preview.australia-new-zealand",
  "Daily": "global.preview.daily",
  "Weekly": "global.preview.weekly",
  "Review first": "global.preview.review-first",
  "Watch": "global.preview.watch"
};
export function publicLabel(value: string): string {
  return LABEL_KEYS[value] ? t(LABEL_KEYS[value]) : value;
}
