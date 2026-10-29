// Loads every page of both exports in Chromium, served with the local server's content security
// policy (scripts/serve.mjs), and checks that each renders styled with no policy violation, that the
// local application follows dark mode while the public pages stay light, and that the preview's
// main interactions still work.
// Run with: npm run build && npm run build:site && npx playwright install chromium && npm run test:browser
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { after, before, test } from "node:test";
import { fileURLToPath } from "node:url";

import { chromium } from "playwright";

import { serve } from "../../scripts/serve.mjs";

const web = fileURLToPath(new URL("../..", import.meta.url));
const copy = JSON.parse(readFileSync(join(web, "design", "copy.json"), "utf8"));
const spec = JSON.parse(readFileSync(join(web, "design", "spec.json"), "utf8"));
const local = join(web, "..", "regwatch", "web");
const site = join(web, "dist");

const LOCAL_PAGES = ["/", "/changes/", "/sources/", "/obligations/", "/briefings/", "/newsletters/", "/documents/", "/automations/", "/keys/", "/settings/"];
const PUBLIC_PAGES = ["/", "/pricing/", "/privacy/", "/onboarding/", "/workspace/", "/workspace/?view=updates", "/workspace/?view=settings"];

let browser;
const servers = {};

before(async () => {
  browser = await chromium.launch();
  servers.local = await serve(local);
  if (existsSync(join(site, "index.html"))) servers.site = await serve(site);
});

after(async () => {
  await browser?.close();
  for (const server of Object.values(servers)) server.close();
});

const origin = (server) => `http://127.0.0.1:${server.address().port}`;
const rgb = (hex) => {
  const n = parseInt(hex.slice(1, 7), 16);
  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
};

/** Open a page and report what the policy refused, script errors, and how it is styled. */
async function open(url, colorScheme = "light", viewport = { width: 1280, height: 900 }) {
  const context = await browser.newContext({ colorScheme, viewport });
  const page = await context.newPage();
  const problems = [];
  page.on("console", (message) => {
    const text = message.text();
    // The preview has no project behind it, so the local pages' /api requests answer 404.
    if (message.type() === "error" && !/status of 404/.test(text)) problems.push(text);
  });
  page.on("pageerror", (error) => problems.push(error.message));
  await page.addInitScript(() => {
    document.addEventListener("securitypolicyviolation", (event) => {
      console.error(`CSP refused ${event.violatedDirective}: ${event.blockedURI}`);
    });
  });
  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForTimeout(200);
  const state = await page.evaluate(() => ({
    adopted: document.adoptedStyleSheets.reduce((n, sheet) => n + sheet.cssRules.length, 0),
    background: getComputedStyle(document.body).backgroundColor,
    heading: document.querySelector("h1")?.textContent ?? "",
    theme: document.documentElement.getAttribute("data-theme"),
  }));
  return { context, page, problems, state };
}

for (const path of LOCAL_PAGES) {
  test(`local ${path} renders styled under the policy, in light and dark`, async () => {
    for (const [scheme, surface] of [["light", spec.colors.surface], ["dark", spec.colors["surface-dark"]]]) {
      const { context, problems, state, page } = await open(`${origin(servers.local)}${path}`, scheme);
      assert.deepEqual(problems, [], `${path} ${scheme}`);
      assert.ok(state.adopted > 10, `${path} has no Material UI styles applied`);
      assert.equal(state.background, rgb(surface), `${path} ${scheme} background`);
      assert.ok(state.heading.length > 0, `${path} has no heading`);
      assert.ok(await page.locator('[data-part="nav-rail"]').isVisible(), `${path} navigation`);
      await context.close();
    }
  });
}

for (const path of PUBLIC_PAGES) {
  test(`public ${path} renders styled under the policy and stays light`, async (t) => {
    if (!servers.site) return t.skip("run npm run build:site first");
    const { context, problems, state } = await open(`${origin(servers.site)}${path}`, "dark");
    assert.deepEqual(problems, [], path);
    assert.ok(state.adopted > 10, `${path} has no Material UI styles applied`);
    assert.equal(state.theme, "light");
    assert.notEqual(state.background, rgb(spec.colors["surface-dark"]), `${path} turned dark`);
    await context.close();
  });
}

test("onboarding checks each step and saves the watchlist in the browser", async (t) => {
  if (!servers.site) return t.skip("run npm run build:site first");
  const { context, page, problems } = await open(`${origin(servers.site)}/onboarding/`);
  const step = (n) => copy[`pages.onboarding.steps.${n}-title`];
  // The name is required by the field itself; without a category the step explains what is missing.
  await page.getByLabel(copy["pages.onboarding.fields.business"]).fill("Example Beverages");
  await page.getByRole("button", { name: copy["pages.onboarding.actions.continue"] }).click();
  await page.getByRole("alert").filter({ hasText: copy["pages.onboarding.errors.business"] }).waitFor();
  await page.getByLabel(copy["global.preview-data.categories.wine"]).check();
  await page.getByRole("button", { name: copy["pages.onboarding.actions.continue"] }).click();
  await page.getByRole("heading", { name: step(2) }).waitFor();
  await page.getByLabel(copy["global.preview-data.markets.us"]).check();
  await page.getByRole("button", { name: copy["pages.onboarding.actions.continue"] }).click();
  await page.getByRole("heading", { name: step(3) }).waitFor();
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem("bev-watch.workspace.v1")));
  assert.equal(stored.company, "Example Beverages");
  assert.deepEqual(stored.markets, ["United States"]);
  assert.deepEqual(problems, []);
  await context.close();
});

test("the workspace marks a sample update reviewed and filters the queue", async (t) => {
  if (!servers.site) return t.skip("run npm run build:site first");
  const { context, page, problems } = await open(`${origin(servers.site)}/workspace/?view=updates`);
  const first = copy["global.preview-data.updates.label.title"];
  await page.getByRole("button", { name: first }).click();
  await page.getByRole("button", { name: copy["pages.workspace.updates.mark-reviewed"] }).click();
  await page.getByRole("status").filter({ hasText: copy["pages.workspace.messages.reviewed"] }).waitFor();
  await page.getByRole("button", { name: copy["pages.workspace.updates.unreviewed"], exact: true }).click();
  assert.equal(await page.getByRole("heading", { name: first }).count(), 0);
  await page.getByRole("button", { name: copy["pages.workspace.updates.reviewed"], exact: true }).click();
  assert.equal(await page.getByRole("heading", { name: first }).count(), 1);
  assert.deepEqual(problems, []);
  await context.close();
});

test("the local navigation rail collapses and the search opens its panel", async () => {
  const { context, page, problems } = await open(`${origin(servers.local)}/changes/`);
  await page.getByRole("button", { name: copy["global.shell.nav.collapse-label"] }).click();
  await page.getByRole("button", { name: copy["global.shell.nav.expand-label"] }).waitFor();
  await page.getByRole("button", { name: copy["global.shell.search.label"] }).click();
  await page.getByRole("combobox", { name: copy["global.shell.search.label"] }).fill("fda");
  await page.getByRole("listbox").waitFor();
  assert.deepEqual(problems.filter((p) => !/request failed|no project/i.test(p)), []);
  await context.close();
});
