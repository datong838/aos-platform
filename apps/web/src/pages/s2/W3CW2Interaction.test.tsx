import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  apiGet: apiMocks.get,
  apiPost: apiMocks.post,
  apiPut: apiMocks.put,
  apiDelete: apiMocks.del,
}));

import { LinkTypeEditorPage } from "./LinkTypeEditorPage";
import { ActionTypeEditorPage } from "./ActionTypeEditorPage";
import { DatasetPreviewPage } from "./DatasetPreviewPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

function byButton(host: HTMLElement, text: string): HTMLButtonElement {
  const button = Array.from(host.querySelectorAll<HTMLButtonElement>("button"))
    .find((item) => item.textContent?.includes(text));
  if (!button) throw new Error(`找不到按钮：${text}`);
  return button;
}

const LINK = {
  id: "lt-usage",
  name: "Usage Link",
  srcType: "Order",
  dstType: "Customer",
  rel: "ordered_by",
  cardinality: "MANY_TO_ONE",
  joinMethod: "foreign_key",
  expectedEdges: 10,
  mdoApproved: false,
  published: true,
  symmetric: false,
  description: "usage test",
  constraints: [],
};

describe("Wave 3C W2 · Link Usage 交互诚实", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    apiMocks.get.mockReset();
    apiMocks.post.mockReset();
    apiMocks.put.mockReset();
    apiMocks.del.mockReset();
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    host.remove();
    vi.unstubAllEnvs();
  });

  async function renderPage() {
    await act(async () => root.render(
      <MemoryRouter initialEntries={["/ontology/link-types/lt-usage"]}>
        <Routes>
          <Route path="/ontology/link-types/:linkId" element={<LinkTypeEditorPage />} />
        </Routes>
      </MemoryRouter>,
    ));
    await flush();
  }

  it("进入 Usage 真读 endpoint：已提供的 0 保持 0，缺失维度显示不可用", async () => {
    apiMocks.get.mockImplementation(async (path: string) => {
      if (path.includes("/usage/link-types/")) {
        return { sources: { workshop: 0, aip: 4 }, window_days: 30 };
      }
      if (path.endsWith("/lt-usage")) return LINK;
      throw new Error(`unexpected ${path}`);
    });
    await renderPage();
    await act(async () => byButton(host, "Usage").click());
    await flush();

    expect(apiMocks.get).toHaveBeenCalledWith("/v1/ontology/usage/link-types/lt-usage");
    expect(host.querySelector("[data-testid='link-usage-workshop']")?.textContent).toContain("0");
    expect(host.querySelector("[data-testid='link-usage-aip']")?.textContent).toContain("4");
    expect(host.querySelector("[data-testid='link-usage-pipeline']")?.textContent).toContain("—");
    expect(host.textContent).toContain("接口未提供");
  });

  it("Usage 失败保留错误且全部指标不可用，刷新只重读 usage", async () => {
    let usageCalls = 0;
    apiMocks.get.mockImplementation(async (path: string) => {
      if (path.includes("/usage/link-types/")) {
        usageCalls += 1;
        throw new Error("usage unavailable");
      }
      if (path.endsWith("/lt-usage")) return LINK;
      throw new Error(`unexpected ${path}`);
    });
    await renderPage();
    await act(async () => byButton(host, "Usage").click());
    await flush();

    expect(host.textContent).toContain("usage unavailable");
    expect(Array.from(host.querySelectorAll("[data-testid^='link-usage-']")))
      .toHaveLength(3);
    expect(Array.from(host.querySelectorAll("[data-testid^='link-usage-']"))
      .every((node) => node.textContent?.includes("—"))).toBe(true);

    await act(async () => byButton(host, "刷新 Usage").click());
    await flush();
    expect(usageCalls).toBe(2);
    expect(apiMocks.put).not.toHaveBeenCalled();
  });
});

describe("Wave 3C W2 · Dataset Preview 来源与回落", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    apiMocks.get.mockReset();
    apiMocks.post.mockReset();
    apiMocks.put.mockReset();
    apiMocks.del.mockReset();
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    host.remove();
    vi.unstubAllEnvs();
  });

  async function renderPage() {
    await act(async () => root.render(
      <MemoryRouter initialEntries={["/data/datasets/ds-orders"]}>
        <Routes>
          <Route path="/data/datasets/:datasetId" element={<DatasetPreviewPage />} />
        </Routes>
      </MemoryRouter>,
    ));
    await flush();
  }

  it("主路径失败且未显式启用 fallback 时保留错误，不注入演示行", async () => {
    apiMocks.get.mockRejectedValue(new Error("preview unavailable"));
    await renderPage();

    expect(host.textContent).toContain("主预览失败：preview unavailable");
    expect(host.textContent).toContain("未启用演示回落");
    expect(host.textContent).not.toContain("ORD-0721-001");
    expect(host.querySelector<HTMLButtonElement>("[data-testid='dataset-export']")?.disabled).toBe(true);
  });

  it("只有显式配置才使用演示 fallback，并同时展示主错误与回落来源", async () => {
    vi.stubEnv("VITE_AOS_DATASET_PREVIEW_DEMO_FALLBACK", "true");
    apiMocks.get.mockRejectedValue(new Error("preview unavailable"));
    await renderPage();

    expect(host.textContent).toContain("主预览失败：preview unavailable");
    expect(host.textContent).toContain("当前来自内置演示数据");
    expect(host.textContent).toContain("ORD-0721-001");
    expect(host.querySelector<HTMLButtonElement>("[data-testid='dataset-export']")?.disabled).toBe(true);
  });

  it("主路径真实空与错误可辨，刷新成功后清错误并恢复可追溯 live 数据", async () => {
    let calls = 0;
    apiMocks.get.mockImplementation(async () => {
      calls += 1;
      if (calls === 1) {
        return {
          dataset_id: "ds-orders",
          columns: ["order_id"],
          rows: [],
          total: 0,
          returned: 0,
          mode: "live",
          synthetic: false,
        };
      }
      return {
        dataset_id: "ds-orders",
        columns: ["order_id"],
        rows: [{ order_id: "ORD-LIVE-1" }],
        total: 1,
        returned: 1,
        mode: "live",
        synthetic: false,
      };
    });
    await renderPage();
    expect(host.textContent).toContain("预览成功但暂无行");

    await act(async () => byButton(host, "刷新预览").click());
    await flush();
    expect(calls).toBe(2);
    expect(host.textContent).toContain("ORD-LIVE-1");
    expect(host.textContent).toContain("来源：主预览 API");
    expect(host.textContent).not.toContain("主预览失败");
    expect(host.querySelector<HTMLButtonElement>("[data-testid='dataset-export']")?.disabled).toBe(false);
  });
});

describe("Wave 3C W2 · Action UI/Capabilities 只读契约", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    apiMocks.get.mockReset();
    apiMocks.post.mockReset();
    apiMocks.put.mockReset();
    apiMocks.del.mockReset();
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    host.remove();
  });

  async function renderPage() {
    apiMocks.get.mockImplementation(async (path: string) => {
      if (path === "/v1/actions/types/CloseWorkOrder") {
        return {
          id: "CloseWorkOrder",
          name: "关闭工单",
          objectType: "WorkOrder",
          parameters: [{ name: "reason", type: "string", required: true }],
          requiredMarkings: ["public"],
          submissionCriteria: [{ field: "reason", op: "required" }],
        };
      }
      if (path.startsWith("/v1/action-rules")) throw new Error("optional rules unavailable");
      throw new Error(`unexpected ${path}`);
    });
    apiMocks.put.mockImplementation(async (_path: string, body: unknown) => body);
    await act(async () => root.render(
      <MemoryRouter initialEntries={["/ontology/action-types/CloseWorkOrder"]}>
        <Routes>
          <Route path="/ontology/action-types/:actionId" element={<ActionTypeEditorPage />} />
        </Routes>
      </MemoryRouter>,
    ));
    await flush();
  }

  it("User Interface 与 Capabilities 控件始终只读，点击和键盘操作不发 PUT", async () => {
    await renderPage();
    await act(async () => byButton(host, "User Interface").click());
    const layout = host.querySelector<HTMLSelectElement>("[data-testid='action-ui-layout']")!;
    expect(layout.disabled).toBe(true);
    await act(async () => layout.dispatchEvent(new Event("change", { bubbles: true })));

    await act(async () => byButton(host, "Capabilities").click());
    const caps = Array.from(host.querySelectorAll<HTMLInputElement>("[data-testid='action-capability']"));
    expect(caps).toHaveLength(6);
    expect(caps.every((input) => input.disabled)).toBe(true);
    await act(async () => caps[0].click());

    expect(host.textContent).toContain("当前只读");
    expect(apiMocks.put).not.toHaveBeenCalled();
  });

  it("受支持字段仍可保存，PUT body 精确匹配后端 DTO", async () => {
    await renderPage();
    const name = Array.from(host.querySelectorAll<HTMLInputElement>("input"))
      .find((input) => input.value === "关闭工单")!;
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(name, "关闭工单 v2");
    await act(async () => name.dispatchEvent(new Event("input", { bubbles: true })));
    await act(async () => byButton(host, "保存").click());
    await flush();

    expect(apiMocks.put).toHaveBeenCalledTimes(1);
    expect(apiMocks.put).toHaveBeenCalledWith(
      "/v1/actions/types/CloseWorkOrder",
      {
        id: "CloseWorkOrder",
        name: "关闭工单 v2",
        objectType: "WorkOrder",
        parameters: [{ name: "reason", type: "string", required: true }],
        requiredMarkings: ["public"],
        submissionCriteria: [{ field: "reason", op: "required" }],
      },
    );
  });
});
