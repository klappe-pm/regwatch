"use client";
import { jsx } from "react/jsx-runtime";
import ListItemButton from "@mui/material/ListItemButton";
import { createPart } from "./core.js";
const listItemButton = {
  material: "ListItemButton",
  render: ({ props, label }) => /* @__PURE__ */ jsx(ListItemButton, { ...props, children: label })
};
const ListItemButtonPart = /* @__PURE__ */ createPart([listItemButton]);
export {
  ListItemButtonPart,
  listItemButton
};
//# sourceMappingURL=list-item-button.js.map