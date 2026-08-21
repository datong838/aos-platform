import type { ResponsibilityPlanRevision, StageTemplateRevision } from "../../api/aipProductionContracts";

export type ProductionProfileProjection = {
  profile: string;
  stageCount: number;
  planCount: number;
  stageReady: number;
  planReady: number;
};

export function projectProductionProfiles(
  stages: StageTemplateRevision[],
  plans: ResponsibilityPlanRevision[],
): ProductionProfileProjection[] {
  const map = new Map<string, ProductionProfileProjection>();
  for (const stage of stages) {
    const profile = String(stage.profile || "").trim();
    if (!profile) continue;
    const row = map.get(profile) || { profile, stageCount: 0, planCount: 0, stageReady: 0, planReady: 0 };
    row.stageCount += 1;
    if (stage.readiness === "ready") row.stageReady += 1;
    map.set(profile, row);
  }
  for (const plan of plans) {
    const profile = String(plan.profile || "").trim();
    if (!profile) continue;
    const row = map.get(profile) || { profile, stageCount: 0, planCount: 0, stageReady: 0, planReady: 0 };
    row.planCount += 1;
    if (plan.readiness === "ready") row.planReady += 1;
    map.set(profile, row);
  }
  return [...map.values()].sort((a, b) => a.profile.localeCompare(b.profile));
}

export function productionProjectionEmptyMessage(stageCount: number, planCount: number): string | null {
  if (stageCount > 0 || planCount > 0) return null;
  return "尚无 StageTemplate / ResponsibilityPlan；画布不伪造可引用 Profile。请先在生产契约登记权威表。";
}
