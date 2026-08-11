import { describe, expect, it } from "vitest";

import { parseActionDraftBundle, parseActionExecution, parseActionProposalList } from "./contracts";

const hash = "a".repeat(64);
const proposal = {
  id: "proposal-1", actionType: { actionTypeId: "send_notice", revisionHash: hash, objectType: "Order" },
  taskId: "task-1", runId: "run-1", objectRef: null, purpose: "发送已审通知", riskLevel: "R2",
  payload: { orderId: "order-1" }, proposalHash: hash, status: "approved",
  expiresAt: "2026-08-12T00:00:00Z", version: 3, createdBy: { actorType: "user", actorId: "maker" },
  createdAt: "2026-08-11T00:00:00Z", updatedAt: "2026-08-11T01:00:00Z",
};
const draft = {
  id: "draft-1", proposalId: "proposal-1", proposalVersion: 1, proposalHash: hash,
  diff: { status: "notified" }, evidenceRefs: [], status: "approved", createdAt: "2026-08-11T00:00:00Z",
};
const bundle = { proposal, draft, approvals: [{ id: "approval-1", proposalId: "proposal-1", proposalVersion: 2, proposalHash: hash, decision: "approved", actor: { actorType: "user", actorId: "checker" }, reason: "通过", expiresAt: null, createdAt: "2026-08-11T00:30:00Z" }] };

describe("aipActions contracts", () => {
  it("严格解析互相一致的 Proposal/Draft/Approval", () => {
    expect(parseActionDraftBundle(bundle).proposal.status).toBe("approved");
    expect(parseActionProposalList({ items: [bundle], count: 1 }).count).toBe(1);
  });

  it("未知状态、跨资源引用和重复 Receipt 均失败关闭", () => {
    expect(() => parseActionDraftBundle({ ...bundle, proposal: { ...proposal, status: "done" } })).toThrow("未知");
    expect(() => parseActionDraftBundle({ ...bundle, draft: { ...draft, proposalId: "other" } })).toThrow("引用不一致");
    const receipt = { id: "receipt-1", proposalId: "proposal-1", leaseId: "lease-1", status: "applied", providerRequestId: "provider-1", evidenceRefs: [], createdAt: "2026-08-11T02:00:00Z", receiptKind: "initial", supersedesReceiptId: null, requestFingerprint: hash, payload: {} };
    expect(() => parseActionExecution({ proposal: { ...proposal, status: "applied" }, lease: { id: "lease-1", proposalId: "proposal-1", proposalHash: hash, attempt: 1, expiresAt: "2026-08-11T02:10:00Z", createdAt: "2026-08-11T02:00:00Z" }, receipts: [receipt, receipt] })).toThrow("重复");
  });
});
