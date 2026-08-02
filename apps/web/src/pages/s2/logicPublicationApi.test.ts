import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));

vi.mock("../../api/client", () => ({ apiGet: api.get, apiPost: api.post }));

import {
  getLogicPublication,
  listLogicPublications,
  publishLogicGraph,
} from "./logicPublicationApi";
import type { LogicPublishRequest } from "./logicPublicationContracts";

const HASH = "a".repeat(64);
const request: LogicPublishRequest = {
  expected_revision: 7,
  expected_graph_hash: HASH,
  eval_suite_id: "suite-1",
  eval_report_id: "report-1",
  idempotency_key: "publish-logic-1-r7",
};

function publication(overrides: Record<string, unknown> = {}) {
  return {
    publication_id: "pub/1",
    graph_id: "logic safe",
    graph_revision: 7,
    graph_hash: HASH,
    dry_run_id: "run-1",
    graph_snapshot: {
      id: "logic safe",
      name: "可信发布",
      description: "",
      status: "draft",
      schema_version: 1,
      revision: 7,
      published_version: null,
      graph_hash: HASH,
      persisted: true,
      nodes: [{ id: "input", kind: "input", label: "输入", position_x: 1, position_y: 2, config: {} }],
      edges: [],
      entry_node_ids: ["input"],
      created_at: "2026-08-02T00:00:00Z",
      updated_at: "2026-08-02T00:01:00Z",
    },
    eval_suite_id: "suite-1",
    eval_report_id: "report-1",
    eval_gate: { gate_passed: true, pass_rate: 1, threshold: 0.92, passed: 1, failed: 0, total: 1, run_at: "2026-08-02T00:00:30Z" },
    actor: "user-1",
    created_at: "2026-08-02T00:02:00Z",
    ...overrides,
  };
}

describe("logicPublicationApi", () => {
  beforeEach(() => vi.clearAllMocks());

  it("读取 publication 列表与详情并编码资源 ID", async () => {
    api.get.mockResolvedValueOnce({ items: [publication()], count: 1 });
    await expect(listLogicPublications("logic safe")).resolves.toMatchObject({ count: 1 });
    expect(api.get).toHaveBeenNthCalledWith(1, "/v1/aip/logic/graphs/logic%20safe/publications");

    api.get.mockResolvedValueOnce(publication());
    await expect(getLogicPublication("logic safe", "pub/1")).resolves.toMatchObject({ publication_id: "pub/1" });
    expect(api.get).toHaveBeenNthCalledWith(2, "/v1/aip/logic/graphs/logic%20safe/publications/pub%2F1");
  });

  it("发布必须 POST 后 GET 同一 publication 严格回读才返回成功", async () => {
    api.post.mockResolvedValueOnce(publication());
    api.get.mockResolvedValueOnce(publication());

    await expect(publishLogicGraph("logic safe", request)).resolves.toMatchObject({ publication_id: "pub/1" });
    expect(api.post).toHaveBeenCalledWith("/v1/aip/logic/graphs/logic%20safe/publish", request);
    expect(api.get).toHaveBeenCalledWith("/v1/aip/logic/graphs/logic%20safe/publications/pub%2F1");
  });

  it("POST 回包错配时不发 GET，回读错配时拒绝成功", async () => {
    api.post.mockResolvedValueOnce(publication({ graph_revision: 8 }));
    await expect(publishLogicGraph("logic safe", request)).rejects.toThrow("graph_revision");
    expect(api.get).not.toHaveBeenCalled();

    api.post.mockResolvedValueOnce(publication());
    api.get.mockResolvedValueOnce(publication({ actor: "other-user" }));
    await expect(publishLogicGraph("logic safe", request)).rejects.toThrow("回读不一致");
  });

  it("拒绝空资源 ID 与不诚实列表", async () => {
    await expect(listLogicPublications(" ")).rejects.toThrow("graphId");
    await expect(getLogicPublication("logic safe", "")).rejects.toThrow("publicationId");
    api.get.mockResolvedValueOnce({ items: [], count: 1 });
    await expect(listLogicPublications("logic safe")).rejects.toThrow("count");
  });
});
