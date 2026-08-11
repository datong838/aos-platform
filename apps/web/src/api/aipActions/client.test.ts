import { describe, expect, it, vi } from "vitest";

import type { AipClient } from "../aip/client";
import { AipActionsSdk } from "./client";
import type { ActionProposal } from "./contracts";

const hash = "a".repeat(64);
const proposal: ActionProposal = { id: "proposal-1", actionType: { actionTypeId: "send_notice", revisionHash: hash, objectType: "Order" }, taskId: null, runId: null, objectRef: null, purpose: "发送通知", riskLevel: "R2", payload: {}, proposalHash: hash, status: "drafted", expiresAt: "2026-08-12T00:00:00Z", version: 1, createdBy: { actorType: "user", actorId: "maker" }, createdAt: "2026-08-11T00:00:00Z", updatedAt: "2026-08-11T00:00:00Z" };
const bundle = { proposal, draft: { id: "draft-1", proposalId: "proposal-1", proposalVersion: 1, proposalHash: hash, diff: {}, evidenceRefs: [], status: "awaiting_approval", createdAt: "2026-08-11T00:00:00Z" }, approvals: [] };

describe("AipActionsSdk", () => {
  it("通过唯一 AIP client 列出 Proposal，并绑定精确 version/hash 审批", async () => {
    const request = vi.fn()
      .mockResolvedValueOnce({ items: [bundle], count: 1 })
      .mockResolvedValueOnce({ ...bundle, proposal: { ...proposal, status: "approved", version: 2 } });
    const sdk = new AipActionsSdk({ request } as unknown as AipClient);
    const listed = await sdk.list(100);
    await sdk.decide(listed.items[0], "approved", "通过");
    expect(request).toHaveBeenNthCalledWith(1, "listActionProposals", { params: { limit: "100" } });
    expect(request).toHaveBeenNthCalledWith(2, "decideActionProposal", expect.objectContaining({
      params: { proposal_id: "proposal-1" },
      headers: { "Idempotency-Key": expect.stringMatching(/^action-approved-/) },
      body: expect.objectContaining({ expectedProposalVersion: 1, expectedProposalHash: hash, decision: "approved" }),
    }));
  });

  it("没有 Lease 时禁止执行，不发送请求", async () => {
    const request = vi.fn();
    const sdk = new AipActionsSdk({ request } as unknown as AipClient);
    await expect(sdk.execute({ proposal, lease: null, receipts: [] })).rejects.toThrow("ExecutionLease");
    expect(request).not.toHaveBeenCalled();
  });
});
