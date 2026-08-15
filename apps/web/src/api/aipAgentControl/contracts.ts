export type Tenant = { orgId: string; projectId: string };
export type AssetRef = { assetType: string; assetId: string; revision: number; contentHash: string };
export type ResourceRef = { resourceType: string; resourceId: string; revision: string | null; authority: string };

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
  canonicalLogicId: string;
  lifecycle: "evaluated" | "published";
  requiredCapabilities: string[];
  riskLevel: string;
};

export type AgentCatalogItem = {
  template: AgentTemplate;
  instance: AgentInstance | null;
  skills: SkillTemplate[];
  requiredCapabilityIds: string[];
  runtimeReadiness: "blocked";
  blockers: string[];
};

export type AgentCatalogResponse = {
  tenant: Tenant;
  items: AgentCatalogItem[];
  stats: { definitionCount: number; installedCount: number; runnableCount: number; skillDefinitionCount: number; capabilityDefinitionCount: number };
};

export type AgentInstanceListResponse = { tenant: Tenant; items: AgentInstance[]; count: number };

export type CapabilityRevision = {
  capabilityId: string;
  revision: number;
  displayName: string;
  lifecycle: "published";
  aliases: string[];
  riskLevel: string;
  readiness: "available" | "degraded" | "disabled" | "blocked" | "unknown";
  readinessReasons: string[];
  contentHash: string;
};

export type CapabilityCatalogResponse = { tenant: Tenant; items: CapabilityRevision[]; count: number; availableCount: number };
export type AgentInstallResponse = { tenant: Tenant; status: "installed" | "partial"; createdCount: number; existingCount: number; runnableCount: 0; items: Array<{ instance: AgentInstance; disposition: "created" | "existing" }> };

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
