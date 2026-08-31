import { apiGet } from "../client";
import { parseModelRouteRevision, parseModelRuntimeCostOverview, parseModelRuntimeOverview, parseProviderInstanceRevision, parseProviderPluginRevision, parseRegisteredModelRevision } from "./parser";

export const aipModelRuntime = {
  async overview() { return parseModelRuntimeOverview(await apiGet<unknown>("/v1/aip/model-runtime/overview")); },
  async costOverview() { return parseModelRuntimeCostOverview(await apiGet<unknown>("/v1/aip/model-runtime/cost-overview")); },
  async provider(providerId: string) { return parseProviderInstanceRevision(await apiGet<unknown>(`/v1/aip/model-runtime/providers/${encodeURIComponent(providerId)}`)); },
  async model(modelId: string, revision?: number) { return parseRegisteredModelRevision(await apiGet<unknown>(`/v1/aip/model-runtime/models/${encodeURIComponent(modelId)}${revision ? `?revision=${revision}` : ""}`)); },
  async providerPlugin(pluginId: string, revision: number) { return parseProviderPluginRevision(await apiGet<unknown>(`/v1/aip/model-runtime/provider-plugins/${encodeURIComponent(pluginId)}?revision=${revision}`)); },
  async routeRevisions(routeId: string) { const value = await apiGet<unknown>(`/v1/aip/model-runtime/routes/${encodeURIComponent(routeId)}/revisions`); if (!Array.isArray(value)) throw new Error("路由历史必须是数组"); return value.map(parseModelRouteRevision); },
};
export * from "./contracts";
export { parseModelRouteRevision, parseModelRuntimeCostOverview, parseModelRuntimeOverview, parseProviderInstanceRevision, parseProviderPluginRevision, parseRegisteredModelRevision } from "./parser";
