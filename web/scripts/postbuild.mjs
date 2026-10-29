// After `next build`: move the Material UI styles that Emotion rendered into each page into one style
// sheet file per distinct set, and confirm the export holds no inline style and no inline executable
// script. The local server sends `script-src 'self'` (plus the hashes of the page's inline scripts) and
// `style-src 'self'`, which blocks every inline style.
import { createHash } from "node:crypto";
import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const out = fileURLToPath(new URL("../out", import.meta.url));
const cssDir = join(out, "_next", "static", "css");
const STYLE = /<style data-emotion="[^"]*"[^>]*>([\s\S]*?)<\/style>/g;

async function walk(dir) {
  const files = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) files.push(...(await walk(path)));
    else if (entry.name.endsWith(".html")) files.push(path);
  }
  return files;
}

await mkdir(cssDir, { recursive: true });
const problems = [];
const sheets = new Set();
const pages = await walk(out);
for (const page of pages) {
  let html = await readFile(page, "utf8");
  const css = [...html.matchAll(STYLE)].map((match) => match[1]).join("\n");
  if (css) {
    const name = `emotion-${createHash("sha256").update(css).digest("hex").slice(0, 16)}.css`;
    if (!sheets.has(name)) {
      await writeFile(join(cssDir, name), `${css}\n`);
      sheets.add(name);
    }
    let first = true;
    html = html.replace(STYLE, () => {
      if (!first) return "";
      first = false;
      return `<link rel="stylesheet" href="/_next/static/css/${name}"/>`;
    });
    await writeFile(page, html);
  }
  const where = relative(out, page);
  if (/<style[\s>]/.test(html)) problems.push(`${where}: an inline <style> element`);
  if (/<[a-z][^>]*\sstyle\s*=/i.test(html)) problems.push(`${where}: a style attribute`);
  for (const match of html.matchAll(/<script(?![^>]*\bsrc=)([^>]*)>/g)) {
    if (!/type="application\/json"/.test(match[1])) problems.push(`${where}: an inline executable script`);
  }
}
if (problems.length) {
  console.error(`The export breaks the local server's content security policy:\n${problems.join("\n")}`);
  process.exit(1);
}
console.log(`Moved the Material UI styles of ${pages.length} pages into ${sheets.size} style sheet files; no inline style or script.`);
