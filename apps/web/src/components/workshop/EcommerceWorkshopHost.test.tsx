import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ecommerceWorkshopClient } from "../../api/ecommerceWorkshop";
import { setTenant } from "../../api/tenant";
import { EcommerceWorkshopCatalogProvider } from "./EcommerceWorkshopCatalogContext";
import { EcommerceWorkshopHost } from "./EcommerceWorkshopHost";
import { moduleWithReadiness, workshopCatalogFixture } from "./workshopTestFixtures";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

describe("EcommerceWorkshopHost task cockpit", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { sessionStorage.clear(); setTenant({ orgId: "org-org", projectId: "dev-project", workspaceName: "real" }); host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { vi.restoreAllMocks(); act(() => root.unmount()); host.remove(); });

  it("只在 canonical task-cockpit Module 中挂载 partial read page，并保持 Shell 唯一 H1", async () => {
    const taskModule = moduleWithReadiness("degraded"); Object.assign(taskModule, { moduleId: "ecommerce.task-cockpit", displayName: "日常任务总控大屏", menuLabel: "日常任务总控大屏", route: "/workshop/cockpit" });
    const catalog = { listModules: vi.fn().mockResolvedValue(workshopCatalogFixture({ items: [taskModule] })) };
    vi.spyOn(ecommerceWorkshopClient, "getSourceReadiness").mockRejectedValue(new Error("source readiness outside host assertion"));
    vi.spyOn(ecommerceWorkshopClient, "getTaskCockpitCore").mockResolvedValue({ schemaVersion: "aos.ecommerce-workshop.task-cockpit/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: "2026-08-15T10:00:00Z", taskCutoff: "2026-08-15T10:00:00Z", stateConsistency: "current_state_per_page", readiness: "degraded", blockers: [
      { code: "TASK_COCKPIT_STAGE_MAPPING_RUN_SCOPED", severity: "warning", dependency: "stage", requiredAction: "按 Run 展开" }, { code: "TASK_COCKPIT_RESPONSIBILITY_HANDOFF_UNAVAILABLE", severity: "warning", dependency: "responsibility", requiredAction: "等待 reader" }, { code: "TASK_COCKPIT_BUSINESS_CONTEXT_BLOCKED", severity: "blocking", dependency: "business", requiredAction: "等待 W2-00" },
    ], items: [], page: { limit: 20, count: 0, hasMore: false, nextCursor: null } });
    await act(async () => root.render(<MemoryRouter initialEntries={["/workshop/cockpit"]}><EcommerceWorkshopCatalogProvider client={catalog}><EcommerceWorkshopHost /></EcommerceWorkshopCatalogProvider></MemoryRouter>));
    expect(host.querySelectorAll("h1")).toHaveLength(1); expect(host.textContent).toContain("日常任务总控大屏"); expect(host.textContent).toContain("数据源就绪度"); expect(host.textContent).toContain("当前只读范围"); expect(host.textContent).toContain("当前权威 Task 集合为空");
  });

  it("Module authority 未验证时仍暴露只读视图，并同时保留 unknown 阻断", async () => {
    const taskModule = moduleWithReadiness("unknown"); Object.assign(taskModule, { moduleId: "ecommerce.task-cockpit", displayName: "日常任务总控大屏", menuLabel: "日常任务总控大屏", route: "/workshop/cockpit" });
    const catalog = { listModules: vi.fn().mockResolvedValue(workshopCatalogFixture({ items: [taskModule] })) };
    vi.spyOn(ecommerceWorkshopClient, "getSourceReadiness").mockRejectedValue(new Error("source readiness outside host assertion"));
    vi.spyOn(ecommerceWorkshopClient, "getTaskCockpitCore").mockResolvedValue({ schemaVersion: "aos.ecommerce-workshop.task-cockpit/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: "2026-08-15T10:00:00Z", taskCutoff: "2026-08-15T10:00:00Z", stateConsistency: "current_state_per_page", readiness: "degraded", blockers: [
      { code: "TASK_COCKPIT_BUSINESS_CONTEXT_BLOCKED", severity: "blocking", dependency: "business", requiredAction: "等待 W2-00" },
    ], items: [], page: { limit: 20, count: 0, hasMore: false, nextCursor: null } });
    await act(async () => root.render(<MemoryRouter initialEntries={["/workshop/cockpit"]}><EcommerceWorkshopCatalogProvider client={catalog}><EcommerceWorkshopHost /></EcommerceWorkshopCatalogProvider></MemoryRouter>));
    expect(host.textContent).toContain("就绪状态待验证"); expect(host.textContent).toContain("当前只读范围"); expect(host.textContent).toContain("当前权威 Task 集合为空"); expect(host.querySelectorAll("h1")).toHaveLength(1);
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
    expect(host.textContent).toContain("就绪状态待验证");
    expect(host.textContent).toContain("统一待办 · 权威切片");
    expect(host.textContent).toContain("只读分诊");
    expect(host.textContent).toContain("动作建议 · 失败关闭");
  });
});
