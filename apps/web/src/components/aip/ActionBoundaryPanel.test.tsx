import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import type { ActionDraftBundle, ActionExecutionView } from "../../api/aipActions";
import { ActionBoundaryPanel, deriveActionBoundaryStages } from "./ActionBoundaryPanel";

const hash = "a".repeat(64);
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

function bundle(status: ActionDraftBundle["proposal"]["status"]): ActionDraftBundle {
  return {
    proposal: {
      id: "proposal-1",
      actionType: { actionTypeId: "send_notice", revisionHash: hash, objectType: "Order" },
      taskId: "task-1",
      runId: "run-1",
      objectRef: null,
      impactPreviewRef: null,
      purpose: "发送通知",
      riskLevel: "R2",
      payload: {},
      proposalHash: hash,
      status,
      expiresAt: "2026-08-26T00:00:00Z",
      version: 3,
      createdBy: { actorType: "user", actorId: "maker" },
      createdAt: "2026-08-25T00:00:00Z",
      updatedAt: "2026-08-25T01:00:00Z",
    },
    draft: {
      id: "draft-1",
      proposalId: "proposal-1",
      proposalVersion: 3,
      proposalHash: hash,
      diff: { status: "notified" },
      evidenceRefs: [],
      status,
      createdAt: "2026-08-25T00:00:00Z",
    },
    approvals: status === "drafted" ? [] : [{
      id: "approval-1",
      proposalId: "proposal-1",
      proposalVersion: 3,
      proposalHash: hash,
      decision: "approved",
      actor: { actorType: "user", actorId: "checker" },
      reason: "通过",
      expiresAt: null,
      createdAt: "2026-08-25T00:30:00Z",
    }],
  };
}

function execution(
  item: ActionDraftBundle,
  receiptStatus?: "accepted" | "applied" | "failed" | "unknown" | "reconciled",
  effectReview = false,
): ActionExecutionView {
  const lease = item.proposal.status === "approved" ? null : {
    id: "lease-1",
    proposalId: item.proposal.id,
    proposalHash: hash,
    attempt: 1,
    expiresAt: "2026-08-25T02:00:00Z",
    createdAt: "2026-08-25T01:30:00Z",
  };
  return {
    proposal: item.proposal,
    lease,
    receipts: receiptStatus && lease ? [{
      id: "receipt-1",
      proposalId: item.proposal.id,
      leaseId: lease.id,
      status: receiptStatus,
      providerRequestId: "provider-request-1",
      evidenceRefs: effectReview ? [{ resourceType: "EffectReview", resourceId: "effect-1", revision: "1", authority: "aip-effects" }] : [],
      createdAt: "2026-08-25T01:45:00Z",
      receiptKind: "initial",
      supersedesReceiptId: null,
      requestFingerprint: hash,
      payload: {},
    }] : [],
  };
}

describe("ActionBoundaryPanel", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  it("approved 只完成审批轴，不把专业产物误报为已执行", () => {
    const item = bundle("approved");
    const stages = deriveActionBoundaryStages(item, execution(item));
    expect(stages.find((stage) => stage.id === "approval")?.state).toBe("complete");
    expect(stages.find((stage) => stage.id === "receipt")?.state).toBe("waiting");
    expect(stages.find((stage) => stage.id === "effect")?.state).toBe("waiting");
  });

  it("unknown 只允许进入对账，不报告 Action 或 Effect 成功", () => {
    const item = bundle("unknown");
    act(() => root.render(<ActionBoundaryPanel bundle={item} execution={execution(item, "unknown")} />));
    expect(host.textContent).toContain("结果未知，等待只读对账");
    expect(host.textContent).toContain("外部结果未闭合，禁止推导效果");
  });

  it("applied Receipt 没有 EffectReview 时仍保持效果待复核", () => {
    const item = bundle("applied");
    act(() => root.render(<ActionBoundaryPanel bundle={item} execution={execution(item, "applied")} />));
    expect(host.textContent).toContain("交付凭证已证明外部结果");
    expect(host.textContent).toContain("尚无 exact EffectReview 引用");
  });

  it("普通 EffectReview resource ref 不冒充 exact hash authority", () => {
    const item = bundle("reconciled");
    const stages = deriveActionBoundaryStages(item, execution(item, "reconciled", true));
    expect(stages.find((stage) => stage.id === "effect")?.state).toBe("waiting");
    expect(stages.find((stage) => stage.id === "effect")?.detail).toContain("不含 contentHash");
  });
});
