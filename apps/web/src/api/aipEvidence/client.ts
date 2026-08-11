import { aipClient, type AipClient } from "../aip/client";
import { parseLineageEvents, type LineageEvent, type LineageRootType } from "./contracts";

export class AipEvidenceSdk {
  constructor(private readonly client: AipClient = aipClient) {}

  async lineage(rootType: LineageRootType, rootId: string): Promise<LineageEvent[]> {
    if (!rootId.trim() || rootId !== rootId.trim()) throw new TypeError("Lineage root id 无效");
    return parseLineageEvents(await this.client.request("listLineageAuthority", {
      params: { root_type: rootType, root_id: rootId },
    }));
  }
}

export const aipEvidenceSdk = new AipEvidenceSdk();
