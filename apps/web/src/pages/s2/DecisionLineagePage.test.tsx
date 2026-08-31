import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DecisionLineagePage } from "./aip";

const evidenceMocks = vi.hoisted(() => ({ evidenceChain: vi.fn() }));
const actionMocks = vi.hoisted(() => ({ list: vi.fn() }));
const workbenchMocks = vi.hoisted(() => ({ listAssistSubjects: vi.fn() }));
vi.mock("../../api/aipEvidence", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/aipEvidence")>();
  return { ...original, aipEvidenceSdk: { evidenceChain: evidenceMocks.evidenceChain } };
});
vi.mock("../../api/aipActions", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/aipActions")>();
  return { ...original, aipActionsSdk: { list: actionMocks.list } };
});
vi.mock("../../api/aipWorkbench", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/aipWorkbench")>();
  return { ...original, listAssistSubjects: workbenchMocks.listAssistSubjects };
});

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("DecisionLineagePage authority interaction", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    evidenceMocks.evidenceChain.mockReset();
    actionMocks.list.mockReset();
    actionMocks.list.mockResolvedValue({ items: [], count: 0 });
    workbenchMocks.listAssistSubjects.mockReset();
    workbenchMocks.listAssistSubjects.mockResolvedValue({ tenant: { orgId: "org-org", projectId: "dev-project" }, items: [], count: 0 });
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  it("初始状态不展示固定 Trace 或六段示例", async () => {
    await act(async () => root.render(<MemoryRouter><DecisionLineagePage /></MemoryRouter>));
    expect(host.textContent).toContain("不会展示示例链路或固定步骤");
    expect(host.textContent).not.toContain("tr-8f3a2c91");
    expect(host.textContent).not.toContain("维修派单 Buddy");
    expect(evidenceMocks.evidenceChain).not.toHaveBeenCalled();
  });

  it("真实空列表显示空态且不回填默认步骤", async () => {
    evidenceMocks.evidenceChain.mockResolvedValue({ rootType: "task_run", rootId: "run-1", lineageId: null, events: [], spans: [], usageReceipts: [] });
    await act(async () => root.render(<MemoryRouter><DecisionLineagePage /></MemoryRouter>));
    const input = host.querySelector<HTMLInputElement>("[aria-label='lineage-root-id']")!;
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(input, "run-1");
    await act(async () => input.dispatchEvent(new Event("input", { bubbles: true })));
    const query = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "查询权威谱系")!;
    await act(async () => query.click());
    await flush();
    expect(evidenceMocks.evidenceChain).toHaveBeenCalledWith("task_run", "run-1");
    expect(host.querySelector("[data-testid='lineage-empty']")).not.toBeNull();
    expect(host.querySelector("[data-testid='lineage-authority-timeline']")).toBeNull();
    expect(host.querySelector("[data-testid='lineage-observability-blocked']")).not.toBeNull();
    expect(host.querySelector("[data-testid='lineage-jump-observability']")).toBeNull();
  });

  it("权威事件按服务端序列展示 source 与质量", async () => {
    evidenceMocks.evidenceChain.mockResolvedValue({ rootType: "task_run", rootId: "run-1", lineageId: "lin-1", events: [{
      eventId: "evt-1", lineageId: "lin-1", rootType: "task_run", rootId: "run-1",
      sequence: 1, eventType: "input", payloadHash: "a".repeat(64), quality: "measured",
      occurredAt: "2026-08-12T01:00:00Z", observedAt: "2026-08-12T01:00:01Z",
      sourceKind: "task_run", sourceId: "run-1", sourceHash: "b".repeat(64), subject: null, artifact: null,
    }], spans: [], usageReceipts: [] });
    await act(async () => root.render(<MemoryRouter><DecisionLineagePage /></MemoryRouter>));
    const input = host.querySelector<HTMLInputElement>("[aria-label='lineage-root-id']")!;
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(input, "run-1");
    await act(async () => input.dispatchEvent(new Event("input", { bubbles: true })));
    const query = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "查询权威谱系")!;
    await act(async () => query.click());
    await flush();
    expect(host.textContent).toContain("lin-1");
    expect(host.textContent).toContain("步骤 1");
    expect(host.textContent).toContain("接收业务输入");
    expect(host.textContent).toContain("任务运行");
    expect(host.textContent).toContain("权威实测");
    expect(host.textContent).toContain("缺少观测证据");
    expect(host.textContent).toContain("缺少用量凭证");
    expect(host.querySelector<HTMLAnchorElement>("[data-testid='lineage-jump-observability']")?.getAttribute("href"))
      .toBe("/aip/observability?lineageId=lin-1&rootType=task_run&rootId=run-1");
  });

  it("从最近业务动作进入谱系并保留审批与任务回跳", async () => {
    actionMocks.list.mockResolvedValue({ items: [{
      proposal: {
        id: "proposal-1", actionType: { actionTypeId: "ecommerce.case.classify", revisionHash: "a".repeat(64), objectType: "Order" },
        taskId: "task-1", runId: "run-1", purpose: "复核异常订单并形成处置建议", status: "approved",
      }, draft: { id: "draft-1" }, approvals: [],
    }], count: 1 });
    evidenceMocks.evidenceChain.mockResolvedValue({ rootType: "action", rootId: "proposal-1", lineageId: null, events: [], spans: [], usageReceipts: [] });
    await act(async () => root.render(<MemoryRouter><DecisionLineagePage /></MemoryRouter>));
    await flush();
    const picker = host.querySelector<HTMLSelectElement>("[aria-label='lineage-business-record']")!;
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")?.set?.call(picker, "proposal-1");
    await act(async () => picker.dispatchEvent(new Event("change", { bubbles: true })));
    const query = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "查看业务因果链")!;
    await act(async () => query.click());
    await flush();
    expect(evidenceMocks.evidenceChain).toHaveBeenCalledWith("action", "proposal-1");
    expect(host.textContent).toContain("复核异常订单并形成处置建议");
    expect(host.querySelector<HTMLAnchorElement>('[href="/aip/drafts?proposal=proposal-1"]')).not.toBeNull();
    expect(host.querySelector<HTMLAnchorElement>('[href="/aip/assist?taskId=task-1&runId=run-1"]')).not.toBeNull();
    expect(host.querySelector<HTMLAnchorElement>('[href="/aip/logic?taskId=task-1&runId=run-1"]')).not.toBeNull();
  });

  it("从最近真实任务运行进入谱系", async () => {
    workbenchMocks.listAssistSubjects.mockResolvedValue({ tenant: { orgId: "org-org", projectId: "dev-project" }, items: [{
      subject: {
        taskRef: { resourceType: "Task", resourceId: "task-2", revision: "2", authority: "aip-task-store" },
        taskRunRef: { resourceType: "TaskRun", resourceId: "run-2", revision: "3", authority: "aip-task-store" },
        agentRunRef: { resourceType: "AgentRun", resourceId: "agent-run-2", revision: "1", authority: "aip-agent-run-store" },
        selectionRefs: [], cutoffAt: "2026-08-31T01:00:00Z",
      },
      taskTitle: "复核本周价格异常", taskDescription: "", owner: "价格运营", taskStatus: "executing", runStatus: "running", agentStatus: "running", source: "task", updatedAt: "2026-08-31T01:00:00Z",
    }], count: 1 });
    evidenceMocks.evidenceChain.mockResolvedValue({ rootType: "task_run", rootId: "run-2", lineageId: null, events: [], spans: [], usageReceipts: [] });
    await act(async () => root.render(<MemoryRouter><DecisionLineagePage /></MemoryRouter>));
    await flush();
    const picker = host.querySelector<HTMLSelectElement>("[aria-label='lineage-task-run-record']")!;
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")?.set?.call(picker, "run-2");
    await act(async () => picker.dispatchEvent(new Event("change", { bubbles: true })));
    const query = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "查看业务因果链")!;
    await act(async () => query.click());
    await flush();
    expect(host.textContent).toContain("复核本周价格异常");
    expect(evidenceMocks.evidenceChain).toHaveBeenCalledWith("task_run", "run-2");
  });
});
