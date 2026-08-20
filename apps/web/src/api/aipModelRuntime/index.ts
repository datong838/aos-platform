import { apiGet } from "../client";
import { parseModelRuntimeOverview, parseProviderInstanceRevision, parseProviderPluginRevision } from "./parser";

export const aipModelRuntime = {
  async overview() { return parseModelRuntimeOverview(await apiGet<unknown>("/v1/aip/model-runtime/overview")); },
  async provider(providerId: string) { return parseProviderInstanceRevision(await apiGet<unknown>(`/v1/aip/model-runtime/providers/${encodeURIComponent(providerId)}`)); },
  async providerPlugin(pluginId: string, revision: number) { return parseProviderPluginRevision(await apiGet<unknown>(`/v1/aip/model-runtime/provider-plugins/${encodeURIComponent(pluginId)}?revision=${revision}`)); },
};
export * from "./contracts";
export { parseModelRuntimeOverview, parseProviderInstanceRevision, parseProviderPluginRevision } from "./parser";
