"use client";
import { jsx } from "react/jsx-runtime";
import Button from "@mui/material/Button";
import { createPart } from "./core.js";
const button = {
  material: "Button",
  render: ({ props, label, variant }) => /* @__PURE__ */ jsx(Button, { variant: variant ?? "contained", disableElevation: true, ...props, children: label })
};
const ButtonPart = /* @__PURE__ */ createPart([button]);
export {
  ButtonPart,
  button
};
//# sourceMappingURL=button.js.map