import { describe, expect, it } from "vitest";
import { parseMediaInternalWorkflowCommand, parseMediaInternalWorkflowHistory, parseMediaInternalWorkflowList } from "./mediaWorkflowParser";

const draft = (revision = 1) => ({ resourceType: "TaskBriefRevision", resourceId: "media-brief-1", revision, contentHash: "a".repeat(64), version: revision, mediaType: "short_video", title: "栖月汇商品讲解短视频", summary: "围绕正式商品资料准备内容", details: { mediaType: "short_video", businessObject: "栖月汇商品", lastCommand: "create" }, status: "draft" });
const tenant = { orgId: "org-org", projectId: "dev-project" };

describe("mediaWorkflowParser", () => {
  it("解析零外部副作用命令响应", () => { const value = parseMediaInternalWorkflowCommand({ tenant, command: "create", taskId: "task-1", draft: draft(), receipt: { receiptId: "receipt-1", operation: "task_brief.create", idempotencyKey: "key", replay: false }, sideEffects: { providerInvocationCount: 0, externalGenerationCount: 0, feeChargeCount: 0, publicationCount: 0, businessMutationCount: 0 }, message: "内部任务已创建" }); expect(value.draft.mediaType).toBe("short_video"); });
  it("拒绝副作用、未知 details 和不连续历史", () => { expect(() => parseMediaInternalWorkflowCommand({ tenant, command: "create", taskId: "task-1", draft: draft(), receipt: { receiptId: "receipt-1", operation: "task_brief.create", idempotencyKey: "key", replay: false }, sideEffects: { providerInvocationCount: 1, externalGenerationCount: 0, feeChargeCount: 0, publicationCount: 0, businessMutationCount: 0 }, message: "x" })).toThrow(/side effects/); expect(() => parseMediaInternalWorkflowList({ tenant, items: [{ ...draft(), details: { ...draft().details, secret: "x" } }], count: 1 })).toThrow(/details/); expect(() => parseMediaInternalWorkflowHistory({ tenant, items: [draft(1), draft(3)], count: 2 })).toThrow(/history drift/); });
});
