import { apiGet, apiPost } from "./client";
import type { ExplorationCreate, ObjectRef } from "./ontologyExplorerContracts";

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
