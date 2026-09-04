// R3-07 第 1/8 步只读观察：通过应用自身的已鉴权请求，回读 org-org/dev-project 真实栖月汇业务对象规模。
// 不读取 cookie / localStorage / token，只监听应用发出的响应。仅 GET，不创建任务、不写任何数据。
import { acquirePage } from "./cdp-page.mjs";
import { writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const outDir = dirname(fileURLToPath(import.meta.url));
const { browser, page } = await acquirePage();
await page.setViewportSize({ width: 1440, height: 900 });

const observed = [];
const INTEREST = /\/v1\/(objects\/|ontology\/object-types|ontology\/link-types|data\/source-readiness|ecommerce-workshop\/views\/(analyst|operations|customer)|ecommerce-workshop\/source-readiness)/;

page.on("response", async (response) => {
  const url = response.url();
  if (!INTEREST.test(url)) return;
  const entry = { endpoint: url.replace(/^https?:\/\/[^/]+/, "").split("?")[0], method: response.request().method(), status: response.status() };
  try {
    const body = await response.json();
    if (Array.isArray(body)) entry.itemCount = body.length;
    else if (Array.isArray(body?.items)) { entry.itemCount = body.items.length; entry.total = body.total ?? body.count ?? null; entry.sampleKeys = body.items[0] ? Object.keys(body.items[0]).slice(0, 12) : []; }
    else if (body?.views) entry.metrics = body.views.flatMap((view) => (view.metrics ?? []).map((metric) => ({ viewId: view.viewId, metricId: metric.metricId, status: metric.status, value: metric.value })));
    else if (body?.sources) entry.sources = { count: body.sources.length, status: body.status, ready: body.sources.filter((source) => source.status === "ready").length };
    else entry.shape = Object.keys(body ?? {}).slice(0, 12);
  } catch { entry.unparsed = true; }
  observed.push(entry);
});

const routes = ["/workshop/cockpit", "/workshop/graph", "/ontology/graph-health"];
for (const route of routes) {
  try {
    await page.goto(`http://127.0.0.1:5173${route}`, { waitUntil: "networkidle", timeout: 45000 });
    await page.waitForTimeout(3000);
  } catch (error) { observed.push({ endpoint: route, navigationError: String(error).slice(0, 160) }); }
}

// 去重汇总
const summary = {};
for (const entry of observed) {
  const key = `${entry.method ?? "NAV"} ${entry.endpoint}`;
  if (!summary[key]) summary[key] = entry;
}
const report = { visitedRoutes: routes, observed: Object.values(summary) };
writeFileSync(`${outDir}/canonical-reads-report.json`, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
await browser.close();
