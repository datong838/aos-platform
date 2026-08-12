import { describe, expect, it, vi } from "vitest";
import type { AipClient } from "../aip/client";
import { AipMemorySdk } from "./client";
import { parseKnowledgeQueryResult, parseMemoryAuthorityItem } from "./contracts";

const candidate = { candidateId: "candidate-1", status: "pending", scope: "workspace", version: 1, updatedAt: "2026-08-12T00:00:00Z", request: {}, quarantineReasons: [] };
const memory = { item: { memoryItemId: "memory-1", status: "active", scope: "workspace", currentRevision: 1, subject: {} }, revision: { revision: 1, contentHash: "a".repeat(64), sourceId: "source-1", sourceRevision: 1, applicability: ["skill:content"], markings: ["internal"], effectiveAt: "2026-08-12T00:00:00Z" } };

describe("AipMemorySdk", () => {
  it("通过唯一 AIP client 读取候选和 Memory", async () => { const request = vi.fn().mockResolvedValueOnce([candidate]).mockResolvedValueOnce([memory]); const sdk = new AipMemorySdk({ request } as unknown as AipClient); await expect(sdk.candidates()).resolves.toMatchObject([{ candidateId: "candidate-1" }]); await expect(sdk.memories()).resolves.toMatchObject([{ item: { memoryItemId: "memory-1" } }]); expect(request).toHaveBeenNthCalledWith(1, "listMemoryCandidates"); expect(request).toHaveBeenNthCalledWith(2, "listMemoryItems"); });
  it("revision/hash 漂移失败关闭", () => { expect(() => parseMemoryAuthorityItem({ ...memory, item: { ...memory.item, currentRevision: 2 } })).toThrow("revision 不一致"); expect(() => parseMemoryAuthorityItem({ ...memory, revision: { ...memory.revision, contentHash: "bad" } })).toThrow("sha256"); });
  it("blocked/degraded token 结构严格", () => { expect(parseKnowledgeQueryResult({ status: "blocked", citations: [], chunks: [], blockedReasons: ["knowledge_not_found"], assembledTokens: 0 }).status).toBe("blocked"); expect(() => parseKnowledgeQueryResult({ status: "complete", citations: [{}], chunks: [], blockedReasons: [], assembledTokens: 0 })).toThrow("不一致"); });
});
