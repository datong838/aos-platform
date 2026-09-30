import { aipClient, type AipClient } from "../aip/client";

export type NetworkDecisionResult = { status: "not_attempted" | "unresolved" }
  | { status: "observed"; eventId: string; decision: "approved" | "rejected" };
export type NetworkDecisionInput = {
  expectedProposalVersion: number;
  expectedProposalHash: string;
  decision: "approved" | "rejected";
  reason: string;
};

function parseResult(value: unknown, allowNotAttempted: boolean): NetworkDecisionResult {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new TypeError("审批查询响应不完整");
  const r = value as Record<string, unknown>;
  if (Object.keys(r).some(k => !["status", "eventId", "decision"].includes(k))) throw new TypeError("审批查询响应字段未知");
  if (r.status === "observed" && typeof r.eventId === "string" && r.eventId.trim() === r.eventId && r.eventId.length > 0
      && (r.decision === "approved" || r.decision === "rejected")) {
    return { status: "observed", eventId: r.eventId, decision: r.decision };
  }
  if ((r.status === "unresolved" || (allowNotAttempted && r.status === "not_attempted"))
      && r.eventId == null && r.decision == null) return { status: r.status as "not_attempted" | "unresolved" };
  throw new TypeError("审批查询缺少有效事件凭证");
}

export class NetworkDecisionSdk {
  constructor(private readonly client: AipClient = aipClient) {}
  async inquire(proposalId: string, version: number): Promise<NetworkDecisionResult> {
    if (!Number.isSafeInteger(version) || version < 1) throw new TypeError("提案版本无效");
    return parseResult(await this.client.request("getNetworkDecisionIntent", {
      params: { proposal_id: proposalId, version: String(version) },
    }), true);
  }
  async submit(proposalId: string, body: NetworkDecisionInput): Promise<NetworkDecisionResult> {
    if (!Number.isSafeInteger(body.expectedProposalVersion) || body.expectedProposalVersion < 1
        || !/^[0-9a-f]{64}$/.test(body.expectedProposalHash) || !body.reason.trim()
        || !["approved", "rejected"].includes(body.decision)) throw new TypeError("审批必须绑定精确提案与意见");
    return parseResult(await this.client.request("submitNetworkDecisionIntent", {
      params: { proposal_id: proposalId }, body,
    }), false);
  }
}

export const networkDecisionSdk = new NetworkDecisionSdk();
