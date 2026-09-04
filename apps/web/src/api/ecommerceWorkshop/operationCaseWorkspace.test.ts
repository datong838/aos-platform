import { describe, expect, it } from "vitest";

import { parseOperationCaseWorkspace } from "./operationCaseWorkspace";

const hash = "a".repeat(64);
const scope = { orgId: "org-org", projectId: "dev-project" };
const ref = { tenant: scope, resourceType: "ProductSku", resourceId: "niushop:1:70", contentHash: hash, sourceUpdatedAt: "2026-09-04T10:00:00Z" };
const value = {
  schemaVersion: "aos.ecommerce-workshop.operation-case-workspace/v1",
  tenant: scope,
  status: "ready",
  evaluatedAt: "2026-09-04T10:00:00Z",
  dataCutoff: "2026-09-04T10:00:00Z",
  sources: ["orders", "inventory", "shipments", "aftersaleEvents", "payments", "operationCases"].map((sourceId, index) => ({ sourceId, status: "ready", count: index === 1 ? 1 : 0, blocker: null })),
  cases: [],
  candidates: [{ candidateId: "b".repeat(64), kind: "inventory_data_gap", title: "库存资料待核对", summary: "缺少库存数量和告警阈值。", priority: "high", memberRefs: [ref], externalEffectAllowed: false }],
  availableRefs: [ref],
  ledger: { sourceTotal: 1, assigned: 0, unassigned: 1, candidates: 1, openCases: 0, pausedCases: 0, closedCases: 0 },
  externalEffectAllowed: false,
};

describe("parseOperationCaseWorkspace", () => {
  it("解析同租户、守恒且无外部副作用的工作区", () => {
    expect(parseOperationCaseWorkspace(value, scope)).toMatchObject({ status: "ready", ledger: { sourceTotal: 1, candidates: 1 }, externalEffectAllowed: false });
  });

  it("拒绝租户、来源顺序、守恒和外部副作用漂移", () => {
    expect(() => parseOperationCaseWorkspace({ ...value, tenant: { ...scope, orgId: "dev-org" } }, scope)).toThrow("tenant 漂移");
    expect(() => parseOperationCaseWorkspace({ ...value, sources: [...value.sources].reverse() }, scope)).toThrow("canonical order");
    expect(() => parseOperationCaseWorkspace({ ...value, ledger: { ...value.ledger, sourceTotal: 2 } }, scope)).toThrow("ledger 漂移");
    expect(() => parseOperationCaseWorkspace({ ...value, externalEffectAllowed: true }, scope)).toThrow("权限边界漂移");
  });
});
