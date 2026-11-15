"use client";
import { useDesignSpec } from "../spec-context.js";
import { partProps } from "../styles.js";
function useParts(names, ...extra) {
  return partProps(useDesignSpec("useParts"), names, ...extra);
}
export {
  useParts
};
//# sourceMappingURL=use-parts.js.map