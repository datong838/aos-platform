import { describe, expect, it } from "vitest";

import {
  assertDryRunDetailMatches,
  assertLogicDryRunRequest,
  normalizeLogicDryRun,
  normalizeLogicRunList,
  type LogicDryRunRequest,
} from "./logicRunContracts";

const graphHash = "a".repeat(64);

function request(overrides: Record<string, unknown> = {}): LogicDryRunRequest {
  return {
    expected_revision: 2,
    dry_run: true,
    expected_graph_hash: graphHash,
    inputs: { workOrder: { status: "open" } },
    ...overrides,
  } as LogicDryRunRequest;
}

function nodeResult(overrides: Record<string, unknown> = {}) {
  return {
    node_id: "input-1",
    kind: "input",
    status: "executed",
    started_at: "2026-08-01T00:00:00Z",
    finished_at: "2026-08-01T00:00:00.005Z",
    elapsed_ms: 5,
    summary: "输入校验完成",
    output: { accepted: true },
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
    run_id: "run-1",
    graph_id: "logic-safe",
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
    run_id: "run-1",
    graph_id: "logic-safe",
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

describe("logicRunContracts · strict request", () => {
  it("accepts only explicit dry_run with revision, server hash and JSON inputs", () => {
    expect(() => assertLogicDryRunRequest(request())).not.toThrow();
    expect(() => assertLogicDryRunRequest(request({ dry_run: false }))).toThrow("严格为 true");
    expect(() => assertLogicDryRunRequest({
      expected_revision: 2,
      dryRun: true,
      expected_graph_hash: graphHash,
      inputs: {},
    })).toThrow("未允许字段");
    expect(() => assertLogicDryRunRequest(request({ expected_revision: 0 }))).toThrow("大于等于 1");
    expect(() => assertLogicDryRunRequest(request({ expected_graph_hash: "client-hash" }))).toThrow("64 位");
    expect(() => assertLogicDryRunRequest(request({ inputs: [] }))).toThrow("JSON 对象");
  });

  it("rejects extra request fields, missing inputs and oversized inputs", () => {
    expect(() => assertLogicDryRunRequest(request({ graph: { nodes: [] } }))).toThrow("未允许字段");
    const missingInputs = { ...request() } as Record<string, unknown>;
    delete missingInputs.inputs;
    expect(() => assertLogicDryRunRequest(missingInputs)).toThrow("inputs 必须是 JSON 对象");
    expect(() => assertLogicDryRunRequest(request({ inputs: { value: "x".repeat(256 * 1024) } }))).toThrow("256 KiB");
    expect(() => assertLogicDryRunRequest(request({ idempotency_key: "x".repeat(161) }))).toThrow("160");
  });
});

describe("logicRunContracts · response honesty", () => {
  const expectation = { graphId: "logic-safe", revision: 2, graphHash, nodeIds: ["input-1"] };

  it("normalizes a complete response and preserves null token truth", () => {
    const normalized = normalizeLogicDryRun(dryRun(), expectation);
    expect(normalized).toMatchObject({
      run_id: "run-1",
      mode: "dry_run",
      production_written: false,
      total_tokens: null,
      node_results: [{ node_id: "input-1", status: "executed", truncated: false }],
    });
  });

  it.each(["cot", "reasoning", "chain_of_thought", "CoT"])(
    "recursively rejects forbidden private reasoning key %s",
    (key) => {
      expect(() => normalizeLogicDryRun(dryRun({
        node_results: [nodeResult({ output: { nested: [{ [key]: "private" }] } })],
      }), expectation)).toThrow("模型私有推理字段");
    },
  );

  it("rejects unknown transport fields and unsafe production claims", () => {
    expect(() => normalizeLogicDryRun(dryRun({ demo: true }), expectation)).toThrow("未允许字段");
    expect(() => normalizeLogicDryRun(dryRun({ production_written: true }), expectation)).toThrow("严格为 false");
    expect(() => normalizeLogicDryRun(dryRun({ mode: "production" }), expectation)).toThrow("严格");
    expect(() => normalizeLogicDryRun(dryRun({ total_tokens: 0, estimated_tokens: true }), expectation)).toThrow("未允许字段");
  });

  it("rejects revision/hash/node mismatches, duplicate nodes and unknown status", () => {
    expect(() => normalizeLogicDryRun(dryRun({ evaluated_revision: 3 }), expectation)).toThrow("revision");
    expect(() => normalizeLogicDryRun(dryRun({ graph_hash: "b".repeat(64) }), expectation)).toThrow("graph_hash");
    expect(() => normalizeLogicDryRun(dryRun({ node_results: [nodeResult({ node_id: "other" })] }), expectation)).toThrow("不属于当前图");
    expect(() => normalizeLogicDryRun(dryRun({ node_results: [nodeResult(), nodeResult()] }), expectation)).toThrow("重复 node_id");
    expect(() => normalizeLogicDryRun(dryRun({ node_results: [nodeResult({ status: "running" })] }), expectation)).toThrow("status 未知");
  });

  it("strictly validates real usage, safe tool metadata, edits and structured error", () => {
    const valid = dryRun({
      total_tokens: 7,
      node_results: [nodeResult({
        kind: "use_tool",
        usage: { model: "approved-model", input_tokens: 4, output_tokens: 3, total_tokens: 7 },
        tool_call: { tool: "lookup", adapter: "readonly-v1", read_only: true, dry_run_safe: true },
        proposed_edits: [{ action: "suggest", object_id: "obj-1", field: "status", value: "review", source_node_id: "input-1", applied: false }],
      })],
    });
    expect(normalizeLogicDryRun(valid, expectation).node_results[0].usage?.total_tokens).toBe(7);
    expect(() => normalizeLogicDryRun(dryRun({
      node_results: [nodeResult({ usage: { model: "m", input_tokens: 4, output_tokens: 3, total_tokens: 99 } })],
    }), expectation)).toThrow("token 不一致");
    expect(() => normalizeLogicDryRun(dryRun({
      node_results: [nodeResult({ tool_call: { tool: "write", adapter: "unsafe", read_only: false, dry_run_safe: true } })],
    }), expectation)).toThrow("read_only=true");
    expect(() => normalizeLogicDryRun(dryRun({
      proposed_edits: [{ action: "write", object_id: "obj", field: "x", value: 1, source_node_id: "input-1", applied: true }],
    }), expectation)).toThrow("applied 必须严格为 false");
  });

  it("accepts structured failed evidence and requires machine-readable skipped reasons", () => {
    const failedError = { code: "CAPABILITY_UNAVAILABLE", message: "adapter unavailable", node_id: "input-1", reason: "adapter_missing" };
    const failed = dryRun({
      status: "failed",
      node_results: [nodeResult({ status: "failed", error: failedError })],
      error: failedError,
    });
    expect(normalizeLogicDryRun(failed, expectation)).toMatchObject({
      status: "failed",
      error: { code: "CAPABILITY_UNAVAILABLE", reason: "adapter_missing" },
    });
    expect(() => normalizeLogicDryRun(dryRun({
      node_results: [nodeResult({ status: "skipped", started_at: null, finished_at: null, elapsed_ms: null })],
    }), expectation)).toThrow("机器可读 reason");
  });

  it("accepts exact detail verification and rejects mismatched persisted evidence", () => {
    const response = normalizeLogicDryRun(dryRun(), expectation);
    const detail = normalizeLogicDryRun(dryRun(), expectation);
    expect(() => assertDryRunDetailMatches(response, detail)).not.toThrow();
    expect(() => assertDryRunDetailMatches(response, { ...detail, status: "failed" })).toThrow("历史持久化核验失败");
  });
});

describe("logicRunContracts · history list", () => {
  it("normalizes exact summaries, node counts and cursor", () => {
    expect(normalizeLogicRunList({ items: [summary()], count: 1, next_cursor: "cursor-1" }, "logic-safe")).toEqual({
      items: [summary()],
      count: 1,
      next_cursor: "cursor-1",
    });
  });

  it("rejects wrong graph, duplicate ids, dishonest count and forbidden reasoning", () => {
    expect(() => normalizeLogicRunList({ items: [summary({ graph_id: "other" })], count: 1, next_cursor: null }, "logic-safe")).toThrow("graph_id");
    expect(() => normalizeLogicRunList({ items: [summary(), summary()], count: 2, next_cursor: null }, "logic-safe")).toThrow("重复 run_id");
    expect(() => normalizeLogicRunList({ items: [summary()], count: 2, next_cursor: null }, "logic-safe")).toThrow("count");
    expect(() => normalizeLogicRunList({ items: [summary({ reasoning: "private" })], count: 1, next_cursor: null }, "logic-safe")).toThrow("模型私有推理字段");
  });
});
