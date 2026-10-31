import { apiPostUnqueued } from "./client";

export type GuardDecisionInput = {
  proposalId: string;
  proposalVersion: string;
  proposalHash: string;
  decision: "" | "approved" | "rejected";
};

export type GuardDecisionRequest = {
  decision: "approved" | "rejected";
  expectedProposalVersion: number;
  expectedProposalHash: string;
};

export type GuardDecisionResult = {
  status: "observed" | "unresolved";
  proposalId?: string;
  approvalEventId?: string;
  decision?: "approved" | "rejected";
  activationAuthorized: false;
};

export function buildGuardDecision(input: GuardDecisionInput) {
  const proposalId = input.proposalId.trim();
  if (!proposalId || proposalId.length > 160 || /\s/.test(proposalId)) throw new Error("须填写精确提案 ID");
  if (!/^[1-9]\d*$/.test(input.proposalVersion) || !Number.isSafeInteger(Number(input.proposalVersion))) {
    throw new Error("须填写精确提案版本");
  }
  if (!/^[0-9a-f]{64}$/.test(input.proposalHash)) throw new Error("须填写精确 64 位提案摘要");
  if (input.decision !== "approved" && input.decision !== "rejected") throw new Error("须明确选择批准或拒绝");
  return { proposalId, body: { decision: input.decision, expectedProposalVersion: Number(input.proposalVersion),
    expectedProposalHash: input.proposalHash } satisfies GuardDecisionRequest };
}

export function exactGuardDecisionResult(value: unknown, expected: ReturnType<typeof buildGuardDecision>): value is GuardDecisionResult {
  if (!value || typeof value !== "object") return false;
  const row = value as Partial<GuardDecisionResult>;
  if (row.activationAuthorized !== false || (row.status !== "observed" && row.status !== "unresolved")) return false;
  if (row.status === "unresolved") return row.proposalId === undefined && row.approvalEventId === undefined;
  return row.proposalId === expected.proposalId && row.decision === expected.body.decision
    && typeof row.approvalEventId === "string" && row.approvalEventId.length > 0;
}

export async function sendGuardDecision(input: GuardDecisionInput, idempotencyKey: string, inquiry: boolean) {
  const request = buildGuardDecision(input);
  const suffix = inquiry ? "/inquiry" : "";
  const result = await apiPostUnqueued<unknown>(
    `/v1/aip/runtime-guard-policies/activation-proposals/${encodeURIComponent(request.proposalId)}/decision-intent${suffix}`,
    request.body, { "Idempotency-Key": idempotencyKey },
  );
  if (!exactGuardDecisionResult(result, request)) throw new Error("审批响应与原请求不一致");
  return result;
}
