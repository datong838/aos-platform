import { apiGet, apiPost } from "../client";
import { parseAgentCatalog, parseAgentInstances, parseCapabilities, parseInstall } from "./parser";

export const aipAgentControl = {
  async listCatalog() { return parseAgentCatalog(await apiGet<unknown>("/v1/aip/agent-registry")); },
  async listInstances() { return parseAgentInstances(await apiGet<unknown>("/v1/aip/agents")); },
  async listCapabilities() { return parseCapabilities(await apiGet<unknown>("/v1/aip/capability-catalog")); },
  async installEcommerce(idempotencyKey: string) {
    if (!idempotencyKey.trim()) throw new Error("Idempotency-Key 不能为空");
    return parseInstall(await apiPost<unknown>("/v1/aip/agents/install-ecommerce", {}, { "Idempotency-Key": idempotencyKey }));
  },
};
export * from "./contracts";
