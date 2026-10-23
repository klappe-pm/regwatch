// Copy the outline paths of the Material Symbols the pages use into one module, so the
// built pages carry the icons inline and load no icon font at run time.
// Material Symbols are by Google and licensed under the Apache License 2.0.
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const source = join(here, "..", "node_modules", "@material-symbols", "svg-400", "outlined");
const target = join(here, "..", "src", "lib", "icons.generated.ts");

const names = [
  "add",
  "arrow_forward",
  "article",
  "check_circle",
  "chevron_right",
  "close",
  "dashboard",
  "database",
  "delete",
  "description",
  "difference",
  "download",
  "error",
  "filter_list",
  "gavel",
  "key",
  "left_panel_close",
  "left_panel_open",
  "lock",
  "mail",
  "play_arrow",
  "print",
  "schedule",
  "search",
  "settings",
  "warning",
];

const paths = {};
for (const name of names) {
  const svg = readFileSync(join(source, `${name}.svg`), "utf8");
  const found = [...svg.matchAll(/ d="([^"]+)"/g)].map((match) => match[1]);
  if (found.length === 0) throw new Error(`no path in ${name}.svg`);
  paths[name] = found.join(" ");
}

const body = Object.entries(paths)
  .map(([name, d]) => `  ${name}: ${JSON.stringify(d)},`)
  .join("\n");
writeFileSync(
  target,
  "// Made by scripts/make-icons.mjs from @material-symbols/svg-400 (Apache License 2.0).\n" +
    "// Do not edit; run npm --prefix web run icons.\n" +
    `export const ICON_PATHS = {\n${body}\n} as const;\n\n` +
    "export type IconName = keyof typeof ICON_PATHS;\n",
);
