// AV05 定向取证：同一次页面加载内，同时捕获 analyst 视图接口响应与页签文案，
// 验证「接口 status=ready 的视图是否被页面标记为等待条件」。
// 不同快照不得拼成同一结论（清单 §2.2 第 4 条），故必须同源同时。
// 只读：仅一次导航与 DOM 读取。
import { acquirePage } from "../2026-09-04-r3-cockpit-layout-and-task-loop/cdp-page.mjs";
import { writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const outDir = dirname(fileURLToPath(import.meta.url));
const { browser, page } = await acquirePage();
await page.setViewportSize({ width: 1280, height: 720 });

const captured = [];
page.on("response", async (response) => {
  const url = response.url();
  if (!/\/v1\/ecommerce-workshop\/views\/analyst/.test(url)) return;
  try {
    const body = await response.json();
    captured.push({ url, status: response.status(), body });
  } catch { captured.push({ url, status: response.status(), body: null }); }
});

await page.goto("http://127.0.0.1:5173/workshop/analyst", { waitUntil: "networkidle", timeout: 45000 });
await page.waitForTimeout(3000);

const domTabs = await page.evaluate(() => {
  const clean = (value) => (value ?? "").replace(/\s+/g, " ").trim();
  const tabs = [...document.querySelectorAll("[role='tab'], [class*='tab']")]
    .map((node) => clean(node.textContent))
    .filter((text) => text && text.length < 30);
  const channel = [...document.querySelectorAll("*")].filter((n) => n.children.length === 0).map((n) => clean(n.textContent)).filter((t) => t.includes("渠道"));
  const entity = [...document.querySelectorAll("*")].filter((n) => n.children.length === 0).map((n) => clean(n.textContent)).filter((t) => t.includes("经营实体"));
  return { tabs: [...new Set(tabs)], channelTexts: [...new Set(channel)].slice(0, 6), entityTexts: [...new Set(entity)].slice(0, 6) };
});

// 接口 ready 视图 vs 页面页签状态。响应结构未知，深度递归找带 viewId+status 的对象。
const collectMetrics = (node, out = []) => {
  if (Array.isArray(node)) { for (const item of node) collectMetrics(item, out); return out; }
  if (node && typeof node === "object") {
    if ("viewId" in node && "status" in node) out.push(node);
    for (const value of Object.values(node)) collectMetrics(value, out);
  }
  return out;
};
const metrics = captured.flatMap((c) => collectMetrics(c.body));
writeFileSync(`${outDir}/av05-analyst-raw-response.json`, JSON.stringify(captured.map((c) => ({ url: c.url, status: c.status, topLevelKeys: c.body && typeof c.body === "object" ? Object.keys(c.body) : null, body: c.body })), null, 2));
const byView = {};
for (const metric of metrics) {
  byView[metric.viewId] ??= { total: 0, ready: 0, ids: [] };
  byView[metric.viewId].total += 1;
  if (metric.status === "ready") byView[metric.viewId].ready += 1;
  byView[metric.viewId].ids.push(`${metric.metricId}=${metric.value}(${metric.status})`);
}

const VIEW_LABEL = { overview: "经营总览", drivers: "驱动因素", diagnosis: "问题诊断", quality: "数据质量", plan: "增长计划", review: "效果复盘", evidence: "证据链" };
const conflicts = [];
for (const [viewId, stat] of Object.entries(byView)) {
  const label = VIEW_LABEL[viewId] ?? viewId;
  const tab = domTabs.tabs.find((text) => text.startsWith(label));
  const pageSaysBlocked = tab ? /等待条件|待核对|未就绪/.test(tab) : null;
  if (stat.ready > 0 && pageSaysBlocked) conflicts.push({ viewId, label, tabText: tab, readyMetrics: stat.ready, detail: stat.ids });
  console.log(`${label.padEnd(8)} 接口 ready ${stat.ready}/${stat.total}  页签「${tab ?? "未找到"}」  冲突=${stat.ready > 0 && pageSaysBlocked}`);
}

const report = { capturedAt: new Date().toISOString(), sameLoad: true, route: "/workshop/analyst", responses: captured.map((c) => ({ url: c.url, status: c.status })), metricsByView: byView, domTabs, conflicts };
writeFileSync(`${outDir}/av05-analyst-ready-vs-label.json`, JSON.stringify(report, null, 2));
console.log("\n渠道文案:", JSON.stringify(domTabs.channelTexts, null, 0));
console.log("经营实体文案:", JSON.stringify(domTabs.entityTexts, null, 0));
console.log(`\n冲突数: ${conflicts.length}`);
console.log("saved av05-analyst-ready-vs-label.json");
await browser.close();
