import { describe, expect, it } from "vitest";
import {
  blockerDisplayName,
  capabilityDisplayName,
  formatBlockers,
  logicDisplayName,
  responsibilityDisplayName,
} from "./aipChineseLabels";

describe("aipChineseLabels", () => {
  it("把 logic 代号译为中文名", () => {
    expect(logicDisplayName("ecommerce.logic.S01")).toBe("意图与情绪识别");
    expect(logicDisplayName("D03")).toBe("增长方案生成");
    expect(logicDisplayName("ecommerce.logic.A01")).toBe("活动机会与目标");
  });

  it("把 Capability / 职责 / 阻断码译为中文", () => {
    expect(capabilityDisplayName("strategy.plan")).toBe("策略规划");
    expect(responsibilityDisplayName("service.escalation")).toBe("售后服务与升级");
    expect(blockerDisplayName("skill_binding_readiness_stale")).toContain("技能绑定");
    expect(blockerDisplayName("skill_revision_not_published:C01")).toContain("热点竞品");
    expect(formatBlockers(["capability_binding_readiness_stale", "skill_binding_readiness_stale"])).toContain("；");
  });
});
