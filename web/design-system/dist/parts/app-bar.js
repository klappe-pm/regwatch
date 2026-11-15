"use client";
import { jsx } from "react/jsx-runtime";
import AppBar from "@mui/material/AppBar";
import { createPart } from "./core.js";
const appBar = {
  material: "AppBar",
  render: ({ props, children }) => /* @__PURE__ */ jsx(AppBar, { position: "static", elevation: 0, ...props, children })
};
const AppBarPart = /* @__PURE__ */ createPart([appBar]);
export {
  AppBarPart,
  appBar
};
//# sourceMappingURL=app-bar.js.map