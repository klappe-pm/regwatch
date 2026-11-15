"use client";
import { jsx } from "react/jsx-runtime";
import Chip from "@mui/material/Chip";
import { createPart } from "./core.js";
const chip = {
  material: "Chip",
  render: ({ props, label }) => /* @__PURE__ */ jsx(Chip, { label, ...props })
};
const ChipPart = /* @__PURE__ */ createPart([chip]);
export {
  ChipPart,
  chip
};
//# sourceMappingURL=chip.js.map