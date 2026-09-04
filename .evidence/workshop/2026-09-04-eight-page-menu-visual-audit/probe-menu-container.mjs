// 只读复验清单 §1 第 1～2 条菜单缺陷：侧栏主导航 `nav.nav` 的链接数、分组、滚动与滚到底行为。
// 2026-08-30 审计结论为"八页各自硬编码缩减菜单、每页仅 13 个链接；Buddy 完整 canonical 菜单 80 个链接"。
// 只读：仅导航与容器内滚动，滚动后复位；不点击写入按钮、不改主题/租户/折叠等持久化状态。
import { acquirePage } from "../2026-09-04-r3-cockpit-layout-and-task-loop/cdp-page.mjs";
import { writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const outDir = dirname(fileURLToPath(import.meta.url));
const { browser, page } = await acquirePage();
await page.setViewportSize({ width: 1280, height: 720 });

const ROUTES = [
  "/workshop/cockpit", "/workshop/content-campaign", "/workshop/operations", "/workshop/creator-growth",
  "/workshop/media-studio", "/workshop/analyst", "/workshop/price-governance", "/workshop/customer",
];

const report = [];
for (const route of ROUTES) {
  await page.goto(`http://127.0.0.1:5173${route}`, { waitUntil: "networkidle", timeout: 45000 });
  await page.waitForTimeout(2000);

  const info = await page.evaluate(() => {
    const clean = (value) => (value ?? "").replace(/\s+/g, " ").trim();
    const sidebarNav = document.querySelector("nav.nav") ?? document.querySelector('nav[aria-label="主导航"]');
    const globalNav = document.querySelector("nav.p-nav-global");
    const aside = document.querySelector("aside.aside");
    if (!sidebarNav) return { error: "未找到 nav.nav 主导航" };

    const navLinks = [...sidebarNav.querySelectorAll("a[href]")];
    const rect = sidebarNav.getBoundingClientRect();

    // 侧栏主导航的滚动祖先
    let scroller = sidebarNav; let scrollerInfo = null;
    while (scroller && scroller !== document.body) {
      const style = getComputedStyle(scroller);
      if (style.overflowY === "auto" || style.overflowY === "scroll") {
        scrollerInfo = { cls: clean(scroller.className).slice(0, 60), scrollHeight: scroller.scrollHeight, clientHeight: scroller.clientHeight, scrollable: scroller.scrollHeight > scroller.clientHeight + 1 };
        break;
      }
      scroller = scroller.parentElement;
    }

    return {
      sidebarNavLinkCount: navLinks.length,
      globalNavLinkCount: globalNav ? globalNav.querySelectorAll("a[href]").length : null,
      mainContentLinkCount: document.querySelectorAll("a[href]").length - navLinks.length - (globalNav?.querySelectorAll("a[href]").length ?? 0),
      asideCollapsed: aside ? aside.className.includes("is-collapsed") : null,
      groupHeadings: [...sidebarNav.querySelectorAll("strong, h2, h3, [class*='group'], [class*='section']")].map((node) => clean(node.textContent)).filter(Boolean).slice(0, 20),
      rect: { top: Math.round(rect.top), bottom: Math.round(rect.bottom), left: Math.round(rect.left), width: Math.round(rect.width), height: Math.round(rect.height) },
      navOverflowY: getComputedStyle(sidebarNav).overflowY,
      scroller: scrollerInfo,
      activeLink: (() => { const active = navLinks.find((node) => node.getAttribute("aria-current") || node.className.includes("active")); return active ? `${clean(active.textContent)} → ${active.getAttribute("href")}` : null; })(),
      firstLinks: navLinks.slice(0, 4).map((node) => `${clean(node.textContent)} → ${node.getAttribute("href")}`),
      lastLinks: navLinks.slice(-4).map((node) => `${clean(node.textContent)} → ${node.getAttribute("href")}`),
    };
  });

  // 只读滚到底验证：滚动侧栏滚动容器并复位
  let toBottom = null;
  if (info.scroller?.scrollable) {
    toBottom = await page.evaluate(() => {
      const nav = document.querySelector("nav.nav");
      let node = nav;
      while (node && node !== document.body) {
        const style = getComputedStyle(node);
        if ((style.overflowY === "auto" || style.overflowY === "scroll") && node.scrollHeight > node.clientHeight + 1) break;
        node = node.parentElement;
      }
      if (!node || node === document.body) return null;
      const before = node.scrollTop;
      node.scrollTop = node.scrollHeight;
      const reached = node.scrollTop + node.clientHeight >= node.scrollHeight - 2;
      const lastLinkVisible = (() => {
        const links = [...node.querySelectorAll("a[href]")];
        const last = links.at(-1);
        if (!last) return null;
        const linkRect = last.getBoundingClientRect(); const boxRect = node.getBoundingClientRect();
        return linkRect.bottom <= boxRect.bottom + 2 && linkRect.top >= boxRect.top - 2;
      })();
      node.scrollTop = before;
      return { reachedBottom: reached, lastLinkVisibleAtBottom: lastLinkVisible };
    });
  }

  report.push({ route, ...info, toBottom });
  console.log(`${route.padEnd(30)} sidebarNav=${String(info.sidebarNavLinkCount).padEnd(4)} globalNav=${String(info.globalNavLinkCount).padEnd(4)} pageLinks=${String(info.mainContentLinkCount).padEnd(4)} scrollable=${info.scroller?.scrollable} toBottom=${toBottom?.reachedBottom}`);
}

writeFileSync(`${outDir}/menu-container-audit.json`, JSON.stringify({ auditedAt: new Date().toISOString(), viewport: "1280x720", baseline2026_08_30: { perPageReducedLinks: 13, buddyCanonicalLinks: 80 }, pages: report }, null, 2));
console.log("\nsaved menu-container-audit.json");
await browser.close();
