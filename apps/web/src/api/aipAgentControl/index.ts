import { apiGet, apiPost } from "../client";
import { getTenant } from "../tenant";
import { parseAgentCatalog, parseAgentInstances, parseCapabilities, parseInstall, parseRuntimeReadiness } from "./parser";

export const aipAgentControl = {
  async listCatalog() { return parseAgentCatalog(await apiGet<unknown>("/v1/aip/agent-registry"), getTenant()); },
  async listInstances() { return parseAgentInstances(await apiGet<unknown>("/v1/aip/agents"), getTenant()); },
  async listCapabilities() { return parseCapabilities(await apiGet<unknown>("/v1/aip/capability-catalog"), getTenant()); },
  async runtimeReadiness() { return parseRuntimeReadiness(await apiGet<unknown>("/v1/aip/agent-registry/runtime-readiness"), getTenant()); },
  async installEcommerce(idempotencyKey: string) {
    if (!idempotencyKey.trim()) throw new Error("Idempotency-Key 不能为空");
    return parseInstall(await apiPost<unknown>("/v1/aip/agents/install-ecommerce", {}, { "Idempotency-Key": idempotencyKey }), getTenant());
  },
};
export * from "./contracts";
