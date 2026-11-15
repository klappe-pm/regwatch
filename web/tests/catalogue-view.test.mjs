// The Sources page layout: a search shows the server's ranking as one flat list.
// Run with: node --test web/tests/ (Node 22.18 or newer strips the types).

import assert from "node:assert/strict";
import { test } from "node:test";

import { RANKED_GROUP, catalogueGroups } from "../src/lib/catalogue-view.ts";

const CATEGORIES = [
  ["regulation", "Regulation"],
  ["industry-news", "Industry News"],
];

// Ranked by the server: the industry news entry is the best match.
const RANKED = [
  { source_id: "news-best", category: "industry-news" },
  { source_id: "reg-second", category: "regulation" },
  { source_id: "news-third", category: "industry-news" },
];

test("a search keeps the ranked order in one flat list", () => {
  const groups = catalogueGroups(RANKED, "fda", CATEGORIES);
  assert.equal(groups.length, 1);
  assert.equal(groups[0].id, RANKED_GROUP);
  assert.equal(groups[0].ranked, true);
  assert.deepEqual(
    groups[0].entries.map((e) => e.source_id),
    ["news-best", "reg-second", "news-third"],
  );
});

test("an empty search box groups by category in the page's order", () => {
  const groups = catalogueGroups(RANKED, "   ", CATEGORIES);
  assert.deepEqual(
    groups.map((g) => [g.id, g.entries.map((e) => e.source_id)]),
    [
      ["regulation", ["reg-second"]],
      ["industry-news", ["news-best", "news-third"]],
    ],
  );
  assert.ok(groups.every((g) => !g.ranked));
});

test("a search with no result shows no group", () => {
  assert.deepEqual(catalogueGroups([], "nothing", CATEGORIES), []);
});

test("an unknown category is listed last, never dropped", () => {
  const groups = catalogueGroups(
    [...RANKED, { source_id: "odd", category: "something-new" }],
    "",
    CATEGORIES,
  );
  assert.deepEqual(groups.at(-1).entries.map((e) => e.source_id), ["odd"]);
});
