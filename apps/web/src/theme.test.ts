import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  getTheme,
  setTheme,
  toggleTheme,
  initTheme,
  THEME_STORAGE_KEY,
} from "./theme";
import { APPEARANCE_STORAGE_KEY } from "./lib/appearance";

// jsdom 未实现 matchMedia，手动 mock
function mockMatchMedia(matches: boolean) {
  const mq = { matches, addEventListener: vi.fn(), removeEventListener: vi.fn() };
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    configurable: true,
    value: vi.fn(() => mq),
  });
}

describe("theme.ts — 主题切换 API", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-aos-theme");
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.removeAttribute("data-aos-appearance");
    mockMatchMedia(false);
  });

  describe("getTheme", () => {
    it("返回 data-aos-theme 属性的值", () => {
      document.documentElement.setAttribute("data-aos-theme", "dark");
      expect(getTheme()).toBe("dark");
    });

    it("无属性时回退到 dark（localStorage 默认）", () => {
      expect(getTheme()).toBe("dark");
    });

    it("localStorage 设为 dark 时回退到 dark", () => {
      localStorage.setItem(APPEARANCE_STORAGE_KEY, "dark");
      expect(getTheme()).toBe("dark");
    });
  });

  describe("setTheme", () => {
    it("设置 data-aos-theme 属性", () => {
      setTheme("dark");
      expect(document.documentElement.getAttribute("data-aos-theme")).toBe(
        "dark",
      );
    });

    it("同步设置 data-theme 属性（兼容 [data-theme] 选择器）", () => {
      setTheme("dark");
      expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    });

    it("持久化到 localStorage", () => {
      setTheme("dark");
      expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
      expect(localStorage.getItem(APPEARANCE_STORAGE_KEY)).toBe("dark");
    });

    it("切换到 light 时属性正确", () => {
      setTheme("dark");
      setTheme("light");
      expect(document.documentElement.getAttribute("data-aos-theme")).toBe(
        "light",
      );
      expect(document.documentElement.getAttribute("data-theme")).toBe("light");
      expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    });
  });

  describe("toggleTheme", () => {
    it("从 light 切换到 dark", () => {
      setTheme("light");
      const result = toggleTheme();
      expect(result).toBe("dark");
      expect(getTheme()).toBe("dark");
    });

    it("从 dark 切换到 light", () => {
      setTheme("dark");
      const result = toggleTheme();
      expect(result).toBe("light");
      expect(getTheme()).toBe("light");
    });

    it("连续切换在两态之间来回", () => {
      setTheme("light");
      expect(toggleTheme()).toBe("dark");
      expect(toggleTheme()).toBe("light");
      expect(toggleTheme()).toBe("dark");
    });
  });

  describe("initTheme", () => {
    it("无偏好时默认应用 dark", () => {
      initTheme();
      expect(document.documentElement.getAttribute("data-aos-theme")).toBe(
        "dark",
      );
      expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    });

    it("localStorage 有 dark 偏好时应用 dark", () => {
      localStorage.setItem(APPEARANCE_STORAGE_KEY, "dark");
      initTheme();
      expect(document.documentElement.getAttribute("data-aos-theme")).toBe(
        "dark",
      );
      expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    });

    it("localStorage 有 light 偏好时应用 light", () => {
      localStorage.setItem(APPEARANCE_STORAGE_KEY, "light");
      initTheme();
      expect(document.documentElement.getAttribute("data-aos-theme")).toBe(
        "light",
      );
    });

    it("设置 data-aos-appearance 属性", () => {
      initTheme();
      expect(
        document.documentElement.getAttribute("data-aos-appearance"),
      ).toBe("dark");
    });
  });

  describe("THEME_STORAGE_KEY", () => {
    it("与 appearance 模块共享同一 key", () => {
      expect(THEME_STORAGE_KEY).toBe(APPEARANCE_STORAGE_KEY);
    });
  });

  describe("data-theme 属性兼容性", () => {
    it("setTheme('dark') 后 [data-theme='dark'] 选择器可匹配", () => {
      setTheme("dark");
      expect(document.documentElement.matches('[data-theme="dark"]')).toBe(
        true,
      );
    });

    it("setTheme('light') 后 [data-theme='dark'] 不匹配", () => {
      setTheme("light");
      expect(document.documentElement.matches('[data-theme="dark"]')).toBe(
        false,
      );
    });
  });
});
