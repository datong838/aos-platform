// R3-07 第 1/8 步只读观察：统计 org-org/dev-project 真实 Order 对象的字段分布，
// 用于确定"哪些真实业务对象值得派生任务"的 canonical 筛选口径（不凭空编造条件）。
// 仅监听应用自身的已鉴权 GET 响应；不读 token，不写任何数据。
import { acquirePage } from "./cdp-page.mjs";
import { writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const outDir = dirname(fileURLToPath(import.meta.url));
const { browser, page } = await acquirePage();
await page.setViewportSize({ width: 1440, height: 900 });

let orders = null;
page.on("response", async (response) => {
  if (!/\/v1\/objects\/Order(\?|$)/.test(response.url())) return;
  try { const body = await response.json(); if (Array.isArray(body?.items)) orders = body.items; } catch { /* ignore */ }
});

await page.goto("http://127.0.0.1:5173/workshop/graph", { waitUntil: "networkidle", timeout: 45000 });
await page.waitForTimeout(4000);

if (!orders) { console.log(JSON.stringify({ error: "未观察到 /v1/objects/Order 响应" })); await browser.close(); process.exit(1); }

const tally = (key) => {
  const counts = {};
  for (const order of orders) { const value = String(order[key]); counts[value] = (counts[value] ?? 0) + 1; }
  return Object.fromEntries(Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 12));
};
const numeric = (key) => {
  const values = orders.map((order) => order[key]).filter((value) => typeof value === "number");
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  return { count: values.length, min: sorted[0], p50: sorted[Math.floor(sorted.length * 0.5)], p90: sorted[Math.floor(sorted.length * 0.9)], max: sorted.at(-1) };
};

const report = {
  orderCount: orders.length,
  propertyKeys: [...new Set(orders.flatMap((order) => Object.keys(order)))].sort(),
  status: tally("status"),
  payStatus: tally("payStatus"),
  isDelete: tally("isDelete"),
  shopId: tally("shopId"),
  currency: tally("currency"),
  riskScore: numeric("risk_score"),
  createdAtRange: (() => {
    const dates = orders.map((order) => order.createdAt).filter(Boolean).sort();
    return { min: dates[0] ?? null, max: dates.at(-1) ?? null };
  })(),
  sample: orders.slice(0, 2).map((order) => ({ id: order.id, orderNo: order.orderNo, status: order.status, payStatus: order.payStatus, risk_score: order.risk_score, createdAt: order.createdAt })),
};

writeFileSync(`${outDir}/order-distribution.json`, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
await browser.close();
