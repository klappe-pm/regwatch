// Build the public website without replacing the Python package's local application.
import { cpSync, existsSync, mkdtempSync, renameSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const web = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const env = { ...process.env, NEXT_PUBLIC_BEV_WATCH_MODE: "hosted-preview" };
for (const args of [[join(web,"scripts/managed.mjs")],[join(web,"scripts/make-icons.mjs")],[join(web,"node_modules/next/dist/bin/next"),"build"]]) {
  const result = spawnSync(process.execPath, args, { cwd: web, env, stdio: "inherit" });
  if (result.status !== 0) process.exit(result.status || 1);
}
const site = join(web,"site");
const staged = mkdtempSync(join(web,".site-next-"));
const previous = `${staged}-previous`;
try {
  for (const name of ["index.html","index.txt","404.html","404","_next","icon.svg","pricing","privacy","onboarding","workspace"]) {
    cpSync(join(web,"out",name),join(staged,name),{recursive:true});
  }
  if (existsSync(site)) renameSync(site,previous);
  try { renameSync(staged,site); }
  catch (reason) {
    if (existsSync(previous)) renameSync(previous,site);
    throw reason;
  }
  rmSync(previous,{recursive:true,force:true});
} finally {
  rmSync(staged,{recursive:true,force:true});
}
console.log("Public website ready in web/site. Local engine routes are excluded.");
