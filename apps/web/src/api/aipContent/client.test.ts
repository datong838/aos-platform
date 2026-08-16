import { describe, expect, it } from "vitest";
import { parseContentBrief, parseContentPipeline, parsePublishProposal } from "./parser";

const hash = "a".repeat(64);
const exact = (resourceType: string, resourceId: string) => ({ resourceType, resourceId, revision: 1, contentHash: hash });
const resource = (resourceType: string, resourceId: string) => ({ resourceType, resourceId, revision: "1", authority: "aip-authority" });
const mutable = (resourceType: string, resourceId: string) => ({ resourceType, resourceId, version: 1 });

describe("AIP-9 Content-0A strict parser", () => {
  it("解析真实事实引用的 content brief，并拒绝租户注入", () => {
    const brief = { briefType:"content_campaign",objective:"真实商品种草",deliverableKinds:["seed_copy"],channelTargets:["weapp"],productRefs:[resource("Product","product-1")],audienceRefs:[],evidenceBundleRef:exact("EvidenceBundleRevision","evidence-1"),factualClaimPolicy:"evidence_only",contentConstraints:{language:"zh-CN"},cutoffAt:"2026-08-16T00:00:00Z" };
    expect(parseContentBrief(brief).productRefs[0].revision).toBe("1");
    expect(() => parseContentBrief({ ...brief, orgId: "dev-org" })).toThrow("未知字段");
  });

  it("pipeline readiness 与 blockers 必须一致", () => {
    const pipeline = { briefRef:exact("TaskBriefRevision","brief-1"),stageTemplateRef:exact("StageTemplateRevision","stage-1"),responsibilityPlanRef:exact("ResponsibilityPlanRevision","plan-1"),evalContractRef:exact("EvalContractRevision","eval-1"),modelRouteRef:null,runtimePolicyRef:null,capabilityRefs:[],toolBindingRefs:[],budgetRef:null,readiness:"blocked",blockers:[{code:"RESPONSIBILITY_TEMPLATE_AUTHORITY_MISSING",message:"missing",resourceRef:null}] };
    expect(parseContentPipeline(pipeline).readiness).toBe("blocked");
    expect(() => parseContentPipeline({ ...pipeline, readiness: "ready" })).toThrow("不一致");
  });

  it("PublishProposal 只能表达 proposal_only，拒绝假平台回执", () => {
    const value = { actionType:"publish_content",contentDraftRef:{artifactId:"draft-1",artifactType:"content_draft",revision:"1",contentHash:hash},channel:"weapp",accountRef:mutable("PlatformAccountBinding","account-1"),harnessRevisionRef:exact("PlatformHarnessRevision","weapp"),impactPreviewRef:exact("ImpactPreviewRevision","preview-1"),evidenceBundleRef:exact("EvidenceBundleRevision","evidence-1"),requestedMode:"proposal_only",scheduledAt:null };
    expect(parsePublishProposal(value).requestedMode).toBe("proposal_only");
    expect(() => parsePublishProposal({ ...value, platformReceipt: "fake" })).toThrow("未知字段");
  });
});
