// The Settings page's colour check matches the one regwatch.toml is checked with.
// Run with: node --test web/tests/ (Node 22.18 or newer strips the types).

import assert from "node:assert/strict";
import { test } from "node:test";

import { colorWarning, contrastWithWhite, isHexColor } from "../src/lib/contrast.ts";

test("only #rrggbb is a colour", () => {
  assert.equal(isHexColor("#1d5a92"), true);
  assert.equal(isHexColor("#1D5A92"), true);
  for (const value of ["1d5a92", "#123", "#12345g", "red", "#1d5a92 "]) {
    assert.equal(isHexColor(value), false, value);
  }
});

test("the ratio is the WCAG ratio against white", () => {
  assert.equal(contrastWithWhite("#000000").toFixed(2), "21.00");
  assert.equal(contrastWithWhite("#ffffff").toFixed(2), "1.00");
  assert.equal(contrastWithWhite("#1d5a92").toFixed(2), "7.17");
  assert.equal(contrastWithWhite("#ffff00").toFixed(2), "1.07");
  assert.equal(contrastWithWhite("blue"), null);
});

test("a light colour or a bad value gets a warning, a dark one none", () => {
  assert.equal(colorWarning("Primary colour", "#1d5a92"), null);
  assert.match(colorWarning("Primary colour", "#ffff00"), /1\.07:1 against white/);
  assert.match(colorWarning("Accent colour", "#zzzzzz"), /#rrggbb/);
});
