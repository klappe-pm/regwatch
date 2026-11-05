// Reads the built files of both exports: the local application copied to regwatch/web by
// `npm run build`, and the public website written to web/dist by `npm run build:site`. Checks that
// every page, link, script and style sheet resolves inside its export, that no copy key shows as page
// text, and that every data-part names a part in design/spec.json, so the hub's usage scan finds it.
// Run with: npm run build && npm run build:site && npm run test:build
import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const web = fileURLToPath(new URL("../..", import.meta.url));
const copy = JSON.parse(readFileSync(join(web, "design", "copy.json"), "utf8"));
const spec = JSON.parse(readFileSync(join(web, "design", "spec.json"), "utf8"));

const EXPORTS = {
  local: {
    root: join(web, "..", "regwatch", "web"),
    pages: ["/", "/changes/", "/sources/", "/obligations/", "/briefings/", "/newsletters/", "/documents/", "/automations/", "/keys/", "/settings/"],
    hint: "run npm run build first",
  },
  site: {
    root: join(web, "dist"),
    pages: ["/", "/pricing/", "/privacy/", "/onboarding/", "/workspace/"],
    hint: "run npm run build:site first",
  },
};

// A reference that leaves the export: another origin, a fragment, inline data, or the local server's API.
const EXTERNAL = /^(?:[a-z][a-z0-9+.-]*:|\/\/|#)/i;
const SERVED = /^\/api(?:\/|$)/;

function files(root, extension) {
  return readdirSync(root, { recursive: true })
    .filter((name) => name.endsWith(extension))
    .map((name) => join(root, name));
}

/** The file a reference from `from` names inside `root`, or null when nothing there serves it. */
function resolve(root, from, reference) {
  const bare = reference.split(/[?#]/)[0];
  if (bare === "") return from;
  const base = bare.startsWith("/") ? join(root, bare) : join(dirname(from), bare);
  for (const candidate of [base, join(base, "index.html"), `${base}.html`]) {
    if (existsSync(candidate) && statSync(candidate).isFile()) return candidate;
  }
  return null;
}

function references(html) {
  const found = [];
  for (const tag of html.matchAll(/<(?:a|link|script|img|source|use)\b[^>]*>/gi)) {
    for (const attribute of tag[0].matchAll(/\s(?:href|src)="([^"]*)"/gi)) found.push(attribute[1]);
  }
  return found;
}

function text(html) {
  return html
    .replace(/<script\b[\s\S]*?<\/script>/gi, " ")
    .replace(/<style\b[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ");
}

const decode = (value) => value.replaceAll("&amp;", "&").replaceAll("&quot;", '"').replaceAll("&#x27;", "'");
const keys = Object.keys(copy);
const parts = new Set(Object.keys(spec.components));

for (const [name, { root, pages, hint }] of Object.entries(EXPORTS)) {
  test(`${name} export has every page`, (t) => {
    if (!existsSync(join(root, "index.html"))) return t.skip(hint);
    for (const page of pages) {
      assert.ok(resolve(root, root, page), `${name} ${page} is missing`);
    }
  });

  test(`${name} export resolves every link, script and style sheet`, (t) => {
    if (!existsSync(join(root, "index.html"))) return t.skip(hint);
    const broken = [];
    for (const file of files(root, ".html")) {
      for (const raw of references(readFileSync(file, "utf8"))) {
        const reference = decode(raw);
        if (EXTERNAL.test(reference) || SERVED.test(reference)) continue;
        if (!resolve(root, file, reference)) broken.push(`${relative(root, file)} -> ${reference}`);
      }
    }
    for (const file of files(root, ".css")) {
      for (const match of readFileSync(file, "utf8").matchAll(/url\(\s*["']?([^"')]+)["']?\s*\)/g)) {
        const reference = match[1];
        if (EXTERNAL.test(reference)) continue;
        if (!resolve(root, file, reference)) broken.push(`${relative(root, file)} -> ${reference}`);
      }
    }
    assert.deepEqual(broken, []);
  });

  test(`${name} export shows no copy key as page text`, (t) => {
    if (!existsSync(join(root, "index.html"))) return t.skip(hint);
    const shown = [];
    for (const file of files(root, ".html")) {
      const words = new Set(text(readFileSync(file, "utf8")).split(/\s+/));
      for (const key of keys) if (words.has(key)) shown.push(`${relative(root, file)}: ${key}`);
    }
    assert.deepEqual(shown, []);
  });

  test(`${name} export tags only parts that DESIGN.md defines`, (t) => {
    if (!existsSync(join(root, "index.html"))) return t.skip(hint);
    const unknown = [];
    let tagged = 0;
    for (const file of files(root, ".html")) {
      for (const match of readFileSync(file, "utf8").matchAll(/\sdata-part="([^"]+)"/g)) {
        tagged += 1;
        for (const part of match[1].split(/\s+/)) {
          if (!parts.has(part)) unknown.push(`${relative(root, file)}: ${part}`);
        }
      }
    }
    assert.ok(tagged > 0, `${name} export carries no data-part`);
    assert.deepEqual(unknown, []);
  });
}

test("local pages carry the navigation rail part", (t) => {
  const { root, pages, hint } = EXPORTS.local;
  if (!existsSync(join(root, "index.html"))) return t.skip(hint);
  for (const page of pages) {
    const html = readFileSync(resolve(root, root, page), "utf8");
    assert.match(html, /data-part="nav-rail"/, `${page} navigation rail`);
  }
});
