import { aipClient, type AipClient } from "../aip/client";
import { parseKnowledgeQueryResult, parseMemoryAuthorityItem, parseMemoryAuthorityItems, parseMemoryCandidate, parseMemoryCandidates, type KnowledgeQueryResult, type MemoryAuthorityItem, type MemoryCandidate } from "./contracts";

export class AipMemorySdk {
  constructor(private readonly client: AipClient = aipClient) {}
  async candidates(): Promise<MemoryCandidate[]> { return parseMemoryCandidates(await this.client.request("listMemoryCandidates")); }
  async candidate(id: string): Promise<MemoryCandidate> { return parseMemoryCandidate(await this.client.request("getMemoryCandidate", { params: { candidate_id: exactId(id) } })); }
  async memories(): Promise<MemoryAuthorityItem[]> { return parseMemoryAuthorityItems(await this.client.request("listMemoryItems")); }
  async memory(id: string): Promise<MemoryAuthorityItem> { return parseMemoryAuthorityItem(await this.client.request("getMemoryItem", { params: { memory_item_id: exactId(id) } })); }
  async query(body: Record<string, unknown>): Promise<KnowledgeQueryResult> { return parseKnowledgeQueryResult(await this.client.request("queryMemoryKnowledge", { body })); }
}
function exactId(value: string): string { if (!value.trim() || value !== value.trim()) throw new TypeError("memory id 无效"); return value; }
export const aipMemorySdk = new AipMemorySdk();
