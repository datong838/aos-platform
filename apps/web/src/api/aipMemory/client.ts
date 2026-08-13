import { aipClient, type AipClient } from "../aip/client";
import { parseKnowledgePipelineAlerts, parseKnowledgePipelineCheckpointView, parseKnowledgePipelinePolicies, parseKnowledgePipelineReceiptView, parseKnowledgePipelineRun, parseKnowledgePipelineRuns, parseKnowledgePipelineSchedule, parseKnowledgePipelineSchedules, parseKnowledgeQueryResult, parseKnowledgeReadiness, parseMemoryAuthorityItem, parseMemoryAuthorityItems, parseMemoryCandidate, parseMemoryCandidateEvents, parseMemoryCandidates, type GovernanceApprovalRef, type KnowledgePipelineAlert, type KnowledgePipelineCheckpoint, type KnowledgePipelinePolicy, type KnowledgePipelineReceipt, type KnowledgePipelineRun, type KnowledgePipelineSchedule, type KnowledgeQueryResult, type KnowledgeReadiness, type MemoryAuthorityItem, type MemoryCandidate, type MemoryCandidateEvent } from "./contracts";

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
  async knowledgeReadiness(): Promise<KnowledgeReadiness> { return parseKnowledgeReadiness(await this.client.request("getMemoryKnowledgeReadiness")); }
  async pipelinePolicies(): Promise<KnowledgePipelinePolicy[]> { return parseKnowledgePipelinePolicies(await this.client.request("listMemoryPipelinePolicies")); }
  async pipelineSchedules(): Promise<KnowledgePipelineSchedule[]> { return parseKnowledgePipelineSchedules(await this.client.request("listMemoryPipelineSchedules")); }
  async createPipelineSchedule(body: Record<string, unknown>, idempotencyKey: string): Promise<KnowledgePipelineSchedule> { return parseKnowledgePipelineSchedule(await this.client.request("createMemoryPipelineSchedule", { body, headers: { "X-Idempotency-Key": exactId(idempotencyKey) } })); }
  async transitionPipelineSchedule(id: string, body: Record<string, unknown>): Promise<KnowledgePipelineSchedule> { return parseKnowledgePipelineSchedule(await this.client.request("transitionMemoryPipelineSchedule", { params: { schedule_id: exactId(id) }, body })); }
  async pipelineRuns(): Promise<KnowledgePipelineRun[]> { return parseKnowledgePipelineRuns(await this.client.request("listMemoryPipelineRuns")); }
  async createPipelineRun(body: Record<string, unknown>, idempotencyKey: string): Promise<KnowledgePipelineRun> { return parseKnowledgePipelineRun(await this.client.request("createMemoryPipelineRun", { body, headers: { "X-Idempotency-Key": exactId(idempotencyKey) } })); }
  async pipelineReceipt(id: string): Promise<KnowledgePipelineReceipt | null> { return parseKnowledgePipelineReceiptView(await this.client.request("getMemoryPipelineReceipt", { params: { pipeline_run_id: exactId(id) } })); }
  async pipelineCheckpoint(id: string): Promise<KnowledgePipelineCheckpoint | null> { return parseKnowledgePipelineCheckpointView(await this.client.request("getMemoryPipelineCheckpoint", { params: { schedule_id: exactId(id) } })); }
  async pipelineAlerts(id: string): Promise<KnowledgePipelineAlert[]> { return parseKnowledgePipelineAlerts(await this.client.request("listMemoryPipelineAlerts", { params: { pipeline_run_id: exactId(id) } })); }
}
function exactId(value: string): string { if (!value.trim() || value !== value.trim()) throw new TypeError("memory id 无效"); return value; }
export const aipMemorySdk = new AipMemorySdk();
