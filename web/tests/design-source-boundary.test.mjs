import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { outputs } from "../design-system/src/core/node.mjs";

test("design compilation reads CSS only from the configured source folders", () => {
  const root = mkdtempSync(join(tmpdir(), "regwatch-design-"));
  try {
    mkdirSync(join(root, "src"));
    mkdirSync(join(root, "copy"));
    writeFileSync(join(root, "src", "app.css"), ":root { --app-accent: #123456; }");
    writeFileSync(join(root, "DESIGN.md"), "---\nroles:\n  primary: var(--app-accent)\n  on-primary: '#ffffff'\n  surface: '#ffffff'\n  on-surface: '#000000'\n---\n");
    // A broken unrelated path proves the compiler never stats root environment files.
    symlinkSync(join(root, "missing"), join(root, ".env.local"));
    const result = outputs({ root, config: { designFile: "DESIGN.md", cmsDir: "copy", out: "design", src: ["src"], ignore: [], files: {}, hostVariables: [] } });
    assert.deepEqual(result.errors, []);
    assert.match(result.files["design/spec.json"], /#123456/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
