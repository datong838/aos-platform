import { act, createElement, type ComponentProps } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ObjectTypeDetailPanel } from "./objectTypeDetail";

const api = vi.hoisted(() => ({ apiGet: vi.fn(), apiPut: vi.fn() }));
const ontology = vi.hoisted(() => ({ putObject: vi.fn() }));
vi.mock("../../api/client", () => api);
vi.mock("../../api/ontologyClient", () => ({ getOntologyClient: () => ontology }));
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

describe("Wave 3C W1 · Object Type 保存后详情重读", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    Object.values(api).forEach((mock) => mock.mockReset());
    Object.values(ontology).forEach((mock) => mock.mockReset());
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  async function flush() {
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });
  }

  function detail(overrides: Record<string, unknown> = {}) {
    return {
      id: "Order",
      name: "订单",
      description: "订单类型",
      published: false,
      properties: [{ name: "id", type: "string" }],
      rid: "ri.ontology.main.object-type.order",
      apiName: "Order",
      primaryKey: "id",
      titleKey: "id",
      backingDataset: "ds/order",
      syncStrategy: "incremental",
      storageType: "object_storage",
      visibility: "org",
      ...overrides,
    };
  }

  function renderPanel(
    onMetaSaved = vi.fn(),
    overrides: Partial<ComponentProps<typeof ObjectTypeDetailPanel>> = {},
  ) {
    act(() => root.render(createElement(
      MemoryRouter,
      null,
      createElement(ObjectTypeDetailPanel, {
        typeId: "Order",
        typeName: "订单",
        description: "订单类型",
        published: false,
        properties: [{ name: "id", type: "string" }],
        branchId: "main",
        branchReadonly: true,
        instanceCount: 0,
        objects: [],
        onOpenInstance: vi.fn(),
        detail: null,
        neighbors: [],
        onMetaSaved,
        ...overrides,
      }),
    )));
    return onMetaSaved;
  }

  function saveButton(): HTMLButtonElement {
    const found = Array.from(host.querySelectorAll("button")).find((item) =>
      item.textContent?.includes("保存元数据"),
    );
    if (!found) throw new Error("save metadata button not found");
    return found;
  }

  it("PUT 已提交但详情 GET 失败时独立报 verify_failed 且不报成功", async () => {
    let detailReads = 0;
    api.apiGet.mockImplementation((path: string) => {
      if (path === "/v1/ontology/object-types/Order") {
        detailReads += 1;
        return detailReads === 1 ? Promise.resolve(detail()) : Promise.reject(new Error("verify unavailable"));
      }
      if (path === "/v1/metrics") return Promise.resolve({ totals: { count: 0 } });
      return Promise.resolve({ items: [] });
    });
    api.apiPut.mockResolvedValue(detail());
    const onMetaSaved = renderPanel();
    await flush();

    await act(async () => saveButton().click());
    await flush();

    expect(api.apiPut).toHaveBeenCalledTimes(1);
    expect(detailReads).toBe(2);
    expect(host.textContent).toContain("写入已提交但详情重读失败");
    expect(host.textContent).toContain("verify unavailable");
    expect(host.textContent).not.toContain("已保存 Object Type 元数据");
    expect(onMetaSaved).not.toHaveBeenCalled();
  });

  it("详情重读匹配后才应用快照并报告成功", async () => {
    let detailReads = 0;
    api.apiGet.mockImplementation((path: string) => {
      if (path === "/v1/ontology/object-types/Order") {
        detailReads += 1;
        return Promise.resolve(detail(detailReads > 1 ? { description: "订单类型" } : {}));
      }
      if (path === "/v1/metrics") return Promise.resolve({ totals: { count: 0 } });
      return Promise.resolve({ items: [] });
    });
    api.apiPut.mockResolvedValue(detail());
    const onMetaSaved = renderPanel();
    await flush();

    await act(async () => saveButton().click());
    await flush();

    expect(detailReads).toBe(2);
    expect(host.textContent).toContain("已保存并重读 Object Type 详情");
    expect(onMetaSaved).toHaveBeenCalledTimes(1);
  });

  it("分支实例写入校验回包并重读 Object Type 详情", async () => {
    let detailReads = 0;
    api.apiGet.mockImplementation((path: string) => {
      if (path === "/v1/ontology/object-types/Order") {
        detailReads += 1;
        return Promise.resolve(detail());
      }
      if (path === "/v1/metrics") return Promise.resolve({ totals: { count: 0 } });
      return Promise.resolve({ items: [] });
    });
    ontology.putObject.mockResolvedValue({
      ok: true,
      objectType: "Order",
      objectId: "o-1",
      branch: "dev",
      op: "upsert",
    });
    const onBranchSaved = vi.fn();
    renderPanel(vi.fn(), {
      branchId: "dev",
      branchReadonly: false,
      detail: { id: "o-1", title: "O1", status: "open" },
      objects: [{ id: "o-1", title: "O1", status: "open" }],
      onBranchSaved,
    });
    await flush();

    const dataTab = Array.from(host.querySelectorAll("button")).find((item) => item.textContent?.trim() === "Data");
    if (!dataTab) throw new Error("Data tab not found");
    await act(async () => dataTab.click());
    const save = Array.from(host.querySelectorAll("button")).find((item) => item.textContent?.includes("保存到分支 dev"));
    if (!save) throw new Error("branch save button not found");
    await act(async () => save.click());
    await flush();

    expect(ontology.putObject).toHaveBeenCalledTimes(1);
    expect(detailReads).toBe(2);
    expect(host.textContent).toContain("已写入分支 overlay 并重读 Object Type 详情 · dev");
    expect(onBranchSaved).toHaveBeenCalledTimes(1);
  });

  it("typeId 切换后旧保存重读不得回写新对象页面", async () => {
    let orderReads = 0;
    let resolveOldVerify: ((value: ReturnType<typeof detail>) => void) | undefined;
    api.apiGet.mockImplementation((path: string) => {
      if (path === "/v1/ontology/object-types/Order") {
        orderReads += 1;
        if (orderReads === 1) return Promise.resolve(detail());
        return new Promise((resolve) => { resolveOldVerify = resolve; });
      }
      if (path === "/v1/ontology/object-types/Customer") {
        return Promise.resolve(detail({ id: "Customer", name: "客户", apiName: "Customer" }));
      }
      if (path === "/v1/metrics") return Promise.resolve({ totals: { count: 0 } });
      return Promise.resolve({ items: [] });
    });
    api.apiPut.mockResolvedValue(detail());
    const oldSaved = renderPanel();
    await flush();

    await act(async () => saveButton().click());
    await flush();
    expect(orderReads).toBe(2);

    renderPanel(vi.fn(), {
      typeId: "Customer",
      typeName: "客户",
      description: "客户类型",
      properties: [{ name: "customer_id", type: "string" }],
    });
    await flush();
    if (!resolveOldVerify) throw new Error("old verification request not captured");
    await act(async () => resolveOldVerify?.(detail()));
    await flush();

    expect(host.textContent).toContain("客户");
    expect(host.textContent).not.toContain("已保存并重读 Object Type 详情");
    expect(oldSaved).not.toHaveBeenCalled();
    expect(saveButton().disabled).toBe(false);
  });
});
