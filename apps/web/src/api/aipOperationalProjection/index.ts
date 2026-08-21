import { apiGet } from "../client";
import { getTenant } from "../tenant";
import { parseAipOperationalProjection } from "./parser";

export const aipOperationalProjection = {
  async read() {
    const parsed = parseAipOperationalProjection(await apiGet<unknown>("/v1/aip/operational-projection"));
    const tenant = getTenant();
    if (parsed.tenant.orgId !== tenant.orgId || parsed.tenant.projectId !== tenant.projectId) {
      throw new Error("运行投影租户与当前会话不一致");
    }
    return parsed;
  },
};

export * from "./contracts";
export { parseAipOperationalProjection } from "./parser";
