import { apiPost } from "./client";
import { getTenant } from "./tenant";
import {
  hasKnownGraphMetadata,
  type GraphQuery,
  type GraphSnapshot,
} from "./ontologyExplorerContracts";

function object(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label} 必须是对象`);
  }
  return value as Record<string, unknown>;
}

export function normalizeGraphSnapshot(value: unknown): GraphSnapshot {
  const raw = object(value, "GraphSnapshot");
  const scope = object(raw.scope, "GraphSnapshot.scope");
  const tenant = getTenant();
  if (scope.orgId !== tenant.orgId || scope.workspaceId !== tenant.projectId) {
    throw new Error("GraphSnapshot scope 与当前组织/工作区不一致");
  }
  if (raw.graphDomain !== "domain" && raw.graphDomain !== "operational_lineage") {
    throw new Error("GraphSnapshot graphDomain 无效");
  }
  const expectedAuthority = raw.graphDomain === "domain"
    ? "ecom_authoritative"
    : "operational_authoritative";
  if (raw.sourceAuthority !== expectedAuthority) {
    throw new Error("GraphSnapshot authority 与图域不匹配");
  }
  if (typeof raw.schemaEtag !== "string" || !raw.schemaEtag) {
    throw new Error("GraphSnapshot 缺少 schemaEtag");
  }
  const snapshot = object(raw.snapshot, "GraphSnapshot.snapshot");
  if (typeof snapshot.asOf !== "string" || typeof snapshot.watermark !== "string") {
    throw new Error("GraphSnapshot 缺少权威水位");
  }
  if (!Array.isArray(raw.nodes) || !Array.isArray(raw.edges)) {
    throw new Error("GraphSnapshot nodes/edges 必须是数组");
  }
  const nodeKeys = new Set<string>();
  for (const item of raw.nodes) {
    const node = object(item, "GraphSnapshot.node");
    if (
      typeof node.key !== "string" || !node.key
      || typeof node.objectType !== "string" || !node.objectType
      || typeof node.objectId !== "string" || !node.objectId
      || typeof node.depth !== "number"
      || node.masked !== true
      || nodeKeys.has(node.key)
    ) {
      throw new Error("GraphSnapshot node 不满足稳定引用、脱敏或唯一性合同");
    }
    nodeKeys.add(node.key);
  }
  for (const item of raw.edges) {
    const edge = object(item, "GraphSnapshot.edge");
    if (
      typeof edge.key !== "string" || !edge.key
      || typeof edge.source !== "string" || !nodeKeys.has(edge.source)
      || typeof edge.target !== "string" || !nodeKeys.has(edge.target)
      || !hasKnownGraphMetadata(edge)
      || edge.graphDomain !== raw.graphDomain
      || edge.edgeAuthority !== "authoritative"
    ) {
      throw new Error("GraphSnapshot edge authority 或端点合同无效");
    }
  }
  const page = object(raw.page, "GraphSnapshot.page");
  const limits = object(raw.limits, "GraphSnapshot.limits");
  if (typeof page.truncated !== "boolean" || typeof limits.maxNodes !== "number" || typeof limits.maxHops !== "number") {
    throw new Error("GraphSnapshot page/limits 合同无效");
  }
  return raw as unknown as GraphSnapshot;
}

export async function queryAuthoritativeGraph(query: GraphQuery): Promise<GraphSnapshot> {
  return normalizeGraphSnapshot(await apiPost<unknown>("/v1/ontology/graph/query", query));
}
