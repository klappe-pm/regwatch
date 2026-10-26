// The Documents and Newsletters pages: a failed status request shows an error, not Loading.
// Run with: node --test web/tests/ (Node 22.18 or newer strips the types).

import assert from "node:assert/strict";
import { test } from "node:test";

import { premiumView, viewQuery } from "../src/lib/premium-view.ts";

test("a second Generate loads the new copy, so the query changes", () => {
  const first = viewQuery("since=7", true, 1);
  const second = viewQuery("since=7", true, 2);
  assert.notEqual(first, second);
  assert.ok(first.startsWith("since=7&generated=1"));
});

test("without generated copy the query is the plain one", () => {
  assert.equal(viewQuery("kind=digest&tier=v2", false, 3), "kind=digest&tier=v2");
});

test("a failed status request is an error, not loading", () => {
  assert.equal(premiumView(null, "The server stopped."), "error");
});

test("no status and no error yet is loading", () => {
  assert.equal(premiumView(null, null), "loading");
});

test("a status decides locked or open, even after a failed refresh", () => {
  assert.equal(premiumView({ premium: false }, null), "locked");
  assert.equal(premiumView({ premium: true }, null), "open");
  assert.equal(premiumView({ premium: true }, "The server stopped."), "open");
});
