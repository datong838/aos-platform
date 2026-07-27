/**
 * Theme — 主题切换 API（Phase 6 品牌色统一推广）
 *
 * 本模块是对 lib/appearance.ts 的轻量封装，提供任务规范要求的
 * getTheme / setTheme / toggleTheme / initTheme 四个函数。
 *
 * 底层仍使用 data-aos-theme 属性驱动 tokens.css 的 CSS 变量体系，
 * 同时同步设置 data-theme 属性以兼容 [data-theme="dark"] 选择器。
 */

import {
  APPEARANCE_STORAGE_KEY,
  applyThemeToDocument,
  persistAppearance,
  readAppearancePreference,
  resolveTheme,
  type AppearancePreference,
  type ResolvedTheme,
} from "./lib/appearance";

export type Theme = ResolvedTheme; // "light" | "dark"

/** localStorage 键名（与 appearance 模块共享，保证偏好同步） */
export const THEME_STORAGE_KEY = APPEARANCE_STORAGE_KEY;

/**
 * 读取当前已解析的主题（从 data-aos-theme 属性）。
 * 若属性未设置，回退到 appearance 偏好的解析结果。
 */
export function getTheme(): Theme {
  if (typeof document !== "undefined") {
    const attr = document.documentElement.getAttribute("data-aos-theme");
    if (attr === "light" || attr === "dark") return attr;
  }
  const pref = readAppearancePreference();
  const systemDark =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;
  return resolveTheme(pref, systemDark);
}

/**
 * 设置主题并持久化到 localStorage。
 * 同时更新 data-aos-theme 和 data-theme 两个属性，
 * 保证 tokens.css 中 html[data-aos-theme="dark"] 和 [data-theme="dark"]
 * 两套选择器都能正确触发。
 */
export function setTheme(theme: Theme): void {
  const pref: AppearancePreference = theme;
  persistAppearance(pref);
  applyThemeToDocument(theme);
  document.documentElement.setAttribute("data-theme", theme);
  document.documentElement.setAttribute("data-aos-appearance", theme);
}

/**
 * 在 light / dark 之间切换，返回切换后的主题。
 */
export function toggleTheme(): Theme {
  const next: Theme = getTheme() === "dark" ? "light" : "dark";
  setTheme(next);
  return next;
}

/**
 * 初始化主题：读取 localStorage 偏好并应用到文档。
 * 应在应用启动时调用一次（AppShell 已通过 appearance 模块完成此工作，
 * 此函数作为独立入口点供无 AppShell 的场景使用）。
 */
export function initTheme(): void {
  const pref = readAppearancePreference();
  const systemDark =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;
  const resolved = resolveTheme(pref, systemDark);
  applyThemeToDocument(resolved);
  document.documentElement.setAttribute("data-theme", resolved);
  document.documentElement.setAttribute("data-aos-appearance", pref);
}
