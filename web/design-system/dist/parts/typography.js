"use client";
import { jsx } from "react/jsx-runtime";
import Typography from "@mui/material/Typography";
import { createPart } from "./core.js";
const typography = {
  material: "Typography",
  render: ({ props, label }) => /* @__PURE__ */ jsx(Typography, { ...props, children: label })
};
const TypographyPart = /* @__PURE__ */ createPart([typography]);
export {
  TypographyPart,
  typography
};
//# sourceMappingURL=typography.js.map