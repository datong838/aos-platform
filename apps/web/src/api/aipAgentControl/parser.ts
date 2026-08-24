import type {
  AgentCatalogResponse,
  AgentInstance,
  AgentInstanceListResponse,
  AgentInstallResponse,
  AgentRuntimeReadinessResponse,
  AgentRun,
  AssetRef,
  BindingHealth,
  BindingReadiness,
  BindingStatus,
  CapabilityBinding,
  CapabilityCatalogResponse,
  OperationalBindingDependencies,
  ResourceRef,
  SkillBinding,
  HandoffDecision,
  HandoffDecisionListResponse,
  HandoffEnvelope,
  IssuedHandoff,
  DecidedHandoff,
  RegistryReceipt,
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
function exactResourceRef(value: unknown, label: string, expectedType: string): ResourceRef {
  const result = resourceRef(value, label);
  if (result.resourceType !== expectedType) throw new Error(`${label}.resourceType 必须为 ${expectedType}`);
  if (result.revision === null || !result.revision.trim()) throw new Error(`${label}.revision 必须为 exact revision`);
  return result;
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
      const skillRequired = ["skillId", "revision", "canonicalLogicId", "lifecycle", "inputSchema", "outputSchema", "toolAllowlist", "requiredCapabilities", "riskLevel", "evalPackRef", "memoryPolicyRef", "handoffPolicyRef", "sourceRef", "sourceLicense", "parentRef", "publicationTenant", "releaseGateRef", "publicationRef", "modelRouteRef", "runtimePolicyRef", "contentHash", "createdBy", "createdAt"] as const;
      exact(skill, `items[${index}].skills[${skillIndex}]`, [...skillRequired, "logicRevisionRef"], skillRequired);
      return { skillId: str(skill.skillId, "skillId"), revision: integer(skill.revision, "skill.revision", 1), canonicalLogicId: str(skill.canonicalLogicId, "canonicalLogicId"), lifecycle: enumeration(skill.lifecycle, "skill.lifecycle", ["evaluated", "published"] as const), requiredCapabilities: strings(skill.requiredCapabilities, "requiredCapabilities"), riskLevel: str(skill.riskLevel, "riskLevel"), contentHash: sha256(skill.contentHash, "skill.contentHash"), logicRevisionRef: nullableRef(skill.logicRevisionRef, "skill.logicRevisionRef", "LogicRevision") };
    });
    return {
      template: { templateId: str(template.templateId, "templateId"), revision: integer(template.revision, "revision", 1), displayName: str(template.displayName, "displayName"), roleKey: str(template.roleKey, "roleKey"), lifecycle: enumeration(template.lifecycle, "lifecycle", ["published"] as const), sourceRef: resourceRef(template.sourceRef, "sourceRef"), sourceLicense: str(template.sourceLicense, "sourceLicense"), manifest: { logicIds: strings(manifest.logicIds, "logicIds"), responsibility: str(manifest.responsibility, "responsibility"), runtimeReadiness: str(manifest.runtimeReadiness, "runtimeReadiness"), blockers: strings(manifest.blockers, "blockers") }, contentHash: sha256(template.contentHash, "contentHash") },
      instance: item.instance == null ? null : parseAgentInstance(item.instance, scope), skills, requiredCapabilityIds: strings(item.requiredCapabilityIds, "requiredCapabilityIds"), runtimeReadiness: enumeration(item.runtimeReadiness, "runtimeReadiness", ["blocked", "runnable"] as const), blockers: strings(item.blockers, "blockers"),
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
  exact(raw, "AgentInstallResponse", ["tenant", "solutionPackId", "solutionPackVersion", "status", "items", "createdCount", "existingCount", "runnableCount"]);
  const scope = tenant(raw.tenant); if (expectedTenant) sameTenant(scope, expectedTenant, "AgentInstallResponse");
  if (raw.solutionPackId !== "solution.ecommerce.growth") throw new Error("solutionPackId 非法");
  const solutionPackVersion = str(raw.solutionPackVersion, "solutionPackVersion"); if (!/^\d+\.\d+\.\d+$/.test(solutionPackVersion)) throw new Error("solutionPackVersion 非法");
  const runnableCount = integer(raw.runnableCount, "runnableCount"); if (runnableCount !== 0) throw new Error("runnableCount 必须为 0");
  return { tenant: scope, solutionPackId: "solution.ecommerce.growth", solutionPackVersion, status: enumeration(raw.status, "status", ["installed", "partial"] as const), createdCount: integer(raw.createdCount, "createdCount"), existingCount: integer(raw.existingCount, "existingCount"), runnableCount: 0, items: array(raw.items, "items").map((value, index) => { const item = obj(value, `items[${index}]`); exact(item, `items[${index}]`, ["instance", "disposition", "receipt"], ["instance", "disposition"]); return { instance: parseAgentInstance(item.instance, scope), disposition: enumeration(item.disposition, "disposition", ["created", "existing"] as const) }; }) };
}

export function parseAgentRun(value: unknown, expectedTenant: Tenant): AgentRun {
  const raw = obj(value, "AgentRun");
  exact(raw, "AgentRun", ["tenant", "agentRunId", "taskId", "taskRunId", "instanceId", "instanceVersion", "skillBindingId", "request", "status", "version", "createdAt", "updatedAt"]);
  const scope = tenant(raw.tenant, "AgentRun.tenant"); sameTenant(scope, expectedTenant, "AgentRun");
  const request = obj(raw.request, "AgentRun.request");
  exact(request, "AgentRun.request", ["taskRef", "planRef", "agentInstance", "skill", "logic", "modelRoute", "policy", "inputRefs"]);
  const policy = ref(request.policy, "AgentRun.request.policy");
  if (!["PolicyRevision", "RuntimePolicyRevision"].includes(policy.assetType)) throw new Error("AgentRun.request.policy.assetType 非法");
  return {
    tenant: scope,
    agentRunId: str(raw.agentRunId, "AgentRun.agentRunId"), taskId: str(raw.taskId, "AgentRun.taskId"), taskRunId: str(raw.taskRunId, "AgentRun.taskRunId"),
    instanceId: str(raw.instanceId, "AgentRun.instanceId"), instanceVersion: integer(raw.instanceVersion, "AgentRun.instanceVersion", 1), skillBindingId: str(raw.skillBindingId, "AgentRun.skillBindingId"),
    request: {
      taskRef: exactResourceRef(request.taskRef, "AgentRun.request.taskRef", "Task"), planRef: exactResourceRef(request.planRef, "AgentRun.request.planRef", "PlanRevision"),
      agentInstance: ref(request.agentInstance, "AgentRun.request.agentInstance", "AgentInstance"), skill: ref(request.skill, "AgentRun.request.skill", "SkillTemplate"), logic: ref(request.logic, "AgentRun.request.logic", "LogicRevision"),
      modelRoute: ref(request.modelRoute, "AgentRun.request.modelRoute", "ModelRouteRevision"), policy,
      inputRefs: array(request.inputRefs, "AgentRun.request.inputRefs").map((item, index) => resourceRef(item, `AgentRun.request.inputRefs[${index}]`)),
    },
    status: enumeration(raw.status, "AgentRun.status", ["queued", "running", "paused", "succeeded", "failed", "cancelled", "unknown"] as const),
    version: integer(raw.version, "AgentRun.version", 1), createdAt: iso(raw.createdAt, "AgentRun.createdAt"), updatedAt: iso(raw.updatedAt, "AgentRun.updatedAt"),
  };
}

export function parseHandoff(value: unknown, expectedTenant: Tenant): HandoffEnvelope {
  const raw = obj(value, "HandoffEnvelope"); exact(raw, "HandoffEnvelope", ["tenant", "handoffId", "envelope", "status", "version", "consumedAt", "createdAt"]);
  const scope = tenant(raw.tenant, "HandoffEnvelope.tenant"); sameTenant(scope, expectedTenant, "HandoffEnvelope");
  const envelope = obj(raw.envelope, "HandoffEnvelope.envelope");
  exact(envelope, "HandoffEnvelope.envelope", ["taskRef", "runRef", "senderInstance", "receiverInstance", "objectRefs", "artifactRefs", "evidenceRefs", "context", "allowedContextFields", "markings", "expiresAt"]);
  const context = obj(envelope.context, "HandoffEnvelope.envelope.context");
  const allowedContextFields = strings(envelope.allowedContextFields, "HandoffEnvelope.envelope.allowedContextFields");
  if (Object.keys(context).some((key) => !allowedContextFields.includes(key))) throw new Error("HandoffEnvelope.envelope.context 超出 allowlist");
  const senderInstance = ref(envelope.senderInstance, "HandoffEnvelope.envelope.senderInstance", "AgentInstance");
  const receiverInstance = ref(envelope.receiverInstance, "HandoffEnvelope.envelope.receiverInstance", "AgentInstance");
  if (senderInstance.assetId === receiverInstance.assetId) throw new Error("HandoffEnvelope sender 与 receiver 必须不同");
  return {
    tenant: scope, handoffId: str(raw.handoffId, "HandoffEnvelope.handoffId"),
    envelope: {
      taskRef: exactResourceRef(envelope.taskRef, "HandoffEnvelope.envelope.taskRef", "Task"), runRef: exactResourceRef(envelope.runRef, "HandoffEnvelope.envelope.runRef", "TaskRun"),
      senderInstance, receiverInstance,
      objectRefs: array(envelope.objectRefs, "HandoffEnvelope.envelope.objectRefs").map((item, index) => resourceRef(item, `objectRefs[${index}]`)), artifactRefs: array(envelope.artifactRefs, "HandoffEnvelope.envelope.artifactRefs").map((item, index) => resourceRef(item, `artifactRefs[${index}]`)), evidenceRefs: array(envelope.evidenceRefs, "HandoffEnvelope.envelope.evidenceRefs").map((item, index) => resourceRef(item, `evidenceRefs[${index}]`)),
      context, allowedContextFields, markings: strings(envelope.markings, "HandoffEnvelope.envelope.markings"), expiresAt: iso(envelope.expiresAt, "HandoffEnvelope.envelope.expiresAt"),
    },
    status: enumeration(raw.status, "HandoffEnvelope.status", ["issued", "consumed", "revoked", "expired"] as const), version: integer(raw.version, "HandoffEnvelope.version", 1), consumedAt: nullableIso(raw.consumedAt, "HandoffEnvelope.consumedAt"), createdAt: iso(raw.createdAt, "HandoffEnvelope.createdAt"),
  };
}

function parseRegistryReceipt(value: unknown, expectedTenant: Tenant, operation: string, label: string): RegistryReceipt {
  const raw = obj(value, label); exact(raw, label, ["tenant", "receiptId", "operation", "idempotencyKey", "requestHash", "resourceRef", "resultRef", "status", "createdBy", "createdAt"]);
  const scope = tenant(raw.tenant, `${label}.tenant`); sameTenant(scope, expectedTenant, label);
  const parsedOperation = str(raw.operation, `${label}.operation`); if (parsedOperation !== operation) throw new Error(`${label}.operation 漂移`);
  const status = enumeration(raw.status, `${label}.status`, ["applied"] as const);
  return { tenant: scope, receiptId: str(raw.receiptId, `${label}.receiptId`), operation: parsedOperation, idempotencyKey: str(raw.idempotencyKey, `${label}.idempotencyKey`), requestHash: sha256(raw.requestHash, `${label}.requestHash`), resourceRef: resourceRef(raw.resourceRef, `${label}.resourceRef`), resultRef: resourceRef(raw.resultRef, `${label}.resultRef`), status, createdBy: str(raw.createdBy, `${label}.createdBy`), createdAt: iso(raw.createdAt, `${label}.createdAt`) };
}

export function parseIssuedHandoff(value: unknown, expectedTenant: Tenant): IssuedHandoff {
  const raw = obj(value, "IssuedHandoff"); exact(raw, "IssuedHandoff", ["handoff", "bearerToken", "receipt"]);
  const handoff = parseHandoff(raw.handoff, expectedTenant);
  const bearerToken = raw.bearerToken === null ? null : str(raw.bearerToken, "IssuedHandoff.bearerToken");
  if (bearerToken !== null && bearerToken.length < 32) throw new Error("IssuedHandoff.bearerToken 太短");
  const receipt = parseRegistryReceipt(raw.receipt, expectedTenant, "handoff.issue", "IssuedHandoff.receipt");
  if (receipt.resultRef.resourceType !== "HandoffEnvelope" || receipt.resultRef.resourceId !== handoff.handoffId) throw new Error("IssuedHandoff receipt resultRef 漂移");
  return { handoff, bearerToken, receipt };
}

function parseHandoffDecision(value: unknown, expectedTenant: Tenant, expectedHandoffId: string, label: string): HandoffDecision {
  const raw = obj(value, label); exact(raw, label, ["tenant", "decisionId", "handoffId", "revision", "envelopeRef", "decision", "reasonCode", "gapCodes", "returnRefs", "correlationRef", "receiverInstance", "contentHash", "createdBy", "createdAt"]);
  const scope = tenant(raw.tenant, `${label}.tenant`); sameTenant(scope, expectedTenant, label);
  const handoffId = str(raw.handoffId, `${label}.handoffId`); if (handoffId !== expectedHandoffId) throw new Error(`${label}.handoffId 漂移`);
  const decision = enumeration(raw.decision, `${label}.decision`, ["accepted", "rejected", "request_more", "returned"] as const);
  const reasonCode = raw.reasonCode === null ? null : str(raw.reasonCode, `${label}.reasonCode`);
  const gapCodes = strings(raw.gapCodes, `${label}.gapCodes`);
  const returnRefs = array(raw.returnRefs, `${label}.returnRefs`).map((item, index) => resourceRef(item, `${label}.returnRefs[${index}]`));
  if (decision === "request_more" && gapCodes.length === 0) throw new Error(`${label}.request_more 必须提供 gapCodes`);
  if (decision === "returned" && returnRefs.length === 0) throw new Error(`${label}.returned 必须提供 returnRefs`);
  if (decision === "rejected" && !reasonCode) throw new Error(`${label}.rejected 必须提供 reasonCode`);
  return { tenant: scope, decisionId: str(raw.decisionId, `${label}.decisionId`), handoffId, revision: integer(raw.revision, `${label}.revision`, 1), envelopeRef: exactResourceRef(raw.envelopeRef, `${label}.envelopeRef`, "HandoffEnvelope"), decision, reasonCode, gapCodes, returnRefs, correlationRef: raw.correlationRef === null ? null : resourceRef(raw.correlationRef, `${label}.correlationRef`), receiverInstance: ref(raw.receiverInstance, `${label}.receiverInstance`, "AgentInstance"), contentHash: sha256(raw.contentHash, `${label}.contentHash`), createdBy: str(raw.createdBy, `${label}.createdBy`), createdAt: iso(raw.createdAt, `${label}.createdAt`) };
}

export function parseHandoffDecisions(value: unknown, expectedTenant: Tenant): HandoffDecisionListResponse {
  const raw = obj(value, "HandoffDecisionListResponse"); exact(raw, "HandoffDecisionListResponse", ["tenant", "handoffId", "items", "count", "headVersion"]);
  const scope = tenant(raw.tenant); sameTenant(scope, expectedTenant, "HandoffDecisionListResponse"); const handoffId = str(raw.handoffId, "handoffId");
  const items = array(raw.items, "items").map((item, index) => parseHandoffDecision(item, scope, handoffId, `items[${index}]`));
  const count = integer(raw.count, "count"); if (count !== items.length) throw new Error("count 与 items 数量不一致");
  const identities = new Set(items.map((item) => item.decisionId)); if (identities.size !== items.length) throw new Error("decisionId 必须唯一");
  return { tenant: scope, handoffId, items, count, headVersion: integer(raw.headVersion, "headVersion") };
}

export function parseDecidedHandoff(value: unknown, expectedTenant: Tenant, expectedHandoffId: string): DecidedHandoff {
  const raw = obj(value, "DecidedHandoff"); exact(raw, "DecidedHandoff", ["decision", "receipt"]);
  const decision = parseHandoffDecision(raw.decision, expectedTenant, expectedHandoffId, "DecidedHandoff.decision");
  const receipt = parseRegistryReceipt(raw.receipt, expectedTenant, "handoff.decision", "DecidedHandoff.receipt");
  if (receipt.resultRef.resourceType !== "HandoffDecisionRevision" || receipt.resultRef.resourceId !== decision.decisionId) throw new Error("DecidedHandoff receipt resultRef 漂移");
  return { decision, receipt };
}
