import type {
  AgentCatalogResponse,
  AgentInstance,
  AgentInstanceListResponse,
  AgentInstallResponse,
  CapabilityCatalogResponse,
} from "./contracts";

function obj(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} 必须是对象`);
  return value as Record<string, unknown>;
}
function str(value: unknown, label: string): string {
  if (typeof value !== "string" || !value) throw new Error(`${label} 必须是非空字符串`);
  return value;
}
function num(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) throw new Error(`${label} 必须是数字`);
  return value;
}
function strings(value: unknown, label: string): string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string" || !item)) throw new Error(`${label} 必须是字符串数组`);
  return value as string[];
}
function tenant(value: unknown) {
  const raw = obj(value, "tenant");
  return { orgId: str(raw.orgId, "tenant.orgId"), projectId: str(raw.projectId, "tenant.projectId") };
}
function ref(value: unknown, label: string) {
  const raw = obj(value, label);
  const contentHash = str(raw.contentHash, `${label}.contentHash`);
  if (!/^[0-9a-f]{64}$/.test(contentHash)) throw new Error(`${label}.contentHash 非 SHA-256`);
  return { assetType: str(raw.assetType, `${label}.assetType`), assetId: str(raw.assetId, `${label}.assetId`), revision: num(raw.revision, `${label}.revision`), contentHash };
}
function resourceRef(value: unknown, label: string) {
  const raw = obj(value, label);
  const revision = raw.revision;
  if (revision !== null && typeof revision !== "string") throw new Error(`${label}.revision 必须是字符串或 null`);
  return {
    resourceType: str(raw.resourceType, `${label}.resourceType`),
    resourceId: str(raw.resourceId, `${label}.resourceId`),
    revision,
    authority: str(raw.authority, `${label}.authority`),
  };
}
function sha256(value: unknown, label: string) {
  const contentHash = str(value, label);
  if (!/^[0-9a-f]{64}$/.test(contentHash)) throw new Error(`${label} 非 SHA-256`);
  return contentHash;
}
export function parseAgentInstance(value: unknown): AgentInstance {
  const raw = obj(value, "AgentInstance");
  const status = str(raw.status, "AgentInstance.status") as AgentInstance["status"];
  if (!["provisioning", "active", "suspended", "deleted"].includes(status)) throw new Error("AgentInstance.status 非法");
  const overlay = obj(raw.overlay, "AgentInstance.overlay");
  return {
    tenant: tenant(raw.tenant), instanceId: str(raw.instanceId, "AgentInstance.instanceId"),
    instanceRef: ref(raw.instanceRef, "AgentInstance.instanceRef"), template: ref(raw.template, "AgentInstance.template"), status,
    overlay: { displayName: overlay.displayName == null ? null : str(overlay.displayName, "overlay.displayName"), allowedCapabilityIds: strings(overlay.allowedCapabilityIds ?? [], "overlay.allowedCapabilityIds") },
    version: num(raw.version, "AgentInstance.version"), updatedAt: str(raw.updatedAt, "AgentInstance.updatedAt"),
  };
}
export function parseAgentCatalog(value: unknown): AgentCatalogResponse {
  const raw = obj(value, "AgentCatalogResponse"); const stats = obj(raw.stats, "stats");
  if (!Array.isArray(raw.items)) throw new Error("items 必须是数组");
  const items = raw.items.map((value, index) => {
    const item = obj(value, `items[${index}]`); const template = obj(item.template, "template"); const manifest = obj(template.manifest, "manifest");
    if (!Array.isArray(item.skills)) throw new Error("skills 必须是数组");
    if (str(template.lifecycle, "lifecycle") !== "published") throw new Error("template.lifecycle 非 published");
    const lifecycle = "published" as const;
    if (str(item.runtimeReadiness, "runtimeReadiness") !== "blocked") throw new Error("runtimeReadiness 非 blocked");
    const runtimeReadiness = "blocked" as const;
    return {
      template: { templateId: str(template.templateId, "templateId"), revision: num(template.revision, "revision"), displayName: str(template.displayName, "displayName"), roleKey: str(template.roleKey, "roleKey"), lifecycle, sourceRef: resourceRef(template.sourceRef, "sourceRef"), sourceLicense: str(template.sourceLicense, "sourceLicense"), manifest: { logicIds: strings(manifest.logicIds, "logicIds"), responsibility: str(manifest.responsibility, "responsibility"), runtimeReadiness: str(manifest.runtimeReadiness, "runtimeReadiness"), blockers: strings(manifest.blockers, "blockers") }, contentHash: sha256(template.contentHash, "contentHash") },
      instance: item.instance == null ? null : parseAgentInstance(item.instance),
      skills: item.skills.map((skillValue) => { const skill = obj(skillValue, "skill"); if (str(skill.lifecycle, "skill.lifecycle") !== "evaluated") throw new Error("skill.lifecycle 非 evaluated"); return { skillId: str(skill.skillId, "skillId"), canonicalLogicId: str(skill.canonicalLogicId, "canonicalLogicId"), lifecycle: "evaluated" as const, requiredCapabilities: strings(skill.requiredCapabilities, "requiredCapabilities"), riskLevel: str(skill.riskLevel, "riskLevel") }; }),
      requiredCapabilityIds: strings(item.requiredCapabilityIds, "requiredCapabilityIds"), runtimeReadiness, blockers: strings(item.blockers, "blockers"),
    };
  });
  return { tenant: tenant(raw.tenant), items, stats: { definitionCount: num(stats.definitionCount, "definitionCount"), installedCount: num(stats.installedCount, "installedCount"), runnableCount: num(stats.runnableCount, "runnableCount"), skillDefinitionCount: num(stats.skillDefinitionCount, "skillDefinitionCount"), capabilityDefinitionCount: num(stats.capabilityDefinitionCount, "capabilityDefinitionCount") } };
}
export function parseAgentInstances(value: unknown): AgentInstanceListResponse { const raw = obj(value, "AgentInstanceListResponse"); if (!Array.isArray(raw.items)) throw new Error("items 必须是数组"); const items = raw.items.map(parseAgentInstance); return { tenant: tenant(raw.tenant), items, count: num(raw.count, "count") }; }
export function parseCapabilities(value: unknown): CapabilityCatalogResponse { const raw = obj(value, "CapabilityCatalogResponse"); if (!Array.isArray(raw.items)) throw new Error("items 必须是数组"); return { tenant: tenant(raw.tenant), items: raw.items.map((value) => { const item = obj(value, "capability"); if (str(item.lifecycle, "lifecycle") !== "published") throw new Error("capability.lifecycle 非 published"); const readiness = str(item.readiness, "readiness") as CapabilityCatalogResponse["items"][number]["readiness"]; if (!["available","degraded","disabled","blocked","unknown"].includes(readiness)) throw new Error("readiness 非法"); return { capabilityId: str(item.capabilityId, "capabilityId"), revision: num(item.revision, "revision"), displayName: str(item.displayName, "displayName"), lifecycle: "published" as const, aliases: strings(item.aliases, "aliases"), riskLevel: str(item.riskLevel, "riskLevel"), readiness, readinessReasons: strings(item.readinessReasons, "readinessReasons"), contentHash: sha256(item.contentHash, "contentHash") }; }), count: num(raw.count, "count"), availableCount: num(raw.availableCount, "availableCount") }; }
export function parseInstall(value: unknown): AgentInstallResponse { const raw = obj(value, "AgentInstallResponse"); if (!Array.isArray(raw.items)) throw new Error("items 必须是数组"); const status = str(raw.status, "status") as "installed"|"partial"; if (!["installed","partial"].includes(status)) throw new Error("status 非法"); const runnableCount = num(raw.runnableCount, "runnableCount"); if (runnableCount !== 0) throw new Error("runnableCount 必须为 0"); return { tenant: tenant(raw.tenant), status, createdCount: num(raw.createdCount, "createdCount"), existingCount: num(raw.existingCount, "existingCount"), runnableCount, items: raw.items.map((value) => { const item=obj(value,"installItem"); const disposition=str(item.disposition,"disposition") as "created"|"existing"; if (!["created","existing"].includes(disposition)) throw new Error("disposition 非法"); return {instance:parseAgentInstance(item.instance),disposition}; }) }; }
