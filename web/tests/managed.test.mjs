import assert from "node:assert/strict";
import { cpSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { test } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import { buildCopy, buildManaged, componentCss, copyEntries, designTokens, webRoot } from "../scripts/managed.mjs";
import { COPY } from "../src/lib/copy.generated.ts";
import { CATEGORIES, MARKETS, emptyWorkspace, parseWorkspace } from "../src/lib/bev-watch.ts";

test("the committed snapshots contain every managed copy value and remain fresh", () => {
  assert.deepEqual(buildCopy(join(webRoot, "content")), COPY);
  assert.doesNotThrow(() => buildManaged(webRoot, true));
  for (const key of ["pages.landing.the-rules-change", "pages.onboarding.continue", "pages.workspace.save-product", "pages.pricing.no-charge", "pages.privacy.what-this-website-stores", "global.brand.get-started"]) assert.equal(typeof COPY[key], "string");
});

test("copy groups use the editable document key contract", () => {
  assert.deepEqual(copyEntries("# Copy\n\n## `hero`\n\nWhere: page title.\n\n- `title`: A new title\n\n### `cta`\n\n- `label`: Continue\n\n## `footer`\n\n- `label`: Privacy\n"), [
    { key: "hero.title", value: "A new title" },
    { key: "hero.cta.label", value: "Continue" },
    { key: "footer.label", value: "Privacy" },
  ]);
});

test("onboarding marker styles exclude the managed label span at desktop and mobile", () => {
  const source = readFileSync(join(webRoot, "src/app/onboarding/page.tsx"), "utf8");
  const page = ts.createSourceFile("onboarding.tsx", source, ts.ScriptTarget.Latest, true);
  let progress;
  function find(node) {
    if (ts.isJsxElement(node) && node.openingElement.tagName.getText(page) === "li") progress = node;
    ts.forEachChild(node, find);
  }
  find(page);
  assert.ok(progress, "the progress item exists in the actual onboarding markup");
  const children = progress.children.filter(node => !ts.isJsxText(node) || node.text.trim());
  assert.equal(children[0].openingElement.tagName.getText(page), "span");
  assert.equal(children[1].tagName.getText(page), "Copy");
  const styles = readFileSync(join(webRoot, "src/app/globals.css"), "utf8");
  const spanRules = [...styles.matchAll(/([^{}]+)\{([^{}]*)\}/g)].filter(([, selector]) => selector.includes(".bw-onboard-grid li") && selector.includes("> span"));
  assert.equal(spanRules.length, 3, "desktop geometry, active color, and mobile type each have a marker rule");
  for (const [, selector] of spanRules) {
    assert.match(selector, /> span:first-child\s*$/, `progress labels must not match the marker selector: ${selector.trim()}`);
  }
  assert.match(spanRules[0][2], /width: 28px; height: 28px/);
  assert.match(spanRules[2][2], /font-size: 12px/);
  assert.match(styles, /\.bw-onboard-grid li \{ margin: 0; font-size: 0; \}/);
});

function copyComponentUrl(generated) {
  let source = readFileSync(join(webRoot, "src/components/copy.tsx"), "utf8").replace("@/lib/copy.generated", pathToFileURL(generated).href);
  source = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText.replace('"react/jsx-runtime"', JSON.stringify(import.meta.resolve("react/jsx-runtime")));
  return `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
}

async function renderCopy(generated, key) {
  const { Copy } = await import(copyComponentUrl(generated));
  return renderToStaticMarkup(createElement(Copy, { k: key }));
}

async function renderProductForm(generated) {
  const moduleUrl = source => `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
  const imports = {
    "@/components/copy": copyComponentUrl(generated),
    "@/lib/copy.generated": pathToFileURL(generated).href,
    "@/lib/bev-watch": pathToFileURL(join(webRoot, "src/lib/bev-watch.ts")).href,
    "@/components/brand": moduleUrl("export function Brand() { return null; }"),
    "@/components/icon": moduleUrl("export function Icon() { return null; }"),
    "next/link": moduleUrl("export default function Link() { return null; }"),
    "next/navigation": moduleUrl("export function useSearchParams() { return null; }"),
    "react": import.meta.resolve("react"),
    "react/jsx-runtime": import.meta.resolve("react/jsx-runtime"),
  };
  let source = readFileSync(join(webRoot, "src/app/workspace/page.tsx"), "utf8").replace("function ProductForm(", "export function ProductForm(");
  source = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
  for (const [name, url] of Object.entries(imports)) source = source.replaceAll(JSON.stringify(name), JSON.stringify(url));
  const { ProductForm } = await import(moduleUrl(source));
  return renderToStaticMarkup(createElement(ProductForm, { markets: [], onSave() {}, onCancel() {} }));
}

test("duplicate editable wording keeps the actual product heading bound to its original copy key", async () => {
  const fixture = mkdtempSync(join(tmpdir(), "regwatch-copy-identity-"));
  const web = join(fixture, "web");
  try {
    cpSync(join(webRoot, "content"), join(web, "content"), { recursive: true });
    cpSync(join(webRoot, "../DESIGN.md"), join(fixture, "DESIGN.md"));
    const document = join(web, "content/pages/workspace.md");
    writeFileSync(document, readFileSync(document, "utf8").replace("- `add-product`: Add product", "- `add-product`: Add your first product"));
    buildManaged(web);
    const rendered = await renderProductForm(join(web, "src/lib/copy.generated.ts"));
    assert.match(rendered, /<h2><span data-copy-key="pages\.workspace\.add-your-first-product">Add your first product<\/span><\/h2>/);
  } finally {
    rmSync(fixture, { recursive: true, force: true });
  }
});

test("an editable copy and design change reaches the actual text component and CSS snapshots", async () => {
  const fixture = mkdtempSync(join(tmpdir(), "regwatch-managed-"));
  const web = join(fixture, "web");
  try {
    cpSync(join(webRoot, "content"), join(web, "content"), { recursive: true });
    const landing = join(web, "content/pages/landing.md");
    writeFileSync(landing, readFileSync(landing, "utf8").replace("The rules change.", "The review & <next> move."));
    const design = readFileSync(join(webRoot, "../DESIGN.md"), "utf8").replace('bw-navy: "#183e56"', 'bw-navy: "#123456"').replace('padding: "12px 22px"', 'padding: "16px 24px"');
    writeFileSync(join(fixture, "DESIGN.md"), design);
    buildManaged(web);
    const rendered = await renderCopy(join(web, "src/lib/copy.generated.ts"), "pages.landing.the-rules-change");
    assert.match(rendered, /data-copy-key="pages\.landing\.the-rules-change"/);
    assert.match(rendered, /The review &amp; &lt;next&gt; move\./);
    assert.match(readFileSync(join(web, "design/tokens.css"), "utf8"), /--ds-color-bw-navy: #123456;/);
    assert.match(readFileSync(join(web, "design/components.css"), "utf8"), /\[data-component="button-primary"\][\s\S]*?padding: var\(--bw-button-padding, 16px 24px\);/);
    assert.doesNotThrow(() => buildManaged(web, true));
    writeFileSync(landing, readFileSync(landing, "utf8").replace("The review & <next> move.", "Changed again."));
    assert.throws(() => buildManaged(web, true), /Stale managed output/);
  } finally {
    rmSync(fixture, { recursive: true, force: true });
  }
});

test("design snapshots preserve the implemented palette and component references", () => {
  const tokens = designTokens(readFileSync(join(webRoot, "../DESIGN.md"), "utf8"));
  assert.equal(tokens.colors["bw-navy"], "#183e56");
  assert.equal(tokens.colors["brand-red"], "#b33a36");
  assert.match(componentCss(tokens), /background-color: var\(--ds-color-bw-navy\)/);
  assert.match(componentCss(tokens), /\[data-component="choice-selected"\]\.is-selected/);
  const publicStyles = readFileSync(join(webRoot, "src/app/globals.css"), "utf8").split("/* Public website")[1];
  assert.doesNotMatch(publicStyles, /#[0-9a-f]{3,8}\b/i);
  assert.match(publicStyles, /--bw-navy: var\(--ds-color-bw-navy\)/);
  assert.match(publicStyles, /white-space: nowrap/);
  assert.doesNotMatch(publicStyles, /var\([^)]*\)-space/);
  assert.throws(() => designTokens("# Missing token map"), /YAML token map/);
  assert.throws(() => designTokens('```yaml\ncolors:\n  navy: "#123456"\n  navy: "#654321"\n```'), /Duplicate design token/);
});

test("editable category and market labels leave persisted workspace values stable", () => {
  const workspace = { ...emptyWorkspace(), categories: [CATEGORIES[0]], markets: [MARKETS[0]], cadence: "Weekly" };
  assert.deepEqual(parseWorkspace(workspace), workspace);
  assert.equal(CATEGORIES[0], "Non-alcoholic beverages");
  assert.equal(MARKETS[0], "United States");
});
