export type Tenant = { orgId: string; projectId: string };

export type ResourceRef = {
  resourceType: string;
  resourceId: string;
  revision: string;
  authority: string;
};

export type QueryFilter = {
  field: string;
  operator: "eq" | "neq" | "lt" | "lte" | "gt" | "gte" | "in" | "contains";
  value: unknown;
};

export type QuerySort = { field: string; direction: "asc" | "desc" };

export type SemanticQuery = {
  kind: "semantic";
  objectType: string;
  filters: QueryFilter[];
  sort: QuerySort[];
  selectionRefs: ResourceRef[];
  pageSize: number;
  cutoffAt: string;
};

export type KnowledgeQuery = {
  kind: "knowledge";
  query: string;
  taskRef: ResourceRef;
  skillRef: ResourceRef;
  selectionRefs: ResourceRef[];
  markings: string[];
  maxTokens: number;
  cutoffAt: string;
};

export type MetricQuery = {
  kind: "metric";
  metricRef: ResourceRef;
  dimensions: string[];
  filters: QueryFilter[];
  selectionRefs: ResourceRef[];
  windowStart: string;
  windowEnd: string;
  cutoffAt: string;
};

export type AnalystQuery = SemanticQuery | KnowledgeQuery | MetricQuery;
export type AnalystStatus = "complete" | "empty" | "degraded" | "partial" | "blocked";
export type QueryColumn = {
  key: string;
  label: string;
  valueType: "string" | "number" | "boolean" | "datetime" | "object_ref";
  marking: string | null;
};
export type QueryRow = { rowId: string; values: Record<string, unknown> };
export type QuerySource = {
  ref: ResourceRef;
  contentHash: string;
  cutoffAt: string;
  freshness: "fresh" | "stale" | "unknown";
  markings: string[];
};
export type Blocker = {
  code: string;
  message: string;
  dependencyRef: ResourceRef | null;
  retryable: boolean;
};
export type QueryResultRevision = {
  tenant: Tenant;
  queryId: string;
  revision: number;
  kind: "semantic" | "knowledge" | "metric";
  status: AnalystStatus;
  columns: QueryColumn[];
  rows: QueryRow[];
  sourceRefs: QuerySource[];
  lineageRefs: ResourceRef[];
  blockers: Blocker[];
  uncertainties: string[];
  cutoffAt: string;
  contentHash: string;
  createdAt: string;
};

export type AssistSubject = {
  taskRef: ResourceRef;
  taskRunRef: ResourceRef;
  agentRunRef: ResourceRef;
  selectionRefs: ResourceRef[];
  cutoffAt: string;
};
export type AssistThread = {
  tenant: Tenant;
  threadId: string;
  subject: AssistSubject;
  status: "open" | "blocked" | "closed";
  version: number;
  createdBy: string;
  createdAt: string;
};
export type AssistContext = AssistSubject & {
  tenant: Tenant;
  planRef: ResourceRef;
  agentInstanceRef: ResourceRef;
  skillRef: ResourceRef;
  logicRef: ResourceRef;
  modelRouteRef: ResourceRef;
  policyRef: ResourceRef;
  evalRef: ResourceRef;
  skillBindingRef: ResourceRef;
  capabilityBindingRefs: ResourceRef[];
  knowledgeCitationRefs: ResourceRef[];
  markings: string[];
  readinessBlockers: Blocker[];
  contextHash: string;
};
export type AssistEvent = {
  eventType: "start" | "context" | "blocked" | "delta" | "proposal" | "done" | "error";
  threadId: string;
  turnId: string;
  sequence: number;
  occurredAt: string;
  context: AssistContext | null;
  blocker: Blocker | null;
  content: string | null;
  proposalRef: ResourceRef | null;
  usageRefs: ResourceRef[];
  lineageRefs: ResourceRef[];
};

export type CreateAssistThread = AssistSubject & { title?: string };
export type CreateAssistTurn = { message: string; expectedThreadVersion: number; cutoffAt: string };
