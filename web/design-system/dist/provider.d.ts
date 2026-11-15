import * as react from 'react';
import { ReactNode } from 'react';
import { ThemeOptions } from '@mui/material/styles';
import { PartRenderer } from './parts/core.js';
export { useDesignSpec } from './spec-context.js';
import { DesignSpec, CopyMap, Translate, OnMissing } from './types.js';

declare const TAILWIND_LAYER_ORDER = "@layer theme, base, mui, components, utilities;";
type ColorMode = 'light' | 'dark' | 'system';
type DesignSystemProviderProps = {
    spec: DesignSpec;
    /** The copy map, or a translate function already built with createCopy. */
    copy: CopyMap | Translate;
    /** What T and useCopy do with a missing key: 'key' (default) shows the key, 'throw' throws. Ignored when copy is a function. */
    onMissing?: OnMissing;
    children: ReactNode;
    themeOptions?: ThemeOptions;
    baseline?: boolean;
    /** Element id to scope the theme and token variables to. */
    scope?: string;
    /**
     * 'light' or 'dark' forces that scheme; 'system' follows the operating system. Changing the prop switches the
     * scheme. Without it the provider follows the system (or the stored choice with persistColorScheme).
     */
    colorMode?: ColorMode;
    /**
     * Remember the visitor's light or dark choice in localStorage. Off by default: sites promise no browser storage.
     * `{ key }` names the storage key for the mode (default 'mui-mode'); the color scheme is stored under `<key>-scheme`
     * unless `colorSchemeKey` names another. Pass the same key to InitColorSchemeScript (`modeStorageKey`).
     */
    persistColorScheme?: boolean | {
        key?: string;
        colorSchemeKey?: string;
    };
    /**
     * Which element gets the color-scheme attribute: 'scope' (the scope's element; the default when `scope` is set),
     * 'root' (the page's <html>; the default without a scope) or an element (a popout window's root, say). The dark
     * palette and the dark token roles follow the attribute on that element.
     */
    colorSchemeNode?: 'scope' | 'root' | Element | null;
    /**
     * The color-scheme attribute (default 'data-theme'), or a selector with %s for the scheme name (`.theme-%s`,
     * `[data-mode="%s"] #app`). design/ds.css switches on data-theme unless ds.config.json sets colorSchemeAttribute.
     */
    colorSchemeSelector?: string;
    /**
     * How the token variables (--ds-*) reach the page. true: an inline <style> element (the default with `scope`).
     * 'cache': through the Emotion cache in use, as global styles, so createCspEmotionCache adopts them as a constructed
     * style sheet (hosts that forbid <style> elements, such as Obsidian, or a strict style-src). false: not at all (the
     * default without a scope, where the app imports design/ds.css).
     */
    injectTokens?: boolean | 'cache';
    /** Part renderers for Material UI components the main Part does not render itself (Table, Alert and so on). */
    parts?: readonly PartRenderer[];
    /**
     * Put Material UI's styles in the `mui` cascade layer, so the app's own (unlayered) CSS wins over them without
     * specificity fights. true or 'mui': enable the layer. 'tailwind': also declare Tailwind v4's layer order
     * (theme, base, mui, components, utilities) so utilities beat Material UI. For the Next.js app router, pass
     * `options={{ enableCssLayer: true }}` to AppRouterCacheProvider instead, since it owns the Emotion cache there.
     */
    cssLayer?: boolean | 'mui' | 'tailwind';
};
declare function DesignSystemProvider({ spec, copy, onMissing, children, themeOptions, baseline, scope, colorMode, persistColorScheme, colorSchemeNode, colorSchemeSelector, injectTokens, parts, cssLayer, }: DesignSystemProviderProps): react.JSX.Element;

export { type ColorMode, DesignSystemProvider, type DesignSystemProviderProps, TAILWIND_LAYER_ORDER };
