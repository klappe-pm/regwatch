"use client";
import { Fragment, jsx } from "react/jsx-runtime";
import { createContext, useContext, useMemo } from "react";
import Box from "@mui/material/Box";
import { useCopy } from "../copy.js";
import { useDesignSpec } from "../spec-context.js";
import { partSx, partTokens } from "../styles.js";
const PartRegistryContext = createContext(/* @__PURE__ */ new Map());
function PartRegistry({ parts, children }) {
  const parent = useContext(PartRegistryContext);
  const value = useMemo(() => {
    if (!parts.length) return parent;
    const map = new Map(parent);
    for (const r of parts) map.set(r.material, r);
    return map;
  }, [parent, parts]);
  return /* @__PURE__ */ jsx(PartRegistryContext.Provider, { value, children });
}
const CONTAINERS = /* @__PURE__ */ new Set(["Card", "AppBar", "Paper", "Table", "TableHead", "TableBody", "TableRow", "List"]);
const BUTTON_LIKE = /* @__PURE__ */ new Set(["Button", "IconButton", "ButtonBase"]);
const ENTRY = {
  Button: "button",
  IconButton: "icon-button",
  ButtonBase: "button-base",
  Link: "link",
  TextField: "text-field",
  Chip: "chip",
  Tab: "tab",
  Card: "card",
  AppBar: "app-bar",
  ListItemButton: "list-item-button",
  Typography: "typography",
  Checkbox: "checkbox",
  Switch: "switch",
  Table: "table",
  TableHead: "table",
  TableBody: "table",
  TableRow: "table",
  TableCell: "table",
  Paper: "paper",
  List: "list",
  ListItem: "list",
  InputBase: "input-base",
  NativeSelect: "native-select",
  Alert: "alert",
  CircularProgress: "circular-progress",
  FormLabel: "form-label"
};
const RENDERER_NAME = (comp) => comp === "Switch" ? "switchControl" : comp.charAt(0).toLowerCase() + comp.slice(1);
const warned = /* @__PURE__ */ new Set();
function warnOnce(message) {
  if (process.env.NODE_ENV === "production" || warned.has(message)) return;
  warned.add(message);
  console.warn(message);
}
function createPart(renderers) {
  const own = new Map(renderers.map((r) => [r.material, r]));
  function Part({ name, children, labelKey, sx, unlabeled = false, modifiers, ...rest }) {
    const spec = useDesignSpec(`<Part name="${name}">`);
    const t = useCopy();
    const registry = useContext(PartRegistryContext);
    const c = spec.components[name];
    const mods = (modifiers ?? []).filter(Boolean);
    const dataPart = partTokens([name, ...mods], rest["data-part"]);
    if (!c) {
      warnOnce(`No component "${name}" in DESIGN.md.`);
      return /* @__PURE__ */ jsx(Box, { ...rest, "data-part": dataPart, "data-component": name, children });
    }
    for (const m of mods) if (!spec.components[m]) warnOnce(`No modifier component "${m}" in DESIGN.md.`);
    const key = labelKey ?? c.label;
    const label = children ?? (key ? t(key) : null);
    const style = [partSx(spec, name), ...mods.map((m) => partSx(spec, m)), ...Array.isArray(sx) ? sx : sx ? [sx] : []];
    const [comp, variant] = c.material.split(":");
    const usesLabel = !CONTAINERS.has(comp) && rest.label === void 0;
    const props = { ...rest, "data-part": dataPart, "data-component": name, ...usesLabel && children == null && key ? { "data-copy-key": key } : {}, sx: style };
    if (BUTTON_LIKE.has(comp) && props.type === void 0 && props.href === void 0 && (props.component === void 0 || props.component === "button")) props.type = "button";
    const renderer = own.get(comp) ?? registry.get(comp);
    if (!renderer) {
      if (comp !== "none" && comp !== "Box") {
        const entry = ENTRY[comp];
        warnOnce(entry ? `Part "${name}" renders ${comp}, which has no renderer here. Register it: import { ${RENDERER_NAME(comp)} } from 'regwatch-design/parts/${entry}' and pass it to createPart, <PartRegistry parts={[...]}> or the provider's parts prop.` : `Part "${name}" renders ${comp}, which has no renderer. Register a PartRenderer for it.`);
      }
      const { type: _type, ...box } = props;
      return /* @__PURE__ */ jsx(Box, { ...comp === "none" || comp === "Box" ? props : box, children: children ?? label });
    }
    const copyText = () => key ? t(key) : null;
    return /* @__PURE__ */ jsx(Fragment, { children: renderer.render({ name, props, label, children, copyKey: children == null && key ? key : null, copyText, variant, unlabeled, spec }) });
  }
  return Part;
}
function controlProps({ inputProps, ...props }) {
  if (!inputProps) return props;
  const slotProps = props.slotProps ?? {};
  return { ...props, slotProps: { ...slotProps, input: { ...inputProps, ...slotProps.input ?? {} } } };
}
const textLabel = (label) => typeof label === "string" || typeof label === "number" ? String(label) : void 0;
export {
  PartRegistry,
  controlProps,
  createPart,
  textLabel
};
//# sourceMappingURL=core.js.map