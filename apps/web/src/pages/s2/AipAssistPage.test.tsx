// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AipAssistPage, subjectFromSearch } from "./AipAssistPage";
import type { AssistEvent, AssistThread } from "../../api/aipWorkbench";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

function params(): URLSearchParams {
  return new URLSearchParams({
    taskId: "task-1", taskRevision: "1", taskAuthority: "aip-task",
    taskRunId: "run-1", taskRunRevision: "2", taskRunAuthority: "aip-task-run",
    agentRunId: "agent-run-1", agentRunRevision: "3", agentRunAuthority: "aip-agent-run",
    cutoffAt: "2026-08-16T00:00:00Z",
  });
}

describe("AipAssistPage exact subject", () => {
  let host: HTMLDivElement;
  let root: Root;
  beforeEach(() => {
    host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
    window.history.replaceState({}, "", `/?${params().toString()}`);
  });
  afterEach(() => { act(() => root.unmount()); host.remove(); });

  it("accepts only a complete exact upstream subject", () => {
    expect(subjectFromSearch(params())).toEqual(expect.objectContaining({ taskRef: expect.objectContaining({ resourceType: "Task", revision: "1" }), taskRunRef: expect.objectContaining({ resourceType: "TaskRun", revision: "2" }), agentRunRef: expect.objectContaining({ resourceType: "AgentRun", revision: "3" }) }));
  });
  it("does not invent a default AgentRun", () => { const value = params(); value.delete("agentRunAuthority"); expect(subjectFromSearch(value)).toBeNull(); });

  it("使用任务协作助手业务名称，并只把真实近期任务作为上游入口", async () => {
    window.history.replaceState({}, "", "/aip/assist");
    const client = {
      createThread: vi.fn(), streamTurn: vi.fn(), cancelTaskRun: vi.fn(), newKey: vi.fn(() => "key"),
      listRecentTasks: vi.fn().mockResolvedValue([{ id: "task-9", title: "新品内容策划", status: "approved", version: 4, updatedAt: "2026-08-23T08:00:00Z" }]),
    };
    await act(async () => root.render(<MemoryRouter><AipAssistPage client={client} /></MemoryRouter>));
    await act(async () => undefined);
    expect(host.textContent).toContain("任务协作助手");
    expect(host.textContent).toContain("选择最近真实任务");
    expect(host.textContent).toContain("新品内容策划");
    expect(host.textContent).toContain("仍需从真实运行流程补齐任务运行和智能体运行引用");
    expect((host.querySelector("input[aria-label='向当前智能体运行提问']") as HTMLInputElement).disabled).toBe(true);
  });

  it("uses the exact TaskRun ref for the lineage deep link and never guesses a lineageId", async () => {
    const client = { createThread: vi.fn(), streamTurn: vi.fn(), cancelTaskRun: vi.fn(), newKey: vi.fn(() => "key") };
    await act(async () => root.render(<MemoryRouter><AipAssistPage client={client} /></MemoryRouter>));
    expect(host.querySelector<HTMLAnchorElement>("[data-testid='assist-jump-lineage']")?.getAttribute("href"))
      .toBe("/aip/lineage?rootType=task_run&rootId=run-1");
    expect(host.innerHTML).not.toContain("lineageId=");

    act(() => root.unmount());
    root = createRoot(host);
    window.history.replaceState({}, "", "/aip/assist");
    await act(async () => root.render(<MemoryRouter><AipAssistPage client={client} /></MemoryRouter>));
    expect(host.querySelector("[data-testid='assist-lineage-blocked']")).not.toBeNull();
    expect(host.querySelector("[data-testid='assist-jump-lineage']")).toBeNull();
  });
  it("rejects invalid cutoff and partial Task authority", () => {
    const invalidCutoff = params(); invalidCutoff.set("cutoffAt", "not-a-time"); expect(subjectFromSearch(invalidCutoff)).toBeNull();
    const partialTask = params(); partialTask.delete("taskRevision"); expect(subjectFromSearch(partialTask)).toBeNull();
  });

  it("reuses exact thread/turn idempotency keys after transport failure", async () => {
    const keys = ["thread-key", "turn-key"];
    const thread: AssistThread = { tenant: { orgId: "org-org", projectId: "dev-project" }, threadId: "thread-1", subject: subjectFromSearch(params())!, status: "open", version: 1, createdBy: "user-1", createdAt: "2026-08-16T00:00:00Z" };
    const done: AssistEvent[] = [
      { eventType: "start", threadId: "thread-1", turnId: "turn-1", sequence: 1, occurredAt: "2026-08-16T00:00:01Z", context: null, blocker: null, content: null, proposalRef: null, usageRefs: [], lineageRefs: [] },
      { eventType: "done", threadId: "thread-1", turnId: "turn-1", sequence: 2, occurredAt: "2026-08-16T00:00:02Z", context: null, blocker: null, content: null, proposalRef: null, usageRefs: [], lineageRefs: [] },
    ];
    const client = { createThread: vi.fn().mockResolvedValue(thread), streamTurn: vi.fn().mockRejectedValueOnce(new Error("network unavailable")).mockResolvedValueOnce(done), cancelTaskRun: vi.fn(), newKey: vi.fn(() => keys.shift()!) };
    await act(async () => root.render(<MemoryRouter><AipAssistPage client={client} /></MemoryRouter>));
    const input = host.querySelector("input")!;
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    await act(async () => { setter.call(input, "核查订单"); input.dispatchEvent(new Event("input", { bubbles: true })); });
    const send = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "发送")!;
    await act(async () => send.click());
    expect(host.textContent).toContain("network unavailable");
    expect(client.createThread).toHaveBeenCalledTimes(1);
    await act(async () => send.click());
    expect(client.createThread).toHaveBeenCalledTimes(1);
    expect(client.streamTurn).toHaveBeenNthCalledWith(1, "thread-1", expect.any(Object), "turn-key");
    expect(client.streamTurn).toHaveBeenNthCalledWith(2, "thread-1", expect.any(Object), "turn-key");
    expect(client.newKey).toHaveBeenCalledTimes(2);
    expect(host.textContent).toContain("完成");
  });

  it("uses canonical CAS cancellation and retains its key until a persisted result", async () => {
    const client = {
      createThread: vi.fn(), streamTurn: vi.fn(),
      cancelTaskRun: vi.fn().mockRejectedValueOnce(new Error("timeout")).mockResolvedValueOnce({ task: { id: "task-1", status: "cancelled", version: 2 }, run: { id: "run-1", status: "cancelled", version: 3 } }),
      newKey: vi.fn(() => "stable-cancel-key"),
    };
    await act(async () => root.render(<MemoryRouter><AipAssistPage client={client} /></MemoryRouter>));
    const cancel = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "取消任务运行")!;
    await act(async () => cancel.click());
    expect(host.textContent).toContain("timeout");
    await act(async () => cancel.click());
    expect(client.cancelTaskRun).toHaveBeenNthCalledWith(1, "run-1", { expectedRunVersion: 2, expectedTaskVersion: 1, reason: "AIP Assist 用户取消" }, "stable-cancel-key");
    expect(client.cancelTaskRun).toHaveBeenNthCalledWith(2, "run-1", { expectedRunVersion: 2, expectedTaskVersion: 1, reason: "AIP Assist 用户取消" }, "stable-cancel-key");
    expect(client.newKey).toHaveBeenCalledTimes(1);
    expect(host.textContent).toContain("任务运行已取消 · 版本 3");
  });

  it("prevents duplicate Turn submission inside the same event loop", async () => {
    let resolve!: (events: AssistEvent[]) => void;
    const thread: AssistThread = { tenant: { orgId: "org-org", projectId: "dev-project" }, threadId: "thread-1", subject: subjectFromSearch(params())!, status: "open", version: 1, createdBy: "user-1", createdAt: "2026-08-16T00:00:00Z" };
    const client = { createThread: vi.fn().mockResolvedValue(thread), streamTurn: vi.fn(() => new Promise<AssistEvent[]>((done) => { resolve = done; })), cancelTaskRun: vi.fn(), newKey: vi.fn().mockReturnValueOnce("thread-key").mockReturnValueOnce("turn-key") };
    await act(async () => root.render(<MemoryRouter><AipAssistPage client={client} /></MemoryRouter>));
    const input = host.querySelector("input")!;
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    await act(async () => { setter.call(input, "核查订单"); input.dispatchEvent(new Event("input", { bubbles: true })); });
    const send = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "发送")!;
    await act(async () => { send.click(); send.click(); });
    expect(client.createThread).toHaveBeenCalledTimes(1);
    expect(client.streamTurn).toHaveBeenCalledTimes(1);
    await act(async () => resolve([
      { eventType: "start", threadId: "thread-1", turnId: "turn-1", sequence: 1, occurredAt: "2026-08-16T00:00:01Z", context: null, blocker: null, content: null, proposalRef: null, usageRefs: [], lineageRefs: [] },
      { eventType: "done", threadId: "thread-1", turnId: "turn-1", sequence: 2, occurredAt: "2026-08-16T00:00:02Z", context: null, blocker: null, content: null, proposalRef: null, usageRefs: [], lineageRefs: [] },
    ]));
  });

  it("disables cancellation when exact refs are not positive CAS revisions", async () => {
    const invalid = params(); invalid.set("taskRunRevision", "latest");
    window.history.replaceState({}, "", `/?${invalid.toString()}`);
    const client = { createThread: vi.fn(), streamTurn: vi.fn(), cancelTaskRun: vi.fn(), newKey: vi.fn(() => "key") };
    await act(async () => root.render(<MemoryRouter><AipAssistPage client={client} /></MemoryRouter>));
    const cancel = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "取消任务运行")!;
    expect(cancel.disabled).toBe(true);
    expect(cancel.title).toContain("版本不可用于并发安全校验");
    expect(client.cancelTaskRun).not.toHaveBeenCalled();
  });

  it("uses native toolbar buttons for keyboard activation", async () => {
    const client = { createThread: vi.fn(), streamTurn: vi.fn(), cancelTaskRun: vi.fn(), newKey: vi.fn(() => "key") };
    await act(async () => root.render(<MemoryRouter><AipAssistPage client={client} /></MemoryRouter>));
    const collapse = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "收起上下文")!;
    collapse.focus();
    await act(async () => { collapse.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })); });
    expect(collapse.tagName).toBe("BUTTON");
    expect(document.activeElement).toBe(collapse);
    expect(collapse.getAttribute("aria-expanded")).toBe("false");
    const focus = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "专注模式")!;
    await act(async () => { focus.dispatchEvent(new KeyboardEvent("keydown", { key: " ", bubbles: true })); });
    expect(focus.getAttribute("aria-pressed")).toBe("true");
  });
});
