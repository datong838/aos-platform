export type Tenant = { orgId: string; projectId: string };
export type AssetRef = { assetType: string; assetId: string; revision: number; contentHash: string };
export type ResourceRef = { resourceType: string; resourceId: string; revision: string | null; authority: string; contentHash?: string };

export type AgentTemplate = {
  templateId: string;
  revision: number;
  displayName: string;
  roleKey: string;
  lifecycle: "published";
  sourceRef: ResourceRef;
  sourceLicense: string;
  manifest: { logicIds: string[]; responsibility: string; runtimeReadiness: string; blockers: string[] };
  contentHash: string;
};

export type AgentInstance = {
  tenant: Tenant;
  instanceId: string;
  instanceRef: AssetRef;
  template: AssetRef;
  status: "provisioning" | "active" | "suspended" | "deleted";
  overlay: { displayName: string | null; allowedCapabilityIds: string[] };
  version: number;
  updatedAt: string;
};

export type SkillTemplate = {
  skillId: string;
  revision: number;
  canonicalLogicId: string;
  lifecycle: "evaluated" | "published";
  requiredCapabilities: string[];
  riskLevel: string;
  contentHash: string;
  logicRevisionRef: AssetRef | null;
};

export type AgentCatalogItem = {
  template: AgentTemplate;
  instance: AgentInstance | null;
  skills: SkillTemplate[];
  requiredCapabilityIds: string[];
  runtimeReadiness: "blocked" | "runnable";
  blockers: string[];
};

export type AgentCatalogResponse = {
  tenant: Tenant;
  items: AgentCatalogItem[];
  stats: { definitionCount: number; installedCount: number; runnableCount: number; skillDefinitionCount: number; capabilityDefinitionCount: number };
};

export type AgentInstanceListResponse = { tenant: Tenant; items: AgentInstance[]; count: number };
export type AgentInstanceActivationResponse = { tenant: Tenant; instance: AgentInstance; capabilityBindingIds: string[]; receipt: RegistryReceipt };

export type CapabilityRevision = {
  capabilityId: string;
  revision: number;
  displayName: string;
  lifecycle: "published";
  aliases: string[];
  inputSchemaRef?: AssetRef | null;
  outputSchemaRef?: AssetRef | null;
  riskLevel: string;
  requiredDataRefs?: AssetRef[];
  requiredToolRefs?: AssetRef[];
  requiredCapabilityRefs?: AssetRef[];
  evalPackRef?: AssetRef | null;
  readiness: "available" | "degraded" | "disabled" | "blocked" | "unknown";
  readinessReasons: string[];
  contentHash: string;
};

export type CapabilityCatalogResponse = { tenant: Tenant; items: CapabilityRevision[]; count: number; availableCount: number };
export type AgentInstallResponse = { tenant: Tenant; solutionPackId: "solution.ecommerce.growth"; solutionPackVersion: string; status: "installed" | "partial"; createdCount: number; existingCount: number; runnableCount: 0; items: Array<{ instance: AgentInstance; disposition: "created" | "existing" }> };

export type BindingReadiness = "available" | "degraded" | "disabled" | "blocked" | "unknown";
export type BindingHealth = "unknown" | "healthy" | "degraded" | "unavailable" | "revoked";
export type BindingStatus = "provisioning" | "active" | "suspended" | "revoked";

export type OperationalBindingDependencies = {
  providerRef: AssetRef | null;
  modelRouteRef: AssetRef | null;
  runtimePolicyRef: AssetRef | null;
  evalGateRef: AssetRef | null;
  evalContractRef: AssetRef | null;
  licenseEvidenceRefs: ResourceRef[];
  dataDependencyRefs: AssetRef[];
  toolDependencyRefs: AssetRef[];
  budgetPolicyRef: AssetRef | null;
  allowDegraded: boolean;
};

export type CapabilityBinding = {
  tenant: Tenant;
  bindingId: string;
  capability: AssetRef;
  secretRef: string;
  health: BindingHealth;
  networkPolicyRevision: string;
  quotaPolicyRevision: string;
  timeoutMs: number;
  maxConcurrency: number;
  dependencies: OperationalBindingDependencies;
  operationalReadiness: BindingReadiness;
  readinessReasons: string[];
  dependencySnapshotHash: string | null;
  lastEvaluatedAt: string | null;
  readinessExpiresAt: string | null;
  status: BindingStatus;
  version: number;
  observedAt: string | null;
  createdAt: string;
  updatedAt: string;
};

export type SkillBinding = {
  tenant: Tenant;
  bindingId: string;
  instanceId: string;
  skill: AssetRef;
  capabilityBindingIds: string[];
  budgetPolicyRef: AssetRef;
  dependencies: OperationalBindingDependencies;
  readiness: BindingReadiness;
  readinessReasons: string[];
  dependencySnapshotHash: string | null;
  lastEvaluatedAt: string | null;
  readinessExpiresAt: string | null;
  status: BindingStatus;
  version: number;
  createdAt: string;
  updatedAt: string;
};

export type AgentRuntimeReadinessResponse = {
  tenant: Tenant;
  catalog: AgentCatalogResponse;
  capabilityBindings: CapabilityBinding[];
  skillBindings: SkillBinding[];
  bindingStats: {
    capabilityBindingCount: number;
    skillBindingCount: number;
    activeCapabilityBindingCount: number;
    activeSkillBindingCount: number;
  };
  evaluatedAt: string;
};

export type AgentRunRequest = {
  taskRef: ResourceRef;
  planRef: ResourceRef;
  agentInstance: AssetRef;
  skill: AssetRef;
  logic: AssetRef;
  modelRoute: AssetRef;
  policy: AssetRef;
  inputRefs: ResourceRef[];
};

export type AgentRun = {
  tenant: Tenant;
  agentRunId: string;
  taskId: string;
  taskRunId: string;
  instanceId: string;
  instanceVersion: number;
  skillBindingId: string;
  request: AgentRunRequest;
  status: "queued" | "running" | "paused" | "succeeded" | "failed" | "cancelled" | "unknown";
  version: number;
  createdAt: string;
  updatedAt: string;
};

export type AgentRunListResponse = { tenant: Tenant; items: AgentRun[]; count: number };

export type AgentRunCommandResponse = {
  tenant: Tenant;
  agentRun: AgentRun;
  receipt: RegistryReceipt;
};

export type CreateAgentRunInput = {
  agentRunId: string;
  taskRunRef: ResourceRef;
  skillBindingId: string;
  run: AgentRunRequest;
};

export type HandoffEnvelope = {
  tenant: Tenant;
  handoffId: string;
  envelope: {
    taskRef: ResourceRef;
    runRef: ResourceRef;
    senderInstance: AssetRef;
    receiverInstance: AssetRef;
    objectRefs: ResourceRef[];
    artifactRefs: ResourceRef[];
    evidenceRefs: ResourceRef[];
    context: Record<string, unknown>;
    allowedContextFields: string[];
    markings: string[];
    expiresAt: string;
  };
  status: "issued" | "consumed" | "revoked" | "expired";
  version: number;
  consumedAt: string | null;
  createdAt: string;
};

export type RegistryReceipt = {
  tenant: Tenant;
  receiptId: string;
  operation: string;
  idempotencyKey: string;
  requestHash: string;
  resourceRef: ResourceRef;
  resultRef: ResourceRef;
  status: "applied";
  createdBy: string;
  createdAt: string;
};

export type IssueHandoffInput = {
  handoffId: string;
  envelope: HandoffEnvelope["envelope"];
};

export type IssuedHandoff = {
  handoff: HandoffEnvelope;
  bearerToken: string | null;
  receipt: RegistryReceipt;
};

export type ConsumeHandoffInput = {
  bearerToken: string;
  receiverInstance: AssetRef;
};

export type HandoffDecision = {
  tenant: Tenant;
  decisionId: string;
  handoffId: string;
  revision: number;
  envelopeRef: ResourceRef;
  decision: "accepted" | "rejected" | "request_more" | "returned";
  reasonCode: string | null;
  gapCodes: string[];
  returnRefs: ResourceRef[];
  correlationRef: ResourceRef | null;
  receiverInstance: AssetRef;
  contentHash: string;
  createdBy: string;
  createdAt: string;
};

export type HandoffDecisionListResponse = {
  tenant: Tenant;
  handoffId: string;
  items: HandoffDecision[];
  count: number;
  headVersion: number;
};

export type CreateHandoffDecisionInput = {
  decision: HandoffDecision["decision"];
  expectedHeadVersion: number;
  reasonCode: string | null;
  gapCodes: string[];
  returnRefs: ResourceRef[];
  correlationRef: ResourceRef | null;
  receiverInstance: AssetRef;
};

export type DecidedHandoff = { decision: HandoffDecision; receipt: RegistryReceipt };
