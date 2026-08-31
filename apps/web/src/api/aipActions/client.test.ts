import { describe, expect, it, vi } from "vitest";

import type { AipClient } from "../aip/client";
import { AipActionsSdk } from "./client";
import type { ActionProposal } from "./contracts";

const hash = "a".repeat(64);
const proposal: ActionProposal = { id: "proposal-1", actionType: { actionTypeId: "send_notice", revisionHash: hash, objectType: "Order" }, taskId: null, runId: null, objectRef: null, impactPreviewRef: { resourceType: "ImpactPreviewRevision", resourceId: "preview-1", revision: 2, contentHash: hash }, purpose: "发送通知", riskLevel: "R2", payload: {}, proposalHash: hash, status: "drafted", expiresAt: "2026-08-12T00:00:00Z", version: 1, createdBy: { actorType: "user", actorId: "maker" }, createdAt: "2026-08-11T00:00:00Z", updatedAt: "2026-08-11T00:00:00Z" };
const bundle = { proposal, draft: { id: "draft-1", proposalId: "proposal-1", proposalVersion: 1, proposalHash: hash, diff: {}, evidenceRefs: [], status: "awaiting_approval", createdAt: "2026-08-11T00:00:00Z" }, approvals: [] };
const draftRevision = {
  draftId: "working-draft-1", revision: 1, version: 1, lifecycle: "draft",
  request: {}, actionTypeRevisionHash: hash, riskLevel: "R2", approvalPolicyHash: hash,
  contentHash: hash, submittedProposalId: null,
  createdBy: { actorType: "user", actorId: "maker" }, createdAt: "2026-08-11T00:00:00Z",
};

describe("AipActionsSdk", () => {
  it("通过唯一 AIP client 列出 Proposal，并绑定精确 version/hash 审批", async () => {
    const request = vi.fn()
      .mockResolvedValueOnce({ items: [bundle], count: 1 })
      .mockResolvedValueOnce({ ...bundle, proposal: { ...proposal, status: "approved", version: 2 } });
    const sdk = new AipActionsSdk({ request } as unknown as AipClient);
    const listed = await sdk.list(100);
    expect(listed.items[0].proposal.impactPreviewRef).toEqual({ resourceType: "ImpactPreviewRevision", resourceId: "preview-1", revision: 2, contentHash: hash });
    await sdk.decide(listed.items[0], "approved", "通过");
    expect(request).toHaveBeenNthCalledWith(1, "listActionProposals", { params: { limit: "100" } });
    expect(request).toHaveBeenNthCalledWith(2, "decideActionProposal", expect.objectContaining({
      params: { proposal_id: "proposal-1" },
      headers: { "Idempotency-Key": expect.stringMatching(/^action-approved-/) },
      body: expect.objectContaining({ expectedProposalVersion: 1, expectedProposalHash: hash, decision: "approved" }),
    }));
  });

  it("拒绝 ActionProposal 中漂移的 ImpactPreview exact ref", async () => {
    const request = vi.fn().mockResolvedValue({
      items: [{ ...bundle, proposal: { ...proposal, impactPreviewRef: { resourceType: "ImpactPreviewRevision", resourceId: "preview-1", revision: 2, contentHash: "bad" } } }],
      count: 1,
    });
    const sdk = new AipActionsSdk({ request } as unknown as AipClient);
    await expect(sdk.list()).rejects.toThrow("contentHash 不是 sha256");
  });

  it("没有 Lease 时禁止执行，不发送请求", async () => {
    const request = vi.fn();
    const sdk = new AipActionsSdk({ request } as unknown as AipClient);
    await expect(sdk.execute({ proposal, lease: null, receipts: [] })).rejects.toThrow("ExecutionLease");
    expect(request).not.toHaveBeenCalled();
  });

  it("修改会创建工作草稿并按精确 revision/hash 提交为新提案", async () => {
    const replacement = { ...bundle, proposal: { ...proposal, id: "proposal-2", proposalHash: "b".repeat(64) }, draft: { ...bundle.draft, id: "draft-2", proposalId: "proposal-2", proposalHash: "b".repeat(64) } };
    const request = vi.fn().mockResolvedValueOnce(draftRevision).mockResolvedValueOnce(replacement);
    const sdk = new AipActionsSdk({ request } as unknown as AipClient);
    const result = await sdk.createReplacementProposal(bundle, {
      purpose: "调整通知范围",
      diff: { status: { from: "待处理", to: "已通知" } },
      expiresAt: new Date(Date.now() + 60_000).toISOString(),
    });
    expect(result.proposal.id).toBe("proposal-2");
    expect(request).toHaveBeenNthCalledWith(1, "createActionDraft", expect.objectContaining({
      headers: { "Idempotency-Key": expect.stringMatching(/^action-draft-create-/) },
      body: expect.objectContaining({ actionTypeId: "send_notice", purpose: "调整通知范围" }),
    }));
    expect(request).toHaveBeenNthCalledWith(2, "submitActionDraft", expect.objectContaining({
      params: { draft_id: "working-draft-1" },
      body: { expectedRevision: 1, expectedContentHash: hash },
    }));
  });

  it("补偿只创建独立提案并绑定已确认凭证", async () => {
    const request = vi.fn().mockResolvedValue(bundle);
    const sdk = new AipActionsSdk({ request } as unknown as AipClient);
    await sdk.createCompensation(bundle, "receipt-1", "抵消已确认的通知影响");
    expect(request).toHaveBeenCalledWith("createActionCompensation", expect.objectContaining({
      params: { proposal_id: "proposal-1" },
      headers: { "Idempotency-Key": expect.stringMatching(/^action-compensation-/) },
      body: { receiptId: "receipt-1", purpose: "抵消已确认的通知影响" },
    }));
  });

  it("撤回使用精确版本与哈希且必须填写原因", async () => {
    const withdrawn = { ...bundle, proposal: { ...proposal, status: "withdrawn" as const, version: 4 } };
    const request = vi.fn().mockResolvedValue(withdrawn);
    const sdk = new AipActionsSdk({ request } as unknown as AipClient);
    await sdk.withdraw(bundle, "业务范围已经调整");
    expect(request).toHaveBeenCalledWith("withdrawActionProposal", expect.objectContaining({
      params: { proposal_id: "proposal-1" },
      headers: { "Idempotency-Key": expect.stringMatching(/^action-withdraw-/) },
      body: { expectedProposalVersion: 1, expectedProposalHash: hash, reason: "业务范围已经调整" },
    }));
    request.mockClear();
    await expect(sdk.withdraw(bundle, "  ")).rejects.toThrow("撤回原因不能为空");
    expect(request).not.toHaveBeenCalled();
  });
});
