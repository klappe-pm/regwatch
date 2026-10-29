// The Emotion cache the pages use in the browser.
//
// The local server sends `style-src 'self'`: no inline <style> element and no style attribute may
// apply. Emotion normally writes Material UI's styles into <style> elements, which that policy blocks.
// This cache writes them into constructed style sheets adopted by the document instead, which the
// policy does not cover, so the pages keep the strict policy. The server-rendered styles are moved
// into a style sheet file by scripts/postbuild.mjs. Every rule goes into the `mui` cascade layer, so
// the plain style sheets in styles/ win over Material UI without specificity fights.
import createCache, { type EmotionCache } from "@emotion/cache";

const LAYER_ORDER = /^@layer\s+(?:[^{]*?)$/;

interface SheetOptions {
  key: string;
  nonce?: string;
  container?: Node;
  speedy?: boolean;
}

// The main sheet of the cache; the sheets of global styles go before it, as Emotion orders them.
let main: CSSStyleSheet | null = null;

function attach(sheet: CSSStyleSheet, global: boolean): void {
  const sheets = [...document.adoptedStyleSheets];
  if (sheets.includes(sheet)) return;
  const at = global && main ? sheets.indexOf(main) : -1;
  if (at >= 0) sheets.splice(at, 0, sheet);
  else sheets.push(sheet);
  document.adoptedStyleSheets = sheets;
}

function detach(sheet: CSSStyleSheet): void {
  document.adoptedStyleSheets = document.adoptedStyleSheets.filter((s) => s !== sheet);
}

/** The StyleSheet interface Emotion and its Global component use, backed by a constructed sheet. */
class AdoptedSheet {
  key: string;
  nonce?: string;
  container?: Node;
  isSpeedy = true;
  before: Element | null = null;
  ctr = 0;
  private readonly sheet = new CSSStyleSheet();
  private readonly global: boolean;
  // Emotion's Global component flushes a sheet before re-inserting only when it has tags.
  private readonly marker = [{ nextElementSibling: null }] as unknown as Element[];

  constructor(options: SheetOptions) {
    this.key = options.key;
    this.nonce = options.nonce;
    this.container = options.container;
    this.global = options.key.endsWith("-global");
    if (!this.global) main = this.sheet;
  }

  get tags(): Element[] {
    return this.ctr > 0 ? this.marker : [];
  }

  hydrate(): void {
    // No server-rendered <style> element is left in the page to take over.
  }

  insert(rule: string): void {
    attach(this.sheet, this.global);
    try {
      this.sheet.insertRule(rule, this.sheet.cssRules.length);
    } catch {
      // A rule for another browser (a vendor-prefixed selector) is refused; Emotion ignores it too.
    }
    this.ctr += 1;
  }

  flush(): void {
    this.sheet.replaceSync("");
    this.ctr = 0;
    if (this.global) detach(this.sheet);
  }
}

function inLayer(cache: EmotionCache): EmotionCache {
  const insert = cache.insert;
  cache.insert = (...args: Parameters<EmotionCache["insert"]>) => {
    if (!LAYER_ORDER.test(args[1].styles)) args[1].styles = `@layer mui {${args[1].styles}}`;
    return insert(...args);
  };
  return cache;
}

let browserCache: EmotionCache | null = null;

/** The cache for this browser page, created once. */
export function browserEmotionCache(): EmotionCache {
  if (browserCache) return browserCache;
  const cache = createCache({ key: "mui" });
  if (typeof document !== "undefined" && "adoptedStyleSheets" in document) {
    (cache as unknown as { sheet: AdoptedSheet }).sheet = new AdoptedSheet({ key: "mui" });
  }
  browserCache = inLayer(cache);
  return browserCache;
}

/** The cache for rendering a page at build time; its styles are extracted into the page. */
export function serverEmotionCache(): EmotionCache {
  return inLayer(createCache({ key: "mui" }));
}
