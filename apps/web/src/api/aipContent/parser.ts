import type {
  ArtifactRef,
  AvatarSessionSnapshot,
  AvatarSessionStatus,
  ContentBriefSpec,
  ContentChannel,
  ContentDeliverableKind,
  ContentDraftProjection,
  ContentPipelineRefs,
  ContractBlocker,
  ContractReadiness,
  ExactRevisionRef,
  MediaAssetRef,
  MediaJobKind,
  MediaJobSnapshot,
  MediaJobStatus,
  MediaType,
  MediaUsage,
  MutableAuthorityRef,
  PublishProposalPayload,
  ResourceRef,
  Tenant,
} from "./contracts";

function object(value: unknown, label: string, allowed: readonly string[]): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} 必须是对象`);
  const result = value as Record<string, unknown>;
  const extra = Object.keys(result).filter((key) => !allowed.includes(key));
  if (extra.length) throw new Error(`${label} 包含未知字段: ${extra.join(",")}`);
  return result;
}
function string(value: unknown, label: string): string { if (typeof value !== "string" || !value.trim()) throw new Error(`${label} 必须是非空字符串`); return value; }
function integer(value: unknown, label: string, minimum = 0): number { if (typeof value !== "number" || !Number.isInteger(value) || value < minimum) throw new Error(`${label} 必须是大于等于 ${minimum} 的整数`); return value; }
function array(value: unknown, label: string): unknown[] { if (!Array.isArray(value)) throw new Error(`${label} 必须是数组`); return value; }
function record(value: unknown, label: string): Record<string, unknown> { if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} 必须是对象`); return value as Record<string, unknown>; }
function nullable<T>(value: unknown, parse: (item: unknown) => T): T | null { return value === null ? null : parse(value); }
function enumValue<T extends string>(value: unknown, label: string, values: readonly T[]): T { const result=string(value,label) as T; if(!values.includes(result)) throw new Error(`${label} 非法`); return result; }
function sha(value: unknown, label: string): string { const result=string(value,label); if(!/^[0-9a-f]{64}$/.test(result)) throw new Error(`${label} 非 SHA-256`); return result; }
function date(value: unknown, label: string): string { const result=string(value,label); if(Number.isNaN(Date.parse(result))) throw new Error(`${label} 非合法时间`); return result; }

const channels = ["weapp","douyin","kuaishou","wechat_channels","xiaohongshu"] as const;
const deliverables = ["seed_copy","short_video","live_plan","platform_variant"] as const;
const readinessValues = ["ready","blocked","stale","unknown"] as const;
const mediaTypes = ["image","audio","video","subtitle","font","avatar","document"] as const;
const mediaUsages = ["input","output","reference"] as const;

function tenant(value: unknown): Tenant { const raw=object(value,"tenant",["orgId","projectId"]); return {orgId:string(raw.orgId,"tenant.orgId"),projectId:string(raw.projectId,"tenant.projectId")}; }
function resource(value: unknown, label: string): ResourceRef { const raw=object(value,label,["resourceType","resourceId","revision","authority"]); return {resourceType:string(raw.resourceType,`${label}.resourceType`),resourceId:string(raw.resourceId,`${label}.resourceId`),revision:string(raw.revision,`${label}.revision`),authority:string(raw.authority,`${label}.authority`)}; }
function exact(value: unknown, label: string): ExactRevisionRef { const raw=object(value,label,["resourceType","resourceId","revision","contentHash"]); return {resourceType:string(raw.resourceType,`${label}.resourceType`),resourceId:string(raw.resourceId,`${label}.resourceId`),revision:integer(raw.revision,`${label}.revision`,1),contentHash:sha(raw.contentHash,`${label}.contentHash`)}; }
function mutable(value: unknown, label: string): MutableAuthorityRef { const raw=object(value,label,["resourceType","resourceId","version"]); return {resourceType:string(raw.resourceType,`${label}.resourceType`),resourceId:string(raw.resourceId,`${label}.resourceId`),version:integer(raw.version,`${label}.version`,1)}; }
function artifact(value: unknown, label: string): ArtifactRef { const raw=object(value,label,["artifactId","artifactType","revision","contentHash"]); return {artifactId:string(raw.artifactId,`${label}.artifactId`),artifactType:string(raw.artifactType,`${label}.artifactType`),revision:string(raw.revision,`${label}.revision`),contentHash:sha(raw.contentHash,`${label}.contentHash`)}; }
function blocker(value: unknown, index: number): ContractBlocker { const label=`blockers[${index}]`,raw=object(value,label,["code","message","resourceRef"]); return {code:string(raw.code,`${label}.code`),message:string(raw.message,`${label}.message`),resourceRef:nullable(raw.resourceRef,(item)=>exact(item,`${label}.resourceRef`))}; }
function exactKind(value: unknown, label: string, kind: string): ExactRevisionRef { const ref=exact(value,label); if(ref.resourceType!==kind) throw new Error(`${label} 必须引用 ${kind}`); return ref; }
function mutableKind(value: unknown, label: string, kind: string): MutableAuthorityRef { const ref=mutable(value,label); if(ref.resourceType!==kind) throw new Error(`${label} 必须引用 ${kind}`); return ref; }
function resourceKind(value: unknown, label: string, kind: string): ResourceRef { const ref=resource(value,label); if(ref.resourceType!==kind) throw new Error(`${label} 必须引用 ${kind}`); return ref; }

export function parseContentBrief(value: unknown): ContentBriefSpec {
  const raw=object(value,"ContentBriefSpec",["briefType","objective","deliverableKinds","channelTargets","productRefs","audienceRefs","evidenceBundleRef","factualClaimPolicy","contentConstraints","cutoffAt"]);
  if(raw.briefType!=="content_campaign"||raw.factualClaimPolicy!=="evidence_only") throw new Error("ContentBrief 固定策略非法");
  const productRefs=array(raw.productRefs,"productRefs").map((item,index)=>resource(item,`productRefs[${index}]`)); if(!productRefs.length) throw new Error("productRefs 不能为空");
  const deliverableKinds=array(raw.deliverableKinds,"deliverableKinds").map((item,index)=>enumValue<ContentDeliverableKind>(item,`deliverableKinds[${index}]`,deliverables));
  const channelTargets=array(raw.channelTargets,"channelTargets").map((item,index)=>enumValue<ContentChannel>(item,`channelTargets[${index}]`,channels));
  if(!deliverableKinds.length||new Set(deliverableKinds).size!==deliverableKinds.length) throw new Error("deliverableKinds 必须非空且唯一");
  if(!channelTargets.length||new Set(channelTargets).size!==channelTargets.length) throw new Error("channelTargets 必须非空且唯一");
  return {briefType:"content_campaign",objective:string(raw.objective,"objective"),deliverableKinds,channelTargets,productRefs,audienceRefs:array(raw.audienceRefs,"audienceRefs").map((item,index)=>resource(item,`audienceRefs[${index}]`)),evidenceBundleRef:exactKind(raw.evidenceBundleRef,"evidenceBundleRef","EvidenceBundleRevision"),factualClaimPolicy:"evidence_only",contentConstraints:record(raw.contentConstraints,"contentConstraints"),cutoffAt:date(raw.cutoffAt,"cutoffAt")};
}

export function parseContentPipeline(value: unknown): ContentPipelineRefs {
  const raw=object(value,"ContentPipelineRefs",["briefRef","stageTemplateRef","responsibilityPlanRef","evalContractRef","modelRouteRef","runtimePolicyRef","capabilityRefs","toolBindingRefs","budgetRef","readiness","blockers"]);
  const readiness=enumValue<ContractReadiness>(raw.readiness,"readiness",readinessValues), blockers=array(raw.blockers,"blockers").map(blocker);
  if((readiness==="ready")!==(!blockers.length)) throw new Error("pipeline readiness 与 blockers 不一致");
  const modelRouteRef=nullable(raw.modelRouteRef,(item)=>exactKind(item,"modelRouteRef","ModelRouteRevision"));
  const runtimePolicyRef=nullable(raw.runtimePolicyRef,(item)=>exactKind(item,"runtimePolicyRef","RuntimePolicyRevision"));
  if((modelRouteRef===null)!==(runtimePolicyRef===null)) throw new Error("modelRouteRef/runtimePolicyRef 必须成对");
  const capabilityRefs=array(raw.capabilityRefs,"capabilityRefs").map((item,index)=>exactKind(item,`capabilityRefs[${index}]`,"CapabilityRevision")),toolBindingRefs=array(raw.toolBindingRefs,"toolBindingRefs").map((item,index)=>mutableKind(item,`toolBindingRefs[${index}]`,"ToolBinding")),budgetRef=nullable(raw.budgetRef,(item)=>exactKind(item,"budgetRef","BudgetRevision"));
  if(readiness==="ready"&&(!modelRouteRef||!capabilityRefs.length||!budgetRef)) throw new Error("ready pipeline 缺少 route/capability/budget");
  return {briefRef:exactKind(raw.briefRef,"briefRef","TaskBriefRevision"),stageTemplateRef:exactKind(raw.stageTemplateRef,"stageTemplateRef","StageTemplateRevision"),responsibilityPlanRef:exactKind(raw.responsibilityPlanRef,"responsibilityPlanRef","ResponsibilityPlanRevision"),evalContractRef:exactKind(raw.evalContractRef,"evalContractRef","EvalContractRevision"),modelRouteRef,runtimePolicyRef,capabilityRefs,toolBindingRefs,budgetRef,readiness,blockers};
}

function mediaAsset(value: unknown, label: string): MediaAssetRef {
  const raw=object(value,label,["artifactRef","mediaType","usage","provenanceRef","licenseRef","evidenceBundleRef","withdrawalPolicyRef"]);
  const artifactRef=artifact(raw.artifactRef,`${label}.artifactRef`),mediaType=enumValue<MediaType>(raw.mediaType,`${label}.mediaType`,mediaTypes); if(artifactRef.artifactType!==mediaType) throw new Error(`${label}.artifactRef 与 mediaType 不一致`);
  return {artifactRef,mediaType,usage:enumValue<MediaUsage>(raw.usage,`${label}.usage`,mediaUsages),provenanceRef:exactKind(raw.provenanceRef,`${label}.provenanceRef`,"AssetProvenanceRevision"),licenseRef:exactKind(raw.licenseRef,`${label}.licenseRef`,"AssetLicenseRevision"),evidenceBundleRef:exactKind(raw.evidenceBundleRef,`${label}.evidenceBundleRef`,"EvidenceBundleRevision"),withdrawalPolicyRef:exactKind(raw.withdrawalPolicyRef,`${label}.withdrawalPolicyRef`,"AssetWithdrawalPolicyRevision")};
}

export function parseContentDraft(value: unknown): ContentDraftProjection {
  const raw=object(value,"ContentDraftProjection",["artifactRef","briefRef","pipeline","variantKey","channel","sourceAssets","evidenceBundleRef","evalReportRef","reviewIssueRefs"]),artifactRef=artifact(raw.artifactRef,"artifactRef"); if(artifactRef.artifactType!=="content_draft") throw new Error("artifactRef 必须是 content_draft");
  return {artifactRef,briefRef:exactKind(raw.briefRef,"briefRef","TaskBriefRevision"),pipeline:parseContentPipeline(raw.pipeline),variantKey:string(raw.variantKey,"variantKey"),channel:enumValue<ContentChannel>(raw.channel,"channel",channels),sourceAssets:array(raw.sourceAssets,"sourceAssets").map((item,index)=>mediaAsset(item,`sourceAssets[${index}]`)),evidenceBundleRef:exactKind(raw.evidenceBundleRef,"evidenceBundleRef","EvidenceBundleRevision"),evalReportRef:nullable(raw.evalReportRef,(item)=>exactKind(item,"evalReportRef","EvalReportRevision")),reviewIssueRefs:array(raw.reviewIssueRefs,"reviewIssueRefs").map((item,index)=>mutableKind(item,`reviewIssueRefs[${index}]`,"ReviewIssue"))};
}

export function parsePublishProposal(value: unknown): PublishProposalPayload {
  const raw=object(value,"PublishProposalPayload",["actionType","contentDraftRef","channel","accountRef","harnessRevisionRef","impactPreviewRef","evidenceBundleRef","requestedMode","scheduledAt"]),contentDraftRef=artifact(raw.contentDraftRef,"contentDraftRef");
  if(raw.actionType!=="publish_content"||raw.requestedMode!=="proposal_only"||contentDraftRef.artifactType!=="content_draft") throw new Error("PublishProposal 只能是 content draft proposal_only");
  return {actionType:"publish_content",contentDraftRef,channel:enumValue<ContentChannel>(raw.channel,"channel",channels),accountRef:mutableKind(raw.accountRef,"accountRef","PlatformAccountBinding"),harnessRevisionRef:exactKind(raw.harnessRevisionRef,"harnessRevisionRef","PlatformHarnessRevision"),impactPreviewRef:exactKind(raw.impactPreviewRef,"impactPreviewRef","ImpactPreviewRevision"),evidenceBundleRef:exactKind(raw.evidenceBundleRef,"evidenceBundleRef","EvidenceBundleRevision"),requestedMode:"proposal_only",scheduledAt:raw.scheduledAt===null?null:date(raw.scheduledAt,"scheduledAt")};
}

export function parseMediaJobSnapshot(value: unknown): MediaJobSnapshot {
  const keys=["tenant","jobId","requestHash","taskRunRef","stepRunRef","jobKind","attempt","status","latestSequence","executorLeaseRef","heartbeatAt","leaseExpiresAt","outputArtifactRefs","completionReceiptRef","blockers","reasonCode","createdAt","updatedAt","finishedAt"] as const,raw=object(value,"MediaJobSnapshot",keys),status=enumValue<MediaJobStatus>(raw.status,"status",["queued","running","succeeded","failed","cancelled","unknown"]),executorLeaseRef=nullable(raw.executorLeaseRef,(item)=>resource(item,"executorLeaseRef")),heartbeatAt=raw.heartbeatAt===null?null:date(raw.heartbeatAt,"heartbeatAt"),leaseExpiresAt=raw.leaseExpiresAt===null?null:date(raw.leaseExpiresAt,"leaseExpiresAt"),outputs=array(raw.outputArtifactRefs,"outputArtifactRefs").map((item,index)=>artifact(item,`outputArtifactRefs[${index}]`)),completionReceiptRef=nullable(raw.completionReceiptRef,(item)=>exactKind(item,"completionReceiptRef","MediaJobReceipt")),blockers=array(raw.blockers,"blockers").map(blocker),finishedAt=raw.finishedAt===null?null:date(raw.finishedAt,"finishedAt"),reasonCode=raw.reasonCode===null?null:string(raw.reasonCode,"reasonCode");
  if(status==="running"&&(!executorLeaseRef||!heartbeatAt||!leaseExpiresAt)) throw new Error("running MediaJob 缺少 lease/heartbeat"); if(status!=="running"&&(executorLeaseRef||heartbeatAt||leaseExpiresAt)) throw new Error("非 running MediaJob 不能携带 lease"); if(status==="succeeded"&&(!outputs.length||!completionReceiptRef||!finishedAt||blockers.length||reasonCode)) throw new Error("succeeded MediaJob 证据不完整"); if(status!=="succeeded"&&outputs.length) throw new Error("非 succeeded MediaJob 不能携带产物"); if(status==="unknown"&&(!blockers.length||finishedAt)) throw new Error("unknown MediaJob 状态非法");
  return {tenant:tenant(raw.tenant),jobId:string(raw.jobId,"jobId"),requestHash:sha(raw.requestHash,"requestHash"),taskRunRef:resourceKind(raw.taskRunRef,"taskRunRef","TaskRun"),stepRunRef:resourceKind(raw.stepRunRef,"stepRunRef","StepRun"),jobKind:enumValue<MediaJobKind>(raw.jobKind,"jobKind",["tts","subtitle","video_render","transcode","thumbnail"]),attempt:integer(raw.attempt,"attempt",1),status,latestSequence:integer(raw.latestSequence,"latestSequence",1),executorLeaseRef,heartbeatAt,leaseExpiresAt,outputArtifactRefs:outputs,completionReceiptRef,blockers,reasonCode,createdAt:date(raw.createdAt,"createdAt"),updatedAt:date(raw.updatedAt,"updatedAt"),finishedAt};
}

export function parseAvatarSessionSnapshot(value: unknown): AvatarSessionSnapshot {
  const keys=["tenant","sessionId","requestHash","taskRunRef","stepRunRef","capabilityBindingRef","budgetRef","killPolicyRef","maxDurationSeconds","status","latestSequence","engineSessionRef","humanHeartbeatAt","humanHeartbeatExpiresAt","completionReceiptRef","blockers","reasonCode","createdAt","updatedAt","finishedAt"] as const,raw=object(value,"AvatarSessionSnapshot",keys),status=enumValue<AvatarSessionStatus>(raw.status,"status",["opening","ready","live","paused","closing","closed","failed","killed","unknown"]),engineSessionRef=nullable(raw.engineSessionRef,(item)=>exactKind(item,"engineSessionRef","OpaqueAvatarEngineSessionRef")),humanHeartbeatAt=raw.humanHeartbeatAt===null?null:date(raw.humanHeartbeatAt,"humanHeartbeatAt"),humanHeartbeatExpiresAt=raw.humanHeartbeatExpiresAt===null?null:date(raw.humanHeartbeatExpiresAt,"humanHeartbeatExpiresAt"),completionReceiptRef=nullable(raw.completionReceiptRef,(item)=>exact(item,"completionReceiptRef")),blockers=array(raw.blockers,"blockers").map(blocker),reasonCode=raw.reasonCode===null?null:string(raw.reasonCode,"reasonCode"),finishedAt=raw.finishedAt===null?null:date(raw.finishedAt,"finishedAt");
  if(status==="live"&&(!engineSessionRef||!humanHeartbeatAt||!humanHeartbeatExpiresAt)) throw new Error("live AvatarSession 缺少引擎或人工心跳"); if(status!=="live"&&(humanHeartbeatAt||humanHeartbeatExpiresAt)) throw new Error("非 live AvatarSession 不能携带人工心跳"); const terminal=["closed","failed","killed"].includes(status); if(terminal!==Boolean(finishedAt&&completionReceiptRef)) throw new Error("AvatarSession 终态证据不一致"); if(status==="unknown"&&!blockers.length) throw new Error("unknown AvatarSession 缺少 blocker");
  return {tenant:tenant(raw.tenant),sessionId:string(raw.sessionId,"sessionId"),requestHash:sha(raw.requestHash,"requestHash"),taskRunRef:resourceKind(raw.taskRunRef,"taskRunRef","TaskRun"),stepRunRef:resourceKind(raw.stepRunRef,"stepRunRef","StepRun"),capabilityBindingRef:mutableKind(raw.capabilityBindingRef,"capabilityBindingRef","CapabilityBinding"),budgetRef:exact(raw.budgetRef,"budgetRef"),killPolicyRef:exact(raw.killPolicyRef,"killPolicyRef"),maxDurationSeconds:integer(raw.maxDurationSeconds,"maxDurationSeconds",1),status,latestSequence:integer(raw.latestSequence,"latestSequence",1),engineSessionRef,humanHeartbeatAt,humanHeartbeatExpiresAt,completionReceiptRef,blockers,reasonCode,createdAt:date(raw.createdAt,"createdAt"),updatedAt:date(raw.updatedAt,"updatedAt"),finishedAt};
}
