import { apiGet, apiPost } from "../client";
import { getTenant } from "../tenant";
import { parseAgentCatalog, parseAgentInstances, parseAgentRun, parseAgentRunCommand, parseAgentRuns, parseCapabilities, parseDecidedHandoff, parseHandoff, parseHandoffDecisions, parseInstall, parseIssuedHandoff, parseRuntimeReadiness } from "./parser";
import type { AgentInstanceActivationResponse, ConsumeHandoffInput, CreateAgentRunInput, CreateHandoffDecisionInput, IssueHandoffInput } from "./contracts";

function segment(value: string, label: string): string {
  const cleaned = value.trim();
  if (!cleaned || cleaned.length > 200 || cleaned.includes("/") || cleaned !== value) throw new TypeError(`${label} 非法`);
  return encodeURIComponent(cleaned);
}

function keyHeaders(value: string): { "Idempotency-Key": string } {
  if (!value || value !== value.trim() || value.length > 200) throw new TypeError("Idempotency-Key 非法");
  return { "Idempotency-Key": value };
}

export const aipAgentControl = {
  async listCatalog() { return parseAgentCatalog(await apiGet<unknown>("/v1/aip/agent-registry"), getTenant()); },
  async listInstances() { return parseAgentInstances(await apiGet<unknown>("/v1/aip/agents"), getTenant()); },
  async listCapabilities() { return parseCapabilities(await apiGet<unknown>("/v1/aip/capability-catalog"), getTenant()); },
  async runtimeReadiness() { return parseRuntimeReadiness(await apiGet<unknown>("/v1/aip/agent-registry/runtime-readiness"), getTenant()); },
  async getAgentRun(agentRunId: string) { return parseAgentRun(await apiGet<unknown>(`/v1/aip/agent-runs/${segment(agentRunId, "agentRunId")}`), getTenant()); },
  async listAgentRuns(instanceId?: string, limit = 10) {
    if (!Number.isInteger(limit) || limit < 1 || limit > 100) throw new TypeError("limit 非法");
    const query = new URLSearchParams({ limit: String(limit) });
    if (instanceId !== undefined) query.set("instance_id", segment(instanceId, "instanceId"));
    return parseAgentRuns(await apiGet<unknown>(`/v1/aip/agent-runs?${query.toString()}`), getTenant());
  },
  async createAgentRun(input: CreateAgentRunInput, idempotencyKey: string) {
    return parseAgentRunCommand(await apiPost<unknown>("/v1/aip/agent-runs", input, keyHeaders(idempotencyKey)), getTenant(), "agent_run.create");
  },
  async cancelQueuedAgentRun(agentRunId: string, expectedVersion: number, reason: string, idempotencyKey: string) {
    return parseAgentRunCommand(await apiPost<unknown>(`/v1/aip/agent-runs/${segment(agentRunId, "agentRunId")}/cancel-queued`, { expectedVersion, reason }, keyHeaders(idempotencyKey)), getTenant(), "agent_run.cancel_queued");
  },
  async getHandoff(handoffId: string) { return parseHandoff(await apiGet<unknown>(`/v1/aip/handoffs/${segment(handoffId, "handoffId")}`), getTenant()); },
  async listHandoffDecisions(handoffId: string) { return parseHandoffDecisions(await apiGet<unknown>(`/v1/aip/handoffs/${segment(handoffId, "handoffId")}/decisions`), getTenant()); },
  async issueHandoff(input: IssueHandoffInput, idempotencyKey: string) {
    return parseIssuedHandoff(await apiPost<unknown>("/v1/aip/handoffs", input, keyHeaders(idempotencyKey)), getTenant());
  },
  async consumeHandoff(handoffId: string, input: ConsumeHandoffInput) {
    if (!input.bearerToken || input.bearerToken !== input.bearerToken.trim()) throw new TypeError("bearerToken 非法");
    return parseHandoff(await apiPost<unknown>(`/v1/aip/handoffs/${segment(handoffId, "handoffId")}/consume`, input), getTenant());
  },
  async createHandoffDecision(handoffId: string, input: CreateHandoffDecisionInput, idempotencyKey: string) {
    const exactId = segment(handoffId, "handoffId");
    return parseDecidedHandoff(await apiPost<unknown>(`/v1/aip/handoffs/${exactId}/decisions`, input, keyHeaders(idempotencyKey)), getTenant(), handoffId);
  },
  async refreshReadiness(idempotencyKey: string) {
    if (!idempotencyKey.trim()) throw new Error("Idempotency-Key 不能为空");
    return parseRuntimeReadiness(
      await apiPost<unknown>("/v1/aip/agent-registry/refresh-readiness", {}, { "Idempotency-Key": idempotencyKey }),
      getTenant(),
    );
  },
  async installEcommerce(idempotencyKey: string) {
    if (!idempotencyKey.trim()) throw new Error("Idempotency-Key 不能为空");
    return parseInstall(await apiPost<unknown>("/v1/aip/agents/install-ecommerce", {}, { "Idempotency-Key": idempotencyKey }), getTenant());
  },
  async activateAgent(instanceId: string, expectedVersion: number, capabilityBindingIds: string[], idempotencyKey: string) {
    return apiPost<AgentInstanceActivationResponse>(`/v1/aip/agents/${segment(instanceId, "instanceId")}/activate`, { expectedVersion, capabilityBindingIds }, keyHeaders(idempotencyKey));
  },
  async suspendAgent(instanceId: string, expectedVersion: number, reason: string, idempotencyKey: string) {
    return apiPost<AgentInstanceActivationResponse>(`/v1/aip/agents/${segment(instanceId, "instanceId")}/suspend`, { expectedVersion, reason }, keyHeaders(idempotencyKey));
  },
};
export * from "./contracts";
