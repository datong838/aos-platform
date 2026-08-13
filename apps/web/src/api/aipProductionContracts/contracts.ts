export type Tenant = { orgId: string; projectId: string };
export type ResourceRef = { resourceType: string; resourceId: string; revision: string | null; authority: string };
export type ExactRevisionRef = { resourceType: string; resourceId: string; revision: number; contentHash: string };

export type TaskBriefRevision = {
  tenant: Tenant;
  briefId: string;
  taskId: string;
  revision: number;
  version: number;
  briefType: string;
  schemaRef: ResourceRef;
  spec: Record<string, unknown>;
  contentHash: string;
  lifecycle: "draft" | "frozen" | "withdrawn" | "superseded";
  createdBy: string;
  createdAt: string;
};

export type EvidenceBundleRevision = {
  tenant: Tenant;
  bundleId: string;
  revision: number;
  briefRef: ExactRevisionRef;
  subjectRefs: ResourceRef[];
  cutoffAt: string;
  itemRefs: ExactRevisionRef[];
  coverage: "complete" | "partial" | "blocked" | "unknown";
  missing: Record<string, unknown>[];
  conflicts: Record<string, unknown>[];
  uncertainties: Record<string, unknown>[];
  freshness: "fresh" | "stale" | "blocked" | "unknown";
  marking: string[];
  licenseSummary: Record<string, unknown>;
  contentHash: string;
  lifecycle: "frozen";
  createdBy: string;
  createdAt: string;
};

export type TaskBriefListResponse = { tenant: Tenant; items: TaskBriefRevision[]; count: number };
export type EvidenceBundleListResponse = { tenant: Tenant; items: EvidenceBundleRevision[]; count: number };

export type CreateTaskBriefInput = {
  taskId: string;
  briefType: string;
  schemaRef: ResourceRef;
  spec: Record<string, unknown>;
};
