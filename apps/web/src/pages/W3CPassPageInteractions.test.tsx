import { act } from "react";
import { createElement, type ComponentType } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiDelete: vi.fn(),
  probeApiHealth: vi.fn(),
  listObjects: vi.fn(),
  getObject: vi.fn(),
  neighbors: vi.fn(),
}));

vi.mock("../api/client", () => ({
  apiGet: mocks.apiGet,
  apiPost: mocks.apiPost,
  apiPut: mocks.apiPut,
  apiDelete: mocks.apiDelete,
  probeApiHealth: mocks.probeApiHealth,
}));

vi.mock("../api/apiBase", () => ({
  getApiBase: () => "http://127.0.0.1:8080",
}));

vi.mock("../api/ontologyClient", () => ({
  getOntologyClient: () => ({
    listObjects: mocks.listObjects,
    getObject: mocks.getObject,
    neighbors: mocks.neighbors,
  }),
}));

import { ApolloPage } from "./ApolloPage";
import { CapabilityPage } from "./CapabilityPage";
import { LocalPlatformPage } from "./LocalPlatformPage";
import { OntologyPage } from "./OntologyPage";
import { OpsStartGuidePage } from "./OpsStartGuidePage";
import { ProvidersPage } from "./s2/aip";

function buttonByText(host: HTMLElement, text: string): HTMLButtonElement {
  const button = Array.from(host.querySelectorAll("button")).find((node) =>
    node.textContent?.includes(text),
  );
  if (!button) throw new Error(`button not found: ${text}`);
  return button as HTMLButtonElement;
}

async function flushEffects() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
    await Promise.resolve();
  });
}

describe("Wave 3C · six passing pages keep their main interactions honest", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    sessionStorage.clear();
    localStorage.clear();
    vi.clearAllMocks();
    mocks.probeApiHealth.mockResolvedValue({ ok: true, detail: "ok" });
    mocks.apiPost.mockResolvedValue({ ok: true });
    mocks.apiPut.mockResolvedValue({ ok: true });
    mocks.apiDelete.mockResolvedValue({ ok: true });
    mocks.listObjects.mockResolvedValue({ items: [{ id: "wo-1", code: "WO-1" }] });
    mocks.getObject.mockResolvedValue({ id: "wo-1" });
    mocks.neighbors.mockResolvedValue({ items: [] });
    mocks.apiGet.mockImplementation(async (path: string) => {
      if (path === "/v1/aip/capabilities") {
        return { items: [{ id: "video-job", kind: "job", endpoint: "https://jobs.example/v1" }] };
      }
      if (path === "/v1/aip/providers") {
        return { items: [], apiKeyRef: "vault:secret/data/aos/llm#never-render-this-token" };
      }
      if (path === "/v1/aip/llm-provider-plugins") return { items: [], totals: { installed: 0 } };
      if (path === "/v1/aip/gateway-default") return { current: { kind: "agnes" }, options: [] };
      if (path === "/v1/aip/model-runtime/overview") {
        return {
          providers: [],
          resolutions: [
            { readiness: "blocked", blockerCodes: ["PROVIDER_HEALTH_EXPIRED"] },
            { readiness: "blocked", blockerCodes: ["PRICE_SNAPSHOT_MISSING"] },
            { readiness: "blocked", blockerCodes: ["EVAL_GATE_BLOCKED"] },
          ],
        };
      }
      if (path === "/v1/ontology/object-types") {
        return { items: [{ id: "WorkOrder", name: "工作单", description: "live" }] };
      }
      if (path === "/v1/ontology/branches") {
        return { items: [{ id: "main", name: "main", baseRef: "main", readonly: true }] };
      }
      if (path === "/v1/ontology/graph-health") return { score: 98, metrics: {} };
      if (path === "/v1/ontology/link-types" || path === "/v1/actions/types") return { items: [] };
      if (path.includes("/v1/funnel/")) return { stage: "live" };
      if (path === "/v1/ops/local/deps") {
        return { ok: true, items: [{ id: "pg", name: "PostgreSQL", endpoint: "127.0.0.1:5433", ok: true }] };
      }
      if (path === "/v1/ops/local/hub") return { ok: true, message: "可达" };
      if (path === "/v1/apollo/fleet") return { hub: { id: "hub-1", status: "healthy" }, spokes: [], channels: [] };
      if (path === "/v1/apollo/channels") return { items: [{ id: "stable", name: "Stable", status: "ready" }] };
      if (path === "/v1/apollo/spokes") return { items: [] };
      if (path === "/v1/apollo/channels/stable") return { id: "stable", status: "ready", rank: 1 };
      return {};
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  async function render(Page: ComponentType) {
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(Page)));
    });
    await flushEffects();
  }

  it("Capability real connectivity failure cannot become a simulated success", async () => {
    mocks.apiPost.mockRejectedValueOnce(new Error("gateway timeout"));
    await render(CapabilityPage);
    await act(async () => buttonByText(host, "测连通").click());
    await flushEffects();
    expect(host.textContent).toContain("连通测试失败");
    expect(host.textContent).toContain("未执行本地模拟");
    expect(host.textContent).not.toContain("连通正常");
  });

  it("Model Providers distinguishes confirmed empty and never echoes a secret reference", async () => {
    await render(ProvidersPage);
    expect(host.textContent).toContain("服务端已确认暂无已安装插件");
    expect(host.textContent).toContain("0/3 路由 ready");
    expect(host.textContent).not.toContain("never-render-this-token");
  });

  it("Model Providers treats legacy gateway discovery as compatibility and blocks default writes", async () => {
    mocks.apiGet.mockImplementation(async (path: string) => {
      if (path === "/v1/aip/providers") {
        return { items: [{ id: "mock-llm", name: "Legacy Mock", kind: "openai", ready: true }], sidecar: "fallback-mock" };
      }
      if (path === "/v1/aip/llm-provider-plugins") return { items: [], totals: { installed: 0 } };
      if (path === "/v1/aip/gateway-default") {
        return { current: { kind: "mock" }, options: [{ kind: "mock", label: "Local Mock" }] };
      }
      if (path === "/v1/aip/model-runtime/overview") {
        return {
          providers: [{ ref: { assetId: "agnes-text" } }],
          resolutions: [{ readiness: "blocked", blockerCodes: ["PROVIDER_HEALTH_EXPIRED"] }],
        };
      }
      return {};
    });
    await render(ProvidersPage);

    expect(host.textContent).toContain("兼容默认网关（非 canonical 运行权威）");
    expect(host.textContent).toContain("非运行权威");
    expect(host.textContent).not.toContain("Legacy Mock · 运行态");
    expect(buttonByText(host, "保存为默认").disabled).toBe(true);
    expect(mocks.apiPut).not.toHaveBeenCalled();
  });

  it("Model Providers failure does not masquerade as a confirmed empty result", async () => {
    mocks.apiGet.mockImplementation(async (path: string) => {
      if (path === "/v1/aip/providers") throw new Error("providers offline");
      if (path === "/v1/aip/llm-provider-plugins") return { items: [] };
      if (path === "/v1/aip/gateway-default") return { options: [] };
      return {};
    });
    await render(ProvidersPage);
    expect(host.textContent).toContain("providers offline");
    expect(host.textContent).not.toContain("服务端已确认暂无已安装插件");
  });

  it("Model Providers credentials view accepts only an opaque reference", async () => {
    mocks.apiGet.mockImplementation(async (path: string) => {
      if (path === "/v1/aip/providers") return { items: [{ id: "agnes-text", name: "Agnes 文本", kind: "openai", ready: true, apiKeyRef: "keychain://aos/agnes" }] };
      if (path === "/v1/aip/llm-provider-plugins") return { items: [], totals: { installed: 0 } };
      if (path === "/v1/aip/gateway-default") return { options: [] };
      return {};
    });
    await render(ProvidersPage);
    await act(async () => buttonByText(host, "管理凭据").click());
    expect(host.textContent).toContain("凭据引用");
    expect(host.textContent).not.toContain("新密钥");
    expect(host.querySelector('input[type="password"]')).toBeNull();
  });

  it("Ontology Discover searches and opens objects from the live response", async () => {
    await render(OntologyPage);
    const search = host.querySelector('input[type="search"]') as HTMLInputElement;
    await act(async () => {
      search.value = "工作单";
      search.dispatchEvent(new Event("input", { bubbles: true }));
      search.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await act(async () => buttonByText(host, "内嵌").click());
    await flushEffects();
    expect(host.textContent).toContain("工作单");
    expect(mocks.listObjects).toHaveBeenCalledWith("WorkOrder", { branch: "main" });
  });

  it("Local Platform exposes dependency auto-ensure failure", async () => {
    mocks.apiGet.mockImplementation(async (path: string) => {
      if (path === "/v1/ops/local/deps") {
        return { ok: false, items: [{ id: "pg", name: "PostgreSQL", endpoint: "127.0.0.1:5433", ok: false }] };
      }
      if (path === "/v1/ops/local/hub") return { ok: true, message: "可达" };
      return {};
    });
    mocks.apiPost.mockRejectedValueOnce(new Error("docker unavailable"));
    await render(LocalPlatformPage);
    expect(host.textContent).toContain("自动拉起失败：docker unavailable");
    expect(host.textContent).not.toContain("依赖已就绪");
  });

  it("Ops Start Guide tabs change real instructions and keep real links", async () => {
    await render(OpsStartGuidePage);
    expect(host.textContent).toContain("① 单机版");
    await act(async () => buttonByText(host, "④ SaaS 版").click());
    expect(host.textContent).toContain("客户不装本机 Docker 平台");
    expect(host.querySelector('a[href="/settings/local-platform"]')).toBeTruthy();
    expect(host.querySelector('a[href="/apollo"]')).toBeTruthy();
  });

  it("Apollo promote failure remains an error and never emits success", async () => {
    await render(ApolloPage);
    mocks.apiPost.mockRejectedValueOnce(new Error("promotion rejected"));
    await act(async () => buttonByText(host, "Promote 选中 Channel").click());
    await flushEffects();
    expect(host.textContent).toContain("promotion rejected");
    expect(host.textContent).not.toContain("已 promote stable");
  });
});
