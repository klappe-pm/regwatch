// Every visible string comes from the copy documents. This checks, without a build, that every
// literal copy key the pages use exists in design/copy.json (which `ds sync` writes from
// docs/content-management-system/), that the copy is current with its documents, and that the
// shared modules read their words from it.
// Run with: node --test web/tests/ (Node 22.18 or newer strips the types).

import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { copyMap as compile } from "@klappe/design-system/core";

const web = fileURLToPath(new URL("..", import.meta.url));
const copy = JSON.parse(readFileSync(join(web, "design", "copy.json"), "utf8"));
const docs = join(web, "..", "docs", "content-management-system");

function walk(dir, test, out = []) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) walk(path, test, out);
    else if (test(path)) out.push(path);
  }
  return out;
}

const sources = [...walk(join(web, "src"), (p) => /\.tsx?$/.test(p)), ...walk(join(web, "pages"), (p) => p.endsWith(".tsx"))];

/** The literal keys a file looks up: t("..."), T k="...", and p("...") under the file's prefix. */
function keysIn(text) {
  const prefix = text.match(/const p = \([^)]*\) => t\(`([\w.-]+)\.\$\{key\}`/)?.[1];
  const keys = [];
  for (const m of text.matchAll(/\bt\("([\w.-]+)"/g)) keys.push(m[1]);
  for (const m of text.matchAll(/<T k="([\w.-]+)"/g)) keys.push(m[1]);
  if (prefix) for (const m of text.matchAll(/\bp\("([\w.-]+)"/g)) keys.push(`${prefix}.${m[1]}`);
  return keys;
}

test("design/copy.json is current with the copy documents", () => {
  const files = walk(docs, (p) => p.endsWith(".md"));
  const built = compile(files.map((p) => ({ doc: relative(docs, p).replace(/\.md$/, ""), markdown: readFileSync(p, "utf8") })));
  assert.deepEqual(built, copy, "run npm run sync in web/");
});

test("every literal copy key in the pages and parts exists", () => {
  const missing = [];
  let count = 0;
  for (const file of sources) {
    for (const key of keysIn(readFileSync(file, "utf8"))) {
      count += 1;
      if (!(key in copy)) missing.push(`${relative(web, file)}: ${key}`);
    }
  }
  assert.ok(count > 300, `found only ${count} keys; the scan is not reading the pages`);
  assert.deepEqual(missing, []);
});

test("no copy entry is empty", () => {
  assert.deepEqual(Object.entries(copy).filter(([, value]) => !value.trim()), []);
});

test("a missing key throws instead of showing the key", async () => {
  const { t } = await import("../src/lib/text.ts");
  assert.throws(() => t("pages.nowhere.missing"), /Missing copy/);
  assert.equal(t("global.preview-data.brand.home", { name: "Bev Watch" }), "Bev Watch home");
});

test("the shared modules read their words from the copy", async () => {
  const { SEVERITY, TIERS, outcome, cadence } = await import("../src/lib/labels.ts");
  assert.equal(SEVERITY["act-now"], copy["global.labels.severity.act-now"]);
  assert.deepEqual(TIERS.map(([, name]) => name), ["v1", "v2", "v3"].map((id) => copy[`global.labels.tiers.${id}`]));
  assert.equal(outcome(3), copy["global.labels.outcome.changes"]);
  assert.equal(outcome(9), "Exit 9");
  assert.equal(cadence("daily"), copy["global.labels.cadence.daily"]);
  const { SOURCES, SAMPLE_UPDATES, categoryName } = await import("../src/lib/bev-watch.ts");
  assert.equal(SOURCES[0].name, copy["global.preview-data.sources.fda.name"]);
  assert.equal(SAMPLE_UPDATES[0].title, copy["global.preview-data.updates.label.title"]);
  assert.equal(categoryName("Beer & cider"), copy["global.preview-data.categories.beer-cider"]);
});
