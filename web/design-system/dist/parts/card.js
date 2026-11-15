"use client";
import { jsx } from "react/jsx-runtime";
import Card from "@mui/material/Card";
import { createPart } from "./core.js";
const card = {
  material: "Card",
  render: ({ props, children, variant }) => /* @__PURE__ */ jsx(Card, { variant: variant === "elevation" ? "elevation" : "outlined", ...props, children })
};
const CardPart = /* @__PURE__ */ createPart([card]);
export {
  CardPart,
  card
};
//# sourceMappingURL=card.js.map