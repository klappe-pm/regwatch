// A hub edit renders: one copy entry and one DESIGN.md component colour are edited in a copy of the project, as the
// hub's publish would edit them, and the local application is rebuilt from that copy into a temporary folder. The
// rebuilt page must show the new heading and the new rail colour, while the committed build still shows the current
// ones. This fails when a page stops reading its words from the copy or its look from DESIGN.md, for example when an
// app style overrides a component.
// Run with: npx playwright install chromium && npm run test:browser (it builds, so it takes about a minute).
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { cpSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, before, test } from "node:test";

import { chromium } from "playwright";

import { serve } from "../../scripts/serve.mjs";
import { copyText, rgb, root, setCopy, setValue, web } from "../design-values.mjs";

const KEY = "pages.changes.header.title";
const HEADING = "Hub Edit Check";
const COMPONENT = ["components", "nav-rail", "backgroundColor"];
const COLOR = "#0c2238";

let browser;
let scratch;
const servers = {};

function run(cwd, ...args) {
  const result = spawnSync(process.execPath, args, { cwd, env: { ...process.env, NEXT_TELEMETRY_DISABLED: "1" }, encoding: "utf8" });
  assert.equal(result.status, 0, `${args.join(" ")}\n${result.stdout.slice(-2000)}\n${result.stderr.slice(-2000)}`);
}

before(async () => {
  scratch = mkdtempSync(join(tmpdir(), "regwatch-hub-edit-"));
  // The project as ds.config.json sees it: DESIGN.md and the copy documents one level above web/.
  cpSync(join(root, "docs", "content-management-system"), join(scratch, "docs", "content-management-system"), { recursive: true });
  const skip = new Set(["node_modules", ".next", "out", "dist", "site"].map((name) => join(web, name)));
  cpSync(web, join(scratch, "web"), { recursive: true, filter: (source) => !skip.has(source) });
  symlinkSync(join(web, "node_modules"), join(scratch, "web", "node_modules"), "dir");
  writeFileSync(join(scratch, "DESIGN.md"), setValue(readFileSync(join(root, "DESIGN.md"), "utf8"), COMPONENT, COLOR));
  setCopy(join(scratch, "docs", "content-management-system"), KEY, HEADING);

  const project = join(scratch, "web");
  const ds = join(web, "node_modules/@klappe/design-system/bin/ds.mjs");
  run(project, ds, "sync");
  run(project, join(project, "scripts", "make-icons.mjs"));
  run(project, join(web, "node_modules", "next", "dist", "bin", "next"), "build", "--webpack");
  run(project, ds, "csp", "out");

  browser = await chromium.launch();
  servers.committed = await serve(join(root, "regwatch", "web"));
  servers.edited = await serve(join(project, "out"));
});

after(async () => {
  await browser?.close();
  for (const server of Object.values(servers)) server.close();
  if (scratch) rmSync(scratch, { recursive: true, force: true });
});

async function look(server) {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto(`http://127.0.0.1:${server.address().port}/changes/`, { waitUntil: "networkidle" });
  const rail = page.locator('[data-part~="nav-rail"]');
  const seen = {
    heading: (await page.getByRole("heading", { level: 1 }).textContent()).trim(),
    rail: await rail.evaluate((element) => getComputedStyle(element).backgroundColor),
  };
  await page.close();
  return seen;
}

test("a hub copy edit and a DESIGN.md component edit change the rendered page", { timeout: 600_000 }, async () => {
  const committed = await look(servers.committed);
  const edited = await look(servers.edited);
  assert.equal(committed.heading, copyText(KEY), "the committed build shows the current copy");
  assert.notEqual(committed.rail, rgb(COLOR), "the edit colour differs from the current rail colour");
  assert.equal(edited.heading, HEADING, "the copy edit renders");
  assert.equal(edited.rail, rgb(COLOR), "the nav-rail component edit renders");
});
