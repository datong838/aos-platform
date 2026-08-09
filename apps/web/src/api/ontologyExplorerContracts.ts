export const ONTOLOGY_EXPLORER_ERROR_CODES = [
  "TENANT_SCOPE_REQUIRED",
  "TENANT_SCOPE_FORBIDDEN",
  "EXPLORATION_SHARE_FORBIDDEN",
  "EXPLORATION_NOT_FOUND",
  "IDEMPOTENCY_CONFLICT",
  "OBJECT_REFERENCE_UNSTABLE",
  "REVISION_CONFLICT",
  "GRAPH_QUERY_TOO_LARGE",
  "GRAPH_QUERY_INVALID",
  "OBJECT_SET_TYPE_MISMATCH",
  "GRAPH_QUERY_RATE_LIMITED",
  "GRAPH_AUTHORITY_UNAVAILABLE",
  "EXPLORATION_ARCHIVE_REQUIRED",
] as const;

export type OntologyExplorerErrorCode = (typeof ONTOLOGY_EXPLORER_ERROR_CODES)[number];
export type ExplorationViewMode = "table" | "graph" | "annotation";
export type ExplorationVisibility = "private" | "workspace";
export type GraphDomain = "domain" | "operational_lineage";
export type EdgeAuthority = "authoritative" | "inferred" | "compat_projection";
export type GraphSourceAuthority =
  | "ecom_authoritative"
  | "operational_authoritative"
  | "knowledge_authoritative"
  | "compat_projection";

export type ExplorationCreate = {
  name: string;
  objectType: string;
  viewMode: ExplorationViewMode;
  visibility: ExplorationVisibility;
  query: Record<string, unknown>;
  columns: Record<string, unknown>[];
  graph: Record<string, unknown>;
};

export type ObjectRef = { objectType: string; objectId: string };
export type LinkRef = { relationType: string; source: ObjectRef; target: ObjectRef };
export type KnowledgeSubjectRef = {
  subjectType: "object_type" | "object_instance" | "action_type" | "rule" | "platform" | "task_type";
  subjectId: string;
  objectRef?: ObjectRef | null;
};
export type TaskRef = { taskId: string; revision?: number | null };
export type EvidenceRef = { evidenceId: string; revision: number };
export type ObjectSetCreate = { name: string; objectType: string; items: ObjectRef[] };

export type GraphQuery = {
  seeds: ObjectRef[];
  hops: number;
  maxNodes: number;
  direction: "out" | "in" | "both";
  objectTypes: string[];
  relationTypes: string[];
  graphDomains?: GraphDomain[];
  cursor?: string | null;
};

export type GraphSnapshot = {
  scope: { orgId: string; workspaceId: string };
  sourceAuthority: GraphSourceAuthority;
  graphDomain?: GraphDomain | null;
  schemaEtag: string;
  snapshot: { asOf: string; watermark: string };
  nodes: Array<{ key: string; objectType: string; objectId: string; label: string; depth: number; masked: boolean }>;
  edges: Array<{
    key: string;
    relationType: string;
    source: string;
    target: string;
    direction: "out" | "in";
    graphDomain?: GraphDomain | null;
    edgeAuthority?: EdgeAuthority | null;
    sourceRevision?: string | null;
    validity?: { validFrom?: string | null; validUntil?: string | null } | null;
    evidenceRefs?: EvidenceRef[];
    confidence?: number | null;
    inferenceBasis?: string | null;
  }>;
  page: { truncated: boolean; nextCursor: string | null };
  limits: { maxNodes: number; maxHops: number };
};

export function isOntologyExplorerErrorCode(value: string): value is OntologyExplorerErrorCode {
  return (ONTOLOGY_EXPLORER_ERROR_CODES as readonly string[]).includes(value);
}

export function isGraphDomain(value: unknown): value is GraphDomain {
  return value === "domain" || value === "operational_lineage";
}

export function isEdgeAuthority(value: unknown): value is EdgeAuthority {
  return value === "authoritative" || value === "inferred" || value === "compat_projection";
}

export function hasKnownGraphMetadata(value: {
  graphDomain?: unknown;
  edgeAuthority?: unknown;
}): value is { graphDomain: GraphDomain; edgeAuthority: EdgeAuthority } {
  return isGraphDomain(value.graphDomain) && isEdgeAuthority(value.edgeAuthority);
}
