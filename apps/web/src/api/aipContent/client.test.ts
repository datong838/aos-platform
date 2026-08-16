import { describe, expect, it, vi } from "vitest";
import { AipContentSdk, type AipContentTransport } from "./client";
import type { AvatarSessionOpenRequest, MediaJobCreateRequest } from "./contracts";
import { parseContentBrief, parseContentPipeline, parsePublishProposal } from "./parser";

const hash = "a".repeat(64);
const exact = (resourceType: string, resourceId: string) => ({ resourceType, resourceId, revision: 1, contentHash: hash });
const resource = (resourceType: string, resourceId: string) => ({ resourceType, resourceId, revision: "1", authority: "aip-authority" });
const mutable = (resourceType: string, resourceId: string) => ({ resourceType, resourceId, version: 1 });
const tenant = { orgId: "org-org", projectId: "dev-project" };
const now = "2026-08-16T05:00:00Z";
const mediaSnapshot = { tenant,jobId:"media-job-1",requestHash:hash,taskRunRef:resource("TaskRun","run-1"),stepRunRef:resource("StepRun","step-1"),jobKind:"video_render",attempt:1,status:"queued",latestSequence:1,executorLeaseRef:null,heartbeatAt:null,leaseExpiresAt:null,outputArtifactRefs:[],completionReceiptRef:null,blockers:[],reasonCode:null,createdAt:now,updatedAt:now,finishedAt:null };
const avatarSnapshot = { tenant,sessionId:"avatar-session-1",requestHash:hash,taskRunRef:resource("TaskRun","run-1"),stepRunRef:resource("StepRun","step-1"),capabilityBindingRef:mutable("CapabilityBinding","avatar-1"),budgetRef:exact("BudgetRevision","budget-1"),killPolicyRef:exact("KillPolicyRevision","kill-1"),maxDurationSeconds:300,status:"opening",latestSequence:1,engineSessionRef:null,humanHeartbeatAt:null,humanHeartbeatExpiresAt:null,completionReceiptRef:null,blockers:[],reasonCode:null,createdAt:now,updatedAt:now,finishedAt:null };
const mediaRequest: MediaJobCreateRequest = { taskRunRef:resource("TaskRun","run-1"),stepRunRef:resource("StepRun","step-1"),jobKind:"video_render",inputAssets:[{artifactRef:{artifactId:"image-1",artifactType:"image",revision:"1",contentHash:hash},mediaType:"image",usage:"input",provenanceRef:exact("AssetProvenanceRevision","p-1"),licenseRef:exact("AssetLicenseRevision","l-1"),evidenceBundleRef:exact("EvidenceBundleRevision","e-1"),withdrawalPolicyRef:exact("AssetWithdrawalPolicyRevision","w-1")}],outputSchemaRef:resource("JsonSchemaRevision","video-v1"),capabilityRef:exact("CapabilityRevision","render"),capabilityBindingRef:mutable("CapabilityBinding","render-1"),budgetRef:exact("BudgetRevision","budget-1"),deadlineAt:"2026-08-16T06:00:00Z" };
const avatarRequest: AvatarSessionOpenRequest = { taskRunRef:resource("TaskRun","run-1"),stepRunRef:resource("StepRun","step-1"),capabilityRef:exact("CapabilityRevision","avatar"),capabilityBindingRef:mutable("CapabilityBinding","avatar-1"),budgetRef:exact("BudgetRevision","budget-1"),killPolicyRef:exact("KillPolicyRevision","kill-1"),livePlanRef:{artifactId:"plan-1",artifactType:"live_plan",revision:"1",contentHash:hash},maxDurationSeconds:300 };

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

describe("AIP-9 Content-0E strict SDK", () => {
  it("覆盖 24 条 canonical operation，统一携带幂等键并编码资源 ID", async () => {
    const get = vi.fn(async (path: string) => path.includes("avatar-sessions?limit=") ? [avatarSnapshot] : path.includes("avatar") ? avatarSnapshot : path.includes("media-jobs/") ? mediaSnapshot : [mediaSnapshot]);
    const post = vi.fn(async (path: string, _body: unknown, _headers: Record<string,string>) => path.includes("avatar") ? avatarSnapshot : mediaSnapshot);
    const sdk = new AipContentSdk({ get, post } as AipContentTransport, () => tenant);
    await sdk.listMediaJobs(20); await sdk.getMediaJob("media/job 1"); await sdk.submitMediaJob(mediaRequest,"media-create");
    const lease={executorLeaseRef:resource("ExecutorLease","lease-1"),heartbeatAt:now,leaseExpiresAt:"2026-08-16T05:05:00Z",expectedVersion:1};
    await sdk.claimMediaJob("job-1",lease,"claim"); await sdk.heartbeatMediaJob("job-1",{...lease,expectedVersion:2},"heartbeat");
    await sdk.completeMediaJob("job-1",{expectedVersion:3,outputArtifactRefs:[{artifactId:"video-1",artifactType:"video",revision:"1",contentHash:hash}]},"complete");
    await sdk.failMediaJob("job-1",{expectedVersion:1,reasonCode:"failed"},"fail"); await sdk.cancelMediaJob("job-1",{expectedVersion:1,reasonCode:"cancelled"},"cancel");
    await sdk.markMediaJobUnknown("job-1",{expectedVersion:1,blockers:[{code:"LOST",message:"lost",resourceRef:null}]},"unknown"); await sdk.reconcileMediaJob("job-1",{expectedVersion:2,reconcileStatus:"queued"},"reconcile");
    await sdk.listAvatarSessions(20); await sdk.getAvatarSession("avatar/session 1"); await sdk.openAvatarSession(avatarRequest,"avatar-create");
    await sdk.readyAvatarSession("session-1",{expectedVersion:1},"ready");
    const live={expectedVersion:2,engineSessionRef:exact("OpaqueAvatarEngineSessionRef","engine-1"),heartbeatAt:now,heartbeatExpiresAt:"2026-08-16T05:01:00Z"};
    await sdk.liveAvatarSession("session-1",live,"live"); await sdk.heartbeatAvatarSession("session-1",{expectedVersion:3,heartbeatAt:now,heartbeatExpiresAt:"2026-08-16T05:01:00Z"},"avatar-heartbeat");
    await sdk.pauseAvatarSession("session-1",{expectedVersion:4},"pause"); await sdk.resumeAvatarSession("session-1",{...live,expectedVersion:5},"resume");
    await sdk.closingAvatarSession("session-1",{expectedVersion:6},"closing"); await sdk.closeAvatarSession("session-1",{expectedVersion:7},"close");
    await sdk.failAvatarSession("session-1",{expectedVersion:1,reasonCode:"failed"},"avatar-fail"); await sdk.killAvatarSession("session-1",{expectedVersion:1,reasonCode:"killed"},"kill");
    await sdk.markAvatarSessionUnknown("session-1",{expectedVersion:1,blockers:[{code:"LOST",message:"lost",resourceRef:null}]},"avatar-unknown"); await sdk.reconcileAvatarSession("session-1",{expectedVersion:2,reconcileStatus:"opening"},"avatar-reconcile");
    expect(get).toHaveBeenCalledTimes(4); expect(post).toHaveBeenCalledTimes(20);
    expect(get).toHaveBeenCalledWith("/v1/aip/content/media-jobs/media%2Fjob%201");
    expect(get).toHaveBeenCalledWith("/v1/aip/content/avatar-sessions/avatar%2Fsession%201");
    expect(post.mock.calls.every((call) => call[2]["Idempotency-Key"])).toBe(true);
  });

  it("响应 tenant 漂移、authority 注入和非法本地参数在网络前失败关闭", async () => {
    const get = vi.fn().mockResolvedValue([{...mediaSnapshot,tenant:{orgId:"dev-org",projectId:"dev-project"}}]);
    const post = vi.fn().mockResolvedValue(mediaSnapshot);
    const sdk = new AipContentSdk({get,post} as AipContentTransport,()=>tenant);
    await expect(sdk.listMediaJobs()).rejects.toThrow("tenant echo 不一致");
    await expect(sdk.getMediaJob(" bad ")).rejects.toThrow("id 无效");
    await expect(sdk.listAvatarSessions(201)).rejects.toThrow("1..200");
    expect(() => sdk.cancelMediaJob("job-1",{expectedVersion:0,reasonCode:"bad"},"cancel")).toThrow("expectedVersion");
    await expect(sdk.cancelMediaJob("job-1",{expectedVersion:1,reasonCode:"bad"}," bad ")).rejects.toThrow("Idempotency-Key");
    await expect(sdk.submitMediaJob({...mediaRequest,orgId:"dev-org"} as MediaJobCreateRequest,"key")).rejects.toThrow("禁止字段 orgId");
    expect(post).not.toHaveBeenCalled();
  });
});
