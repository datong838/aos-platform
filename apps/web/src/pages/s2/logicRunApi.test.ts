import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  apiGet: api.get,
  apiPost: api.post,
}));

import { dryRunLogicGraph, getLogicRun, listLogicRuns } from "./logicRunApi";
import type { LogicDryRunRequest } from "./logicRunContracts";

const graphHash = "a".repeat(64);

const request: LogicDryRunRequest = {
  expected_revision: 2,
  dry_run: true,
  expected_graph_hash: graphHash,
  inputs: { workOrder: { status: "open" } },
  idempotency_key: "browser-1",
};

function nodeResult(overrides: Record<string, unknown> = {}) {
  return {
    node_id: "input-1",
    kind: "input",
    status: "executed",
    started_at: "2026-08-01T00:00:00Z",
    finished_at: "2026-08-01T00:00:00.005Z",
    elapsed_ms: 5,
    summary: "输入校验完成",
    output: null,
    usage: null,
    tool_call: null,
    selected_branch_path: null,
    proposed_edits: [],
    error: null,
    truncated: false,
    ...overrides,
  };
}

function dryRun(overrides: Record<string, unknown> = {}) {
  return {
    run_id: "run/1",
    graph_id: "logic safe",
    mode: "dry_run",
    status: "succeeded",
    evaluated_revision: 2,
    graph_hash: graphHash,
    production_written: false,
    started_at: "2026-08-01T00:00:00Z",
    finished_at: "2026-08-01T00:00:00.010Z",
    elapsed_ms: 10,
    total_tokens: null,
    node_results: [nodeResult()],
    proposed_edits: [],
    error: null,
    ...overrides,
  };
}

function summary(overrides: Record<string, unknown> = {}) {
  return {
    run_id: "run/1",
    graph_id: "logic safe",
    mode: "dry_run",
    status: "succeeded",
    evaluated_revision: 2,
    graph_hash: graphHash,
    production_written: false,
    started_at: "2026-08-01T00:00:00Z",
    finished_at: "2026-08-01T00:00:00.010Z",
    elapsed_ms: 10,
    total_tokens: null,
    node_counts: { executed: 1, skipped: 0, failed: 0, canceled: 0 },
    error_code: null,
    ...overrides,
  };
}

describe("logicRunApi · canonical dry-run", () => {
  beforeEach(() => vi.clearAllMocks());

  it("posts only the frozen request and returns only after exact detail reread", async () => {
    api.post.mockResolvedValue(dryRun());
    api.get.mockResolvedValue(dryRun());

    await expect(dryRunLogicGraph("logic safe", request, ["input-1"])).resolves.toMatchObject({
      run_id: "run/1",
      graph_id: "logic safe",
      production_written: false,
    });

    expect(api.post).toHaveBeenCalledWith(
      "/v1/aip/logic/graphs/logic%20safe/dry-run",
      request,
    );
    expect(api.get).toHaveBeenCalledWith(
      "/v1/aip/logic/graphs/logic%20safe/runs/run%2F1",
    );
  });

  it("fails closed when detail is absent or differs from the POST evidence", async () => {
    api.post.mockResolvedValue(dryRun());
    api.get.mockRejectedValueOnce(new Error("detail unavailable"));
    await expect(dryRunLogicGraph("logic safe", request, ["input-1"])).rejects.toThrow(
      "响应已收到，但历史持久化核验失败：detail unavailable",
    );

    api.get.mockResolvedValueOnce(dryRun({ status: "failed" }));
    await expect(dryRunLogicGraph("logic safe", request, ["input-1"])).rejects.toThrow(
      "历史持久化核验失败",
    );
  });

  it("does not POST malformed requests or reread an unsafe response", async () => {
    await expect(dryRunLogicGraph("logic safe", {
      ...request,
      dry_run: false as true,
    }, ["input-1"])).rejects.toThrow("严格为 true");
    expect(api.post).not.toHaveBeenCalled();

    api.post.mockResolvedValue(dryRun({ production_written: true }));
    await expect(dryRunLogicGraph("logic safe", request, ["input-1"])).rejects.toThrow("严格为 false");
    expect(api.get).not.toHaveBeenCalled();
  });

  it("bubbles a 409 without fabricating or requesting history", async () => {
    const conflict = Object.assign(new Error("revision conflict"), { status: 409 });
    api.post.mockRejectedValue(conflict);
    await expect(dryRunLogicGraph("logic safe", request, ["input-1"])).rejects.toBe(conflict);
    expect(api.get).not.toHaveBeenCalled();
  });
});

describe("logicRunApi · history list/detail", () => {
  beforeEach(() => vi.clearAllMocks());

  it("loads strict paginated summaries with encoded graph and cursor", async () => {
    api.get.mockResolvedValue({ items: [summary()], count: 1, next_cursor: "next" });
    await expect(listLogicRuns("logic safe", { limit: 50, before: "cursor/1" })).resolves.toMatchObject({
      count: 1,
      next_cursor: "next",
    });
    expect(api.get).toHaveBeenCalledWith(
      "/v1/aip/logic/graphs/logic%20safe/runs?limit=50&before=cursor%2F1",
    );
  });

  it("loads full detail and verifies graph/run ids against the path", async () => {
    api.get.mockResolvedValue(dryRun());
    await expect(getLogicRun("logic safe", "run/1")).resolves.toMatchObject({ run_id: "run/1" });
    api.get.mockResolvedValueOnce(dryRun({ run_id: "other" }));
    await expect(getLogicRun("logic safe", "run/1")).rejects.toThrow("run_id");
    api.get.mockResolvedValueOnce(dryRun({ graph_id: "other" }));
    await expect(getLogicRun("logic safe", "run/1")).rejects.toThrow("graph_id");
  });

  it("rejects invalid pagination before I/O and never falls back to demo history", async () => {
    await expect(listLogicRuns("logic safe", { limit: 101 })).rejects.toThrow("1 到 100");
    expect(api.get).not.toHaveBeenCalled();
    const networkError = new Error("offline");
    api.get.mockRejectedValue(networkError);
    await expect(listLogicRuns("logic safe")).rejects.toBe(networkError);
    expect(api.get).toHaveBeenCalledTimes(1);
  });

  it("rejects private reasoning in either list or detail", async () => {
    api.get.mockResolvedValueOnce({ items: [summary({ chain_of_thought: "private" })], count: 1, next_cursor: null });
    await expect(listLogicRuns("logic safe")).rejects.toThrow("模型私有推理字段");
    api.get.mockResolvedValueOnce(dryRun({ node_results: [nodeResult({ output: { cot: "private" } })] }));
    await expect(getLogicRun("logic safe", "run/1")).rejects.toThrow("模型私有推理字段");
  });
});
