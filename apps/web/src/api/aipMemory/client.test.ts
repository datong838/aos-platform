import { describe, expect, it, vi } from "vitest";
import type { AipClient } from "../aip/client";
import { AipMemorySdk } from "./client";
import { parseKnowledgePipelinePolicies, parseKnowledgeQueryResult, parseMemoryAuthorityItem, parseMemoryCandidate } from "./contracts";

const tenant = { orgId: "org-org", projectId: "dev-project" };
const ref = (resourceType: string, resourceId: string, revision?: string) => ({ resourceType, resourceId, ...(revision ? { revision } : {}), authority: "postgresql" });
const artifact = (artifactId: string) => ({ artifactType: "Artifact", artifactId, revision: "r1", contentHash: "a".repeat(64) });
const source = { sourceKind: "authorized_document", sourceUri: "aos://wiki/page-1", observedAt: "2026-08-12T00:00:00Z", freshnessExpiresAt: "2027-08-12T00:00:00Z", licenseId: "internal", usagePolicy: "aip-retrieval", contentHash: "a".repeat(64), provider: "o1-wiki", providerVersion: "1", applicability: ["skill:content"] };
const request = { candidateLayer: "semantic", taskId: "task-1", runId: "run-1", subject: ref("Product", "p1"), payload: artifact("payload-1"), source, confidence: 0.9, marking: ["internal"] };
const candidate = { tenant, candidateId: "candidate-1", status: "pending", scope: "workspace", version: 1, createdAt: "2026-08-12T00:00:00Z", updatedAt: "2026-08-12T00:00:00Z", request, quarantineReasons: [], governance: null };
const memory = { item: { tenant, memoryItemId: "memory-1", memoryLayer: "semantic", status: "active", scope: "workspace", currentRevision: 1, version: 1, subject: ref("Product", "p1"), createdAt: "2026-08-12T00:00:00Z", updatedAt: "2026-08-12T00:00:00Z" }, revision: { tenant, memoryItemId: "memory-1", revision: 1, candidateId: "candidate-1", contentHash: "a".repeat(64), sourceId: "source-1", sourceRevision: 1, payload: artifact("payload-1"), confidence: 0.9, applicability: ["skill:content"], markings: ["internal"], effectiveAt: "2026-08-12T00:00:00Z", expiresAt: null, createdBy: "reviewer", createdAt: "2026-08-12T00:00:00Z" } };
const citation = { memoryItemId: "memory-1", revision: 1, scope: "workspace", subject: ref("Product", "p1"), payload: artifact("payload-1"), contentHash: "a".repeat(64), source, freshness: "active", confidence: 0.9, applicability: ["skill:content"], markings: ["internal"] };

describe("AipMemorySdk", () => {
  it("通过唯一 AIP client 读取候选和 Memory", async () => {
    const clientRequest = vi.fn().mockResolvedValueOnce([candidate]).mockResolvedValueOnce([memory]);
    const sdk = new AipMemorySdk({ request: clientRequest } as unknown as AipClient);
    await expect(sdk.candidates()).resolves.toMatchObject([{ candidateId: "candidate-1" }]);
    await expect(sdk.memories()).resolves.toMatchObject([{ item: { memoryItemId: "memory-1" } }]);
    expect(clientRequest).toHaveBeenNthCalledWith(1, "listMemoryCandidates");
    expect(clientRequest).toHaveBeenNthCalledWith(2, "listMemoryItems");
  });

  it("事件、审批、晋升全部沿用唯一 client 与严格解析", async () => {
    const event = { tenant, eventId: "event-1", candidateId: "candidate-1", sequence: 1, eventType: "submitted", fromStatus: null, toStatus: "pending", reasonCodes: [], evidenceRef: null, eventHash: "b".repeat(64), actor: "system", occurredAt: "2026-08-12T00:00:00Z" };
    const clientRequest = vi.fn().mockResolvedValueOnce([event]).mockResolvedValueOnce(candidate).mockResolvedValueOnce(memory);
    const sdk = new AipMemorySdk({ request: clientRequest } as unknown as AipClient);
    await expect(sdk.candidateEvents("candidate-1")).resolves.toHaveLength(1);
    await expect(sdk.approveCandidate("candidate-1", { expectedVersion: 1, governance: { evalReport: artifact("eval-1"), draft: ref("Draft", "draft-1", "1"), approvalEvent: ref("ApprovalEvent", "approval-1", "1") }, requiredApplicability: ["skill:content"] })).resolves.toMatchObject({ candidateId: "candidate-1" });
    await expect(sdk.promoteCandidate("candidate-1", { memoryItemId: "memory-1", expectedVersion: 2, requiredApplicability: ["skill:content"] })).resolves.toMatchObject({ item: { memoryItemId: "memory-1" } });
    expect(clientRequest).toHaveBeenNthCalledWith(1, "listMemoryCandidateEvents", { params: { candidate_id: "candidate-1" } });
    expect(clientRequest).toHaveBeenNthCalledWith(2, "approveMemoryCandidate", expect.objectContaining({ params: { candidate_id: "candidate-1" } }));
    expect(clientRequest).toHaveBeenNthCalledWith(3, "promoteMemoryCandidate", expect.objectContaining({ params: { candidate_id: "candidate-1" } }));
  });

  it("缺失 tenant/source/governance 的成功响应失败关闭", () => {
    expect(() => parseMemoryCandidate({ ...candidate, tenant: undefined })).toThrow("tenant");
    expect(() => parseMemoryCandidate({ ...candidate, request: { ...request, source: undefined } })).toThrow("source");
    expect(() => parseMemoryCandidate({ ...candidate, status: "approved" })).toThrow("治理证据");
  });

  it("revision/hash/tenant 漂移失败关闭", () => {
    expect(() => parseMemoryAuthorityItem({ ...memory, item: { ...memory.item, currentRevision: 2 } })).toThrow("revision 不一致");
    expect(() => parseMemoryAuthorityItem({ ...memory, revision: { ...memory.revision, contentHash: "bad" } })).toThrow("sha256");
    expect(() => parseMemoryAuthorityItem({ ...memory, revision: { ...memory.revision, tenant: { orgId: "dev-org", projectId: "dev-project" } } })).toThrow("tenant 不一致");
  });

  it("blocked/degraded token 与 citation 结构严格", () => {
    expect(parseKnowledgeQueryResult({ status: "blocked", citations: [], chunks: [], blockedReasons: ["knowledge_not_found"], assembledTokens: 0 }).status).toBe("blocked");
    expect(parseKnowledgeQueryResult({ status: "degraded", citations: [citation], chunks: [{ citation, content: "知识正文", tokenCount: 4 }], blockedReasons: [], assembledTokens: 4 }).status).toBe("degraded");
    expect(() => parseKnowledgeQueryResult({ status: "complete", citations: [citation], chunks: [], blockedReasons: [], assembledTokens: 0 })).toThrow("不一致");
    expect(() => parseKnowledgeQueryResult({ status: "complete", citations: [citation], chunks: [{ citation: { ...citation, revision: 2 }, content: "知识正文", tokenCount: 4 }], blockedReasons: [], assembledTokens: 4 })).toThrow("引用不一致");
  });

  it("知识管道 SDK 通过唯一 client 严格读取 Schedule/Run/Receipt/Checkpoint/Alert", async () => {
    const schedule = { tenant, scheduleId: "seed-1", pipelineKind: "seed_import", trigger: "manual", config: artifact("config-1"), status: "paused", checkpointVersion: 0, version: 1, nextRunAt: null, createdAt: "2026-08-13T00:00:00Z", updatedAt: "2026-08-13T00:00:00Z" };
    const run = { tenant, pipelineRunId: "pipeline-run-1", scheduleId: "seed-1", taskId: "task-1", runId: "run-1", trigger: "manual", status: "succeeded", attempt: 1, retryOfRunId: null, expectedCheckpointVersion: 0, idempotencyKey: "run-key", requestHash: "b".repeat(64), version: 2, scheduledFor: "2026-08-13T00:00:00Z", leaseOwner: null, leaseExpiresAt: null, startedAt: "2026-08-13T00:00:01Z", finishedAt: "2026-08-13T00:00:02Z", createdAt: "2026-08-13T00:00:00Z", updatedAt: "2026-08-13T00:00:02Z" };
    const receipt = { tenant, receiptId: "receipt-1", pipelineRunId: "pipeline-run-1", status: "succeeded", inputHash: "a".repeat(64), outputHash: "b".repeat(64), candidateRefs: [], checkpointBeforeVersion: 0, checkpointAfterVersion: 1, producedCount: 0, failedCount: 0, errorCodes: [], receiptHash: "c".repeat(64), createdAt: "2026-08-13T00:00:02Z" };
    const checkpoint = { tenant, scheduleId: "seed-1", revision: 1, pipelineRunId: "pipeline-run-1", receiptId: "receipt-1", checkpoint: artifact("checkpoint-1"), checkpointHash: "a".repeat(64), createdAt: "2026-08-13T00:00:02Z" };
    const alert = { tenant, alertId: "alert-1", pipelineRunId: "pipeline-run-1", code: "PIPELINE_PARTIAL", severity: "warning", evidenceRef: ref("aip.pipeline_receipt", "receipt-1", "1"), alertHash: "d".repeat(64), createdAt: "2026-08-13T00:00:02Z" };
    const clientRequest = vi.fn()
      .mockResolvedValueOnce([schedule])
      .mockResolvedValueOnce([run])
      .mockResolvedValueOnce({ receipt })
      .mockResolvedValueOnce({ checkpoint })
      .mockResolvedValueOnce([alert]);
    const sdk = new AipMemorySdk({ request: clientRequest } as unknown as AipClient);
    await expect(sdk.pipelineSchedules()).resolves.toMatchObject([{ scheduleId: "seed-1" }]);
    await expect(sdk.pipelineRuns()).resolves.toMatchObject([{ pipelineRunId: "pipeline-run-1" }]);
    await expect(sdk.pipelineReceipt("pipeline-run-1")).resolves.toMatchObject({ receiptId: "receipt-1" });
    await expect(sdk.pipelineCheckpoint("seed-1")).resolves.toMatchObject({ revision: 1 });
    await expect(sdk.pipelineAlerts("pipeline-run-1")).resolves.toMatchObject([{ code: "PIPELINE_PARTIAL" }]);
  });

  it("知识管道响应缺 authority、hash 或出现未知枚举时失败关闭", () => {
    const policy = { pipelineKind: "seed_import", allowedTriggers: ["manual"], defaultStatus: "paused", requiredDependencies: ["license"], allowedReceiptTypes: ["aip.artifact_receipt"], allowedSourceKinds: ["authorized_document"] };
    expect(parseKnowledgePipelinePolicies([policy])).toHaveLength(1);
    expect(() => parseKnowledgePipelinePolicies([{ ...policy, pipelineKind: "future_pipeline" }])).toThrow("未知");
    expect(() => parseMemoryCandidate({ ...candidate, request: { ...request, subject: { resourceType: "Product", resourceId: "p1" } } })).toThrow("authority");
    expect(() => parseMemoryCandidate({ ...candidate, request: { ...request, payload: { ...artifact("payload-1"), contentHash: "bad" } } })).toThrow("sha256");
  });
});
