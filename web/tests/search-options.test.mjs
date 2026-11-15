// The global search: catalogue hits link by id, and a failed request shows its error.
// Run with: node --test web/tests/ (Node 22.18 or newer strips the types).

import assert from "node:assert/strict";
import { test } from "node:test";

import { searchNote, searchOptions } from "../src/lib/search-options.ts";
import { copyText } from "./design-values.mjs";

const RESULTS = {
  query: "fda",
  sources: [
    { source_id: "us-fda-recalls", name: "FDA Recalls & Alerts", jurisdiction: "us", mine: false },
    { source_id: "us-fda-warning", name: "FDA Warning Letters", jurisdiction: "us", mine: true },
  ],
  changes: [],
  obligations: [],
};

test("a catalogue hit links to the catalogue search by id, not by name", () => {
  const [catalogue, mine] = searchOptions(RESULTS);
  assert.equal(catalogue.href, "/sources/?catalogue=us-fda-recalls");
  assert.equal(mine.href, "/sources/?q=us-fda-warning");
});

test("a failed search shows the error instead of No matches", () => {
  assert.equal(searchNote("fda", 0, "The server stopped."), copyText("global.labels.search.failed", { error: "The server stopped." }));
  assert.equal(searchNote("fda", 0, null), copyText("global.labels.search.no-matches"));
  assert.equal(searchNote("  ", 0, "The server stopped."), copyText("global.labels.search.empty"));
  assert.equal(searchNote("fda", 2, null), null);
});
