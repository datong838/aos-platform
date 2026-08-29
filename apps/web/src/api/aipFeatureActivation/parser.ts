import type {
  AipFeatureActivationCommandResponse,
  AipFeatureActivationList,
  AipFeatureActivationProjection,
} from "./contracts";

const HASH = /^sha256:[0-9a-f]{64}$/;
const FEATURE = /^aip\.[a-z0-9]+(?:[.-][a-z0-9]+)*$/;

function object(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new TypeError(`${label} 必须是对象`);
  return value as Record<string, unknown>;
}
function text(value: unknown, label: string): string {
  if (typeof value !== "string" || !value) throw new TypeError(`${label} 必须是非空字符串`);
  return value;
}
function time(value: unknown, label: string): string {
  const result = text(value, label);
  if (!Number.isFinite(Date.parse(result))) throw new TypeError(`${label} 必须是时间戳`);
  return result;
}
function integer(value: unknown, label: string): number {
  if (!Number.isSafeInteger(value) || Number(value) < 1) throw new TypeError(`${label} 必须是正整数`);
  return Number(value);
}
function tenant(value: unknown, label: string): { orgId: string; projectId: string } {
  const raw = object(value, label);
  return { orgId: text(raw.orgId, `${label}.orgId`), projectId: text(raw.projectId, `${label}.projectId`) };
}
function projection(value: unknown, label: string): AipFeatureActivationProjection {
  const raw = object(value, label);
  const featureId = text(raw.featureId, `${label}.featureId`);
  const contentHash = text(raw.contentHash, `${label}.contentHash`);
  if (!FEATURE.test(featureId) || !HASH.test(contentHash)) throw new TypeError(`${label} exact ref 非法`);
  if (!(["active", "superseded", "revoked"] as unknown[]).includes(raw.status)) throw new TypeError(`${label}.status 非法`);
  const expiresAt = raw.expiresAt === null ? null : time(raw.expiresAt, `${label}.expiresAt`);
  return { featureId, revision: integer(raw.revision, `${label}.revision`), contentHash, status: raw.status as AipFeatureActivationProjection["status"], activatedAt: time(raw.activatedAt, `${label}.activatedAt`), expiresAt };
}

export function parseAipFeatureActivationList(value: unknown): AipFeatureActivationList {
  const raw = object(value, "FeatureActivation list");
  if (raw.schemaVersion !== "aos.ecommerce-workshop.feature-activation-list/v1" || !Array.isArray(raw.items)) throw new TypeError("FeatureActivation list 合同非法");
  const items = raw.items.map((item, index) => projection(item, `items[${index}]`));
  if (new Set(items.map((item) => item.featureId)).size !== items.length) throw new TypeError("FeatureActivation featureId 重复");
  return { schemaVersion: raw.schemaVersion, tenant: tenant(raw.tenant, "tenant"), evaluatedAt: time(raw.evaluatedAt, "evaluatedAt"), items };
}

export function parseAipFeatureActivationCommand(value: unknown): AipFeatureActivationCommandResponse {
  const raw = object(value, "FeatureActivation command");
  const receipt = object(raw.receipt, "receipt");
  const featureId = text(receipt.featureId, "receipt.featureId");
  const contentHash = text(receipt.contentHash, "receipt.contentHash");
  if (receipt.schemaVersion !== "aos.ecommerce-workshop.feature-activation-command-receipt/v1" || !FEATURE.test(featureId) || !HASH.test(contentHash)) throw new TypeError("FeatureActivation receipt exact ref 非法");
  if (!(receipt.operation === "activate" || receipt.operation === "revoke") || !(receipt.status === "active" || receipt.status === "revoked")) throw new TypeError("FeatureActivation receipt 状态非法");
  if (typeof raw.replayed !== "boolean") throw new TypeError("FeatureActivation replayed 非法");
  return { tenant: tenant(raw.tenant, "tenant"), replayed: raw.replayed, receipt: { schemaVersion: receipt.schemaVersion, receiptId: text(receipt.receiptId, "receipt.receiptId"), featureId, operation: receipt.operation, revision: integer(receipt.revision, "receipt.revision"), status: receipt.status, contentHash, createdAt: time(receipt.createdAt, "receipt.createdAt") } };
}
