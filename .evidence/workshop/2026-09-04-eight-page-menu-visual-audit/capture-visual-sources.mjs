// 按清单 §3 第 1 条采集正式视觉稿同视口截图，与实页截图构成成对对账证据。
// 只读：本地 file:// 渲染静态视觉稿，不访问业务接口、不写任何数据。
import { acquirePage } from "../2026-09-04-r3-cockpit-layout-and-task-loop/cdp-page.mjs";
import { writeFileSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const outDir = dirname(fileURLToPath(import.meta.url));
const foundry = resolve(outDir, "../../../../docs/palantier/foundry/html");

const PAIRS = [
  { key: "01-cockpit", visual: "workshop-task-cockpit.html", label: "日常任务总控大屏" },
  { key: "02-content-campaign", visual: "workshop-content-campaign.html", label: "内容与活动工作台" },
  { key: "03-operations", visual: "workshop-app-order.html", label: "统一运营驾驶舱（正确基线，非 workshop-cop.html）" },
  { key: "04-creator-growth", visual: "workshop-creator-outreach.html", label: "达人邀约驾驶舱" },
  { key: "05-media-studio", visual: "workshop-media-studio.html", label: "多媒体内容生产" },
  { key: "06-analyst", visual: "workshop-analyst.html", label: "经营参谋 · 增长指挥中心" },
  { key: "07-price-governance", visual: "workshop-price-governance.html", label: "价格治理驾驶舱" },
  { key: "08-customer", visual: "workshop-customer.html", label: "客户关系工作台" },
];
const VIEWPORTS = [
  { name: "1280x720", width: 1280, height: 720 },
  { name: "1440x900", width: 1440, height: 900 },
  { name: "1920x1080", width: 1920, height: 1080 },
];

const { browser, page } = await acquirePage();
const report = [];

for (const pair of PAIRS) {
  const file = `${foundry}/${pair.visual}`;
  if (!existsSync(file)) { report.push({ ...pair, error: "视觉稿文件不存在" }); console.log(`${pair.key} MISSING ${pair.visual}`); continue; }
  const entry = { ...pair, viewports: {} };
  for (const viewport of VIEWPORTS) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.goto(`file://${file}`, { waitUntil: "load", timeout: 30000 });
    await page.waitForTimeout(800);
    const dom = await page.evaluate(() => {
      const clean = (value) => (value ?? "").replace(/\s+/g, " ").trim();
      return {
        h1: [...document.querySelectorAll("h1")].map((node) => clean(node.textContent)).slice(0, 3),
        h2Count: document.querySelectorAll("h2").length,
        h3Count: document.querySelectorAll("h3").length,
        navLinkCount: (document.querySelector("nav.nav") ?? document.querySelector("nav"))?.querySelectorAll("a").length ?? 0,
        buttonCount: document.querySelectorAll("button").length,
        tabCount: document.querySelectorAll("[role='tab'], .tab, [class*='tab-']").length,
        listItemCount: document.querySelectorAll("li").length,
        horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
      };
    });
    await page.screenshot({ path: `${outDir}/${pair.key}-VISUAL-${viewport.name}.png` });
    entry.viewports[viewport.name] = dom;
  }
  report.push(entry);
  const first = entry.viewports["1280x720"];
  console.log(`${pair.key.padEnd(20)} visualH2/H3=${first.h2Count}/${first.h3Count} visualNavLinks=${first.navLinkCount} visualButtons=${first.buttonCount} visualTabs=${first.tabCount} visualLi=${first.listItemCount}`);
}

writeFileSync(`${outDir}/visual-source-audit.json`, JSON.stringify({ capturedAt: new Date().toISOString(), foundry, pairs: report }, null, 2));
console.log("\nsaved visual-source-audit.json");
await browser.close();
