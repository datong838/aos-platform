import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  apiGet: api.get,
  apiPost: api.post,
  apiPut: api.put,
}));

import { createLogicGraph, getLogicGraph, listLogicGraphs, replaceLogicGraph, type LogicGraphDraft } from "./logicGraphApi";

const draft: LogicGraphDraft = {
  id: "logic-safe",
  name: "安全 Logic",
  description: "",
  status: "draft",
  schema_version: 1,
  nodes: [{ id: "input", kind: "input", label: "输入", position_x: 20, position_y: 30, config: {} }],
  edges: [],
  entry_node_ids: ["input"],
};

function snapshot(revision: number, graphHash = `hash-${revision}`) {
  return {
    ...draft,
    revision,
    published_version: null,
    graph_hash: graphHash,
    persisted: true,
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-01T00:00:00Z",
  };
}

describe("logicGraphApi · verified persistence", () => {
  beforeEach(() => vi.clearAllMocks());

  it("creates with a client-stable id and only returns after exact reread", async () => {
    api.post.mockResolvedValue(snapshot(1));
    api.get.mockResolvedValue(snapshot(1));
    await expect(createLogicGraph(draft)).resolves.toMatchObject({ id: draft.id, revision: 1 });
    expect(api.post).toHaveBeenCalledWith("/v1/aip/logic/graphs", expect.objectContaining({ id: draft.id }));
    expect(api.get).toHaveBeenCalledWith("/v1/aip/logic/graphs/logic-safe");
  });

  it("replaces with CAS and rejects a stale or mismatched reread", async () => {
    api.put.mockResolvedValue(snapshot(2, "committed"));
    api.get.mockResolvedValue(snapshot(2, "different"));
    await expect(replaceLogicGraph(draft, 1)).rejects.toThrow("校验和不一致");
    expect(api.put).toHaveBeenCalledWith("/v1/aip/logic/graphs/logic-safe", expect.objectContaining({ expected_revision: 1 }));
  });

  it("fails closed when the save response does not advance exactly one revision", async () => {
    api.put.mockResolvedValue(snapshot(3));
    await expect(replaceLogicGraph(draft, 1)).rejects.toThrow("revision");
    expect(api.get).not.toHaveBeenCalled();
  });

  it("normalizes list/get and rejects dishonest list counts", async () => {
    api.get.mockResolvedValueOnce({ items: [snapshot(1)], count: 1 });
    await expect(listLogicGraphs()).resolves.toMatchObject({ count: 1 });
    api.get.mockResolvedValueOnce({ items: [snapshot(1)], count: 2 });
    await expect(listLogicGraphs()).rejects.toThrow("列表响应不完整");
    api.get.mockResolvedValueOnce(snapshot(1));
    await expect(getLogicGraph("logic-safe")).resolves.toMatchObject({ id: "logic-safe" });
  });
});
