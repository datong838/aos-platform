// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const sdk = vi.hoisted(() => ({
  candidates: vi.fn(), memories: vi.fn(), candidateEvents: vi.fn(), query: vi.fn(),
  approveCandidate: vi.fn(), rejectCandidate: vi.fn(), promoteCandidate: vi.fn(), revokeMemory: vi.fn(),
  pipelinePolicies: vi.fn(), pipelineSchedules: vi.fn(), pipelineRuns: vi.fn(),
  pipelineReadiness: vi.fn(),
  transitionPipelineSchedule: vi.fn(), pipelineReceipt: vi.fn(), pipelineCheckpoint: vi.fn(), pipelineAlerts: vi.fn(),
  knowledgeReadiness: vi.fn(),
  agentInstances: vi.fn(), agentProjections: vi.fn(), memoryExposures: vi.fn(), improvementObservations: vi.fn(),
  createAgentProjection: vi.fn(), revokeAgentProjection: vi.fn(), agentProjectionImpact: vi.fn(),
}));
vi.mock("../../api/aipMemory", () => ({ aipMemorySdk: sdk }));

import { MemoryGovernancePage, authoritySubjectLabel, memoryStatusLabel, parseMemoryContributionContext } from "./MemoryGovernancePage";

describe("MemoryGovernancePage", () => {
  let host: HTMLDivElement;
  beforeEach(() => {
    host = document.createElement("div"); document.body.appendChild(host);
    Object.values(sdk).forEach((mock) => mock.mockReset());
    sdk.pipelinePolicies.mockResolvedValue([]); sdk.pipelineSchedules.mockResolvedValue([]); sdk.pipelineRuns.mockResolvedValue([]);
    sdk.pipelineReadiness.mockResolvedValue({
      tenant: { orgId: "org-org", projectId: "dev-project" },
      pipelines: ["seed_import", "operational_learning", "network_learning", "competitor_analysis", "professional_database", "customer_feedback", "human_experience"].map((pipelineKind) => ({
        tenant: { orgId: "org-org", projectId: "dev-project" }, pipelineKind, defaultStatus: "paused",
        dependencyAllowed: false, dependencyReasonCodes: ["dependency_review_unknown"], adapterRequired: false,
        adapterRegistered: true, scheduleCounts: [], runCounts: [], alertCount: 0,
        operationalStatus: "unconfigured", blockerCodes: ["dependency_review_unknown", "schedule_not_registered", "successful_receipt_missing"],
        observedAt: "2026-08-13T00:00:00Z",
      })),
      observedAt: "2026-08-13T00:00:00Z",
    });
    sdk.knowledgeReadiness.mockResolvedValue({ tenant: { orgId: "org-org", projectId: "dev-project" }, package: { status: "authority_unavailable", blocker: "knowledge_package_installation_authority_unavailable" }, sources: [], sourceBlockers: ["knowledge_source_missing"], search: { referenceCount: 0, providerConfigured: false, capabilities: [{ lane: "fulltext", status: "unbuilt", reasonCode: "capability_not_registered", version: 1, observedAt: "2026-08-13T00:00:00Z" }, { lane: "vector", status: "degraded", reasonCode: "degraded_vector_unavailable", version: 1, observedAt: "2026-08-13T00:00:00Z" }, { lane: "rerank", status: "unbuilt", reasonCode: "capability_not_registered", version: 1, observedAt: "2026-08-13T00:00:00Z" }], blockers: ["trusted_search_provider_unavailable", "search_reference_missing"] }, eval: { status: "authority_unavailable", blocker: "gold_set_registry_authority_unavailable" }, observedAt: "2026-08-13T00:00:00Z" });
    sdk.agentInstances.mockResolvedValue([]); sdk.agentProjections.mockResolvedValue([]); sdk.memoryExposures.mockResolvedValue([]); sdk.improvementObservations.mockResolvedValue([]);
  });
  afterEach(() => { host.remove(); });

  it("将权威状态和主体显示成人可读标签", () => {
    expect(memoryStatusLabel("quarantined")).toBe("已隔离");
    expect(authoritySubjectLabel({ resourceType: "Product", resourceId: "p-1" })).toBe("Product · p-1");
  });

  it("只消费受限长度的 exact 贡献上下文", () => {
    const context = parseMemoryContributionContext(new URLSearchParams("subjectType=Product&subjectId=p-1&taskId=task-1&skillId=extract-memory-candidate&logicId=review-to-memory&coworkerId=content-officer&moduleId=content"));
    expect(context).toEqual({ subjectType: "Product", subjectId: "p-1", taskId: "task-1", skillId: "extract-memory-candidate", logicId: "review-to-memory", coworkerId: "content-officer", moduleId: "content" });
    expect(parseMemoryContributionContext(new URLSearchParams(`skillId=${"x".repeat(201)}`)).skillId).toBe("");
  });

  it("深链预填 Skill 查询并展示数字同事贡献链", async () => {
    sdk.candidates.mockResolvedValue([]); sdk.memories.mockResolvedValue([]);
    const root = createRoot(host);
    await act(async () => root.render(<MemoryRouter initialEntries={["/aip/memory-governance?view=query&subjectType=Product&subjectId=p-1&taskId=task-1&skillId=extract-memory-candidate&logicId=review-to-memory&coworkerId=content-officer&moduleId=content"]}><MemoryGovernancePage /></MemoryRouter>));
    await act(async () => undefined);
    expect((host.querySelector('[aria-label="memory-subject-id"]') as HTMLInputElement).value).toBe("p-1");
    expect((host.querySelector('[aria-label="memory-skill-id"]') as HTMLInputElement).value).toBe("extract-memory-candidate");
    expect(host.querySelector('[data-testid="memory-contribution-context"]')?.textContent).toContain("原子 Skill：extract-memory-candidate");
    expect(host.textContent).toContain("Logic 编排：review-to-memory");
    expect(host.textContent).toContain("数字同事：content-officer");
    await act(async () => root.unmount());
  });

  it("真实空列表保持空态，不注入静态知识", async () => {
    sdk.candidates.mockResolvedValue([]); sdk.memories.mockResolvedValue([]);
    const root = createRoot(host);
    await act(async () => root.render(<MemoryRouter><MemoryGovernancePage /></MemoryRouter>));
    await act(async () => undefined);
    expect(host.textContent).toContain("当前没有待治理知识");
    expect(host.textContent).not.toContain("示例知识候选");
    await act(async () => root.unmount());
  });

  it("候选治理展示业务语义并以 exact 版本驳回后回读不可变事件", async () => {
    const candidate = {
      tenant: { orgId: "org-org", projectId: "dev-project" }, candidateId: "candidate-1", status: "pending", scope: "workspace",
      request: {
        candidateLayer: "semantic", taskId: "task-1", runId: "run-1",
        subject: { resourceType: "ecom.product", resourceId: "product-1", revision: "1", authority: "postgresql" },
        payload: { artifactType: "memory_payload", artifactId: "payload-1", revision: "1", contentHash: "a".repeat(64) },
        source: { sourceKind: "authorized_document", sourceUri: "urn:source:1", observedAt: "2026-08-12T00:00:00Z", freshnessExpiresAt: "2026-09-12T00:00:00Z", licenseId: "internal", usagePolicy: "summary-and-citation", contentHash: "b".repeat(64), provider: "栖月汇经营复盘", providerVersion: "1", applicability: ["skill:content"] },
        confidence: 0.9, marking: ["internal"],
      },
      quarantineReasons: [], version: 1, createdAt: "2026-08-12T00:00:00Z", updatedAt: "2026-08-12T00:00:00Z",
    };
    const rejected = { ...candidate, status: "rejected", version: 2 };
    const event = { tenant: candidate.tenant, eventId: "event-2", candidateId: "candidate-1", sequence: 2, eventType: "rejected", fromStatus: "pending", toStatus: "rejected", reasonCodes: ["quality_review_failed"], evidenceRef: null, eventHash: "c".repeat(64), actor: "reviewer", occurredAt: "2026-08-12T00:01:00Z" };
    sdk.candidates.mockResolvedValueOnce([candidate]).mockResolvedValueOnce([rejected]);
    sdk.memories.mockResolvedValue([]);
    sdk.candidateEvents.mockResolvedValueOnce([]).mockResolvedValueOnce([event]);
    sdk.rejectCandidate.mockResolvedValue(rejected);
    const root = createRoot(host);
    await act(async () => root.render(<MemoryRouter><MemoryGovernancePage /></MemoryRouter>)); await act(async () => undefined);
    expect(host.textContent).toContain("商品事实与概念候选");
    expect(host.textContent).toContain("栖月汇经营复盘");
    await act(async () => (Array.from(host.querySelectorAll("button")).find((button) => button.textContent?.includes("商品事实与概念候选")) as HTMLButtonElement).click());
    await act(async () => (host.querySelector('[data-testid="memory-candidate-governance"] summary') as HTMLElement).click());
    await act(async () => (Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "驳回候选") as HTMLButtonElement).click());
    expect(sdk.rejectCandidate).toHaveBeenCalledWith("candidate-1", { expectedVersion: 1, reasonCodes: ["quality_review_failed"] });
    expect(host.textContent).toContain("#2 已拒绝");
    expect(host.textContent).toContain("候选已驳回并保留不可变事件");
    await act(async () => root.unmount());
  });

  it("正式记忆撤销提交 exact 版本和治理原因", async () => {
    const memory = {
      item: { tenant: { orgId: "org-org", projectId: "dev-project" }, memoryItemId: "memory-1", memoryLayer: "semantic", scope: "workspace", status: "active", subject: { resourceType: "ecom.product", resourceId: "product-1", revision: "1", authority: "postgresql" }, currentRevision: 1, version: 3, createdAt: "2026-08-12T00:00:00Z", updatedAt: "2026-08-12T00:00:00Z" },
      revision: { tenant: { orgId: "org-org", projectId: "dev-project" }, memoryItemId: "memory-1", revision: 1, candidateId: "candidate-1", sourceId: "source-1", sourceRevision: 1, payload: { artifactType: "memory_payload", artifactId: "payload-1", revision: "1", contentHash: "a".repeat(64) }, contentHash: "a".repeat(64), confidence: 0.9, applicability: ["skill:content"], markings: ["internal"], effectiveAt: "2026-08-12T00:00:00Z", expiresAt: null, createdBy: "reviewer", createdAt: "2026-08-12T00:00:00Z" },
    };
    sdk.candidates.mockResolvedValue([]); sdk.memories.mockResolvedValueOnce([memory]).mockResolvedValueOnce([{ ...memory, item: { ...memory.item, status: "revoked", version: 4 } }]);
    sdk.revokeMemory.mockResolvedValue({ ...memory, item: { ...memory.item, status: "revoked", version: 4 } });
    const root = createRoot(host);
    await act(async () => root.render(<MemoryRouter><MemoryGovernancePage /></MemoryRouter>)); await act(async () => undefined);
    await act(async () => (host.querySelector('[data-testid="memory-tab-memories"]') as HTMLButtonElement).click());
    await act(async () => (Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "撤销/污染处置") as HTMLButtonElement).click());
    expect(sdk.revokeMemory).toHaveBeenCalledWith("memory-1", { expectedVersion: 3, reasonCode: "contamination_confirmed" });
    expect(host.textContent).toContain("正式记忆已撤销");
    await act(async () => root.unmount());
  });

  it("API 错误失败关闭且 query 初始不自动执行", async () => {
    sdk.candidates.mockRejectedValue(new Error("authority unavailable")); sdk.memories.mockResolvedValue([]);
    const root = createRoot(host);
    await act(async () => root.render(<MemoryRouter><MemoryGovernancePage /></MemoryRouter>));
    await act(async () => undefined);
    expect(host.textContent).toContain("记忆权威读取失败");
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
    expect(host.textContent).toContain("未配置");
    expect(host.textContent).toContain("dependency_review_unknown");
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
