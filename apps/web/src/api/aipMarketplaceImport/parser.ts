import type { ImportCandidate, ImportJob, ImportJobMutation, ImportPreview, MarketplaceCatalog, ResourceRef, Tenant } from "./contracts";

const obj = (value: unknown, label: string): Record<string, unknown> => {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} 必须是对象`);
  return value as Record<string, unknown>;
};
const exact = (raw: Record<string, unknown>, label: string, fields: readonly string[]) => {
  const missing = fields.filter((field) => !(field in raw));
  const extra = Object.keys(raw).filter((field) => !fields.includes(field));
  if (missing.length) throw new Error(`${label} 缺少字段：${missing.join("、")}`);
  if (extra.length) throw new Error(`${label} 包含额外字段：${extra.join("、")}`);
};
const str = (value: unknown, label: string): string => {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${label} 必须是非空字符串`);
  return value;
};
const bool = (value: unknown, label: string): boolean => {
  if (typeof value !== "boolean") throw new Error(`${label} 必须是布尔值`);
  return value;
};
const integer = (value: unknown, label: string): number => {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) throw new Error(`${label} 必须是非负整数`);
  return value;
};
const arr = (value: unknown, label: string): unknown[] => {
  if (!Array.isArray(value)) throw new Error(`${label} 必须是数组`);
  return value;
};
const sha = (value: unknown, label: string): string => {
  const result = str(value, label);
  if (!/^[0-9a-f]{64}$/.test(result)) throw new Error(`${label} 非 SHA-256`);
  return result;
};
const oneOf = <T extends string>(value: unknown, label: string, values: readonly T[]): T => {
  const result = str(value, label) as T;
  if (!values.includes(result)) throw new Error(`${label} 非法`);
  return result;
};
const tenant = (value: unknown, expected?: Tenant): Tenant => {
  const raw = obj(value, "tenant"); exact(raw, "tenant", ["orgId", "projectId"]);
  const result = { orgId: str(raw.orgId, "tenant.orgId"), projectId: str(raw.projectId, "tenant.projectId") };
  if (expected && (result.orgId !== expected.orgId || result.projectId !== expected.projectId)) throw new Error("tenant echo 不一致");
  return result;
};
const ref = (value: unknown, label: string): ResourceRef => {
  const raw = obj(value, label); exact(raw, label, ["resourceType", "resourceId", "revision", "authority"]);
  if (raw.revision !== null && typeof raw.revision !== "string") throw new Error(`${label}.revision 非法`);
  return { resourceType: str(raw.resourceType, `${label}.resourceType`), resourceId: str(raw.resourceId, `${label}.resourceId`), revision: raw.revision as string | null, authority: str(raw.authority, `${label}.authority`) };
};
const strings = (value: unknown, label: string) => arr(value, label).map((item, index) => str(item, `${label}[${index}]`));

export function parseMarketplaceCatalog(value: unknown, expected?: Tenant): MarketplaceCatalog {
  const raw = obj(value, "MarketplaceCatalog"); exact(raw, "MarketplaceCatalog", ["tenant", "items", "count"]);
  const items = arr(raw.items, "items").map((value, index) => {
    const item = obj(value, `items[${index}]`);
    exact(item, `items[${index}]`, ["packageId", "version", "contentHash", "displayName", "publisher", "license", "sourceRef", "agentCount", "skillCount", "capabilityCount", "installedCount", "runnableCount", "discoverable", "installAuthorized", "agents"]);
    const agents = arr(item.agents, "agents").map((value, agentIndex) => {
      const agent = obj(value, `agents[${agentIndex}]`);
      exact(agent, `agents[${agentIndex}]`, ["templateId", "displayName", "installed", "runtimeReadiness", "blockers", "repairHref", "repairLabel"]);
      return { templateId: str(agent.templateId, "templateId"), displayName: str(agent.displayName, "displayName"), installed: bool(agent.installed, "installed"), runtimeReadiness: str(agent.runtimeReadiness, "runtimeReadiness"), blockers: strings(agent.blockers, "blockers"), repairHref: str(agent.repairHref, "repairHref"), repairLabel: str(agent.repairLabel, "repairLabel") };
    });
    return { packageId: str(item.packageId, "packageId"), version: str(item.version, "version"), contentHash: sha(item.contentHash, "contentHash"), displayName: str(item.displayName, "displayName"), publisher: str(item.publisher, "publisher"), license: str(item.license, "license"), sourceRef: ref(item.sourceRef, "sourceRef"), agentCount: integer(item.agentCount, "agentCount"), skillCount: integer(item.skillCount, "skillCount"), capabilityCount: integer(item.capabilityCount, "capabilityCount"), installedCount: integer(item.installedCount, "installedCount"), runnableCount: integer(item.runnableCount, "runnableCount"), discoverable: bool(item.discoverable, "discoverable"), installAuthorized: bool(item.installAuthorized, "installAuthorized"), agents };
  });
  const count = integer(raw.count, "count");
  if (count !== items.length) throw new Error("市场目录 count 漂移");
  return { tenant: tenant(raw.tenant, expected), items, count };
}
export function parseImportPreview(value: unknown, expected?: Tenant): ImportPreview {
  const raw = obj(value, "ImportPreview");
  exact(raw, "ImportPreview", ["tenant", "previewId", "kind", "status", "contentHash", "steps", "scanArtifact", "importJobAuthority", "approvalRequired"]);
  const steps = arr(raw.steps, "steps").map((value, index) => {
    const item = obj(value, `steps[${index}]`); exact(item, `steps[${index}]`, ["step", "status", "contentHash", "blockerCodes", "summary"]);
    return { step: str(item.step, "step"), status: oneOf(item.status, "status", ["unknown", "passed", "blocked", "external_required"] as const), contentHash: sha(item.contentHash, "step.contentHash"), blockerCodes: strings(item.blockerCodes, "blockerCodes"), summary: str(item.summary, "summary") };
  });
  const scan = obj(raw.scanArtifact, "scanArtifact"); exact(scan, "scanArtifact", ["scannerId", "scannerVersion", "ruleSetHash", "sourceRef", "sourceCommit", "sourceContentHash", "licenseId", "sbomRef", "findings", "status", "accepted", "artifactHash"]);
  const findings = arr(scan.findings, "findings").map((value, index) => {
    const item = obj(value, `findings[${index}]`); exact(item, `findings[${index}]`, ["ruleId", "category", "severity", "path", "line", "message", "evidenceHash"]);
    return { ruleId: str(item.ruleId, "ruleId"), category: str(item.category, "category"), severity: str(item.severity, "severity"), path: str(item.path, "path"), line: integer(item.line, "line"), message: str(item.message, "message"), evidenceHash: sha(item.evidenceHash, "evidenceHash") };
  });
  const status = oneOf(raw.status, "status", ["blocked", "external_required"] as const);
  if (raw.importJobAuthority !== "not_created" || raw.approvalRequired !== true) throw new Error("导入预检越权声明");
  return { tenant: tenant(raw.tenant, expected), previewId: str(raw.previewId, "previewId"), kind: oneOf(raw.kind, "kind", ["agent", "capability"] as const), status, contentHash: sha(raw.contentHash, "contentHash"), steps, scanArtifact: { scannerId: str(scan.scannerId, "scannerId"), scannerVersion: str(scan.scannerVersion, "scannerVersion"), ruleSetHash: sha(scan.ruleSetHash, "ruleSetHash"), sourceRef: ref(scan.sourceRef, "scan.sourceRef"), sourceCommit: str(scan.sourceCommit, "sourceCommit"), sourceContentHash: sha(scan.sourceContentHash, "sourceContentHash"), licenseId: str(scan.licenseId, "licenseId"), sbomRef: ref(scan.sbomRef, "scan.sbomRef"), findings, status: oneOf(scan.status, "scan.status", ["passed", "blocked"] as const), accepted: bool(scan.accepted, "scan.accepted"), artifactHash: sha(scan.artifactHash, "artifactHash") }, importJobAuthority: "not_created", approvalRequired: true };
}

const nullableString = (value: unknown, label: string): string | null => value === null ? null : str(value, label);
const iso = (value: unknown, label: string): string => {
  const result = str(value, label);
  if (Number.isNaN(Date.parse(result))) throw new Error(`${label} 非法`);
  return result;
};
const record = (value: unknown, label: string): Record<string, string> => {
  const raw = obj(value, label);
  return Object.fromEntries(Object.entries(raw).map(([key, item]) => [key, str(item, `${label}.${key}`)]));
};
const parseImportJob = (value: unknown, expected?: Tenant): ImportJob => {
  const raw = obj(value, "ImportJob");
  exact(raw, "ImportJob", ["tenant", "jobId", "previewId", "previewContentHash", "kind", "targetId", "displayName", "status", "conflictDecisions", "approvalEvidenceRef", "approvalReason", "rollbackReason", "createdRefs", "compensatedRefs", "version", "createdBy", "approvedBy", "appliedBy", "createdAt", "updatedAt"]);
  return {
    tenant: tenant(raw.tenant, expected), jobId: str(raw.jobId, "jobId"), previewId: str(raw.previewId, "previewId"),
    previewContentHash: sha(raw.previewContentHash, "previewContentHash"), kind: oneOf(raw.kind, "kind", ["agent", "capability"] as const),
    targetId: str(raw.targetId, "targetId"), displayName: str(raw.displayName, "displayName"),
    status: oneOf(raw.status, "status", ["awaiting_approval", "approved", "applied", "rolled_back"] as const),
    conflictDecisions: record(raw.conflictDecisions, "conflictDecisions"),
    approvalEvidenceRef: raw.approvalEvidenceRef === null ? null : ref(raw.approvalEvidenceRef, "approvalEvidenceRef"),
    approvalReason: nullableString(raw.approvalReason, "approvalReason"), rollbackReason: nullableString(raw.rollbackReason, "rollbackReason"),
    createdRefs: arr(raw.createdRefs, "createdRefs").map((item, index) => ref(item, `createdRefs[${index}]`)),
    compensatedRefs: arr(raw.compensatedRefs, "compensatedRefs").map((item, index) => ref(item, `compensatedRefs[${index}]`)),
    version: integer(raw.version, "version"), createdBy: str(raw.createdBy, "createdBy"),
    approvedBy: nullableString(raw.approvedBy, "approvedBy"), appliedBy: nullableString(raw.appliedBy, "appliedBy"),
    createdAt: iso(raw.createdAt, "createdAt"), updatedAt: iso(raw.updatedAt, "updatedAt"),
  };
};
const parseCandidate = (value: unknown, expected?: Tenant): ImportCandidate => {
  const raw = obj(value, "ImportCandidate");
  exact(raw, "ImportCandidate", ["tenant", "candidateId", "jobId", "kind", "targetId", "displayName", "status", "sourceRef", "contentHash", "createdAt", "rolledBackAt"]);
  return {
    tenant: tenant(raw.tenant, expected), candidateId: str(raw.candidateId, "candidateId"), jobId: str(raw.jobId, "jobId"),
    kind: oneOf(raw.kind, "kind", ["agent", "capability"] as const), targetId: str(raw.targetId, "targetId"),
    displayName: str(raw.displayName, "displayName"), status: oneOf(raw.status, "status", ["active", "rolled_back"] as const),
    sourceRef: ref(raw.sourceRef, "sourceRef"), contentHash: sha(raw.contentHash, "contentHash"),
    createdAt: iso(raw.createdAt, "createdAt"), rolledBackAt: raw.rolledBackAt === null ? null : iso(raw.rolledBackAt, "rolledBackAt"),
  };
};
export function parseImportJobMutation(value: unknown, expected?: Tenant): ImportJobMutation {
  const raw = obj(value, "ImportJobMutation"); exact(raw, "ImportJobMutation", ["job", "candidate", "receipt"]);
  const receipt = obj(raw.receipt, "receipt");
  exact(receipt, "receipt", ["receiptId", "operation", "idempotencyKey", "requestHash", "status", "createdBy", "createdAt"]);
  return {
    job: parseImportJob(raw.job, expected), candidate: raw.candidate === null ? null : parseCandidate(raw.candidate, expected),
    receipt: { receiptId: str(receipt.receiptId, "receiptId"), operation: str(receipt.operation, "operation"), idempotencyKey: str(receipt.idempotencyKey, "idempotencyKey"), requestHash: sha(receipt.requestHash, "requestHash"), status: str(receipt.status, "receipt.status"), createdBy: str(receipt.createdBy, "receipt.createdBy"), createdAt: iso(receipt.createdAt, "receipt.createdAt") },
  };
}
