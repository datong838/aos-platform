export type Tenant = { orgId: string; projectId: string };
export type ResourceRef = { resourceType: string; resourceId: string; revision: string; authority: string };
export type ExactRevisionRef = { resourceType: string; resourceId: string; revision: number; contentHash: string };
export type MutableAuthorityRef = { resourceType: string; resourceId: string; version: number };
export type ArtifactRef = { artifactId: string; artifactType: string; revision: string; contentHash: string };
export type ContractBlocker = { code: string; message: string; resourceRef: ExactRevisionRef | null };

export type ContentChannel = "weapp" | "douyin" | "kuaishou" | "wechat_channels" | "xiaohongshu";
export type ContentDeliverableKind = "seed_copy" | "short_video" | "live_plan" | "platform_variant";
export type ContractReadiness = "ready" | "blocked" | "stale" | "unknown";
export type MediaType = "image" | "audio" | "video" | "subtitle" | "font" | "avatar" | "document";
export type MediaUsage = "input" | "output" | "reference";

export type ContentBriefSpec = {
  briefType: "content_campaign";
  objective: string;
  deliverableKinds: ContentDeliverableKind[];
  channelTargets: ContentChannel[];
  productRefs: ResourceRef[];
  audienceRefs: ResourceRef[];
  evidenceBundleRef: ExactRevisionRef;
  factualClaimPolicy: "evidence_only";
  contentConstraints: Record<string, unknown>;
  cutoffAt: string;
};

export type ContentPipelineRefs = {
  briefRef: ExactRevisionRef;
  stageTemplateRef: ExactRevisionRef;
  responsibilityPlanRef: ExactRevisionRef;
  evalContractRef: ExactRevisionRef;
  modelRouteRef: ExactRevisionRef | null;
  runtimePolicyRef: ExactRevisionRef | null;
  capabilityRefs: ExactRevisionRef[];
  toolBindingRefs: MutableAuthorityRef[];
  budgetRef: ExactRevisionRef | null;
  readiness: ContractReadiness;
  blockers: ContractBlocker[];
};

export type MediaAssetRef = {
  artifactRef: ArtifactRef;
  mediaType: MediaType;
  usage: MediaUsage;
  provenanceRef: ExactRevisionRef;
  licenseRef: ExactRevisionRef;
  evidenceBundleRef: ExactRevisionRef;
  withdrawalPolicyRef: ExactRevisionRef;
};

export type ContentDraftProjection = {
  artifactRef: ArtifactRef;
  briefRef: ExactRevisionRef;
  pipeline: ContentPipelineRefs;
  variantKey: string;
  channel: ContentChannel;
  sourceAssets: MediaAssetRef[];
  evidenceBundleRef: ExactRevisionRef;
  evalReportRef: ExactRevisionRef | null;
  reviewIssueRefs: MutableAuthorityRef[];
};

export type PublishProposalPayload = {
  actionType: "publish_content";
  contentDraftRef: ArtifactRef;
  channel: ContentChannel;
  accountRef: MutableAuthorityRef;
  harnessRevisionRef: ExactRevisionRef;
  impactPreviewRef: ExactRevisionRef;
  evidenceBundleRef: ExactRevisionRef;
  requestedMode: "proposal_only";
  scheduledAt: string | null;
};

export type MediaJobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled" | "unknown";
export type MediaJobKind = "tts" | "subtitle" | "video_render" | "transcode" | "thumbnail";
export type MediaJobCreateRequest = {
  taskRunRef: ResourceRef;
  stepRunRef: ResourceRef;
  jobKind: MediaJobKind;
  inputAssets: MediaAssetRef[];
  outputSchemaRef: ResourceRef;
  capabilityRef: ExactRevisionRef;
  capabilityBindingRef: MutableAuthorityRef;
  budgetRef: ExactRevisionRef;
  deadlineAt: string;
};
export type ExpectedVersionCommand = { expectedVersion: number };
export type MediaClaimCommand = ExpectedVersionCommand & {
  executorLeaseRef: ResourceRef;
  heartbeatAt: string;
  leaseExpiresAt: string;
};
export type MediaCompleteCommand = ExpectedVersionCommand & { outputArtifactRefs: ArtifactRef[] };
export type FailureCommand = ExpectedVersionCommand & { reasonCode: string };
export type UnknownCommand = ExpectedVersionCommand & { blockers: ContractBlocker[] };
export type MediaReconcileCommand = ExpectedVersionCommand & {
  reconcileStatus: MediaJobStatus;
  reasonCode?: string;
};
export type MediaJobSnapshot = {
  tenant: Tenant;
  jobId: string;
  requestHash: string;
  taskRunRef: ResourceRef;
  stepRunRef: ResourceRef;
  jobKind: MediaJobKind;
  attempt: number;
  status: MediaJobStatus;
  latestSequence: number;
  executorLeaseRef: ResourceRef | null;
  heartbeatAt: string | null;
  leaseExpiresAt: string | null;
  outputArtifactRefs: ArtifactRef[];
  completionReceiptRef: ExactRevisionRef | null;
  blockers: ContractBlocker[];
  reasonCode: string | null;
  createdAt: string;
  updatedAt: string;
  finishedAt: string | null;
};

export type AvatarSessionStatus = "opening" | "ready" | "live" | "paused" | "closing" | "closed" | "failed" | "killed" | "unknown";
export type AvatarSessionOpenRequest = {
  taskRunRef: ResourceRef;
  stepRunRef: ResourceRef;
  capabilityRef: ExactRevisionRef;
  capabilityBindingRef: MutableAuthorityRef;
  budgetRef: ExactRevisionRef;
  killPolicyRef: ExactRevisionRef;
  livePlanRef: ArtifactRef;
  maxDurationSeconds: number;
};
export type AvatarLiveCommand = ExpectedVersionCommand & {
  engineSessionRef: ExactRevisionRef;
  heartbeatAt: string;
  heartbeatExpiresAt: string;
};
export type AvatarHeartbeatCommand = ExpectedVersionCommand & {
  heartbeatAt: string;
  heartbeatExpiresAt: string;
};
export type AvatarReconcileCommand = ExpectedVersionCommand & {
  reconcileStatus: AvatarSessionStatus;
  reasonCode?: string;
};
export type AvatarSessionSnapshot = {
  tenant: Tenant;
  sessionId: string;
  requestHash: string;
  taskRunRef: ResourceRef;
  stepRunRef: ResourceRef;
  capabilityBindingRef: MutableAuthorityRef;
  budgetRef: ExactRevisionRef;
  killPolicyRef: ExactRevisionRef;
  maxDurationSeconds: number;
  status: AvatarSessionStatus;
  latestSequence: number;
  engineSessionRef: ExactRevisionRef | null;
  humanHeartbeatAt: string | null;
  humanHeartbeatExpiresAt: string | null;
  completionReceiptRef: ExactRevisionRef | null;
  blockers: ContractBlocker[];
  reasonCode: string | null;
  createdAt: string;
  updatedAt: string;
  finishedAt: string | null;
};
