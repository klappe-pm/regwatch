// Copy and design values for tests, read from the outputs `ds sync` writes (design/copy.json and design/spec.json)
// and from DESIGN.md, so a hub edit to a copy entry, a token or a component never breaks a test that checks behaviour.
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

export const web = fileURLToPath(new URL("..", import.meta.url));
export const root = join(web, "..");

export const copy = JSON.parse(readFileSync(join(web, "design", "copy.json"), "utf8"));
export const spec = JSON.parse(readFileSync(join(web, "design", "spec.json"), "utf8"));

/** The text of a copy entry, with its {placeholders} filled from `vars`. Throws on a missing key. */
export function copyText(key, vars) {
  if (!Object.hasOwn(copy, key)) throw new Error(`Missing copy: ${key}`);
  return vars ? copy[key].replace(/\{(\w+)\}/g, (all, name) => (name in vars ? String(vars[name]) : all)) : copy[key];
}

const escape = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** A RegExp that matches a copy entry literally; its {placeholders} match any text. */
export function copyPattern(key, flags = "") {
  return new RegExp(copyText(key).split(/\{\w+\}/).map(escape).join("[\\s\\S]*"), flags);
}

/**
 * Replace the copy entry with this full key (for example `pages.changes.header.title`) in the copy documents under
 * `docs` (docs/content-management-system or a copy of it), whatever its current text, as a hub edit does.
 */
export function setCopy(docs, key, value) {
  for (const name of readdirSync(docs, { recursive: true })) {
    if (!name.endsWith(".md")) continue;
    const doc = name.slice(0, -3).split(/[\\/]/).join(".");
    if (!key.startsWith(`${doc}.`)) continue;
    const file = join(docs, name);
    const lines = readFileSync(file, "utf8").split("\n");
    const groups = [];
    for (const [i, line] of lines.entries()) {
      const heading = /^(#{2,6}) `([a-z0-9-]+)`$/.exec(line);
      if (heading) {
        groups.length = heading[1].length - 2;
        groups.push(heading[2]);
        continue;
      }
      const entry = /^- `([a-z0-9-]+)`: /.exec(line);
      if (entry && [doc, ...groups, entry[1]].join(".") === key) {
        lines[i] = `- \`${entry[1]}\`: ${value}`;
        writeFileSync(file, lines.join("\n"));
        return;
      }
    }
  }
  throw new Error(`No copy entry ${key} under ${docs}`);
}

/** Replace the scalar at a DESIGN.md frontmatter path, for example ["components", "button-primary", "backgroundColor"]. */
export function setValue(design, path, value) {
  const lines = design.split("\n");
  const close = lines.indexOf("---", 1);
  const stack = [];
  for (let i = 1; i < close; i += 1) {
    const match = /^( *)([^\s:#][^:]*):(?: (.*))?$/.exec(lines[i]);
    if (!match) continue;
    const depth = match[1].length / 2;
    stack.length = depth;
    stack[depth] = match[2].trim();
    if (stack.length === path.length && path.every((key, index) => key === stack[index]) && match[3] !== undefined) {
      lines[i] = `${match[1]}${match[2]}: ${JSON.stringify(value)}`;
      return lines.join("\n");
    }
  }
  throw new Error(`DESIGN.md has no value at ${path.join(".")}`);
}

/** The rgb() string a browser computes for a #rrggbb colour (a DESIGN.md colour value). */
export function rgb(hex) {
  const n = parseInt(hex.slice(1, 7), 16);
  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
}
