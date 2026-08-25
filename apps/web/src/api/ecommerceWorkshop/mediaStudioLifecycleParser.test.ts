import { describe, expect, it } from "vitest";

import { parseMediaStudioView } from "./parser";

const hash = "a".repeat(64);
const ref = (resourceType: string, resourceId: string) => ({ resourceType, resourceId, revision: 1, contentHash: hash });
const nodes = ["prepare", "freeze_confirm", "compile_approve", "start_run", "review_return", "deliver_publish", "reconcile_effect"] as const;
const slots = ["media.producer", "media.director", "media.screenwriter", "media.art", "media.storyboard", "media.capture", "media.post", "media.review"] as const;

function payload() {
  const dataCutoff = "2026-08-26T00:00:00Z";
  return {
    schemaVersion: "aos.ecommerce-workshop.media-studio-view/v4",
    tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: dataCutoff, dataCutoff, readiness: "degraded",
    slices: ["context", "execution", "delivery"].map((sliceId) => ({ sliceId, status: "ready", dataCutoff, readinessAxes: ["module", "capability", "assignee", "provider", "budget", "publication"].map((axis) => ({ axis, status: "not_applicable", exactRef: null, targetContractRef: null, gaps: [], blockers: [] })), authorityRefs: [], blockers: [], countLedger: { denominator: 6, ready: 0, target: 0, blocked: 0, unknown: 0, conflict: 0, notApplicable: 6 } })),
    providerJobsStatus: "ready", providerJobs: [], providerJobBlockers: [], mediaFinanceStatus: "ready", mediaFinance: [], mediaFinanceBlockers: [],
    lifecycleStatus: "ready",
    lifecycle: {
      schemaVersion: "aos.ecommerce-workshop.media-studio-lifecycle/v1", contextId: "context-1", contextRevision: 2, contextHash: hash, taskId: "task-1", status: "partial",
      lifecycle: nodes.map((nodeId, index) => ({ nodeId, label: nodeId, status: index < 4 ? "active" : "blocked", authorityRefs: index < 4 ? [ref("ProductionContextRevision", "context-1")] : [], blockerCodes: index < 4 ? [] : ["MEDIA_NOT_AUTHORIZED"], observedAt: null })),
      responsibilities: slots.map((slotId) => ({ slotId, label: slotId, responsibilityType: slotId, status: "assigned", requiredCapabilityIds: ["video.compose"], assigneeKind: "digital_colleague", assigneeId: `colleague:${slotId}`, assigneeVersion: 1, resolutionReceiptId: `receipt:${slotId}`, blockerCodes: [] })),
      stages: [{ stageId: "stage-1", taskRunId: "run-1", attempt: 1, status: "running", capabilityRef: ref("CapabilityRevision", "video.compose"), colleagueBindingRef: ref("CapabilityBindingRevision", "content-officer"), providerRef: ref("ProviderInstanceRevision", "provider-1"), providerJobId: "job-1", blockerCodes: [], externalEffectsAllowed: false }],
      artifactFamilies: [{ familyId: "family-1", version: 1, topologyStatus: "valid", memberCount: 1, conflictCount: 0, gateSetCount: 1, latestGateReadiness: "review_required", issueCount: 1 }],
      reviewIssues: [{ issueId: "issue-1", version: 1, status: "open", severity: "major", artifactId: "artifact-1", artifactHash: hash, returnStage: "post", returnDecisionCount: 1 }],
      commandCapabilities: ["freeze", "start", "pause_resume", "return", "publish", "settle_reconcile"].map((commandId) => ({ commandId, allowed: false, reasonCode: "MEDIA_STUDIO_W7_09_READ_ONLY_NO_EXTERNAL_EFFECT", expectedVersion: 2, requiredExactRefs: [ref("ProductionContextRevision", "context-1")] })),
      blockerCodes: ["MEDIA_PUBLICATION_NOT_AUTHORIZED"], externalEffectsAllowed: false,
    },
    lifecycleBlockers: [], page: { limit: 100, count: 0, hasMore: false, nextCursor: null },
  };
}

describe("Media Studio v4 lifecycle parser", () => {
  it("保留七节点、八职责、Stage 与交付贡献且所有命令失败关闭", () => {
    const result = parseMediaStudioView(payload(), { orgId: "org-org", projectId: "dev-project" });
    expect(result.lifecycle?.lifecycle.map((item) => item.nodeId)).toEqual(nodes);
    expect(result.lifecycle?.responsibilities.map((item) => item.slotId)).toEqual(slots);
    expect(result.lifecycle?.stages[0].capabilityRef.resourceId).toBe("video.compose");
    expect(result.lifecycle?.artifactFamilies[0].issueCount).toBe(1);
    expect(result.lifecycle?.commandCapabilities.every((item) => item.allowed === false)).toBe(true);
  });

  it("拒绝职责乱序和伪造可执行命令", () => {
    const wrongOrder = payload();
    wrongOrder.lifecycle.responsibilities.reverse();
    expect(() => parseMediaStudioView(wrongOrder)).toThrow(/responsibility canonical order/);
    const enabled = payload();
    enabled.lifecycle.commandCapabilities[0].allowed = true;
    expect(() => parseMediaStudioView(enabled)).toThrow(/失败关闭/);
  });
});
