#!/usr/bin/env node
/**
 * AIP menu browser deep audit — org-org/dev-project only.
 * Does not touch w2-workshop. Does not replay sealed pilots.
 */
import { chromium } from "playwright";
import fs from "fs";
import path from "path";

const BASE = process.env.AOS_WEB_BASE || "http://127.0.0.1:5173";
const OUT = process.env.AOS_AUDIT_OUT ||
  "/Users/ddt/work/projects/ai_agent/aos-platform-w1-aip/.evidence/aip/2026-08-19-aip-menu-browser-audit";

const PAGES = [
  { id: "aip-assist", label: "AIP 助手", path: "/aip/assist", expectTitle: /AIP 助手|助手/ },
  { id: "aip-studio", label: "对话机器人", path: "/aip/studio", expectTitle: /对话机器人|Studio|机器人/ },
  { id: "aip-analyst", label: "AIP 分析师", path: "/aip/analyst", expectTitle: /分析师|Analyst/ },
  { id: "aip-logic", label: "AIP 逻辑画布", path: "/aip/logic", expectTitle: /逻辑|画布|Logic/ },
  { id: "aip-tools", label: "Agent 工具面板", path: "/aip/tools", expectTitle: /工具|Tools|Agent/ },
  { id: "aip-maturity", label: "成熟度楼梯", path: "/aip/maturity", expectTitle: /成熟度|楼梯|Maturity/ },
  { id: "aip-production-contracts", label: "生产契约", path: "/aip/production-contracts", expectTitle: /生产契约|契约/ },
  { id: "aip-capabilities", label: "智能体插件", path: "/aip/capabilities", expectTitle: /插件|Capability|能力/ },
  { id: "aip-agent-registry", label: "智能体目录", path: "/aip/agent-registry", expectTitle: /智能体目录|目录/ },
  { id: "aip-agents", label: "智能体列表", path: "/aip/agents", expectTitle: /智能体列表|实例|列表/ },
  { id: "aip-agent-import", label: "智能体导入", path: "/aip/agent-import", expectTitle: /导入|Import/ },
  { id: "aip-capability-import", label: "能力导入", path: "/aip/capability-import", expectTitle: /能力导入|导入/ },
  { id: "aip-evals", label: "Evals 门控", path: "/aip/evals", expectTitle: /Eval|门控|评测/ },
  { id: "aip-drafts", label: "Draft 审批台", path: "/aip/drafts", expectTitle: /Draft|审批|草稿/ },
  { id: "aip-lineage", label: "决策谱系", path: "/aip/lineage", expectTitle: /谱系|Lineage|决策/ },
  { id: "aip-observability", label: "可观测性", path: "/aip/observability", expectTitle: /可观测|Observability/ },
  { id: "aip-memory-governance", label: "记忆与知识治理", path: "/aip/memory-governance", expectTitle: /记忆|知识|治理/ },
  { id: "aip-model-catalog", label: "模型目录", path: "/aip/model-catalog", expectTitle: /模型目录|目录/ },
  { id: "aip-model-providers", label: "模型供应商", path: "/aip/model-providers", expectTitle: /供应商|Provider/ },
  { id: "aip-model-router", label: "模型路由", path: "/aip/model-router", expectTitle: /模型路由|路由/ },
  { id: "aip-capacity", label: "容量管理", path: "/aip/capacity", expectTitle: /容量|Capacity/ },
  { id: "aip-model-runtime", label: "运行就绪", path: "/aip/model-runtime", expectTitle: /运行就绪|就绪|Runtime/ },
];

function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true });
}

async function clickSafeReadonly(page) {
  const clicks = [];
  const candidates = [
    'button:has-text("刷新")',
    'button:has-text("展开")',
    'button:has-text("收起")',
    '[role="tab"]',
    'button:has-text("重新加载")',
  ];
  for (const sel of candidates) {
    const loc = page.locator(sel).first();
    if ((await loc.count()) === 0) continue;
    if (!(await loc.isVisible().catch(() => false))) continue;
    if (await loc.isDisabled().catch(() => true)) continue;
    try {
      await loc.click({ timeout: 1500 });
      clicks.push(sel);
      await page.waitForTimeout(400);
    } catch (e) {
      clicks.push(`${sel}:fail:${String(e.message || e).slice(0, 80)}`);
    }
  }
  return clicks;
}

async function auditOne(browser, item) {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 960 },
  });
  const page = await context.newPage();
  const consoleErrors = [];
  const pageErrors = [];
  const failedResponses = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text().slice(0, 300));
  });
  page.on("pageerror", (err) => pageErrors.push(String(err).slice(0, 300)));
  page.on("response", (res) => {
    const status = res.status();
    const url = res.url();
    if (status >= 500 && url.includes("/v1/")) {
      failedResponses.push({ status, url: url.slice(0, 200) });
    }
  });

  const url = `${BASE}${item.path}`;
  let navError = null;
  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForTimeout(1800);
  } catch (e) {
    navError = String(e.message || e).slice(0, 300);
  }

  // Ensure tenant default is org-org/dev-project in session if app uses sessionStorage
  await page.evaluate(() => {
    try {
      const key = "aos-tenant-v1";
      const desired = {
        orgId: "org-org",
        projectId: "dev-project",
        workspaceName: "默认工作区",
      };
      sessionStorage.setItem(key, JSON.stringify(desired));
    } catch (_) {}
  });
  // Reload once so tenant sticks for pages that read storage at boot
  if (!navError) {
    try {
      await page.reload({ waitUntil: "domcontentloaded", timeout: 30000 });
      await page.waitForTimeout(2000);
    } catch (e) {
      navError = String(e.message || e).slice(0, 300);
    }
  }

  const bodyText = (await page.locator("body").innerText().catch(() => "")).slice(0, 4000);
  const titleText = (
    await page.locator("h1, h2, [data-page-title], .page-chrome h1, .PageChrome h1").first().innerText().catch(() => "")
  ).trim();
  const hasBlank = !bodyText || bodyText.trim().length < 20;
  const titleOk = item.expectTitle.test(titleText) || item.expectTitle.test(bodyText.slice(0, 500));
  const honestBlock =
    /失败|不可用|阻断|blocked|empty|暂无|尚未|读取失败|离线|OFFLINE|fail-closed|未安装/i.test(bodyText);
  const fakeSuccess = /全部成功|mock成功|演示数据已写入/i.test(bodyText);
  const shellCatalogFail = /目录读取失败/.test(bodyText);
  const modules5xx = failedResponses.some((r) =>
    String(r.url).includes("/v1/ecommerce-workshop/modules")
  );

  let clicks = [];
  if (!navError && !hasBlank) {
    clicks = await clickSafeReadonly(page);
  }

  const shot = path.join(OUT, "screenshots", `${item.id}.png`);
  ensureDir(path.dirname(shot));
  await page.screenshot({ path: shot, fullPage: true }).catch(() => null);

  const severity = [];
  if (navError) severity.push("NAV_FAIL");
  if (hasBlank) severity.push("BLANK");
  if (!titleOk) severity.push("TITLE_MISMATCH");
  if (pageErrors.length) severity.push("PAGE_ERROR");
  if (failedResponses.length) severity.push("API_5XX");
  if (fakeSuccess) severity.push("FAKE_SUCCESS");
  if (shellCatalogFail || modules5xx) severity.push("SHELL_CATALOG_FAIL");

  const status = severity.length ? "RED" : "GREEN";
  await context.close();

  return {
    id: item.id,
    label: item.label,
    path: item.path,
    url,
    status,
    severity,
    titleText,
    titleOk,
    hasBlank,
    honestBlock,
    fakeSuccess,
    shellCatalogFail,
    modules5xx,
    navError,
    consoleErrors: consoleErrors.slice(0, 12),
    pageErrors: pageErrors.slice(0, 12),
    failedResponses: failedResponses.slice(0, 20),
    clicks,
    screenshot: shot,
    bodyPreview: bodyText.slice(0, 400),
  };
}

async function main() {
  ensureDir(OUT);
  ensureDir(path.join(OUT, "screenshots"));
  const browser = await chromium.launch({
    headless: true,
    executablePath:
      process.env.PLAYWRIGHT_CHROME ||
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  });

  const results = [];
  for (const item of PAGES) {
    process.stdout.write(`audit ${item.path} ... `);
    const row = await auditOne(browser, item);
    results.push(row);
    console.log(row.status, (row.severity || []).join(",") || "ok");
  }
  await browser.close();

  const summary = {
    schema: "aip-menu-browser-audit/v1",
    recordedAt: new Date().toISOString(),
    scope: { orgId: "org-org", projectId: "dev-project" },
    base: BASE,
    pageCount: results.length,
    greenCount: results.filter((r) => r.status === "GREEN").length,
    redCount: results.filter((r) => r.status === "RED").length,
    results,
  };
  const outFile = path.join(OUT, "audit.json");
  fs.writeFileSync(outFile, JSON.stringify(summary, null, 2) + "\n");
  console.log(`\nWrote ${outFile}`);
  console.log(`GREEN ${summary.greenCount} / RED ${summary.redCount}`);
  process.exit(summary.redCount ? 2 : 0);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
