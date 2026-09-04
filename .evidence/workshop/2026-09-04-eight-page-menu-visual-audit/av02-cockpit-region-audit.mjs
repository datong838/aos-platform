// AV02 日常任务总控大屏 逐区域成对对账（回归）。
// 判据来源：清单 R3-01 精确施工范围（1280×720 目标几何 73/53/120-中央-120-复盘/50/34）与 R3-01～R3-07 八项。
// 兼还 R3-01 §5 记录的「响应式多尺寸复验保留到 R9」欠账：本次用 CDP 设三档视口实测。
// 只读：仅导航、悬停、容器内滚动（复位）与截图；不点击下达/分派等写入动作。
import { acquirePage } from "../2026-09-04-r3-cockpit-layout-and-task-loop/cdp-page.mjs";
import { writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const outDir = dirname(fileURLToPath(import.meta.url));
const { browser, page } = await acquirePage();

const VIEWPORTS = [
  { name: "1280x720", width: 1280, height: 720 },
  { name: "1440x900", width: 1440, height: 900 },
  { name: "1920x1080", width: 1920, height: 1080 },
];

const measure = () => page.evaluate(() => {
  const clean = (value) => (value ?? "").replace(/\s+/g, " ").trim();
  const box = (node) => { if (!node) return null; const r = node.getBoundingClientRect(); return { top: Math.round(r.top), bottom: Math.round(r.bottom), left: Math.round(r.left), right: Math.round(r.right), width: Math.round(r.width), height: Math.round(r.height) }; };
  const byLabel = (label) => document.querySelector(`[aria-label="${label}"]`);
  const findByText = (selector, text) => [...document.querySelectorAll(selector)].find((node) => clean(node.textContent).includes(text)) ?? null;

  // 六段区域：KPI 带 / 下达带 / 执行组 / 中央任务流 / 策划组 / 右侧复盘 / 共享能力带 / 明日预告
  const regions = {};
  const candidates = {
    kpi: ['[class*="cockpit-kpi"]', '[aria-label*="KPI"]', '[class*="kpi"]'],
    dispatch: ['[class*="dispatch"]', '[class*="cockpit-command"]', '[aria-label*="下达"]'],
    execGroup: ['[class*="exec"]', '[aria-label*="执行组"]'],
    taskStream: ['[class*="task-stream"]', '[class*="cockpit-center"]', '[aria-label*="任务流"]'],
    planGroup: ['[class*="plan-group"]', '[aria-label*="策划组"]'],
    review: ['[class*="review"]', '[aria-label*="复盘"]'],
    skills: ['[class*="capability"]', '[class*="skill"]', '[aria-label*="共享"]', '[aria-label*="能力"]'],
    tomorrow: ['[class*="tomorrow"]', '[aria-label*="明日"]'],
  };
  for (const [key, selectors] of Object.entries(candidates)) {
    let node = null;
    for (const selector of selectors) { node = document.querySelector(selector); if (node) break; }
    regions[key] = node ? { selector: clean(node.className).slice(0, 50) || node.getAttribute("aria-label"), ...box(node) } : null;
  }

  // 遮挡检测：共享能力带与明日预告是否被覆盖（R3-07 修复项）
  const overlapOf = (a, b) => (!a || !b) ? null : !(a.bottom <= b.top || b.bottom <= a.top || a.right <= b.left || b.right <= a.left);

  // R3 八项的可见语义锚点
  const anchors = {
    "R3-02 推荐任务": !!findByText("*", "推荐"),
    "R3-03 任务指令输入": !!document.querySelector('input[type="text"], textarea'),
    "R3-04 数字同事卡片": document.querySelectorAll('[class*="colleague"], [class*="teammate"]').length,
    "R3-05 共享能力标签": document.querySelectorAll('[class*="capability"] [class*="chip"], [class*="capability"] li, [class*="skill"] li').length,
    "R3-06 今日复盘": !!findByText("*", "今日复盘"),
    "R3-06 AI 改进建议": !!findByText("*", "AI 改进建议"),
    "R3-06 经验沉淀 Wiki": !!findByText("*", "经验沉淀"),
    "R3-07 明日预告": !!findByText("*", "明日"),
  };

  // 任务列表滚动（R3-07）
  const taskScroller = [...document.querySelectorAll("*")].find((node) => {
    const style = getComputedStyle(node);
    return (style.overflowY === "auto" || style.overflowY === "scroll") && node.scrollHeight > node.clientHeight + 1 && node.querySelectorAll("li, [class*='task']").length > 3;
  });

  return {
    viewportInner: { width: window.innerWidth, height: window.innerHeight },
    regions,
    overlaps: {
      "共享能力带×明日预告": overlapOf(regions.skills, regions.tomorrow),
      "中央任务流×共享能力带": overlapOf(regions.taskStream, regions.skills),
      "右侧复盘×共享能力带": overlapOf(regions.review, regions.skills),
    },
    anchors,
    taskScroller: taskScroller ? { cls: clean(taskScroller.className).slice(0, 50), scrollHeight: taskScroller.scrollHeight, clientHeight: taskScroller.clientHeight } : null,
    horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
    bodyBottomCut: document.documentElement.scrollHeight - window.innerHeight,
  };
});

const result = { auditedAt: new Date().toISOString(), page: "日常任务总控大屏", route: "/workshop/cockpit", targetGeometry1280: { kpi: 73, dispatch: 53, sideColumn: 120, skills: 50, tomorrow: 34 }, viewports: {} };

for (const viewport of VIEWPORTS) {
  await page.setViewportSize({ width: viewport.width, height: viewport.height });
  await page.goto("http://127.0.0.1:5173/workshop/cockpit", { waitUntil: "networkidle", timeout: 45000 });
  await page.waitForTimeout(2500);
  const data = await measure();
  await page.screenshot({ path: `${outDir}/av02-cockpit-${viewport.name}-full.png`, fullPage: true });
  result.viewports[viewport.name] = data;
  const r = data.regions;
  console.log(`\n[${viewport.name}] hOverflow=${data.horizontalOverflow} 页面可滚高度差=${data.bodyBottomCut}`);
  for (const [key, value] of Object.entries(r)) console.log(`  ${key.padEnd(12)} ${value ? `h=${String(value.height).padEnd(5)} w=${String(value.width).padEnd(5)} top=${value.top}` : "未定位"}`);
  console.log(`  遮挡: ${JSON.stringify(data.overlaps)}`);
  console.log(`  锚点: ${JSON.stringify(data.anchors, null, 0)}`);
}

writeFileSync(`${outDir}/av02-cockpit-region-audit.json`, JSON.stringify(result, null, 2));
console.log("\nsaved av02-cockpit-region-audit.json");
await browser.close();
