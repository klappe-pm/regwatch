"use client";
import Switch from "@mui/material/Switch";
import { createPart } from "./core.js";
import { controlRenderer } from "./control.js";
const switchControl = /* @__PURE__ */ controlRenderer("Switch", Switch);
const SwitchPart = /* @__PURE__ */ createPart([switchControl]);
export {
  SwitchPart,
  switchControl
};
//# sourceMappingURL=switch.js.map