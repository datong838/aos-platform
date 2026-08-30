export type Tenant = { orgId: string; projectId: string };
export type ResourceRef = { resourceType: string; resourceId: string; revision: string | null; authority: string };

export type MarketplaceAgentReadiness = {
  templateId: string;
  displayName: string;
  installed: boolean;
  runtimeReadiness: string;
  blockers: string[];
  repairHref: string;
  repairLabel: string;
};
export type MarketplacePackage = {
  packageId: string;
  version: string;
  contentHash: string;
  displayName: string;
  publisher: string;
  license: string;
  sourceRef: ResourceRef;
  agentCount: number;
  skillCount: number;
  capabilityCount: number;
  installedCount: number;
  runnableCount: number;
  discoverable: boolean;
  installAuthorized: boolean;
  agents: MarketplaceAgentReadiness[];
};

export type MarketplaceCatalog = { tenant: Tenant; items: MarketplacePackage[]; count: number };
export type ImportKind = "agent" | "capability";
export type ImportEvidenceStatus = "unknown" | "passed" | "blocked" | "external_required";
export type ImportSourceFile = { path: string; content: string };
export type ImportPreviewRequest = {
  kind: ImportKind;
  source: {
    sourceRef: ResourceRef;
    sourceCommit: string;
    licenseId: string;
    signatureRef: ResourceRef;
    sbomRef: ResourceRef;
    dependencyRefs: ResourceRef[];
    files: ImportSourceFile[];
  };
  mapping: {
    targetId: string;
    displayName: string;
    toolMappings: Record<string, string>;
    permissionMappings: Record<string, string>;
    inputSchema: Record<string, unknown>;
    outputSchema: Record<string, unknown>;
  };
  security: { riskLevel: "low" | "medium" | "high" | "critical"; networkPolicyRef: string | null; secretRef: string | null };
};
export type ImportStepEvidence = { step: string; status: ImportEvidenceStatus; contentHash: string; blockerCodes: string[]; summary: string };
export type ScanFinding = { ruleId: string; category: string; severity: string; path: string; line: number; message: string; evidenceHash: string };
export type ScanArtifact = {
  scannerId: string; scannerVersion: string; ruleSetHash: string; sourceRef: ResourceRef; sourceCommit: string;
  sourceContentHash: string; licenseId: string; sbomRef: ResourceRef; findings: ScanFinding[];
  status: "passed" | "blocked"; accepted: boolean; artifactHash: string;
};
export type ImportPreview = {
  tenant: Tenant; previewId: string; kind: ImportKind; status: "blocked" | "external_required"; contentHash: string;
  steps: ImportStepEvidence[]; scanArtifact: ScanArtifact; importJobAuthority: "not_created"; approvalRequired: true;
};
export type ImportJobStatus = "awaiting_approval" | "approved" | "applied" | "rolled_back";
export type ImportJob = {
  tenant: Tenant; jobId: string; previewId: string; previewContentHash: string; kind: ImportKind;
  targetId: string; displayName: string; status: ImportJobStatus; conflictDecisions: Record<string, string>;
  approvalEvidenceRef: ResourceRef | null; approvalReason: string | null; rollbackReason: string | null;
  createdRefs: ResourceRef[]; compensatedRefs: ResourceRef[];
  version: number; createdBy: string; approvedBy: string | null; appliedBy: string | null;
  createdAt: string; updatedAt: string;
};
export type ImportCandidate = {
  tenant: Tenant; candidateId: string; jobId: string; kind: ImportKind; targetId: string; displayName: string;
  status: "active" | "rolled_back"; sourceRef: ResourceRef; contentHash: string; createdAt: string; rolledBackAt: string | null;
};
export type ImportJobReceipt = {
  receiptId: string; operation: string; idempotencyKey: string; requestHash: string;
  status: string; createdBy: string; createdAt: string;
};
export type ImportJobMutation = { job: ImportJob; candidate: ImportCandidate | null; receipt: ImportJobReceipt };
