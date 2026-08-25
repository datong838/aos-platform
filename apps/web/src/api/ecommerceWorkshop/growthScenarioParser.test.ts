import { describe, expect, it } from "vitest";

import { parseAnalystView } from "./parser";

const views = ["overview", "drivers", "diagnosis", "plan", "effects", "evidence", "quality"] as const;
const readinessAxes = ["metric_query", "model", "eval", "plan_materialization", "professional_handoff"] as const;
const stages = ["insight", "growth_plan", "content", "creator", "media", "publication", "effect_review", "memory_candidate"] as const;
const outcomeAxes = ["provider_applied", "usage_settled", "effect_mature", "memory_governed"] as const;
const cutoff = "2026-08-26T03:00:00Z";
const blocker = { code: "GROWTH_PLAN_EXACT_ROOT_REQUIRED", dependency: "workshop.growth-plan-authority", requiredAction: "provide tenant-bound exact refs" };

function payload() {
  return {
    schemaVersion: "aos.ecommerce-workshop.analyst-view/v2", tenant: { orgId: "org-org", projectId: "dev-project" }, resourceRevision: 1, evaluatedAt: cutoff, dataCutoff: cutoff, readiness: "degraded",
    views: views.map((viewId) => { const viewBlocker = { code: `ANALYST_${viewId.toUpperCase()}_AUTHORITY_NOT_AVAILABLE`, dependency: viewId, requiredAction: "attach exact refs" }; return { viewId, status: "blocked", resourceRevision: 1, dataCutoff: cutoff, readinessAxes: readinessAxes.map((axis) => ({ axis, status: "blocked", exactRef: null, blockers: [viewBlocker] })), metrics: [], authorityRefs: [], blockers: [viewBlocker], countLedger: { denominator: 0, ready: 0, unknown: 0, blocked: 0, conflict: 0 } }; }),
    growthScenario: { schemaVersion: "aos.ecommerce-workshop.growth-scenario/v1", status: "blocked", rootPlanRef: null, scenarioBindingHash: null, evaluatedAt: cutoff, stages: stages.map((stageId) => ({ stageId, status: "blocked", exactRefs: [], contribution: "等待 exact authority", blockers: [blocker] })), ledger: { tasksExpected: 0, tasksObserved: 0, handoffsExpected: 0, handoffsObserved: 0, outcomesExpected: 4, outcomesReady: 0, outcomesBlocked: 4, outcomesUnknown: 0 }, outcomeAxes: outcomeAxes.map((axisId) => ({ axisId, status: "blocked", exactRef: null, blocker })), blockers: [blocker], commands: { materialize: false, dispatch: false, publish: false, promoteMemory: false }, externalEffectsAllowed: false },
    page: { limit: 100, count: 0, hasMore: false, nextCursor: null },
  };
}

describe("Analyst v2 growth scenario parser", () => {
  it("保留八阶段、四轴与写入口关闭", () => {
    const result = parseAnalystView(payload(), { orgId: "org-org", projectId: "dev-project" });
    expect(result.growthScenario?.stages).toHaveLength(8);
    expect(result.growthScenario?.outcomeAxes).toHaveLength(4);
    expect(result.growthScenario?.commands).toEqual({ materialize: false, dispatch: false, publish: false, promoteMemory: false });
  });

  it("拒绝越门命令、数量不守恒和负向租户串线", () => {
    const command = payload(); command.growthScenario.commands.publish = true as false;
    expect(() => parseAnalystView(command)).toThrow(/write command/);
    const ledger = payload(); ledger.growthScenario.ledger.outcomesBlocked = 3;
    expect(() => parseAnalystView(ledger)).toThrow(/不守恒/);
    expect(() => parseAnalystView(payload(), { orgId: "dev-org", projectId: "dev-project" })).toThrow(/tenant|租户/);
  });
});
