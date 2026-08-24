import { apiGet, apiGetAuthoritative, apiPost } from "./client";
import type { ExplorationCreate, ObjectRef } from "./ontologyExplorerContracts";
import { getTenant } from "./tenant";

export type ExplorationAsset = {
  kind: "exploration";
  id: string;
  owner: string;
  revision: number;
  payload: ExplorationCreate;
  payloadHash: string;
  archived: boolean;
};

export type RelatedAsset = {
  kind: "object_set" | "annotation";
  id: string;
  owner: string;
  revision: number;
  payload: Record<string, unknown>;
  payloadHash: string;
  archived: boolean;
};

export type ShareGrantView = {
  tenant: { orgId: string; projectId: string };
  grantId: string;
  opaqueRef: string;
  assetId: string;
  assetRevision: number;
  assetPayloadHash: string;
  grantorSubject: string;
  granteeScope: "workspace" | "link";
  purpose: "exploration_read";
  markings: string[];
  status: "active";
  issuedAt: string;
  expiresAt: string;
  revokedAt: null;
  revokeReason: null;
  version: number;
  blocker: null;
};

function record(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} 必须是对象`);
  return value as Record<string, unknown>;
}

function exactKeys(value: Record<string, unknown>, keys: string[], label: string): void {
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) {
    throw new Error(`${label} 字段合同不一致`);
  }
}

function text(value: unknown, label: string): string {
  if (typeof value !== "string" || !value) throw new Error(`${label} 必须是非空字符串`);
  return value;
}

function positiveInt(value: unknown, label: string): number {
  if (!Number.isInteger(value) || Number(value) < 1) throw new Error(`${label} 必须是正整数`);
  return Number(value);
}

function parseExplorationAsset(value: unknown): ExplorationAsset {
  const raw = record(value, "Shared exploration");
  exactKeys(raw, ["kind", "id", "owner", "revision", "payload", "payloadHash", "archived"], "Shared exploration");
  if (raw.kind !== "exploration" || raw.archived !== false) throw new Error("Shared exploration 类型或归档状态无效");
  const payloadHash = text(raw.payloadHash, "Shared exploration.payloadHash");
  if (!/^[0-9a-f]{64}$/.test(payloadHash)) throw new Error("Shared exploration.payloadHash 必须是 SHA-256");
  return {
    kind: "exploration",
    id: text(raw.id, "Shared exploration.id"),
    owner: text(raw.owner, "Shared exploration.owner"),
    revision: positiveInt(raw.revision, "Shared exploration.revision"),
    payload: record(raw.payload, "Shared exploration.payload") as ExplorationCreate,
    payloadHash,
    archived: false,
  };
}

export function parseShareGrant(value: unknown): ShareGrantView {
  const raw = record(value, "Share grant");
  exactKeys(raw, ["tenant", "grantId", "opaqueRef", "assetId", "assetRevision", "assetPayloadHash", "grantorSubject", "granteeScope", "purpose", "markings", "status", "issuedAt", "expiresAt", "revokedAt", "revokeReason", "version", "blocker"], "Share grant");
  const tenant = record(raw.tenant, "Share grant.tenant");
  exactKeys(tenant, ["orgId", "projectId"], "Share grant.tenant");
  const current = getTenant();
  if (tenant.orgId !== current.orgId || tenant.projectId !== current.projectId) throw new Error("Share grant 租户与当前工作区不一致");
  if (raw.status !== "active" || raw.blocker !== null || raw.revokedAt !== null || raw.revokeReason !== null) throw new Error("Share grant 已失效");
  if (raw.purpose !== "exploration_read") throw new Error("Share grant purpose 不允许读取探索");
  if (raw.granteeScope !== "workspace" && raw.granteeScope !== "link") throw new Error("Share grant granteeScope 无效");
  const expiresAt = text(raw.expiresAt, "Share grant.expiresAt");
  if (!Number.isFinite(Date.parse(expiresAt)) || Date.parse(expiresAt) <= Date.now()) throw new Error("Share grant 已过期");
  const issuedAt = text(raw.issuedAt, "Share grant.issuedAt");
  if (!Number.isFinite(Date.parse(issuedAt))) throw new Error("Share grant.issuedAt 无效");
  if (!Array.isArray(raw.markings) || raw.markings.some((item) => typeof item !== "string" || !item)) throw new Error("Share grant.markings 无效");
  const assetPayloadHash = text(raw.assetPayloadHash, "Share grant.assetPayloadHash");
  if (!/^[0-9a-f]{64}$/.test(assetPayloadHash)) throw new Error("Share grant.assetPayloadHash 必须是 SHA-256");
  return {
    tenant: { orgId: String(tenant.orgId), projectId: String(tenant.projectId) },
    grantId: text(raw.grantId, "Share grant.grantId"),
    opaqueRef: text(raw.opaqueRef, "Share grant.opaqueRef"),
    assetId: text(raw.assetId, "Share grant.assetId"),
    assetRevision: positiveInt(raw.assetRevision, "Share grant.assetRevision"),
    assetPayloadHash,
    grantorSubject: text(raw.grantorSubject, "Share grant.grantorSubject"),
    granteeScope: raw.granteeScope,
    purpose: "exploration_read",
    markings: [...raw.markings] as string[],
    status: "active",
    issuedAt,
    expiresAt,
    revokedAt: null,
    revokeReason: null,
    version: positiveInt(raw.version, "Share grant.version"),
    blocker: null,
  };
}

export async function resolveSharedExploration(opaqueRef: string): Promise<{ grant: ShareGrantView; exploration: ExplorationAsset }> {
  if (!/^[A-Za-z0-9_-]{16,200}$/.test(opaqueRef)) throw new Error("shareRef 格式无效");
  const raw = record(await apiGetAuthoritative<unknown>(`/v1/ontology/exploration-share-grants/${encodeURIComponent(opaqueRef)}/exploration`), "Shared exploration response");
  exactKeys(raw, ["grant", "exploration"], "Shared exploration response");
  const grant = parseShareGrant(raw.grant);
  const exploration = parseExplorationAsset(raw.exploration);
  if (grant.opaqueRef !== opaqueRef || grant.assetId !== exploration.id || grant.assetRevision !== exploration.revision || grant.assetPayloadHash !== exploration.payloadHash || grant.grantorSubject !== exploration.owner) {
    throw new Error("Share grant 与 exact exploration 引用不一致");
  }
  return { grant, exploration };
}

function idempotencyKey(prefix: string): string {
  const suffix = typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${suffix}`;
}

export async function listExplorations(): Promise<ExplorationAsset[]> {
  const response = await apiGet<{ items: ExplorationAsset[] }>("/v1/ontology/explorations");
  return response.items;
}

export async function createExploration(payload: ExplorationCreate): Promise<ExplorationAsset> {
  const created = await apiPost<ExplorationAsset>(
    "/v1/ontology/explorations",
    payload,
    { "Idempotency-Key": idempotencyKey("exploration") },
  );
  const reread = await apiGet<ExplorationAsset>(`/v1/ontology/explorations/${encodeURIComponent(created.id)}`);
  if (reread.revision !== created.revision || reread.payloadHash !== created.payloadHash) {
    throw new Error("保存后服务端重读不一致");
  }
  return reread;
}

export async function createObjectSet(payload: {
  name: string;
  objectType: string;
  visibility: "private" | "workspace";
  items: ObjectRef[];
}): Promise<RelatedAsset> {
  return apiPost<RelatedAsset>("/v1/ontology/object-sets", payload, {
    "Idempotency-Key": idempotencyKey("object-set"),
  });
}

export async function createAnnotation(payload: {
  title: string;
  body: string;
  subject: {
    subjectType: "object_type" | "object_instance";
    subjectId: string;
    objectRef?: ObjectRef;
  };
  visibility: "private" | "workspace";
  state: "draft";
}): Promise<RelatedAsset> {
  return apiPost<RelatedAsset>("/v1/ontology/annotations", payload, {
    "Idempotency-Key": idempotencyKey("annotation"),
  });
}
