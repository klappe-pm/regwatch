// The line shown after Generate on the Newsletters and Documents pages. The sentences are copy entries under
// global.labels.generate, read by key, so a hub edit to their wording keeps these checks.
// Run with: node --test web/tests/ (Node 22.18 or newer strips the types).

import assert from "node:assert/strict";
import { test } from "node:test";

import { copyNotice, generateNotice } from "../src/lib/generate-notice.ts";
import { copyText } from "./design-values.mjs";

const g = (key, vars) => copyText(`global.labels.generate.${key}`, vars);

test("copying HTML with an inline logo warns that pasting drops it", () => {
  const html = '<img src="data:image/png;base64,AAAA" alt="Pantry">';
  assert.equal(copyNotice("HTML", html), g("copied-html-logo"));
  assert.equal(copyNotice("HTML", "<p>no logo</p>"), g("copied-html"));
  assert.equal(copyNotice("text", html), g("copied-text"));
});

test("a notice from the server is shown instead of Generated", () => {
  const notice = "Nothing in this period gives the language model anything to write from.";
  assert.equal(generateNotice({ dropped: [], notice }), notice);
  assert.equal(generateNotice({ dropped: ["passage 1: x"], notice }), notice);
});

test("dropped passages are counted in words and given their own reasons", () => {
  const reason = "passage 2: it uses the number 9, which no fact it cites holds";
  assert.equal(generateNotice({ dropped: [reason] }), g("left-out", { what: g("one-left-out"), reasons: reason }));
  const two = generateNotice({ dropped: ["passage 1: a", "passage 3: b"] });
  assert.equal(two, g("left-out", { what: g("many-left-out", { count: 2 }), reasons: "passage 1: a; passage 3: b" }));
  assert.doesNotMatch(two, /\(s\)/);
});

test("without a notice the page says the copy was generated", () => {
  assert.equal(generateNotice({ dropped: [], notice: "" }), g("generated"));
  assert.equal(generateNotice({ dropped: [] }), g("generated"));
});
