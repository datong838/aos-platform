import { apiGet } from "../client";
import { parseModelRuntimeOverview } from "./parser";

export const aipModelRuntime = {
  async overview() { return parseModelRuntimeOverview(await apiGet<unknown>("/v1/aip/model-runtime/overview")); },
};
export * from "./contracts";
export { parseModelRuntimeOverview } from "./parser";
