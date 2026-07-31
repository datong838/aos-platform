import { describe, expect, it } from "vitest";
import { MOCK_RELEASES, stageBadge } from "./ReleasesPage";

describe("ReleasesPage · MOCK_RELEASES stages", () => {
  it("有 3 个发布通道（rc/beta/stable）", () => {
    expect(MOCK_RELEASES.stages).toHaveLength(3);
  });

  it("每个 stage 有 version 和 channel", () => {
    for (const s of MOCK_RELEASES.stages) {
      expect(s.version.length).toBeGreaterThan(0);
      expect(["rc", "beta", "stable"]).toContain(s.channel);
    }
  });

  it("beta 标记为当前通道", () => {
    const beta = MOCK_RELEASES.stages.find((s) => s.channel === "beta");
    expect(beta?.isCurrent).toBe(true);
  });

  it("stable 推送百分比 100", () => {
    const stable = MOCK_RELEASES.stages.find((s) => s.channel === "stable");
    expect(stable?.pushPercent).toBe(100);
  });
});

describe("ReleasesPage · Hotfix 数据", () => {
  it("有至少一条 hotfix", () => {
    expect(MOCK_RELEASES.hotfix.length).toBeGreaterThan(0);
  });

  it("每条 hotfix 有 CVE 编号和补丁版本", () => {
    for (const h of MOCK_RELEASES.hotfix) {
      expect(h.patchVersion.length).toBeGreaterThan(0);
      expect(h.cveNumber.length).toBeGreaterThan(0);
    }
  });
});

describe("ReleasesPage · Recall 数据", () => {
  it("有至少一条回滚记录", () => {
    expect(MOCK_RELEASES.recalls.length).toBeGreaterThan(0);
  });

  it("每条 recall 有 fromVersion 和 toVersion", () => {
    for (const r of MOCK_RELEASES.recalls) {
      expect(r.fromVersion.length).toBeGreaterThan(0);
      expect(r.toVersion.length).toBeGreaterThan(0);
    }
  });
});

describe("ReleasesPage · stageBadge", () => {
  it("rc 通道返回 warn 样式", () => {
    const badge = stageBadge("rc");
    expect(badge.label).toBe("rc");
    expect(badge.cls).toContain("warn");
  });

  it("stable 通道返回 ok 样式", () => {
    const badge = stageBadge("stable");
    expect(badge.label).toBe("stable");
    expect(badge.cls).toContain("ok");
  });
});
