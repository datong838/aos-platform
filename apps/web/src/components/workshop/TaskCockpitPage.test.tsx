import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EcommerceWorkshopClientError, type DispatchControlObservation, type DispatchScenarioContribution, type ResponsibilityAssignmentObservation, type TaskCockpitActionReceiptResponse, type TaskCockpitApprovalReviewResponse, type TaskCockpitCoreResponse, type TaskCockpitProductionContextResponse, type TaskCockpitResponsibilityHandoffResponse, type TaskCockpitSkillContributionResponse } from "../../api/ecommerceWorkshop";
import type { BatchScenarioContribution } from "../../api/ecommerceWorkshop";
import { TaskCockpitPage } from "./TaskCockpitPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const blockers = [
  { code: "TASK_COCKPIT_STAGE_MAPPING_RUN_SCOPED", severity: "warning" as const, dependency: "stage", requiredAction: "按 Run 展开" },
  { code: "TASK_COCKPIT_BUSINESS_CONTEXT_INDEPENDENT_SNAPSHOT", severity: "warning" as const, dependency: "business-context:ecommerce.source-readiness", requiredAction: "按独立 cutoff 展示" },
];
const core = (title = "每日巡检"): TaskCockpitCoreResponse => ({ schemaVersion: "aos.ecommerce-workshop.task-cockpit/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: "2026-08-15T10:00:00Z", taskCutoff: "2026-08-15T10:00:00Z", stateConsistency: "current_state_per_page", readiness: "degraded", blockers, items: [{ taskId: `task-${title}`, taskType: "daily", title, status: "executing", priority: 50, version: 1, currentPlanRevisionId: "plan-1", createdAt: "2026-08-15T08:00:00Z", updatedAt: "2026-08-15T09:01:00Z", run: { runId: "run-1", planRevisionId: "plan-1", status: "running", version: 1, startedAt: null, finishedAt: null, createdAt: "2026-08-15T09:00:00Z", updatedAt: "2026-08-15T09:01:00Z" } }], page: { limit: 20, count: 1, hasMore: false, nextCursor: null } });
const detailBase = { schemaVersion: "aos.ecommerce-workshop.task-cockpit/v1" as const, tenant: { orgId: "org-org", projectId: "dev-project" }, runId: "run-1", evaluatedAt: "2026-08-15T10:00:00Z", membershipCutoff: "2026-08-15T10:00:00Z", stateConsistency: "current_state_per_page" as const, items: [], page: { limit: 20, count: 0, hasMore: false, nextCursor: null } };
const productionContext: TaskCockpitProductionContextResponse = { schemaVersion: "aos.ecommerce-workshop.task-cockpit/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, runId: "run-1", taskId: "task-1", evaluatedAt: "2026-08-15T10:00:00Z", planRef: { resourceType: "PlanRevision", resourceId: "plan-1", revision: 2, contentHash: "a".repeat(64) }, stageTemplateRef: { resourceType: "StageTemplateRevision", resourceId: "template-1", revision: 1, contentHash: "b".repeat(64) }, responsibilityPlanRef: { resourceType: "ResponsibilityPlanRevision", resourceId: "responsibility-1", revision: 1, contentHash: "c".repeat(64) }, compilerVersion: "w2c.v1", stages: [{ stageId: "collect", title: "采集", dependsOn: [], requiredSlotIds: ["collector"], applicabilityResult: "applicable", evaluatedProfile: "standard" }], applicableStageIds: ["collect"], notApplicableStageIds: [] };
const responsibilityHandoffs: TaskCockpitResponsibilityHandoffResponse = { schemaVersion: "aos.ecommerce-workshop.task-cockpit/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, runId: "run-1", taskId: "task-1", evaluatedAt: "2026-08-15T10:00:00Z", responsibilityPlanRef: { resourceType: "ResponsibilityPlanRevision", resourceId: "responsibility-1", revision: 1, contentHash: "c".repeat(64) }, profile: "standard", lifecycle: "frozen", compilationReadiness: "ready_at_compile", compiledRequiredSlotIds: ["collector"], slots: [{ slotId: "collector", responsibilityType: "collection", requiredCapabilityIds: ["ecommerce.collect"], returnStage: "collect", assignee: { kind: "agent_instance", resourceId: "agent-collector", version: 2, operationalReadiness: "resolved_at_observation", resolutionReceipts: [{ receiptId: "resolution-1", subjectId: "responsibility-plan:responsibility-1@1/slot:collector", kind: "agent_instance", resourceId: "agent-collector", version: 2, status: "resolved", blockerCodes: [], contentHash: "9".repeat(64), snapshotHash: "8".repeat(64), expiresAt: "2026-08-15T10:10:00Z", requiredCapabilityCount: 1, bindingCount: 2, snapshotStatus: "exact_fresh", createdAt: "2026-08-15T09:40:00Z" }] } }], handoffs: [{ handoffId: "handoff-1", status: "consumed", version: 2, senderInstanceRef: { resourceType: "AgentInstance", resourceId: "agent-collector", revision: 2, contentHash: "d".repeat(64) }, receiverInstanceRef: { resourceType: "AgentInstance", resourceId: "agent-review", revision: 1, contentHash: "e".repeat(64) }, expiresAt: "2026-08-15T11:00:00Z", consumedAt: "2026-08-15T10:30:00Z", createdAt: "2026-08-15T10:00:00Z", decisions: [{ decisionId: "decision-1", revision: 1, decision: "accepted", reasonCode: null, gapCodes: [], contentHash: "f".repeat(64), createdAt: "2026-08-15T10:30:00Z" }] }] };
const approvalReview: TaskCockpitApprovalReviewResponse = { schemaVersion: "aos.ecommerce-workshop.task-cockpit/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, runId: "run-1", taskId: "task-1", evaluatedAt: "2026-08-15T10:00:00Z", planApproval: { planRef: productionContext.planRef, approvalStatus: "approved", approvedBy: "reviewer-1", approvedAt: "2026-08-15T08:50:00Z", navigation: { routeIdentity: "aip.task-plan", routePath: "/aip/studio?taskId=task-1&runId=run-1", targetRef: productionContext.planRef, commandReadiness: "read_only_fact", requiredPermission: "aip.plan.read", blockerCodes: ["NO_APPROVAL_COMMAND"], returnFocusToken: "a".repeat(64) } }, actionApprovals: [{ proposalRef: { resourceType: "ActionProposalRevision", resourceId: "proposal-1", revision: 1, contentHash: "d".repeat(64) }, actionTypeId: "ecommerce.case.classify", status: "approved", expiresAt: "2026-08-15T11:00:00Z", decisions: [{ approvalEventId: "approval-1", proposalVersion: 1, proposalHash: "d".repeat(64), decision: "approved", actorId: "reviewer-1", expiresAt: null, createdAt: "2026-08-15T09:10:00Z" }], navigation: { routeIdentity: "aip.action-drafts", routePath: "/aip/drafts?taskId=task-1&runId=run-1&proposalId=proposal-1", targetRef: { resourceType: "ActionProposalRevision", resourceId: "proposal-1", revision: 1, contentHash: "d".repeat(64) }, commandReadiness: "destination_reauthorization_required", requiredPermission: "aip.action.approval.decide", blockerCodes: ["DESTINATION_REAUTHORIZATION_REQUIRED"], returnFocusToken: "b".repeat(64) } }], reviewIssues: [{ issueId: "issue-1", version: 1, status: "open", severity: "warning", ruleRef: { resourceType: "EvalRuleRevision", resourceId: "rule-1", revision: 1, contentHash: "e".repeat(64) }, artifactId: "artifact-1", artifactHash: "f".repeat(64), evalReportRef: { resourceType: "EvalReportRevision", resourceId: "report-1", revision: 1, contentHash: "1".repeat(64) }, returnStage: "collect", evidenceCount: 0, lineageReadiness: "attempt_unresolved", returnLineage: null, events: [{ eventId: "issue-event-1", sequence: 1, eventType: "opened", issueVersion: 1, payloadHash: "2".repeat(64), payload: null, payloadReadiness: "legacy_unavailable", actor: "reviewer-1", createdAt: "2026-08-15T09:20:00Z" }] }], actionApprovalCount: 1, reviewIssueCount: 1, unresolvedAttemptCount: 1 };
const actionReceipts: TaskCockpitActionReceiptResponse = { schemaVersion: "aos.ecommerce-workshop.task-cockpit/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, runId: "run-1", taskId: "task-1", evaluatedAt: "2026-08-15T10:00:00Z", executions: [{ proposalRef: { resourceType: "ActionProposalRevision", resourceId: "proposal-1", revision: 4, contentHash: "d".repeat(64) }, actionTypeId: "ecommerce.case.classify", proposalStatus: "unknown", leaseId: "lease-1", attempt: 1, reconciliationState: "required", receipts: [{ receiptId: "receipt-1", receiptKind: "initial", status: "unknown", leaseId: "lease-1", requestFingerprint: "e".repeat(64), providerRequestPresent: true, evidenceCount: 0, supersedesReceiptId: null, resolvedStatus: null, createdAt: "2026-08-15T09:30:00Z" }] }], proposalCount: 1, receiptCount: 1, unknownReceiptCount: 1, reconcileRequiredCount: 1, reconciledReceiptCount: 0 };
const skillContributions: TaskCockpitSkillContributionResponse = { schemaVersion: "aos.ecommerce-workshop.task-cockpit/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, runId: "run-1", taskId: "task-1", evaluatedAt: "2026-08-15T10:00:00Z", projectionStatus: "ready", blockerCodes: [], items: [{ contributionId: "agent-run-1", taskRunRef: { resourceType: "TaskRun", resourceId: "run-1", revision: null, authority: "aip-task-runtime" }, agentRunRef: { resourceType: "AgentRun", resourceId: "agent-run-1", revision: "2", authority: "aip-agent-run" }, moduleId: "ecommerce.task-cockpit", roleRef: { resourceType: "AgentTemplate", resourceId: "ecommerce.data_advisor", revision: 1, contentHash: "a".repeat(64) }, assigneeRef: { resourceType: "AgentInstance", resourceId: "agent-1", revision: 3, contentHash: "b".repeat(64) }, skillRevisionRef: { resourceType: "SkillTemplate", resourceId: "ecommerce.skill.D01", revision: 1, contentHash: "c".repeat(64) }, bindingRef: { resourceType: "SkillBinding", resourceId: "binding-1", revision: "4", authority: "aip-skill-registry" }, logicRevisionRef: { resourceType: "LogicRevision", resourceId: "ecommerce.logic.D01", revision: 2, contentHash: "d".repeat(64) }, displayName: "数据参谋 · 专业贡献", purpose: "完成受控专业步骤", responsibility: "data_advisor", readiness: { status: "available", freshness: "fresh", reasonCodes: [], bindingStatus: "active", lastVerifiedAt: "2026-08-15T09:58:00Z", expiresAt: "2026-08-15T10:10:00Z" }, runProjection: { status: "running", startedAt: null, updatedAt: "2026-08-15T09:59:00Z", waitingFor: [] }, inputRefs: [], outputArtifactRefs: [{ resourceType: "Artifact", resourceId: "artifact-1", revision: "1", authority: "aip-artifact" }], assumptions: [], uncertainties: [], conflicts: [], missingInputs: [], allowedCommands: [] }] };
const assignmentObservation: ResponsibilityAssignmentObservation = { tenant: { orgId: "org-org", projectId: "dev-project" }, runRef: { resourceType: "TaskRun", resourceId: "run-1", version: 1 }, takeoverRequests: [], takeoverDecisions: [], assignmentLeases: [], evaluatedAt: "2026-08-15T10:00:00Z" };
const dispatchObservation: DispatchControlObservation = { tenant: { orgId: "org-org", projectId: "dev-project" }, taskRef: { resourceType: "Task", resourceId: "task-每日巡检", version: 2 }, dispatchIntents: [{ tenant: { orgId: "org-org", projectId: "dev-project" }, intentId: "intent-1", revision: 1, taskRef: { resourceType: "Task", resourceId: "task-每日巡检", version: 1 }, taskRunRef: null, stepRunRef: null, responsibilityPlanRef: responsibilityHandoffs.responsibilityPlanRef, command: { commandKind: "responsibility_successor", routeIdentity: "aip.responsibility.successor", routePath: "/v1/aip/responsibility-assignments/successors", requiredPermission: "aip.responsibility.write" }, sourceIdentity: "agent-old", targetIdentity: "agent-new", sourceSlotId: "collector", targetSlotId: null, expectedFence: null, reasonCode: "OPERATOR_REASSIGNED", policyRef: { resourceType: "PolicyRevision", resourceId: "dispatch-policy-1", revision: 1, contentHash: "8".repeat(64) }, diff: {}, impact: {}, readiness: "ready", blockers: [], maker: "user:maker", createdAt: "2026-08-15T10:00:00Z", contentHash: "7".repeat(64) }], confirmations: [], priorityDecisions: [{ tenant: { orgId: "org-org", projectId: "dev-project" }, decisionId: "priority-1", revision: 1, taskRefBefore: { resourceType: "Task", resourceId: "task-每日巡检", version: 1 }, taskRefAfter: { resourceType: "Task", resourceId: "task-每日巡检", version: 2 }, oldPriority: 50, newPriority: 80, reasonCode: "SLA_ESCALATION", policyRef: { resourceType: "PolicyRevision", resourceId: "priority-policy-1", revision: 1, contentHash: "6".repeat(64) }, actor: "user:operator", createdAt: "2026-08-15T10:00:00Z", contentHash: "5".repeat(64) }], evaluatedAt: "2026-08-15T10:00:00Z" };
const scenarioRef = (resourceType: string, resourceId: string) => ({ resourceType, resourceId, revision: 1, contentHash: `sha256:${"a".repeat(64)}` });
const scenarioBlocker = { code: "PROVIDER_OUTCOME_UNKNOWN_RECONCILIATION_REQUIRED", dependency: "workshop.dispatch-scenario", requiredAction: "追加 exact reconcile evidence" };
const dispatchScenario: DispatchScenarioContribution = {
  schemaVersion: "aos.ecommerce-workshop.dispatch-scenario/v1", status: "blocked", rootTaskGraphRef: scenarioRef("TaskGraphRevision", "graph-1"), rootTaskRunRef: scenarioRef("TaskRun", "run-1"), dispatchBindingHash: "b".repeat(64), evaluatedAt: "2026-08-26T04:00:00Z",
  composition: { atomicSkillRefs: [scenarioRef("SkillRevision", "prepare-handoff"), scenarioRef("SkillRevision", "plan-responsibilities")], logicRevisionRef: scenarioRef("LogicRevision", "daily-control-dispatch"), roleBindings: [{ roleRef: scenarioRef("AgentTemplate", "operations-lead"), assigneeRef: scenarioRef("AgentInstance", "operations-lead-1"), skillBindingRef: scenarioRef("SkillBinding", "binding-1") }] },
  stages: (["task_graph", "dispatch_intent", "handoff", "receiver_decision", "request_more_or_return", "takeover", "owner_timeline"] as const).map((stageId) => ({ stageId, status: "ready", exactRefs: [scenarioRef("DecisionReceiptRevision", `${stageId}-1`)], contribution: `stage ${stageId}`, blockers: [] })),
  ledger: { tasksExpected: 1, tasksObserved: 1, handoffsExpected: 1, handoffsObserved: 1, decisionsExpected: 2, decisionsRecorded: 2, accepted: 1, rejected: 0, requestMore: 1, returned: 0, takeoverRequested: 1, takeoverDecided: 1, activeOwnerCount: 1 },
  outcomeAxes: (["dispatch_decision_recorded", "receiver_reauthorized", "single_active_owner", "takeover_decided", "execution_reconciled"] as const).map((axisId, index) => index === 4 ? { axisId, status: "unknown", exactRef: null, blocker: scenarioBlocker } : { axisId, status: "ready", exactRef: scenarioRef("DecisionReceiptRevision", axisId), blocker: null }),
  blockers: [scenarioBlocker], commands: { dispatch: false, decideHandoff: false, requestTakeover: false, approveTakeover: false, mutateOwner: false }, externalEffectsAllowed: false,
};
const batchBlocker = { code: "CHILD_OUTCOME_UNKNOWN_RECONCILIATION_REQUIRED", dependency: "workshop.batch-scenario", requiredAction: "同指纹权威回读" };
const batchScenario: BatchScenarioContribution = {
  schemaVersion: "aos.ecommerce-workshop.batch-scenario/v1", status: "blocked", batchPreparationRevisionRef: scenarioRef("BatchPreparationRevision", "prepare-1"), batchStartDecisionRef: scenarioRef("BatchStartDecision", "start-1"), batchStartBindingHash: "c".repeat(64), evaluatedAt: "2026-08-26T07:00:00Z",
  composition: { atomicSkillRefs: [scenarioRef("SkillRevision", "freeze-batch"), scenarioRef("SkillRevision", "reconcile-attempt")], logicRevisionRef: scenarioRef("LogicRevision", "batch-control-loop"), roleBindings: [{ roleRef: scenarioRef("AgentTemplate", "operations-lead"), assigneeRef: scenarioRef("AgentInstance", "operations-lead-1"), skillBindingRef: scenarioRef("SkillBinding", "batch-binding-1") }] },
  preparationDecisions: [{ itemKey: "item-1", disposition: "included", originalRefs: [scenarioRef("BusinessItemRevision", "item-1")], decisionRef: scenarioRef("ItemPreparationDecision", "decision-1"), reasonCodes: [] }, { itemKey: "item-2", disposition: "unknown", originalRefs: [scenarioRef("BusinessItemRevision", "item-2")], decisionRef: scenarioRef("ItemPreparationDecision", "decision-2"), reasonCodes: ["SOURCE_FACT_UNKNOWN"] }],
  childOutcomes: [{ itemKey: "item-1", status: "unknown", requestFingerprint: "d".repeat(64), attemptRef: scenarioRef("Attempt", "attempt-1"), authorityRefs: [scenarioRef("ProviderRequestReceipt", "request-1")], reconcileReceiptRefs: [], automaticRetryAllowed: false }],
  stages: (["prepare_root", "impact_cost_preview", "explicit_start", "child_dispatch", "partial_outcomes", "unknown_reconcile", "restart_rebuild"] as const).map((stageId, index) => index < 5 ? { stageId, status: "ready", exactRefs: [scenarioRef("StageReceipt", `stage-${index}`)], contribution: `stage ${stageId}`, blockers: [] } : { stageId, status: index === 5 ? "unknown" : "blocked", exactRefs: [], contribution: `wait ${stageId}`, blockers: [batchBlocker] }),
  ledger: { frozenTotal: 2, included: 1, excluded: 0, blocked: 0, preparationUnknown: 1, childrenExpected: 1, childrenObserved: 1, succeeded: 0, failed: 0, cancelled: 0, childUnknown: 1, reconciled: 0, reconcileReceiptsObserved: 0 },
  outcomeAxes: (["business_item", "external_action", "usage_settlement", "effect_maturity", "handoff_decision"] as const).map((axisId) => ({ axisId, status: "unknown", exactRefs: [], blockers: [batchBlocker] })),
  sideEffectLedger: { prepareExternalCalls: 0, providerCalls: 0, actionAttempts: 0, externalEffects: 0 }, blockers: [batchBlocker], commands: { prepare: false, start: false, cancel: false, reconcile: false }, automaticRetryAllowed: false, externalEffectsAllowed: false, releaseAllowed: false,
};
const unreadDetails = { listTaskCockpitRunSteps: vi.fn(), listTaskCockpitRunCheckpoints: vi.fn(), getTaskCockpitRunProductionContext: vi.fn(), getTaskCockpitRunResponsibilityHandoffs: vi.fn(), compileTaskCockpitRunHandoff: vi.fn(), getTaskCockpitRunApprovalReview: vi.fn(), getTaskCockpitRunActionReceipts: vi.fn(), getTaskCockpitRunSkillContributions: vi.fn() };

describe("TaskCockpitPage", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); });

  it("shows the W8-12 release decision as NO_GO without approval flag or release controls", async () => {
    const client = { getTaskCockpitCore: vi.fn().mockResolvedValue(core()), ...unreadDetails };
    await act(async () => root.render(<TaskCockpitPage client={client} />));
    expect(host.querySelector('[aria-label="运营就绪与发布决定"]')).not.toBeNull();
    expect(host.textContent).toContain("暂不发布"); expect(host.textContent).toContain("8 blocked"); expect(host.textContent).toContain("Approval");
    expect(host.textContent).toContain("批准候选、开启功能、开始灰度");
    expect([...host.querySelectorAll("button")].some((item) => /approve candidate|feature flag|rollout|rollback|release|发布/i.test(item.textContent ?? "") && !item.disabled)).toBe(false);
  });

  it("shows the W8-11 cumulative gate fail closed without migration or release controls", async () => {
    const client = { getTaskCockpitCore: vi.fn().mockResolvedValue(core()), ...unreadDetails };
    await act(async () => root.render(<TaskCockpitPage client={client} />));
    expect(host.querySelector('[aria-label="累计发布安全检查"]')).not.toBeNull();
    expect(host.textContent).toContain("等待发布证据"); expect(host.textContent).toContain("0 / 14"); expect(host.textContent).toContain("未知（不以 0 代替）");
    expect(host.textContent).toContain("运行测试、生成接口契约、应用数据变更");
    expect([...host.querySelectorAll("button")].some((item) => /migration|install bundle|release|迁移|安装|发布/i.test(item.textContent ?? "") && !item.disabled)).toBe(false);
  });

  it("shows the W8-10 DR contract fail closed without exposing data-operation controls", async () => {
    const client = { getTaskCockpitCore: vi.fn().mockResolvedValue(core()), ...unreadDetails };
    await act(async () => root.render(<TaskCockpitPage client={client} />));
    expect(host.querySelector('[aria-label="灾难恢复预检"]')).not.toBeNull();
    expect(host.textContent).toContain("Backup manifest"); expect(host.textContent).toContain("RLS negatives"); expect(host.textContent).toContain("未知（不以 0 代替）");
    expect(host.textContent).toContain("检查备份、恢复、重建数据视图");
    expect([...host.querySelectorAll("button")].some((item) => /restore|failover|failback|恢复|重建/i.test(item.textContent ?? "") && !item.disabled)).toBe(false);
  });

  it("shows the W8-09 operating contract fail closed without exposing control commands", async () => {
    const client = { getTaskCockpitCore: vi.fn().mockResolvedValue(core()), ...unreadDetails };
    await act(async () => root.render(<TaskCockpitPage client={client} />));
    expect(host.querySelector('[aria-label="运营就绪预检"]')).not.toBeNull();
    expect(host.textContent).toContain("待核对事项");
    expect(host.textContent).toContain("未知（不以 0 代替）");
    expect(host.textContent).toContain("全部禁用");
  });

  it("只显示正式任务范围、服务端待补条件和执行记录，视觉命令槽返回安全预检且不制造 H1", async () => {
    const client = { getTaskCockpitCore: vi.fn().mockResolvedValue(core()), ...unreadDetails };
    await act(async () => root.render(<TaskCockpitPage client={client} />));
    expect(host.querySelectorAll("h1")).toHaveLength(0);
    expect(host.textContent).toContain("当前任务权威指标"); expect(host.textContent).toContain("每日巡检"); expect(host.textContent).toContain("TASK_COCKPIT_STAGE_MAPPING_RUN_SCOPED");
    expect(host.textContent).toContain("业务上下文未装配");
    expect(host.textContent).not.toMatch(/派发|暂停任务|取消任务|批准任务/);
    expect(host.querySelector(".task-cockpit-command-blocked input")).toBeNull();
    expect(host.querySelector<HTMLInputElement>(".task-cockpit-visual-command input")?.disabled).toBe(false);
    const dispatch = [...host.querySelectorAll<HTMLButtonElement>("button")].find((item) => item.textContent === "下达");
    expect(dispatch?.disabled).toBe(false);
    act(() => dispatch?.click());
    expect(host.querySelector('[role="status"]')?.textContent).toContain("请先输入需要处理的业务任务");
    expect(client.getTaskCockpitCore).toHaveBeenCalledWith({ status: undefined, limit: 20, cursor: undefined });
  });

  it("按正式视觉层次呈现真实计数和明确阻断，不复制经营示例", async () => {
    const client = { getTaskCockpitCore: vi.fn().mockResolvedValue(core()), ...unreadDetails };
    await act(async () => root.render(<TaskCockpitPage client={client} />));
    expect(host.querySelectorAll(".task-cockpit-metrics > div")).toHaveLength(6);
    expect(host.querySelectorAll(".task-cockpit-visual-metrics > div")).toHaveLength(7);
    expect(host.querySelector<HTMLElement>('.task-cockpit-visual-progress[aria-label="执行进度未提供"] i')?.style.width).toBe("0%");
    expect(host.textContent).toContain("通用任务指令仍失败关闭");
    expect(host.textContent).toContain("执行组"); expect(host.textContent).toContain("策划组");
    expect(host.textContent).toContain("当日任务流 · 执行进度");
    expect(host.textContent).toContain("复盘 · 权威缺口");
    expect(host.textContent).toContain("共享能力 · 待接入");
    expect(host.textContent).toContain("当前页任务1"); expect(host.textContent).toContain("latest Run1");
    expect(host.textContent).not.toMatch(/今日 GMV|六数字同事在线|经验已入库|朋友圈3条内容/);
  });

  it("独立呈现 W8-03 四层贡献、七阶段与五轴，所有命令保持关闭", async () => {
    const client = { getTaskCockpitCore: vi.fn().mockResolvedValue(core()), getTaskCockpitDispatchScenario: vi.fn().mockResolvedValue(dispatchScenario), ...unreadDetails };
    await act(async () => root.render(<TaskCockpitPage client={client} />));
    expect(host.textContent).toContain("跨工作台派发、退回、补充与人工接管");
    expect(host.textContent).toContain("原子 Skill → Logic 编排 → 数字同事绑定 → 工作台贡献视图");
    expect(host.textContent).toContain("prepare-handoff@1");
    expect(host.textContent).toContain("daily-control-dispatch");
    expect(host.textContent).toContain("operations-lead → operations-lead-1");
    expect(host.querySelectorAll(".task-cockpit-dispatch-stages > li")).toHaveLength(7);
    expect(host.querySelectorAll(".task-cockpit-dispatch-axes > article")).toHaveLength(5);
    expect(host.textContent).toContain("1/1");
    expect(host.textContent).toContain("dispatch=false");
    expect(host.textContent).toContain("mutate_owner=false");
    expect(client.getTaskCockpitDispatchScenario).toHaveBeenCalledTimes(1);
    expect([...host.querySelectorAll("button")].some((item) => /派发|接管|owner/i.test(item.textContent ?? "") && !item.disabled)).toBe(false);
  });

  it("W8-03 独立读取失败不拖垮原有 Task Cockpit", async () => {
    const client = { getTaskCockpitCore: vi.fn().mockResolvedValue(core()), getTaskCockpitDispatchScenario: vi.fn().mockRejectedValue(new Error("offline")), ...unreadDetails };
    await act(async () => root.render(<TaskCockpitPage client={client} />));
    expect(host.textContent).toContain("跨工作台任务派发状态读取失败");
    expect(host.textContent).toContain("每日巡检");
    expect(host.textContent).toContain("当日任务流 · 执行进度");
    expect(host.textContent).toContain("派发、决定、接管与负责人变更均不开放");
  });

  it("独立呈现 W8-06 四层批量贡献、七阶段与五结果轴且零命令", async () => {
    const client = { getTaskCockpitCore: vi.fn().mockResolvedValue(core()), getTaskCockpitBatchScenario: vi.fn().mockResolvedValue(batchScenario), ...unreadDetails };
    await act(async () => root.render(<TaskCockpitPage client={client} />));
    expect(host.textContent).toContain("批量准备、显式启动与结果协调");
    expect(host.textContent).toContain("freeze-batch@1"); expect(host.textContent).toContain("batch-control-loop"); expect(host.textContent).toContain("operations-lead → operations-lead-1");
    expect(host.querySelectorAll(".task-cockpit-batch-stages > li")).toHaveLength(7);
    expect(host.querySelectorAll(".task-cockpit-batch-axes > article")).toHaveLength(5);
    expect(host.querySelectorAll(".task-cockpit-batch-items li")).toHaveLength(2);
    expect(host.textContent).toContain("SOURCE_FACT_UNKNOWN"); expect(host.textContent).toContain("automatic_retry=false");
    expect(client.getTaskCockpitBatchScenario).toHaveBeenCalledTimes(1);
    expect([...host.querySelectorAll("button")].some((item) => /准备|启动|协调/.test(item.textContent ?? "") && !item.disabled)).toBe(false);
  });

  it("显式展开 Run 后诚实显示 Step/Checkpoint 空权威集合", async () => {
    const client = { getTaskCockpitCore: vi.fn().mockResolvedValue(core()), listTaskCockpitRunSteps: vi.fn().mockResolvedValue(detailBase), listTaskCockpitRunCheckpoints: vi.fn().mockResolvedValue(detailBase), getTaskCockpitRunProductionContext: vi.fn().mockResolvedValue(productionContext), getTaskCockpitRunResponsibilityHandoffs: vi.fn().mockResolvedValue(responsibilityHandoffs), compileTaskCockpitRunHandoff: vi.fn(), getTaskCockpitRunApprovalReview: vi.fn().mockResolvedValue(approvalReview), getTaskCockpitRunActionReceipts: vi.fn().mockResolvedValue(actionReceipts), getTaskCockpitRunSkillContributions: vi.fn().mockResolvedValue(skillContributions), getResponsibilityAssignmentObservation: vi.fn().mockResolvedValue(assignmentObservation), getDispatchControlObservation: vi.fn().mockResolvedValue(dispatchObservation) };
    await act(async () => root.render(<TaskCockpitPage client={client} />));
    const button = [...host.querySelectorAll("button")].find((item) => item.textContent === "查看运行明细")!;
    await act(async () => button.click());
    expect(button.getAttribute("aria-expanded")).toBe("true");
    expect(host.textContent).toContain("当前权威 Step 集合为空"); expect(host.textContent).toContain("当前权威 Checkpoint 集合为空");
    expect(host.textContent).toContain("Stage 编排 · w2c.v1"); expect(host.textContent).toContain("采集collect适用");
    expect(host.textContent).toContain("职责与交接 · standard"); expect(host.textContent).toContain("观测时已解析"); expect(host.textContent).toContain("只认带 snapshot hash"); expect(host.textContent).toContain("exact_fresh"); expect(host.textContent).toContain("agent-collector → agent-review");
    expect(host.textContent).toContain("审批与复核"); expect(host.textContent).toContain("打开不等于批准；批准不等于应用"); expect(host.textContent).toContain("attempt 未解析；保持失败关闭");
    expect(host.textContent).toContain("Action 回执与对账"); expect(host.textContent).toContain("unknown：仅允许授权 provider 回读对账"); expect(host.textContent).toContain("禁止重复执行");
    expect(host.textContent).not.toContain("provider-secret");
    expect(host.textContent).toContain("专业 Skill 贡献 · 只读"); expect(host.textContent).toContain("数据参谋 · 专业贡献"); expect(host.textContent).toContain("允许命令 0");
    expect(host.textContent).toContain("职责控制四轴"); expect(host.textContent).toContain("启动前改派"); expect(host.textContent).toContain("0 个请求 · 0 个决定 · 0 个当前 Lease"); expect(host.textContent).toContain("TASK_RUN_EXISTS_USE_TAKEOVER");
    expect([...host.querySelectorAll("button")].filter((item) => ["生成改派后继", "申请人工接管"].includes(item.textContent ?? "")).every((item) => item.disabled)).toBe(true);
    expect(client.listTaskCockpitRunSteps).toHaveBeenCalledWith("run-1", { limit: 20 });
    expect(client.getTaskCockpitRunSkillContributions).toHaveBeenCalledWith("run-1");
    expect(client.getResponsibilityAssignmentObservation).toHaveBeenCalledWith("run-1");
    expect(client.getDispatchControlObservation).toHaveBeenCalledWith("task-每日巡检");
    expect(host.textContent).toContain("派发、优先级与审批导航 · canonical 只读"); expect(host.textContent).toContain("50 → 80"); expect(host.textContent).toContain("agent-old → agent-new");
    expect([...host.querySelectorAll("button")].filter((item) => ["新建派发建议", "调整业务优先级"].includes(item.textContent ?? "")).every((item) => item.disabled)).toBe(true);
  });

  it("模块交接先编译零副作用，未确认前不签发", async () => {
    const reviewer = { ...responsibilityHandoffs.slots[0], slotId: "reviewer", responsibilityType: "review", assignee: { ...responsibilityHandoffs.slots[0].assignee, resourceId: "agent-review", version: 1, resolutionReceipts: [{ ...responsibilityHandoffs.slots[0].assignee.resolutionReceipts[0], receiptId: "resolution-2", subjectId: "responsibility-plan:responsibility-1@1/slot:reviewer", resourceId: "agent-review", version: 1 }] } };
    const responsibility = { ...responsibilityHandoffs, compiledRequiredSlotIds: ["collector", "reviewer"], slots: [...responsibilityHandoffs.slots, reviewer] };
    const issueCommand = { handoffId: "handoff-new", envelope: { taskRef: { resourceType: "Task", resourceId: "task-每日巡检", revision: "1", authority: "postgresql" }, runRef: { resourceType: "TaskRun", resourceId: "run-1", revision: "1", authority: "postgresql" }, senderInstance: { assetType: "AgentInstance", assetId: "agent-collector", revision: 2, contentHash: "a".repeat(64) }, receiverInstance: { assetType: "AgentInstance", assetId: "agent-review", revision: 1, contentHash: "b".repeat(64) }, objectRefs: [], artifactRefs: [], evidenceRefs: [], context: { sourceModuleId: "ecommerce.content-campaign", targetModuleId: "ecommerce.media-studio", sourceSlotId: "collector", targetSlotId: "reviewer", purpose: "跨模块受控协作", requestedOutcome: "返回可审计的业务决定" }, allowedContextFields: ["sourceModuleId", "targetModuleId", "sourceSlotId", "targetSlotId", "purpose", "requestedOutcome"], markings: ["public"], expiresAt: "2026-08-25T01:15:00Z" } };
    const compileTaskCockpitRunHandoff = vi.fn().mockResolvedValue({ schemaVersion: "aos.ecommerce-workshop.module-handoff-compile/v1", tenant: responsibility.tenant, runId: "run-1", taskId: "task-每日巡检", evaluatedAt: "2026-08-25T01:00:00Z", responsibilityPlanRef: responsibility.responsibilityPlanRef, sourceModuleId: "ecommerce.content-campaign", targetModuleId: "ecommerce.media-studio", sourceSlotId: "collector", targetSlotId: "reviewer", readiness: "ready", blockers: [], issueCommand, sideEffects: { handoffsIssued: 0, tokensMinted: 0, decisionsCreated: 0, agentRunsStarted: 0 } });
    const client = { getTaskCockpitCore: vi.fn().mockResolvedValue(core()), listTaskCockpitRunSteps: vi.fn().mockResolvedValue(detailBase), listTaskCockpitRunCheckpoints: vi.fn().mockResolvedValue(detailBase), getTaskCockpitRunProductionContext: vi.fn().mockResolvedValue(productionContext), getTaskCockpitRunResponsibilityHandoffs: vi.fn().mockResolvedValue(responsibility), compileTaskCockpitRunHandoff, getTaskCockpitRunApprovalReview: vi.fn().mockResolvedValue(approvalReview), getTaskCockpitRunActionReceipts: vi.fn().mockResolvedValue(actionReceipts), getTaskCockpitRunSkillContributions: vi.fn().mockResolvedValue(skillContributions) };
    const handoffClient = { issueHandoff: vi.fn(), consumeHandoff: vi.fn(), listHandoffDecisions: vi.fn(), createHandoffDecision: vi.fn() };
    await act(async () => root.render(<TaskCockpitPage client={client} handoffClient={handoffClient} />));
    await act(async () => [...host.querySelectorAll("button")].find((item) => item.textContent === "查看运行明细")!.click());
    expect(host.textContent).toContain("模块交接 · 显式受控命令");
    await act(async () => [...host.querySelectorAll("button")].find((item) => item.textContent === "编译交接")!.click());
    expect(compileTaskCockpitRunHandoff).toHaveBeenCalledWith("run-1", expect.objectContaining({ sourceSlotId: "collector", targetSlotId: "reviewer", taskRef: expect.objectContaining({ revision: "1" }), runRef: expect.objectContaining({ revision: "1" }) }));
    expect(host.textContent).toContain("编译完成：零副作用");
    expect(host.textContent).toContain("确认签发");
    expect(handoffClient.issueHandoff).not.toHaveBeenCalled();
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
    const client = { getTaskCockpitCore: vi.fn().mockResolvedValue(core()), listTaskCockpitRunSteps: vi.fn().mockResolvedValue(detailBase), listTaskCockpitRunCheckpoints: vi.fn().mockRejectedValue(new Error("offline")), getTaskCockpitRunProductionContext: vi.fn().mockResolvedValue(productionContext), getTaskCockpitRunResponsibilityHandoffs: vi.fn().mockResolvedValue(responsibilityHandoffs), compileTaskCockpitRunHandoff: vi.fn(), getTaskCockpitRunApprovalReview: vi.fn().mockResolvedValue(approvalReview), getTaskCockpitRunActionReceipts: vi.fn().mockResolvedValue(actionReceipts), getTaskCockpitRunSkillContributions: vi.fn().mockResolvedValue(skillContributions) };
    await act(async () => root.render(<TaskCockpitPage client={client} />));
    const button = [...host.querySelectorAll("button")].find((item) => item.textContent === "查看运行明细")!;
    await act(async () => button.click());
    expect(host.textContent).toContain("运行明细读取失败"); expect(host.textContent).not.toContain("当前权威 Step 集合为空");
  });

  it("专业 Skill 贡献接口失败不拖垮原有六类运行明细", async () => {
    const client = { getTaskCockpitCore: vi.fn().mockResolvedValue(core()), listTaskCockpitRunSteps: vi.fn().mockResolvedValue(detailBase), listTaskCockpitRunCheckpoints: vi.fn().mockResolvedValue(detailBase), getTaskCockpitRunProductionContext: vi.fn().mockResolvedValue(productionContext), getTaskCockpitRunResponsibilityHandoffs: vi.fn().mockResolvedValue(responsibilityHandoffs), compileTaskCockpitRunHandoff: vi.fn(), getTaskCockpitRunApprovalReview: vi.fn().mockResolvedValue(approvalReview), getTaskCockpitRunActionReceipts: vi.fn().mockResolvedValue(actionReceipts), getTaskCockpitRunSkillContributions: vi.fn().mockRejectedValue(new Error("offline")) };
    await act(async () => root.render(<TaskCockpitPage client={client} />));
    const button = [...host.querySelectorAll("button")].find((item) => item.textContent === "查看运行明细")!;
    await act(async () => button.click());
    expect(host.textContent).toContain("专业 Skill 贡献读取失败");
    expect(host.textContent).toContain("Stage 编排 · w2c.v1");
    expect(host.textContent).toContain("当前权威 Step 集合为空");
    expect(host.textContent).not.toContain("运行明细读取失败");
  });
});
