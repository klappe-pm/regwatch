"use client";
import { jsx, jsxs } from "react/jsx-runtime";
import Box from "@mui/material/Box";
import Container from "@mui/material/Container";
import Link from "@mui/material/Link";
import Stack from "@mui/material/Stack";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import { Part } from "./Part.js";
import { useDesignSpec } from "../spec-context.js";
const space = (name, fallback) => `var(--ds-space-${name}, ${fallback})`;
function Page({ children, maxWidth = "lg", ...rest }) {
  return /* @__PURE__ */ jsx(Box, { component: "main", id: "main", ...rest, children: /* @__PURE__ */ jsx(Container, { maxWidth, sx: { px: space("gutter", "24px") }, children }) });
}
function Section({ children, tone = "surface", spacing = "section", ...rest }) {
  const bg = tone === "primary" ? "primary.main" : tone === "secondary" ? "secondary.main" : "transparent";
  const color = tone === "primary" ? "primary.contrastText" : tone === "secondary" ? "secondary.contrastText" : "inherit";
  return /* @__PURE__ */ jsx(Box, { component: "section", ...rest, sx: { py: space(spacing, "96px"), bgcolor: bg, color, ...rest.sx }, children });
}
function SiteHeader({ brand, brandHref = "/", links, action, linkComponent, navLabel = "Main navigation", skipLabel }) {
  const spec = useDesignSpec("SiteHeader");
  const navPart = spec.components["navigation-link"] ? "navigation-link" : null;
  return /* @__PURE__ */ jsxs(Box, { component: "header", children: [
    skipLabel ? /* @__PURE__ */ jsx(Link, { href: "#main", sx: { position: "absolute", left: -9999, "&:focus": { left: 16, top: 16, zIndex: 10 } }, children: skipLabel }) : null,
    /* @__PURE__ */ jsxs(Toolbar, { disableGutters: true, sx: { px: space("gutter", "24px"), minHeight: 72, gap: 3, flexWrap: "wrap" }, children: [
      /* @__PURE__ */ jsx(Link, { href: brandHref, component: linkComponent ?? "a", underline: "none", color: "inherit", sx: { typography: spec.typography.wordmark ? "wordmark" : "h6" }, children: brand }),
      /* @__PURE__ */ jsx(Stack, { component: "nav", "aria-label": navLabel, direction: "row", spacing: 3, sx: { ml: "auto", flexWrap: "wrap" }, children: links.map((l) => navPart ? /* @__PURE__ */ jsx(Part, { name: navPart, href: l.href, component: linkComponent ?? "a", "aria-current": l.current ? "page" : void 0, children: l.label }, l.href) : /* @__PURE__ */ jsx(Link, { href: l.href, component: linkComponent ?? "a", underline: "hover", color: "inherit", "aria-current": l.current ? "page" : void 0, children: l.label }, l.href)) }),
      action
    ] })
  ] });
}
function SiteFooter({ children, links = [], linkComponent }) {
  const spec = useDesignSpec("SiteFooter");
  const body = /* @__PURE__ */ jsx(Container, { maxWidth: "lg", sx: { py: space("wide", "40px"), px: space("gutter", "24px") }, children: /* @__PURE__ */ jsxs(Stack, { direction: { xs: "column", sm: "row" }, spacing: 3, sx: { justifyContent: "space-between" }, children: [
    /* @__PURE__ */ jsx(Typography, { component: "div", variant: "body2", children }),
    /* @__PURE__ */ jsx(Stack, { direction: "row", spacing: 3, component: "nav", sx: { flexWrap: "wrap" }, children: links.map((l) => /* @__PURE__ */ jsx(Link, { href: l.href, component: linkComponent ?? "a", color: "inherit", underline: "hover", children: l.label }, l.href)) })
  ] }) });
  return spec.components.footer ? /* @__PURE__ */ jsx(Part, { name: "footer", component: "footer", children: body }) : /* @__PURE__ */ jsx(Box, { component: "footer", children: body });
}
export {
  Page,
  Section,
  SiteFooter,
  SiteHeader
};
//# sourceMappingURL=layout.js.map