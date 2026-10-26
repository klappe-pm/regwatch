// The Settings preview names a document as regwatch.toml's title format does.
// Run with: node --test web/tests/ (Node 22.18 or newer strips the types).

import assert from "node:assert/strict";
import { test } from "node:test";

import { designTitle, sampleTitle } from "../src/lib/design-title.ts";

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
  assert.equal(sampleTitle("{title}", "2026-10-19", "Pantry Co"), "Pantry Co regulatory briefing");
  assert.equal(sampleTitle("{organisation}: {title}", "2026-10-19", "Pantry Co"), "Pantry Co: Regulatory briefing");
  assert.equal(
    sampleTitle("{organisation} | {title} | {date}", "2026-10-19", ""),
    "Your organisation | Regulatory briefing | 2026-10-19",
  );
});
