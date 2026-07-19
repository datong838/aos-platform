import { beforeEach, describe, expect, it } from "vitest";
import {
  clearApiBaseOverride,
  FALLBACK,
  getApiBase,
  resolveDefaultApiBase,
  setApiBase,
  STORAGE_KEY,
} from "./apiBase";

describe("TWB.1 apiBase", () => {
  beforeEach(() => {
    localStorage.clear();
    clearApiBaseOverride();
  });

  it("defaults to env or fallback", () => {
    expect(resolveDefaultApiBase(undefined)).toBe(FALLBACK);
    expect(resolveDefaultApiBase("https://aos.example.com/")).toBe(
      "https://aos.example.com/",
    );
    expect(getApiBase()).toMatch(/^https?:\/\//);
  });

  it("override persists and strips trailing slash", () => {
    setApiBase("https://private.example.com/api/");
    expect(getApiBase()).toBe("https://private.example.com/api");
    expect(localStorage.getItem(STORAGE_KEY)).toBe(
      "https://private.example.com/api",
    );
  });

  it("clear restores default", () => {
    setApiBase("https://saas.example.com");
    clearApiBaseOverride();
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
    expect(getApiBase()).toBe(resolveDefaultApiBase().replace(/\/$/, ""));
  });
});
