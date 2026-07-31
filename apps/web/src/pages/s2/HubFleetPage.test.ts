import { describe, expect, it } from "vitest";
import {
  MOCK_HUB,
  MOCK_SPOKES,
  healthLabel,
  healthBadgeClass,
  spokeTypeTag,
} from "./HubFleetPage";

describe("HubFleetPage · MOCK_HUB 数据", () => {
  it("有 hubRegion 字段", () => {
    expect(MOCK_HUB.hubRegion.length).toBeGreaterThan(0);
  });

  it("onlineCount <= totalCount", () => {
    expect(MOCK_HUB.onlineCount).toBeLessThanOrEqual(MOCK_HUB.totalCount);
  });

  it("lastProbe 非空", () => {
    expect(MOCK_HUB.lastProbe.length).toBeGreaterThan(0);
  });
});

describe("HubFleetPage · MOCK_SPOKES 数据", () => {
  it("有 5 个预设 Spoke", () => {
    expect(MOCK_SPOKES.length).toBeGreaterThanOrEqual(4);
  });

  it("每个 Spoke 有完整字段", () => {
    for (const s of MOCK_SPOKES) {
      expect(s.id.length).toBeGreaterThan(0);
      expect(s.name.length).toBeGreaterThan(0);
      expect(["online", "degraded", "offline"]).toContain(s.health);
      expect(["stable", "beta", "rc"]).toContain(s.channel);
    }
  });

  it("包含至少一个 online 和一个 offline Spoke", () => {
    const healths = MOCK_SPOKES.map((s) => s.health);
    expect(healths).toContain("online");
    expect(healths).toContain("offline");
  });
});

describe("HubFleetPage · healthLabel", () => {
  it("online → 健康", () => {
    expect(healthLabel("online")).toBe("健康");
  });

  it("degraded → 降级", () => {
    expect(healthLabel("degraded")).toBe("降级");
  });

  it("offline → 离线", () => {
    expect(healthLabel("offline")).toBe("离线");
  });
});

describe("HubFleetPage · healthBadgeClass", () => {
  it("online → ok 样式", () => {
    expect(healthBadgeClass("online")).toContain("ok");
  });

  it("offline → bad 样式", () => {
    expect(healthBadgeClass("offline")).toContain("bad");
  });
});

describe("HubFleetPage · spokeTypeTag", () => {
  it("full → 包含 Full Spoke", () => {
    expect(spokeTypeTag("full")).toContain("Full Spoke");
  });

  it("lite → 包含 Lite Spoke", () => {
    expect(spokeTypeTag("lite")).toContain("Lite Spoke");
  });
});
