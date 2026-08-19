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

  it("Capacity Cancel 恢复服务端项目快照且不产生 PUT", async () => {
    apiMocks.apiGet.mockImplementation(async (path: string) => {
      if (path.includes("/usage")) return { items: [] };
      if (path.includes("/project-limits")) return { scope: "project", scopeKey: "default", rpmLimit: 60, tpmLimit: 60000 };
      if (path.includes("/user-limits")) return { items: [] };
      throw new Error(`unexpected ${path}`);
    });
    await act(async () => root.render(<MemoryRouter><CapacityPage /></MemoryRouter>));
    await flush();
    const rateTab = Array.from(host.querySelectorAll("button")).find((button) => button.textContent?.includes("速率限制"))!;
    await act(async () => rateTab.click());
    await act(async () => host.querySelector<HTMLButtonElement>("[data-testid='manage-project-limit']")!.click());
    const rpm = host.querySelector<HTMLInputElement>("[aria-label='capacity-rpm']")!;
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(rpm, "99");
    await act(async () => rpm.dispatchEvent(new Event("input", { bubbles: true })));
    const cancel = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "取消")!;
    await act(async () => cancel.click());
    expect(host.querySelector("[data-testid='capacity-editor-project']")).toBeNull();
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

  it("Studio Try chat 失败保持失败，不显示示意答案", async () => {
    apiMocks.apiGet.mockImplementation(async (path: string) => {
      if (path === "/v1/aip/agents") return { items: [{ id: "a1", name: "真实 Agent", status: "draft", tags: ["L2"] }] };
      if (path.endsWith("/prompt")) return { agent_id: "a1", prompt: "system" };
      if (path.endsWith("/tools")) return { agent_id: "a1", items: [] };
      if (path.endsWith("/guardrails")) return { agent_id: "a1", items: [] };
      if (path === "/v1/aip/tools") return { items: [] };
      if (path === "/v1/aip/models") return { defaultTextModel: "m1" };
      throw new Error(`unexpected ${path}`);
    });
    apiMocks.apiPost.mockRejectedValue(new Error("chat unavailable"));
    await act(async () => root.render(<MemoryRouter><StudioPage /></MemoryRouter>));
    await flush();
    const tryTab = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "试运行")!;
    await act(async () => tryTab.click());
    const send = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "发送")!;
    await act(async () => send.click());
    await flush();
    expect(host.textContent).toContain("chat unavailable");
    expect(host.textContent).toContain("尚未运行；发送后仅展示真实 API 回包");
    expect(host.textContent).not.toContain("建议 Action");
  });
});
