import { describe, expect, it } from "vitest";

import { parseDispatchScenario } from "./parser";

const cutoff = "2026-08-26T04:00:00Z";
const contentHash = `sha256:${"a".repeat(64)}`;
const bindingHash = "b".repeat(64);
const blocker = { code: "PROVIDER_OUTCOME_UNKNOWN_RECONCILIATION_REQUIRED", dependency: "workshop.dispatch-scenario", requiredAction: "append exact reconcile evidence" };
const stageIds = ["task_graph", "dispatch_intent", "handoff", "receiver_decision", "request_more_or_return", "takeover", "owner_timeline"] as const;
const axisIds = ["dispatch_decision_recorded", "receiver_reauthorized", "single_active_owner", "takeover_decided", "execution_reconciled"] as const;
const ref = (resourceType: string, resourceId: string) => ({ resourceType, resourceId, revision: 1, contentHash });

function blockedFixture() {
  return {
    schemaVersion: "aos.ecommerce-workshop.dispatch-scenario/v1",
    status: "blocked",
    rootTaskGraphRef: null,
    rootTaskRunRef: null,
    dispatchBindingHash: null,
    composition: null,
    evaluatedAt: cutoff,
    stages: stageIds.map((stageId) => ({ stageId, status: "blocked", exactRefs: [], contribution: "等待 exact authority", blockers: [blocker] })),
    ledger: { tasksExpected: 0, tasksObserved: 0, handoffsExpected: 0, handoffsObserved: 0, decisionsExpected: 0, decisionsRecorded: 0, accepted: 0, rejected: 0, requestMore: 0, returned: 0, takeoverRequested: 0, takeoverDecided: 0, activeOwnerCount: 0 },
    outcomeAxes: axisIds.map((axisId) => ({ axisId, status: "blocked", exactRef: null, blocker })),
    blockers: [blocker],
    commands: { dispatch: false, decideHandoff: false, requestTakeover: false, approveTakeover: false, mutateOwner: false },
    externalEffectsAllowed: false,
  };
}

function layeredFixture() {
  const graph = ref("TaskGraphRevision", "graph-1");
  const run = ref("TaskRun", "run-1");
  const stageRefs = [[graph, run], [ref("DispatchIntentRevision", "intent-1")], [ref("HandoffEnvelopeRevision", "handoff-1")], [ref("HandoffDecisionRevision", "decision-1")], [ref("ContextRequirementRevision", "gap-1")], [ref("TakeoverRequestRevision", "takeover-1")], [ref("OwnerTimelineRevision", "timeline-1")]];
  return {
    ...blockedFixture(),
    rootTaskGraphRef: graph,
    rootTaskRunRef: run,
    dispatchBindingHash: bindingHash,
    composition: {
      atomicSkillRefs: [ref("SkillRevision", "prepare-handoff"), ref("SkillRevision", "plan-responsibilities")],
      logicRevisionRef: ref("LogicRevision", "daily-control-dispatch"),
      roleBindings: [{ roleRef: ref("AgentTemplate", "operations-lead"), assigneeRef: ref("AgentInstance", "operations-lead-1"), skillBindingRef: ref("SkillBinding", "binding-1") }],
    },
    stages: stageIds.map((stageId, index) => ({ stageId, status: "ready", exactRefs: stageRefs[index], contribution: `stage ${stageId}`, blockers: [] })),
    ledger: { tasksExpected: 1, tasksObserved: 1, handoffsExpected: 1, handoffsObserved: 1, decisionsExpected: 2, decisionsRecorded: 2, accepted: 1, rejected: 0, requestMore: 1, returned: 0, takeoverRequested: 1, takeoverDecided: 1, activeOwnerCount: 1 },
    outcomeAxes: axisIds.map((axisId, index) => index === 4 ? ({ axisId, status: "unknown", exactRef: null, blocker }) : ({ axisId, status: "ready", exactRef: ref("DecisionReceiptRevision", axisId), blocker: null })),
  };
}

describe("W8-03 dispatch scenario parser", () => {
  it("keeps the missing-root response structured and command-free", () => {
    const result = parseDispatchScenario(blockedFixture());
    expect(result.stages.map((item) => item.stageId)).toEqual(stageIds);
    expect(result.outcomeAxes.map((item) => item.axisId)).toEqual(axisIds);
    expect(result.commands).toEqual({ dispatch: false, decideHandoff: false, requestTakeover: false, approveTakeover: false, mutateOwner: false });
  });

  it("keeps atomic skills, logic and digital-colleague bindings distinct", () => {
    const result = parseDispatchScenario(layeredFixture());
    expect(result.composition?.atomicSkillRefs).toHaveLength(2);
    expect(result.composition?.logicRevisionRef.resourceType).toBe("LogicRevision");
    expect(result.composition?.roleBindings[0]?.skillBindingRef.resourceType).toBe("SkillBinding");
    expect(result.ledger.activeOwnerCount).toBe(1);
  });

  it("rejects protected payload fields instead of silently parsing them", () => {
    const fixture = layeredFixture();
    (fixture.composition.roleBindings[0] as Record<string, unknown>).phone = "should-not-cross-view";
    expect(() => parseDispatchScenario(fixture)).toThrow(/\u5b57\u6bb5\u6f02\u79fb/);
  });

  it("rejects decision conservation drift and opened commands", () => {
    const ledgerDrift = layeredFixture(); ledgerDrift.ledger.decisionsRecorded = 1;
    expect(() => parseDispatchScenario(ledgerDrift)).toThrow(/ledger/);
    const commandDrift = layeredFixture(); commandDrift.commands.dispatch = true;
    expect(() => parseDispatchScenario(commandDrift)).toThrow(/command/);
  });
});
