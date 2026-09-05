import type { MediaDeliveryCandidate, MediaDeliveryExportResponse, MediaDeliveryPublishProposalResponse, MediaDeliveryWorkspaceResponse } from "./contracts";
import { parseMediaInternalWorkflowDraft, parseMediaInternalWorkflowHistory } from "./mediaWorkflowParser";

const SHA256 = /^[a-f0-9]{64}$/;
const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const integer = (value: unknown) => Number.isSafeInteger(value) && Number(value) >= 1;
function tenant(value: unknown): void { if (!isRecord(value) || typeof value.orgId !== "string" || typeof value.projectId !== "string") throw new TypeError("media delivery tenant invalid"); }
function exact(value: unknown, type?: string): void { if (!isRecord(value) || (type !== undefined && value.resourceType !== type) || typeof value.resourceType !== "string" || typeof value.resourceId !== "string" || !integer(value.revision) || typeof value.contentHash !== "string" || !SHA256.test(value.contentHash)) throw new TypeError("media delivery exact ref invalid"); }
function zero(value: unknown): void { if (!isRecord(value) || value.providerInvocationCount !== 0 || value.externalGenerationCount !== 0 || value.feeChargeCount !== 0 || value.publicationCount !== 0 || value.businessMutationCount !== 0) throw new TypeError("media delivery external effects invalid"); }

function candidate(value: unknown): asserts value is MediaDeliveryCandidate {
  if (!isRecord(value) || typeof value.familyId !== "string" || !integer(value.familyVersion) || !Array.isArray(value.impactPreviewRefs) || !Array.isArray(value.reviewIssues) || !Number.isSafeInteger(value.returnDecisionCount) || Number(value.returnDecisionCount) < 0 || typeof value.publishReady !== "boolean" || !Array.isArray(value.blockerCodes)) throw new TypeError("media delivery candidate invalid");
  exact(value.variantRef, "ArtifactRevision"); if (value.gateSetRef !== null) exact(value.gateSetRef, "MediaGateSetDecision");
  if (value.gateReadiness !== null && !["ready", "blocked", "stale", "conflict", "unknown"].includes(String(value.gateReadiness))) throw new TypeError("media delivery gate invalid");
  value.impactPreviewRefs.forEach((item) => exact(item, "ImpactPreviewRevision"));
  for (const item of value.reviewIssues) if (!isRecord(item) || typeof item.issueId !== "string" || !integer(item.version) || !["open", "resolved", "returned", "superseded"].includes(String(item.status)) || !["info", "warning", "error", "critical"].includes(String(item.severity)) || typeof item.returnStage !== "string") throw new TypeError("media delivery review invalid");
  if (value.publishReady !== (value.blockerCodes.length === 0)) throw new TypeError("media delivery readiness drift");
}

export function parseMediaDeliveryWorkspace(value: unknown): MediaDeliveryWorkspaceResponse {
  if (!isRecord(value) || !Array.isArray(value.history) || !Array.isArray(value.candidates) || !Array.isArray(value.blockerCodes) || value.externalEffectsAllowed !== false || !integer(value.historyCount) || value.historyCount !== value.history.length) throw new TypeError("media delivery history or external boundary invalid");
  tenant(value.tenant); const current = parseMediaInternalWorkflowDraft(value.currentDraft); parseMediaInternalWorkflowHistory({ tenant: value.tenant, items: value.history, count: value.historyCount }); value.candidates.forEach(candidate);
  const latest = value.history.at(-1); if (!latest || latest.resourceId !== current.resourceId || latest.revision !== current.revision || latest.contentHash !== current.contentHash) throw new TypeError("media delivery current history drift");
  return value as unknown as MediaDeliveryWorkspaceResponse;
}

export function parseMediaDeliveryExport(value: unknown): MediaDeliveryExportResponse { if (!isRecord(value) || typeof value.fileName !== "string" || value.contentType !== "application/json" || typeof value.content !== "string" || typeof value.contentHash !== "string" || !SHA256.test(value.contentHash)) throw new TypeError("media delivery export invalid"); tenant(value.tenant); zero(value.sideEffects); return value as unknown as MediaDeliveryExportResponse; }
export function parseMediaDeliveryPublishProposal(value: unknown): MediaDeliveryPublishProposalResponse { if (!isRecord(value) || !isRecord(value.proposal) || typeof value.proposal.proposalId !== "string" || !integer(value.proposal.version) || typeof value.proposal.proposalHash !== "string" || !SHA256.test(value.proposal.proposalHash) || typeof value.proposal.status !== "string" || typeof value.message !== "string") throw new TypeError("media delivery Proposal invalid"); tenant(value.tenant); zero(value.sideEffects); return value as unknown as MediaDeliveryPublishProposalResponse; }
