"use client";
import { jsx } from "react/jsx-runtime";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import { createPart } from "./core.js";
const tab = {
  material: "Tab",
  render: ({ props, label, name }) => /* @__PURE__ */ jsx(Tabs, { value: 0, "aria-label": typeof label === "string" ? label : name, slotProps: { indicator: { sx: { display: "none" } } }, children: /* @__PURE__ */ jsx(Tab, { value: 0, label, ...props }) })
};
const TabPart = /* @__PURE__ */ createPart([tab]);
export {
  TabPart,
  tab
};
//# sourceMappingURL=tab.js.map