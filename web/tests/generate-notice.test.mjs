// The line shown after Generate on the Newsletters and Documents pages.
// Run with: node --test web/tests/ (Node 22.18 or newer strips the types).

import assert from "node:assert/strict";
import { test } from "node:test";

import { generateNotice } from "../src/lib/generate-notice.ts";

test("a notice from the server is shown instead of Generated", () => {
  const notice = "Nothing in this period gives the language model anything to write from.";
  assert.equal(generateNotice({ dropped: [], notice }), notice);
  assert.equal(generateNotice({ dropped: ["passage 1: x"], notice }), notice);
});

test("without a notice the page says the copy was generated", () => {
  assert.match(generateNotice({ dropped: [], notice: "" }), /^Generated\. Check each passage/);
  assert.match(generateNotice({ dropped: [] }), /^Generated\./);
});
