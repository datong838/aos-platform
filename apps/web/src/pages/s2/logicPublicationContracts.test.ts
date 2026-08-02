import { describe, expect, it } from "vitest";

import {
  assertLogicPublicationDetailMatches,
  assertLogicPublicationRequest,
  normalizeLogicPublication,
  normalizeLogicPublicationList,
  type LogicPublishRequest,
} from "./logicPublicationContracts";

const HASH = "a".repeat(64);

const request: LogicPublishRequest = {
  expected_revision: 7,
  expected_graph_hash: HASH,
  eval_suite_id: "suite-1",
  eval_report_id: "report-1",
  idempotency_key: "publish-logic-1-r7",
};

function snapshot(overrides: Record<string, unknown> = {}) {
  return {
    id: "logic-1",
    name: "可信发布",
    description: "",
    status: "draft",
    schema_version: 1,
    revision: 7,
    published_version: null,
    graph_hash: HASH,
    persisted: true,
    nodes: [{ id: "input-1", kind: "input", label: "输入", position_x: 20, position_y: 30, config: {} }],
    edges: [],
    entry_node_ids: ["input-1"],
    created_at: "2026-08-02T00:00:00Z",
    updated_at: "2026-08-02T00:01:00Z",
    ...overrides,
  };
}

function publication(overrides: Record<string, unknown> = {}) {
  return {
    publication_id: "pub-1",
    graph_id: "logic-1",
    graph_revision: 7,
    graph_hash: HASH,
    graph_snapshot: snapshot(),
    dry_run_id: "run-1",
    eval_suite_id: "suite-1",
    eval_report_id: "report-1",
    eval_gate: {
      gate_passed: true,
      pass_rate: 1,
      threshold: 0.92,
      passed: 10,
      failed: 0,
      total: 10,
      run_at: "2026-08-02T00:00:30Z",
    },
    actor: "user-1",
    created_at: "2026-08-02T00:02:00Z",
    ...overrides,
  };
}

describe("logicPublicationContracts", () => {
  it("严格接受绑定精确 revision/hash 和 Evals 证据的发布请求", () => {
    expect(() => assertLogicPublicationRequest(request)).not.toThrow();
    expect(() => assertLogicPublicationRequest({ ...request, expected_revision: 0 })).toThrow("expected_revision");
    expect(() => assertLogicPublicationRequest({ ...request, expected_graph_hash: "short" })).toThrow("expected_graph_hash");
    expect(() => assertLogicPublicationRequest({ ...request, eval_report_id: "" })).toThrow("eval_report_id");
    expect(() => assertLogicPublicationRequest({ ...request, extra: true } as LogicPublishRequest)).toThrow("未允许字段");
  });

  it("归一化发布产物并验证不可变 graph snapshot 与顶层绑定", () => {
    expect(normalizeLogicPublication(publication(), { graphId: "logic-1", request })).toMatchObject({
      publication_id: "pub-1",
      graph_revision: 7,
      dry_run_id: "run-1",
      eval_gate: { gate_passed: true, total: 10 },
    });
    expect(() => normalizeLogicPublication(publication({ graph_revision: 8 }), { graphId: "logic-1", request }))
      .toThrow("graph_revision");
    expect(() => normalizeLogicPublication(publication({ graph_snapshot: snapshot({ graph_hash: "b".repeat(64) }) })))
      .toThrow("graph_snapshot.graph_hash");
    expect(() => normalizeLogicPublication(publication({ graph_snapshot: snapshot({ persisted: false }) })))
      .toThrow("persisted=true");
  });

  it("拒绝未通过、自相矛盾或无用例的 Evals 门控摘要", () => {
    expect(() => normalizeLogicPublication(publication({
      eval_gate: { gate_passed: false, pass_rate: 1, threshold: 0.92, passed: 10, failed: 0, total: 10, run_at: "2026-08-02T00:00:30Z" },
    }))).toThrow("gate_passed=true");
    expect(() => normalizeLogicPublication(publication({
      eval_gate: { gate_passed: true, pass_rate: 0.5, threshold: 0.92, passed: 5, failed: 4, total: 10, run_at: "2026-08-02T00:00:30Z" },
    }))).toThrow("passed + failed");
    expect(() => normalizeLogicPublication(publication({
      eval_gate: { gate_passed: true, pass_rate: 1, threshold: 0.92, passed: 0, failed: 0, total: 0, run_at: "2026-08-02T00:00:30Z" },
    }))).toThrow("total 必须大于 0");
  });

  it("列表必须 graph 一致、count 精确且 publication_id 唯一", () => {
    expect(normalizeLogicPublicationList({ items: [publication()], count: 1 }, "logic-1").count).toBe(1);
    expect(() => normalizeLogicPublicationList({ items: [publication()], count: 2 }, "logic-1")).toThrow("count");
    expect(() => normalizeLogicPublicationList({ items: [publication(), publication()], count: 2 }, "logic-1"))
      .toThrow("publication_id 重复");
    expect(() => normalizeLogicPublicationList({ items: [publication({ graph_id: "other", graph_snapshot: snapshot({ id: "other" }) })], count: 1 }, "logic-1"))
      .toThrow("graph_id");
  });

  it("POST 与 GET 任一不可变证据不一致都 fail-closed", () => {
    const posted = normalizeLogicPublication(publication(), { graphId: "logic-1", request });
    const reread = normalizeLogicPublication(publication({
      graph_snapshot: Object.fromEntries(Object.entries(snapshot()).reverse()),
    }), { graphId: "logic-1", request });
    expect(() => assertLogicPublicationDetailMatches(posted, reread)).not.toThrow();
    expect(() => assertLogicPublicationDetailMatches(posted, {
      ...reread,
      actor: "other-user",
    })).toThrow("回读不一致");
  });

  it("拒绝额外字段、无效时间和非安全整数", () => {
    expect(() => normalizeLogicPublication(publication({ private_reasoning: "secret" }))).toThrow("未允许字段");
    expect(() => normalizeLogicPublication(publication({ created_at: "not-a-time" }))).toThrow("created_at");
    expect(() => normalizeLogicPublication(publication({ graph_revision: Number.MAX_SAFE_INTEGER + 1 }))).toThrow("安全整数");
  });
});
