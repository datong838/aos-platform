import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ActionDraftBundle, ActionExecutionView, ActionProposalTimeline, AipActionsSdk } from "../api/aipActions";
import { CanonicalDraftInboxPage, actionStatusTab, filterCanonicalProposals } from "./CanonicalDraftInboxPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const hash = "a".repeat(64);
function bundle(status: ActionDraftBundle["proposal"]["status"] = "approved"): ActionDraftBundle {
  return {
    proposal: { id: "proposal-1", actionType: { actionTypeId: "send_notice", revisionHash: hash, objectType: "Order" }, taskId: "task-1", runId: "run-1", objectRef: null, purpose: "发送已审订单通知", riskLevel: "R2", payload: {}, proposalHash: hash, status, expiresAt: "2026-08-12T00:00:00Z", version: 3, createdBy: { actorType: "user", actorId: "maker" }, createdAt: "2026-08-11T00:00:00Z", updatedAt: "2026-08-11T01:00:00Z" },
    draft: { id: "draft-1", proposalId: "proposal-1", proposalVersion: 1, proposalHash: hash, diff: { status: "notified" }, evidenceRefs: [], status, createdAt: "2026-08-11T00:00:00Z" },
    approvals: [{ id: "approval-1", proposalId: "proposal-1", proposalVersion: 2, proposalHash: hash, decision: "approved", actor: { actorType: "user", actorId: "checker" }, reason: "通过", expiresAt: null, createdAt: "2026-08-11T00:30:00Z" }],
  };
}
function execution(item: ActionDraftBundle): ActionExecutionView { return { proposal: item.proposal, lease: null, receipts: [] }; }
function timeline(item: ActionDraftBundle): ActionProposalTimeline { return { bundle: item, events: [{ id: "event-1", type: "approved", actorId: "checker", proposalVersion: 3, proposalHash: hash, payload: {}, createdAt: "2026-08-11T00:30:00Z" }] }; }

function button(host: HTMLElement, label: string): HTMLButtonElement {
  const result = [...host.querySelectorAll<HTMLButtonElement>("button")].find((item) => item.textContent?.includes(label));
  if (!result) throw new Error(`button not found: ${label}`);
  return result;
}

describe("CanonicalDraftInboxPage", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); });

  it("明确区分 approved 与 applied，并从 TaskRun 查询参数筛选", async () => {
    const item = bundle("approved");
    const sdk = { list: vi.fn().mockResolvedValue({ items: [item], count: 1 }), timeline: vi.fn().mockResolvedValue(timeline(item)), execution: vi.fn().mockResolvedValue(execution(item)) } as unknown as AipActionsSdk;
    await act(async () => root.render(<MemoryRouter initialEntries={["/aip/drafts?taskId=task-1&runId=run-1"]}><CanonicalDraftInboxPage sdk={sdk} /></MemoryRouter>));
    await act(async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); });
    expect(host.textContent).toContain("已批准");
    expect(host.textContent).toContain("尚无 Receipt，不能宣称已执行");
    expect(host.textContent).toContain("Task task-1 · Run run-1");
    expect(button(host, "获取单次执行租约").disabled).toBe(false);
  });

  it("服务不可用时展示真实错误空态，不注入示例数据且禁用写按钮", async () => {
    const sdk = { list: vi.fn().mockRejectedValue(new Error("offline")) } as unknown as AipActionsSdk;
    await act(async () => root.render(<MemoryRouter><CanonicalDraftInboxPage sdk={sdk} /></MemoryRouter>));
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(host.textContent).toContain("Action 服务不可用：offline");
    expect(host.querySelector('[data-testid="canonical-action-inbox"]')?.textContent).not.toContain("纯度异常");
    expect([...host.querySelectorAll("button")].some((item) => item.textContent?.includes("执行一次"))).toBe(false);
  });

  it("状态分栏与 task/run 过滤由服务端身份内的 canonical refs 决定", () => {
    const approved = bundle("approved");
    const other = { ...bundle("unknown"), proposal: { ...bundle("unknown").proposal, id: "proposal-2", taskId: "task-2" }, draft: { ...bundle("unknown").draft, id: "draft-2", proposalId: "proposal-2" } };
    expect(actionStatusTab("unknown")).toBe("execution");
    expect(filterCanonicalProposals([approved, other], "approved", "", "task-1", "run-1")).toEqual([approved]);
  });

  it("切换到不含当前 Proposal 的分栏后不保留隐藏详情和写按钮", async () => {
    const item = bundle("approved");
    const sdk = { list: vi.fn().mockResolvedValue({ items: [item], count: 1 }), timeline: vi.fn().mockResolvedValue(timeline(item)), execution: vi.fn().mockResolvedValue(execution(item)) } as unknown as AipActionsSdk;
    await act(async () => root.render(<MemoryRouter><CanonicalDraftInboxPage sdk={sdk} /></MemoryRouter>));
    await act(async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); });
    await act(async () => button(host, "待审批").click());
    expect(host.textContent).toContain("当前筛选下暂无 Proposal");
    expect([...host.querySelectorAll("button")].some((candidate) => candidate.textContent?.includes("获取单次执行租约"))).toBe(false);
  });
});
