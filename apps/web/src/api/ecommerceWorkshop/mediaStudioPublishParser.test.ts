import { describe, expect, it } from "vitest";

import { parseMediaStudioView } from "./parser";

const hash = "a".repeat(64);
const binding = "b".repeat(64);
const ref = (resourceType: string, resourceId: string) => ({ resourceType, resourceId, revision: 1, contentHash: hash });

function payload() {
  return {
    schemaVersion: "aos.ecommerce-workshop.media-studio-view/v5",
    tenant: { orgId: "org-org", projectId: "dev-project" },
    evaluatedAt: "2026-08-26T00:00:00Z",
    dataCutoff: "2026-08-26T00:00:00Z",
    readiness: "degraded",
    slices: ["context", "execution", "delivery"].map((sliceId) => ({
      sliceId,
      status: "ready",
      dataCutoff: "2026-08-26T00:00:00Z",
      readinessAxes: ["module", "capability", "assignee", "provider", "budget", "publication"].map((axis) => ({
        axis,
        status: "not_applicable",
        exactRef: null,
        targetContractRef: null,
        gaps: [],
        blockers: [],
      })),
      authorityRefs: [],
      blockers: [],
      countLedger: { denominator: 6, ready: 0, target: 0, blocked: 0, unknown: 0, conflict: 0, notApplicable: 6 },
    })),
    providerJobsStatus: "ready",
    providerJobs: [],
    providerJobBlockers: [],
    mediaFinanceStatus: "ready",
    mediaFinance: [],
    mediaFinanceBlockers: [],
    lifecycleStatus: "blocked",
    lifecycle: null,
    lifecycleBlockers: [{ code: "MEDIA_LIFECYCLE_NOT_AVAILABLE", dependency: "media-lifecycle", requiredAction: "refresh canonical lifecycle projection" }],
    publishStatus: "ready",
    publishContributions: [{
      schemaVersion: "aos.ecommerce-workshop.media-publish-contribution/v1",
      candidate: { familyId: "family-1", familyVersion: 3, variantRef: ref("ArtifactRevision", "variant-1"), gateSetRef: ref("MediaGateSetDecision", "gate-1"), platform: "douyin", profile: "short-video" },
      impact: { previewRef: ref("ImpactPreviewRevision", "preview-1"), actionBindingHash: binding, readiness: "ready", expiresAt: "2026-08-27T00:00:00Z", atomicSkillRefs: [ref("CapabilityRevision", "content.publish")], logicRef: ref("PlanRevision", "plan-1"), colleagueBindingRefs: [] },
      action: { proposalId: "proposal-1", proposalVersion: 2, proposalHash: hash, status: "approved", actionBindingHash: binding, approvalCount: 1, leaseId: null, attemptId: null },
      receipt: null,
      handoff: { status: "required", reasonCode: "MEDIA_PUBLISH_MANUAL_EVIDENCE_REQUIRED", requiredFacts: ["provider object identity", "observed status"], minimalDisclosure: true, completionReceiptRequired: true, completionAllowed: false },
      blockerCodes: ["MEDIA_PUBLISH_EXTERNAL_EFFECT_NOT_AUTHORIZED", "MEDIA_PUBLISH_RECEIPT_NOT_AVAILABLE"], externalEffectsAllowed: false,
    }],
    publishBlockers: [],
    page: { limit: 100, count: 0, hasMore: false, nextCursor: null },
  };
}

describe("Media Studio v5 publish contribution parser", () => {
  it("保留 Candidate/Impact/Action/Receipt/Handoff 并关闭外部副作用", () => {
    const result = parseMediaStudioView(payload(), { orgId: "org-org", projectId: "dev-project" });
    expect(result.publishContributions[0]?.candidate.variantRef.resourceId).toBe("variant-1");
    expect(result.publishContributions[0]?.impact.logicRef.resourceId).toBe("plan-1");
    expect(result.publishContributions[0]?.receipt).toBeNull();
    expect(result.publishContributions[0]?.handoff.completionAllowed).toBe(false);
    expect(result.publishContributions[0]?.externalEffectsAllowed).toBe(false);
  });

  it("拒绝 binding 漂移、伪完成 handoff 与可执行副作用", () => {
    const drifted = payload();
    drifted.publishContributions[0].action.actionBindingHash = "c".repeat(64);
    expect(() => parseMediaStudioView(drifted)).toThrow(/binding\/outcome/);
    const enabled = payload();
    enabled.publishContributions[0].handoff.completionAllowed = true;
    expect(() => parseMediaStudioView(enabled)).toThrow(/安全边界/);
    const external = payload();
    external.publishContributions[0].externalEffectsAllowed = true;
    expect(() => parseMediaStudioView(external)).toThrow(/contract/);
  });
});
