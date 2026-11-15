"use client";
import { Fragment, jsx, jsxs } from "react/jsx-runtime";
import { useLayoutEffect, useMemo, useState } from "react";
import CssBaseline from "@mui/material/CssBaseline";
import GlobalStyles from "@mui/material/GlobalStyles";
import ScopedCssBaseline from "@mui/material/ScopedCssBaseline";
import { StyledEngineProvider, ThemeProvider, useColorScheme } from "@mui/material/styles";
import { cssVariables } from "../src/core/index.mjs";
import { CopyProvider } from "./copy.js";
import { PartRegistry } from "./parts/core.js";
import { SpecContext, useDesignSpec } from "./spec-context.js";
import { scopedTokenCss } from "./styles.js";
import { createDesignTheme } from "./theme.js";
const TAILWIND_LAYER_ORDER = "@layer theme, base, mui, components, utilities;";
function ColorModeSync({ mode }) {
  const { mode: current, setMode } = useColorScheme();
  useLayoutEffect(() => {
    if (current !== mode) setMode(mode);
  }, [mode, current, setMode]);
  return null;
}
function schemeSelectors(scope, node, selector) {
  if (selector.includes("%s")) return { mui: selector, tokens: selector };
  const attribute = selector === "data" ? "data-%s" : selector;
  if (!scope) return { mui: attribute, tokens: attribute };
  const on = `[${attribute}="%s"]`;
  return { mui: node === "scope" ? `#${scope}${on}` : `${on} #${scope}`, tokens: attribute };
}
function DesignSystemProvider({
  spec,
  copy,
  onMissing,
  children,
  themeOptions,
  baseline = true,
  scope,
  colorMode,
  persistColorScheme = false,
  colorSchemeNode,
  colorSchemeSelector = "data-theme",
  injectTokens,
  parts,
  cssLayer = false
}) {
  const ownSelector = Boolean(themeOptions?.cssVariables?.colorSchemeSelector);
  const nodeKind = colorSchemeNode === void 0 ? scope && !ownSelector ? "scope" : "root" : colorSchemeNode === "scope" && scope ? "scope" : "root";
  const selectors = schemeSelectors(scope, nodeKind, colorSchemeSelector);
  const theme = useMemo(
    () => createDesignTheme(spec, themeOptions, scope ? { rootSelector: `#${scope}`, colorSchemeSelector: selectors.mui } : { colorSchemeSelector: selectors.mui }),
    [spec, themeOptions, scope, selectors.mui]
  );
  const tokenMode = injectTokens ?? (scope ? true : false);
  const tokens = useMemo(() => {
    if (!tokenMode) return null;
    if (!scope) return cssVariables(spec, { attribute: selectors.tokens });
    return scopedTokenCss(spec, { scope, colorSchemeNode: nodeKind, attribute: selectors.tokens });
  }, [spec, scope, tokenMode, nodeKind, selectors.tokens]);
  const [scopeEl, setScopeEl] = useState(null);
  const node = colorSchemeNode === null || typeof colorSchemeNode === "object" && colorSchemeNode !== null ? colorSchemeNode : nodeKind === "scope" ? scopeEl : void 0;
  const storage = persistColorScheme ? typeof persistColorScheme === "object" && persistColorScheme.key ? { modeStorageKey: persistColorScheme.key, colorSchemeStorageKey: persistColorScheme.colorSchemeKey ?? `${persistColorScheme.key}-scheme` } : {} : { storageManager: null };
  const tokenStyle = tokens == null ? null : tokenMode === "cache" ? /* @__PURE__ */ jsx(GlobalStyles, { styles: tokens }) : /* @__PURE__ */ jsx("style", { children: tokens });
  const body = /* @__PURE__ */ jsx(CopyProvider, { copy, onMissing, children: parts?.length ? /* @__PURE__ */ jsx(PartRegistry, { parts, children }) : children });
  const tree = /* @__PURE__ */ jsx(SpecContext.Provider, { value: spec, children: /* @__PURE__ */ jsxs(
    ThemeProvider,
    {
      theme,
      ...storage,
      ...colorMode ? { defaultMode: colorMode } : {},
      ...node !== void 0 ? { colorSchemeNode: node } : {},
      ...scope ? { disableNestedContext: true } : {},
      children: [
        cssLayer === "tailwind" ? /* @__PURE__ */ jsx(GlobalStyles, { styles: TAILWIND_LAYER_ORDER }) : null,
        colorMode && spec.rolesDark ? /* @__PURE__ */ jsx(ColorModeSync, { mode: colorMode }) : null,
        scope ? /* @__PURE__ */ jsxs(ScopedCssBaseline, { id: scope, ref: setScopeEl, enableColorScheme: true, children: [
          tokenStyle,
          body
        ] }) : /* @__PURE__ */ jsxs(Fragment, { children: [
          baseline ? /* @__PURE__ */ jsx(CssBaseline, { enableColorScheme: true }) : null,
          tokenStyle,
          body
        ] })
      ]
    }
  ) });
  return cssLayer ? /* @__PURE__ */ jsx(StyledEngineProvider, { enableCssLayer: true, children: tree }) : tree;
}
export {
  DesignSystemProvider,
  TAILWIND_LAYER_ORDER,
  useDesignSpec
};
//# sourceMappingURL=provider.js.map