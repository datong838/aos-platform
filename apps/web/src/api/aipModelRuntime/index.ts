import { apiGet, apiPostUnqueued } from "../client";
import { parseModelEvalCandidate, parseModelRouteRevision, parseModelRuntimeChainOverview, parseModelRuntimeCostOverview, parseModelRuntimeOverview, parseProviderInstanceRevision, parseProviderPluginRevision, parseRegisteredModelRevision, parseRuntimePolicyRevision } from "./parser";
import type { ModelRouteRevision, RegisteredModelRevision, RuntimePolicyRevision } from "./contracts";

export const aipModelRuntime = {
  async evalCandidates() { const value = await apiGet<unknown>("/v1/aip/model-runtime/eval-candidates"); if (!Array.isArray(value)) throw new Error("评测候选必须是数组"); return value.map(parseModelEvalCandidate); },
  async overview() { return parseModelRuntimeOverview(await apiGet<unknown>("/v1/aip/model-runtime/overview")); },
  async chainOverview() { return parseModelRuntimeChainOverview(await apiGet<unknown>("/v1/aip/model-runtime/chain-overview")); },
  async costOverview() { return parseModelRuntimeCostOverview(await apiGet<unknown>("/v1/aip/model-runtime/cost-overview")); },
  async provider(providerId: string) { return parseProviderInstanceRevision(await apiGet<unknown>(`/v1/aip/model-runtime/providers/${encodeURIComponent(providerId)}`)); },
  async model(modelId: string, revision?: number) { return parseRegisteredModelRevision(await apiGet<unknown>(`/v1/aip/model-runtime/models/${encodeURIComponent(modelId)}${revision ? `?revision=${revision}` : ""}`)); },
  async policy(policyId: string, revision?: number) { return parseRuntimePolicyRevision(await apiGet<unknown>(`/v1/aip/model-runtime/policies/${encodeURIComponent(policyId)}${revision ? `?revision=${revision}` : ""}`)); },
  async route(routeId: string, revision?: number) { return parseModelRouteRevision(await apiGet<unknown>(`/v1/aip/model-runtime/routes/${encodeURIComponent(routeId)}${revision ? `?revision=${revision}` : ""}`)); },
  async publishModel(item: RegisteredModelRevision, idempotencyKey: string, expectedVersion: number) { return parseRegisteredModelRevision(await apiPostUnqueued<unknown>("/v1/aip/model-runtime/models", item, { "Idempotency-Key": idempotencyKey, "If-Match": String(expectedVersion) })); },
  async publishPolicy(item: RuntimePolicyRevision, idempotencyKey: string, expectedVersion: number) { return parseRuntimePolicyRevision(await apiPostUnqueued<unknown>("/v1/aip/model-runtime/policies", item, { "Idempotency-Key": idempotencyKey, "If-Match": String(expectedVersion) })); },
  async publishRoute(item: ModelRouteRevision, idempotencyKey: string, expectedVersion: number) { return parseModelRouteRevision(await apiPostUnqueued<unknown>("/v1/aip/model-runtime/routes", item, { "Idempotency-Key": idempotencyKey, "If-Match": String(expectedVersion) })); },
  async providerPlugin(pluginId: string, revision: number) { return parseProviderPluginRevision(await apiGet<unknown>(`/v1/aip/model-runtime/provider-plugins/${encodeURIComponent(pluginId)}?revision=${revision}`)); },
  async routeRevisions(routeId: string) { const value = await apiGet<unknown>(`/v1/aip/model-runtime/routes/${encodeURIComponent(routeId)}/revisions`); if (!Array.isArray(value)) throw new Error("路由历史必须是数组"); return value.map(parseModelRouteRevision); },
};
export * from "./contracts";
export { parseModelRouteRevision, parseModelRuntimeChainOverview, parseModelRuntimeCostOverview, parseModelRuntimeOverview, parseProviderInstanceRevision, parseProviderPluginRevision, parseRegisteredModelRevision, parseRuntimePolicyRevision } from "./parser";
