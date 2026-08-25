import { describe, expect, it } from "vitest";

import { parseFullVideoScenario } from "./parser";

const contentHash = `sha256:${"a".repeat(64)}`;
const ref = (resourceType: string, resourceId: string) => ({ resourceType, resourceId, revision: 1, contentHash });
const blocker = { code: "FULL_VIDEO_EXTERNAL_GATE_REQUIRED", dependency: "workshop.full-video", requiredAction: "append exact current evidence" };
const stageIds = ["brief_profile", "compile_start", "script_art", "storyboard_capture", "post_review", "publish_delivery", "settlement_effect"] as const;
const responsibilityIds = ["media.producer", "media.director", "media.screenwriter", "media.art", "media.storyboard", "media.capture", "media.post", "media.review"] as const;
const faultIds = ["crash_before_submit", "crash_after_submit_before_receipt", "lease_fence_loss", "webhook_ordering", "timeout_cancel_late_result", "checkpoint_drift", "capacity_budget_race", "restart_partition", "malicious_artifact"] as const;

function fixture() {
  const brief = ref("MediaProductionBriefRevision", "brief-1"); const run = ref("TaskRun", "run-1");
  return {
    schemaVersion: "aos.ecommerce-workshop.full-video-scenario/v1", status: "blocked", rootBriefRef: brief, taskRunRef: run, fullProductionBindingHash: "b".repeat(64),
    composition: { atomicSkillRefs: [ref("SkillRevision", "media-script"), ref("SkillRevision", "media-gate-review")], logicRevisionRef: ref("LogicRevision", "full-short-video-production"), roleBindings: [{ roleRef: ref("AgentTemplate", "content-officer"), assigneeRef: ref("AgentInstance", "content-officer-1"), skillBindingRef: ref("SkillBinding", "media-script-binding") }] },
    evaluatedAt: "2026-08-26T06:00:00Z",
    responsibilities: responsibilityIds.map((responsibilityId, index) => ({ responsibilityId, label: responsibilityId, status: "assigned", assigneeRef: ref("AgentInstance", `assignee-${index % 3}`), skillBindingRef: ref("SkillBinding", `binding-${index}`), independentReviewRequired: responsibilityId === "media.review", blocker: null })),
    stages: stageIds.map((stageId, index) => index < 5 ? ({ stageId, status: "ready", exactRefs: [index === 0 ? brief : index === 1 ? run : ref("ArtifactRevision", `artifact-${index}`)], contribution: `stage ${stageId}`, blocker: null }) : ({ stageId, status: "blocked", exactRefs: [], contribution: "external gate blocked", blocker })),
    faultRecovery: faultIds.map((faultId, index) => index < 8 ? ({ faultId, status: "ready", recoveryDecision: `durable ${faultId}`, authorityRefs: [ref("RecoveryDecisionReceipt", `recovery-${index}`)], blocker: null, automaticRetryAllowed: false }) : ({ faultId, status: "unknown", recoveryDecision: "quarantine evidence required", authorityRefs: [], blocker, automaticRetryAllowed: false })),
    ledger: { responsibilitiesExpected: 8, responsibilitiesObserved: 8, stagesExpected: 7, stagesObserved: 5, attemptsExpected: 5, attemptsObserved: 5, artifactsExpected: 6, artifactsObserved: 6, mediaGatesExpected: 4, mediaGatesObserved: 4, faultCasesExpected: 9, faultCasesObserved: 8, usageBucketsExpected: 2, usageBucketsObserved: 2 },
    blockers: [blocker], commands: { prepare: false, start: false, resume: false, takeover: false, cancel: false, reconcile: false, publish: false, settle: false }, externalEffectsAllowed: false, releaseAllowed: false,
  };
}

describe("W8-05 FULL video scenario parser", () => {
  it("preserves four layers, eight responsibilities and nine fault axes", () => {
    const result = parseFullVideoScenario(fixture());
    expect(result.composition?.atomicSkillRefs).toHaveLength(2);
    expect(result.composition?.logicRevisionRef.resourceType).toBe("LogicRevision");
    expect(result.responsibilities).toHaveLength(8);
    expect(result.faultRecovery).toHaveLength(9);
    expect(result.ledger.mediaGatesObserved).toBe(4);
    expect(Object.values(result.commands).every((value) => value === false)).toBe(true);
  });

  it("rejects protected payload and opened commands", () => {
    const protectedPayload = fixture(); (protectedPayload.composition as Record<string, unknown>).mediaPayload = "secret";
    expect(() => parseFullVideoScenario(protectedPayload)).toThrow(/字段漂移/);
    const opened = fixture(); opened.commands.start = true;
    expect(() => parseFullVideoScenario(opened)).toThrow(/command/);
  });

  it("rejects ledger and exact-root drift", () => {
    const ledger = fixture(); ledger.ledger.faultCasesObserved = 9;
    expect(() => parseFullVideoScenario(ledger)).toThrow(/ledger/);
    const root = fixture(); root.stages[0].exactRefs = [ref("MediaProductionBriefRevision", "brief-other")];
    expect(() => parseFullVideoScenario(root)).toThrow(/root stage/);
  });
});
