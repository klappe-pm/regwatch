// The line shown after Generate on the Newsletters and Documents pages.
// Run with: node --test web/tests/ (Node 22.18 or newer strips the types).

import assert from "node:assert/strict";
import { test } from "node:test";

import { copyNotice, generateNotice } from "../src/lib/generate-notice.ts";

test("copying HTML with an inline logo warns that pasting drops it", () => {
  const html = '<img src="data:image/png;base64,AAAA" alt="Pantry">';
  assert.match(copyNotice("HTML", html), /drops the logo/);
  assert.equal(copyNotice("HTML", "<p>no logo</p>"), "Copied the HTML.");
  assert.equal(copyNotice("text", html), "Copied the text.");
});

test("a notice from the server is shown instead of Generated", () => {
  const notice = "Nothing in this period gives the language model anything to write from.";
  assert.equal(generateNotice({ dropped: [], notice }), notice);
  assert.equal(generateNotice({ dropped: ["passage 1: x"], notice }), notice);
});

test("dropped passages are counted in words and given their own reasons", () => {
  const one = generateNotice({ dropped: ["passage 2: it uses the number 9, which no fact it cites holds"] });
  assert.match(one, /^Generated\. One passage was left out: passage 2: it uses the number 9/);
  const two = generateNotice({ dropped: ["passage 1: a", "passage 3: b"] });
  assert.match(two, /^Generated\. 2 passages were left out: passage 1: a; passage 3: b\./);
  assert.doesNotMatch(one + two, /\(s\)|facts they were not given/);
});

test("without a notice the page says the copy was generated", () => {
  assert.match(generateNotice({ dropped: [], notice: "" }), /^Generated\. Check each passage/);
  assert.match(generateNotice({ dropped: [] }), /^Generated\./);
});
