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
    vi.spyOn(ecommerceWorkshopClient, "getTaskCockpitCore").mockResolvedValue({ schemaVersion: "aos.ecommerce-workshop.task-cockpit/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: "2026-08-15T10:00:00Z", taskCutoff: "2026-08-15T10:00:00Z", stateConsistency: "current_state_per_page", readiness: "degraded", blockers: [
      { code: "TASK_COCKPIT_STAGE_MAPPING_UNAVAILABLE", severity: "warning", dependency: "stage", requiredAction: "等待映射" }, { code: "TASK_COCKPIT_RESPONSIBILITY_HANDOFF_UNAVAILABLE", severity: "warning", dependency: "responsibility", requiredAction: "等待 reader" }, { code: "TASK_COCKPIT_BUSINESS_CONTEXT_BLOCKED", severity: "blocking", dependency: "business", requiredAction: "等待 W2-00" },
    ], items: [], page: { limit: 20, count: 0, hasMore: false, nextCursor: null } });
    await act(async () => root.render(<MemoryRouter initialEntries={["/workshop/cockpit"]}><EcommerceWorkshopCatalogProvider client={catalog}><EcommerceWorkshopHost /></EcommerceWorkshopCatalogProvider></MemoryRouter>));
    expect(host.querySelectorAll("h1")).toHaveLength(1); expect(host.textContent).toContain("日常任务总控大屏"); expect(host.textContent).toContain("当前只读范围"); expect(host.textContent).toContain("当前权威 Task 集合为空");
  });

  it("Module authority 未验证时仍暴露只读视图，并同时保留 unknown 阻断", async () => {
    const taskModule = moduleWithReadiness("unknown"); Object.assign(taskModule, { moduleId: "ecommerce.task-cockpit", displayName: "日常任务总控大屏", menuLabel: "日常任务总控大屏", route: "/workshop/cockpit" });
    const catalog = { listModules: vi.fn().mockResolvedValue(workshopCatalogFixture({ items: [taskModule] })) };
    vi.spyOn(ecommerceWorkshopClient, "getTaskCockpitCore").mockResolvedValue({ schemaVersion: "aos.ecommerce-workshop.task-cockpit/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: "2026-08-15T10:00:00Z", taskCutoff: "2026-08-15T10:00:00Z", stateConsistency: "current_state_per_page", readiness: "degraded", blockers: [
      { code: "TASK_COCKPIT_BUSINESS_CONTEXT_BLOCKED", severity: "blocking", dependency: "business", requiredAction: "等待 W2-00" },
    ], items: [], page: { limit: 20, count: 0, hasMore: false, nextCursor: null } });
    await act(async () => root.render(<MemoryRouter initialEntries={["/workshop/cockpit"]}><EcommerceWorkshopCatalogProvider client={catalog}><EcommerceWorkshopHost /></EcommerceWorkshopCatalogProvider></MemoryRouter>));
    expect(host.textContent).toContain("就绪状态待验证"); expect(host.textContent).toContain("当前只读范围"); expect(host.textContent).toContain("当前权威 Task 集合为空"); expect(host.querySelectorAll("h1")).toHaveLength(1);
  });
});
