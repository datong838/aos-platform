import { describe, expect, it } from "vitest";
import { parseAnalystRoleQueryTemplates, parseAssistEvent, parseQueryResult, validateAssistStream } from "./parser";

const tenant = { orgId: "org-org", projectId: "dev-project" };
const ref = { resourceType: "SelectionRevision", resourceId: "sel-1", revision: "1", authority: "test" };
const baseEvent = { threadId: "thread-1", turnId: "turn-1", occurredAt: "2026-08-16T00:00:00Z", context: null, blocker: null, content: null, proposalRef: null, usageRefs: [], lineageRefs: [] };
const source = { ref, contentHash: "b".repeat(64), cutoffAt: "2026-08-16T00:00:00Z", freshness: "fresh", markings: [] };
const column = { key: "orderNo", label: "订单号", valueType: "string", marking: null };
const row = { rowId: "order-1", values: { orderNo: "20260816001" } };

function result(status: "complete" | "empty" | "degraded" | "partial" | "blocked") {
  const hasRows = !["empty", "blocked"].includes(status);
  return {
    tenant, queryId: `q-${status}`, revision: 1, kind: "semantic", status,
    columns: hasRows ? [column] : [], rows: hasRows ? [row] : [],
    sourceRefs: status === "blocked" ? [] : [source], lineageRefs: status === "blocked" ? [] : [ref],
    blockers: status === "blocked" ? [{ code: "OWNER_UNAVAILABLE", message: "blocked", dependencyRef: null, retryable: false }] : [],
    uncertainties: ["degraded", "partial"].includes(status) ? ["部分来源晚于 cutoff"] : [],
    confidence: status === "blocked"
      ? { status: "unknown", score: null, basis: ["OWNER_UNAVAILABLE"] }
      : { status: "not_applicable", score: null, basis: ["deterministic_canonical_read"] },
    cutoffAt: "2026-08-16T00:00:00Z", contentHash: "a".repeat(64), createdAt: "2026-08-16T00:00:01Z",
  };
}

describe("aipWorkbench strict parser", () => {
  it("accepts honest blocked Analyst result and rejects drift", () => {
    const value = result("blocked");
    expect(parseQueryResult(value, tenant).status).toBe("blocked");
    expect(() => parseQueryResult({ ...value, shadow: "mock" }, tenant)).toThrow("额外字段");
    expect(() => parseQueryResult({ ...value, tenant: { orgId: "dev-org", projectId: "dev-project" } }, tenant)).toThrow("tenant echo");
  });

  it.each(["complete", "empty", "partial", "degraded"] as const)("accepts honest %s Analyst result", (status) => {
    expect(parseQueryResult(result(status), tenant).status).toBe(status);
  });

  it("rejects status payloads that would hide missing evidence", () => {
    expect(() => parseQueryResult({ ...result("empty"), sourceRefs: [] }, tenant)).toThrow("empty Result revision");
    expect(() => parseQueryResult({ ...result("partial"), uncertainties: [] }, tenant)).toThrow("必须声明不确定性");
    expect(() => parseQueryResult({ ...result("complete"), blockers: result("blocked").blockers }, tenant)).toThrow("来源或 blocker");
    expect(() => parseQueryResult({ ...result("complete"), confidence: { status: "unknown", score: 0.9, basis: ["invented"] } }, tenant)).toThrow("不得包含 score");
  });

  it("parses exact six-role templates and rejects tenant or count drift", () => {
    const roles = ["data_advisor", "content_officer", "shopping_advisor", "customer_service", "private_domain_manager", "campaign_planner"];
    const payload = {
      tenant,
      bundleRef: { resourceType: "SolutionPack", resourceId: "solution.ecommerce.growth", revision: "1.3.0", authority: "asset-registry" },
      contentHash: "c".repeat(64), count: 6,
      items: roles.map((role) => ({
        templateId: `ecommerce.analyst.${role}`, revision: 1, roleId: `ecommerce.${role}`, roleName: role,
        queryKind: "semantic", defaultObjectType: "Order", defaultPrompt: "", requiredObjectTypes: ["Order"],
        requiredLogicIds: ["D01"], sourceDataTypes: ["order"], purpose: "真实查询", policy: "canonical-read-only",
        readiness: "ready", blockers: [],
      })),
    };
    expect(parseAnalystRoleQueryTemplates(payload, tenant).items).toHaveLength(6);
    expect(() => parseAnalystRoleQueryTemplates({ ...payload, count: 5 }, tenant)).toThrow("数量漂移");
    expect(() => parseAnalystRoleQueryTemplates({ ...payload, tenant: { orgId: "dev-org", projectId: "dev-project" } }, tenant)).toThrow("tenant echo");
  });

  it("requires contiguous terminal Assist events", () => {
    const start = parseAssistEvent({ ...baseEvent, eventType: "start", sequence: 1 });
    const blocked = parseAssistEvent({ ...baseEvent, eventType: "blocked", sequence: 2, blocker: { code: "ASSIST_AGENT_RUN_NOT_FOUND", message: "blocked", dependencyRef: null, retryable: false } });
    expect(validateAssistStream([start, blocked])).toHaveLength(2);
    expect(() => validateAssistStream([start])).toThrow("终态");
    expect(() => validateAssistStream([start, { ...blocked, sequence: 3 }])).toThrow("序列漂移");
    expect(ref.revision).toBe("1");
  });

  it("rejects Assist event drift and nonterminal usage claims", () => {
    expect(() => parseAssistEvent({ ...baseEvent, eventType: "delta", sequence: 1, content: "片段", usageRefs: [ref] })).toThrow("usage/lineage");
    expect(() => parseAssistEvent({ ...baseEvent, eventType: "done", sequence: 2, localAnswer: "伪答案" })).toThrow("额外字段");
  });
});
