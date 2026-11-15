"use client";
import { jsx } from "react/jsx-runtime";
import Link from "@mui/material/Link";
import { createPart } from "./core.js";
const link = {
  material: "Link",
  render: ({ props, label }) => /* @__PURE__ */ jsx(Link, { underline: "hover", ...props, children: label })
};
const LinkPart = /* @__PURE__ */ createPart([link]);
export {
  LinkPart,
  link
};
//# sourceMappingURL=link.js.map