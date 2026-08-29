import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ModelRouterPage } from "./aip";

const apiMocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiDelete: vi.fn(),
}));

vi.mock("../../api/client", () => apiMocks);

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}

const routeConfig = {
  version: 7,
  updatedAt: "2026-08-01T00:00:00Z",
  items: [
    {
      id: "summarize",
      task: "摘要 / 分类",
      primary: "model-a",
      fallback: "model-b",
      egress: "禁公网",
      span: false,
      strategy: "failover",
      weights: [{ model: "model-a", pct: 100 }],
      fallback_chain: ["model-a", "model-b", "报错"],
      circuit_config: {},
      enabled: true,
    },
  ],
};

const runtimeReady = {
  providers: [],
  models: [],
  routes: [],
  policies: [],
  priceSnapshots: [],
  evalGates: [],
  capacityPools: [],
  healthObservations: [],
  resolutions: [{ readiness: "ready", blockerCodes: [] }],
};

describe("Wave 3C W3 · Model Router 单一版本化真源", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    Object.values(apiMocks).forEach((mock) => mock.mockReset());
    apiMocks.apiGet.mockImplementation(async (path: string) => {
      if (path === "/v1/aip/models") {
        return {
          items: [
            { id: "model-a", kind: "chat", ready: true },
            { id: "model-b", kind: "chat", ready: true },
          ],
          defaultTextModel: "model-a",
        };
      }
      if (path === "/v1/aip/models/warmup") return { ready: true, models: [] };
      if (path === "/v1/aip/model-runtime/overview") return runtimeReady;
      if (path === "/api/models/router/draft") return routeConfig;
      if (path === "/api/models/router/draft/circuit-config") return { config: {}, version: 1, updatedAt: "2026-08-29T00:00:00Z", activated: false };
      throw new Error(`unexpected ${path}`);
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  it("加载、编辑与高级面板只读取 canonical router，不读取旧规则真源", async () => {
    await act(async () => root.render(<MemoryRouter><ModelRouterPage /></MemoryRouter>));
    await flush();

    expect(apiMocks.apiGet).toHaveBeenCalledWith("/api/models/router/draft");
    expect(apiMocks.apiGet).not.toHaveBeenCalledWith("/v1/aip/model-routes");
    expect(host.textContent).toContain("草稿版本 v7");
    expect(host.textContent).toContain("摘要 / 分类");
  });

  it("保存携带 expectedVersion，PUT 后 GET 重读一致才报告成功", async () => {
    const saved = {
      ...routeConfig,
      version: 8,
      updatedAt: "2026-08-01T00:01:00Z",
      items: [{ ...routeConfig.items[0], primary: "model-b" }],
    };
    apiMocks.apiPut.mockResolvedValue(saved);
    apiMocks.apiGet.mockImplementation(async (path: string) => {
      if (path === "/v1/aip/models") {
        return { items: [{ id: "model-a", kind: "chat", ready: true }, { id: "model-b", kind: "chat", ready: true }] };
      }
      if (path === "/v1/aip/models/warmup") return { ready: true, models: [] };
      if (path === "/v1/aip/model-runtime/overview") return runtimeReady;
      if (path === "/api/models/router/draft/circuit-config") return { config: {}, version: 1, updatedAt: "2026-08-29T00:00:00Z", activated: false };
      if (path === "/api/models/router/draft") return apiMocks.apiPut.mock.calls.length > 0 ? saved : routeConfig;
      throw new Error(`unexpected ${path}`);
    });
    await act(async () => root.render(<MemoryRouter><ModelRouterPage /></MemoryRouter>));
    await flush();

    const primary = host.querySelector<HTMLSelectElement>("[aria-label='摘要 / 分类-primary']")!;
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")?.set?.call(primary, "model-b");
    await act(async () => primary.dispatchEvent(new Event("change", { bubbles: true })));
    const save = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "保存配置草稿")!;
    await act(async () => save.click());
    await flush();

    expect(apiMocks.apiPut).toHaveBeenCalledWith(
      "/api/models/router/draft",
      expect.objectContaining({ expectedVersion: 7 }),
    );
    expect(apiMocks.apiGet.mock.calls.filter(([path]) => path === "/api/models/router/draft")).toHaveLength(2);
    expect(host.textContent).toContain("路由配置草稿已保存并重读确认 · v8 · 未激活运行");
  });

  it("路由测试携带当前版本且 evaluatedVersion 不一致时 fail-closed", async () => {
    apiMocks.apiPost.mockResolvedValue({
      route_id: "summarize",
      strategy: "failover",
      prompt: "test",
      selected: [{ model: "model-a", weight_pct: 100, reason: "primary" }],
      estimated_latency_ms: 200,
      estimated_input_tokens: 1,
      estimated_output_tokens: 10,
      circuit_state: "closed",
      tested_at: "2026-08-01T00:00:00Z",
      evaluatedVersion: 8,
    });
    await act(async () => root.render(<MemoryRouter><ModelRouterPage /></MemoryRouter>));
    await flush();
    const testTab = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "路由测试")!;
    await act(async () => testTab.click());
    const test = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "测试路由")!;
    await act(async () => test.click());
    await flush();

    expect(apiMocks.apiPost).toHaveBeenCalledWith(
      "/api/models/router/summarize/test",
      expect.objectContaining({ configVersion: 7 }),
    );
    expect(host.textContent).toContain("版本不一致");
    expect(host.textContent).not.toContain("路由测试结果");
  });

  it("运行链未就绪时仍允许维护配置，但演练与调用继续失败关闭", async () => {
    apiMocks.apiGet.mockImplementation(async (path: string) => {
      if (path === "/v1/aip/models") {
        return { items: [{ id: "model-a", kind: "chat", ready: true }], defaultTextModel: "model-a" };
      }
      if (path === "/v1/aip/models/warmup") return { ready: true, models: [] };
      if (path === "/v1/aip/model-runtime/overview") {
        return {
          ...runtimeReady,
          resolutions: [
            { readiness: "blocked", blockerCodes: ["PROVIDER_HEALTH_EXPIRED"] },
            { readiness: "blocked", blockerCodes: ["PRICE_SNAPSHOT_MISSING"] },
            { readiness: "blocked", blockerCodes: ["EVAL_GATE_BLOCKED"] },
          ],
        };
      }
      if (path === "/api/models/router/draft") return routeConfig;
      if (path === "/api/models/router/draft/circuit-config") return { config: {}, version: 1, updatedAt: "2026-08-29T00:00:00Z", activated: false };
      throw new Error(`unexpected ${path}`);
    });
    await act(async () => root.render(<MemoryRouter><ModelRouterPage /></MemoryRouter>));
    await flush();

    expect(host.textContent).toContain("0/3 条路由已就绪");
    expect(host.textContent).toContain("草稿可编辑");
    expect(host.textContent).toContain("存在尚未归类的运行阻断");
    expect(host.querySelector<HTMLSelectElement>("[aria-label='摘要 / 分类-primary']")?.disabled).toBe(false);
    const save = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "保存配置草稿")!;
    const drill = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "熔断演练")!;
    expect(save.disabled).toBe(false);
    expect(drill.disabled).toBe(true);
    expect(apiMocks.apiPut).not.toHaveBeenCalled();
    expect(apiMocks.apiPost).not.toHaveBeenCalled();
  });

  it("保存后重读不一致时保留失败，不显示伪成功", async () => {
    const saved = { ...routeConfig, version: 8, items: [{ ...routeConfig.items[0], primary: "model-b" }] };
    apiMocks.apiPut.mockResolvedValue(saved);
    apiMocks.apiGet.mockImplementation(async (path: string) => {
      if (path === "/v1/aip/models") return { items: [{ id: "model-a", kind: "chat", ready: true }, { id: "model-b", kind: "chat", ready: true }] };
      if (path === "/v1/aip/models/warmup") return { ready: true, models: [] };
      if (path === "/v1/aip/model-runtime/overview") return runtimeReady;
      if (path === "/api/models/router/draft/circuit-config") return { config: {}, version: 1, updatedAt: "2026-08-29T00:00:00Z", activated: false };
      if (path === "/api/models/router/draft") {
        return apiMocks.apiPut.mock.calls.length > 0
          ? { ...saved, items: [{ ...saved.items[0], primary: "model-a" }] }
          : routeConfig;
      }
      throw new Error(`unexpected ${path}`);
    });
    await act(async () => root.render(<MemoryRouter><ModelRouterPage /></MemoryRouter>));
    await flush();
    const primary = host.querySelector<HTMLSelectElement>("[aria-label='摘要 / 分类-primary']")!;
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")?.set?.call(primary, "model-b");
    await act(async () => primary.dispatchEvent(new Event("change", { bubbles: true })));
    const save = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "保存配置草稿")!;
    await act(async () => save.click());
    await flush();

    expect(host.textContent).toContain("配置重读与保存回包不一致");
    expect(host.textContent).not.toContain("已保存并重读确认");
  });
});
