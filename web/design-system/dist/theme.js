import { createTheme } from "@mui/material/styles";
import { partSx, typeStyle } from "./styles.js";
import { componentSx } from "./styles.js";
const TYPE_TO_VARIANT = {
  display: "h1",
  headline: "h2",
  title: "h3",
  subtitle: "h4",
  heading: "h4",
  lead: "subtitle1",
  body: "body1",
  small: "body2",
  caption: "caption",
  label: "subtitle2",
  action: "button",
  overline: "overline"
};
const MUI_VARIANTS = ["h1", "h2", "h3", "h4", "h5", "h6", "subtitle1", "subtitle2", "body1", "body2", "button", "caption", "overline"];
function scheme(roles) {
  const pick = (...keys) => keys.map((k) => roles[k]).find(Boolean);
  const tone = (main, on) => main ? { main, ...on ? { contrastText: on } : {} } : void 0;
  const palette = {};
  const primary = tone(pick("primary"), pick("on-primary"));
  const secondary = tone(pick("secondary", "secondary-container"), pick("on-secondary", "on-secondary-container"));
  const tertiary = tone(pick("tertiary", "tertiary-container"), pick("on-tertiary", "on-tertiary-container"));
  const error = tone(pick("error"), pick("on-error"));
  if (primary) palette.primary = primary;
  if (secondary) palette.secondary = secondary;
  if (tertiary) palette.info = tertiary;
  if (error) palette.error = error;
  const surface = pick("background", "surface");
  if (surface) palette.background = { default: surface, paper: pick("surface-container-lowest", "surface-container-low", "surface") ?? surface };
  const text = pick("on-surface", "on-background");
  if (text) palette.text = { primary: text, secondary: pick("on-surface-variant") ?? text };
  const divider = pick("outline-variant", "outline");
  if (divider) palette.divider = divider;
  return { palette };
}
function componentOverrides(spec) {
  const out = {};
  const claimed = /* @__PURE__ */ new Set();
  for (const [name, c] of Object.entries(spec.components)) {
    if (!c.global || c.base || c.modifier || c.material === "none") continue;
    const [comp, variant] = c.material.split(":");
    const slot = variant ?? "root";
    const key = `${comp}:${slot}`;
    if (claimed.has(key)) continue;
    claimed.add(key);
    const style = partSx(spec, name);
    const muiName = `Mui${comp}`;
    out[muiName] ??= { styleOverrides: {} };
    out[muiName].styleOverrides[slot] = { ...out[muiName].styleOverrides[slot] ?? {}, ...style };
  }
  return out;
}
const firstLength = (o, ...keys) => {
  for (const k of keys) if (o[k] !== void 0) return o[k];
  return Object.values(o)[0];
};
const px = (v) => v && /^-?\d*\.?\d+px$/.test(v) ? parseFloat(v) : v && /^-?\d*\.?\d+rem$/.test(v) ? parseFloat(v) * 16 : v && /^0$/.test(v) ? 0 : void 0;
function spacingUnit(spec) {
  return px(spec.spacingUnit) || px(spec.spacing.base) || 8;
}
const BOX_SIZING = {
  "details::details-content": { boxSizing: "inherit" },
  "details > *": { boxSizing: "border-box" },
  "select option, select optgroup": { boxSizing: "border-box" }
};
const SCOPED_BOX_SIZING = Object.fromEntries(Object.entries(BOX_SIZING).map(([sel, v]) => [sel.split(", ").map((s) => `& ${s}`).join(", "), v]));
function baselineOverrides(user, scoped) {
  const ours = scoped ? { root: SCOPED_BOX_SIZING } : BOX_SIZING;
  const u = user ?? {};
  if (u.styleOverrides !== void 0 && (typeof u.styleOverrides !== "object" || u.styleOverrides === null)) return u;
  const theirs = u.styleOverrides ?? {};
  const merged = { ...ours, ...theirs };
  if (scoped && theirs.root && typeof theirs.root === "object") merged.root = { ...ours.root, ...theirs.root };
  return { ...u, styleOverrides: merged };
}
function createDesignTheme(spec, overrides = {}, scope) {
  const typography = {};
  const body = spec.typography.body ?? Object.values(spec.typography)[0];
  if (body?.fontFamily) typography.fontFamily = body.fontFamily;
  const variantMapping = {};
  for (const [name, t] of Object.entries(spec.typography)) {
    const variant = MUI_VARIANTS.includes(name) ? name : TYPE_TO_VARIANT[name];
    if (variant && !typography[variant]) typography[variant] = variant === "button" ? { textTransform: "none", ...typeStyle(t) } : typeStyle(t);
    typography[name] = typeStyle(t);
    if (!MUI_VARIANTS.includes(name)) variantMapping[name] = variant && /^h\d$/.test(variant) ? variant : "p";
  }
  if (!typography.button) typography.button = { textTransform: "none" };
  const radius = px(firstLength(spec.rounded, "default", "medium", "regular", "small", "square"));
  const space = spacingUnit(spec);
  const userComponents = overrides.components ?? {};
  return createTheme({
    cssVariables: {
      colorSchemeSelector: scope?.colorSchemeSelector ?? "data-theme",
      nativeColor: true,
      ...scope?.rootSelector ? { rootSelector: scope.rootSelector, cssVarPrefix: scope.cssVarPrefix ?? "ds-mui" } : {}
    },
    colorSchemes: { light: scheme(spec.roles), ...spec.rolesDark ? { dark: scheme(spec.rolesDark) } : {} },
    typography,
    ...radius !== void 0 ? { shape: { borderRadius: radius } } : {},
    spacing: space,
    ...overrides,
    components: {
      MuiTypography: { defaultProps: { variantMapping } },
      ...componentOverrides(spec),
      ...userComponents,
      MuiCssBaseline: baselineOverrides(userComponents.MuiCssBaseline, false),
      MuiScopedCssBaseline: baselineOverrides(userComponents.MuiScopedCssBaseline, true)
    }
  });
}
export {
  componentSx,
  createDesignTheme,
  spacingUnit
};
//# sourceMappingURL=theme.js.map