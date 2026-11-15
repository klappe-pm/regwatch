"use client";
import { Fragment, jsx, jsxs } from "react/jsx-runtime";
import { createContext, Fragment as Fragment2, useContext, useMemo } from "react";
import { createCopy } from "../src/core/index.mjs";
const CopyContext = createContext(null);
const NO_PROVIDER = (who) => `${who} needs a CopyProvider or DesignSystemProvider above it, and none was found. Wrap the tree in <DesignSystemProvider spec={spec} copy={copy}> (or <CopyProvider copy={copy}>), give <T> a \`fallback\`, or call createCopy(copy) from regwatch-design/core outside React. If a provider is there, two copies of regwatch-design may be installed; check that the app resolves one.`;
function CopyProvider({ copy, children, onMissing }) {
  const t = useMemo(() => typeof copy === "function" ? copy : createCopy(copy, { onMissing }), [copy, onMissing]);
  return /* @__PURE__ */ jsx(CopyContext.Provider, { value: t, children });
}
function useCopy() {
  const t = useContext(CopyContext);
  if (!t) throw new Error(NO_PROVIDER("useCopy"));
  return t;
}
function Lines({ text }) {
  const parts = text.split(/<br\s*\/?>/i);
  return /* @__PURE__ */ jsx(Fragment, { children: parts.map((part, i) => /* @__PURE__ */ jsxs(Fragment2, { children: [
    i ? /* @__PURE__ */ jsx("br", {}) : null,
    part
  ] }, i)) });
}
function T({ k, vars, annotate = false, fallback }) {
  const t = useContext(CopyContext);
  if (!t) {
    if (fallback !== void 0) return /* @__PURE__ */ jsx(Fragment, { children: fallback });
    throw new Error(NO_PROVIDER(`<T k="${k}">`));
  }
  const text = t(k, vars);
  return annotate ? /* @__PURE__ */ jsx("span", { "data-copy-key": k, children: /* @__PURE__ */ jsx(Lines, { text }) }) : /* @__PURE__ */ jsx(Lines, { text });
}
export {
  CopyProvider,
  Lines,
  T,
  createCopy,
  useCopy
};
//# sourceMappingURL=copy.js.map