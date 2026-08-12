import { aipClient, type AipClient } from "../aip/client";
import { parseKnowledgeQueryResult, parseMemoryAuthorityItem, parseMemoryAuthorityItems, parseMemoryCandidate, parseMemoryCandidateEvents, parseMemoryCandidates, type GovernanceApprovalRef, type KnowledgeQueryResult, type MemoryAuthorityItem, type MemoryCandidate, type MemoryCandidateEvent } from "./contracts";

export class AipMemorySdk {
  constructor(private readonly client: AipClient = aipClient) {}
  async candidates(): Promise<MemoryCandidate[]> { return parseMemoryCandidates(await this.client.request("listMemoryCandidates")); }
  async candidate(id: string): Promise<MemoryCandidate> { return parseMemoryCandidate(await this.client.request("getMemoryCandidate", { params: { candidate_id: exactId(id) } })); }
  async candidateEvents(id: string): Promise<MemoryCandidateEvent[]> { return parseMemoryCandidateEvents(await this.client.request("listMemoryCandidateEvents", { params: { candidate_id: exactId(id) } })); }
  async approveCandidate(id: string, input: { expectedVersion: number; governance: GovernanceApprovalRef; requiredApplicability: string[] }): Promise<MemoryCandidate> { return parseMemoryCandidate(await this.client.request("approveMemoryCandidate", { params: { candidate_id: exactId(id) }, body: input })); }
  async promoteCandidate(id: string, input: { memoryItemId: string; expectedVersion: number; requiredApplicability: string[]; expiresAt?: string }): Promise<MemoryAuthorityItem> { return parseMemoryAuthorityItem(await this.client.request("promoteMemoryCandidate", { params: { candidate_id: exactId(id) }, body: input })); }
  async memories(): Promise<MemoryAuthorityItem[]> { return parseMemoryAuthorityItems(await this.client.request("listMemoryItems")); }
  async memory(id: string): Promise<MemoryAuthorityItem> { return parseMemoryAuthorityItem(await this.client.request("getMemoryItem", { params: { memory_item_id: exactId(id) } })); }
  async query(body: Record<string, unknown>): Promise<KnowledgeQueryResult> { return parseKnowledgeQueryResult(await this.client.request("queryMemoryKnowledge", { body })); }
}
function exactId(value: string): string { if (!value.trim() || value !== value.trim()) throw new TypeError("memory id 无效"); return value; }
export const aipMemorySdk = new AipMemorySdk();
