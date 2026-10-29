export const BRAND = "Bev Watch";
export const WORKSPACE_STORAGE = "bev-watch.workspace.v1";
export function isPublicPage(pathname: string): boolean {
  if (process.env.NEXT_PUBLIC_BEV_WATCH_MODE === "hosted-preview") return true;
  const normalized = pathname.replace(/\/?$/, "/");
  return ["/pricing/", "/onboarding/", "/workspace/", "/privacy/"].includes(normalized);
}
export const CATEGORIES = ["Non-alcoholic beverages", "Beer & cider", "Wine", "Spirits", "Functional beverages", "Cannabis & hemp beverages"];
export const MARKETS = ["United States", "Canada", "United Kingdom", "European Union", "Australia & New Zealand"];
export const SOURCES = [
  { id: "fda", name: "Food & Drug Administration", short: "FDA", market: "United States", topic: "Ingredients, labeling & food safety", url: "https://www.fda.gov/food" },
  { id: "ttb", name: "Alcohol and Tobacco Tax and Trade Bureau", short: "TTB", market: "United States", topic: "Alcohol labeling, formulas & permits", url: "https://www.ttb.gov/" },
  { id: "fr", name: "Federal Register", short: "FR", market: "United States", topic: "Proposed and final federal rules", url: "https://www.federalregister.gov/" },
  { id: "hc", name: "Health Canada", short: "HC", market: "Canada", topic: "Food standards & product labeling", url: "https://www.canada.ca/en/health-canada.html" },
  { id: "fsa", name: "Food Standards Agency", short: "FSA", market: "United Kingdom", topic: "Food safety, guidance & alerts", url: "https://www.food.gov.uk/" },
  { id: "eu", name: "EUR-Lex", short: "EU", market: "European Union", topic: "European Union legislation", url: "https://eur-lex.europa.eu/" },
  { id: "fsanz", name: "Food Standards Australia New Zealand", short: "FSANZ", market: "Australia & New Zealand", topic: "Food standards & consultations", url: "https://www.foodstandards.gov.au/" },
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
  constructor() { super("This workspace changed in another tab. Reload the workspace to load the latest saved data before trying again."); }
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
export const SAMPLE_UPDATES = [
  { id: "label", title: "A labeling proposal appears in your market", source: "FDA", market: "United States", category: "Labeling", priority: "Review first", summary: "An illustrative proposal would change how a beverage label presents a nutrient claim. Compare the proposal with your product claims and identify where a label review would be needed.", action: "Review affected labels and record a decision with your regulatory reviewer.", url: "https://www.fda.gov/food/food-labeling-nutrition" },
  { id: "ingredient", title: "An ingredient consultation opens for comment", source: "FR", market: "United States", category: "Ingredients", priority: "Watch", summary: "This sample consultation demonstrates how an ingredient mentioned in your portfolio could be surfaced for review. It is invented and does not describe a current proceeding.", action: "Check whether the ingredient is used in your portfolio and whether a response is appropriate.", url: "https://www.federalregister.gov/" },
  { id: "alcohol", title: "Alcohol label guidance is revised", source: "TTB", market: "United States", category: "Alcohol", priority: "Review first", summary: "An invented guidance change shows how alcohol-specific updates could reach your team. A qualified reviewer must verify actual guidance before deciding what to change.", action: "Compare your label approval workflow with the primary source.", url: "https://www.ttb.gov/" },
  { id: "canada", title: "A food standard changes in a second market", source: "HC", market: "Canada", category: "Standards", priority: "Watch", summary: "This synthetic example illustrates cross-market monitoring. It does not describe an actual change to Canadian food standards.", action: "Assign a reviewer for products sold in this market.", url: "https://www.canada.ca/en/health-canada.html" },
];
export const PLAN_FEATURES = ["A workspace for your beverage portfolio", "Market and source selection", "A prioritized review queue", "Briefing export", "Saved review decisions"];
export function briefingText(workspace: Workspace): string {
  return [`${BRAND} | ${workspace.company || "Your workspace"}`, "Preview briefing. All regulatory updates below are synthetic examples, not current regulatory information.", `Markets: ${workspace.markets.join(", ") || "Not selected"}`, `Products: ${workspace.products.map(p => p.name).join(", ") || "No products added"}`, ...SAMPLE_UPDATES.map(u => `${u.title}\n${u.summary}\nSuggested review: ${u.action}\nExample source homepage: ${u.url}`), "For human review. Not legal advice. No live monitoring or email delivery is active in this preview."].join("\n\n");
}
export function downloadText(filename: string, content: string, type = "text/plain") {
  const url = URL.createObjectURL(new Blob([content], { type })); const a = document.createElement("a");
  a.href = url; a.download = filename; a.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
