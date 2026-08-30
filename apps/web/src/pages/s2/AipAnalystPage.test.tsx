// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AipAnalystPage, buildGovernedQuery, businessRowLabel, matchLogicMount, summarizeResult } from "./AipAnalystPage";
import type { AnalystRoleQueryTemplateList, QueryResultRevision } from "../../api/aipWorkbench";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const exact = { resourceType: "Task", resourceId: "task-1", revision: "1", authority: "aip-task" };
const logicGraph = { id: "ecommerce.logic.A02", name: "A02", revision: 1, graphHash: "a".repeat(64) };
const listObjectTypes = () => Promise.resolve([{ id: "Order", name: "订单" }]);
const listLogicGraphs = () => Promise.resolve([logicGraph]);
const emptyLogic = () => Promise.resolve([]);
const roleIds = ["data_advisor", "content_officer", "shopping_advisor", "customer_service", "private_domain_manager", "campaign_planner"];
const roleCatalog: AnalystRoleQueryTemplateList = {
  tenant: { orgId: "org-org", projectId: "dev-project" },
  bundleRef: { resourceType: "SolutionPack", resourceId: "solution.ecommerce.growth", revision: "1.3.0", authority: "asset-registry" },
  contentHash: "c".repeat(64), count: 6,
  items: roleIds.map((role, index) => ({
    templateId: `template.${role}`, revision: 1, roleId: `ecommerce.${role}`, roleName: role,
    queryKind: "semantic", defaultObjectType: "Order", defaultPrompt: "", requiredObjectTypes: ["Order"],
    requiredLogicIds: [`D0${index + 1}`], sourceDataTypes: ["order"], purpose: "真实治理查询", policy: "canonical-read-only",
    readiness: "ready", blockers: [],
  })),
};
const listRoleTemplates = () => Promise.resolve(roleCatalog);

describe("AipAnalystPage governed query", () => {
  let host: HTMLDivElement;
  let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); });

  it("builds semantic query without SQL or client tenant", () => {
    const query = buildGovernedQuery({ kind: "semantic", objectType: "Order", prompt: "", cutoffAt: "2026-08-16T00:00:00Z", taskRef: null, skillRef: null, metricRef: null });
    expect(query).toEqual(expect.objectContaining({ kind: "semantic", objectType: "Order" }));
    expect(JSON.stringify(query)).not.toMatch(/sql|orgId|projectId|Northampton/i);
  });

  it("builds governed filters and presents business labels instead of raw object ids", () => {
    const query = buildGovernedQuery({ kind: "semantic", objectType: "Product", prompt: "", cutoffAt: "2026-08-30T00:00:00Z", taskRef: null, skillRef: null, metricRef: null, filterField: "status", filterOperator: "eq", filterValue: "在售", pageSize: 20 });
    expect(query).toEqual(expect.objectContaining({ filters: [{ field: "status", operator: "eq", value: "在售" }], pageSize: 20 }));
    const result: QueryResultRevision = { tenant: { orgId: "org-org", projectId: "dev-project" }, queryId: "q", revision: 1, kind: "semantic", status: "complete", columns: [{ key: "product_name", label: "商品名称", valueType: "string", marking: null }, { key: "sales", label: "销量", valueType: "number", marking: null }], rows: [{ rowId: "niushop:1:27", values: { product_name: "栖月汇桂花糕", sales: 18 } }], sourceRefs: [{ ref: { resourceType: "ObjectType", resourceId: "Product", revision: "1", authority: "ontology" }, contentHash: "a".repeat(64), cutoffAt: "2026-08-30T00:00:00Z", freshness: "fresh", markings: ["public"] }], lineageRefs: [], blockers: [], uncertainties: [], confidence: { status: "measured", score: .9, basis: ["canonical"] }, cutoffAt: "2026-08-30T00:00:00Z", contentHash: "b".repeat(64), createdAt: "2026-08-30T00:00:01Z" };
    expect(businessRowLabel(result.rows[0], result.columns)).toBe("栖月汇桂花糕");
    expect(businessRowLabel({ rowId: "niushop:1:108", values: { objectId: "niushop:1:108", status: "active" } }, [{ key: "objectId", label: "对象 ID", valueType: "string", marking: null }, { key: "status", label: "状态", valueType: "string", marking: null }], "订单")).toBe("订单 108");
    expect(summarizeResult(result, "哪些商品值得关注？").summary).toContain("1 条业务记录");
    expect(summarizeResult(result, "哪些商品值得关注？").comparison).toContain("因果");
  });

  it("fails closed when knowledge or metric exact refs are absent", () => {
    expect(buildGovernedQuery({ kind: "knowledge", objectType: "", prompt: "核查", cutoffAt: "2026-08-16T00:00:00Z", taskRef: null, skillRef: null, metricRef: null })).toBeNull();
    expect(buildGovernedQuery({ kind: "metric", objectType: "", prompt: "", cutoffAt: "2026-08-16T00:00:00Z", taskRef: null, skillRef: null, metricRef: null })).toBeNull();
    expect(exact.revision).toBe("1");
  });

  it("builds knowledge and metric queries only from exact upstream refs", () => {
    expect(buildGovernedQuery({ kind: "knowledge", objectType: "", prompt: "核查订单风险", cutoffAt: "2026-08-16T00:00:00Z", taskRef: exact, skillRef: { ...exact, resourceType: "Skill", resourceId: "skill-1" }, metricRef: null })).toEqual(expect.objectContaining({ kind: "knowledge", taskRef: exact }));
    expect(buildGovernedQuery({ kind: "metric", objectType: "", prompt: "", cutoffAt: "2026-08-16T00:00:00Z", taskRef: null, skillRef: null, metricRef: { ...exact, resourceType: "Metric", resourceId: "gmv" } })).toEqual(expect.objectContaining({ kind: "metric", dimensions: [] }));
  });

  it("uses native buttons for keyboard activation and never double-runs while busy", async () => {
    let resolve!: (value: QueryResultRevision) => void;
    const runQuery = vi.fn(() => new Promise<QueryResultRevision>((done) => { resolve = done; }));
    const listObjectTypesFn = vi.fn().mockResolvedValue([{ id: "Order", name: "订单" }]);
    await act(async () => root.render(<MemoryRouter><AipAnalystPage runQuery={runQuery} listObjectTypes={listObjectTypesFn} listLogicGraphs={listLogicGraphs} listRoleTemplates={listRoleTemplates} /></MemoryRouter>));
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    const collapse = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "收起查询")!;
    expect(collapse.tagName).toBe("BUTTON");
    collapse.focus();
    await act(async () => { collapse.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })); });
    expect(document.activeElement).toBe(collapse);
    expect(collapse.getAttribute("aria-expanded")).toBe("false");
    await act(async () => { collapse.dispatchEvent(new KeyboardEvent("keydown", { key: " ", bubbles: true })); });
    expect(collapse.getAttribute("aria-expanded")).toBe("true");
    const evidence = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "收起证据")!;
    await act(async () => { evidence.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })); });
    expect(evidence.getAttribute("aria-expanded")).toBe("false");
    const focus = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "专注模式")!;
    await act(async () => { focus.dispatchEvent(new KeyboardEvent("keydown", { key: " ", bubbles: true })); });
    expect(focus.getAttribute("aria-pressed")).toBe("true");
    await act(async () => focus.click());

    const run = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "运行真实查询")!;
    await act(async () => { run.click(); run.click(); });
    expect(runQuery).toHaveBeenCalledTimes(1);
    expect(host.textContent).toContain("查询中…");
    await act(async () => resolve({
      tenant: { orgId: "org-org", projectId: "dev-project" }, queryId: "query-1", revision: 1,
      kind: "semantic", status: "empty", columns: [], rows: [],
      sourceRefs: [{ ref: { resourceType: "ObjectType", resourceId: "Order", revision: "1", authority: "ontology" }, contentHash: "a".repeat(64), cutoffAt: "2026-08-16T00:00:00Z", freshness: "fresh", markings: [] }],
      lineageRefs: [], blockers: [], uncertainties: [], cutoffAt: "2026-08-16T00:00:00Z",
      confidence: { status: "not_applicable", score: null, basis: ["deterministic_canonical_read"] },
      contentHash: "b".repeat(64), createdAt: "2026-08-16T00:00:01Z",
    }));
    expect(host.textContent).toContain("真实查询返回空结果");
  });

  it("clears the previous revision and fails closed when a refresh fails", async () => {
    const result: QueryResultRevision = {
      tenant: { orgId: "org-org", projectId: "dev-project" }, queryId: "query-old", revision: 3,
      kind: "semantic", status: "empty", columns: [], rows: [],
      sourceRefs: [{ ref: { resourceType: "ObjectType", resourceId: "Order", revision: "1", authority: "ontology" }, contentHash: "a".repeat(64), cutoffAt: "2026-08-16T00:00:00Z", freshness: "fresh", markings: [] }],
      lineageRefs: [], blockers: [], uncertainties: [], cutoffAt: "2026-08-16T00:00:00Z", contentHash: "b".repeat(64), createdAt: "2026-08-16T00:00:01Z",
      confidence: { status: "not_applicable", score: null, basis: ["deterministic_canonical_read"] },
    };
    const runQuery = vi.fn().mockResolvedValueOnce(result).mockRejectedValueOnce(new Error("authority unavailable"));
    const listObjectTypesFn = vi.fn().mockResolvedValue([{ id: "Order", name: "订单" }]);
    await act(async () => root.render(<MemoryRouter><AipAnalystPage runQuery={runQuery} listObjectTypes={listObjectTypesFn} listLogicGraphs={listLogicGraphs} listRoleTemplates={listRoleTemplates} /></MemoryRouter>));
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    const run = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "运行真实查询")!;
    await act(async () => run.click());
    expect(host.textContent).toContain("修订 3");
    await act(async () => run.click());
    expect(host.textContent).toContain("请求失败：authority unavailable");
    expect(host.textContent).not.toContain("r3");
    expect(host.textContent).not.toContain("Northampton");
  });

  it("loads Object Types from authority and refuses demo fallback when empty", async () => {
    const listObjectTypesFn = vi.fn().mockResolvedValue([]);
    await act(async () => root.render(<MemoryRouter><AipAnalystPage listObjectTypes={listObjectTypesFn} listLogicGraphs={emptyLogic} listRoleTemplates={listRoleTemplates} /></MemoryRouter>));
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(host.textContent).toContain("当前租户暂无已安装 Object Type；不生成演示类型");
    expect(host.textContent).not.toContain("Northampton");
    expect(host.querySelector('[data-testid="analyst-run-query"]')).toBeTruthy();
    expect((host.querySelector('[data-testid="analyst-run-query"]') as HTMLButtonElement).disabled).toBe(true);
  });

  it("disables a query when the user clears the exact cutoff", async () => {
    await act(async () => root.render(<MemoryRouter><AipAnalystPage listObjectTypes={listObjectTypes} listLogicGraphs={listLogicGraphs} listRoleTemplates={listRoleTemplates} listSaved={() => Promise.resolve([])} /></MemoryRouter>));
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    const cutoff = host.querySelector<HTMLInputElement>('input[type="datetime-local"]')!;
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    await act(async () => { setter.call(cutoff, ""); cutoff.dispatchEvent(new Event("input", { bubbles: true })); });
    expect((host.querySelector('[data-testid="analyst-run-query"]') as HTMLButtonElement).disabled).toBe(true);
  });

  it("mounts exact Logic revision and blocks when no saved graphs", async () => {
    expect(matchLogicMount([logicGraph], { id: "ecommerce.logic.A02", revision: "1", hash: "a".repeat(64) })?.id).toBe("ecommerce.logic.A02");
    await act(async () => root.render(<MemoryRouter><AipAnalystPage listObjectTypes={listObjectTypes} listLogicGraphs={listLogicGraphs} listRoleTemplates={listRoleTemplates} /></MemoryRouter>));
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(host.querySelector('[data-testid="analyst-logic-mount-exact"]')?.textContent).toContain("ecommerce.logic.A02@r1");
    expect(host.querySelector('[data-testid="analyst-jump-logic"]')?.getAttribute("href")).toContain("/aip/logic?graph=ecommerce.logic.A02");
    await act(async () => root.render(<MemoryRouter><AipAnalystPage listObjectTypes={listObjectTypes} listLogicGraphs={emptyLogic} listRoleTemplates={listRoleTemplates} /></MemoryRouter>));
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(host.textContent).toContain("当前租户暂无已保存业务逻辑；本次仅执行受控查询");
  });

  it("renders six role templates and selects a role without inventing readiness", async () => {
    const blockedCatalog: AnalystRoleQueryTemplateList = {
      ...roleCatalog,
      items: roleCatalog.items.map((item, index) => index === 0 ? {
        ...item,
        readiness: "blocked",
        blockers: [{ code: "OBJECT_TYPE_NOT_INSTALLED", message: "required Object Type is not installed: Payment", dependencyRef: null, retryable: false }],
      } : item),
    };
    await act(async () => root.render(<MemoryRouter><AipAnalystPage listObjectTypes={listObjectTypes} listLogicGraphs={listLogicGraphs} listRoleTemplates={() => Promise.resolve(blockedCatalog)} /></MemoryRouter>));
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(host.querySelectorAll('button[data-testid^="analyst-role-"]')).toHaveLength(6);
    const roleCard = host.querySelector('[data-testid="analyst-role-data_advisor"]') as HTMLButtonElement;
    expect(roleCard.style.background).toBe("var(--aos-accent-light)");
    expect(roleCard.style.color).toBe("var(--aos-text)");
    expect(host.textContent).toContain("需补充条件");
    expect(host.textContent).toContain("OBJECT_TYPE_NOT_INSTALLED");
    expect((host.querySelector('[data-testid="analyst-run-query"]') as HTMLButtonElement).disabled).toBe(true);
  });
});
