// Serve a built folder (out/ by default) on 127.0.0.1 with the content security policy the local
// server sends (regwatch/server.py): this origin only, the page's own inline scripts by hash, and
// style sheets from this origin only. /api/* answers 404, as a page with no project behind it.
//   node scripts/serve.mjs [folder] [port]
import { createHash } from "node:crypto";
import { readFile, stat } from "node:fs/promises";
import { createServer } from "node:http";
import { extname, join, normalize, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json",
  ".txt": "text/plain; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
};

export function policy(html) {
  const hashes = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)]
    .map((match) => match[1])
    .filter(Boolean)
    .map((body) => `'sha256-${createHash("sha256").update(body, "utf8").digest("base64")}'`);
  return [
    "default-src 'none'",
    `script-src ${["'self'", ...hashes].join(" ")}`,
    "style-src 'self'",
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "manifest-src 'self'",
    "frame-src 'self'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");
}

async function find(root, path) {
  const target = normalize(join(root, decodeURIComponent(path)));
  if (!target.startsWith(root)) return null;
  for (const candidate of [target, join(target, "index.html")]) {
    try {
      if ((await stat(candidate)).isFile()) return candidate;
    } catch {
      // try the next candidate
    }
  }
  return null;
}

export function serve(folder, port = 0) {
  const root = resolve(folder);
  const server = createServer(async (request, response) => {
    const path = new URL(request.url ?? "/", "http://localhost").pathname;
    if (path.startsWith("/api/")) {
      response.writeHead(404, { "Content-Type": "application/json" });
      response.end(JSON.stringify({ error: "There is no project behind this preview." }));
      return;
    }
    const file = (await find(root, path)) ?? join(root, "404.html");
    const body = await readFile(file);
    const headers = { "Content-Type": TYPES[extname(file)] ?? "application/octet-stream" };
    if (extname(file) === ".html") headers["Content-Security-Policy"] = policy(body.toString("utf8"));
    response.writeHead(file.endsWith("404.html") && !path.endsWith("404.html") ? 404 : 200, headers);
    response.end(body);
  });
  return new Promise((done) => server.listen(port, "127.0.0.1", () => done(server)));
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const folder = process.argv[2] ?? fileURLToPath(new URL("../out", import.meta.url));
  const server = await serve(folder, Number(process.argv[3] ?? 4180));
  console.log(`serving ${folder} at http://127.0.0.1:${server.address().port}/`);
}
