import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ecommerceWorkshopClient, type SourceReadinessEnvelope } from "../../api/ecommerceWorkshop";
import { setTenant } from "../../api/tenant";
import { EcommerceWorkshopCatalogProvider } from "./EcommerceWorkshopCatalogContext";
import { EcommerceWorkshopHost } from "./EcommerceWorkshopHost";
import { moduleWithReadiness, workshopCatalogFixture } from "./workshopTestFixtures";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const sourcePipelines = ["P01-shop-qyh", "P02-product-qyh", "P03-product-sku-qyh", "P04-category-qyh", "P05-order-qyh", "P06-order-line-qyh", "P07-shipment-qyh", "P08-customer-lite-qyh", "P09-weapp-qyh", "P10-system-config-qyh", "P11-product-review-qyh", "P12-payment-qyh"];
const sourceCutoff = "2026-08-21T14:00:00Z";
const sourceBlocker = "SOURCE_CONFIG_EXACT_REF_MISSING";
const sourceReadiness: SourceReadinessEnvelope = {
  schemaVersion: "aos.source-readiness/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, checkedAt: sourceCutoff, cutoffAt: sourceCutoff, status: "blocked", receiptRef: null,
  sources: sourcePipelines.map((pipelineId) => ({ schemaVersion: "aos.source-readiness/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, sourceId: "niushop-qyh", pipelineId, objectType: "Object", status: "blocked", checkedAt: sourceCutoff, observedAt: sourceCutoff, sourceEventAt: null, projectedAt: sourceCutoff, dataCutoff: sourceCutoff, freshnessExpiresAt: null, sourceConfigRef: null, mappingRef: null, schemaRef: null, maskingPolicyRef: null, freshnessPolicyRef: null, qualityPolicyRef: null, reconciliationPolicyRef: null, queryCapabilityRef: null, latestRun: { runId: "run-1", status: "succeeded", scheduledFor: sourceCutoff, startedAt: sourceCutoff, finishedAt: sourceCutoff, rowsWritten: 1, errorCode: null }, counts: { sourceTotal: 1, sourceActive: 1, sourceDeleted: 0, projectionTotal: 1, unexplainedDelta: 0 }, quality: { status: "unknown", ruleRef: null, summary: null }, reconciliation: { status: "unknown", ruleRef: null, summary: null }, reasons: [sourceBlocker], blockers: [sourceBlocker] })),
};

describe("EcommerceWorkshopHost task cockpit", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { sessionStorage.clear(); setTenant({ orgId: "org-org", projectId: "dev-project", workspaceName: "real" }); host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { vi.restoreAllMocks(); act(() => root.unmount()); host.remove(); });

  it("只在 canonical task-cockpit Module 中挂载 partial read page，并保持 Shell 唯一 H1", async () => {
    const taskModule = moduleWithReadiness("degraded"); Object.assign(taskModule, { moduleId: "ecommerce.task-cockpit", displayName: "日常任务总控大屏", menuLabel: "日常任务总控大屏", route: "/workshop/cockpit" });
    const catalog = { listModules: vi.fn().mockResolvedValue(workshopCatalogFixture({ items: [taskModule] })) };
    const sourceSpy = vi.spyOn(ecommerceWorkshopClient, "getSourceReadiness").mockResolvedValue(sourceReadiness);
    vi.spyOn(ecommerceWorkshopClient, "getTaskCockpitCore").mockResolvedValue({ schemaVersion: "aos.ecommerce-workshop.task-cockpit/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: "2026-08-15T10:00:00Z", taskCutoff: "2026-08-15T10:00:00Z", stateConsistency: "current_state_per_page", readiness: "degraded", blockers: [
      { code: "TASK_COCKPIT_STAGE_MAPPING_RUN_SCOPED", severity: "warning", dependency: "stage", requiredAction: "按 Run 展开" }, { code: "TASK_COCKPIT_BUSINESS_CONTEXT_INDEPENDENT_SNAPSHOT", severity: "warning", dependency: "business-context:ecommerce.source-readiness", requiredAction: "按独立 cutoff 展示" },
    ], items: [], page: { limit: 20, count: 0, hasMore: false, nextCursor: null } });
    await act(async () => root.render(<MemoryRouter initialEntries={["/workshop/cockpit"]}><EcommerceWorkshopCatalogProvider client={catalog}><EcommerceWorkshopHost /></EcommerceWorkshopCatalogProvider></MemoryRouter>));
    expect(host.querySelectorAll("h1")).toHaveLength(1); expect(host.textContent).toContain("日常任务总控大屏"); expect(host.textContent).toContain("数据源就绪度"); expect(host.textContent).toContain("当前只读范围"); expect(host.textContent).toContain("当前权威 Task 集合为空");
    expect(host.textContent).toContain("业务上下文 · 独立 SourceReadiness 快照"); expect(host.textContent).toContain("0 / 12"); expect(host.textContent).toContain("无 exact EvidencePack Receipt");
    expect(sourceSpy).toHaveBeenCalledTimes(1);
  });

  it("Module authority 未验证时仍暴露只读视图，并同时保留 unknown 阻断", async () => {
    const taskModule = moduleWithReadiness("unknown"); Object.assign(taskModule, { moduleId: "ecommerce.task-cockpit", displayName: "日常任务总控大屏", menuLabel: "日常任务总控大屏", route: "/workshop/cockpit" });
    const catalog = { listModules: vi.fn().mockResolvedValue(workshopCatalogFixture({ items: [taskModule] })) };
    vi.spyOn(ecommerceWorkshopClient, "getSourceReadiness").mockRejectedValue(new Error("source readiness outside host assertion"));
    vi.spyOn(ecommerceWorkshopClient, "getTaskCockpitCore").mockResolvedValue({ schemaVersion: "aos.ecommerce-workshop.task-cockpit/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: "2026-08-15T10:00:00Z", taskCutoff: "2026-08-15T10:00:00Z", stateConsistency: "current_state_per_page", readiness: "degraded", blockers: [
      { code: "TASK_COCKPIT_BUSINESS_CONTEXT_INDEPENDENT_SNAPSHOT", severity: "warning", dependency: "business-context:ecommerce.source-readiness", requiredAction: "按独立 cutoff 展示" },
    ], items: [], page: { limit: 20, count: 0, hasMore: false, nextCursor: null } });
    await act(async () => root.render(<MemoryRouter initialEntries={["/workshop/cockpit"]}><EcommerceWorkshopCatalogProvider client={catalog}><EcommerceWorkshopHost /></EcommerceWorkshopCatalogProvider></MemoryRouter>));
    expect(host.textContent).toContain("模块能力待核对"); expect(host.textContent).toContain("数据源就绪度读取失败"); expect(host.textContent).toContain("当前只读范围"); expect(host.textContent).toContain("当前权威 Task 集合为空"); expect(host.querySelectorAll("h1")).toHaveLength(1);
  });

  it("Operations authority 未验证时仍挂载只读分诊，并保留 Shell 阻断", async () => {
    const operationsModule = moduleWithReadiness("unknown"); Object.assign(operationsModule, { moduleId: "ecommerce.operations", displayName: "统一运营驾驶舱", menuLabel: "统一运营驾驶舱", route: "/workshop/operations" });
    const catalog = { listModules: vi.fn().mockResolvedValue(workshopCatalogFixture({ items: [operationsModule] })) };
    vi.spyOn(ecommerceWorkshopClient, "getSourceReadiness").mockRejectedValue(new Error("source readiness outside host assertion"));
    const ids = ["orders", "orderLines", "inventory", "shipments", "payments", "aftersaleEvents", "operationCases"] as const;
    vi.spyOn(ecommerceWorkshopClient, "getOperationsView").mockResolvedValue({ schemaVersion: "aos.ecommerce-workshop.operations-view/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: "2026-08-24T08:00:00Z", dataCutoff: "2026-08-24T08:00:00Z", readiness: "degraded", slices: ids.map((sliceId) => ({ sliceId, status: "ready", dataCutoff: "2026-08-24T08:00:00Z", authorityRefs: [{ resourceType: "ReadAuthority", resourceId: sliceId, revision: 1, contentHash: `sha256:${"a".repeat(64)}`, receiptId: "receipt-1" }], blockers: [], countLedger: { sourceTotal: 0, attached: 0, unmatched: 0, conflicted: 0 } })), page: { limit: 50, count: 0, hasMore: false, nextCursor: null } });
    const commandIds = ["classify", "createCase", "changeMembership", "manageSla", "automationKill", "refund"] as const;
    vi.spyOn(ecommerceWorkshopClient, "getOperationCommandReadiness").mockResolvedValue({ schemaVersion: "aos.ecommerce-workshop.operation-command-readiness/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: "2026-08-24T08:00:00Z", commands: commandIds.map((commandId, index) => ({ commandId, label: `命令${index}`, status: "blocked", risk: index > 3 ? "high" : "controlled", sideEffect: index === 5 ? "external" : "internalAuthority", blockers: [{ code: "OPERATION_COMMAND_HANDLER_NOT_BOUND", dependency: "W3-12B2", requiredAction: "完成 exact command gate" }] })) });
    await act(async () => root.render(<MemoryRouter initialEntries={["/workshop/operations"]}><EcommerceWorkshopCatalogProvider client={catalog}><EcommerceWorkshopHost /></EcommerceWorkshopCatalogProvider></MemoryRouter>));
    expect(host.querySelectorAll("h1")).toHaveLength(1);
    expect(host.textContent).toContain("统一运营驾驶舱");
    expect(host.textContent).toContain("模块能力待核对");
    expect(host.textContent).toContain("下方业务视图按自身当前 canonical GET 独立判定");
    expect(host.textContent).toContain("数据源就绪度读取失败");
    expect(host.textContent).toContain("统一待办 · 业务切片");
    expect(host.textContent).toContain("跨域只读分诊");
    expect(host.textContent).toContain("动作安全预检");
  });

  it("Content Campaign authority 未验证时仍挂载正式只读三栏且保留阻断", async () => {
    const contentModule = moduleWithReadiness("unknown"); Object.assign(contentModule, { moduleId: "ecommerce.content-campaign", displayName: "内容与活动工作台", menuLabel: "内容与活动工作台", route: "/workshop/content-campaign" });
    const catalog = { listModules: vi.fn().mockResolvedValue(workshopCatalogFixture({ items: [contentModule] })) };
    const cutoff = "2026-08-24T13:00:00Z";
    vi.spyOn(ecommerceWorkshopClient, "getContentCampaignView").mockResolvedValue({ schemaVersion: "aos.ecommerce-workshop.content-campaign-view/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: cutoff, dataCutoff: cutoff, readiness: "degraded", slices: (["plan", "calendar", "content"] as const).map((sliceId) => ({ sliceId, status: "blocked", dataCutoff: cutoff, authorityRefs: [], items: [], blockers: [{ code: `CANONICAL_${sliceId.toUpperCase()}_AUTHORITY_NOT_AVAILABLE`, dependency: `ecommerce.${sliceId}`, requiredAction: "接入 exact authority" }], countLedger: { eligible: 0, attached: 0, unmatched: 0, conflicted: 0 } })), page: { limit: 100, count: 0, hasMore: false, nextCursor: null } });
    await act(async () => root.render(<MemoryRouter initialEntries={["/workshop/content-campaign"]}><EcommerceWorkshopCatalogProvider client={catalog}><EcommerceWorkshopHost /></EcommerceWorkshopCatalogProvider></MemoryRouter>));
    expect(host.querySelectorAll("h1")).toHaveLength(1); expect(host.textContent).toContain("内容与活动工作台"); expect(host.textContent).toContain("模块能力待核对"); expect(host.textContent).toContain("数据源就绪度读取失败"); expect(host.querySelectorAll(".content-campaign-slice")).toHaveLength(3); expect(host.textContent).toContain("无写入口");
  });
});
