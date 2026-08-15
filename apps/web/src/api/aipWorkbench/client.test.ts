import { afterEach, describe, expect, it, vi } from "vitest";
import { streamAssistTurn } from "./client";

afterEach(() => vi.restoreAllMocks());
const base = { threadId: "thread-1", turnId: "turn-1", occurredAt: "2026-08-16T00:00:00Z", context: null, blocker: null, content: null, proposalRef: null, usageRefs: [], lineageRefs: [] };
function frame(name: string, data: unknown) { return `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`; }

describe("aipWorkbench Assist SSE client", () => {
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
});
