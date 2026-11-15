"use client";
import { appBar } from "../parts/app-bar.js";
import { button } from "../parts/button.js";
import { card } from "../parts/card.js";
import { checkbox } from "../parts/checkbox.js";
import { chip } from "../parts/chip.js";
import { createPart } from "../parts/core.js";
import { link } from "../parts/link.js";
import { listItemButton } from "../parts/list-item-button.js";
import { switchControl } from "../parts/switch.js";
import { tab } from "../parts/tab.js";
import { textField } from "../parts/text-field.js";
import { typography } from "../parts/typography.js";
import { partProps, partSx } from "../styles.js";
import { useParts } from "../parts/use-parts.js";
import { PartRegistry, createPart as createPart2 } from "../parts/core.js";
const Part = /* @__PURE__ */ createPart([button, link, textField, chip, tab, card, appBar, listItemButton, typography, checkbox, switchControl]);
export {
  Part,
  PartRegistry,
  createPart2 as createPart,
  partProps,
  partSx,
  useParts
};
//# sourceMappingURL=Part.js.map