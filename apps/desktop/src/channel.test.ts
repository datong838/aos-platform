import { beforeEach, describe, expect, it } from "vitest";
import {
  CHANNEL_STORAGE_KEY,
  getChannelConfig,
  parseChannelSku,
  setChannelSku,
  shouldSkipWelcomeForce,
} from "./channel";

describe("TWC.12 channel SKU", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("parses three SKUs", () => {
    expect(parseChannelSku("private")).toBe("private");
    expect(parseChannelSku("saas")).toBe("saas");
    expect(parseChannelSku("local")).toBe("local");
    expect(parseChannelSku("nope")).toBe("local");
  });

  it("private has empty base and cannot skip welcome", () => {
    setChannelSku("private");
    const c = getChannelConfig();
    expect(c.defaultApiBase).toBe("");
    expect(shouldSkipWelcomeForce(c)).toBe(false);
  });

  it("saas / local preset base and skip welcome", () => {
    expect(shouldSkipWelcomeForce(getChannelConfig("saas"))).toBe(true);
    expect(getChannelConfig("saas").defaultApiBase).toMatch(/^https:/);
    expect(shouldSkipWelcomeForce(getChannelConfig("local"))).toBe(true);
    expect(getChannelConfig("local").defaultApiBase).toContain("127.0.0.1");
  });

  it("persists sku", () => {
    setChannelSku("saas");
    expect(localStorage.getItem(CHANNEL_STORAGE_KEY)).toBe("saas");
    expect(getChannelConfig().channel).toBe("saas");
  });
});
