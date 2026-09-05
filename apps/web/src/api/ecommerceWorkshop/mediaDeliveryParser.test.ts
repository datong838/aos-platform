import { describe, expect, it } from "vitest";

import { parseMediaDeliveryExport, parseMediaDeliveryPublishProposal, parseMediaDeliveryWorkspace } from "./mediaDeliveryParser";

const hash = "a".repeat(64);
const ref = (resourceType: string, resourceId: string, revision = 1, contentHash = hash) => ({ resourceType, resourceId, revision, contentHash });
const draft = { ...ref("TaskBriefRevision", "brief-1"), version: 1, mediaType: "planting_copy", title: "种草任务", summary: "准备种草内容", details: { mediaType: "planting_copy", lastCommand: "create" }, status: "draft" };
const zero = { providerInvocationCount: 0, externalGenerationCount: 0, feeChargeCount: 0, publicationCount: 0, businessMutationCount: 0 };

describe("media delivery strict parser", () => {
  it("parses exact history, review and publish candidate", () => {
    const value = { tenant: { orgId: "org-org", projectId: "dev-project" }, currentDraft: draft, history: [draft], historyCount: 1, candidates: [{ familyId: "family-1", familyVersion: 2, variantRef: ref("ArtifactRevision", "variant-1"), gateSetRef: ref("MediaGateSetDecision", "gate-1"), gateReadiness: "ready", impactPreviewRefs: [ref("ImpactPreviewRevision", "preview-1")], reviewIssues: [{ issueId: "issue-1", version: 1, status: "resolved", severity: "warning", returnStage: "review" }], returnDecisionCount: 1, publishReady: true, blockerCodes: [] }], blockerCodes: [], externalEffectsAllowed: false };
    expect(parseMediaDeliveryWorkspace(value).candidates[0]?.publishReady).toBe(true);
    expect(() => parseMediaDeliveryWorkspace({ ...value, historyCount: 2 })).toThrow(/history/i);
    expect(() => parseMediaDeliveryWorkspace({ ...value, externalEffectsAllowed: true })).toThrow(/external/i);
  });

  it("parses deterministic export and zero side effects", () => {
    const value = { tenant: { orgId: "org-org", projectId: "dev-project" }, fileName: "media-brief-1-r1.json", contentType: "application/json", content: "{}", contentHash: hash, sideEffects: zero };
    expect(parseMediaDeliveryExport(value).fileName).toContain("brief-1");
    expect(() => parseMediaDeliveryExport({ ...value, sideEffects: { ...zero, publicationCount: 1 } })).toThrow(/effect/i);
  });

  it("parses internal Proposal without implying publication", () => {
    const value = { tenant: { orgId: "org-org", projectId: "dev-project" }, proposal: { proposalId: "proposal-1", version: 1, proposalHash: hash, status: "pending" }, sideEffects: zero, message: "Proposal 已创建，未发布" };
    expect(parseMediaDeliveryPublishProposal(value).proposal.status).toBe("pending");
  });
});
