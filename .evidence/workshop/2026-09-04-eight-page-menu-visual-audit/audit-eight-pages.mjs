// 八页菜单组件 / 视觉 / 数据只读审计（清单 §3 统一验收定义）。
// 只读：仅导航、展开、滚动与截图；不点击写入按钮、不提交表单、不调用 Provider。
import { acquirePage } from "../2026-09-04-r3-cockpit-layout-and-task-loop/cdp-page.mjs";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const outDir = dirname(fileURLToPath(import.meta.url));
mkdirSync(outDir, { recursive: true });

const PAGES = [
  { key: "01-cockpit", route: "/workshop/cockpit", label: "日常任务总控大屏", visual: "workshop-task-cockpit.html" },
  { key: "02-content-campaign", route: "/workshop/content-campaign", label: "内容与活动工作台", visual: "workshop-content-campaign.html" },
  { key: "03-operations", route: "/workshop/operations", label: "统一运营驾驶舱", visual: "workshop-app-order.html" },
  { key: "04-creator-growth", route: "/workshop/creator-growth", label: "达人邀约驾驶舱", visual: "workshop-creator-outreach.html" },
  { key: "05-media-studio", route: "/workshop/media-studio", label: "多媒体内容生产", visual: "workshop-media-studio.html" },
  { key: "06-analyst", route: "/workshop/analyst", label: "经营参谋 · 增长指挥中心", visual: "workshop-analyst.html" },
  { key: "07-price-governance", route: "/workshop/price-governance", label: "价格治理驾驶舱", visual: "workshop-price-governance.html" },
  { key: "08-customer", route: "/workshop/customer", label: "客户关系工作台", visual: "workshop-customer.html" },
];
const VIEWPORTS = [
  { name: "1280x720", width: 1280, height: 720 },
  { name: "1440x900", width: 1440, height: 900 },
  { name: "1920x1080", width: 1920, height: 1080 },
];

const { browser, page } = await acquirePage();

// 菜单与结构审计（只读 DOM 度量）
const auditDom = () => page.evaluate(() => {
  const clean = (value) => (value ?? "").replace(/\s+/g, " ").trim();
  const sidebar = document.querySelector("nav, aside[class*='nav'], [class*='sidebar']");
  const allLinks = [...document.querySelectorAll("a[href]")];
  const navLinks = sidebar ? [...sidebar.querySelectorAll("a[href]")] : [];
  const scrollContainers = [...document.querySelectorAll("*")]
    .filter((node) => {
      const style = getComputedStyle(node);
      return (style.overflowY === "auto" || style.overflowY === "scroll") && node.scrollHeight > node.clientHeight + 1;
    })
    .map((node) => ({ tag: node.tagName.toLowerCase(), cls: clean(node.className).slice(0, 60), scrollHeight: node.scrollHeight, clientHeight: node.clientHeight }));

  const navScroller = sidebar
    ? (() => {
        let node = sidebar;
        while (node && node !== document.body) {
          const style = getComputedStyle(node);
          if (style.overflowY === "auto" || style.overflowY === "scroll") {
            return { cls: clean(node.className).slice(0, 60), scrollHeight: node.scrollHeight, clientHeight: node.clientHeight, scrollable: node.scrollHeight > node.clientHeight + 1 };
          }
          node = node.parentElement;
        }
        return null;
      })()
    : null;

  return {
    title: clean(document.title),
    h1: [...document.querySelectorAll("h1")].map((node) => clean(node.textContent)),
    h2Count: document.querySelectorAll("h2").length,
    h3Count: document.querySelectorAll("h3").length,
    navLinkCount: navLinks.length,
    navLinkSample: navLinks.slice(0, 6).map((node) => clean(node.textContent)),
    documentLinkCount: allLinks.length,
    navScroller,
    buttonCount: document.querySelectorAll("button").length,
    disabledButtonCount: document.querySelectorAll("button[disabled]").length,
    tabCount: document.querySelectorAll("[role='tab']").length,
    tableCount: document.querySelectorAll("table").length,
    listItemCount: document.querySelectorAll("li").length,
    alertCount: document.querySelectorAll("[role='alert']").length,
    statusCount: document.querySelectorAll("[role='status']").length,
    horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
    verticalPageScroll: document.documentElement.scrollHeight > window.innerHeight + 1,
    scrollContainerCount: scrollContainers.length,
    scrollContainers: scrollContainers.slice(0, 6),
    emptyStateHits: ["暂无", "没有", "空", "待核对", "尚无", "未就绪", "读取失败"].filter((token) => document.body.textContent.includes(token)),
    safetyPrecheckHits: ["安全预检", "不会创建", "预检已打开"].filter((token) => document.body.textContent.includes(token)),
  };
});

const results = [];
for (const spec of PAGES) {
  const entry = { ...spec, viewports: {} };
  for (const viewport of VIEWPORTS) {
    try {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto(`http://127.0.0.1:5173${spec.route}`, { waitUntil: "networkidle", timeout: 45000 });
      await page.waitForTimeout(2500);
      const dom = await auditDom();
      await page.screenshot({ path: `${outDir}/${spec.key}-${viewport.name}.png` });
      entry.viewports[viewport.name] = dom;
    } catch (error) {
      entry.viewports[viewport.name] = { error: String(error).slice(0, 200) };
    }
  }
  results.push(entry);
  const first = entry.viewports["1280x720"] ?? {};
  console.log(`${spec.key.padEnd(20)} navLinks=${String(first.navLinkCount).padEnd(4)} docLinks=${String(first.documentLinkCount).padEnd(4)} buttons=${String(first.buttonCount).padEnd(4)} tabs=${String(first.tabCount).padEnd(3)} hOverflow=${first.horizontalOverflow} navScrollable=${first.navScroller?.scrollable}`);
}

writeFileSync(`${outDir}/eight-page-audit.json`, JSON.stringify({ auditedAt: new Date().toISOString(), viewports: VIEWPORTS.map((v) => v.name), pages: results }, null, 2));
console.log("\nsaved eight-page-audit.json");
await browser.close();
