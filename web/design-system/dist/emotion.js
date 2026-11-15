import createCache from "@emotion/cache";
const LAYER_STATEMENT = /^@layer\s+[^{]*$/;
function adoptedSheetClass(doc) {
  const shared = { main: null };
  const Sheet = doc.defaultView?.CSSStyleSheet ?? CSSStyleSheet;
  return class AdoptedSheet {
    key;
    nonce;
    container;
    isSpeedy = true;
    before = null;
    ctr = 0;
    sheet = new Sheet();
    global;
    // Emotion's Global component flushes a sheet before re-inserting only when it has tags.
    marker = [{ nextElementSibling: null }];
    constructor(options) {
      this.key = options.key;
      this.nonce = options.nonce;
      this.container = options.container;
      this.global = options.key.endsWith("-global");
      if (!this.global) shared.main = this.sheet;
    }
    get tags() {
      return this.ctr > 0 ? this.marker : [];
    }
    hydrate() {
    }
    insert(rule) {
      this.attach();
      try {
        this.sheet.insertRule(rule, this.sheet.cssRules.length);
      } catch {
      }
      this.ctr += 1;
    }
    /** Empties the sheet and takes it off the document, so nothing outlives a flushed cache (a plugin unloading). */
    flush() {
      this.sheet.replaceSync("");
      this.ctr = 0;
      doc.adoptedStyleSheets = doc.adoptedStyleSheets.filter((s) => s !== this.sheet);
    }
    attach() {
      const sheets = [...doc.adoptedStyleSheets];
      if (sheets.includes(this.sheet)) return;
      const at = this.global && shared.main ? sheets.indexOf(shared.main) : -1;
      if (at >= 0) sheets.splice(at, 0, this.sheet);
      else sheets.push(this.sheet);
      doc.adoptedStyleSheets = sheets;
    }
  };
}
function wrapInsert(cache, layer, specificity) {
  const repeat = typeof specificity === "number" && specificity > 1 ? Math.floor(specificity) : 1;
  const prefix = typeof specificity === "string" && specificity.trim() ? specificity.trim() : "";
  if (!layer && repeat === 1 && !prefix) return cache;
  const insert = cache.insert;
  cache.insert = (...args) => {
    const [selector, serialized] = args;
    if (layer && !LAYER_STATEMENT.test(serialized.styles)) serialized.styles = `@layer ${layer} {${serialized.styles}}`;
    if (selector) args[0] = prefix ? `${prefix} ${selector}` : selector.repeat(repeat);
    return insert(...args);
  };
  return cache;
}
function createCspEmotionCache({ key = "mui", layer = "mui", document: target, specificity } = {}) {
  const doc = target ?? (typeof document === "undefined" ? void 0 : document);
  const cache = createCache({ key, ...doc && doc !== globalThis.document && doc.head ? { container: doc.head } : {} });
  if (doc && "adoptedStyleSheets" in doc) {
    const Sheet = adoptedSheetClass(doc);
    cache.sheet = new Sheet({ key });
  }
  return wrapInsert(cache, layer, specificity);
}
function createServerEmotionCache({ key = "mui", layer = "mui", specificity } = {}) {
  return wrapInsert(createCache({ key }), layer, specificity);
}
function disposeCspEmotionCache(cache) {
  cache.sheet.flush();
  cache.inserted = {};
  cache.registered = {};
}
export {
  createCspEmotionCache,
  createServerEmotionCache,
  disposeCspEmotionCache
};
//# sourceMappingURL=emotion.js.map