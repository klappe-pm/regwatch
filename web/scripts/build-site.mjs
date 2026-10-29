// Build the public website without replacing the Python package's local application.
import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const web = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const env = { ...process.env, NEXT_PUBLIC_BEV_WATCH_MODE: "hosted-preview" };
const steps = [
  [join(web, "scripts/make-icons.mjs")],
  [join(web, "node_modules/@klappe/design-system/bin/ds.mjs"), "check"],
  [join(web, "node_modules/next/dist/bin/next"), "build", "--webpack"],
  [join(web, "scripts/postbuild.mjs")],
];
for (const args of steps) {
  const result = spawnSync(process.execPath, args, { cwd: web, env, stdio: "inherit" });
  if (result.status !== 0) process.exit(result.status || 1);
}
// dist/ rather than site/: ds skips dist/ when it reads the custom properties of the
// project's CSS, so a public build left in place cannot make design/spec.json look stale.
const site = join(web, "dist");
rmSync(site, { recursive: true, force: true });
mkdirSync(site, { recursive: true });
for (const name of ["index.html", "404.html", "404", "_next", "icon.svg", "pricing", "privacy", "onboarding", "workspace"]) {
  if (existsSync(join(web, "out", name))) cpSync(join(web, "out", name), join(site, name), { recursive: true });
}
console.log("Public website ready in web/dist. Local engine routes are excluded.");
