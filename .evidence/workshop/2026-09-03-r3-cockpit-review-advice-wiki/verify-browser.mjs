// R3-06 内置浏览器只读验收：连接本地 CDP，回读右侧复盘三段的 canonical 呈现。
// 只读脚本：不提交候选、不审批、不 promote、不发布 Wiki、不触发任何写命令。
import { chromium } from "playwright-core";
import { mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const CDP = "http://127.0.0.1:9333";
const TARGET = "http://127.0.0.1:5173/workshop/cockpit";
const outDir = dirname(fileURLToPath(import.meta.url));
mkdirSync(outDir, { recursive: true });

const browser = await chromium.connectOverCDP(CDP);
const context = browser.contexts()[0];
const owned = context.pages().find((page) => page.url().startsWith("http://127.0.0.1:5173/"));
const page = owned ?? (await context.newPage());
await page.setViewportSize({ width: 1680, height: 1050 });
const observedReads = [];
page.on("response", async (response) => {
  const url = response.url();
  if (!/memory-authority\/(improvement-observations|candidates|memories)(\?|$)/.test(url)) return;
  let count = null;
  try { const body = await response.json(); count = Array.isArray(body) ? body.length : typeof body; } catch { count = "unparsed"; }
  observedReads.push({ endpoint: url.replace(/^.*memory-authority\//, ""), method: response.request().method(), status: response.status(), count });
});
await page.goto(TARGET, { waitUntil: "networkidle", timeout: 45000 });
await page.waitForSelector(".task-cockpit-visual-review", { timeout: 30000 });
await page.waitForTimeout(2500);

const report = await page.evaluate(() => {
  const review = document.querySelector(".task-cockpit-visual-review");
  const sections = [...document.querySelectorAll(".task-cockpit-visual-review .task-cockpit-review-section")];
  const clean = (value) => (value ?? "").replace(/\s+/g, " ").trim();
  return {
    url: location.href,
    reviewPresent: Boolean(review),
    sectionCount: sections.length,
    headings: sections.map((section) => clean(section.querySelector("h3")?.textContent)),
    ariaLabels: sections.map((section) => section.getAttribute("aria-label")),
    sections: sections.map((section) => ({
      label: section.getAttribute("aria-label"),
      scrollable: section.scrollHeight > section.clientHeight || [...section.querySelectorAll("ul")].some((list) => list.scrollHeight > list.clientHeight),
      text: clean(section.textContent).slice(0, 900),
    })),
    forbiddenSampleText: ["有效 6", "有害", "CN-05", "AFT-03", "VIP3过敏处理SOP"].filter((token) => clean(review?.textContent).includes(token)),
    writeControls: [...document.querySelectorAll(".task-cockpit-visual-review button")].map((button) => clean(button.textContent)),
    kpiPresent: Boolean(document.querySelector(".task-cockpit-visual-metrics")),
    capabilityCount: document.querySelectorAll(".task-cockpit-visual-skills button").length,
  };
});

await page.screenshot({ path: `${outDir}/01-cockpit-review-three-sections.png`, fullPage: false });
const reviewBox = await page.locator(".task-cockpit-visual-review").first();
await reviewBox.screenshot({ path: `${outDir}/02-review-column.png` });

console.log(JSON.stringify({ ...report, observedReads }, null, 2));
if (!owned) await page.close();
await browser.close();
