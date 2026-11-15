// Replace regwatch/web/ (package data that ships in the wheel and the sdist) with the
// static export that `next build` wrote to web/out/.
import { cpSync, existsSync, rmSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const web = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const exported = join(web, "out");
const target = join(web, "..", "regwatch", "web");

if (basename(target) !== "web" || basename(dirname(target)) !== "regwatch") {
  throw new Error(`refusing to replace an unexpected folder: ${target}`);
}
if (!existsSync(join(exported, "index.html"))) {
  throw new Error("web/out/index.html is missing; run next build first");
}
rmSync(target, { recursive: true, force: true });
cpSync(exported, target, { recursive: true });
console.log(`copied the export to ${target}`);
