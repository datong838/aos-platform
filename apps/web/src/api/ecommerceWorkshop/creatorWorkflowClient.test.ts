import { describe, expect, it, vi } from "vitest";

import { EcommerceWorkshopClient } from "./client";

const tenant = { orgId: "org-org", projectId: "dev-project" };
const draft = { resourceType: "TaskBriefRevision" as const, resourceId: "creator-brief-1", revision: 1, contentHash: "a".repeat(64), version: 1, purpose: "outreach_batch", title: "七夕达人邀约", summary: "整理候选范围和邀约目标", details: { channel: "站内邀约" }, status: "draft" };
const response = { tenant, command: "create", taskId: "creator-task-1", draft, receipt: { receiptId: "receipt-1", operation: "task_brief.create", idempotencyKey: "creator-key:creator-brief", replay: false }, sideEffects: { providerInvocationCount: 0, externalOutreachCount: 0, contractSignatureCount: 0, businessMutationCount: 0 }, message: "内部业务草稿已创建。" };

function clientFor(payload: unknown, calls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = []) {
  return new EcommerceWorkshopClient({
    fetch: vi.fn(async (input, init) => { calls.push({ input, init }); return new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } }); }),
    getBaseUrl: () => "http://api.test",
    getAuthHeaders: () => ({ "X-Org-Id": "org-org", "X-Project-Id": "dev-project" }),
  });
}

describe("Creator internal workflow client", () => {
  it("发送租户内草稿命令并验证零外部副作用", async () => {
    const calls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
    const client = clientFor(response, calls);
    await expect(client.executeCreatorInternalWorkflow({ command: "create", purpose: "outreach_batch", title: draft.title, summary: draft.summary, details: draft.details }, "creator-key")).resolves.toMatchObject({ draft: { status: "draft" } });
    expect(calls[0]?.init).toMatchObject({ method: "POST", headers: expect.objectContaining({ "Idempotency-Key": "creator-key" }) });
    expect(String(calls[0]?.input)).toContain("/views/creator-growth/workflow/commands");
  });

  it("读取完整版本历史并拒绝伪造副作用", async () => {
    const client = clientFor({ tenant, items: [draft], count: 1 });
    await expect(client.getCreatorInternalWorkflowHistory("creator-brief-1")).resolves.toMatchObject({ count: 1 });
    const drift = structuredClone(response); drift.sideEffects.externalOutreachCount = 1;
    await expect(clientFor(drift).executeCreatorInternalWorkflow({ command: "create", purpose: "outreach_batch", title: draft.title, summary: draft.summary }, "creator-key")).rejects.toThrow("side effects");
    await expect(clientFor(response).executeCreatorInternalWorkflow({ command: "save", purpose: "outreach_batch", title: draft.title, summary: draft.summary, draftRef: draft }, "creator-key")).rejects.toThrow("parameters invalid");
  });

  it("读取当前租户最新内部草稿列表", async () => {
    const calls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
    const client = clientFor({ tenant, items: [draft], count: 1 }, calls);
    await expect(client.listCreatorInternalWorkflows()).resolves.toMatchObject({ count: 1 });
    expect(String(calls[0]?.input)).toContain("/views/creator-growth/workflow/drafts");
  });
});
