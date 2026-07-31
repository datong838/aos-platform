import { describe, expect, it } from "vitest";
import {
  MOCK_SPOKE_DETAIL,
  TABS,
  healthLabel,
  planStatusBadge,
} from "./SpokeDetailPage";

describe("SpokeDetailPage · MOCK_SPOKE_DETAIL 数据", () => {
  it("spoke 有完整基本信息", () => {
    const s = MOCK_SPOKE_DETAIL.spoke;
    expect(s.id.length).toBeGreaterThan(0);
    expect(s.name.length).toBeGreaterThan(0);
    expect(s.region.length).toBeGreaterThan(0);
    expect(["full", "lite"]).toContain(s.spokeType);
    expect(["online", "degraded", "offline"]).toContain(s.health);
  });

  it("plans 有至少 2 条", () => {
    expect(MOCK_SPOKE_DETAIL.plans.length).toBeGreaterThanOrEqual(2);
  });

  it("planDiff 有变更条目", () => {
    expect(MOCK_SPOKE_DETAIL.planDiff.length).toBeGreaterThan(0);
    for (const d of MOCK_SPOKE_DETAIL.planDiff) {
      expect(["added", "changed", "removed"]).toContain(d.diffType);
    }
  });

  it("config 有配置覆盖项", () => {
    expect(MOCK_SPOKE_DETAIL.config.length).toBeGreaterThan(0);
  });

  it("maintenanceWindow 存在且有时间段", () => {
    const mw = MOCK_SPOKE_DETAIL.maintenanceWindow;
    expect(mw).not.toBeNull();
    expect(mw!.start.length).toBeGreaterThan(0);
    expect(mw!.end.length).toBeGreaterThan(0);
  });
});

describe("SpokeDetailPage · TABS", () => {
  it("有 5 个标签页", () => {
    expect(TABS).toHaveLength(5);
  });

  it("包含 overview/plan/config 等", () => {
    const ids = TABS.map((t) => t.id);
    expect(ids).toContain("overview");
    expect(ids).toContain("plan");
    expect(ids).toContain("config");
  });
});

describe("SpokeDetailPage · healthLabel", () => {
  it("online → 健康", () => {
    expect(healthLabel("online")).toBe("健康");
  });

  it("offline → 离线", () => {
    expect(healthLabel("offline")).toBe("离线");
  });
});

describe("SpokeDetailPage · planStatusBadge", () => {
  it("applied → 已应用", () => {
    expect(planStatusBadge("applied").label).toBe("已应用");
  });

  it("pending → 待应用", () => {
    expect(planStatusBadge("pending").label).toBe("待应用");
  });

  it("failed → 失败", () => {
    expect(planStatusBadge("failed").label).toBe("失败");
  });
});
