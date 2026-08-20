import type { AipOperationalProjection, OperationalStageCounts } from "./contracts";

function object(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} 必须是对象`);
  return value as Record<string, unknown>;
}
function exact(raw: Record<string, unknown>, keys: string[], label: string) {
  const actual = Object.keys(raw).sort();
  const expected = [...keys].sort();
  if (actual.join("\0") !== expected.join("\0")) throw new Error(`${label} 字段集不匹配`);
}
function string(value: unknown, label: string): string {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${label} 必须是非空字符串`);
  return value;
}
function integer(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) throw new Error(`${label} 必须是非负整数`);
  return value;
}
function iso(value: unknown, label: string): string {
  const result = string(value, label);
  if (Number.isNaN(Date.parse(result))) throw new Error(`${label} 必须是 ISO 时间`);
  return result;
}
function sha(value: unknown, label: string): string {
  const result = string(value, label);
  if (!/^[0-9a-f]{64}$/.test(result)) throw new Error(`${label} 必须是 SHA-256`);
  return result;
}
function stages(value: unknown, label: string): OperationalStageCounts {
  const raw = object(value, label);
  exact(raw, ["definition", "bound", "enabled", "runnable"], label);
  const result = {
    definition: integer(raw.definition, `${label}.definition`),
    bound: integer(raw.bound, `${label}.bound`),
    enabled: integer(raw.enabled, `${label}.enabled`),
    runnable: integer(raw.runnable, `${label}.runnable`),
  };
  if (!(result.runnable <= result.enabled && result.enabled <= result.bound && result.bound <= result.definition)) {
    throw new Error(`${label} 四态计数非单调`);
  }
  return result;
}

export function parseAipOperationalProjection(value: unknown): AipOperationalProjection {
  const raw = object(value, "AipOperationalProjection");
  exact(raw, ["tenant", "roles", "capabilities", "tools", "evalGates", "routes", "overallReadiness", "blockerCodes", "sources", "snapshotHash", "generatedAt"], "AipOperationalProjection");
  const tenant = object(raw.tenant, "tenant");
  exact(tenant, ["orgId", "projectId"], "tenant");
  const sources = object(raw.sources, "sources");
  exact(sources, ["agentReadinessAt", "modelRuntimeAt"], "sources");
  if (!Array.isArray(raw.blockerCodes)) throw new Error("blockerCodes 必须是数组");
  const blockers = raw.blockerCodes.map((item, index) => string(item, `blockerCodes[${index}]`));
  const readiness = string(raw.overallReadiness, "overallReadiness");
  if (readiness !== "ready" && readiness !== "blocked") throw new Error("overallReadiness 非法");
  if ((readiness === "ready" && blockers.length) || (readiness === "blocked" && !blockers.length)) {
    throw new Error("overallReadiness 与 blockerCodes 不一致");
  }
  return {
    tenant: { orgId: string(tenant.orgId, "tenant.orgId"), projectId: string(tenant.projectId, "tenant.projectId") },
    roles: stages(raw.roles, "roles"),
    capabilities: stages(raw.capabilities, "capabilities"),
    tools: stages(raw.tools, "tools"),
    evalGates: stages(raw.evalGates, "evalGates"),
    routes: stages(raw.routes, "routes"),
    overallReadiness: readiness,
    blockerCodes: blockers,
    sources: {
      agentReadinessAt: iso(sources.agentReadinessAt, "sources.agentReadinessAt"),
      modelRuntimeAt: iso(sources.modelRuntimeAt, "sources.modelRuntimeAt"),
    },
    snapshotHash: sha(raw.snapshotHash, "snapshotHash"),
    generatedAt: iso(raw.generatedAt, "generatedAt"),
  };
}
