import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EcommerceWorkshopClientError, type TaskCockpitApprovalReviewResponse, type TaskCockpitCoreResponse, type TaskCockpitProductionContextResponse, type TaskCockpitResponsibilityHandoffResponse } from "../../api/ecommerceWorkshop";
import { TaskCockpitPage } from "./TaskCockpitPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const blockers = [
  { code: "TASK_COCKPIT_STAGE_MAPPING_RUN_SCOPED", severity: "warning" as const, dependency: "stage", requiredAction: "按 Run 展开" },
  { code: "TASK_COCKPIT_ASSIGNEE_OPERATIONAL_READINESS_UNAVAILABLE", severity: "warning" as const, dependency: "aip.assignee-operational-readiness", requiredAction: "等待 assignee operational readiness exact reader" },
  { code: "TASK_COCKPIT_BUSINESS_CONTEXT_BLOCKED", severity: "blocking" as const, dependency: "business", requiredAction: "等待 W2-00" },
];
const core = (title = "每日巡检"): TaskCockpitCoreResponse => ({ schemaVersion: "aos.ecommerce-workshop.task-cockpit/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: "2026-08-15T10:00:00Z", taskCutoff: "2026-08-15T10:00:00Z", stateConsistency: "current_state_per_page", readiness: "degraded", blockers, items: [{ taskId: `task-${title}`, taskType: "daily", title, status: "executing", priority: 50, version: 1, currentPlanRevisionId: "plan-1", createdAt: "2026-08-15T08:00:00Z", updatedAt: "2026-08-15T09:01:00Z", run: { runId: "run-1", planRevisionId: "plan-1", status: "running", version: 1, startedAt: null, finishedAt: null, createdAt: "2026-08-15T09:00:00Z", updatedAt: "2026-08-15T09:01:00Z" } }], page: { limit: 20, count: 1, hasMore: false, nextCursor: null } });
const detailBase = { schemaVersion: "aos.ecommerce-workshop.task-cockpit/v1" as const, tenant: { orgId: "org-org", projectId: "dev-project" }, runId: "run-1", evaluatedAt: "2026-08-15T10:00:00Z", membershipCutoff: "2026-08-15T10:00:00Z", stateConsistency: "current_state_per_page" as const, items: [], page: { limit: 20, count: 0, hasMore: false, nextCursor: null } };
const productionContext: TaskCockpitProductionContextResponse = { schemaVersion: "aos.ecommerce-workshop.task-cockpit/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, runId: "run-1", taskId: "task-1", evaluatedAt: "2026-08-15T10:00:00Z", planRef: { resourceType: "PlanRevision", resourceId: "plan-1", revision: 2, contentHash: "a".repeat(64) }, stageTemplateRef: { resourceType: "StageTemplateRevision", resourceId: "template-1", revision: 1, contentHash: "b".repeat(64) }, responsibilityPlanRef: { resourceType: "ResponsibilityPlanRevision", resourceId: "responsibility-1", revision: 1, contentHash: "c".repeat(64) }, compilerVersion: "w2c.v1", stages: [{ stageId: "collect", title: "采集", dependsOn: [], requiredSlotIds: ["collector"], applicabilityResult: "applicable", evaluatedProfile: "standard" }], applicableStageIds: ["collect"], notApplicableStageIds: [] };
const responsibilityHandoffs: TaskCockpitResponsibilityHandoffResponse = { schemaVersion: "aos.ecommerce-workshop.task-cockpit/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, runId: "run-1", taskId: "task-1", evaluatedAt: "2026-08-15T10:00:00Z", responsibilityPlanRef: { resourceType: "ResponsibilityPlanRevision", resourceId: "responsibility-1", revision: 1, contentHash: "c".repeat(64) }, profile: "standard", lifecycle: "frozen", compilationReadiness: "ready_at_compile", compiledRequiredSlotIds: ["collector"], slots: [{ slotId: "collector", responsibilityType: "collection", requiredCapabilityIds: ["ecommerce.collect"], returnStage: "collect", assignee: { kind: "agent_instance", resourceId: "agent-collector", version: 2, operationalReadiness: "unverified" } }], handoffs: [{ handoffId: "handoff-1", status: "consumed", version: 2, senderInstanceRef: { resourceType: "AgentInstance", resourceId: "agent-collector", revision: 2, contentHash: "d".repeat(64) }, receiverInstanceRef: { resourceType: "AgentInstance", resourceId: "agent-review", revision: 1, contentHash: "e".repeat(64) }, expiresAt: "2026-08-15T11:00:00Z", consumedAt: "2026-08-15T10:30:00Z", createdAt: "2026-08-15T10:00:00Z", decisions: [{ decisionId: "decision-1", revision: 1, decision: "accepted", reasonCode: null, gapCodes: [], contentHash: "f".repeat(64), createdAt: "2026-08-15T10:30:00Z" }] }] };
const approvalReview: TaskCockpitApprovalReviewResponse = { schemaVersion: "aos.ecommerce-workshop.task-cockpit/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, runId: "run-1", taskId: "task-1", evaluatedAt: "2026-08-15T10:00:00Z", planApproval: { planRef: productionContext.planRef, approvalStatus: "approved", approvedBy: "reviewer-1", approvedAt: "2026-08-15T08:50:00Z", navigation: { routeIdentity: "aip.task-plan", routePath: "/aip/studio?taskId=task-1&runId=run-1", targetRef: productionContext.planRef, commandReadiness: "read_only_fact", requiredPermission: "aip.plan.read", blockerCodes: ["NO_APPROVAL_COMMAND"], returnFocusToken: "a".repeat(64) } }, actionApprovals: [{ proposalRef: { resourceType: "ActionProposalRevision", resourceId: "proposal-1", revision: 1, contentHash: "d".repeat(64) }, actionTypeId: "ecommerce.case.classify", status: "approved", expiresAt: "2026-08-15T11:00:00Z", decisions: [{ approvalEventId: "approval-1", proposalVersion: 1, proposalHash: "d".repeat(64), decision: "approved", actorId: "reviewer-1", expiresAt: null, createdAt: "2026-08-15T09:10:00Z" }], navigation: { routeIdentity: "aip.action-drafts", routePath: "/aip/drafts?taskId=task-1&runId=run-1&proposalId=proposal-1", targetRef: { resourceType: "ActionProposalRevision", resourceId: "proposal-1", revision: 1, contentHash: "d".repeat(64) }, commandReadiness: "destination_reauthorization_required", requiredPermission: "aip.action.approval.decide", blockerCodes: ["DESTINATION_REAUTHORIZATION_REQUIRED"], returnFocusToken: "b".repeat(64) } }], reviewIssues: [{ issueId: "issue-1", version: 1, status: "open", severity: "warning", ruleRef: { resourceType: "EvalRuleRevision", resourceId: "rule-1", revision: 1, contentHash: "e".repeat(64) }, artifactId: "artifact-1", artifactHash: "f".repeat(64), evalReportRef: { resourceType: "EvalReportRevision", resourceId: "report-1", revision: 1, contentHash: "1".repeat(64) }, returnStage: "collect", evidenceCount: 0, lineageReadiness: "attempt_unresolved", returnLineage: null, events: [{ eventId: "issue-event-1", sequence: 1, eventType: "opened", issueVersion: 1, payloadHash: "2".repeat(64), actor: "reviewer-1", createdAt: "2026-08-15T09:20:00Z" }] }], actionApprovalCount: 1, reviewIssueCount: 1, unresolvedAttemptCount: 1 };
const unreadDetails = { listTaskCockpitRunSteps: vi.fn(), listTaskCockpitRunCheckpoints: vi.fn(), getTaskCockpitRunProductionContext: vi.fn(), getTaskCockpitRunResponsibilityHandoffs: vi.fn(), getTaskCockpitRunApprovalReview: vi.fn() };

describe("TaskCockpitPage", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); });

  it("只显示 canonical partial 范围、服务端 blocker 和 Task/Run，不制造命令或 H1", async () => {
    const client = { getTaskCockpitCore: vi.fn().mockResolvedValue(core()), ...unreadDetails };
    await act(async () => root.render(<TaskCockpitPage client={client} />));
    expect(host.querySelectorAll("h1")).toHaveLength(0);
    expect(host.textContent).toContain("当前任务权威指标"); expect(host.textContent).toContain("每日巡检"); expect(host.textContent).toContain("TASK_COCKPIT_STAGE_MAPPING_RUN_SCOPED");
    expect(host.textContent).not.toMatch(/派发|暂停任务|取消任务|批准任务/);
    expect(host.querySelector(".task-cockpit-command-blocked input")).toBeNull();
    expect([...host.querySelectorAll("button")].some((item) => item.textContent === "下达")).toBe(false);
    expect(client.getTaskCockpitCore).toHaveBeenCalledWith({ status: undefined, limit: 20, cursor: undefined });
  });

  it("按正式视觉层次呈现真实计数和明确阻断，不复制经营示例", async () => {
    const client = { getTaskCockpitCore: vi.fn().mockResolvedValue(core()), ...unreadDetails };
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
    const client = { getTaskCockpitCore: vi.fn().mockResolvedValue(core()), listTaskCockpitRunSteps: vi.fn().mockResolvedValue(detailBase), listTaskCockpitRunCheckpoints: vi.fn().mockResolvedValue(detailBase), getTaskCockpitRunProductionContext: vi.fn().mockResolvedValue(productionContext), getTaskCockpitRunResponsibilityHandoffs: vi.fn().mockResolvedValue(responsibilityHandoffs), getTaskCockpitRunApprovalReview: vi.fn().mockResolvedValue(approvalReview) };
    await act(async () => root.render(<TaskCockpitPage client={client} />));
    const button = [...host.querySelectorAll("button")].find((item) => item.textContent === "查看运行明细")!;
    await act(async () => button.click());
    expect(button.getAttribute("aria-expanded")).toBe("true");
    expect(host.textContent).toContain("当前权威 Step 集合为空"); expect(host.textContent).toContain("当前权威 Checkpoint 集合为空");
    expect(host.textContent).toContain("Stage 编排 · w2c.v1"); expect(host.textContent).toContain("采集collect适用");
    expect(host.textContent).toContain("职责与交接 · standard"); expect(host.textContent).toContain("运行就绪未验证"); expect(host.textContent).toContain("agent-collector → agent-review");
    expect(host.textContent).toContain("审批与复核"); expect(host.textContent).toContain("打开不等于批准；批准不等于应用"); expect(host.textContent).toContain("attempt 未解析；保持失败关闭");
    expect(client.listTaskCockpitRunSteps).toHaveBeenCalledWith("run-1", { limit: 20 });
  });

  it("409 保留已标记内容并要求重读，不自动重放或变空", async () => {
    const stale = new EcommerceWorkshopClientError("stale", { status: 409, body: { code: "TASK_COCKPIT_CURSOR_STALE", message: "stale", details: null, traceId: "trace" }, operationId: "ecommerceWorkshopTaskCockpitCoreGet" });
    const client = { getTaskCockpitCore: vi.fn().mockResolvedValueOnce(core()).mockRejectedValueOnce(stale), ...unreadDetails };
    await act(async () => root.render(<TaskCockpitPage client={client} />));
    const refresh = [...host.querySelectorAll("button")].find((item) => item.textContent === "重新读取")!;
    await act(async () => refresh.click());
    expect(host.textContent).toContain("游标或当前快照已变化"); expect(host.textContent).toContain("每日巡检"); expect(client.getTaskCockpitCore).toHaveBeenCalledTimes(2);
  });

  it("403 与明细失败分别失败关闭", async () => {
    const denied = new EcommerceWorkshopClientError("denied", { status: 403, body: { code: "FORBIDDEN", message: "denied", details: null, traceId: "trace" }, operationId: "ecommerceWorkshopTaskCockpitCoreGet" });
    const client = { getTaskCockpitCore: vi.fn().mockRejectedValue(denied), ...unreadDetails };
    await act(async () => root.render(<TaskCockpitPage client={client} />));
    expect(host.textContent).toContain("没有访问权限"); expect(host.textContent).not.toContain("暂无数据");
  });

  it("晚到的旧筛选响应不能覆盖新筛选结果", async () => {
    let resolveFirst!: (value: TaskCockpitCoreResponse) => void; let resolveSecond!: (value: TaskCockpitCoreResponse) => void;
    const first = new Promise<TaskCockpitCoreResponse>((resolve) => { resolveFirst = resolve; }); const second = new Promise<TaskCockpitCoreResponse>((resolve) => { resolveSecond = resolve; });
    const client = { getTaskCockpitCore: vi.fn().mockReturnValueOnce(first).mockReturnValueOnce(second), ...unreadDetails };
    await act(async () => { root.render(<TaskCockpitPage client={client} />); });
    const select = host.querySelector("select")!;
    await act(async () => { select.value = "completed"; select.dispatchEvent(new Event("change", { bubbles: true })); });
    await act(async () => { resolveSecond(core("新筛选")); await second; });
    await act(async () => { resolveFirst(core("晚到旧响应")); await first; });
    expect(host.textContent).toContain("新筛选"); expect(host.textContent).not.toContain("晚到旧响应");
    expect(client.getTaskCockpitCore).toHaveBeenLastCalledWith({ status: "completed", limit: 20, cursor: undefined });
  });

  it("明细任一读取失败都显示失败，不把另一集合冒充完整", async () => {
    const client = { getTaskCockpitCore: vi.fn().mockResolvedValue(core()), listTaskCockpitRunSteps: vi.fn().mockResolvedValue(detailBase), listTaskCockpitRunCheckpoints: vi.fn().mockRejectedValue(new Error("offline")), getTaskCockpitRunProductionContext: vi.fn().mockResolvedValue(productionContext), getTaskCockpitRunResponsibilityHandoffs: vi.fn().mockResolvedValue(responsibilityHandoffs), getTaskCockpitRunApprovalReview: vi.fn().mockResolvedValue(approvalReview) };
    await act(async () => root.render(<TaskCockpitPage client={client} />));
    const button = [...host.querySelectorAll("button")].find((item) => item.textContent === "查看运行明细")!;
    await act(async () => button.click());
    expect(host.textContent).toContain("运行明细读取失败"); expect(host.textContent).not.toContain("当前权威 Step 集合为空");
  });
});
