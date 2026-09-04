// 共用的 CDP 取页助手：复用任务专属标签，不启动/重启/关闭浏览器。
import { chromium } from "playwright-core";

export const CDP_ENDPOINT = "http://127.0.0.1:9333";
export const APP_ORIGIN = "http://127.0.0.1:5173";

export async function acquirePage() {
  const browser = await chromium.connectOverCDP(CDP_ENDPOINT);
  const contexts = browser.contexts();
  if (!contexts.length) throw new Error("CDP 无可用 context；请先在浏览器打开一个标签页");
  const context = contexts[0];
  const existing = context.pages().find((page) => page.url().startsWith(`${APP_ORIGIN}/`));
  if (existing) return { browser, page: existing, owned: false };
  const created = await context.newPage();
  return { browser, page: created, owned: true };
}
