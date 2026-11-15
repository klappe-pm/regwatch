// The Settings preview names a document as regwatch.toml's title format does.
// Run with: node --test web/tests/ (Node 22.18 or newer strips the types).

import assert from "node:assert/strict";
import { test } from "node:test";

import { designTitle, sampleTitle } from "../src/lib/design-title.ts";
import { copyText } from "./design-values.mjs";

// The sample title and the stand-in organisation are copy entries; the format strings are regwatch.toml input.
const sample = (organisation) => copyText("global.labels.design-title.sample-title", { organisation });

test("a leading organisation is not named twice", () => {
  assert.equal(
    designTitle("{organisation}: {title}", "Pantry Co. regulatory newsletter", "2026-10-19", "Pantry Co."),
    "Pantry Co.: Regulatory newsletter",
  );
  assert.equal(designTitle("{organisation}: {title}", "Pantryhouse digest", "d", "Pantry"), "Pantry: Pantryhouse digest");
  assert.equal(designTitle("{title} ({date})", "Pantry digest", "2026-10-19", "Pantry"), "Pantry digest (2026-10-19)");
  assert.equal(designTitle("{organisation}: {title}", "Pantry", "d", "Pantry"), "Pantry: Pantry");
});

test("the preview shows a realistic briefing title", () => {
  const own = copyText("global.labels.design-title.your-organisation");
  const once = (text, name) => text.toLowerCase().split(name.toLowerCase()).length - 1 === 1;
  assert.equal(sampleTitle("{title}", "2026-10-19", "Pantry Co"), sample("Pantry Co"));
  const named = sampleTitle("{organisation}: {title}", "2026-10-19", "Pantry Co");
  assert.ok(named.startsWith("Pantry Co: ") && once(named, "Pantry Co"), named);
  const unnamed = sampleTitle("{organisation} | {title} | {date}", "2026-10-19", "");
  assert.ok(unnamed.startsWith(`${own} | `) && unnamed.endsWith(" | 2026-10-19") && once(unnamed, own), unnamed);
});
