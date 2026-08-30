import { apiGet, apiPost, apiPostReadOnly } from "../client";
import { getTenant } from "../tenant";
import type { ImportPreview, ImportPreviewRequest } from "./contracts";
import { parseImportJobMutation, parseImportPreview, parseMarketplaceCatalog } from "./parser";

const idempotency = (operation: string) => ({ "Idempotency-Key": `${operation}-${crypto.randomUUID()}` });

export const aipMarketplaceImport = {
  async listMarketplace() {
    return parseMarketplaceCatalog(await apiGet<unknown>("/v1/aip/marketplace/catalog"), getTenant());
  },
  async previewImport(request: ImportPreviewRequest) {
    return parseImportPreview(await apiPostReadOnly<unknown>("/v1/aip/import-previews", request), getTenant());
  },
  async createImportJob(preview: ImportPreview, request: ImportPreviewRequest, conflictDecisions: Record<string, string> = {}) {
    return parseImportJobMutation(await apiPost<unknown>("/v1/aip/import-jobs", { previewRequest: request, expectedPreviewId: preview.previewId, expectedContentHash: preview.contentHash, conflictDecisions }, idempotency("create-import-job")), getTenant());
  },
  async approveImportJob(jobId: string, expectedVersion: number, testEvidenceRef: { resourceType: string; resourceId: string; revision: string | null; authority: string }, decisionReason: string) {
    return parseImportJobMutation(await apiPost<unknown>(`/v1/aip/import-jobs/${encodeURIComponent(jobId)}/approval`, { expectedVersion, testEvidenceRef, decisionReason }, idempotency("approve-import-job")), getTenant());
  },
  async applyImportJob(jobId: string, expectedVersion: number) {
    return parseImportJobMutation(await apiPost<unknown>(`/v1/aip/import-jobs/${encodeURIComponent(jobId)}/apply`, { expectedVersion }, idempotency("apply-import-job")), getTenant());
  },
  async rollbackImportJob(jobId: string, expectedVersion: number, reason: string) {
    return parseImportJobMutation(await apiPost<unknown>(`/v1/aip/import-jobs/${encodeURIComponent(jobId)}/rollback`, { expectedVersion, reason }, idempotency("rollback-import-job")), getTenant());
  },
};
export * from "./contracts";
export * from "./parser";
