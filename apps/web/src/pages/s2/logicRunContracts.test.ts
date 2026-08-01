import { describe, expect, it } from "vitest";

import {
  assertDryRunDetailMatches,
  assertLogicDryRunRequest,
  normalizeLogicDryRun,
  normalizeLogicRunList,
  type LogicDryRunRequest,
} from "./logicRunContracts";

const graphHash = "a".repeat(64);

function nestedJson(depth: number): Record<string, unknown> {
  let value: unknown = true;
  for (let level = 1; level < depth; level += 1) value = { next: value };
  return value as Record<string, unknown>;
}

function runError(nodeId = "input-1", reason = "adapter_missing") {
  return { code: "CAPABILITY_UNAVAILABLE", message: "adapter unavailable", node_id: nodeId, reason };
}

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
    expect(() => assertLogicDryRunRequest(request({
      inputs: { values: Array.from({ length: 10 }, () => "x".repeat(30_000)) },
    }))).toThrow("256 KiB");
    expect(() => assertLogicDryRunRequest(request({ idempotency_key: "x".repeat(161) }))).toThrow("160");
  });

  it("enforces exact JSON key, depth, collection and string budgets", () => {
    expect(() => assertLogicDryRunRequest(request({ inputs: { ["k".repeat(256)]: true } }))).not.toThrow();
    expect(() => assertLogicDryRunRequest(request({ inputs: nestedJson(16) }))).not.toThrow();
    expect(() => assertLogicDryRunRequest(request({ inputs: { values: Array.from({ length: 2_000 }, () => 0) } }))).not.toThrow();
    expect(() => assertLogicDryRunRequest(request({ inputs: { value: "x".repeat(32_768) } }))).not.toThrow();

    expect(() => assertLogicDryRunRequest(request({ inputs: { ["k".repeat(257)]: true } }))).toThrow("长度超过 256 的键");
    expect(() => assertLogicDryRunRequest(request({ inputs: nestedJson(17) }))).toThrow("深度超过 16");
    expect(() => assertLogicDryRunRequest(request({ inputs: { values: Array.from({ length: 2_001 }, () => 0) } }))).toThrow("集合长度超过 2000");
    expect(() => assertLogicDryRunRequest(request({ inputs: { value: "x".repeat(32_769) } }))).toThrow("字符串长度超过 32768");
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
    const failedError = runError();
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

  it("keeps top-level status consistent with every terminal node", () => {
    const skipped = nodeResult({
      status: "skipped",
      started_at: null,
      finished_at: null,
      elapsed_ms: null,
      error: runError("input-1", "branch_not_selected"),
    });
    expect(() => normalizeLogicDryRun(dryRun({ node_results: [skipped] }), expectation)).not.toThrow();

    const canceled = nodeResult({
      status: "canceled",
      started_at: null,
      finished_at: null,
      elapsed_ms: null,
      error: runError("input-1", "fail_fast"),
    });
    expect(() => normalizeLogicDryRun(dryRun({ node_results: [canceled] }), expectation)).toThrow("succeeded");
    expect(() => normalizeLogicDryRun(dryRun({
      status: "failed",
      node_results: [canceled],
      error: runError(),
    }), expectation)).toThrow("至少包含一个 failed");
  });

  it("checks timestamp order without equating elapsed monotonic time to wall-clock delta", () => {
    expect(() => normalizeLogicDryRun(dryRun({ elapsed_ms: 999_999 }), expectation)).not.toThrow();
    expect(() => normalizeLogicDryRun(dryRun({
      finished_at: "2026-07-31T23:59:59Z",
    }), expectation)).toThrow("finished_at 不得早于 started_at");
    expect(() => normalizeLogicDryRun(dryRun({
      node_results: [nodeResult({ finished_at: "2026-07-31T23:59:59Z" })],
    }), expectation)).toThrow("finished_at 不得早于 started_at");
  });

  it("requires total_tokens to equal all non-null node usage totals", () => {
    const usageA = { model: "m1", input_tokens: 1, output_tokens: 2, total_tokens: 3 };
    const usageB = { model: "m2", input_tokens: 2, output_tokens: 3, total_tokens: 5 };
    const twoNodes = [nodeResult({ usage: usageA }), nodeResult({ node_id: "llm-2", kind: "use_llm", usage: usageB })];
    const twoNodeExpectation = { ...expectation, nodeIds: ["input-1", "llm-2"] };
    expect(() => normalizeLogicDryRun(dryRun({ total_tokens: 8, node_results: twoNodes }), twoNodeExpectation)).not.toThrow();
    expect(() => normalizeLogicDryRun(dryRun({ total_tokens: 7, node_results: twoNodes }), twoNodeExpectation)).toThrow("usage 汇总不一致");
    expect(() => normalizeLogicDryRun(dryRun({ total_tokens: 0 }), expectation)).toThrow("必须为 null");
  });

  it("requires exact node sets and validates every error/edit node reference", () => {
    expect(() => normalizeLogicDryRun(dryRun(), { ...expectation, nodeIds: ["input-1", "missing"] })).toThrow("缺少当前图 node_id");
    expect(() => normalizeLogicDryRun(dryRun(), { ...expectation, nodeIds: ["input-1", "input-1"] })).toThrow("expectedNodeIds 包含重复");
    expect(() => normalizeLogicDryRun(dryRun({
      status: "failed",
      node_results: [nodeResult({ status: "failed", error: runError("other") })],
      error: runError(),
    }), expectation)).toThrow("error.node_id 必须等于所属");
    expect(() => normalizeLogicDryRun(dryRun({
      status: "failed",
      node_results: [nodeResult({ status: "failed", error: runError() })],
      error: runError("other"),
    }), expectation)).toThrow("run.error.node_id");
    expect(() => normalizeLogicDryRun(dryRun({
      proposed_edits: [{ action: "suggest", object_id: "obj", field: "status", value: "review", source_node_id: "other", applied: false }],
    }), expectation)).toThrow("source_node_id 不属于");
    expect(() => normalizeLogicDryRun(dryRun({
      node_results: [nodeResult({
        proposed_edits: [{ action: "suggest", object_id: "obj", field: "status", value: "review", source_node_id: "other", applied: false }],
      })],
    }), expectation)).toThrow("source_node_id 不属于");
  });

  it("applies JSON safety limits to response output and total result evidence", () => {
    expect(() => normalizeLogicDryRun(dryRun({
      node_results: [nodeResult({ output: { ["k".repeat(257)]: true } })],
    }), expectation)).toThrow("长度超过 256 的键");
    expect(() => normalizeLogicDryRun(dryRun({
      node_results: [nodeResult({ output: nestedJson(17) })],
    }), expectation)).toThrow("深度超过 16");
    expect(() => normalizeLogicDryRun(dryRun({
      node_results: [nodeResult({ output: { values: Array.from({ length: 2_001 }, () => 0) } })],
    }), expectation)).toThrow("集合长度超过 2000");
    expect(() => normalizeLogicDryRun(dryRun({
      node_results: [nodeResult({ output: { value: "x".repeat(32_769) } })],
    }), expectation)).toThrow("字符串长度超过 32768");
    expect(() => normalizeLogicDryRun(dryRun({
      node_results: [nodeResult({ output: Array.from({ length: 5 }, () => "x".repeat(30_000)) })],
    }), expectation)).toThrow("output 超过 128 KiB");

    const largeNodes = Array.from({ length: 18 }, (_, index) => nodeResult({
      node_id: `node-${index}`,
      output: Array.from({ length: 4 }, () => "x".repeat(30_000)),
    }));
    expect(() => normalizeLogicDryRun(dryRun({ node_results: largeNodes }), {
      ...expectation,
      nodeIds: largeNodes.map((node) => node.node_id as string),
    })).toThrow("超过 2 MiB");
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

  it("keeps summary status, node counts, error code and timestamps self-consistent", () => {
    expect(() => normalizeLogicRunList({
      items: [summary({ node_counts: { executed: 0, skipped: 0, failed: 1, canceled: 0 } })],
      count: 1,
      next_cursor: null,
    }, "logic-safe")).toThrow("succeeded 运行摘要");
    expect(() => normalizeLogicRunList({
      items: [summary({ status: "failed", error_code: null })],
      count: 1,
      next_cursor: null,
    }, "logic-safe")).toThrow("failed 运行摘要");
    expect(() => normalizeLogicRunList({
      items: [summary({ status: "failed", node_counts: { executed: 0, skipped: 0, failed: 1, canceled: 0 }, error_code: "NODE_FAILED" })],
      count: 1,
      next_cursor: null,
    }, "logic-safe")).not.toThrow();
    expect(() => normalizeLogicRunList({
      items: [summary({ finished_at: "2026-07-31T23:59:59Z" })],
      count: 1,
      next_cursor: null,
    }, "logic-safe")).toThrow("finished_at 不得早于 started_at");
  });
});
