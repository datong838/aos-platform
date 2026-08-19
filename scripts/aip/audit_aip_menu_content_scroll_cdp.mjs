/**
 * Deep AIP menu content audit: scroll to bottom, flag product gaps (blocked ≠ OK).
 * Visible Chrome via CDP :9333. Base :5174 (w1).
 */
import { chromium } from "./node_modules/playwright/index.mjs";
import fs from "node:fs";
import path from "node:path";

const BASE = process.env.AIP_WEB_BASE || "http://127.0.0.1:5174";
const CDP = process.env.AIP_CDP || "http://127.0.0.1:9333";
const HEADLESS = process.env.AIP_AUDIT_HEADLESS === "1" || process.env.AIP_AUDIT_HEADLESS === "true";
const OUT =
  process.env.AIP_AUDIT_OUT ||
  (HEADLESS
    ? "/Users/ddt/work/projects/ai_agent/aos-platform-w1-aip/.evidence/aip/2026-08-19-aip-menu-headless-scroll-audit"
    : "/Users/ddt/work/projects/ai_agent/aos-platform-w1-aip/.evidence/aip/2026-08-19-aip-menu-content-scroll-audit");
const DWELL_MS = Number(process.env.AIP_AUDIT_DWELL_MS || 900);
const STEP_PAUSE_MS = Number(process.env.AIP_AUDIT_STEP_MS || 350);

const PAGES = [
  { path: "/aip/assist", label: "AIP 助手", mock: "aip-assist.html" },
  { path: "/aip/studio", label: "对话机器人", mock: "NO_MOCK" },
  { path: "/aip/analyst", label: "AIP 分析师", mock: "aip-analyst.html" },
  { path: "/aip/logic", label: "AIP 逻辑画布", mock: "aip-logic.html" },
  { path: "/aip/tools", label: "Agent 工具面板", mock: "aip-tools.html" },
  { path: "/aip/maturity", label: "成熟度楼梯", mock: "aip-maturity.html" },
  { path: "/aip/production-contracts", label: "生产契约", mock: "NO_MOCK" },
  { path: "/aip/capabilities", label: "智能体插件", mock: "aip-capabilities.html" },
  { path: "/aip/agent-registry", label: "智能体目录", mock: "NO_MOCK" },
  { path: "/aip/agents", label: "智能体列表", mock: "NO_MOCK" },
  { path: "/aip/agent-import", label: "智能体导入", mock: "aip-agent-import.html" },
  { path: "/aip/capability-import", label: "能力导入", mock: "aip-capability-import.html" },
  { path: "/aip/evals", label: "Evals 门控", mock: "aip-evals.html" },
  { path: "/aip/drafts", label: "Draft 审批台", mock: "aip-draft-inbox.html" },
  { path: "/aip/lineage", label: "决策谱系", mock: "aip-decision-lineage.html" },
  { path: "/aip/observability", label: "可观测性", mock: "aip-observability.html" },
  { path: "/aip/memory-governance", label: "记忆与知识治理", mock: "NO_MOCK" },
  { path: "/aip/model-catalog", label: "模型目录", mock: "aip-model-catalog.html" },
  { path: "/aip/model-providers", label: "模型供应商", mock: "aip-model-providers.html" },
  { path: "/aip/model-router", label: "模型路由", mock: "aip-model-router.html" },
  { path: "/aip/capacity", label: "容量管理", mock: "aip-capacity-management.html" },
  { path: "/aip/model-runtime", label: "运行就绪", mock: "NO_MOCK" },
];

fs.mkdirSync(path.join(OUT, "screenshots"), { recursive: true });

async function findScrollRoot(page) {
  return page.evaluate(() => {
    // Prefer the app content pane (.content), never the sidebar nav.
    const ranked = [];
    const push = (el, bonus = 0) => {
      if (!el) return;
      const st = getComputedStyle(el);
      const oy = st.overflowY;
      const delta = Math.max(0, (el.scrollHeight || 0) - (el.clientHeight || 0));
      const scrollable = oy === "auto" || oy === "scroll" || oy === "overlay" || delta > 40;
      if (!scrollable && delta <= 40) return;
      if (el.closest?.("nav, aside, .nav, [data-nav]")) return;
      ranked.push({ el, delta: delta + bonus });
    };
    push(document.querySelector(".content"), 500);
    push(document.querySelector("[data-scroll-root]"), 200);
    push(document.querySelector("main .content"));
    push(document.querySelector("main"));
    push(document.querySelector("[role='main']"));
    for (const el of document.querySelectorAll(".overflow-auto, .overflow-y-auto")) push(el);
    ranked.sort((a, b) => b.delta - a.delta);
    const best = ranked[0]?.el || document.scrollingElement || document.documentElement;
    const id =
      best === document.scrollingElement || best === document.documentElement
        ? "document"
        : best.tagName + (best.className ? "." + String(best.className).split(/\s+/).slice(0, 2).join(".") : "");
    return { id, scrollHeight: best.scrollHeight || 0, clientHeight: best.clientHeight || 0, delta: Math.max(0, (best.scrollHeight || 0) - (best.clientHeight || 0)) };
  });
}

async function scrollRootBy(page, y) {
  await page.evaluate((targetY) => {
    const ranked = [];
    const push = (el, bonus = 0) => {
      if (!el) return;
      const st = getComputedStyle(el);
      const oy = st.overflowY;
      const delta = Math.max(0, (el.scrollHeight || 0) - (el.clientHeight || 0));
      const scrollable = oy === "auto" || oy === "scroll" || oy === "overlay" || delta > 40;
      if (!scrollable && delta <= 40) return;
      if (el.closest?.("nav, aside, .nav, [data-nav]")) return;
      ranked.push({ el, delta: delta + bonus });
    };
    push(document.querySelector(".content"), 500);
    push(document.querySelector("[data-scroll-root]"), 200);
    push(document.querySelector("main .content"));
    push(document.querySelector("main"));
    push(document.querySelector("[role='main']"));
    for (const el of document.querySelectorAll(".overflow-auto, .overflow-y-auto")) push(el);
    ranked.sort((a, b) => b.delta - a.delta);
    const best = ranked[0]?.el || document.scrollingElement || document.documentElement;
    if (best === document.scrollingElement || best === document.documentElement || best === document.body) {
      window.scrollTo(0, targetY);
    } else {
      best.scrollTop = targetY;
    }
  }, y);
}

async function scrollToBottomStepped(page) {
  const meta = await findScrollRoot(page);
  const steps = [];
  const maxY = Math.max(0, meta.scrollHeight - meta.clientHeight);
  const step = Math.max(280, Math.floor(meta.clientHeight * 0.75) || 400);
  let y = 0;
  while (y < maxY) {
    await scrollRootBy(page, y);
    await page.waitForTimeout(STEP_PAUSE_MS);
    steps.push(y);
    y += step;
  }
  await scrollRootBy(page, maxY);
  await page.waitForTimeout(STEP_PAUSE_MS);
  steps.push(maxY);
  const after = await findScrollRoot(page);
  return { ...after, steps, reachedBottom: true, maxY };
}

function classifyProduct({ bodyText, pageErrors, failedApi, path: pagePath, disabledPrimaryCount, blockedCount, cardCount }) {
  const issues = [];
  const text = bodyText || "";

  if (pageErrors.length) issues.push({ severity: "crash", code: "pageerror", detail: pageErrors.slice(0, 3) });
  if (failedApi.some((f) => f.status >= 500)) {
    issues.push({
      severity: "crash",
      code: "api_5xx",
      detail: failedApi.filter((f) => f.status >= 500).slice(0, 5),
    });
  }
  if (/Something went wrong|Application Error|白屏|Uncaught/i.test(text)) {
    issues.push({ severity: "crash", code: "crash_copy", detail: "crash-like copy" });
  }
  if (/目录读取失败|REGISTRY_INTEGRITY/i.test(text)) {
    issues.push({ severity: "crash", code: "nav_catalog", detail: "sidebar catalog failure" });
  }
  if (!text.trim() || text.trim().length < 40) {
    issues.push({ severity: "crash", code: "empty_body", detail: "main body too short" });
  }

  // Product gaps: blocked / disabled without usable path
  // 「未绑定」is an honest unbound state with CTA — not the same as operational blocked.
  const unboundHonest = /未绑定/.test(text) && /去目录绑定|智能体目录/.test(text);
  if (blockedCount >= 2 && !unboundHonest) {
    issues.push({
      severity: "product_gap",
      code: "many_blocked",
      detail: `blockedCount=${blockedCount}`,
    });
  }
  if (/\bblocked\b/i.test(text) && /依赖未齐|快照不可用|预检（依赖|激活（快照/i.test(text) && !unboundHonest) {
    issues.push({
      severity: "product_gap",
      code: "capability_blocked_cards",
      detail: "capability cards blocked with disabled activate/precheck",
    });
  }
  if (/控制面：阻断(?!.*部分)/.test(text) && !/控制面：部分就绪|控制面：就绪/.test(text)) {
    issues.push({ severity: "product_gap", code: "control_plane_blocked", detail: "runtime control plane blocked banner" });
  }
  if (/AOS Web \(scaffold\)/.test(text) === false && true) {
    /* title checked separately */
  }
  // Only flag main-pane placeholders (nav also contains 「占位」 menu badges).
  if (/coming soon|TODO 实现|尚未实现|Not implemented|主区占位|页面占位/i.test(text)) {
    issues.push({ severity: "product_gap", code: "placeholder_copy", detail: "placeholder / not-implemented copy" });
  }
  if (pagePath === "/aip/studio" && /暂无智能体/.test(text) && !/内容官|数据参谋|活动策划/.test(text)) {
    issues.push({ severity: "product_gap", code: "studio_fake_empty", detail: "Studio empty agents" });
  }
  if (disabledPrimaryCount >= 2 && blockedCount >= 1 && !unboundHonest) {
    issues.push({
      severity: "product_gap",
      code: "primary_ctas_disabled",
      detail: `disabledPrimaryCount=${disabledPrimaryCount}`,
    });
  }
  if (/目录可用 0|active 0|组织绑定 0/.test(text) && pagePath === "/aip/capabilities" && !unboundHonest) {
    issues.push({ severity: "product_gap", code: "capability_zero_ready", detail: "capabilities catalog not ready for org" });
  }
  // Unbound capability catalog with CTA is acceptable honesty relative to visual "已接入" target.
  if (pagePath === "/aip/capabilities" && unboundHonest && /组织绑定 [1-9]|active [1-9]/.test(text)) {
    issues.push({
      severity: "warn",
      code: "capability_partial_bound",
      detail: "only subset of 10 capabilities bound; unbound cards show CTA",
    });
  }
  // Honest empty without CTA
  if (/暂无|当前工作区暂无/.test(text) && !/打开|前往|安装|创建|查看|刷新|去/.test(text)) {
    issues.push({ severity: "product_gap", code: "empty_without_cta", detail: "empty state without actionable CTA" });
  }

  const api4 = failedApi.filter((f) => f.status >= 400 && f.status < 500);
  if (api4.length) issues.push({ severity: "warn", code: "api_4xx", detail: api4.slice(0, 5) });

  let verdict = "product_ok";
  if (issues.some((i) => i.severity === "crash")) verdict = "crash";
  else if (issues.some((i) => i.severity === "product_gap")) verdict = "product_gap";
  else if (issues.some((i) => i.severity === "warn")) verdict = "warn";
  return { verdict, issues, cardCount };
}

const browser = HEADLESS
  ? await chromium.launch({
      headless: true,
      // Prefer system Chrome so we don't require Playwright browser downloads.
      channel: process.env.AIP_AUDIT_CHANNEL || "chrome",
    })
  : await chromium.connectOverCDP(CDP);
const storageStatePath =
  process.env.AIP_AUDIT_STORAGE_STATE ||
  "/Users/ddt/work/projects/ai_agent/aos-platform-w1-aip/.evidence/aip/auth-storage-state.json";
const context = HEADLESS
  ? await browser.newContext({
      viewport: { width: 1440, height: 900 },
      ...(await import("node:fs").then((fs) =>
        fs.existsSync(storageStatePath) ? { storageState: storageStatePath } : {},
      )),
    })
  : browser.contexts()[0] || (await browser.newContext());
let page = HEADLESS
  ? await context.newPage()
  : context.pages().find((p) => (p.url() || "").includes("127.0.0.1:5174")) ||
    context.pages()[0] ||
    (await context.newPage());

if (!HEADLESS) await page.bringToFront().catch(() => {});
if (HEADLESS) {
  await page.goto(`${BASE}/aip/assist`, { waitUntil: "domcontentloaded", timeout: 30000 }).catch(() => {});
}

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
  const name = item.path.replace(/\//g, "_").replace(/^_/, "") || "root";
  const shotTop = path.join(OUT, "screenshots", `${name}__top.png`);
  await page.screenshot({ path: shotTop, fullPage: false }).catch((e) => pageErrors.push(`shot_top: ${e.message}`));

  const scrollMeta = await scrollToBottomStepped(page);
  const shotBottom = path.join(OUT, "screenshots", `${name}__bottom.png`);
  await page.screenshot({ path: shotBottom, fullPage: false }).catch((e) => pageErrors.push(`shot_bottom: ${e.message}`));

  // also full-page for review
  const shotFull = path.join(OUT, "screenshots", `${name}__full.png`);
  await page.screenshot({ path: shotFull, fullPage: true }).catch(() => {});

  const bodyText = await page.evaluate(() => {
    const pane = document.querySelector(".content") || document.querySelector("main, [role='main']") || document.body;
    return pane.innerText || "";
  }).catch(() => "");
  const title = await page.title().catch(() => "");
  const counts = await page.evaluate(() => {
    const main = document.querySelector(".content") || document.querySelector("main, [role='main']") || document.body;
    const text = (main.innerText || "").toLowerCase();
    const blocked = (main.innerText.match(/\bblocked\b/gi) || []).length;
    const buttons = [...main.querySelectorAll("button, [role='button'], a.button")];
    const disabledPrimary = buttons.filter((b) => {
      const t = (b.innerText || "").trim();
      const dis = b.disabled || b.getAttribute("aria-disabled") === "true" || b.classList.contains("disabled");
      return dis && /预检|激活|发送|新建|保存|安装|运行|批准|提交|试跑/.test(t);
    }).length;
    const cards = main.querySelectorAll("[class*='card'], article, section").length;
    return { blocked, disabledPrimary, cards, textLen: text.length };
  });

  page.off("pageerror", onError);
  page.off("response", onResponse);

  let { verdict, issues } = classifyProduct({
    bodyText,
    pageErrors,
    failedApi,
    path: item.path,
    disabledPrimaryCount: counts.disabledPrimary,
    blockedCount: counts.blocked,
    cardCount: counts.cards,
  });
  if (!navOk) {
    verdict = "crash";
    issues = [...issues, { severity: "crash", code: "nav_fail", detail: "navigation failed" }];
  }
  if (/AOS Web \(scaffold\)/.test(title)) {
    issues = [...issues, { severity: "warn", code: "scaffold_title", detail: title }];
    if (verdict === "product_ok") verdict = "warn";
  }

  const row = {
    path: item.path,
    label: item.label,
    mock: item.mock,
    verdict,
    clickMode,
    finalUrl: page.url(),
    title,
    scroll: {
      root: scrollMeta.id,
      scrollHeight: scrollMeta.scrollHeight,
      clientHeight: scrollMeta.clientHeight,
      maxY: scrollMeta.maxY,
      stepCount: scrollMeta.steps?.length || 0,
      reachedBottom: scrollMeta.reachedBottom,
    },
    counts,
    issueCount: issues.length,
    issues,
    screenshots: { top: shotTop, bottom: shotBottom, full: shotFull },
    bodyPreview: bodyText.replace(/\s+/g, " ").slice(0, 280),
  };
  results.push(row);
  console.log(
    JSON.stringify({
      progress: `${results.length}/${PAGES.length}`,
      path: row.path,
      verdict: row.verdict,
      codes: issues.map((i) => i.code),
      scrollMaxY: row.scroll.maxY,
      blocked: counts.blocked,
    }),
  );
}

const summary = {
  auditedAt: new Date().toISOString(),
  base: BASE,
  cdp: HEADLESS ? "headless" : CDP,
  headless: HEADLESS,
  policy: "scroll_to_bottom + product_gap listing; blocked≠ok; user decides fixes",
  count: results.length,
  product_ok: results.filter((r) => r.verdict === "product_ok").length,
  warn: results.filter((r) => r.verdict === "warn").length,
  product_gap: results.filter((r) => r.verdict === "product_gap").length,
  crash: results.filter((r) => r.verdict === "crash").length,
  pages: results,
  gaps: results
    .filter((r) => r.verdict === "product_gap" || r.verdict === "crash")
    .map((r) => ({
      path: r.path,
      label: r.label,
      verdict: r.verdict,
      codes: r.issues.map((i) => i.code),
      detail: r.issues.filter((i) => i.severity !== "warn").map((i) => i.detail),
    })),
};
fs.writeFileSync(path.join(OUT, "audit-summary.json"), JSON.stringify(summary, null, 2));
console.log(JSON.stringify({ done: true, ...summary, pages: undefined }, null, 2));
await browser.close().catch(() => {});
