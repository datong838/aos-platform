import { afterEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ apiPost: vi.fn(), apiPostReadOnly: vi.fn(), apiGet: vi.fn() }));
vi.mock("../client", () => api);
import { cancelAssistTaskRun, queryAnalyst, streamAssistTurn } from "./client";

afterEach(() => vi.restoreAllMocks());
const base = { threadId: "thread-1", turnId: "turn-1", occurredAt: "2026-08-16T00:00:00Z", context: null, blocker: null, content: null, proposalRef: null, usageRefs: [], lineageRefs: [] };
function frame(name: string, data: unknown) { return `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`; }

describe("aipWorkbench Assist SSE client", () => {
  it("routes Analyst POST through the non-queueing read-only transport", async () => {
    api.apiPostReadOnly.mockRejectedValueOnce(Object.assign(new Error("offline"), { body: { code: "OFFLINE_READ_ONLY" } }));
    await expect(queryAnalyst({ kind: "semantic", objectType: "Order", filters: [], sort: [], selectionRefs: [], pageSize: 1, cutoffAt: "2026-08-16T00:00:00Z" }))
      .rejects.toMatchObject({ body: { code: "OFFLINE_READ_ONLY" } });
    expect(api.apiPostReadOnly).toHaveBeenCalledWith("/v1/aip/analyst/query", expect.objectContaining({ kind: "semantic", objectType: "Order" }));
    expect(api.apiPost).not.toHaveBeenCalled();
  });

  it("cancels through canonical TaskRun control with exact CAS and idempotency", async () => {
    api.apiPost.mockResolvedValue({
      task: {
        id: "task-1", type: "analysis", title: "核查订单", status: "cancelled", priority: 50,
        createdBy: { actorType: "user", actorId: "user-1" }, createdAt: "2026-08-16T00:00:00Z",
        currentPlanRevisionId: "plan-1", version: 8, description: "", goal: {}, selectionRef: null,
        policyRevision: null, updatedAt: "2026-08-16T00:01:00Z",
      },
      run: {
        id: "run-1", taskId: "task-1", planRevisionId: "plan-1", status: "cancelled",
        startedAt: "2026-08-16T00:00:10Z", finishedAt: "2026-08-16T00:01:00Z",
        lastCheckpointId: null, logicGraphId: "logic-1", logicRevision: 3, version: 5,
        createdBy: { actorType: "user", actorId: "user-1" }, createdAt: "2026-08-16T00:00:05Z",
        updatedAt: "2026-08-16T00:01:00Z",
      },
    });
    await expect(cancelAssistTaskRun("run/1", { expectedRunVersion: 4, expectedTaskVersion: 7, reason: "用户取消" }, "cancel-key-1"))
      .resolves.toEqual({ task: { id: "task-1", status: "cancelled", version: 8 }, run: { id: "run-1", status: "cancelled", version: 5 } });
    expect(api.apiPost).toHaveBeenCalledWith(
      "/v1/aip/task-runs/run%2F1/cancel",
      { expectedRunVersion: 4, expectedTaskVersion: 7, reason: "用户取消" },
      { "Idempotency-Key": "cancel-key-1" },
    );
  });

  it("fails closed when TaskRun control response drifts", async () => {
    api.apiPost.mockResolvedValue({ task: {}, run: {}, localSuccess: true });
    await expect(cancelAssistTaskRun("run-1", { expectedRunVersion: 4, expectedTaskVersion: 7, reason: "用户取消" }, "cancel-key-2"))
      .rejects.toThrow("额外字段");
  });

  it("uses canonical endpoint, idempotency and validates persisted sequence", async () => {
    const body = frame("start", { ...base, eventType: "start", sequence: 1 }) + frame("blocked", { ...base, eventType: "blocked", sequence: 2, blocker: { code: "ASSIST_AGENT_RUN_NOT_FOUND", message: "blocked", dependencyRef: null, retryable: false } });
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } }));
    const events = await streamAssistTurn("thread-1", { message: "核查订单", expectedThreadVersion: 1, cutoffAt: "2026-08-16T00:00:00Z" }, "turn-key-1");
    expect(events.at(-1)?.eventType).toBe("blocked");
    const [url, init] = fetch.mock.calls[0];
    expect(String(url)).toContain("/v1/aip/assist/threads/thread-1/turns:stream");
    expect(new Headers(init?.headers).get("Idempotency-Key")).toBe("turn-key-1");
    expect(String(url)).not.toContain("/chat");
  });

  it("fails closed on HTTP and network errors without a local answer", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(JSON.stringify({ message: "runtime blocked" }), { status: 503, headers: { "Content-Type": "application/json" } }));
    await expect(streamAssistTurn("thread-1", { message: "核查订单", expectedThreadVersion: 1, cutoffAt: "2026-08-16T00:00:00Z" }, "turn-key-2")).rejects.toThrow("runtime blocked");
    vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new Error("network unavailable"));
    await expect(streamAssistTurn("thread-1", { message: "核查订单", expectedThreadVersion: 1, cutoffAt: "2026-08-16T00:00:00Z" }, "turn-key-3")).rejects.toThrow("network unavailable");
  });

  it("rejects SSE name drift and missing terminal frames", async () => {
    const start = { ...base, eventType: "start", sequence: 1 };
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(frame("delta", start), { status: 200 }));
    await expect(streamAssistTurn("thread-1", { message: "核查订单", expectedThreadVersion: 1, cutoffAt: "2026-08-16T00:00:00Z" }, "turn-key-4")).rejects.toThrow("名称漂移");
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(frame("start", start), { status: 200 }));
    await expect(streamAssistTurn("thread-1", { message: "核查订单", expectedThreadVersion: 1, cutoffAt: "2026-08-16T00:00:00Z" }, "turn-key-5")).rejects.toThrow("终态");
  });
});
