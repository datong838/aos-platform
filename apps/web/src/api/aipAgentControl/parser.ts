import type {
  AgentCatalogResponse,
  AgentInstance,
  AgentInstanceListResponse,
  AgentInstallResponse,
  AgentRuntimeReadinessResponse,
  AssetRef,
  BindingHealth,
  BindingReadiness,
  BindingStatus,
  CapabilityBinding,
  CapabilityCatalogResponse,
  OperationalBindingDependencies,
  ResourceRef,
  SkillBinding,
  Tenant,
} from "./contracts";

function obj(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} 必须是对象`);
  return value as Record<string, unknown>;
}
function exact(raw: Record<string, unknown>, label: string, allowed: readonly string[], required: readonly string[] = allowed): void {
  const extras = Object.keys(raw).filter((key) => !allowed.includes(key));
  if (extras.length) throw new Error(`${label} 包含额外字段：${extras.join("、")}`);
  const missing = required.filter((key) => !(key in raw));
  if (missing.length) throw new Error(`${label} 缺少字段：${missing.join("、")}`);
}
function str(value: unknown, label: string): string {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${label} 必须是非空字符串`);
  return value;
}
function integer(value: unknown, label: string, min = 0): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < min) throw new Error(`${label} 必须是大于等于 ${min} 的整数`);
  return value;
}
function bool(value: unknown, label: string): boolean {
  if (typeof value !== "boolean") throw new Error(`${label} 必须是布尔值`);
  return value;
}
function array(value: unknown, label: string): unknown[] {
  if (!Array.isArray(value)) throw new Error(`${label} 必须是数组`);
  return value;
}
function strings(value: unknown, label: string): string[] {
  return array(value, label).map((item, index) => str(item, `${label}[${index}]`));
}
function enumeration<T extends string>(value: unknown, label: string, values: readonly T[]): T {
  const result = str(value, label) as T;
  if (!values.includes(result)) throw new Error(`${label} 非法`);
  return result;
}
function iso(value: unknown, label: string): string {
  const result = str(value, label);
  if (Number.isNaN(Date.parse(result))) throw new Error(`${label} 非 ISO 时间`);
  return result;
}
function nullableIso(value: unknown, label: string): string | null {
  return value === null ? null : iso(value, label);
}
function sha256(value: unknown, label: string): string {
  const result = str(value, label);
  if (!/^[0-9a-f]{64}$/.test(result)) throw new Error(`${label} 非 SHA-256`);
  return result;
}
function nullableSha(value: unknown, label: string): string | null {
  return value === null ? null : sha256(value, label);
}

function tenant(value: unknown, label = "tenant"): Tenant {
  const raw = obj(value, label);
  exact(raw, label, ["orgId", "projectId"]);
  return { orgId: str(raw.orgId, `${label}.orgId`), projectId: str(raw.projectId, `${label}.projectId`) };
}
function sameTenant(actual: Tenant, expected: Tenant, label: string): void {
  if (actual.orgId !== expected.orgId || actual.projectId !== expected.projectId) throw new Error(`${label} tenant echo 不一致`);
}
function ref(value: unknown, label: string, expectedType?: string): AssetRef {
  const raw = obj(value, label);
  exact(raw, label, ["assetType", "assetId", "revision", "contentHash"]);
  const result = {
    assetType: str(raw.assetType, `${label}.assetType`),
    assetId: str(raw.assetId, `${label}.assetId`),
    revision: integer(raw.revision, `${label}.revision`, 1),
    contentHash: sha256(raw.contentHash, `${label}.contentHash`),
  };
  if (expectedType && result.assetType !== expectedType) throw new Error(`${label}.assetType 必须为 ${expectedType}`);
  return result;
}
function nullableRef(value: unknown, label: string, expectedType?: string): AssetRef | null {
  return value === null ? null : ref(value, label, expectedType);
}
function resourceRef(value: unknown, label: string): ResourceRef {
  const raw = obj(value, label);
  exact(raw, label, ["resourceType", "resourceId", "revision", "authority"]);
  if (raw.revision !== null && typeof raw.revision !== "string") throw new Error(`${label}.revision 必须是字符串或 null`);
  return {
    resourceType: str(raw.resourceType, `${label}.resourceType`),
    resourceId: str(raw.resourceId, `${label}.resourceId`),
    revision: raw.revision as string | null,
    authority: str(raw.authority, `${label}.authority`),
  };
}

function dependencies(value: unknown, label: string): OperationalBindingDependencies {
  const raw = obj(value, label);
  exact(raw, label, ["providerRef", "modelRouteRef", "runtimePolicyRef", "evalGateRef", "evalContractRef", "licenseEvidenceRefs", "dataDependencyRefs", "toolDependencyRefs", "budgetPolicyRef", "allowDegraded"]);
  return {
    providerRef: nullableRef(raw.providerRef, `${label}.providerRef`, "ProviderInstanceRevision"),
    modelRouteRef: nullableRef(raw.modelRouteRef, `${label}.modelRouteRef`, "ModelRouteRevision"),
    runtimePolicyRef: nullableRef(raw.runtimePolicyRef, `${label}.runtimePolicyRef`, "RuntimePolicyRevision"),
    evalGateRef: nullableRef(raw.evalGateRef, `${label}.evalGateRef`, "EvalGateDecision"),
    evalContractRef: nullableRef(raw.evalContractRef, `${label}.evalContractRef`, "EvalContractRevision"),
    licenseEvidenceRefs: array(raw.licenseEvidenceRefs, `${label}.licenseEvidenceRefs`).map((item, index) => resourceRef(item, `${label}.licenseEvidenceRefs[${index}]`)),
    dataDependencyRefs: array(raw.dataDependencyRefs, `${label}.dataDependencyRefs`).map((item, index) => ref(item, `${label}.dataDependencyRefs[${index}]`)),
    toolDependencyRefs: array(raw.toolDependencyRefs, `${label}.toolDependencyRefs`).map((item, index) => ref(item, `${label}.toolDependencyRefs[${index}]`)),
    budgetPolicyRef: nullableRef(raw.budgetPolicyRef, `${label}.budgetPolicyRef`, "BudgetPolicyRevision"),
    allowDegraded: bool(raw.allowDegraded, `${label}.allowDegraded`),
  };
}

const readinessValues = ["available", "degraded", "disabled", "blocked", "unknown"] as const;
const bindingStatusValues = ["provisioning", "active", "suspended", "revoked"] as const;

function parseCapabilityBinding(value: unknown, expectedTenant: Tenant, label: string): CapabilityBinding {
  const raw = obj(value, label);
  exact(raw, label, ["tenant", "bindingId", "capability", "secretRef", "health", "networkPolicyRevision", "quotaPolicyRevision", "timeoutMs", "maxConcurrency", "dependencies", "operationalReadiness", "readinessReasons", "dependencySnapshotHash", "lastEvaluatedAt", "readinessExpiresAt", "status", "version", "observedAt", "createdAt", "updatedAt"]);
  const scope = tenant(raw.tenant, `${label}.tenant`); sameTenant(scope, expectedTenant, label);
  return {
    tenant: scope,
    bindingId: str(raw.bindingId, `${label}.bindingId`),
    capability: ref(raw.capability, `${label}.capability`, "CapabilityRevision"),
    secretRef: str(raw.secretRef, `${label}.secretRef`),
    health: enumeration<BindingHealth>(raw.health, `${label}.health`, ["unknown", "healthy", "degraded", "unavailable", "revoked"]),
    networkPolicyRevision: str(raw.networkPolicyRevision, `${label}.networkPolicyRevision`),
    quotaPolicyRevision: str(raw.quotaPolicyRevision, `${label}.quotaPolicyRevision`),
    timeoutMs: integer(raw.timeoutMs, `${label}.timeoutMs`, 1),
    maxConcurrency: integer(raw.maxConcurrency, `${label}.maxConcurrency`, 1),
    dependencies: dependencies(raw.dependencies, `${label}.dependencies`),
    operationalReadiness: enumeration<BindingReadiness>(raw.operationalReadiness, `${label}.operationalReadiness`, readinessValues),
    readinessReasons: strings(raw.readinessReasons, `${label}.readinessReasons`),
    dependencySnapshotHash: nullableSha(raw.dependencySnapshotHash, `${label}.dependencySnapshotHash`),
    lastEvaluatedAt: nullableIso(raw.lastEvaluatedAt, `${label}.lastEvaluatedAt`),
    readinessExpiresAt: nullableIso(raw.readinessExpiresAt, `${label}.readinessExpiresAt`),
    status: enumeration<BindingStatus>(raw.status, `${label}.status`, bindingStatusValues),
    version: integer(raw.version, `${label}.version`, 1),
    observedAt: nullableIso(raw.observedAt, `${label}.observedAt`),
    createdAt: iso(raw.createdAt, `${label}.createdAt`), updatedAt: iso(raw.updatedAt, `${label}.updatedAt`),
  };
}

function parseSkillBinding(value: unknown, expectedTenant: Tenant, label: string): SkillBinding {
  const raw = obj(value, label);
  exact(raw, label, ["tenant", "bindingId", "instanceId", "skill", "capabilityBindingIds", "budgetPolicyRef", "dependencies", "readiness", "readinessReasons", "dependencySnapshotHash", "lastEvaluatedAt", "readinessExpiresAt", "status", "version", "createdAt", "updatedAt"]);
  const scope = tenant(raw.tenant, `${label}.tenant`); sameTenant(scope, expectedTenant, label);
  return {
    tenant: scope, bindingId: str(raw.bindingId, `${label}.bindingId`), instanceId: str(raw.instanceId, `${label}.instanceId`),
    skill: ref(raw.skill, `${label}.skill`, "SkillTemplate"), capabilityBindingIds: strings(raw.capabilityBindingIds, `${label}.capabilityBindingIds`),
    budgetPolicyRef: ref(raw.budgetPolicyRef, `${label}.budgetPolicyRef`, "BudgetPolicyRevision"), dependencies: dependencies(raw.dependencies, `${label}.dependencies`),
    readiness: enumeration<BindingReadiness>(raw.readiness, `${label}.readiness`, readinessValues), readinessReasons: strings(raw.readinessReasons, `${label}.readinessReasons`),
    dependencySnapshotHash: nullableSha(raw.dependencySnapshotHash, `${label}.dependencySnapshotHash`), lastEvaluatedAt: nullableIso(raw.lastEvaluatedAt, `${label}.lastEvaluatedAt`), readinessExpiresAt: nullableIso(raw.readinessExpiresAt, `${label}.readinessExpiresAt`),
    status: enumeration<BindingStatus>(raw.status, `${label}.status`, bindingStatusValues), version: integer(raw.version, `${label}.version`, 1), createdAt: iso(raw.createdAt, `${label}.createdAt`), updatedAt: iso(raw.updatedAt, `${label}.updatedAt`),
  };
}

export function parseAgentInstance(value: unknown, expectedTenant?: Tenant): AgentInstance {
  const raw = obj(value, "AgentInstance");
  exact(raw, "AgentInstance", ["tenant", "instanceId", "instanceRef", "template", "status", "overlay", "version", "createdBy", "createdAt", "updatedAt"], ["tenant", "instanceId", "instanceRef", "template", "status", "overlay", "version", "updatedAt"]);
  const scope = tenant(raw.tenant, "AgentInstance.tenant"); if (expectedTenant) sameTenant(scope, expectedTenant, "AgentInstance");
  const overlay = obj(raw.overlay, "AgentInstance.overlay");
  exact(overlay, "AgentInstance.overlay", ["displayName", "promptRevision", "allowedCapabilityIds", "monthlyBudgetMinor", "policyRevision"], ["displayName", "allowedCapabilityIds"]);
  return {
    tenant: scope, instanceId: str(raw.instanceId, "AgentInstance.instanceId"), instanceRef: ref(raw.instanceRef, "AgentInstance.instanceRef", "AgentInstance"), template: ref(raw.template, "AgentInstance.template", "AgentTemplate"),
    status: enumeration(raw.status, "AgentInstance.status", ["provisioning", "active", "suspended", "deleted"] as const),
    overlay: { displayName: overlay.displayName == null ? null : str(overlay.displayName, "overlay.displayName"), allowedCapabilityIds: strings(overlay.allowedCapabilityIds, "overlay.allowedCapabilityIds") },
    version: integer(raw.version, "AgentInstance.version", 1), updatedAt: iso(raw.updatedAt, "AgentInstance.updatedAt"),
  };
}

export function parseAgentCatalog(value: unknown, expectedTenant?: Tenant): AgentCatalogResponse {
  const raw = obj(value, "AgentCatalogResponse"); exact(raw, "AgentCatalogResponse", ["tenant", "items", "stats"]);
  const scope = tenant(raw.tenant); if (expectedTenant) sameTenant(scope, expectedTenant, "AgentCatalogResponse");
  const items = array(raw.items, "items").map((value, index) => {
    const item = obj(value, `items[${index}]`); exact(item, `items[${index}]`, ["template", "instance", "skills", "requiredCapabilityIds", "runtimeReadiness", "blockers"]);
    const template = obj(item.template, `items[${index}].template`);
    exact(template, `items[${index}].template`, ["templateId", "revision", "displayName", "roleKey", "lifecycle", "sourceRef", "sourceLicense", "manifest", "contentHash", "createdBy", "createdAt"], ["templateId", "revision", "displayName", "roleKey", "lifecycle", "sourceRef", "sourceLicense", "manifest", "contentHash"]);
    const manifest = obj(template.manifest, `items[${index}].template.manifest`);
    exact(manifest, `items[${index}].template.manifest`, ["id", "displayName", "roleKey", "logicIds", "responsibility", "runtimeReadiness", "blockers"]);
    const skills = array(item.skills, `items[${index}].skills`).map((value, skillIndex) => {
      const skill = obj(value, `items[${index}].skills[${skillIndex}]`);
      exact(skill, `items[${index}].skills[${skillIndex}]`, ["skillId", "revision", "canonicalLogicId", "lifecycle", "inputSchema", "outputSchema", "toolAllowlist", "requiredCapabilities", "riskLevel", "evalPackRef", "memoryPolicyRef", "handoffPolicyRef", "sourceRef", "sourceLicense", "parentRef", "publicationTenant", "releaseGateRef", "publicationRef", "modelRouteRef", "runtimePolicyRef", "contentHash", "createdBy", "createdAt"]);
      return { skillId: str(skill.skillId, "skillId"), canonicalLogicId: str(skill.canonicalLogicId, "canonicalLogicId"), lifecycle: enumeration(skill.lifecycle, "skill.lifecycle", ["evaluated", "published"] as const), requiredCapabilities: strings(skill.requiredCapabilities, "requiredCapabilities"), riskLevel: str(skill.riskLevel, "riskLevel") };
    });
    return {
      template: { templateId: str(template.templateId, "templateId"), revision: integer(template.revision, "revision", 1), displayName: str(template.displayName, "displayName"), roleKey: str(template.roleKey, "roleKey"), lifecycle: enumeration(template.lifecycle, "lifecycle", ["published"] as const), sourceRef: resourceRef(template.sourceRef, "sourceRef"), sourceLicense: str(template.sourceLicense, "sourceLicense"), manifest: { logicIds: strings(manifest.logicIds, "logicIds"), responsibility: str(manifest.responsibility, "responsibility"), runtimeReadiness: str(manifest.runtimeReadiness, "runtimeReadiness"), blockers: strings(manifest.blockers, "blockers") }, contentHash: sha256(template.contentHash, "contentHash") },
      instance: item.instance == null ? null : parseAgentInstance(item.instance, scope), skills, requiredCapabilityIds: strings(item.requiredCapabilityIds, "requiredCapabilityIds"), runtimeReadiness: enumeration(item.runtimeReadiness, "runtimeReadiness", ["blocked"] as const), blockers: strings(item.blockers, "blockers"),
    };
  });
  const stats = obj(raw.stats, "stats"); exact(stats, "stats", ["definitionCount", "installedCount", "runnableCount", "skillDefinitionCount", "capabilityDefinitionCount"]);
  return { tenant: scope, items, stats: { definitionCount: integer(stats.definitionCount, "definitionCount"), installedCount: integer(stats.installedCount, "installedCount"), runnableCount: integer(stats.runnableCount, "runnableCount"), skillDefinitionCount: integer(stats.skillDefinitionCount, "skillDefinitionCount"), capabilityDefinitionCount: integer(stats.capabilityDefinitionCount, "capabilityDefinitionCount") } };
}

export function parseAgentInstances(value: unknown, expectedTenant?: Tenant): AgentInstanceListResponse {
  const raw = obj(value, "AgentInstanceListResponse"); exact(raw, "AgentInstanceListResponse", ["tenant", "items", "count"]);
  const scope = tenant(raw.tenant); if (expectedTenant) sameTenant(scope, expectedTenant, "AgentInstanceListResponse");
  const items = array(raw.items, "items").map((item) => parseAgentInstance(item, scope));
  return { tenant: scope, items, count: integer(raw.count, "count") };
}

export function parseCapabilities(value: unknown, expectedTenant?: Tenant): CapabilityCatalogResponse {
  const raw = obj(value, "CapabilityCatalogResponse"); exact(raw, "CapabilityCatalogResponse", ["tenant", "items", "count", "availableCount"]);
  const scope = tenant(raw.tenant); if (expectedTenant) sameTenant(scope, expectedTenant, "CapabilityCatalogResponse");
  const items = array(raw.items, "items").map((value, index) => {
    const item = obj(value, `items[${index}]`);
    exact(item, `items[${index}]`, ["capabilityId", "revision", "displayName", "lifecycle", "parentRef", "aliases", "inputSchemaRef", "outputSchemaRef", "riskLevel", "requiredDataRefs", "requiredToolRefs", "requiredCapabilityRefs", "evalPackRef", "memoryPolicyRef", "handoffPolicyRef", "effectReviewSchemaRef", "licensePolicyRef", "readinessPolicyRef", "readiness", "readinessReasons", "sourceRef", "sourceLicense", "contentHash", "createdBy", "createdAt"], ["capabilityId", "revision", "displayName", "lifecycle", "aliases", "riskLevel", "readiness", "readinessReasons", "contentHash"]);
    return { capabilityId: str(item.capabilityId, "capabilityId"), revision: integer(item.revision, "revision", 1), displayName: str(item.displayName, "displayName"), lifecycle: enumeration(item.lifecycle, "lifecycle", ["published"] as const), aliases: strings(item.aliases, "aliases"), riskLevel: str(item.riskLevel, "riskLevel"), readiness: enumeration(item.readiness, "readiness", readinessValues), readinessReasons: strings(item.readinessReasons, "readinessReasons"), contentHash: sha256(item.contentHash, "contentHash") };
  });
  return { tenant: scope, items, count: integer(raw.count, "count"), availableCount: integer(raw.availableCount, "availableCount") };
}

export function parseRuntimeReadiness(value: unknown, expectedTenant: Tenant): AgentRuntimeReadinessResponse {
  const raw = obj(value, "AgentRuntimeReadinessResponse"); exact(raw, "AgentRuntimeReadinessResponse", ["tenant", "catalog", "capabilityBindings", "skillBindings", "bindingStats", "evaluatedAt"]);
  const scope = tenant(raw.tenant); sameTenant(scope, expectedTenant, "AgentRuntimeReadinessResponse");
  const catalog = parseAgentCatalog(raw.catalog, scope);
  const bindingStats = obj(raw.bindingStats, "bindingStats"); exact(bindingStats, "bindingStats", ["capabilityBindingCount", "skillBindingCount", "activeCapabilityBindingCount", "activeSkillBindingCount"]);
  return {
    tenant: scope, catalog,
    capabilityBindings: array(raw.capabilityBindings, "capabilityBindings").map((item, index) => parseCapabilityBinding(item, scope, `capabilityBindings[${index}]`)),
    skillBindings: array(raw.skillBindings, "skillBindings").map((item, index) => parseSkillBinding(item, scope, `skillBindings[${index}]`)),
    bindingStats: { capabilityBindingCount: integer(bindingStats.capabilityBindingCount, "bindingStats.capabilityBindingCount"), skillBindingCount: integer(bindingStats.skillBindingCount, "bindingStats.skillBindingCount"), activeCapabilityBindingCount: integer(bindingStats.activeCapabilityBindingCount, "bindingStats.activeCapabilityBindingCount"), activeSkillBindingCount: integer(bindingStats.activeSkillBindingCount, "bindingStats.activeSkillBindingCount") },
    evaluatedAt: iso(raw.evaluatedAt, "evaluatedAt"),
  };
}

export function parseInstall(value: unknown, expectedTenant?: Tenant): AgentInstallResponse {
  const raw = obj(value, "AgentInstallResponse");
  exact(raw, "AgentInstallResponse", ["tenant", "solutionPackId", "solutionPackVersion", "status", "items", "createdCount", "existingCount", "runnableCount"], ["tenant", "status", "items", "createdCount", "existingCount", "runnableCount"]);
  const scope = tenant(raw.tenant); if (expectedTenant) sameTenant(scope, expectedTenant, "AgentInstallResponse");
  const runnableCount = integer(raw.runnableCount, "runnableCount"); if (runnableCount !== 0) throw new Error("runnableCount 必须为 0");
  return { tenant: scope, status: enumeration(raw.status, "status", ["installed", "partial"] as const), createdCount: integer(raw.createdCount, "createdCount"), existingCount: integer(raw.existingCount, "existingCount"), runnableCount: 0, items: array(raw.items, "items").map((value, index) => { const item = obj(value, `items[${index}]`); exact(item, `items[${index}]`, ["instance", "disposition", "receipt"], ["instance", "disposition"]); return { instance: parseAgentInstance(item.instance, scope), disposition: enumeration(item.disposition, "disposition", ["created", "existing"] as const) }; }) };
}
