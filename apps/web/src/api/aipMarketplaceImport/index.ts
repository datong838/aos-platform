import { apiGet, apiPostReadOnly } from "../client";
import { getTenant } from "../tenant";
import type { ImportPreviewRequest } from "./contracts";
import { parseImportPreview, parseMarketplaceCatalog } from "./parser";

export const aipMarketplaceImport = {
  async listMarketplace() {
    return parseMarketplaceCatalog(await apiGet<unknown>("/v1/aip/marketplace/catalog"), getTenant());
  },
  async previewImport(request: ImportPreviewRequest) {
    return parseImportPreview(await apiPostReadOnly<unknown>("/v1/aip/import-previews", request), getTenant());
  },
};
export * from "./contracts";
export * from "./parser";
