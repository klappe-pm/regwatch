"use client";
import { jsx } from "react/jsx-runtime";
import FormControlLabel from "@mui/material/FormControlLabel";
import { controlProps } from "./core.js";
const CONTROL_PROPS = ["checked", "defaultChecked", "onChange", "inputProps", "inputRef", "slotProps", "slots", "size", "color", "name", "value", "required", "id", "icon", "checkedIcon", "indeterminate", "edge"];
function splitControl(props) {
  const control = {};
  const label = {};
  for (const [k, v] of Object.entries(props)) (CONTROL_PROPS.includes(k) ? control : label)[k] = v;
  if (props.disabled !== void 0) control.disabled = props.disabled;
  return { control: controlProps(control), label };
}
function controlRenderer(material, Control) {
  return {
    material,
    render: ({ props, label, unlabeled }) => {
      if (unlabeled || label == null) {
        const { "data-copy-key": _key, ...own } = props;
        return /* @__PURE__ */ jsx(Control, { ...controlProps(own) });
      }
      const { control, label: wrapper } = splitControl(props);
      return /* @__PURE__ */ jsx(FormControlLabel, { control: /* @__PURE__ */ jsx(Control, { ...control }), label, ...wrapper });
    }
  };
}
export {
  controlRenderer
};
//# sourceMappingURL=control.js.map