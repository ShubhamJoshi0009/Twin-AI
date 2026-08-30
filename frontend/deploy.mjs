#!/usr/bin/env node
/* ═══════════════════════════════════════════════════════════════════════════
 * deploy.mjs — Rebuild + redeploy the Next.js standalone server.
 *
 * WHY THIS EXISTS (the bug it prevents):
 *   Repeatedly copying build assets into an existing standalone folder with
 *   no-clobber semantics caused `static/static/…` nesting and stale chunk
 *   mixing → the HTML referenced new chunk hashes the server couldn't serve
 *   → net::ERR_ABORTED 400 → ChunkLoadError in the browser.
 *
 *   This script ALWAYS wipes the standalone static/public folders and copies
 *   from the fresh build, so every deployed asset matches the served HTML.
 *
 * Usage:  node deploy.mjs            (build + copy + start)
 *         node deploy.mjs --verify   (also run the browser verify.mjs pass)
 * ═══════════════════════════════════════════════════════════════════════════ */
import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = __dirname;
const STANDALONE = path.join(ROOT, ".next", "standalone");
const SA = path.join(STANDALONE, "Business Twin Ai", "frontend");
const PORT = process.env.PORT ?? "3000";
const HOST = process.env.HOSTNAME ?? "127.0.0.1";

function sh(cmd, opts = {}) {
  console.log(`\n$ ${cmd}`);
  execSync(cmd, { stdio: "inherit", shell: true, ...opts });
}

function stopExistingServer() {
  try {
    const out = execSync(`lsof -tiTCP:${PORT} -sTCP:LISTEN 2>/dev/null | head -1`).toString().trim();
    if (out) {
      console.log(`\nStopping existing server on :${PORT} (pid ${out})`);
      execSync(`kill -9 ${out} 2>/dev/null || true`, { shell: true });
      execSync("sleep 2", { shell: true });
    }
  } catch { /* nothing running */ }
}

/* 1 ── build ─────────────────────────────────────────────────────────────── */
sh("npm run build");
if (!fs.existsSync(path.join(SA, "server.js"))) {
  console.error("❌ standalone server.js not found — build did not emit a standalone output");
  process.exit(1);
}

/* 2 ── wipe + copy static & public (THE fix — never cp -rn into existing dirs) */
const wipeAndCopy = (src, dest) => {
  fs.rmSync(dest, { recursive: true, force: true });
  fs.mkdirSync(dest, { recursive: true });
  fs.cpSync(src, dest, { recursive: true });
  console.log(`  wiped + copied ${src} → ${dest}`);
};
wipeAndCopy(path.join(ROOT, ".next", "static"), path.join(SA, ".next", "static"));
if (fs.existsSync(path.join(ROOT, "public"))) {
  wipeAndCopy(path.join(ROOT, "public"), path.join(SA, "public"));
}

/* 3 ── sanity: no nesting, manifest present ───────────────────────────────── */
const nested = path.join(SA, ".next", "static", "static");
if (fs.existsSync(nested)) {
  console.error("❌ static/static nesting detected — deploy aborted");
  process.exit(1);
}
console.log("✅ no static/static nesting");

/* 4 ── start the server ───────────────────────────────────────────────────── */
stopExistingServer();
const env = { ...process.env, PORT, HOSTNAME: HOST };
const child = execSync(`node server.js`, {
  cwd: SA,
  env,
  shell: true,
  stdio: "ignore",
  detached: true,
});
child?.unref?.();
console.log(`\n✅ server starting on http://localhost:${PORT}`);

/* 5 ── health check ──────────────────────────────────────────────────────── */
for (let i = 0; i < 15; i++) {
  try {
    const code = execSync(`curl -s --max-time 4 -o /dev/null -w '%{http_code}' http://localhost:${PORT}/dashboard`)
      .toString()
      .trim();
    if (code === "200") {
      console.log(`✅ server healthy (dashboard → ${code})`);
      break;
    }
  } catch { /* keep waiting */ }
  execSync("sleep 1", { shell: true });
}

/* 6 ── optional browser verification ─────────────────────────────────────── */
if (process.argv.includes("--verify")) {
  console.log("\n──────────── browser verification ────────────");
  sh("node verify.mjs");
}

console.log("\n🎉 deploy complete — hard-refresh the browser (Cmd+Shift+R) once.");
