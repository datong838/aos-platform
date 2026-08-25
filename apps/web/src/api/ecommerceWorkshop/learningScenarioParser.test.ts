import { describe, expect, it } from "vitest";

import { parseLearningScenario } from "./parser";

const cutoff = "2026-08-26T05:00:00Z";
const contentHash = `sha256:${"a".repeat(64)}`;
const bindingHash = "b".repeat(64);
const blocker = { code: "REVOCATION_IMPACT_REVIEW_REQUIRED", dependency: "workshop.learning-scenario", requiredAction: "append exact impact evidence" };
const stageIds = ["effect_review", "maturity", "memory_candidate", "governance", "promotion", "knowledge_query", "revocation_impact"] as const;
const axisIds = ["effect_mature", "candidate_governed", "knowledge_promoted", "future_query_authorized", "revocation_impact_recorded"] as const;
const ref = (resourceType: string, resourceId: string) => ({ resourceType, resourceId, revision: 1, contentHash });

function blockedFixture() {
  return {
    schemaVersion: "aos.ecommerce-workshop.learning-scenario/v1",
    status: "blocked",
    rootEffectReviewRef: null,
    maturityPolicyRef: null,
    learningBindingHash: null,
    composition: null,
    evaluatedAt: cutoff,
    stages: stageIds.map((stageId) => ({ stageId, status: "blocked", exactRefs: [], contribution: "等待 exact authority", blockers: [blocker] })),
    ledger: { reviewsExpected: 0, reviewsObserved: 0, candidatesExpected: 0, candidatesObserved: 0, promotionsExpected: 0, promotionsObserved: 0, citationsExpected: 0, citationsObserved: 0, historicalExposures: 0, retainedExposures: 0, impactRefsExpected: 0, impactRefsObserved: 0 },
    outcomeAxes: axisIds.map((axisId) => ({ axisId, status: "blocked", exactRef: null, blocker })),
    blockers: [blocker],
    commands: { submitCandidate: false, approveCandidate: false, promoteCandidate: false, publishWiki: false, revokeKnowledge: false },
    externalEffectsAllowed: false,
  };
}

function layeredFixture() {
  const review = ref("EffectReviewRevision", "review-1");
  const maturity = ref("EffectMaturityPolicyRevision", "maturity-1");
  const stageRefs = [[review], [maturity], [ref("MemoryCandidateRevision", "candidate-1")], [ref("GovernanceApprovalRevision", "approval-1")], [ref("WikiRevision", "wiki-1")], [ref("KnowledgeCitationRevision", "citation-1")], []];
  return {
    ...blockedFixture(),
    rootEffectReviewRef: review,
    maturityPolicyRef: maturity,
    learningBindingHash: bindingHash,
    composition: {
      atomicSkillRefs: [ref("SkillRevision", "review-outcomes"), ref("SkillRevision", "govern-knowledge")],
      logicRevisionRef: ref("LogicRevision", "effect-to-governed-knowledge"),
      roleBindings: [{ roleRef: ref("AgentTemplate", "analyst"), assigneeRef: ref("AgentInstance", "analyst-1"), skillBindingRef: ref("SkillBinding", "learning-binding-1") }],
    },
    stages: stageIds.map((stageId, index) => index === 6 ? ({ stageId, status: "unknown", exactRefs: [], contribution: "等待影响复核", blockers: [blocker] }) : ({ stageId, status: "ready", exactRefs: stageRefs[index], contribution: `stage ${stageId}`, blockers: [] })),
    ledger: { reviewsExpected: 1, reviewsObserved: 1, candidatesExpected: 1, candidatesObserved: 1, promotionsExpected: 1, promotionsObserved: 1, citationsExpected: 1, citationsObserved: 1, historicalExposures: 2, retainedExposures: 2, impactRefsExpected: 1, impactRefsObserved: 0 },
    outcomeAxes: axisIds.map((axisId, index) => index === 4 ? ({ axisId, status: "unknown", exactRef: null, blocker }) : ({ axisId, status: "ready", exactRef: ref("LearningOutcomeRevision", axisId), blocker: null })),
  };
}

describe("W8-04 learning scenario parser", () => {
  it("keeps the missing-root response structured and command-free", () => {
    const result = parseLearningScenario(blockedFixture());
    expect(result.stages.map((item) => item.stageId)).toEqual(stageIds);
    expect(result.outcomeAxes.map((item) => item.axisId)).toEqual(axisIds);
    expect(result.commands).toEqual({ submitCandidate: false, approveCandidate: false, promoteCandidate: false, publishWiki: false, revokeKnowledge: false });
  });

  it("keeps atomic skills, logic and digital-colleague bindings distinct", () => {
    const result = parseLearningScenario(layeredFixture());
    expect(result.composition?.atomicSkillRefs).toHaveLength(2);
    expect(result.composition?.logicRevisionRef.resourceType).toBe("LogicRevision");
    expect(result.composition?.roleBindings[0]?.skillBindingRef.resourceType).toBe("SkillBinding");
    expect(result.ledger.historicalExposures).toBe(result.ledger.retainedExposures);
  });

  it("rejects protected payload fields instead of silently parsing them", () => {
    const fixture = layeredFixture();
    (fixture.composition.roleBindings[0] as Record<string, unknown>).wikiBody = "protected-content";
    expect(() => parseLearningScenario(fixture)).toThrow(/字段漂移/);
  });

  it("rejects lost historical exposures and opened governance commands", () => {
    const ledgerDrift = layeredFixture(); ledgerDrift.ledger.retainedExposures = 1;
    expect(() => parseLearningScenario(ledgerDrift)).toThrow(/ledger/);
    const commandDrift = layeredFixture(); commandDrift.commands.promoteCandidate = true;
    expect(() => parseLearningScenario(commandDrift)).toThrow(/command/);
  });
});
