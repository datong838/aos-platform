// R3-07 第 1/8 步只读几何测量：确认底部能力带/明日预告遮挡、任务列表滚动、数字同事列可见性。
// 只读脚本：不创建任务、不提交表单、不触发任何写命令。
import { chromium } from "playwright-core";
import { mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const outDir = dirname(fileURLToPath(import.meta.url));
mkdirSync(outDir, { recursive: true });

const browser = await chromium.connectOverCDP("http://127.0.0.1:9333");
const context = browser.contexts()[0];
const owned = context.pages().find((page) => page.url().startsWith("http://127.0.0.1:5173/"));
const page = owned ?? (await context.newPage());
await page.setViewportSize({ width: 1280, height: 720 });
await page.goto("http://127.0.0.1:5173/workshop/cockpit", { waitUntil: "networkidle", timeout: 45000 });
await page.waitForSelector(".task-cockpit-visual-surface", { timeout: 30000 });
await page.waitForTimeout(2000);

const report = await page.evaluate(() => {
  const box = (selector) => {
    const node = document.querySelector(selector);
    if (!node) return null;
    const rect = node.getBoundingClientRect();
    return {
      selector,
      top: Math.round(rect.top), bottom: Math.round(rect.bottom),
      left: Math.round(rect.left), right: Math.round(rect.right),
      width: Math.round(rect.width), height: Math.round(rect.height),
      scrollHeight: node.scrollHeight, clientHeight: node.clientHeight,
      overflowY: getComputedStyle(node).overflowY,
      verticallyScrollable: node.scrollHeight > node.clientHeight + 1,
      visible: rect.width > 0 && rect.height > 0 && getComputedStyle(node).visibility !== "hidden",
    };
  };
  const overlaps = (a, b) => (a && b ? !(a.bottom <= b.top || b.bottom <= a.top || a.right <= b.left || b.right <= a.left) : null);

  const surface = box(".task-cockpit-visual-surface");
  const skills = box(".task-cockpit-visual-skills");
  const tomorrow = box(".task-cockpit-visual-tomorrow");
  const roleColumn = box(".task-cockpit-visual-role-column");
  const taskColumn = box(".task-cockpit-visual-task-column");
  const review = box(".task-cockpit-visual-review");
  const colleagueCards = [...document.querySelectorAll(".task-cockpit-colleague-card")];
  const lastCard = colleagueCards.at(-1);
  const lastCardRect = lastCard?.getBoundingClientRect() ?? null;

  return {
    viewport: { width: window.innerWidth, height: window.innerHeight },
    surface, skills, tomorrow, roleColumn, taskColumn, review,
    colleagueCardCount: colleagueCards.length,
    lastColleagueCardBottom: lastCardRect ? Math.round(lastCardRect.bottom) : null,
    lastColleagueCardFullyVisible: lastCardRect && skills ? Math.round(lastCardRect.bottom) <= skills.top : null,
    overlaps: {
      skills_x_taskColumn: overlaps(skills, taskColumn),
      skills_x_roleColumn: overlaps(skills, roleColumn),
      skills_x_review: overlaps(skills, review),
      tomorrow_x_skills: overlaps(tomorrow, skills),
      tomorrow_x_taskColumn: overlaps(tomorrow, taskColumn),
    },
    taskCardCount: document.querySelectorAll(".task-cockpit-visual-task-column > article").length,
    documentScrollable: document.documentElement.scrollHeight > window.innerHeight + 1,
    documentScrollHeight: document.documentElement.scrollHeight,
  };
});

await page.screenshot({ path: `${outDir}/01-viewport-1280x720.png` });
await page.screenshot({ path: `${outDir}/02-fullpage-1280x720.png`, fullPage: true });

console.log(JSON.stringify(report, null, 2));
if (!owned) await page.close();
await browser.close();
