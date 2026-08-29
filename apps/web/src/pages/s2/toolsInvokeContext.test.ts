import { describe, expect, it } from "vitest";
import {
  buildToolsInvokePayload,
  parseToolsInvokeContext,
  toolsInvokeBlocker,
  validateExactObjectQueryResult,
} from "./toolsInvokeContext";

describe("toolsInvokeContext W-T3", () => {
  it("rejects missing and wo-1001", () => {
    expect(parseToolsInvokeContext(new URLSearchParams())).toBeNull();
    expect(
      parseToolsInvokeContext(new URLSearchParams("objectType=WorkOrder&objectId=wo-1001")),
    ).toBeNull();
    expect(
      toolsInvokeBlocker(null, { draftObjectType: "", draftObjectId: "" }),
    ).toMatch(/缺少精确的业务对象类型/);
    expect(
      toolsInvokeBlocker(null, { draftObjectType: "WorkOrder", draftObjectId: "wo-1001" }),
    ).toMatch(/演示对象已禁用/);
  });

  it("accepts real exact ids", () => {
    const ctx = parseToolsInvokeContext(
      new URLSearchParams("objectType=WorkOrder&objectId=wo-real-9&taskId=task-1"),
    );
    expect(ctx).toEqual(
      expect.objectContaining({ objectType: "WorkOrder", objectId: "wo-real-9", taskId: "task-1" }),
    );
    expect(toolsInvokeBlocker(ctx, { draftObjectType: "", draftObjectId: "" })).toBeNull();
    expect(buildToolsInvokePayload(ctx, { draftObjectType: "", draftObjectId: "" })).toEqual({
      objectType: "WorkOrder",
      objectId: "wo-real-9",
      taskId: "task-1",
    });
  });

  it("accepts only a unique exact object-query result", () => {
    expect(validateExactObjectQueryResult({
      result: { items: [{ id: "order-1" }], total: 1 },
    }, "order-1")).toBeNull();
    expect(validateExactObjectQueryResult({
      result: { items: [{ id: "order-1" }, { id: "order-2" }], total: 2 },
    }, "order-1")).toMatch(/精确对象/);
    expect(validateExactObjectQueryResult({
      result: { items: [{ id: "order-2" }], total: 1 },
    }, "order-1")).toMatch(/不一致/);
  });
});
