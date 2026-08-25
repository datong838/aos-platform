export type Tenant = { orgId: string; projectId: string };
export type ResourceRef = { resourceType: string; resourceId: string; revision: string | null; authority: string };
export type ExactRevisionRef = { resourceType: string; resourceId: string; revision: number; contentHash: string };
export type ResponsibilityProfile = "LITE" | "STANDARD" | "FULL";
export type ProjectedCostRange = {
  profile: ResponsibilityProfile;
  currency: string;
  componentCount: number;
  priceSnapshotRefs: ExactRevisionRef[];
  lowerAmount: string | null;
  upperAmount: string | null;
  assumptions: string[];
  unknownCodes: string[];
  confidence: "high" | "medium" | "low" | "unknown";
  expiresAt: string;
};
export type ProjectedDurationRange = {
  lowerSeconds: number | null;
  upperSeconds: number | null;
  assumptions: string[];
  unknownCodes: string[];
};
export type ProfileRecommendationRevision = {
  tenant: Tenant;
  recommendationId: string;
  revision: number;
  subjectRef: ExactRevisionRef;
  recommendedProfile: ResponsibilityProfile;
  candidateTemplateRefs: Record<ResponsibilityProfile, ExactRevisionRef>;
  selectedTemplateRef: ExactRevisionRef;
  policyRef: ExactRevisionRef;
  riskLevel: number;
  channelCount: number;
  reasonCodes: string[];
  unknownCodes: string[];
  dependencyRefs: ExactRevisionRef[];
  projectedCostRanges: ProjectedCostRange[];
  projectedDuration: ProjectedDurationRange | null;
  assumptions: string[];
  confidence: "high" | "medium" | "low" | "unknown";
  readiness: "ready" | "blocked" | "stale" | "unknown";
  blockers: string[];
  snapshotHash: string;
  contentHash: string;
  expiresAt: string;
  createdBy: string;
  createdAt: string;
};
export type ProfileRecommendationListResponse = {
  tenant: Tenant;
  items: ProfileRecommendationRevision[];
  count: number;
};
export type ProfileConfirmationReceipt = {
  tenant: Tenant;
  confirmationId: string;
  recommendationId: string;
  recommendationRevision: number;
  recommendationHash: string;
  selectedProfile: ResponsibilityProfile;
  selectedTemplateRef: ExactRevisionRef;
  policyRef: ExactRevisionRef;
  recommendationEtag: string | null;
  idempotencyKey: string | null;
  selectedProjectedCostRanges: ProjectedCostRange[];
  actor: string;
  reason: string;
  contentHash: string;
  createdAt: string;
};
export type ProfileConfirmationListResponse = {
  tenant: Tenant;
  items: ProfileConfirmationReceipt[];
  count: number;
};
export type ConfirmMediaProfileInput = {
  recommendationId: string;
  recommendationRevision: number;
  recommendationHash: string;
  selectedProfile: ResponsibilityProfile;
  reason: string;
};

export type TaskBriefRevision = {
  tenant: Tenant;
  briefId: string;
  taskId: string;
  revision: number;
  version: number;
  briefType: string;
  schemaRef: ResourceRef;
  spec: Record<string, unknown>;
  contentHash: string;
  lifecycle: "draft" | "frozen" | "withdrawn" | "superseded";
  createdBy: string;
  createdAt: string;
};

export type EvidenceBundleRevision = {
  tenant: Tenant;
  bundleId: string;
  revision: number;
  briefRef: ExactRevisionRef;
  subjectRefs: ResourceRef[];
  cutoffAt: string;
  itemRefs: ExactRevisionRef[];
  coverage: "complete" | "partial" | "blocked" | "unknown";
  missing: Record<string, unknown>[];
  conflicts: Record<string, unknown>[];
  uncertainties: Record<string, unknown>[];
  freshness: "fresh" | "stale" | "blocked" | "unknown";
  marking: string[];
  licenseSummary: Record<string, unknown>;
  contentHash: string;
  lifecycle: "frozen";
  createdBy: string;
  createdAt: string;
  revoked: boolean;
  revokeReason: string | null;
};

export type TaskBriefListResponse = { tenant: Tenant; items: TaskBriefRevision[]; count: number };
export type EvidenceBundleListResponse = { tenant: Tenant; items: EvidenceBundleRevision[]; count: number };

export type CreateTaskBriefInput = {
  taskId: string;
  briefType: string;
  schemaRef: ResourceRef;
  spec: Record<string, unknown>;
};

export type ContractLifecycle = "draft" | "frozen" | "withdrawn" | "superseded";
export type ContractReadiness = "ready" | "blocked" | "stale" | "unknown";
export type ContractCoverage = "complete" | "partial" | "blocked" | "unknown";
export type AssigneeKind = "agent_instance" | "human_principal" | "tool_binding" | "provider_capability_binding";

export type ContractBlocker = {
  code: string;
  message: string;
  resourceRef: ExactRevisionRef | null;
};

export type CreateEvalContractInput = {
  suiteRef: ExactRevisionRef;
  publicationRef: ExactRevisionRef | null;
  releaseGateRef: ExactRevisionRef | null;
  artifactSchemaRef: ResourceRef;
  severityThresholds: Record<string, number>;
  gatePolicy: Record<string, unknown>;
  returnMapping: Record<string, string>;
  overridePolicy: Record<string, unknown>;
};

export type ReviseEvalContractInput = CreateEvalContractInput & { expectedVersion: number };

export type EvalContractRevision = CreateEvalContractInput & {
  tenant: Tenant;
  contractId: string;
  revision: number;
  version: number;
  contentHash: string;
  lifecycle: ContractLifecycle;
  readiness: ContractReadiness;
  blockers: ContractBlocker[];
  createdBy: string;
  createdAt: string;
};

export type EvalContractListResponse = { tenant: Tenant; items: EvalContractRevision[]; count: number };
export type EvalContractDiffChange = { field: string; label: string; before: unknown; after: unknown; impact: string };
export type EvalContractDiff = {
  tenant: Tenant;
  contractId: string;
  fromRevision: number;
  toRevision: number;
  fromContentHash: string;
  toContentHash: string;
  changes: EvalContractDiffChange[];
  changeCount: number;
  summary: string;
};

export type AssigneeRef = { kind: AssigneeKind; resourceId: string; version: number };
export type ResponsibilitySlot = {
  slotId: string;
  responsibilityType: string;
  requiredCapabilityIds: string[];
  inputSchemaRef: ResourceRef;
  outputSchemaRef: ResourceRef;
  gateRefs: ExactRevisionRef[];
  returnStage: string;
  assignee: AssigneeRef;
};
export type MergeDecision = {
  sourceSlotIds: string[];
  targetSlotId: string;
  reason: string;
  mergedResponsibilityTypes: string[];
};
export type CreateResponsibilityPlanInput = {
  profile: string;
  templateRef: ExactRevisionRef;
  slots: ResponsibilitySlot[];
  mergeDecisions: MergeDecision[];
  profileRecommendationRef?: ExactRevisionRef | null;
  profileConfirmationId?: string | null;
  mergePolicyRef?: ExactRevisionRef | null;
  mergeDecisionReceiptIds?: string[];
};
export type ReviseResponsibilityPlanInput = CreateResponsibilityPlanInput & { expectedVersion: number };
export type ResponsibilityPlanRevision = CreateResponsibilityPlanInput & {
  tenant: Tenant;
  planId: string;
  revision: number;
  version: number;
  coverage: ContractCoverage;
  uncoveredSlots: string[];
  contentHash: string;
  lifecycle: ContractLifecycle;
  readiness: ContractReadiness;
  blockers: ContractBlocker[];
  createdBy: string;
  createdAt: string;
};
export type ResponsibilityPlanListResponse = { tenant: Tenant; items: ResponsibilityPlanRevision[]; count: number };

export type StageApplicability = {
  kind: "always" | "profile_in";
  profiles: string[];
};
export type StageDefinition = {
  stageId: string;
  title: string;
  dependsOn: string[];
  applicability: StageApplicability;
  requiredSlotIds: string[];
  inputSchemaRef: ResourceRef;
  outputSchemaRef: ResourceRef;
  gateRefs: ExactRevisionRef[];
  checkpointPolicy: Record<string, unknown>;
  retryPolicy: Record<string, unknown>;
  compensationPolicy: Record<string, unknown>;
};
export type CreateStageTemplateInput = {
  profile: string;
  sourceBundleRef: ExactRevisionRef;
  stages: StageDefinition[];
};
export type ReviseStageTemplateInput = CreateStageTemplateInput & { expectedVersion: number };
export type StageTemplateRevision = CreateStageTemplateInput & {
  tenant: Tenant;
  templateId: string;
  revision: number;
  version: number;
  contentHash: string;
  lifecycle: ContractLifecycle;
  sealedBy: string | null;
  sealedAt: string | null;
  sealHash: string | null;
  readiness: ContractReadiness;
  blockers: ContractBlocker[];
  createdBy: string;
  createdAt: string;
};
export type StageTemplateListResponse = { tenant: Tenant; items: StageTemplateRevision[]; count: number };
export type CompileStageTemplateInput = {
  taskId: string;
  expectedTaskVersion: number;
  templateRevision: number;
  templateContentHash: string;
  responsibilityPlanRef: ExactRevisionRef;
  productionContextRef: ExactRevisionRef;
  profile: string;
  briefRef?: ExactRevisionRef | null;
  evidenceBundleRef?: ExactRevisionRef | null;
  evalContractRef?: ExactRevisionRef | null;
  profileRecommendationRef?: ExactRevisionRef | null;
  profileConfirmationId?: string | null;
  mergePolicyRef?: ExactRevisionRef | null;
  capabilityRefs?: Record<string, ExactRevisionRef>;
};
export type StageCompilationResult = {
  tenant: Tenant;
  taskId: string;
  templateRef: ExactRevisionRef;
  responsibilityPlanRef: ExactRevisionRef;
  productionContextRef: ExactRevisionRef;
  planRef: ExactRevisionRef;
  compilerVersion: string;
  inputHash: string;
  compilationHash: string;
  normalizedStageIds: string[];
  applicableStageIds: string[];
  notApplicableStageIds: string[];
  createdAt: string;
};

export type ExactArtifactRef = { artifactId: string; contentHash: string };
export type ArtifactRelationType = "family_member" | "variant_of" | "supersedes" | "derived_from";
export type CreateArtifactRelationInput = {
  relationType: ArtifactRelationType;
  fromArtifact: ExactArtifactRef;
  toArtifact: ExactArtifactRef;
  reason: string;
};
export type ArtifactRelation = CreateArtifactRelationInput & {
  tenant: Tenant;
  relationId: string;
  createdBy: string;
  createdAt: string;
};
export type ArtifactRelationListResponse = { tenant: Tenant; items: ArtifactRelation[]; count: number };
export type ArtifactFamilyRole = "family_manifest" | "preview" | "draft" | "master" | "variant";
export type ArtifactFamilyCandidateStatus = "current" | "conflict" | "selected";
export type ArtifactFamilyMember = {
  artifactRef: ExactArtifactRef;
  familyRevision: number;
  role: ArtifactFamilyRole;
  artifactType: string;
  profile: string;
  platform: string;
  renditionSpecHash: string;
  lineageRefs: ExactRevisionRef[];
  masterRef: ExactArtifactRef | null;
  supersedesRef: ExactArtifactRef | null;
  approvalStatus: "not_approved" | "approved" | "unknown";
  executionStatus: "not_executed" | "executed" | "unknown";
  createdAt: string;
};
export type ArtifactFamilyCandidateGroup = {
  selectionKey: string;
  role: ArtifactFamilyRole;
  artifactType: string;
  profile: string;
  platform: string;
  renditionSpecHash: string;
  candidates: ExactArtifactRef[];
  selectedRef: ExactArtifactRef | null;
  status: ArtifactFamilyCandidateStatus;
};
export type ArtifactFamilySelectionDecision = {
  familyId: string;
  selectionKey: string;
  revision: number;
  expectedFamilyVersion: number;
  selectedRef: ExactArtifactRef;
  candidateRefs: ExactArtifactRef[];
  candidateSetHash: string;
  policyRef: ExactRevisionRef;
  reason: string;
  decisionHash: string;
  actor: string;
  createdAt: string;
};
export type ArtifactFamily = {
  tenant: Tenant;
  familyId: string;
  version: number;
  currentRevision: number;
  manifestRef: ExactArtifactRef;
  members: ArtifactFamilyMember[];
  candidateGroups: ArtifactFamilyCandidateGroup[];
  selectionDecisions: ArtifactFamilySelectionDecision[];
  topologyStatus: "empty" | "current" | "conflict";
  updatedAt: string;
};
export type ArtifactFamilyListResponse = { tenant: Tenant; items: ArtifactFamily[]; count: number };

export type ReviewSeverity = "info" | "warning" | "error" | "critical";
export type ReviewIssueStatus = "open" | "resolved" | "returned" | "superseded";
export type CreateReviewIssueInput = {
  ruleRef: ExactRevisionRef;
  severity: ReviewSeverity;
  artifactRef: ExactArtifactRef;
  evalReportRef: ExactRevisionRef;
  location: Record<string, unknown>;
  evidenceRefs: ExactRevisionRef[];
  suggestedFix: string;
  returnStage: string;
};
export type ReviewIssue = CreateReviewIssueInput & {
  tenant: Tenant;
  issueId: string;
  status: ReviewIssueStatus;
  version: number;
  createdBy: string;
  createdAt: string;
  updatedBy: string;
  updatedAt: string;
};
export type ReviewIssueListResponse = { tenant: Tenant; items: ReviewIssue[]; count: number };
export type ResolveReviewIssueInput = { expectedVersion: number; reason: string; resolutionRefs: ExactRevisionRef[] };
export type ReturnReviewIssueInput = {
  expectedVersion: number;
  runId: string;
  targetStage: string;
  reason: string;
  attemptIdempotencyKey: string;
};
export type ReturnDecision = {
  tenant: Tenant;
  decisionId: string;
  issueId: string;
  issueVersion: number;
  runId: string;
  stepKey: string;
  stepRunId: string;
  attempt: number;
  attemptIdempotencyKey: string;
  reason: string;
  impactDecisions: { stepKey: string; action: "invalidate" | "reuse"; reason: string }[];
  impactReadiness: "exact" | "legacy_unavailable";
  decisionHash: string;
  actor: string;
  createdAt: string;
};

export type MutableAuthorityRef = { resourceType: string; resourceId: string; version: number };
export type ActionProposalExactRef = { proposalId: string; version: number; proposalHash: string };
export type ImpactQuality = "measured" | "estimated" | "unknown";
export type ImpactDimension = {
  quality: ImpactQuality;
  value: unknown | null;
  sourceRefs: ResourceRef[];
  cutoffAt: string | null;
  details: Record<string, unknown>;
};
export type ImpactAssessment = {
  objectScope: ImpactDimension;
  channelScope: ImpactDimension;
  cost: ImpactDimension;
  budget: ImpactDimension;
  risks: ImpactDimension;
  reversibility: ImpactDimension;
  approvalChain: ImpactDimension;
  rateCapacityKill: ImpactDimension;
};
export type CreateImpactPreviewInput = {
  taskId: string;
  planRef: ExactRevisionRef;
  productionContextRef: ExactRevisionRef | null;
  briefRef: ExactRevisionRef;
  evidenceBundleRef: ExactRevisionRef;
  evalContractRef: ExactRevisionRef;
  responsibilityPlanRef: ExactRevisionRef;
  stageTemplateRef: ExactRevisionRef;
  modelRouteRef: ExactRevisionRef | null;
  runtimePolicyRef: ExactRevisionRef | null;
  bindingRefs: MutableAuthorityRef[];
  capabilityRef: ExactRevisionRef | null;
  accountRef: MutableAuthorityRef | null;
  impact: ImpactAssessment;
  expiresAt: string;
};
export type ReviseImpactPreviewInput = CreateImpactPreviewInput & { expectedVersion: number };
export type ImpactPreviewRevision = CreateImpactPreviewInput & {
  tenant: Tenant;
  previewId: string;
  revision: number;
  version: number;
  contentHash: string;
  dependencySnapshotHash: string;
  actionBindingHash: string;
  lifecycle: ContractLifecycle;
  readiness: ContractReadiness;
  blockers: ContractBlocker[];
  frozenBy: string | null;
  frozenAt: string | null;
  createdBy: string;
  createdAt: string;
};
export type ImpactPreviewListResponse = { tenant: Tenant; items: ImpactPreviewRevision[]; count: number };

export type ProductionContextRevision = {
  tenant: Tenant;
  contextId: string;
  revision: number;
  taskId: string;
  briefRef: ExactRevisionRef;
  evidenceBundleRef: ExactRevisionRef;
  evalContractRef: ExactRevisionRef;
  responsibilityPlanRef: ExactRevisionRef;
  productionProfileRef: ExactRevisionRef | null;
  preparationRef: ExactRevisionRef | null;
  profile: string;
  dependencySnapshot: Record<string, unknown>[];
  dependencySnapshotHash: string;
  contentHash: string;
  lifecycle: ContractLifecycle;
  readiness: ContractReadiness;
  blockers: ContractBlocker[];
  createdBy: string;
  createdAt: string;
};
export type ProductionContextListResponse = { tenant: Tenant; items: ProductionContextRevision[]; count: number };

export type ProductionStartInput = {
  taskId: string;
  expectedTaskVersion: number;
  productionContextRef: ExactRevisionRef;
  planRef: ExactRevisionRef;
  previewRef: ExactRevisionRef;
  actionProposalRef: ActionProposalExactRef;
  logicGraphId: string;
  logicRevision: number;
  logicGraphHash: string;
};
export type ProductionStartStatus = "started" | "blocked" | "stale" | "unknown";
export type ProductionStartDecision = {
  tenant: Tenant;
  decisionId: string;
  status: ProductionStartStatus;
  taskId: string;
  productionContextRef: ExactRevisionRef | null;
  planRef: ExactRevisionRef;
  previewRef: ExactRevisionRef;
  actionProposalRef: ActionProposalExactRef;
  dependencySnapshotHash: string;
  blockers: ContractBlocker[];
  taskRunRef: ResourceRef | null;
  createdBy: string;
  createdAt: string;
};
export type ProductionStartDecisionListResponse = { tenant: Tenant; items: ProductionStartDecision[]; count: number };
