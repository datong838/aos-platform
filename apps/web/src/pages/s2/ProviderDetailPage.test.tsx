import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProviderDetailPage } from "./ProviderDetailPage";

const H = "a".repeat(64);
const ref = (assetType: string, assetId: string) => ({ assetType, assetId, revision: 1, contentHash: H });
const tenant = { orgId: "org-org", projectId: "dev-project" };

describe("canonical Provider detail", () => {
  let host: HTMLDivElement;
  let root: ReturnType<typeof createRoot>;
  beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); });

  it("shows exact authority and never renders a secret reference or plaintext editor", async () => {
    const client = {
      overview: vi.fn().mockResolvedValue({ tenant, providers: [{ ref: ref("ProviderInstanceRevision", "agnes-text-qyh-dev"), lifecycle: "active", dependencyRefs: [ref("ProviderPluginRevision", "agnes-text")] }], models: [], routes: [], policies: [], priceSnapshots: [], evalGates: [], capacityPools: [], healthObservations: [{ tenant, observationId: "health-1", provider: ref("ProviderInstanceRevision", "agnes-text-qyh-dev"), status: "healthy", availabilityPct: 100, p50LatencyMs: 88, observedAt: "2026-08-20T00:00:00Z", expiresAt: "2099-08-20T00:05:00Z" }], resolutions: [], generatedAt: "2026-08-20T00:00:00Z" }),
      provider: vi.fn().mockResolvedValue({ tenant, providerInstanceId: "agnes-text-qyh-dev", revision: 1, contentHash: H, pluginRef: ref("ProviderPluginRevision", "agnes-text"), endpointProfile: { baseUrl: "https://api.agnes-ai.cn/v1", region: "Singapore (International)", timeoutMs: 30000, metadata: {} }, secretRef: "keychain://aos/agnes", secretBackend: "keychain", secretVersion: "1", egressPolicyRef: ref("EgressPolicyRevision", "egress"), dataClassificationPolicyRef: ref("DataClassificationPolicyRevision", "classification"), lifecycle: "active", createdBy: "fde", createdAt: "2026-08-20T00:00:00Z" }),
      providerPlugin: vi.fn().mockResolvedValue({ providerPluginId: "agnes-text", revision: 1, contentHash: H, manifestVersion: "1.0.0", manifestSourceHash: H, sourceRef: "plugins/llm-providers/agnes-text/manifest.json", owner: "AOS/FDE", usageBasis: "internal", approvedCapabilities: ["text", "llm", "chat"], deniedCapabilities: ["image", "audio", "video", "tool_execution"], modalities: ["text"], defaultModels: ["agnes-2.5-flash"], allowedTenants: [tenant], approvalStatus: "approved", approvedBy: "owner", approvedAt: "2026-08-20T00:00:00Z" }),
    };
    await act(async () => {
      root.render(<MemoryRouter initialEntries={["/aip/model-providers/agnes-text"]}><Routes><Route path="/aip/model-providers/:providerId" element={<ProviderDetailPage client={client} />} /></Routes></MemoryRouter>);
      await Promise.resolve();
    });
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)); });
    expect(host.textContent).toContain("Agnes 文本运行权威");
    expect(host.textContent).toContain("Singapore (International)");
    expect(host.textContent).toContain("Health 新鲜");
    expect(host.textContent).toContain("keychain · version 1");
    expect(host.textContent).not.toContain("keychain://aos/agnes");
    expect(host.querySelector('input[type="password"]')).toBeNull();
    expect(client.provider).toHaveBeenCalledWith("agnes-text-qyh-dev");
  });

  it("fails closed when an installed plugin has no published Provider instance", async () => {
    const client = {
      overview: vi.fn().mockResolvedValue({ tenant, providers: [], models: [], routes: [], policies: [], priceSnapshots: [], evalGates: [], capacityPools: [], healthObservations: [], resolutions: [], generatedAt: "2026-08-20T00:00:00Z" }),
      provider: vi.fn(),
      providerPlugin: vi.fn(),
    };
    await act(async () => {
      root.render(<MemoryRouter initialEntries={["/aip/model-providers/vllm"]}><Routes><Route path="/aip/model-providers/:providerId" element={<ProviderDetailPage client={client} />} /></Routes></MemoryRouter>);
      await Promise.resolve();
    });
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)); });
    expect(host.textContent).toContain("尚未发布与 vllm 插件绑定的 ProviderInstanceRevision");
    expect(host.textContent).toContain("不具备路由、Health 或 AgentRun 启动资格");
    expect(client.provider).not.toHaveBeenCalled();
  });
});
