import { describe, expect, it } from "vitest";
import { MOCK_CONFIG_OVERRIDES, MOCK_MAINTENANCE_WINDOW } from "./ConfigSecretsPage";

describe("ConfigSecretsPage · MOCK_CONFIG_OVERRIDES 数据", () => {
  it("有至少 3 个配置项", () => {
    expect(MOCK_CONFIG_OVERRIDES.length).toBeGreaterThanOrEqual(3);
  });

  it("每个配置项有 key 和 value", () => {
    for (const c of MOCK_CONFIG_OVERRIDES) {
      expect(c.key.length).toBeGreaterThan(0);
      expect(c.value.length).toBeGreaterThan(0);
      expect(["global", "env", "spoke"]).toContain(c.source);
    }
  });

  it("包含至少一个敏感项", () => {
    const sensitive = MOCK_CONFIG_OVERRIDES.filter((c) => c.sensitive);
    expect(sensitive.length).toBeGreaterThan(0);
  });

  it("包含 global/env/spoke 三种来源", () => {
    const sources = new Set(MOCK_CONFIG_OVERRIDES.map((c) => c.source));
    expect(sources.has("global")).toBe(true);
    expect(sources.has("env")).toBe(true);
    expect(sources.has("spoke")).toBe(true);
  });
});

describe("ConfigSecretsPage · MOCK_MAINTENANCE_WINDOW 数据", () => {
  it("有开始和结束时间", () => {
    expect(MOCK_MAINTENANCE_WINDOW.start.length).toBeGreaterThan(0);
    expect(MOCK_MAINTENANCE_WINDOW.end.length).toBeGreaterThan(0);
  });

  it("有备注信息", () => {
    expect(MOCK_MAINTENANCE_WINDOW.notes.length).toBeGreaterThan(0);
  });

  it("active 为布尔值", () => {
    expect(typeof MOCK_MAINTENANCE_WINDOW.active).toBe("boolean");
  });
});
