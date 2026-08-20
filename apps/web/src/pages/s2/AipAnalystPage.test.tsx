// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AipAnalystPage, buildGovernedQuery } from "./AipAnalystPage";
import type { QueryResultRevision } from "../../api/aipWorkbench";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const exact = { resourceType: "Task", resourceId: "task-1", revision: "1", authority: "aip-task" };

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
    const listObjectTypes = vi.fn().mockResolvedValue([{ id: "Order", name: "订单" }]);
    await act(async () => root.render(<MemoryRouter><AipAnalystPage runQuery={runQuery} listObjectTypes={listObjectTypes} /></MemoryRouter>));
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
    };
    const runQuery = vi.fn().mockResolvedValueOnce(result).mockRejectedValueOnce(new Error("authority unavailable"));
    const listObjectTypes = vi.fn().mockResolvedValue([{ id: "Order", name: "订单" }]);
    await act(async () => root.render(<MemoryRouter><AipAnalystPage runQuery={runQuery} listObjectTypes={listObjectTypes} /></MemoryRouter>));
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    const run = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "运行真实查询")!;
    await act(async () => run.click());
    expect(host.textContent).toContain("r3");
    await act(async () => run.click());
    expect(host.textContent).toContain("请求失败：authority unavailable");
    expect(host.textContent).not.toContain("r3");
    expect(host.textContent).not.toContain("Northampton");
  });

  it("loads Object Types from authority and refuses demo fallback when empty", async () => {
    const listObjectTypes = vi.fn().mockResolvedValue([]);
    await act(async () => root.render(<MemoryRouter><AipAnalystPage listObjectTypes={listObjectTypes} /></MemoryRouter>));
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(host.textContent).toContain("当前租户暂无已安装 Object Type；不生成演示类型");
    expect(host.textContent).not.toContain("Northampton");
    expect(host.querySelector('[data-testid="analyst-run-query"]')).toBeTruthy();
    expect((host.querySelector('[data-testid="analyst-run-query"]') as HTMLButtonElement).disabled).toBe(true);
  });
});
