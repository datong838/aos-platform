/**
 * Visible Chrome AIP menu audit via CDP (dedicated profile on :9333).
 * Usage: node audit_aip_menu_visible_cdp.mjs
 */
import { chromium } from "./node_modules/playwright/index.mjs";
import fs from "node:fs";
import path from "node:path";

const BASE = process.env.AIP_WEB_BASE || "http://127.0.0.1:5174";
const CDP = process.env.AIP_CDP || "http://127.0.0.1:9333";
const OUT = process.env.AIP_AUDIT_OUT ||
  "/Users/ddt/work/projects/ai_agent/aos-platform-w1-aip/.evidence/aip/2026-08-19-aip-menu-chrome-visible-audit";
const DWELL_MS = Number(process.env.AIP_AUDIT_DWELL_MS || 1200);

const PAGES = [
  { path: "/aip/assist", label: "AIP 助手" },
  { path: "/aip/studio", label: "对话机器人" },
  { path: "/aip/analyst", label: "AIP 分析师" },
  { path: "/aip/logic", label: "AIP 逻辑画布" },
  { path: "/aip/tools", label: "Agent 工具面板" },
  { path: "/aip/maturity", label: "成熟度楼梯" },
  { path: "/aip/production-contracts", label: "生产契约" },
  { path: "/aip/capabilities", label: "智能体插件" },
  { path: "/aip/agent-registry", label: "智能体目录" },
  { path: "/aip/agents", label: "智能体列表" },
  { path: "/aip/agent-import", label: "智能体导入" },
  { path: "/aip/capability-import", label: "能力导入" },
  { path: "/aip/evals", label: "Evals 门控" },
  { path: "/aip/drafts", label: "Draft 审批台" },
  { path: "/aip/lineage", label: "决策谱系" },
  { path: "/aip/observability", label: "可观测性" },
  { path: "/aip/memory-governance", label: "记忆与知识治理" },
  { path: "/aip/model-catalog", label: "模型目录" },
  { path: "/aip/model-providers", label: "模型供应商" },
  { path: "/aip/model-router", label: "模型路由" },
  { path: "/aip/capacity", label: "容量管理" },
  { path: "/aip/model-runtime", label: "运行就绪" },
];

fs.mkdirSync(path.join(OUT, "screenshots"), { recursive: true });

function classify(bodyText, pageErrors, failedApi) {
  const issues = [];
  const text = bodyText || "";
  if (pageErrors.length) issues.push({ severity: "red", code: "pageerror", detail: pageErrors.slice(0, 3) });
  if (failedApi.some((f) => f.status >= 500)) {
    issues.push({
      severity: "red",
      code: "api_5xx",
      detail: failedApi.filter((f) => f.status >= 500).slice(0, 5),
    });
  }
  if (/Something went wrong|Application Error|白屏|Uncaught/i.test(text)) {
    issues.push({ severity: "red", code: "crash_copy", detail: "crash-like copy" });
  }
  if (/目录读取失败|modules.*500|REGISTRY_INTEGRITY/i.test(text)) {
    issues.push({ severity: "red", code: "nav_catalog", detail: "sidebar catalog failure" });
  }
  if (/暂无智能体/.test(text) && /studio/i.test(arguments[0] || "")) {
    /* path-aware below */
  }
  const warnApi = failedApi.filter((f) => f.status >= 400 && f.status < 500 && !/AIP_CANONICAL_OVERLAY|LEGACY_AGENT/.test(JSON.stringify(f)));
  if (warnApi.length) issues.push({ severity: "warn", code: "api_4xx", detail: warnApi.slice(0, 5) });
  if (!text.trim() || text.trim().length < 40) {
    issues.push({ severity: "red", code: "empty_body", detail: "main body too short" });
  }
  const severity = issues.some((i) => i.severity === "red")
    ? "red"
    : issues.some((i) => i.severity === "warn")
      ? "warn"
      : "green";
  return { severity, issues };
}

const browser = await chromium.connectOverCDP(CDP);
const context = browser.contexts()[0] || (await browser.newContext());
let page = context.pages().find((p) => (p.url() || "").includes("127.0.0.1:5174"))
  || context.pages()[0]
  || (await context.newPage());

await page.bringToFront().catch(() => {});

const results = [];
for (const item of PAGES) {
  const pageErrors = [];
  const failedApi = [];
  const onError = (err) => pageErrors.push(String(err?.message || err));
  const onResponse = (res) => {
    try {
      const u = res.url();
      if (!u.includes("/api/") && !u.includes("/v1/")) return;
      const status = res.status();
      if (status >= 400) failedApi.push({ url: u.slice(0, 180), status });
    } catch {
      /* ignore */
    }
  };
  page.on("pageerror", onError);
  page.on("response", onResponse);

  const url = `${BASE}${item.path}`;
  let navOk = true;
  let clickMode = "goto";
  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
    // Prefer visible sidebar click when label is present (user can watch)
    const navLink = page.locator(`nav a, aside a, [data-nav] a, a`).filter({ hasText: item.label }).first();
    if (await navLink.count().catch(() => 0)) {
      try {
        await navLink.click({ timeout: 2500 });
        clickMode = "sidebar_click";
        await page.waitForTimeout(400);
      } catch {
        clickMode = "goto_fallback";
      }
    }
  } catch (e) {
    navOk = false;
    pageErrors.push(`navigation: ${String(e.message || e)}`);
  }

  await page.waitForTimeout(DWELL_MS);
  const bodyText = await page.locator("main, [role='main'], #root, body").first().innerText().catch(() => "");
  const title = await page.title().catch(() => "");
  const finalUrl = page.url();
  let shot = null;
  try {
    const name = item.path.replace(/\//g, "_").replace(/^_/, "") || "root";
    shot = path.join(OUT, "screenshots", `${name}.png`);
    await page.screenshot({ path: shot, fullPage: false });
  } catch (e) {
    pageErrors.push(`screenshot: ${String(e.message || e)}`);
  }

  page.off("pageerror", onError);
  page.off("response", onResponse);

  let { severity, issues } = classify(bodyText, pageErrors, failedApi);
  if (item.path === "/aip/studio" && /暂无智能体/.test(bodyText) && !/内容官|数据参谋|活动策划/.test(bodyText)) {
    issues = [...issues, { severity: "red", code: "studio_fake_empty", detail: "Studio shows empty agents" }];
    severity = "red";
  }
  if (!navOk) severity = "red";

  const row = {
    path: item.path,
    label: item.label,
    severity,
    clickMode,
    finalUrl,
    title,
    issueCount: issues.length,
    issues,
    screenshot: shot,
    bodyPreview: bodyText.replace(/\s+/g, " ").slice(0, 220),
  };
  results.push(row);
  console.log(JSON.stringify({ progress: `${results.length}/${PAGES.length}`, ...row, bodyPreview: undefined, issues: issues.map((i) => i.code) }));
}

const summary = {
  auditedAt: new Date().toISOString(),
  base: BASE,
  cdp: CDP,
  count: results.length,
  green: results.filter((r) => r.severity === "green").length,
  warn: results.filter((r) => r.severity === "warn").length,
  red: results.filter((r) => r.severity === "red").length,
  pages: results,
};
fs.writeFileSync(path.join(OUT, "audit-summary.json"), JSON.stringify(summary, null, 2));
console.log(JSON.stringify({ done: true, green: summary.green, warn: summary.warn, red: summary.red, out: OUT }, null, 2));
// Keep CDP browser alive for the user
await browser.close().catch(() => {});
