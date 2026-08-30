/* Fast, tightly-bounded browser verification. Writes results to /tmp/verify_results.txt. */
import puppeteer from "puppeteer-core";
import fs from "node:fs";

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const BASE = "http://localhost:3000";
const OUT = "/tmp/verify_results.txt";
const lines = [];
const log = (s) => { lines.push(s); console.log(s); };

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
});
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 900 });

const errors = [];
let current = "?";
page.on("console", (msg) => { if (msg.type() === "error") errors.push(`[${current}] console: ${msg.text()}`); });
page.on("pageerror", (err) => errors.push(`[${current}] pageerror: ${err.message}`));

const results = [];
const withTimeout = (p, ms, label) =>
  Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error(`TIMEOUT ${label}`)), ms))]);

async function testPage(path, marker, fn, wait = 1500) {
  current = path;
  let ok = false, extra = "";
  try {
    await withTimeout(page.goto(`${BASE}${path}`, { waitUntil: "domcontentloaded", timeout: 15000 }), 20000, `goto`);
    await new Promise((r) => setTimeout(r, wait));
    ok = await withTimeout(page.evaluate((m) => document.body.innerText.includes(m), marker), 8000, `marker`);
    if (fn) extra = await withTimeout(fn(), 25000, `fn`);
  } catch (err) {
    extra = `ERR: ${String(err).slice(0, 90)}`;
  }
  results.push({ path, marker, ok, extra });
  log(`  ${ok ? "✅" : "❌"} ${path} ${extra.slice(0, 80)}`);
}

const PAGES = [
  ["/dashboard", "Executive Dashboard"],
  ["/digital-twin", "Digital Twin"],
  ["/simulator", "Scenario Simulator"],
  ["/sc-simulator", "SC Scenario Simulator"],
  ["/command-center", "Command Center"],
  ["/market-watch", "Market Watch"],
  // /comparison intentionally removed from the app (dead feature).
  ["/insights", "Business Insights"],
  ["/supply-chain", "Supply Chain"],
  ["/suppliers", "Supplier Management"],
  ["/inventory", "Inventory Management"],
  ["/logistics", "Logistics Dashboard"],
  ["/alerts", "Alerts Center"],
  ["/chat", "AI Assistant"],
  ["/reports", "Reports"],
  ["/timeline", "Business Timeline"],
  ["/settings", "Settings"],
];

for (const [path, marker] of PAGES) await testPage(path, marker);

await testPage("/digital-twin", "Digital Twin", async () => {
  const n = await page.evaluate(() => document.querySelectorAll(".react-flow__node").length);
  await page.screenshot({ path: "/tmp/bta_shots/digital-twin.png" }).catch(() => {});
  return `canvas nodes: ${n}`;
}, 1800);

await testPage("/chat", "AI Assistant", async () => {
  const clicked = await page.evaluate(() => {
    const b = Array.from(document.querySelectorAll("button")).find((x) => x.textContent?.includes("increase prices"));
    if (b) { b.click(); return true; }
    return false;
  });
  await new Promise((r) => setTimeout(r, 15000));
  const answered = await page.evaluate(
    () => document.body.innerText.includes("Recommendation") || document.body.innerText.includes("Agentic Assessment") || document.body.innerText.includes("✅ Workspace")
  );
  return `clicked:${clicked} answered:${answered}`;
}, 1000);

await testPage("/simulator", "Scenario Simulator", async () => {
  const clicked = await page.evaluate(() => {
    const b = Array.from(document.querySelectorAll("button")).find((x) => x.textContent?.includes("Run Analysis"));
    if (b) { b.click(); return true; }
    return false;
  });
  await new Promise((r) => setTimeout(r, 6000));
  const results2 = await page.evaluate(() => document.body.innerText.includes("Side-by-side comparison"));
  return `ran:${clicked} results:${results2}`;
}, 1000);

await browser.close().catch(() => {});

const passed = results.filter((r) => r.ok).length;
log(`\n${passed}/${results.length} checks passed`);
const pageErrors = errors.filter((e) => e.includes("pageerror"));
log(`page errors: ${pageErrors.length}`);
pageErrors.slice(0, 10).forEach((e) => log(`  ⚠ ${e}`));
const others = errors.filter((e) => !e.includes("pageerror") && !e.includes("favicon") && !e.includes("React DevTools"));
log(`other console errors: ${others.length}`);
others.slice(0, 10).forEach((e) => log(`  ⚠ ${e}`));

fs.writeFileSync(OUT, lines.join("\n"));
process.exit(pageErrors.length === 0 && passed === results.length ? 0 : 1);
