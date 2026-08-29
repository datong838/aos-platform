import { act, createElement, useEffect } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, Route, Routes, useNavigate, type NavigateFunction } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { selectedDatasetRid, sourceSyncStatusLabel, SourceDetailPage } from "./sourceDetailPage";

const api = vi.hoisted(() => ({ apiGet: vi.fn(), apiPost: vi.fn() }));
vi.mock("../../api/client", () => ({ ...api, apiPut: vi.fn(), apiDelete: vi.fn() }));
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

describe("Wave 3C W1 · Source Detail 全量刷新与竞态", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    Object.values(api).forEach((mock) => mock.mockReset());
    api.apiPost.mockResolvedValue({ columns: ["id"], rows: [{ id: 1 }], total: 1 });
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  async function flush(rounds = 6) {
    await act(async () => {
      for (let index = 0; index < rounds; index += 1) await Promise.resolve();
    });
  }

  function RouteHarness({ capture }: { capture?: (navigate: NavigateFunction) => void }) {
    const navigate = useNavigate();
    useEffect(() => capture?.(navigate), [capture, navigate]);
    return createElement(
      Routes,
      null,
      createElement(Route, { path: "/data/sources/:sourceId", element: createElement(SourceDetailPage) }),
    );
  }

  function renderAt(path: string, capture?: (navigate: NavigateFunction) => void) {
    act(() => root.render(createElement(
      MemoryRouter,
      { initialEntries: [path] },
      createElement(RouteHarness, { capture }),
    )));
  }

  async function openExplore() {
    const button = Array.from(host.querySelectorAll("button")).find(
      (item) => item.textContent?.trim() === "探索",
    );
    if (!button) throw new Error("explore tab not found");
    await act(async () => button.click());
    await flush(4);
  }

  function listResponse(path: string) {
    if (path === "/v1/sources") {
      return { items: [
        { id: "s1", type: "jdbc-postgres", status: "active" },
        { id: "s2", type: "jdbc-postgres", status: "active" },
      ] };
    }
    return { items: [] };
  }

  it("源表不借用管道数据集，管道派生表只打开自身数据集", () => {
    expect(selectedDatasetRid({ schema: "shop", table: "orders" }, { datasetRid: "dataset-orders" })).toBeUndefined();
    expect(selectedDatasetRid(null, { datasetRid: "dataset-orders" })).toBe("dataset-orders");
  });

  it("同步运行状态使用运行结果口径，不把成功翻译为在线", () => {
    expect(sourceSyncStatusLabel("SUCCEEDED")).toBe("成功");
    expect(sourceSyncStatusLabel("RUNNING")).toBe("运行中");
    expect(sourceSyncStatusLabel("FAILED")).toBe("失败");
    expect(sourceSyncStatusLabel()).toBe("未读取");
  });

  it("Schema 失败时诚实显示空状态，不回落本地演示数据", async () => {
    api.apiGet.mockImplementation((path: string) => {
      if (path.startsWith("/api/datasource/sources/s1/schemas")) {
        return Promise.reject(new Error("schema unavailable"));
      }
      return Promise.resolve(listResponse(path));
    });
    api.apiPost.mockRejectedValue(new Error("preview unavailable"));
    renderAt("/data/sources/s1");
    await flush(12);
    await openExplore();

    expect(host.textContent).toContain("Schema 加载失败：schema unavailable");
    expect(host.textContent).toContain("当前来源：连接失败");
    expect(host.textContent).toContain("暂无 Schema");
    expect(host.textContent).not.toContain("public.orders");
    expect(api.apiPost).not.toHaveBeenCalled();
  });

  it("页头刷新重读全部页面依赖并用新 Schema 覆盖旧树", async () => {
    let refreshed = false;
    const calls = new Map<string, number>();
    api.apiGet.mockImplementation((path: string) => {
      calls.set(path, (calls.get(path) || 0) + 1);
      if (path === "/api/datasource/sources/s1/schemas") {
        return Promise.resolve({ items: [{ name: refreshed ? "fresh" : "old" }] });
      }
      if (path.endsWith("/tables")) {
        return Promise.resolve({ items: [{ name: refreshed ? "orders_v2" : "orders_v1" }] });
      }
      if (path.endsWith("/columns")) {
        return Promise.resolve({ items: [{ name: refreshed ? "new_id" : "old_id", datatype: "BIGINT" }] });
      }
      return Promise.resolve(listResponse(path));
    });
    renderAt("/data/sources/s1");
    await flush(12);
    await openExplore();
    expect(host.textContent).toContain("old.orders_v1");

    const dependencyPaths = ["/v1/sources", "/v1/pipelines", "/v1/datasets", "/v1/syncs", "/v1/connector-plugins"];
    const before = Object.fromEntries(dependencyPaths.map((path) => [path, calls.get(path) || 0]));
    refreshed = true;
    const refresh = Array.from(host.querySelectorAll("button")).find((item) => item.textContent?.trim() === "刷新");
    if (!refresh) throw new Error("header refresh button not found");
    await act(async () => refresh.click());
    await flush(16);

    for (const path of dependencyPaths) expect(calls.get(path) || 0).toBeGreaterThan(before[path]);
    expect(host.textContent).toContain("fresh.orders_v2");
    expect(calls.has("/api/datasource/sources/s1/schemas/fresh/tables/orders_v2/columns")).toBe(true);
    expect(host.textContent).toContain("id");
    expect(host.textContent).not.toContain("old.orders_v1");
  });

  it("sourceId 切换后旧 Schema 请求不得覆盖新页面", async () => {
    const pendingFirst: Array<(value: { items: { name: string }[] }) => void> = [];
    api.apiGet.mockImplementation((path: string) => {
      if (path === "/api/datasource/sources/s1/schemas") {
        return new Promise((resolve) => pendingFirst.push(resolve));
      }
      if (path === "/api/datasource/sources/s2/schemas") {
        return Promise.resolve({ items: [{ name: "second" }] });
      }
      if (path.includes("/schemas/second/tables")) return Promise.resolve({ items: [{ name: "current_table" }] });
      if (path.includes("/schemas/first/tables")) return Promise.resolve({ items: [{ name: "stale_table" }] });
      if (path.endsWith("/columns")) return Promise.resolve({ items: [{ name: "id", datatype: "BIGINT" }] });
      return Promise.resolve(listResponse(path));
    });
    let navigate: NavigateFunction | undefined;
    renderAt("/data/sources/s1", (next) => { navigate = next; });
    await flush();
    await openExplore();
    if (!navigate) throw new Error("navigate not captured");
    await act(async () => navigate?.("/data/sources/s2"));
    await flush(12);
    expect(host.textContent).toContain("second.current_table");

    await act(async () => {
      for (const resolve of pendingFirst) resolve({ items: [{ name: "first" }] });
      await Promise.resolve();
      await Promise.resolve();
    });
    await flush(8);

    expect(host.textContent).toContain("second.current_table");
    expect(host.textContent).not.toContain("first.stale_table");
  });
});
