"use client";
import { jsx } from "react/jsx-runtime";
import TextField from "@mui/material/TextField";
import { createPart } from "./core.js";
const textField = {
  material: "TextField",
  render: ({ props, label, variant }) => /* @__PURE__ */ jsx(TextField, { variant: variant ?? "outlined", label, ...props })
};
const TextFieldPart = /* @__PURE__ */ createPart([textField]);
export {
  TextFieldPart,
  textField
};
//# sourceMappingURL=text-field.js.map