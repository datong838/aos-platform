// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const sdk = vi.hoisted(() => ({
  candidates: vi.fn(), memories: vi.fn(), candidateEvents: vi.fn(), query: vi.fn(),
  pipelinePolicies: vi.fn(), pipelineSchedules: vi.fn(), pipelineRuns: vi.fn(),
  transitionPipelineSchedule: vi.fn(), pipelineReceipt: vi.fn(), pipelineCheckpoint: vi.fn(), pipelineAlerts: vi.fn(),
  knowledgeReadiness: vi.fn(),
  agentInstances: vi.fn(), agentProjections: vi.fn(), memoryExposures: vi.fn(), improvementObservations: vi.fn(),
  createAgentProjection: vi.fn(), revokeAgentProjection: vi.fn(), agentProjectionImpact: vi.fn(),
}));
vi.mock("../../api/aipMemory", () => ({ aipMemorySdk: sdk }));

import { MemoryGovernancePage, authoritySubjectLabel, memoryStatusLabel } from "./MemoryGovernancePage";

describe("MemoryGovernancePage", () => {
  let host: HTMLDivElement;
  beforeEach(() => {
    host = document.createElement("div"); document.body.appendChild(host);
    Object.values(sdk).forEach((mock) => mock.mockReset());
    sdk.pipelinePolicies.mockResolvedValue([]); sdk.pipelineSchedules.mockResolvedValue([]); sdk.pipelineRuns.mockResolvedValue([]);
    sdk.knowledgeReadiness.mockResolvedValue({ tenant: { orgId: "org-org", projectId: "dev-project" }, package: { status: "authority_unavailable", blocker: "knowledge_package_installation_authority_unavailable" }, sources: [], sourceBlockers: ["knowledge_source_missing"], search: { referenceCount: 0, providerConfigured: false, capabilities: [{ lane: "fulltext", status: "unbuilt", reasonCode: "capability_not_registered", version: 1, observedAt: "2026-08-13T00:00:00Z" }, { lane: "vector", status: "degraded", reasonCode: "degraded_vector_unavailable", version: 1, observedAt: "2026-08-13T00:00:00Z" }, { lane: "rerank", status: "unbuilt", reasonCode: "capability_not_registered", version: 1, observedAt: "2026-08-13T00:00:00Z" }], blockers: ["trusted_search_provider_unavailable", "search_reference_missing"] }, eval: { status: "authority_unavailable", blocker: "gold_set_registry_authority_unavailable" }, observedAt: "2026-08-13T00:00:00Z" });
    sdk.agentInstances.mockResolvedValue([]); sdk.agentProjections.mockResolvedValue([]); sdk.memoryExposures.mockResolvedValue([]); sdk.improvementObservations.mockResolvedValue([]);
  });
  afterEach(() => { host.remove(); });

  it("将权威状态和主体显示成人可读标签", () => {
    expect(memoryStatusLabel("quarantined")).toBe("已隔离");
    expect(authoritySubjectLabel({ resourceType: "Product", resourceId: "p-1" })).toBe("Product · p-1");
  });

  it("真实空列表保持空态，不注入静态知识", async () => {
    sdk.candidates.mockResolvedValue([]); sdk.memories.mockResolvedValue([]);
    const root = createRoot(host);
    await act(async () => root.render(<MemoryRouter><MemoryGovernancePage /></MemoryRouter>));
    await act(async () => undefined);
    expect(host.textContent).toContain("当前租户没有待治理或历史 Candidate");
    expect(host.textContent).not.toContain("示例 Candidate");
    await act(async () => root.unmount());
  });

  it("API 错误失败关闭且 query 初始不自动执行", async () => {
    sdk.candidates.mockRejectedValue(new Error("authority unavailable")); sdk.memories.mockResolvedValue([]);
    const root = createRoot(host);
    await act(async () => root.render(<MemoryRouter><MemoryGovernancePage /></MemoryRouter>));
    await act(async () => undefined);
    expect(host.textContent).toContain("Memory authority 读取失败");
    expect(sdk.query).not.toHaveBeenCalled();
    await act(async () => root.unmount());
  });

  it("七条策略无 Schedule 时诚实禁用，不伪造运行", async () => {
    sdk.candidates.mockResolvedValue([]); sdk.memories.mockResolvedValue([]);
    sdk.pipelinePolicies.mockResolvedValue([{ pipelineKind: "seed_import", allowedTriggers: ["manual"], defaultStatus: "paused", requiredDependencies: ["license"], allowedReceiptTypes: ["aip.artifact_receipt"], allowedSourceKinds: ["authorized_document"] }]);
    const root = createRoot(host);
    await act(async () => root.render(<MemoryRouter><MemoryGovernancePage /></MemoryRouter>));
    await act(async () => undefined);
    const tab = host.querySelector('[data-testid="memory-tab-pipelines"]') as HTMLButtonElement;
    await act(async () => tab.click());
    expect(host.textContent).toContain("种子知识导入");
    expect(host.textContent).toContain("未注册 Schedule");
    expect((Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "等待权威配置") as HTMLButtonElement).disabled).toBe(true);
    await act(async () => root.unmount());
  });

  it("已暂停 Schedule 的启用动作调用真实 transition API", async () => {
    sdk.candidates.mockResolvedValue([]); sdk.memories.mockResolvedValue([]);
    sdk.pipelinePolicies.mockResolvedValue([{ pipelineKind: "seed_import", allowedTriggers: ["manual"], defaultStatus: "paused", requiredDependencies: ["license"], allowedReceiptTypes: ["aip.artifact_receipt"], allowedSourceKinds: ["authorized_document"] }]);
    sdk.pipelineSchedules.mockResolvedValue([{ tenant: { orgId: "org-org", projectId: "dev-project" }, scheduleId: "seed-1", pipelineKind: "seed_import", trigger: "manual", config: { artifactType: "pipeline-config", artifactId: "config-1", revision: "1", contentHash: "a".repeat(64) }, status: "paused", checkpointVersion: 0, version: 3, createdAt: "2026-08-13T00:00:00Z", updatedAt: "2026-08-13T00:00:00Z" }]);
    sdk.transitionPipelineSchedule.mockResolvedValue({});
    const root = createRoot(host);
    await act(async () => root.render(<MemoryRouter><MemoryGovernancePage /></MemoryRouter>));
    await act(async () => undefined);
    await act(async () => (host.querySelector('[data-testid="memory-tab-pipelines"]') as HTMLButtonElement).click());
    const action = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "尝试启用") as HTMLButtonElement;
    await act(async () => action.click());
    expect(sdk.transitionPipelineSchedule).toHaveBeenCalledWith("seed-1", expect.objectContaining({ expectedVersion: 3, fromStatus: "paused", toStatus: "active" }));
    await act(async () => root.unmount());
  });

  it("冷启动与检索视图展示真实租户空态和权威缺口", async () => {
    sdk.candidates.mockResolvedValue([]); sdk.memories.mockResolvedValue([]);
    const root = createRoot(host);
    await act(async () => root.render(<MemoryRouter><MemoryGovernancePage /></MemoryRouter>));
    await act(async () => undefined);
    await act(async () => (host.querySelector('[data-testid="memory-tab-readiness"]') as HTMLButtonElement).click());
    expect(host.textContent).toContain("org-org / dev-project");
    expect(host.textContent).toContain("权威映射尚未建立");
    expect(host.textContent).toContain("0 条");
    expect(host.textContent).toContain("trusted_search_provider_unavailable");
    expect(host.textContent).not.toContain("美妆知识已安装");
    await act(async () => root.unmount());
  });

  it("数字同事记忆没有真实实例时展示诚实空态并禁用创建", async () => {
    sdk.candidates.mockResolvedValue([]); sdk.memories.mockResolvedValue([]);
    const root = createRoot(host);
    await act(async () => root.render(<MemoryRouter><MemoryGovernancePage /></MemoryRouter>)); await act(async () => undefined);
    await act(async () => (host.querySelector('[data-testid="memory-tab-agents"]') as HTMLButtonElement).click()); await act(async () => undefined);
    expect(host.textContent).toContain("当前租户没有真实数字同事实例");
    expect(host.textContent).not.toContain("私域管家");
    await act(async () => root.unmount());
  });

  it("数字同事实例尚在 provisioning 时展示真实版本状态并禁用投影", async () => {
    sdk.candidates.mockResolvedValue([]); sdk.memories.mockResolvedValue([]);
    sdk.agentInstances.mockResolvedValue([{ tenant: { orgId: "org-org", projectId: "dev-project" }, instanceId: "ecommerce.content_officer.default", instanceRef: { assetType: "AgentInstance", assetId: "ecommerce.content_officer.default", revision: 1, contentHash: "a".repeat(64) }, template: { assetType: "AgentTemplate", assetId: "ecommerce.content_officer", revision: 1, contentHash: "b".repeat(64) }, status: "provisioning", overlay: { displayName: "内容官", allowedCapabilityIds: [] }, version: 1, createdBy: "installer", createdAt: "2026-08-15T00:00:00Z", updatedAt: "2026-08-15T00:00:00Z" }]);
    const root = createRoot(host);
    await act(async () => root.render(<MemoryRouter><MemoryGovernancePage /></MemoryRouter>)); await act(async () => undefined);
    await act(async () => (host.querySelector('[data-testid="memory-tab-agents"]') as HTMLButtonElement).click()); await act(async () => undefined);
    expect(host.textContent).toContain("当前租户有 1 个真实数字同事实例，但尚无 active 实例");
    expect(host.textContent).toContain("内容官 · 准备中");
    expect(host.textContent).toContain("v1 · 准备中");
    expect(host.textContent).toContain("当前实例状态为 provisioning，尚不可创建记忆投影");
    const create = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "创建个人引用") as HTMLButtonElement;
    expect(create.disabled).toBe(true);
    await act(async () => root.unmount());
  });

  it("数字同事记忆展示 exact 实例、投影和 unknown 诚实结论", async () => {
    sdk.candidates.mockResolvedValue([]); sdk.memories.mockResolvedValue([]);
    const instanceRef = { assetType: "AgentInstance", assetId: "content-agent", revision: 2, contentHash: "a".repeat(64) };
    sdk.agentInstances.mockResolvedValue([{ tenant: { orgId: "org-org", projectId: "dev-project" }, instanceId: "content-agent", instanceRef, template: { assetType: "AgentTemplate", assetId: "content", revision: 1, contentHash: "b".repeat(64) }, status: "active", overlay: { displayName: "内容官", allowedCapabilityIds: [] }, version: 2, createdBy: "admin", createdAt: "2026-08-15T00:00:00Z", updatedAt: "2026-08-15T00:00:00Z" }]);
    sdk.agentProjections.mockResolvedValue([{ tenant: { orgId: "org-org", projectId: "dev-project" }, projectionRef: { projectionId: "projection-1", version: 1, contentHash: "c".repeat(64) }, kind: "personal", ownerInstanceRef: instanceRef, memoryRef: { memoryItemId: "memory-1", revision: 1, contentHash: "d".repeat(64) }, recipientInstanceRefs: [], allowedPurposes: ["skill:content"], allowedMarkings: ["internal"], disclosure: "citation_only", status: "stale", effectiveAt: "2026-08-15T00:00:00Z", expiresAt: "2026-11-15T00:00:00Z", createdBy: "admin", createdAt: "2026-08-15T00:00:00Z", updatedAt: "2026-08-15T00:00:00Z" }]);
    sdk.improvementObservations.mockResolvedValue([{ tenant: { orgId: "org-org", projectId: "dev-project" }, observationId: "observation-1", agentInstanceRef: instanceRef, metricDefinitionRef: {}, evalContractRef: {}, exposureRefs: [], metrics: [], quality: "unknown", sourceRefs: [], cutoffAt: "2026-08-15T00:00:00Z", observedAt: "2026-08-15T00:00:01Z", conclusion: "insufficient_evidence", limitations: ["sample_size_below_minimum"], observationHash: "e".repeat(64) }]);
    const root = createRoot(host);
    await act(async () => root.render(<MemoryRouter><MemoryGovernancePage /></MemoryRouter>)); await act(async () => undefined);
    await act(async () => (host.querySelector('[data-testid="memory-tab-agents"]') as HTMLButtonElement).click()); await act(async () => undefined);
    expect(host.textContent).toContain("内容官"); expect(host.textContent).toContain("v2"); expect(host.textContent).toContain("Memory/实例 exact ref 已漂移");
    expect(host.textContent).toContain("证据不足（unknown）· 不可判定提升"); expect(host.textContent).not.toContain("baseline 0.0%");
    await act(async () => root.unmount());
  });
});
