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
  return "尚无阶段模板或职责计划；画布不伪造可引用的上线流程。请先在上线执行审批中登记权威记录。";
}
