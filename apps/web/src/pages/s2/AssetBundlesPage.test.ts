import { describe, expect, it } from "vitest";
import { MOCK_ASSET_BUNDLES, CHANNEL_TABS } from "./AssetBundlesPage";

describe("AssetBundlesPage · MOCK_ASSET_BUNDLES 数据", () => {
  it("有至少 3 个资产包", () => {
    expect(MOCK_ASSET_BUNDLES.length).toBeGreaterThanOrEqual(3);
  });

  it("每个资产包有完整字段", () => {
    for (const b of MOCK_ASSET_BUNDLES) {
      expect(b.id.length).toBeGreaterThan(0);
      expect(b.name.length).toBeGreaterThan(0);
      expect(b.version.length).toBeGreaterThan(0);
      expect(["stable", "beta", "rc"]).toContain(b.channel);
      expect(["published", "draft", "deprecated"]).toContain(b.status);
    }
  });

  it("包含 stable/beta/rc 三种通道", () => {
    const channels = new Set(MOCK_ASSET_BUNDLES.map((b) => b.channel));
    expect(channels.has("stable")).toBe(true);
    expect(channels.has("beta")).toBe(true);
    expect(channels.has("rc")).toBe(true);
  });

  it("每个资产包有组件清单", () => {
    for (const b of MOCK_ASSET_BUNDLES) {
      expect(b.components.length).toBeGreaterThan(0);
    }
  });

  it("每个资产包有 changelog", () => {
    for (const b of MOCK_ASSET_BUNDLES) {
      expect(b.changelog.length).toBeGreaterThan(0);
    }
  });
});

describe("AssetBundlesPage · CHANNEL_TABS", () => {
  it("有 4 个通道标签", () => {
    expect(CHANNEL_TABS).toHaveLength(4);
  });

  it("包含 all/stable/beta/rc", () => {
    const ids = CHANNEL_TABS.map((t) => t.id);
    expect(ids).toContain("all");
    expect(ids).toContain("stable");
    expect(ids).toContain("beta");
    expect(ids).toContain("rc");
  });

  it("每个 tab 有 label", () => {
    for (const t of CHANNEL_TABS) {
      expect(t.label.length).toBeGreaterThan(0);
    }
  });
});
