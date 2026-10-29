// Every visible string comes from the copy documents in docs/content-management-system/, which
// `ds sync` compiles to design/copy.json. A missing key throws, so a page cannot ship one.
// Free of React and of the "@/" alias, so `node --test` can load the modules that use it.
import { createCopy, type Translate } from "@klappe/design-system/core";

import copy from "../../design/copy.json" with { type: "json" };

export const copyMap = copy as Record<string, string>;

export const t: Translate = createCopy(copyMap, { onMissing: "throw" });

/** Every key under a prefix, in the order the copy documents sort them. */
export function keysUnder(prefix: string): string[] {
  return Object.keys(copyMap).filter((key) => key.startsWith(`${prefix}.`));
}
