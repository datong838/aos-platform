import { describe, expect, it } from "vitest";
import {
  buildToolsInvokePayload,
  parseToolsInvokeContext,
  toolsInvokeBlocker,
} from "./toolsInvokeContext";

describe("toolsInvokeContext W-T3", () => {
  it("rejects missing and wo-1001", () => {
    expect(parseToolsInvokeContext(new URLSearchParams())).toBeNull();
    expect(
      parseToolsInvokeContext(new URLSearchParams("objectType=WorkOrder&objectId=wo-1001")),
    ).toBeNull();
    expect(
      toolsInvokeBlocker(null, { draftObjectType: "", draftObjectId: "" }),
    ).toMatch(/缺少 exact/);
    expect(
      toolsInvokeBlocker(null, { draftObjectType: "WorkOrder", draftObjectId: "wo-1001" }),
    ).toMatch(/wo-1001/);
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
});
