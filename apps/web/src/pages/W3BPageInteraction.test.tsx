import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CapacityPage } from "./s2/CapacityPage";
import { ModelCatalogPage } from "./s2/ModelCatalogPage";
import { ObservabilityPage } from "./s2/ObservabilityPage";
import { StudioPage } from "./StudioPage";

const apiMocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
}));

const evidenceMocks = vi.hoisted(() => ({
  spans: vi.fn(),
  usage: vi.fn(),
}));

vi.mock("../api/client", () => apiMocks);
vi.mock("../api/aipEvidence", () => ({ aipEvidenceSdk: evidenceMocks }));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("Wave 3B W2 · DOM 负向交互", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    apiMocks.apiGet.mockReset();
    apiMocks.apiPost.mockReset();
    apiMocks.apiPut.mockReset();
    evidenceMocks.spans.mockReset();
    evidenceMocks.usage.mockReset();
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  it("Observability 初始空态不读取、不注入 MOCK 或伪功能", async () => {
    await act(async () => root.render(<ObservabilityPage />));
    await flush();

    expect(host.querySelector("[data-testid='observability-idle']")).not.toBeNull();
    expect(host.textContent).not.toContain("2.84M");
    expect(host.querySelector("[data-testid='obs-tab-dashboards']")).toBeNull();
    expect(evidenceMocks.spans).not.toHaveBeenCalled();
    expect(evidenceMocks.usage).not.toHaveBeenCalled();
    expect(apiMocks.apiPut).not.toHaveBeenCalled();
    expect(apiMocks.apiPost).not.toHaveBeenCalled();
  });

  it("Capacity 只从精确 quota head 打开版本编辑，未保存不产生写请求", async () => {
    apiMocks.apiGet.mockImplementation(async (path: string) => {
      if (path.includes("/usage")) return { items: [] };
      if (path.includes("/project-limits")) return { scope: "project", scopeKey: "default", rpmLimit: 60, tpmLimit: 60000 };
      if (path.includes("/user-limits")) return { items: [] };
      if (path === "/v1/aip/model-runtime/overview") return {
        tenant: { orgId: "org-org", projectId: "dev-project" },
        providers: [], models: [], routes: [], policies: [], priceSnapshots: [],
        evalGates: [], capacityPools: [], healthObservations: [], resolutions: [],
        generatedAt: "2026-08-21T00:00:00Z",
      };
      if (path === "/v1/aip/model-runtime/cost-overview") return {
        tenant: { orgId: "org-org", projectId: "dev-project" },
        modelPrices: [], budgets: [], quotas: [{
          quotaPolicyRef: { assetType: "QuotaPolicyRevision", assetId: "quota-1", revision: 1, contentHash: "a".repeat(64) },
          headRef: { assetType: "QuotaPolicyRevision", assetId: "quota-1", revision: 1, contentHash: "a".repeat(64) }, headVersion: 1,
          status: "active", lifecycle: "active", owner: "fde", approvalRef: "approval:quota", rpmLimit: 60, tpmLimit: 60000,
          maxConcurrency: 2, maxInputTokens: 8000, maxOutputTokens: 2000, hourlyRequestLimit: 50, dailyRequestLimit: 200,
          overflowBehavior: "reject", reservationLeaseSeconds: 60, allowPublicProviderFallback: false, allowAutoScale: false,
          effectiveFrom: "2026-08-01T00:00:00Z", effectiveUntil: "2026-09-30T00:00:00Z", blockerCodes: [],
        }],
        usage: {
          state: "unobserved", receiptCount: 0, measuredCount: 0,
          estimatedCount: 0, unknownCount: 0, adjustmentCount: 0,
          costTotals: {}, latestObservedAt: null, truncated: false, periods: [],
        },
        generatedAt: "2026-08-21T00:00:00Z",
      };
      throw new Error(`unexpected ${path}`);
    });
    await act(async () => root.render(<MemoryRouter><CapacityPage /></MemoryRouter>));
    await flush();
    const rateTab = Array.from(host.querySelectorAll("button")).find((button) => button.textContent?.includes("速率限制"))!;
    await act(async () => rateTab.click());
    expect(host.querySelector<HTMLInputElement>("[aria-label='quota-rpm']")?.value).toBe("60");
    expect(host.querySelector<HTMLInputElement>("[aria-label='quota-tpm']")?.value).toBe("60000");
    expect(host.querySelector("[data-testid='save-quota-revision']")).not.toBeNull();
    expect(apiMocks.apiPost).not.toHaveBeenCalled();
    expect(apiMocks.apiPut).not.toHaveBeenCalled();
  });

  it("Model Catalog 失败态不注入静态模型或注册入口", async () => {
    apiMocks.apiGet.mockRejectedValue(new Error("catalog unavailable"));
    await act(async () => root.render(<MemoryRouter><ModelCatalogPage /></MemoryRouter>));
    await flush();
    expect(host.textContent).toContain("不可用");
    expect(host.textContent).not.toContain("注册到供应商");
    expect(host.textContent).not.toContain("GPT-4o");
    expect(apiMocks.apiPost).not.toHaveBeenCalled();
    expect(apiMocks.apiPut).not.toHaveBeenCalled();
  });

  it("Studio Agent 空列表不回填硬编码，新建入口打开安装向导", async () => {
    apiMocks.apiGet.mockImplementation(async (path: string) => path === "/v1/aip/agents" ? { items: [] } : { items: [] });
    await act(async () => root.render(<MemoryRouter><StudioPage /></MemoryRouter>));
    await flush();
    expect(host.querySelector("[data-testid='studio-agents-empty']")).not.toBeNull();
    const create = host.querySelector<HTMLButtonElement>("[data-testid='studio-btn-new-agent']")!;
    expect(create.textContent).toContain("安装数字同事");
    await act(async () => create.click());
    await flush();
    expect(host.querySelector("[data-testid='studio-install-wizard']")).not.toBeNull();
    expect(host.querySelector("[data-testid='studio-install-ecommerce']")).not.toBeNull();
    expect(host.querySelector<HTMLAnchorElement>("[data-testid='studio-install-registry-link']")?.getAttribute("href")).toBe("/aip/agent-registry");
    expect(host.textContent).not.toContain("维修派单 Buddy");
    expect(apiMocks.apiPost).not.toHaveBeenCalled();
  });

  it("Studio 点击数字同事后切换到目标实例配置且不产生写操作", async () => {
    apiMocks.apiGet.mockImplementation(async (path: string) => {
      if (path === "/v1/aip/agents") return {
        items: [
          { id: "agent-private", name: "私域管家", status: "active", tags: ["L2"] },
          { id: "agent-service", name: "客服专员", status: "active", tags: ["L2"] },
        ],
      };
      if (path === "/v1/aip/models") return { defaultTextModel: "—" };
      if (path === "/v1/aip/tools") return { items: [] };
      if (path.endsWith("/prompt")) {
        const agentId = path.includes("agent-service") ? "agent-service" : "agent-private";
        return { agent_id: agentId, prompt: agentId === "agent-service" ? "客服专员提示词" : "私域管家提示词" };
      }
      if (path.endsWith("/tools") || path.endsWith("/guardrails")) {
        const agentId = path.includes("agent-service") ? "agent-service" : "agent-private";
        return { agent_id: agentId, items: [] };
      }
      if (path === "/v1/aip/operational-projection") throw new Error("projection unavailable");
      throw new Error(`unexpected ${path}`);
    });

    await act(async () => root.render(<MemoryRouter initialEntries={["/aip/studio"]}><StudioPage /></MemoryRouter>));
    await flush();
    expect(host.querySelector("h2")?.textContent).toBe("私域管家");

    const target = Array.from(host.querySelectorAll<HTMLElement>("div,button")).find((element) =>
      element.textContent?.trim() === "客服专员",
    )!;
    await act(async () => target.click());
    await flush();

    expect(host.querySelector("h2")?.textContent).toBe("客服专员");
    expect(host.querySelector<HTMLTextAreaElement>("[aria-label='system-prompt']")?.value).toBe("客服专员提示词");
    expect(apiMocks.apiPut).not.toHaveBeenCalled();
    expect(apiMocks.apiPost).not.toHaveBeenCalled();
  });

  it("Studio Try chat 失败保持失败，不显示示意答案", async () => {
    apiMocks.apiGet.mockImplementation(async (path: string) => {
      if (path === "/v1/aip/agents") return { items: [{ id: "a1", name: "真实 Agent", status: "draft", tags: ["L2"] }] };
      if (path.endsWith("/prompt")) return { agent_id: "a1", prompt: "system" };
      if (path.endsWith("/tools")) return { agent_id: "a1", items: [] };
      if (path.endsWith("/guardrails")) return { agent_id: "a1", items: [] };
      if (path === "/v1/aip/tools") return { items: [] };
      if (path === "/v1/aip/models") return { defaultTextModel: "m1" };
      if (path === "/v1/aip/operational-projection") return {
        tenant: { orgId: "org-org", projectId: "dev-project" },
        roles: { definition: 6, bound: 6, enabled: 6, runnable: 6 },
        capabilities: { definition: 10, bound: 10, enabled: 10, runnable: 10 },
        tools: { definition: 12, bound: 12, enabled: 12, runnable: 12 },
        evalGates: { definition: 3, bound: 3, enabled: 3, runnable: 3 },
        routes: { definition: 3, bound: 3, enabled: 3, runnable: 3 },
        overallReadiness: "ready",
        blockerCodes: [],
        sources: { agentReadinessAt: "2026-08-21T01:00:00Z", modelRuntimeAt: "2026-08-21T01:00:01Z" },
        snapshotHash: "a".repeat(64),
        generatedAt: "2026-08-21T01:00:02Z",
      };
      throw new Error(`unexpected ${path}`);
    });
    apiMocks.apiPost.mockRejectedValue(new Error("chat unavailable"));
    await act(async () => root.render(<MemoryRouter><StudioPage /></MemoryRouter>));
    await flush();
    const tryTab = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "试运行")!;
    await act(async () => tryTab.click());
    const query = host.querySelector<HTMLInputElement>("input[placeholder='输入测试问题…']")!;
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(query, "真实订单怎么处理？");
    await act(async () => query.dispatchEvent(new Event("input", { bubbles: true })));
    const send = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "发送")!;
    await act(async () => send.click());
    await flush();
    expect(host.textContent).toContain("chat unavailable");
    expect(host.textContent).toContain("尚未运行；发送后仅展示真实 API 回包");
    expect(host.textContent).not.toContain("建议 Action");
  });
});
