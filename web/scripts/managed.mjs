// Build public copy and design snapshots without a service or package at build time.
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

export function copyEntries(markdown) {
  const entries = [];
  const groups = [];
  for (const line of markdown.split(/\r?\n/)) {
    const heading = /^(#{2,6}) `([^`]+)`\s*$/.exec(line);
    if (heading) {
      while (groups.at(-1)?.level >= heading[1].length) groups.pop();
      groups.push({ level: heading[1].length, key: heading[2] });
    }
    const entry = /^- `([^`]+)`:(?: (.*))?$/.exec(line);
    if (entry) entries.push({ key: [...groups.map(group => group.key), entry[1]].join("."), value: entry[2] ?? "" });
  }
  return entries;
}

function documents(folder) {
  if (!existsSync(folder)) return [];
  return readdirSync(folder, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name, "en")).flatMap(entry => {
    const path = join(folder, entry.name);
    return entry.isDirectory() ? documents(path) : entry.name.endsWith(".md") ? [path] : [];
  });
}

export function buildCopy(contentRoot) {
  const copy = {};
  for (const folder of ["global", "pages"]) for (const path of documents(join(contentRoot, folder))) {
    const document = relative(contentRoot, path).replace(/\.md$/, "").split(/[\\/]/).join(".");
    for (const entry of copyEntries(readFileSync(path, "utf8"))) {
      const key = `${document}.${entry.key}`;
      if (Object.hasOwn(copy, key)) throw new Error(`Duplicate copy key: ${key}`);
      copy[key] = entry.value;
    }
  }
  if (!Object.keys(copy).length) throw new Error("No managed copy documents found.");
  return copy;
}

// This project uses an indented scalar map inside a YAML fence, not document frontmatter.
export function designTokens(markdown) {
  const fence = /```yaml\r?\n([\s\S]*?)\r?\n```/.exec(markdown);
  if (!fence) throw new Error("DESIGN.md needs its YAML token map.");
  const root = {};
  const parents = [{ indent: -1, value: root }];
  for (const line of fence[1].split(/\r?\n/)) {
    if (!line.trim() || line.trimStart().startsWith("#")) continue;
    const match = /^( *)([a-zA-Z][\w-]*):(?: (.*))?$/.exec(line);
    if (!match || match[1].length % 2) throw new Error(`Unsupported design token line: ${line}`);
    const indent = match[1].length;
    while (parents.at(-1).indent >= indent) parents.pop();
    if (indent !== parents.at(-1).indent + (parents.length === 1 ? 1 : 2)) throw new Error(`Invalid token indentation: ${line}`);
    const parent = parents.at(-1).value;
    if (Object.hasOwn(parent, match[2])) throw new Error(`Duplicate design token: ${match[2]}`);
    const raw = match[3];
    if (raw === undefined) {
      parent[match[2]] = {};
      parents.push({ indent, value: parent[match[2]] });
    } else if (raw.startsWith('"')) parent[match[2]] = JSON.parse(raw);
    else if (raw.startsWith("'") && raw.endsWith("'")) parent[match[2]] = raw.slice(1, -1).replaceAll("''", "'");
    else if (/^-?\d+(?:\.\d+)?$/.test(raw)) parent[match[2]] = Number(raw);
    else parent[match[2]] = raw;
  }
  return root;
}

const kebab = value => value.replace(/([a-z0-9])([A-Z])/g, "$1-$2").toLowerCase();
const fontProperties = { fontFamily: "family", fontSize: "size", fontWeight: "weight", lineHeight: "line-height", letterSpacing: "letter-spacing" };

export function tokenCss(tokens) {
  const declarations = [];
  for (const [group, prefix] of [["colors", "color"], ["spacing", "space"], ["rounded", "radius"]]) {
    for (const [name, value] of Object.entries(tokens[group] ?? {})) declarations.push(`  --ds-${prefix}-${kebab(name)}: ${value};`);
  }
  for (const [name, properties] of Object.entries(tokens.typography ?? {})) for (const [property, value] of Object.entries(properties)) {
    if (fontProperties[property]) declarations.push(`  --ds-font-${kebab(name)}-${fontProperties[property]}: ${value};`);
  }
  return `/* Generated from DESIGN.md. Run npm run managed after editing the token map. */\n:root {\n${declarations.join("\n")}\n}\n`;
}

export function componentCss(tokens) {
  const properties = { backgroundColor: "background-color", textColor: "color", color: "color", rounded: "border-radius", padding: "padding", gap: "gap", borderColor: "border-color", borderWidth: "border-width", fontSize: "font-size", fontWeight: "font-weight", lineHeight: "line-height", letterSpacing: "letter-spacing" };
  const prefixes = { colors: "color", rounded: "radius", spacing: "space" };
  const rules = [];
  for (const [name, styles] of Object.entries(tokens.components ?? {})) {
    const state = /-(hover|focus|active|disabled)$/.exec(name);
    const base = state ? name.slice(0, -state[0].length) : name;
    let selector = `[data-component="${base}"]${state ? `:${state[1]}` : ""}`;
    if (name === "field") selector += " :is(input, select, textarea)";
    if (name === "choice-selected") selector += ".is-selected";
    if (name === "button-small") selector = "[data-component].bw-button-small";
    const declarations = [];
    for (const [property, raw] of Object.entries(styles)) {
      if (!properties[property]) continue;
      const value = String(raw).replace(/\{(colors|rounded|spacing)\.([^}]+)\}/g, (_, group, token) => {
        if (!Object.hasOwn(tokens[group] ?? {}, token)) throw new Error(`Unknown design reference: ${group}.${token}`);
        return `var(--ds-${prefixes[group]}-${kebab(token)})`;
      });
      if (/[;{}<>\r\n]/.test(value)) throw new Error(`Unsupported component style: ${name}.${property}`);
      if (property === "padding" && name === "onboarding-panel") declarations.push(`  --bw-onboard-padding: ${value};`);
      else if (property === "padding" && name === "button-small") declarations.push(`  --bw-small-padding: ${value};`);
      else if (property === "padding" && /^(button-primary|button-light|button-outline)$/.test(name)) declarations.push(`  padding: var(--bw-button-padding, ${value});`);
      else declarations.push(`  ${properties[property]}: ${value};`);
    }
    if (declarations.length) rules.push(`${selector} {\n${declarations.join("\n")}\n}`);
  }
  return `/* Generated from DESIGN.md. Run npm run managed after editing component tokens. */\n${rules.join("\n")}\n`;
}

export function copyModule(copy) {
  return `// Generated from web/content. Run npm run managed after editing the copy documents.\nexport const COPY = ${JSON.stringify(copy, null, 2)} as const;\nexport type CopyKey = keyof typeof COPY;\nexport const t = (key: CopyKey): string => COPY[key];\n`;
}

export function buildManaged(web = webRoot, check = false) {
  const copy = buildCopy(join(web, "content"));
  const tokens = designTokens(readFileSync(join(web, "..", "DESIGN.md"), "utf8"));
  const outputs = {
    "src/lib/copy.generated.ts": copyModule(copy),
    "design/tokens.json": `${JSON.stringify(tokens, null, 2)}\n`,
    "design/tokens.css": tokenCss(tokens),
    "design/components.css": componentCss(tokens),
  };
  for (const [name, source] of Object.entries(outputs)) {
    const target = join(web, name);
    if (existsSync(target) && readFileSync(target, "utf8") === source) continue;
    if (check) throw new Error(`Stale managed output: ${name}. Run npm run managed.`);
    mkdirSync(dirname(target), { recursive: true });
    writeFileSync(target, source);
  }
  return { copy: Object.keys(copy).length, colors: Object.keys(tokens.colors ?? {}).length };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const counts = buildManaged(webRoot, process.argv.includes("--check"));
  console.log(`Managed content ready: ${counts.copy} copy entries, ${counts.colors} colors.`);
}
