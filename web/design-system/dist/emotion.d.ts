import { EmotionCache } from '@emotion/cache';

interface CspEmotionCacheOptions {
    /** Emotion cache key (class name prefix). Default 'mui'. */
    key?: string;
    /** Cascade layer for every rule, or false for none. Default 'mui'. */
    layer?: string | false;
    /**
     * The document whose adoptedStyleSheets receive the styles. Default: the global document. Pass a popout window's
     * document (Obsidian's `containerEl.ownerDocument`) so its views get styles; give each document its own cache.
     */
    document?: Document;
    /**
     * Raise every rule above unlayered host CSS without a layer. A number repeats each class selector that many times
     * (`3`: `.mui-x.mui-x.mui-x`); a string is a selector put in front of every rule (`'.my-root'`: `.my-root .mui-x`).
     * Global styles (GlobalStyles, the baseline, the theme variables) keep their own selectors. Default: none.
     */
    specificity?: number | string;
}
/**
 * A browser Emotion cache that works under `style-src 'self'`: styles go into adopted constructed style sheets, inside
 * the `mui` layer. Create it once per page (module scope), or once per document, and pass it to Emotion's
 * CacheProvider. Where the browser has no adoptedStyleSheets (and on the server) it falls back to Emotion's normal
 * sheet, still layered.
 */
declare function createCspEmotionCache({ key, layer, document: target, specificity }?: CspEmotionCacheOptions): EmotionCache;
/**
 * The matching cache for server rendering (Next.js _document with documentGetInitialProps): the same key, layer and
 * specificity, so class names and selectors match the browser. Its <style data-emotion> output is what `ds csp`
 * extracts into files.
 */
declare function createServerEmotionCache({ key, layer, specificity }?: Omit<CspEmotionCacheOptions, 'document'>): EmotionCache;
/**
 * Emptied sheets for a cache made by createCspEmotionCache: every rule it adopted leaves the document. For a plugin
 * that unloads, or a popout window that closes.
 */
declare function disposeCspEmotionCache(cache: EmotionCache): void;

export { type CspEmotionCacheOptions, createCspEmotionCache, createServerEmotionCache, disposeCspEmotionCache };
