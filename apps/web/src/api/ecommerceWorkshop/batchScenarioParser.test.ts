import { describe, expect, it } from "vitest";

import { parseBatchScenario } from "./parser";

const exactRef = (resourceType: string, resourceId: string) => ({ resourceType, resourceId, revision: 1, contentHash: `sha256:${"a".repeat(64)}` });
const blocker = { code: "CHILD_OUTCOME_UNKNOWN_RECONCILIATION_REQUIRED", dependency: "workshop.batch-scenario", requiredAction: "reread same fingerprint" };
const fixture = () => ({
  schemaVersion: "aos.ecommerce-workshop.batch-scenario/v1", status: "blocked",
  batchPreparationRevisionRef: exactRef("BatchPreparationRevision", "prepare-1"), batchStartDecisionRef: exactRef("BatchStartDecision", "start-1"), batchStartBindingHash: "b".repeat(64),
  composition: { atomicSkillRefs: [exactRef("SkillRevision", "freeze-batch")], logicRevisionRef: exactRef("LogicRevision", "batch-loop"), roleBindings: [{ roleRef: exactRef("AgentTemplate", "operator"), assigneeRef: exactRef("AgentInstance", "operator-1"), skillBindingRef: exactRef("SkillBinding", "binding-1") }] },
  evaluatedAt: "2026-08-26T07:00:00Z",
  preparationDecisions: [
    { itemKey: "item-1", disposition: "included", originalRefs: [exactRef("BusinessItemRevision", "item-1")], decisionRef: exactRef("ItemPreparationDecision", "decision-1"), reasonCodes: [] },
    { itemKey: "item-2", disposition: "unknown", originalRefs: [exactRef("BusinessItemRevision", "item-2")], decisionRef: exactRef("ItemPreparationDecision", "decision-2"), reasonCodes: ["SOURCE_FACT_UNKNOWN"] },
  ],
  childOutcomes: [{ itemKey: "item-1", status: "unknown", requestFingerprint: "c".repeat(64), attemptRef: exactRef("Attempt", "attempt-1"), authorityRefs: [exactRef("ProviderRequestReceipt", "request-1")], reconcileReceiptRefs: [], automaticRetryAllowed: false }],
  stages: ["prepare_root", "impact_cost_preview", "explicit_start", "child_dispatch", "partial_outcomes", "unknown_reconcile", "restart_rebuild"].map((stageId, index) => index < 5 ? { stageId, status: "ready", exactRefs: index === 0 ? [exactRef("BatchPreparationRevision", "prepare-1"), exactRef("BatchStartDecision", "start-1")] : [exactRef("StageReceipt", `stage-${index}`)], contribution: `stage ${stageId}`, blockers: [] } : { stageId, status: index === 5 ? "unknown" : "blocked", exactRefs: [], contribution: `wait ${stageId}`, blockers: [blocker] }),
  ledger: { frozenTotal: 2, included: 1, excluded: 0, blocked: 0, preparationUnknown: 1, childrenExpected: 1, childrenObserved: 1, succeeded: 0, failed: 0, cancelled: 0, childUnknown: 1, reconciled: 0, reconcileReceiptsObserved: 0 },
  outcomeAxes: ["business_item", "external_action", "usage_settlement", "effect_maturity", "handoff_decision"].map((axisId) => ({ axisId, status: "unknown", exactRefs: [], blockers: [blocker] })),
  sideEffectLedger: { prepareExternalCalls: 0, providerCalls: 0, actionAttempts: 0, externalEffects: 0 }, blockers: [blocker], commands: { prepare: false, start: false, cancel: false, reconcile: false }, automaticRetryAllowed: false, externalEffectsAllowed: false, releaseAllowed: false,
});

describe("parseBatchScenario", () => {
  it("保留准备判定、unknown 子结果与四层绑定", () => {
    const result = parseBatchScenario(fixture());
    expect(result.preparationDecisions.map((item) => item.disposition)).toEqual(["included", "unknown"]);
    expect(result.childOutcomes[0].status).toBe("unknown");
    expect(result.composition?.logicRevisionRef.resourceType).toBe("LogicRevision");
    expect(result.commands.start).toBe(false);
  });

  it("拒绝命令开启、账本漂移与受保护字段", () => {
    const command = fixture(); command.commands.start = true;
    expect(() => parseBatchScenario(command)).toThrow(/command/);
    const ledger = fixture(); ledger.ledger.childrenObserved = 0;
    expect(() => parseBatchScenario(ledger)).toThrow(/ledger/);
    const protectedPayload = { ...fixture(), providerToken: "secret" };
    expect(() => parseBatchScenario(protectedPayload)).toThrow(/字段漂移/);
  });
});
