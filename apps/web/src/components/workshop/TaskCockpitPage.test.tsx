import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EcommerceWorkshopClientError, type TaskCockpitCoreResponse } from "../../api/ecommerceWorkshop";
import { TaskCockpitPage } from "./TaskCockpitPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const blockers = [
  { code: "TASK_COCKPIT_STAGE_MAPPING_UNAVAILABLE", severity: "warning" as const, dependency: "stage", requiredAction: "等待映射" },
  { code: "TASK_COCKPIT_RESPONSIBILITY_HANDOFF_UNAVAILABLE", severity: "warning" as const, dependency: "responsibility", requiredAction: "等待 reader" },
  { code: "TASK_COCKPIT_BUSINESS_CONTEXT_BLOCKED", severity: "blocking" as const, dependency: "business", requiredAction: "等待 W2-00" },
];
const core = (title = "每日巡检"): TaskCockpitCoreResponse => ({ schemaVersion: "aos.ecommerce-workshop.task-cockpit/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: "2026-08-15T10:00:00Z", taskCutoff: "2026-08-15T10:00:00Z", stateConsistency: "current_state_per_page", readiness: "degraded", blockers, items: [{ taskId: `task-${title}`, taskType: "daily", title, status: "executing", priority: 50, version: 1, currentPlanRevisionId: "plan-1", createdAt: "2026-08-15T08:00:00Z", updatedAt: "2026-08-15T09:01:00Z", run: { runId: "run-1", planRevisionId: "plan-1", status: "running", version: 1, startedAt: null, finishedAt: null, createdAt: "2026-08-15T09:00:00Z", updatedAt: "2026-08-15T09:01:00Z" } }], page: { limit: 20, count: 1, hasMore: false, nextCursor: null } });
const detailBase = { schemaVersion: "aos.ecommerce-workshop.task-cockpit/v1" as const, tenant: { orgId: "org-org", projectId: "dev-project" }, runId: "run-1", evaluatedAt: "2026-08-15T10:00:00Z", membershipCutoff: "2026-08-15T10:00:00Z", stateConsistency: "current_state_per_page" as const, items: [], page: { limit: 20, count: 0, hasMore: false, nextCursor: null } };

describe("TaskCockpitPage", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); });

  it("只显示 canonical partial 范围、服务端 blocker 和 Task/Run，不制造命令或 H1", async () => {
    const client = { getTaskCockpitCore: vi.fn().mockResolvedValue(core()), listTaskCockpitRunSteps: vi.fn(), listTaskCockpitRunCheckpoints: vi.fn() };
    await act(async () => root.render(<TaskCockpitPage client={client} />));
    expect(host.querySelectorAll("h1")).toHaveLength(0);
    expect(host.textContent).toContain("当前任务权威指标"); expect(host.textContent).toContain("每日巡检"); expect(host.textContent).toContain("TASK_COCKPIT_STAGE_MAPPING_UNAVAILABLE");
    expect(host.textContent).not.toMatch(/派发|暂停任务|取消任务|批准任务/);
    expect(host.querySelector(".task-cockpit-command-blocked input")).toBeNull();
    expect([...host.querySelectorAll("button")].some((item) => item.textContent === "下达")).toBe(false);
    expect(client.getTaskCockpitCore).toHaveBeenCalledWith({ status: undefined, limit: 20, cursor: undefined });
  });

  it("按正式视觉层次呈现真实计数和明确阻断，不复制经营示例", async () => {
    const client = { getTaskCockpitCore: vi.fn().mockResolvedValue(core()), listTaskCockpitRunSteps: vi.fn(), listTaskCockpitRunCheckpoints: vi.fn() };
    await act(async () => root.render(<TaskCockpitPage client={client} />));
    expect(host.querySelectorAll(".task-cockpit-metrics > div")).toHaveLength(6);
    expect(host.textContent).toContain("任务指令尚未开放");
    expect(host.textContent).toContain("执行组"); expect(host.textContent).toContain("策划组");
    expect(host.textContent).toContain("当日任务流 · 执行进度");
    expect(host.textContent).toContain("复盘 · 权威缺口");
    expect(host.textContent).toContain("共享能力 · 待接入");
    expect(host.textContent).toContain("当前页任务1"); expect(host.textContent).toContain("latest Run1");
    expect(host.textContent).not.toMatch(/今日 GMV|六数字同事在线|经验已入库|朋友圈3条内容/);
  });

  it("显式展开 Run 后诚实显示 Step/Checkpoint 空权威集合", async () => {
    const client = { getTaskCockpitCore: vi.fn().mockResolvedValue(core()), listTaskCockpitRunSteps: vi.fn().mockResolvedValue(detailBase), listTaskCockpitRunCheckpoints: vi.fn().mockResolvedValue(detailBase) };
    await act(async () => root.render(<TaskCockpitPage client={client} />));
    const button = [...host.querySelectorAll("button")].find((item) => item.textContent === "查看运行明细")!;
    await act(async () => button.click());
    expect(button.getAttribute("aria-expanded")).toBe("true");
    expect(host.textContent).toContain("当前权威 Step 集合为空"); expect(host.textContent).toContain("当前权威 Checkpoint 集合为空");
    expect(client.listTaskCockpitRunSteps).toHaveBeenCalledWith("run-1", { limit: 20 });
  });

  it("409 保留已标记内容并要求重读，不自动重放或变空", async () => {
    const stale = new EcommerceWorkshopClientError("stale", { status: 409, body: { code: "TASK_COCKPIT_CURSOR_STALE", message: "stale", details: null, traceId: "trace" }, operationId: "ecommerceWorkshopTaskCockpitCoreGet" });
    const client = { getTaskCockpitCore: vi.fn().mockResolvedValueOnce(core()).mockRejectedValueOnce(stale), listTaskCockpitRunSteps: vi.fn(), listTaskCockpitRunCheckpoints: vi.fn() };
    await act(async () => root.render(<TaskCockpitPage client={client} />));
    const refresh = [...host.querySelectorAll("button")].find((item) => item.textContent === "重新读取")!;
    await act(async () => refresh.click());
    expect(host.textContent).toContain("游标或当前快照已变化"); expect(host.textContent).toContain("每日巡检"); expect(client.getTaskCockpitCore).toHaveBeenCalledTimes(2);
  });

  it("403 与明细失败分别失败关闭", async () => {
    const denied = new EcommerceWorkshopClientError("denied", { status: 403, body: { code: "FORBIDDEN", message: "denied", details: null, traceId: "trace" }, operationId: "ecommerceWorkshopTaskCockpitCoreGet" });
    const client = { getTaskCockpitCore: vi.fn().mockRejectedValue(denied), listTaskCockpitRunSteps: vi.fn(), listTaskCockpitRunCheckpoints: vi.fn() };
    await act(async () => root.render(<TaskCockpitPage client={client} />));
    expect(host.textContent).toContain("没有访问权限"); expect(host.textContent).not.toContain("暂无数据");
  });

  it("晚到的旧筛选响应不能覆盖新筛选结果", async () => {
    let resolveFirst!: (value: TaskCockpitCoreResponse) => void; let resolveSecond!: (value: TaskCockpitCoreResponse) => void;
    const first = new Promise<TaskCockpitCoreResponse>((resolve) => { resolveFirst = resolve; }); const second = new Promise<TaskCockpitCoreResponse>((resolve) => { resolveSecond = resolve; });
    const client = { getTaskCockpitCore: vi.fn().mockReturnValueOnce(first).mockReturnValueOnce(second), listTaskCockpitRunSteps: vi.fn(), listTaskCockpitRunCheckpoints: vi.fn() };
    await act(async () => { root.render(<TaskCockpitPage client={client} />); });
    const select = host.querySelector("select")!;
    await act(async () => { select.value = "completed"; select.dispatchEvent(new Event("change", { bubbles: true })); });
    await act(async () => { resolveSecond(core("新筛选")); await second; });
    await act(async () => { resolveFirst(core("晚到旧响应")); await first; });
    expect(host.textContent).toContain("新筛选"); expect(host.textContent).not.toContain("晚到旧响应");
    expect(client.getTaskCockpitCore).toHaveBeenLastCalledWith({ status: "completed", limit: 20, cursor: undefined });
  });

  it("明细任一读取失败都显示失败，不把另一集合冒充完整", async () => {
    const client = { getTaskCockpitCore: vi.fn().mockResolvedValue(core()), listTaskCockpitRunSteps: vi.fn().mockResolvedValue(detailBase), listTaskCockpitRunCheckpoints: vi.fn().mockRejectedValue(new Error("offline")) };
    await act(async () => root.render(<TaskCockpitPage client={client} />));
    const button = [...host.querySelectorAll("button")].find((item) => item.textContent === "查看运行明细")!;
    await act(async () => button.click());
    expect(host.textContent).toContain("运行明细读取失败"); expect(host.textContent).not.toContain("当前权威 Step 集合为空");
  });
});
