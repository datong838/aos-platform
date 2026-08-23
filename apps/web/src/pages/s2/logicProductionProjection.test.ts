import { describe, expect, it } from "vitest";
import { productionProjectionEmptyMessage, projectProductionProfiles } from "./logicProductionProjection";
import type { ResponsibilityPlanRevision, StageTemplateRevision } from "../../api/aipProductionContracts";

describe("logicProductionProjection", () => {
  it("aggregates stage/plan profiles without inventing rows", () => {
    expect(projectProductionProfiles([], [])).toEqual([]);
    expect(productionProjectionEmptyMessage(0, 0)).toContain("尚无阶段模板或职责计划");
    const stages = [
      { profile: "ecommerce-standard", readiness: "ready" },
      { profile: "media-full", readiness: "blocked" },
    ] as StageTemplateRevision[];
    const plans = [
      { profile: "ecommerce-standard", readiness: "blocked" },
    ] as ResponsibilityPlanRevision[];
    expect(projectProductionProfiles(stages, plans)).toEqual([
      { profile: "ecommerce-standard", stageCount: 1, planCount: 1, stageReady: 1, planReady: 0 },
      { profile: "media-full", stageCount: 1, planCount: 0, stageReady: 0, planReady: 0 },
    ]);
    expect(productionProjectionEmptyMessage(1, 0)).toBeNull();
  });
});
