import { describe, expect, it, vi } from "vitest";

import type { AipClient } from "../aip/client";
import { AipTasksSdk } from "./client";

const actor = { actorType: "user", actorId: "operator" };
const task = {
  id: "task-1", type: "logic_graph_run", title: "权威运行", description: "", status: "pending",
  priority: 50, goal: {}, selectionRef: null, policyRevision: null, createdBy: actor,
  createdAt: "2026-08-11T01:00:00Z", currentPlanRevisionId: null, version: 1,
  updatedAt: "2026-08-11T01:00:00Z",
};

describe("AipTasksSdk", () => {
  it("通过唯一 AIP client 发起带幂等键的 Task 创建", async () => {
    const request = vi.fn().mockResolvedValue(task);
    const sdk = new AipTasksSdk({ request } as unknown as AipClient);
    await expect(sdk.createTask({ title: "权威运行" })).resolves.toMatchObject({ id: "task-1" });
    expect(request).toHaveBeenCalledWith("createTask", expect.objectContaining({
      body: { title: "权威运行" },
      headers: { "Idempotency-Key": expect.stringMatching(/^task-/) },
    }));
  });

  it("重试工作台内部任务时复用调用方固定的幂等键且不写入请求体", async () => {
    const request = vi.fn().mockResolvedValue(task);
    const sdk = new AipTasksSdk({ request } as unknown as AipClient);
    const input = { title: "复盘栖月汇微商城的订单与商品规模", idempotencyKey: "workshop-task-fixed-1" };
    await sdk.createTask(input);
    await sdk.createTask(input);
    expect(request).toHaveBeenNthCalledWith(1, "createTask", {
      body: { title: input.title },
      headers: { "Idempotency-Key": input.idempotencyKey },
    });
    expect(request).toHaveBeenNthCalledWith(2, "createTask", {
      body: { title: input.title },
      headers: { "Idempotency-Key": input.idempotencyKey },
    });
  });

  it("按 Logic Graph 从服务端发现运行，不读取 localStorage", async () => {
    const request = vi.fn().mockResolvedValue({ items: [], count: 0 });
    const sdk = new AipTasksSdk({ request } as unknown as AipClient);
    await expect(sdk.listRunsByLogic("logic/1", 20)).resolves.toEqual({ items: [], count: 0 });
    expect(request).toHaveBeenCalledWith("listTaskRunsByLogic", {
      params: { logic_graph_id: "logic/1", limit: "20" },
    });
  });
});
