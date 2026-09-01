import { describe, expect, it } from "vitest";

import { buildColleagueBusinessLoop, COLLEAGUE_BUSINESS_LOOP_DEFINITIONS } from "./colleagueBusinessLoops";

describe("colleagueBusinessLoops", () => {
  it("覆盖六数字同事且每条闭环均可进入工作台并回读贡献", () => {
    expect(Object.keys(COLLEAGUE_BUSINESS_LOOP_DEFINITIONS).sort()).toEqual([
      "campaign_planner",
      "content_officer",
      "customer_service",
      "data_advisor",
      "private_domain_manager",
      "shopping_advisor",
    ]);
    for (const definition of Object.values(COLLEAGUE_BUSINESS_LOOP_DEFINITIONS)) {
      expect(definition.businessInput).toBeTruthy();
      expect(definition.businessOutput).toBeTruthy();
      expect(definition.workshopHref).toMatch(/^\/workshop\//);
      expect(definition.contributionHref).toContain("focus=contribution");
    }
  });

  it("只展示权威回包中的 Logic，不补造本地编号", () => {
    expect(buildColleagueBusinessLoop("data_advisor", [], "blocked").logicLabels).toEqual([]);
    expect(buildColleagueBusinessLoop("data_advisor", ["D03", "A02"], "runnable").logicLabels).toEqual(["D03", "A02"]);
  });

  it("未知角色失败关闭而不是映射到默认同事", () => {
    expect(() => buildColleagueBusinessLoop("unknown_role", ["X01"], "blocked")).toThrow(/未知数字同事角色/);
  });
});
