import { cssVariables } from "../src/core/index.mjs";
const TYPE_KEYS = ["fontFamily", "fontSize", "fontWeight", "lineHeight", "letterSpacing", "textTransform"];
function typeStyle(t) {
  const s = {};
  for (const k of TYPE_KEYS) if (t[k] !== void 0) s[k] = t[k];
  return s;
}
function styleSx(style) {
  const out = {};
  for (const [prop, v] of Object.entries(style)) {
    if (prop === "typography" && v && typeof v === "object") Object.assign(out, typeStyle(v));
    else if (v && typeof v === "object") out[prop] = styleSx(v);
    else if (prop === "textColor") out.color = v;
    else if (prop === "rounded") out.borderRadius = v;
    else out[prop] = v;
  }
  return out;
}
function componentSx(c) {
  return styleSx(c.style);
}
const STATE_SELECTOR = {
  hover: "&:hover",
  active: "&:active",
  pressed: "&:active",
  focus: "&.Mui-focusVisible",
  selected: "&.Mui-selected",
  disabled: "&.Mui-disabled"
};
const DISABLEABLE = /* @__PURE__ */ new Set(["Button", "IconButton", "ButtonBase", "ToggleButton", "Chip", "Tab", "ListItemButton", "MenuItem", "Fab"]);
const NO_FILL = /^(transparent|none|inherit|initial|unset)$/i;
const hasFill = (style) => ["backgroundColor", "background", "bgcolor"].some((k) => typeof style[k] === "string" && !NO_FILL.test(String(style[k]).trim()));
const hasBorder = (style) => Object.keys(style).some((k) => /^border(Color|Top|Right|Bottom|Left)?$|^outline(Color)?$/.test(k));
function onSurfaceMix(spec, pct) {
  const role = spec.roles["on-surface"] !== void 0 ? "on-surface" : spec.roles["on-background"] !== void 0 ? "on-background" : "on-surface";
  const ref = `var(--ds-role-${role}, ${spec.roles[role] ?? "currentColor"})`;
  return `color-mix(in srgb, ${ref} ${pct}%, transparent)`;
}
function disabledSx(spec, name) {
  const c = spec.components[name];
  if (!c) return null;
  const states = Object.values(spec.components).filter((s) => s.base === name && s.state);
  const explicit = states.find((s) => s.state === "disabled");
  const comp = c.material.split(":")[0];
  if (c.modifier || !DISABLEABLE.has(comp)) return explicit ? componentSx(explicit) : null;
  const base = componentSx(c);
  const out = { color: onSurfaceMix(spec, 38) };
  if (hasFill(base)) out.backgroundColor = onSurfaceMix(spec, 12);
  if (hasBorder(base)) out.borderColor = onSurfaceMix(spec, 12);
  if (base.boxShadow !== void 0) out.boxShadow = "none";
  if (comp === "Chip") out.opacity = 1;
  const selected = states.find((s) => s.state === "selected");
  if (selected && !hasFill(base) && hasFill(componentSx(selected))) out["&.Mui-selected"] = { backgroundColor: onSurfaceMix(spec, 12) };
  return explicit ? { ...out, ...componentSx(explicit) } : out;
}
function partSx(spec, name) {
  const c = spec.components[name];
  if (!c) return {};
  const sx = componentSx(c);
  for (const s of Object.values(spec.components)) {
    if (s.base === name && s.state && s.state !== "disabled") sx[STATE_SELECTOR[s.state] ?? `&:${s.state}`] = componentSx(s);
  }
  const disabled = disabledSx(spec, name);
  if (disabled) sx[STATE_SELECTOR.disabled] = disabled;
  return sx;
}
function partTokens(names, existing) {
  const list = [...Array.isArray(names) ? names : [names], ...typeof existing === "string" ? existing.split(/\s+/) : []];
  return [...new Set(list.filter(Boolean))].join(" ");
}
function partProps(spec, names, ...extra) {
  const list = Array.isArray(names) ? names : [names];
  return { "data-part": partTokens(list), sx: [...list.map((n) => partSx(spec, n)), ...extra.filter((x) => Boolean(x))] };
}
function scopedTokenCss(spec, { scope, colorSchemeNode = "scope", attribute = "data-theme" }) {
  return cssVariables(spec, { selector: `#${scope}`, colorSchemeTarget: colorSchemeNode === "root" ? "ancestor" : "self", attribute });
}
export {
  STATE_SELECTOR,
  componentSx,
  disabledSx,
  partProps,
  partSx,
  partTokens,
  scopedTokenCss,
  typeStyle
};
//# sourceMappingURL=styles.js.map