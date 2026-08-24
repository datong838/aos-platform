import { apiGet, apiPost } from "../client";
import { getTenant } from "../tenant";
import { parseAgentCatalog, parseAgentInstances, parseAgentRun, parseCapabilities, parseHandoff, parseHandoffDecisions, parseInstall, parseRuntimeReadiness } from "./parser";

function segment(value: string, label: string): string {
  const cleaned = value.trim();
  if (!cleaned || cleaned.length > 200 || cleaned.includes("/") || cleaned !== value) throw new TypeError(`${label} 非法`);
  return encodeURIComponent(cleaned);
}

export const aipAgentControl = {
  async listCatalog() { return parseAgentCatalog(await apiGet<unknown>("/v1/aip/agent-registry"), getTenant()); },
  async listInstances() { return parseAgentInstances(await apiGet<unknown>("/v1/aip/agents"), getTenant()); },
  async listCapabilities() { return parseCapabilities(await apiGet<unknown>("/v1/aip/capability-catalog"), getTenant()); },
  async runtimeReadiness() { return parseRuntimeReadiness(await apiGet<unknown>("/v1/aip/agent-registry/runtime-readiness"), getTenant()); },
  async getAgentRun(agentRunId: string) { return parseAgentRun(await apiGet<unknown>(`/v1/aip/agent-runs/${segment(agentRunId, "agentRunId")}`), getTenant()); },
  async getHandoff(handoffId: string) { return parseHandoff(await apiGet<unknown>(`/v1/aip/handoffs/${segment(handoffId, "handoffId")}`), getTenant()); },
  async listHandoffDecisions(handoffId: string) { return parseHandoffDecisions(await apiGet<unknown>(`/v1/aip/handoffs/${segment(handoffId, "handoffId")}/decisions`), getTenant()); },
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
};
export * from "./contracts";
