import { aipClient, type AipClient } from "../aip/client";
import {
  parseLineageEvents,
  parseEvalRunAuthority,
  parseTelemetrySpans,
  parseUsageReceipts,
  type LineageEvent,
  type LineageRootType,
  type TelemetrySpan,
  type UsageReceipt,
  type EvalRunAuthority,
  type AuthorityEvidenceChain,
} from "./contracts";

export class AipEvidenceSdk {
  constructor(private readonly client: AipClient = aipClient) {}

  async lineage(rootType: LineageRootType, rootId: string): Promise<LineageEvent[]> {
    if (!rootId.trim() || rootId !== rootId.trim()) throw new TypeError("Lineage root id 无效");
    return parseLineageEvents(await this.client.request("listLineageAuthority", {
      params: { root_type: rootType, root_id: rootId },
    }));
  }

  async spans(lineageId: string): Promise<TelemetrySpan[]> {
    if (!lineageId.trim() || lineageId !== lineageId.trim()) throw new TypeError("lineage id 无效");
    return parseTelemetrySpans(await this.client.request("listTelemetrySpans", {
      params: { lineage_id: lineageId },
    }), lineageId);
  }

  async usage(lineageId: string): Promise<UsageReceipt[]> {
    if (!lineageId.trim() || lineageId !== lineageId.trim()) throw new TypeError("lineage id 无效");
    return parseUsageReceipts(await this.client.request("listUsageReceipts", {
      params: { lineage_id: lineageId },
    }), lineageId);
  }

  async evidenceChain(rootType: LineageRootType, rootId: string): Promise<AuthorityEvidenceChain> {
    const events = await this.lineage(rootType, rootId);
    const lineageId = events[0]?.lineageId ?? null;
    if (!lineageId) return { rootType, rootId, lineageId: null, events, spans: [], usageReceipts: [] };
    const [spans, usageReceipts] = await Promise.all([
      this.spans(lineageId),
      this.usage(lineageId),
    ]);
    return { rootType, rootId, lineageId, events, spans, usageReceipts };
  }

  async evalRun(runId: string): Promise<EvalRunAuthority> {
    if (!runId.trim() || runId !== runId.trim()) throw new TypeError("eval run id 无效");
    return parseEvalRunAuthority(await this.client.request("getEvalAuthorityRun", {
      params: { run_id: runId },
    }), runId);
  }
}

export const aipEvidenceSdk = new AipEvidenceSdk();
