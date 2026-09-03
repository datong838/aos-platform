import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";

import {
  EcommerceWorkshopClientError,
  ecommerceWorkshopClient,
  type AnalystViewResponse,
  type DispatchControlObservation,
  type DispatchScenarioContribution,
  type BatchScenarioContribution,
  type TaskCockpitActionReceiptResponse,
  type TaskCockpitApprovalReviewResponse,
  type TaskCockpitCheckpointPageResponse,
  type TaskCockpitCoreResponse,
  type TaskCockpitProductionContextResponse,
  type TaskCockpitResponsibilityHandoffResponse,
  type ResponsibilityAssignmentObservation,
  type TaskCockpitSkillContributionResponse,
  type TaskCockpitStepPageResponse,
  type TaskCockpitTaskStatus,
} from "../../api/ecommerceWorkshop";
import { AsyncStateBoundary, type AsyncState } from "./AsyncStateBoundary";
import { useSourceReadinessSnapshot } from "./SourceReadinessContext";
import { aipAgentControl, type IssuedHandoff } from "../../api/aipAgentControl";
import type { ModuleHandoffCompileResponse, TaskCockpitTask, TaskCockpitRun } from "../../api/ecommerceWorkshop";
import { WorkshopOperatingReadinessCard } from "./WorkshopOperatingReadinessCard";
import { WorkshopDisasterRecoveryCard } from "./WorkshopDisasterRecoveryCard";
import { WorkshopCumulativeReleaseGateCard } from "./WorkshopCumulativeReleaseGateCard";
import { WorkshopOperationalReleaseDecisionCard } from "./WorkshopOperationalReleaseDecisionCard";
import { NavIcon } from "../../shell/icons";
import type { IconName } from "../../nav";
import { aipTasksSdk } from "../../api/aipTasks/client";
import type { TaskSnapshot } from "../../api/aipTasks/contracts";

type CockpitClient = Pick<typeof ecommerceWorkshopClient, "getTaskCockpitCore" | "listTaskCockpitRunSteps" | "listTaskCockpitRunCheckpoints" | "getTaskCockpitRunProductionContext" | "getTaskCockpitRunResponsibilityHandoffs" | "compileTaskCockpitRunHandoff" | "getTaskCockpitRunApprovalReview" | "getTaskCockpitRunActionReceipts" | "getTaskCockpitRunSkillContributions"> & Partial<Pick<typeof ecommerceWorkshopClient, "getAnalystView" | "getResponsibilityAssignmentObservation" | "getDispatchControlObservation" | "getTaskCockpitDispatchScenario" | "getTaskCockpitBatchScenario">>;
type HandoffCommandClient = Pick<typeof aipAgentControl, "issueHandoff" | "consumeHandoff" | "listHandoffDecisions" | "createHandoffDecision">;
type TaskCommandClient = Pick<typeof aipTasksSdk, "createTask">;
type InternalTaskCommand = { title: string; colleague: CockpitColleague; recommendation: CockpitRecommendation | null; idempotencyKey: string };
type InternalTaskReceipt = { task: TaskSnapshot; colleague: CockpitColleague; visibleInCockpit: boolean };
type CorePhase = "loading" | "ready" | "empty" | "stale" | "forbidden" | "failed";
type SkillContributionState = { phase: "loading" | "ready" | "failed"; response: TaskCockpitSkillContributionResponse | null };
type AssignmentObservationState = { phase: "loading" | "ready" | "failed"; response: ResponsibilityAssignmentObservation | null };
type DispatchObservationState = { phase: "loading" | "ready" | "failed"; response: DispatchControlObservation | null };
type DispatchScenarioState = { phase: "idle" | "loading" | "ready" | "failed"; response: DispatchScenarioContribution | null };
type BatchScenarioState = { phase: "idle" | "loading" | "ready" | "failed"; response: BatchScenarioContribution | null };
type AnalystSuggestionState = { phase: "idle" | "loading" | "ready" | "failed"; response: AnalystViewResponse | null };
type DetailState = { runId: string; phase: "loading" | "ready" | "failed"; steps: TaskCockpitStepPageResponse | null; checkpoints: TaskCockpitCheckpointPageResponse | null; productionContext: TaskCockpitProductionContextResponse | null; responsibilityHandoffs: TaskCockpitResponsibilityHandoffResponse | null; approvalReview: TaskCockpitApprovalReviewResponse | null; actionReceipts: TaskCockpitActionReceiptResponse | null; skillContributions: SkillContributionState; assignmentObservation: AssignmentObservationState; dispatchObservation: DispatchObservationState } | null;
const TASK_STATUSES: readonly { value: "" | TaskCockpitTaskStatus; label: string }[] = [
  { value: "", label: "全部状态" }, { value: "pending", label: "待规划" }, { value: "planning", label: "规划中" }, { value: "awaiting_approval", label: "待审批" }, { value: "approved", label: "已批准" }, { value: "executing", label: "执行中" }, { value: "paused", label: "已暂停" }, { value: "completed", label: "已完成" }, { value: "failed", label: "失败" }, { value: "cancelled", label: "已取消" }, { value: "rolled_back", label: "已回滚" },
];
const ACTIVE_TASK_STATUSES = new Set<TaskCockpitTaskStatus>(["planning", "awaiting_approval", "approved", "executing", "paused"]);
const TASK_STATUS_LABELS: Record<string, string> = Object.fromEntries(TASK_STATUSES.filter((item) => item.value).map((item) => [item.value, item.label]));
const DEVELOPMENT_TASK_PATTERN = /(?:^|\s)(?:R\d+(?:-[0-9A-Z]+)?|W\d+(?:-[0-9A-Z]+)?|BI-W\d+|AOS-\d+)|\b(?:Skill|Provider|AgentRun|Receipt)\b|(?:开发|代码|技术方案|发布治理审批|单次真实.*验收)/i;

type CockpitColleague = {
  id: string;
  roleKey: string;
  name: string;
  group: "execution" | "planning";
  icon: IconName;
  subtitle: string;
  capability: string;
  boundary: string;
  agents: string;
};

const COCKPIT_COLLEAGUES: readonly CockpitColleague[] = [
  { id: "service-specialist", roleKey: "customer_service", name: "客服专员", group: "execution", icon: "chat", subtitle: "客户服务与售后风险处置专家", capability: "意图与情绪识别、订单与物流安全查询、售后分诊、投诉升级、满意度反哺", boundary: "最小验证后读取脱敏事实；输出回复或工单草稿，高风险事项转人工", agents: "素材采集、文案生成" },
  { id: "private-domain-steward", roleKey: "private_domain_manager", name: "私域管家", group: "execution", icon: "heart", subtitle: "客户关系沉淀与生命周期运营专家", capability: "授权身份关联、可解释标签分层、触达排期、沉默召回、关系反馈", boundary: "仅使用受限客户投影；遵守渠道授权、频控与退订边界", agents: "素材采集、文案生成" },
  { id: "shopping-advisor", roleKey: "shopping_advisor", name: "导购顾问", group: "execution", icon: "user", subtitle: "购物决策支持与转化优化专家", capability: "需求诊断、约束下商品推荐、成分属性解释、商品对比搭配、异议处理与促单", boundary: "推荐必须可解释并受库存、价格、禁忌与承诺边界约束；越界转人工", agents: "素材采集、策略规划、脚本撰写、直播编排" },
  { id: "data-advisor", roleKey: "data_advisor", name: "数据参谋", group: "planning", icon: "graph", subtitle: "经营洞察、任务编排与效果复盘专家", capability: "经营健康巡检、内外机会研究、增长方案、审批后任务拆解、执行监控、归因复盘", boundary: "建议必须有证据和时效；审批前只产出草稿，派活须可追溯到经营事实或记忆", agents: "素材采集、策略规划、数据复盘" },
  { id: "content-officer", roleKey: "content_officer", name: "内容官", group: "planning", icon: "film", subtitle: "全平台内容策略与生产编排专家", capability: "选题研究、人群与内容策略、图文文案、短视频策划、多平台适配、事实品牌合规审核、线索识别与归因", boundary: "所有内容先形成草稿；事实、品牌、版权与平台规则通过审核后才能发布", agents: "素材采集、策略规划、文案生成、脚本撰写、内容审核、平台适配" },
  { id: "campaign-planner", roleKey: "campaign_planner", name: "活动策划师", group: "planning", icon: "spark", subtitle: "增长活动设计、协同与止损专家", capability: "机会目标、人群商品机制、预算毛利模拟、跨同事任务编排、执行监控止损、增量复盘", boundary: "方案受库存、毛利、预算、投诉与履约护栏约束；外部合作和高风险动作需审批", agents: "素材采集、策略规划、平台适配、数据复盘" },
];

type CockpitRecommendation = {
  id: string;
  label: string;
  text: string;
  definitionRef: string;
  observationRef: string;
  dataCutoff: string;
};

function cockpitRecommendations(response: AnalystViewResponse | null): CockpitRecommendation[] {
  if (!response) return [];
  const exactMetrics = new Map<string, AnalystViewResponse["views"][number]["metrics"][number]>();
  for (const view of response.views) {
    for (const metric of view.metrics) {
      if (metric.status === "ready" && metric.value !== null && metric.definitionRef && metric.observationRef && !exactMetrics.has(metric.metricId)) {
        exactMetrics.set(metric.metricId, metric);
      }
    }
  }
  const recommendation = (id: string, label: string, text: string, metricIds: string[]): CockpitRecommendation | null => {
    const metrics = metricIds.map((metricId) => exactMetrics.get(metricId)).filter((metric) => metric?.definitionRef && metric.observationRef);
    if (metrics.length !== metricIds.length) return null;
    return {
      id,
      label,
      text,
      definitionRef: metrics.map((metric) => `${metric!.definitionRef!.resourceType}:${metric!.definitionRef!.resourceId}@${metric!.definitionRef!.revision}`).join("|"),
      observationRef: metrics.map((metric) => `${metric!.observationRef!.resourceType}:${metric!.observationRef!.resourceId}@${metric!.observationRef!.revision}`).join("|"),
      dataCutoff: response.dataCutoff,
    };
  };
  const count = (metricId: string) => Math.max(0, Math.trunc(exactMetrics.get(metricId)?.value ?? 0)).toLocaleString("zh-CN");
  const positive = (metricId: string) => (exactMetrics.get(metricId)?.value ?? 0) > 0;
  const storeName = response.tenant.orgId === "org-org" && response.tenant.projectId === "dev-project" ? "栖月汇微商城" : "当前微商城";
  const qualityMetricIds = [positive("failed_source_count") ? "failed_source_count" : null, positive("stale_source_count") ? "stale_source_count" : null].filter((item): item is string => item !== null);
  const qualitySummary = [positive("failed_source_count") ? `${count("failed_source_count")} 个异常数据源` : null, positive("stale_source_count") ? `${count("stale_source_count")} 个过期数据源` : null].filter(Boolean).join("和");
  const operationMetricIds = [exactMetrics.has("order_count") ? "order_count" : null, exactMetrics.has("product_count") ? "product_count" : null, positive("product_review_count") ? "product_review_count" : null].filter((item): item is string => item !== null);
  const operationSummary = [exactMetrics.has("order_count") ? `${count("order_count")} 笔订单` : null, exactMetrics.has("product_count") ? `${count("product_count")} 个商品` : null, positive("product_review_count") ? `${count("product_review_count")} 条商品评价` : null].filter(Boolean).join("、");
  const candidates = [
    qualityMetricIds.length ? recommendation("quality", "核对经营数据异常", `核对${storeName}的${qualitySummary}并生成修复清单`, qualityMetricIds) : null,
    operationMetricIds.length ? recommendation("operation", "复盘订单与商品规模", `复盘${storeName}的${operationSummary}的经营表现并整理问题清单`, operationMetricIds) : null,
    exactMetrics.has("customer_count") ? recommendation("customer", "梳理客户运营机会", `分析${storeName}的${count("customer_count")} 位客户分层并形成跟进建议`, ["customer_count"]) : null,
  ];
  return candidates.filter((item): item is CockpitRecommendation => item !== null).slice(0, 3);
}

function recommendColleague(title: string): CockpitColleague {
  const rules: readonly [RegExp, string][] = [
    [/(?:售后|投诉|退款|物流|客服)/, "customer_service"],
    [/(?:客户|会员|私域|召回|触达)/, "private_domain_manager"],
    [/(?:商品|选品|导购|推荐|价格|比价|库存)/, "shopping_advisor"],
    [/(?:内容|文案|视频|直播|素材)/, "content_officer"],
    [/(?:活动|促销|优惠|增长方案)/, "campaign_planner"],
  ];
  const roleKey = rules.find(([pattern]) => pattern.test(title))?.[1] ?? "data_advisor";
  return COCKPIT_COLLEAGUES.find((profile) => profile.roleKey === roleKey) ?? COCKPIT_COLLEAGUES[3];
}

function validateInternalTaskTitle(value: string): string {
  const title = value.trim().replace(/\s+/g, " ");
  if (!title) throw new Error("请先输入需要处理的业务任务");
  if (title.length < 4 || title.length > 120) throw new Error("任务内容需为 4～120 个字符");
  if (!/[\u3400-\u9fff]/.test(title)) throw new Error("请使用中文描述真实业务任务");
  if (DEVELOPMENT_TASK_PATTERN.test(title)) throw new Error("这里只下达业务任务，不能提交开发编号或技术实施事项");
  return title;
}

function errorPhase(error: unknown): CorePhase {
  if (!(error instanceof EcommerceWorkshopClientError)) return "failed";
  if (error.status === 401 || error.status === 403) return "forbidden";
  if (error.status === 409 && error.body.code === "TASK_COCKPIT_CURSOR_STALE") return "stale";
  return "failed";
}
function stateFor(phase: CorePhase): AsyncState {
  if (phase === "ready" || phase === "empty") return "ready";
  return phase;
}
function formatTime(value: string | null): string { return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "尚未发生"; }
function blockerMatches(dependency: string, tokens: readonly string[]): boolean {
  const normalized = dependency.toLowerCase();
  return tokens.some((token) => normalized.includes(token));
}

function TaskCockpitVisualSurface({ response, analystSuggestions, phase, status, onStatusChange, onReload, onCreateTask }: {
  response: TaskCockpitCoreResponse | null;
  analystSuggestions: AnalystSuggestionState;
  phase: CorePhase;
  status: "" | TaskCockpitTaskStatus;
  onStatusChange: (status: "" | TaskCockpitTaskStatus) => void;
  onReload: () => void;
  onCreateTask: (command: InternalTaskCommand) => Promise<InternalTaskReceipt>;
}) {
  const entryContext = useRef(() => {
    const search = new URLSearchParams(window.location.search);
    return { roleKey: search.get("colleague"), contribution: search.get("focus") === "contribution" };
  }).current();
  const [commandText, setCommandText] = useState("");
  const [commandNotice, setCommandNotice] = useState("");
  const [commandPreview, setCommandPreview] = useState<InternalTaskCommand | null>(null);
  const [commandReceipt, setCommandReceipt] = useState<InternalTaskReceipt | null>(null);
  const [commandSubmitting, setCommandSubmitting] = useState(false);
  const [selectedRecommendation, setSelectedRecommendation] = useState<CockpitRecommendation | null>(null);
  const [calendarVisible, setCalendarVisible] = useState(false);
  const [activeColleague, setActiveColleague] = useState<CockpitColleague | null>(() => COCKPIT_COLLEAGUES.find((profile) => profile.roleKey === entryContext.roleKey) ?? null);
  const [popoverStyle, setPopoverStyle] = useState<CSSProperties>({ visibility: "hidden" });
  const surfaceRef = useRef<HTMLElement | null>(null);
  const colleagueTriggerRef = useRef<HTMLButtonElement | null>(null);
  const colleaguePopoverRef = useRef<HTMLDivElement | null>(null);
  const colleaguePinnedRef = useRef(Boolean(entryContext.roleKey));
  const suppressNextColleagueFocusRef = useRef(false);
  const commandInputRef = useRef<HTMLInputElement | null>(null);
  useEffect(() => {
    const toggleCalendar = () => setCalendarVisible((value) => !value);
    window.addEventListener("aos-workshop-cockpit-calendar", toggleCalendar);
    return () => window.removeEventListener("aos-workshop-cockpit-calendar", toggleCalendar);
  }, []);
  useLayoutEffect(() => {
    if (!activeColleague) return;
    const place = () => {
      const surface = surfaceRef.current;
      const popover = colleaguePopoverRef.current;
      const trigger = colleagueTriggerRef.current ?? [...(surface?.querySelectorAll<HTMLButtonElement>("[data-colleague-role]") ?? [])].find((item) => item.dataset.colleagueRole === activeColleague.roleKey) ?? null;
      if (!surface || !trigger || !popover) return;
      colleagueTriggerRef.current = trigger;
      const rect = trigger.getBoundingClientRect();
      const surfaceRect = surface.getBoundingClientRect();
      const commandBottom = surface.querySelector<HTMLElement>(".task-cockpit-visual-command")?.getBoundingClientRect().bottom ?? surfaceRect.top;
      const skillsTop = surface.querySelector<HTMLElement>(".task-cockpit-visual-skills")?.getBoundingClientRect().top ?? surfaceRect.bottom;
      const safeTop = Math.max(12, commandBottom + 8);
      const safeBottom = Math.min(window.innerHeight - 12, skillsTop - 8);
      const maxHeight = Math.max(48, safeBottom - safeTop);
      const popoverRect = popover.getBoundingClientRect();
      const onLeft = rect.left < surfaceRect.left + surfaceRect.width / 2;
      const preferredLeft = onLeft ? rect.right + 10 : rect.left - popoverRect.width - 10;
      const left = Math.max(surfaceRect.left + 10, Math.min(preferredLeft, surfaceRect.right - popoverRect.width - 10));
      const preferredTop = rect.top + rect.height / 2 - Math.min(popoverRect.height, maxHeight) / 2;
      const top = Math.max(safeTop, Math.min(preferredTop, safeBottom - Math.min(popoverRect.height, maxHeight)));
      setPopoverStyle({ left, top, maxHeight, visibility: "visible" });
    };
    const close = (restoreFocus: boolean) => {
      const trigger = colleagueTriggerRef.current;
      colleaguePinnedRef.current = false;
      setActiveColleague(null);
      if (restoreFocus && trigger) { suppressNextColleagueFocusRef.current = true; trigger.focus(); }
    };
    place();
    const frame = window.requestAnimationFrame(place);
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") close(true);
    };
    const onPointerDown = (event: PointerEvent) => {
      if (!colleaguePinnedRef.current) return;
      const target = event.target;
      if (!(target instanceof Node) || colleaguePopoverRef.current?.contains(target) || colleagueTriggerRef.current?.contains(target)) return;
      close(false);
    };
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("pointerdown", onPointerDown);
    return () => { window.cancelAnimationFrame(frame); window.removeEventListener("resize", place); window.removeEventListener("scroll", place, true); document.removeEventListener("keydown", onKeyDown); document.removeEventListener("pointerdown", onPointerDown); };
  }, [activeColleague, response]);
  const sourceItems = response?.items ?? [];
  const items = sourceItems.filter((task) => !DEVELOPMENT_TASK_PATTERN.test(task.title));
  const excludedDevelopmentTasks = sourceItems.length - items.length;
  const active = items.filter((task) => ACTIVE_TASK_STATUSES.has(task.status)).length;
  const blockers = response?.blockers ?? [];
  const blocking = blockers.filter((item) => item.severity === "blocking").length;
  const warnings = blockers.filter((item) => item.severity === "warning").length;
  const pending = items.filter((task) => task.status === "pending").length;
  const dependencies = [...new Set(blockers.map((item) => item.dependency))];
  const businessDependencyLabel = (dependency: string) => dependency.includes("source-readiness") ? "业务数据准备" : dependency.includes("production") ? "内容生产编排" : dependency.includes("binding") ? "数字同事配置" : "业务协作能力";
  const value = (current: number | undefined) => current === undefined ? "未知" : String(current);
  const recommendations = cockpitRecommendations(analystSuggestions.response);
  const fillRecommendation = (recommendation: CockpitRecommendation) => {
    setCommandText(recommendation.text);
    setSelectedRecommendation(recommendation);
    setCommandPreview(null);
    setCommandReceipt(null);
    setCommandNotice("已填入经营参谋指标建议，可继续编辑后下达。");
    commandInputRef.current?.focus();
  };
  const updateCommandText = (value: string) => {
    setCommandText(value);
    setCommandPreview(null);
    setCommandReceipt(null);
    if (selectedRecommendation && !value.includes(selectedRecommendation.text.slice(0, 8))) setSelectedRecommendation(null);
  };
  const submitCommand = async () => {
    if (commandSubmitting) return;
    let title: string;
    try { title = validateInternalTaskTitle(commandText); }
    catch (error) { setCommandNotice(error instanceof Error ? error.message : "任务内容不符合要求"); return; }
    if (!commandPreview || commandPreview.title !== title) {
      const colleague = recommendColleague(title);
      setCommandPreview({ title, colleague, recommendation: selectedRecommendation, idempotencyKey: `workshop-task-${crypto.randomUUID()}` });
      setCommandReceipt(null);
      setCommandNotice(`安全预检通过，建议由${colleague.name}承接；再次点击“确认下达”创建内部业务任务。`);
      return;
    }
    setCommandSubmitting(true);
    setCommandNotice("正在创建内部业务任务并核对任务列表…");
    try {
      const receipt = await onCreateTask(commandPreview);
      setCommandReceipt(receipt);
      setCommandPreview(null);
      setCommandText("");
      setSelectedRecommendation(null);
      setCommandNotice(receipt.visibleInCockpit ? `任务受理成功：${receipt.task.id} · 第 ${receipt.task.version} 版 · ${TASK_STATUS_LABELS[receipt.task.status] ?? receipt.task.status} · ${receipt.colleague.name}建议承接 · ${formatTime(receipt.task.createdAt)} · 已在任务流回读。` : `任务已受理：${receipt.task.id}；正在等待任务流回读。`);
    } catch (error) {
      setCommandNotice(error instanceof Error ? `任务创建失败：${error.message}` : "任务创建失败，请核对后重试");
    } finally { setCommandSubmitting(false); }
  };
  const showColleague = (profile: CockpitColleague, trigger: HTMLButtonElement, pinned: boolean, resetViewport = false) => {
    if (resetViewport) {
      const scroller = surfaceRef.current?.closest<HTMLElement>(".content");
      if (scroller) {
        scroller.scrollTop = 0;
        scroller.scrollLeft = 0;
      }
    }
    colleagueTriggerRef.current = trigger;
    colleaguePinnedRef.current = pinned;
    if (activeColleague?.id !== profile.id) setPopoverStyle({ visibility: "hidden" });
    setActiveColleague(profile);
  };
  const renderColleague = (profile: CockpitColleague) => <button
    type="button"
    className={`task-cockpit-colleague-card${activeColleague?.id === profile.id ? " is-active" : ""}`}
    key={profile.id}
    aria-haspopup="dialog"
    aria-expanded={activeColleague?.id === profile.id}
    aria-controls="task-cockpit-colleague-popover"
    aria-label={`${profile.name}：${profile.subtitle}；当前状态尚无个人级归因`}
    data-colleague-role={profile.roleKey}
    onMouseEnter={(event) => { if (!colleaguePinnedRef.current) showColleague(profile, event.currentTarget, false); }}
    onMouseLeave={() => { if (!colleaguePinnedRef.current) setActiveColleague(null); }}
    onFocus={(event) => {
      if (suppressNextColleagueFocusRef.current) { suppressNextColleagueFocusRef.current = false; return; }
      if (!colleaguePinnedRef.current) showColleague(profile, event.currentTarget, false);
    }}
    onBlur={() => { if (!colleaguePinnedRef.current) setActiveColleague(null); }}
    onClick={(event) => {
      if (activeColleague?.id === profile.id && colleaguePinnedRef.current) { colleaguePinnedRef.current = false; setActiveColleague(null); return; }
      showColleague(profile, event.currentTarget, true, true);
    }}
  >
    <span aria-hidden="true"><NavIcon name={profile.icon} /></span>
    <strong>{profile.name}</strong>
    <small><i aria-hidden="true" />状态待核对</small>
  </button>;
  return <section ref={surfaceRef} className={`task-cockpit-visual-surface is-${phase}`} aria-label="日常任务总控大屏">
    {entryContext.roleKey && activeColleague ? <div className="notice" role="status" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, margin: "0 12px 10px" }}>
      <span>{entryContext.contribution ? `正在回读${activeColleague.name}的工作台贡献` : `已定位${activeColleague.name}的业务协作入口`}；正式任务和贡献只从当前租户权威记录读取。</span>
      <a className="btn" href="/aip/agent-registry" data-testid="colleague-return-registry">返回数字同事目录</a>
    </div> : null}
    <div className="task-cockpit-visual-metrics" aria-label="实时经营与任务概览">
      <div><strong>{response ? items.length : "待核对"}</strong><span>今日经营任务</span><small>已排除系统验收记录</small></div>
      <div><strong>{value(active)}</strong><span>执行中</span><small>活跃状态</small></div>
      <div><strong>{value(items.filter((task) => task.run).length)}</strong><span>已绑定执行记录</span><small>不补造缺失记录</small></div>
      <div className={blocking ? "is-danger" : ""}><strong>{value(response ? blocking : undefined)}</strong><span>待补条件</span><small>影响任务执行</small></div>
      <div><strong>{value(response ? pending : undefined)}</strong><span>待规划</span><small>尚未进入执行</small></div>
      <div className={warnings ? "is-warning" : ""}><strong>{value(response ? warnings : undefined)}</strong><span>待接入</span><small>需要补充数据</small></div>
      <div className="is-wide" title={response ? `评估 ${formatTime(response.evaluatedAt)} · 数据截止 ${formatTime(response.taskCutoff)}` : "评估与数据截止尚未验证"}><strong>{response ? new Date(response.evaluatedAt).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false }) : "尚未验证"}</strong><span>评估截止</span><small>{response ? new Date(response.taskCutoff).toLocaleDateString("zh-CN") : "截止时间待核对"}</small></div>
    </div>

    <div className="task-cockpit-visual-command" aria-label="任务指令与筛选">
      <span aria-hidden="true">ϟ</span>
      <input ref={commandInputRef} aria-label="任务指令" value={commandText} onChange={(event) => updateCommandText(event.target.value)} placeholder="描述业务任务需求，系统将先做安全预检…" />
      <button type="button" disabled={commandSubmitting} onClick={() => void submitCommand()}>{commandSubmitting ? "受理中" : commandPreview ? "确认下达" : "下达"}</button>
      <div className="task-cockpit-recommendations" aria-label="经营参谋推荐任务">
        {commandNotice ? <p className="task-cockpit-command-notice" role="status" title={commandNotice}>{commandNotice}</p> : recommendations.map((recommendation) => <button
          type="button"
          className="task-cockpit-recommendation"
          key={recommendation.id}
          title={`经营参谋指标建议 · 数据截止 ${formatTime(recommendation.dataCutoff)} · 定义与观测已精确核对`}
          data-definition-ref={recommendation.definitionRef}
          data-observation-ref={recommendation.observationRef}
          onClick={() => fillRecommendation(recommendation)}
        >{recommendation.label}</button>)}
        {analystSuggestions.phase === "loading" ? <small>正在读取经营建议</small> : null}
        {analystSuggestions.phase !== "loading" && recommendations.length === 0 ? <small>暂无可验证推荐任务</small> : null}
      </div>
      <label>任务状态<select value={status} onChange={(event) => onStatusChange(event.target.value as "" | TaskCockpitTaskStatus)}>{TASK_STATUSES.map((item) => <option key={item.value || "all"} value={item.value}>{item.label}</option>)}</select></label>
      <button type="button" className="is-secondary" onClick={onReload}>重新读取</button>
      {commandReceipt ? <output className="task-cockpit-command-receipt" aria-label="任务受理回执" hidden>
        {commandReceipt.task.id} · 第 {commandReceipt.task.version} 版 · {TASK_STATUS_LABELS[commandReceipt.task.status] ?? commandReceipt.task.status} · {commandReceipt.colleague.name}建议承接 · {formatTime(commandReceipt.task.createdAt)}
      </output> : null}
    </div>

    {calendarVisible ? <section className="task-cockpit-calendar-preview" role="status" aria-label="任务日历视图"><header><strong>任务日历</strong><button type="button" onClick={() => setCalendarVisible(false)}>返回任务流</button></header>{items.length ? <div>{items.map((task) => <article key={task.taskId}><strong>{task.title}</strong><span>{TASK_STATUS_LABELS[task.status] ?? "待核对"}</span><small>{response ? new Date(response.taskCutoff).toLocaleDateString("zh-CN") : "日期待核对"}</small></article>)}</div> : <p>当前没有可排入日历的正式业务任务。</p>}</section> : null}

    <div className="task-cockpit-visual-board">
      <aside className="task-cockpit-visual-role-column" aria-label="执行组">
        <h2>执行组</h2>
        {COCKPIT_COLLEAGUES.filter((profile) => profile.group === "execution").map(renderColleague)}
      </aside>

      <section className="task-cockpit-visual-task-column" aria-labelledby="task-cockpit-visual-title">
        <header><h2 id="task-cockpit-visual-title">当日经营任务流 · 执行进度</h2><span>{response ? `${items.length} 项` : "待验证"}</span></header>
        {items.length ? items.map((task) => <article className={`is-${task.status}`} key={task.taskId}>
          <div><span>业务任务</span><strong>{task.title}</strong><em>{TASK_STATUS_LABELS[task.status] ?? "待核对"}</em></div>
          <div className={`task-cockpit-visual-progress${task.status === "completed" ? " is-complete" : " is-unknown"}`} aria-label={task.status === "completed" ? "任务状态已完成" : "执行进度未提供"}><i style={{ width: task.status === "completed" ? "100%" : "0%" }} /></div>
          <footer><span>业务任务</span><small>{task.run ? `执行记录：${TASK_STATUS_LABELS[task.run.status] ?? "待核对"} · 第 ${task.run.version} 版` : "尚无执行记录"}</small></footer>
        </article>) : <div className="task-cockpit-visual-empty" role="status"><strong>{phase === "loading" ? "正在读取当日任务" : "当前没有可验证的经营任务"}</strong><p>当前没有正式业务任务，页面不会用演示任务填充。</p>{excludedDevelopmentTasks ? <details><summary>查看数据筛选说明</summary><span>已隔离 {excludedDevelopmentTasks} 条非经营任务记录。</span></details> : null}</div>}
      </section>

      <aside className="task-cockpit-visual-role-column" aria-label="策划组">
        <h2>策划组</h2>
        {COCKPIT_COLLEAGUES.filter((profile) => profile.group === "planning").map(renderColleague)}
      </aside>

      <aside className="task-cockpit-visual-review" aria-label="复盘与经验沉淀">
        <header><h2>复盘 · 经验沉淀</h2><span>{response ? `${blockers.length} 项待核对` : "待验证"}</span></header>
        {blockers.length ? <ul>{blockers.slice(0, 5).map((blocker) => <li className={`is-${blocker.severity}`} key={blocker.code}><strong>经营复盘所需数据尚未完整</strong><span>需要补充正式业务数据</span><p>当前任务保持待核对，不自动执行。</p><details><summary>查看审计状态码</summary><code>{blocker.code}</code><small>{blocker.dependency}</small><p>{blocker.requiredAction}</p></details></li>)}</ul> : <div className="task-cockpit-visual-empty"><strong>没有可回读复盘</strong><p>不使用静态复盘结果或伪成功状态。</p></div>}
      </aside>
    </div>

    <div className="task-cockpit-visual-skills"><strong>共享业务能力</strong><div>{dependencies.length ? dependencies.map((item) => <span key={item}>{businessDependencyLabel(item)}</span>) : <span>等待正式能力配置</span>}</div></div>
    <footer className="task-cockpit-visual-tomorrow"><span>明日预告 · 仅显示已排期业务任务</span><strong>{response ? `${items.filter((task) => task.status === "pending").length} 项待规划` : "计划表未验证"}</strong></footer>
    {activeColleague ? <div
      ref={colleaguePopoverRef}
      id="task-cockpit-colleague-popover"
      className="task-cockpit-colleague-popover"
      role="dialog"
      aria-label={`${activeColleague.name}介绍`}
      aria-modal="false"
      style={popoverStyle}
    >
      <header><div><strong>{activeColleague.name}</strong><span>{activeColleague.subtitle}</span></div><b>{activeColleague.roleKey === "data_advisor" ? "数字同事 · 总调度" : "数字同事"}</b><button type="button" aria-label="关闭数字同事介绍" onClick={() => { const trigger = colleagueTriggerRef.current; colleaguePinnedRef.current = false; setActiveColleague(null); if (trigger) { suppressNextColleagueFocusRef.current = true; trigger.focus(); } }}>×</button></header>
      <dl>
        <div><dt>专业能力</dt><dd>{activeColleague.capability}</dd></div>
        <div><dt>工作边界</dt><dd>{activeColleague.boundary}</dd></div>
        <div><dt>常用 Agent</dt><dd>{activeColleague.agents}</dd></div>
        <div><dt>当前状态</dt><dd>{response ? "已取得任务总览；尚无个人级归因，不能推导在线或执行中" : "个人运行状态待核对"}</dd></div>
      </dl>
    </div> : null}
  </section>;
}

function TaskCockpitBusinessContext() {
  const snapshot = useSourceReadinessSnapshot();
  if (!snapshot) {
    return <section className="task-cockpit-business-context is-failed" aria-label="业务上下文独立快照"><strong>业务上下文未装配</strong><p>未取得 Shell 的 canonical SourceReadiness 快照；不以空值代替。</p></section>;
  }
  if (snapshot.phase !== "ready" || !snapshot.response) {
    const label = snapshot.phase === "loading" ? "正在读取业务上下文" : snapshot.phase === "forbidden" ? "业务上下文无访问权限" : "业务上下文读取失败";
    return <section className={`task-cockpit-business-context is-${snapshot.phase}`} aria-label="业务上下文独立快照"><strong>{label}</strong><p>SourceReadiness 有独立 cutoff；不与 Task cutoff 混算，也不把未知状态解释为空。</p>{snapshot.phase === "failed" ? <button type="button" onClick={snapshot.reload}>重新读取 SourceReadiness</button> : null}</section>;
  }
  const response = snapshot.response;
  const readyCount = response.sources.filter((source) => source.status === "ready").length;
  const blockers = [...new Set(response.sources.flatMap((source) => source.blockers))].sort();
  return <section className={`task-cockpit-business-context is-${response.status}`} aria-label="业务上下文独立快照">
    <div><p className="ecommerce-workshop-eyebrow">业务上下文 · 独立 SourceReadiness 快照</p><strong>{response.status}</strong></div>
    <dl><div><dt>就绪源</dt><dd>{readyCount} / {response.sources.length}</dd></div><div><dt>检查时间</dt><dd>{formatTime(response.checkedAt)}</dd></div><div><dt>数据 cutoff</dt><dd>{formatTime(response.cutoffAt)}</dd></div><div><dt>EvidencePack</dt><dd>{response.receiptRef ? `${response.receiptRef.resourceId} · r${response.receiptRef.revision}` : "无 exact EvidencePack Receipt"}</dd></div></dl>
    <p>{blockers.length ? `当前 blocker：${blockers.join(" · ")}` : "当前响应未声明 blocker；仍以 exact Receipt 和独立 cutoff 为准。"}</p>
  </section>;
}

function ModuleHandoffCommandPanel({ task, run, responsibility, workshopClient, commandClient, onRefresh }: { task: TaskCockpitTask; run: TaskCockpitRun; responsibility: TaskCockpitResponsibilityHandoffResponse; workshopClient: CockpitClient; commandClient: HandoffCommandClient; onRefresh: () => void }) {
  const slots = responsibility.slots.filter((slot) => slot.assignee.kind === "agent_instance");
  const [sourceModuleId, setSourceModuleId] = useState("ecommerce.content-campaign");
  const [targetModuleId, setTargetModuleId] = useState("ecommerce.media-studio");
  const [sourceSlotId, setSourceSlotId] = useState(slots[0]?.slotId ?? "");
  const [targetSlotId, setTargetSlotId] = useState(slots[1]?.slotId ?? "");
  const [purpose, setPurpose] = useState("跨模块受控协作");
  const [requestedOutcome, setRequestedOutcome] = useState("返回可审计的业务决定");
  const [phase, setPhase] = useState<"idle" | "compiling" | "compiled" | "issuing" | "issued" | "consuming" | "consumed" | "deciding" | "decided" | "failed">("idle");
  const [compiled, setCompiled] = useState<ModuleHandoffCompileResponse | null>(null);
  const [issued, setIssued] = useState<IssuedHandoff | null>(null);
  const [ephemeralToken, setEphemeralToken] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const commandId = () => `${run.runId}-${Date.now()}-${globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2)}`;
  const compile = () => {
    setPhase("compiling"); setFailure(null); setCompiled(null); setIssued(null); setEphemeralToken(null);
    const handoffId = `handoff-${commandId()}`.slice(0, 200);
    void workshopClient.compileTaskCockpitRunHandoff(run.runId, { handoffId, taskRef: { resourceType: "Task", resourceId: task.taskId, revision: String(task.version), authority: "postgresql" }, runRef: { resourceType: "TaskRun", resourceId: run.runId, revision: String(run.version), authority: "postgresql" }, sourceModuleId, targetModuleId, sourceSlotId, targetSlotId, purpose, requestedOutcome, objectRefs: [], artifactRefs: [], evidenceRefs: [], context: {}, allowedContextFields: [], markings: ["public"], expiresAt: new Date(Date.now() + 15 * 60_000).toISOString(), correlationRef: null }).then((result) => { setCompiled(result); setPhase("compiled"); }, (error: unknown) => { setFailure(error instanceof Error ? error.message : "编译失败"); setPhase("failed"); });
  };
  const issue = () => {
    if (!compiled?.issueCommand) return;
    setPhase("issuing"); setFailure(null);
    void commandClient.issueHandoff(compiled.issueCommand, `issue-${commandId()}`.slice(0, 200)).then((result) => { setIssued(result); setEphemeralToken(result.bearerToken); setPhase("issued"); }, (error: unknown) => { setFailure(error instanceof Error ? error.message : "签发失败"); setPhase("failed"); });
  };
  const consume = () => {
    if (!issued || !ephemeralToken || !compiled?.issueCommand) return;
    setPhase("consuming"); setFailure(null);
    void commandClient.consumeHandoff(issued.handoff.handoffId, { bearerToken: ephemeralToken, receiverInstance: compiled.issueCommand.envelope.receiverInstance }).then(() => { setEphemeralToken(null); setPhase("consumed"); }, (error: unknown) => { setFailure(error instanceof Error ? error.message : "接收失败"); setPhase("failed"); });
  };
  const accept = () => {
    if (!issued || !compiled?.issueCommand) return;
    setPhase("deciding"); setFailure(null);
    void commandClient.listHandoffDecisions(issued.handoff.handoffId).then((timeline) => commandClient.createHandoffDecision(issued.handoff.handoffId, { decision: "accepted", expectedHeadVersion: timeline.headVersion, reasonCode: null, gapCodes: [], returnRefs: [], correlationRef: null, receiverInstance: compiled.issueCommand!.envelope.receiverInstance }, `decision-${commandId()}`.slice(0, 200))).then(() => { setPhase("decided"); onRefresh(); }, (error: unknown) => { setFailure(error instanceof Error ? error.message : "决定失败"); setPhase("failed"); });
  };
  const invalid = !sourceModuleId || !targetModuleId || sourceModuleId === targetModuleId || !sourceSlotId || !targetSlotId || sourceSlotId === targetSlotId || !purpose.trim() || !requestedOutcome.trim();
  return <div className="task-cockpit-handoff-command" aria-label="模块交接受控命令">
    <div className="task-cockpit-production-refs"><strong>模块交接 · 显式受控命令</strong><span>compile → issue → consume → decision</span><span>不会自动启动 AgentRun</span></div>
    <p className="task-cockpit-approval-boundary">编译零副作用；签发后 bearer 仅保存在当前页面内存，成功接收即清除。consumed 仍不等于 accepted。</p>
    <div className="task-cockpit-handoff-command-grid">
      <label>来源模块<input value={sourceModuleId} onChange={(event) => setSourceModuleId(event.target.value)} /></label>
      <label>目标模块<input value={targetModuleId} onChange={(event) => setTargetModuleId(event.target.value)} /></label>
      <label>来源职责<select value={sourceSlotId} onChange={(event) => setSourceSlotId(event.target.value)}>{slots.map((slot) => <option value={slot.slotId} key={slot.slotId}>{slot.slotId}</option>)}</select></label>
      <label>目标职责<select value={targetSlotId} onChange={(event) => setTargetSlotId(event.target.value)}>{slots.map((slot) => <option value={slot.slotId} key={slot.slotId}>{slot.slotId}</option>)}</select></label>
      <label>目的<input value={purpose} onChange={(event) => setPurpose(event.target.value)} /></label>
      <label>期望结果<input value={requestedOutcome} onChange={(event) => setRequestedOutcome(event.target.value)} /></label>
    </div>
    <div className="task-cockpit-handoff-actions"><button type="button" disabled={invalid || phase === "compiling"} onClick={compile}>编译交接</button>{compiled?.readiness === "ready" ? <button type="button" disabled={phase === "issuing" || Boolean(issued)} onClick={issue}>确认签发</button> : null}{issued && ephemeralToken ? <button type="button" disabled={phase === "consuming"} onClick={consume}>安全接收</button> : null}{issued && phase === "consumed" ? <button type="button" onClick={accept}>接受交接</button> : null}</div>
    {compiled?.readiness === "blocked" ? <p role="status">编译阻断：{compiled.blockers.map((item) => `${item.code} · ${item.requiredAction}`).join("；")}</p> : null}
    {compiled?.readiness === "ready" && !issued ? <p role="status">编译完成：零副作用；需再次确认才会签发 canonical Handoff。</p> : null}
    {issued ? <p role="status">{issued.handoff.handoffId} · {phase}{ephemeralToken ? " · 一次性凭证尚未接收" : " · 页面未保留凭证"}</p> : null}
    {phase === "decided" ? <p role="status">accepted Decision 已追加；未启动或完成下游任务。</p> : null}
    {failure ? <p role="alert">{failure}</p> : null}
  </div>;
}

export function TaskCockpitPage({ client = ecommerceWorkshopClient, handoffClient = aipAgentControl, taskClient = aipTasksSdk }: { client?: CockpitClient; handoffClient?: HandoffCommandClient; taskClient?: TaskCommandClient }) {
  const [phase, setPhase] = useState<CorePhase>("loading");
  const [response, setResponse] = useState<TaskCockpitCoreResponse | null>(null);
  const [status, setStatus] = useState<"" | TaskCockpitTaskStatus>("");
  const [detail, setDetail] = useState<DetailState>(null);
  const [dispatchScenario, setDispatchScenario] = useState<DispatchScenarioState>({ phase: "idle", response: null });
  const [batchScenario, setBatchScenario] = useState<BatchScenarioState>({ phase: "idle", response: null });
  const [analystSuggestions, setAnalystSuggestions] = useState<AnalystSuggestionState>({ phase: "idle", response: null });
  const coreRequest = useRef(0);
  const detailRequest = useRef(0);
  const scenarioRequest = useRef(0);

  const createInternalTask = async (command: InternalTaskCommand): Promise<InternalTaskReceipt> => {
    const task = await taskClient.createTask({
      type: "ecommerce.workshop.business_task",
      title: command.title,
      description: `由日常任务总控大屏受理，建议${command.colleague.name}承接。`,
      priority: 50,
      idempotencyKey: command.idempotencyKey,
      goal: {
        workshopAssignment: { roleKey: command.colleague.roleKey, colleagueName: command.colleague.name, status: "requested" },
        sourceEvidence: command.recommendation ? { definitionRef: command.recommendation.definitionRef, observationRef: command.recommendation.observationRef, dataCutoff: command.recommendation.dataCutoff } : null,
        origin: "workshop.task-cockpit",
      },
    });
    const requestId = ++coreRequest.current;
    setStatus("");
    const next = await client.getTaskCockpitCore({ status: undefined, limit: 20, cursor: undefined });
    if (requestId === coreRequest.current) {
      setResponse(next);
      setPhase(next.items.length === 0 ? "empty" : "ready");
      setDetail(null);
    }
    return { task, colleague: command.colleague, visibleInCockpit: next.items.some((item) => item.taskId === task.id) };
  };

  const load = (nextStatus: "" | TaskCockpitTaskStatus, cursor?: string, preserve = false) => {
    const requestId = ++coreRequest.current;
    if (!preserve) setResponse(null);
    setPhase(preserve && response ? "stale" : "loading");
    setDetail(null);
    const scenarioRequestId = ++scenarioRequest.current;
    if (client.getAnalystView) {
      setAnalystSuggestions({ phase: "loading", response: null });
      void client.getAnalystView().then(
        (next) => { if (scenarioRequestId === scenarioRequest.current) setAnalystSuggestions({ phase: "ready", response: next }); },
        () => { if (scenarioRequestId === scenarioRequest.current) setAnalystSuggestions({ phase: "failed", response: null }); },
      );
    } else {
      setAnalystSuggestions({ phase: "idle", response: null });
    }
    if (client.getTaskCockpitDispatchScenario) {
      setDispatchScenario({ phase: "loading", response: null });
      void client.getTaskCockpitDispatchScenario().then(
        (next) => { if (scenarioRequestId === scenarioRequest.current) setDispatchScenario({ phase: "ready", response: next }); },
        () => { if (scenarioRequestId === scenarioRequest.current) setDispatchScenario({ phase: "failed", response: null }); },
      );
    } else {
      setDispatchScenario({ phase: "idle", response: null });
    }
    if (client.getTaskCockpitBatchScenario) {
      setBatchScenario({ phase: "loading", response: null });
      void client.getTaskCockpitBatchScenario().then(
        (next) => { if (scenarioRequestId === scenarioRequest.current) setBatchScenario({ phase: "ready", response: next }); },
        () => { if (scenarioRequestId === scenarioRequest.current) setBatchScenario({ phase: "failed", response: null }); },
      );
    } else {
      setBatchScenario({ phase: "idle", response: null });
    }
    void client.getTaskCockpitCore({ status: nextStatus || undefined, limit: 20, cursor }).then(
      (next) => {
        if (requestId !== coreRequest.current) return;
        setResponse(next);
        setPhase(next.items.length === 0 ? "empty" : "ready");
      },
      (error: unknown) => {
        if (requestId !== coreRequest.current) return;
        setPhase(errorPhase(error));
        if (!preserve) setResponse(null);
      },
    );
  };

  useEffect(() => {
    load("", undefined, false);
    return () => { coreRequest.current += 1; detailRequest.current += 1; scenarioRequest.current += 1; };
    // client identity is fixed for the mounted page; tenant change unmounts through Host.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client]);

  const toggleDetails = (taskId: string, runId: string) => {
    if (detail?.runId === runId) { detailRequest.current += 1; setDetail(null); return; }
    const requestId = ++detailRequest.current;
    setDetail({ runId, phase: "loading", steps: null, checkpoints: null, productionContext: null, responsibilityHandoffs: null, approvalReview: null, actionReceipts: null, skillContributions: { phase: "loading", response: null }, assignmentObservation: { phase: "loading", response: null }, dispatchObservation: { phase: "loading", response: null } });
    void Promise.all([client.listTaskCockpitRunSteps(runId, { limit: 20 }), client.listTaskCockpitRunCheckpoints(runId, { limit: 20 }), client.getTaskCockpitRunProductionContext(runId), client.getTaskCockpitRunResponsibilityHandoffs(runId), client.getTaskCockpitRunApprovalReview(runId), client.getTaskCockpitRunActionReceipts(runId)]).then(
      ([steps, checkpoints, productionContext, responsibilityHandoffs, approvalReview, actionReceipts]) => { if (requestId === detailRequest.current) setDetail((current) => current?.runId === runId ? { ...current, phase: "ready", steps, checkpoints, productionContext, responsibilityHandoffs, approvalReview, actionReceipts } : current); },
      () => { if (requestId === detailRequest.current) setDetail((current) => current?.runId === runId ? { ...current, phase: "failed", steps: null, checkpoints: null, productionContext: null, responsibilityHandoffs: null, approvalReview: null, actionReceipts: null } : current); },
    );
    void client.getTaskCockpitRunSkillContributions(runId).then(
      (next) => { if (requestId === detailRequest.current) setDetail((current) => current?.runId === runId ? { ...current, skillContributions: { phase: "ready", response: next } } : current); },
      () => { if (requestId === detailRequest.current) setDetail((current) => current?.runId === runId ? { ...current, skillContributions: { phase: "failed", response: null } } : current); },
    );
    if (client.getResponsibilityAssignmentObservation) {
      void client.getResponsibilityAssignmentObservation(runId).then(
        (next) => { if (requestId === detailRequest.current) setDetail((current) => current?.runId === runId ? { ...current, assignmentObservation: { phase: "ready", response: next } } : current); },
        () => { if (requestId === detailRequest.current) setDetail((current) => current?.runId === runId ? { ...current, assignmentObservation: { phase: "failed", response: null } } : current); },
      );
    } else {
      setDetail((current) => current?.runId === runId ? { ...current, assignmentObservation: { phase: "failed", response: null } } : current);
    }
    if (client.getDispatchControlObservation) {
      void client.getDispatchControlObservation(taskId).then(
        (next) => { if (requestId === detailRequest.current) setDetail((current) => current?.runId === runId ? { ...current, dispatchObservation: { phase: "ready", response: next } } : current); },
        () => { if (requestId === detailRequest.current) setDetail((current) => current?.runId === runId ? { ...current, dispatchObservation: { phase: "failed", response: null } } : current); },
      );
    } else {
      setDetail((current) => current?.runId === runId ? { ...current, dispatchObservation: { phase: "failed", response: null } } : current);
    }
  };

  const content = response ? (() => {
    const latestRunCount = response.items.filter((task) => task.run !== null).length;
    const activeTaskCount = response.items.filter((task) => ACTIVE_TASK_STATUSES.has(task.status)).length;
    const blockingCount = response.blockers.filter((blocker) => blocker.severity === "blocking").length;
    const warningCount = response.blockers.filter((blocker) => blocker.severity === "warning").length;
    const executionBlockers = response.blockers.filter((blocker) => blockerMatches(blocker.dependency, ["responsibility", "handoff", "assignee"]));
    const planningBlockers = response.blockers.filter((blocker) => blockerMatches(blocker.dependency, ["stage", "business", "approval", "issue"]));
    const dependencyTags = [...new Set(response.blockers.map((blocker) => blocker.dependency))];

    return <div className="task-cockpit-read-model">
      <section className="task-cockpit-metrics" aria-label="当前任务权威指标">
        <h2 className="sr-only">当前任务权威指标与当前只读范围</h2>
        <div><span>当前页任务</span><strong>{response.page.count}</strong><small>仅当前权威页</small></div>
        <div><span>活跃状态</span><strong>{activeTaskCount}</strong><small>由 Task 状态计算</small></div>
        <div><span>latest Run</span><strong>{latestRunCount}</strong><small>未补造缺失 Run</small></div>
        <div className={blockingCount ? "is-blocked" : "is-clear"}><span>阻断</span><strong>{blockingCount}</strong><small>blocking blocker</small></div>
        <div className={warningCount ? "is-warning" : "is-clear"}><span>待接入</span><strong>{warningCount}</strong><small>warning blocker</small></div>
        <div className="task-cockpit-metric-cutoff"><span>评估时间</span><strong>{formatTime(response.evaluatedAt)}</strong><small>成员截止 {formatTime(response.taskCutoff)}</small></div>
      </section>

      <TaskCockpitBusinessContext />

      {dispatchScenario.phase === "loading" ? <section className="task-cockpit-dispatch-scenario is-loading" aria-label="跨工作台任务派发" role="status"><strong>正在读取跨工作台任务派发状态…</strong><p>不用页面本地状态推导负责人或交接成功。</p></section> : null}
      {dispatchScenario.phase === "failed" ? <section className="task-cockpit-dispatch-scenario is-failed" aria-label="跨工作台任务派发" role="alert"><strong>跨工作台任务派发状态读取失败</strong><p>任务总控仍可使用；派发、决定、接管与负责人变更均不开放。</p></section> : null}
      {dispatchScenario.phase === "ready" && dispatchScenario.response ? <section className="task-cockpit-dispatch-scenario is-blocked" aria-label="跨工作台任务派发">
        <header><div><span>任务协作 · 只读</span><h2>跨工作台派发、退回、补充与人工接管</h2></div><strong>{dispatchScenario.response.status === "blocked" ? "等待授权条件" : "可读取"}</strong></header>
        <p>原子 Skill → Logic 编排 → 数字同事绑定 → 工作台贡献视图；接收方必须重新授权，accepted 不等于任务完成。</p>
        {dispatchScenario.response.composition ? <div className="task-cockpit-dispatch-layers"><div><span>原子 Skill</span><strong>{dispatchScenario.response.composition.atomicSkillRefs.length}</strong><small>{dispatchScenario.response.composition.atomicSkillRefs.map((item) => `${item.resourceId}@${item.revision}`).join("、")}</small></div><div><span>Logic</span><strong>{dispatchScenario.response.composition.logicRevisionRef.resourceId}</strong><small>v{dispatchScenario.response.composition.logicRevisionRef.revision}</small></div><div><span>数字同事绑定</span><strong>{dispatchScenario.response.composition.roleBindings.length}</strong><small>{dispatchScenario.response.composition.roleBindings.map((item) => `${item.roleRef.resourceId} → ${item.assigneeRef.resourceId}`).join("、")}</small></div></div> : <p className="task-cockpit-approval-boundary">{dispatchScenario.response.blockers.map((item) => item.code).join("、")}；未制造 Skill、Logic、角色或 owner 事实。</p>}
        <ol className="task-cockpit-dispatch-stages">{dispatchScenario.response.stages.map((stage) => <li className={`is-${stage.status}`} key={stage.stageId}><span>{stage.stageId}</span><strong>{stage.status}</strong><p>{stage.contribution}</p><small>{stage.exactRefs.length ? `${stage.exactRefs.length} 个 exact ref` : stage.blockers.map((item) => item.code).join("、")}</small></li>)}</ol>
        <div className="task-cockpit-dispatch-ledger" aria-label="派发决定与 owner 守恒"><div><span>Task</span><strong>{dispatchScenario.response.ledger.tasksObserved}/{dispatchScenario.response.ledger.tasksExpected}</strong></div><div><span>Handoff</span><strong>{dispatchScenario.response.ledger.handoffsObserved}/{dispatchScenario.response.ledger.handoffsExpected}</strong></div><div><span>决定</span><strong>{dispatchScenario.response.ledger.decisionsRecorded}/{dispatchScenario.response.ledger.decisionsExpected}</strong></div><div><span>request_more</span><strong>{dispatchScenario.response.ledger.requestMore}</strong></div><div><span>接管</span><strong>{dispatchScenario.response.ledger.takeoverDecided}/{dispatchScenario.response.ledger.takeoverRequested}</strong></div><div><span>active owner</span><strong>{dispatchScenario.response.ledger.activeOwnerCount}</strong></div></div>
        <div className="task-cockpit-dispatch-axes">{dispatchScenario.response.outcomeAxes.map((axis) => <article className={`is-${axis.status}`} key={axis.axisId}><span>{axis.axisId}</span><strong>{axis.status}</strong><p>{axis.exactRef ? `${axis.exactRef.resourceType} · v${axis.exactRef.revision}` : axis.blocker?.code}</p></article>)}</div>
        <p className="task-cockpit-approval-boundary">本场景命令：dispatch=false · decide_handoff=false · request_takeover=false · approve_takeover=false · mutate_owner=false。</p>
      </section> : null}

      {batchScenario.phase === "loading" ? <section className="task-cockpit-batch-scenario is-loading" aria-label="批量任务准备与结果协调" role="status"><strong>正在读取批量任务状态…</strong><p>准备、显式启动、部分完成、结果待核对与协调不由页面本地状态推导。</p></section> : null}
      {batchScenario.phase === "failed" ? <section className="task-cockpit-batch-scenario is-failed" aria-label="批量任务准备与结果协调" role="alert"><strong>批量任务状态读取失败</strong><p>任务总控仍可使用；准备、启动、取消、自动重试与协调操作均不开放。</p></section> : null}
      {batchScenario.phase === "ready" && batchScenario.response ? <section className="task-cockpit-batch-scenario is-blocked" aria-label="批量任务准备与结果协调">
        <header><div><span>批量任务 · 只读</span><h2>批量准备、显式启动与结果协调</h2></div><strong>等待授权条件</strong></header>
        <p>冻结成员先逐项准备，再以 exact BatchStartDecision 显式启动；unknown 只允许同指纹权威回读或追加 Reconcile Receipt，绝不自动重试。</p>
        {batchScenario.response.composition ? <div className="task-cockpit-batch-layers"><div><span>原子 Skill</span><strong>{batchScenario.response.composition.atomicSkillRefs.length}</strong><small>{batchScenario.response.composition.atomicSkillRefs.map((item) => `${item.resourceId}@${item.revision}`).join("、")}</small></div><div><span>Logic</span><strong>{batchScenario.response.composition.logicRevisionRef.resourceId}</strong><small>v{batchScenario.response.composition.logicRevisionRef.revision}</small></div><div><span>数字同事绑定</span><strong>{batchScenario.response.composition.roleBindings.length}</strong><small>{batchScenario.response.composition.roleBindings.map((item) => `${item.roleRef.resourceId} → ${item.assigneeRef.resourceId}`).join("、")}</small></div></div> : <p className="task-cockpit-approval-boundary">{batchScenario.response.blockers.map((item) => item.code).join("、")}；未制造 Skill、Logic、数字同事绑定或批次事实。</p>}
        <ol className="task-cockpit-batch-stages">{batchScenario.response.stages.map((stage) => <li className={`is-${stage.status}`} key={stage.stageId}><span>{stage.stageId}</span><strong>{stage.status}</strong><p>{stage.contribution}</p><small>{stage.exactRefs.length ? `${stage.exactRefs.length} 个 exact ref` : stage.blockers.map((item) => item.code).join("、")}</small></li>)}</ol>
        <div className="task-cockpit-batch-ledger" aria-label="批量准备与子任务结果守恒"><div><span>冻结成员</span><strong>{batchScenario.response.ledger.frozenTotal}</strong></div><div><span>纳入 / 排除</span><strong>{batchScenario.response.ledger.included} / {batchScenario.response.ledger.excluded}</strong></div><div><span>准备 blocked / unknown</span><strong>{batchScenario.response.ledger.blocked} / {batchScenario.response.ledger.preparationUnknown}</strong></div><div><span>子任务观测</span><strong>{batchScenario.response.ledger.childrenObserved}/{batchScenario.response.ledger.childrenExpected}</strong></div><div><span>成功 / 失败 / 取消</span><strong>{batchScenario.response.ledger.succeeded} / {batchScenario.response.ledger.failed} / {batchScenario.response.ledger.cancelled}</strong></div><div><span>unknown / reconciled</span><strong>{batchScenario.response.ledger.childUnknown} / {batchScenario.response.ledger.reconciled}</strong></div></div>
        {batchScenario.response.preparationDecisions.length ? <div className="task-cockpit-batch-items"><strong>逐项准备判定</strong><ul>{batchScenario.response.preparationDecisions.map((item) => <li className={`is-${item.disposition}`} key={item.itemKey}><span>{item.itemKey}</span><strong>{item.disposition}</strong><small>{item.reasonCodes.join("、") || `${item.originalRefs.length} 个原始 ref`}</small></li>)}</ul></div> : null}
        <div className="task-cockpit-batch-axes">{batchScenario.response.outcomeAxes.map((axis) => <article className={`is-${axis.status}`} key={axis.axisId}><span>{axis.axisId}</span><strong>{axis.status}</strong><p>{axis.exactRefs.length ? `${axis.exactRefs.length} 个 exact ref` : axis.blockers.map((item) => item.code).join("、")}</p></article>)}</div>
        <p className="task-cockpit-approval-boundary">命令：prepare=false · start=false · cancel=false · reconcile=false；automatic_retry=false · external_effect=false · release=false。</p>
      </section> : null}

      <section className="task-cockpit-command-blocked" aria-labelledby="task-cockpit-command-title">
        <span className="task-cockpit-command-icon" aria-hidden="true">✦</span>
        <div>
          <h2 id="task-cockpit-command-title">通用任务指令仍失败关闭</h2>
          <p>Task、Run、Step 与 Checkpoint 保持只读；仅在 Run 明细内开放经过 compiler 与 canonical authority 的模块交接命令。</p>
        </div>
        <span className="task-cockpit-readonly-badge">受控交接</span>
      </section>

      <div className="task-cockpit-board">
        <aside className="task-cockpit-role-lane" aria-labelledby="task-cockpit-execution-title">
          <h2 id="task-cockpit-execution-title">执行组</h2>
          <div className="task-cockpit-lane-state">
            <span aria-hidden="true">◎</span>
            <strong>职责视图未接入</strong>
            <p>不使用视觉稿中的六角色在线状态或任务数量代替权威分配。</p>
          </div>
          {executionBlockers.map((blocker) => <div className="task-cockpit-lane-blocker" key={blocker.code}><span>{blocker.dependency}</span><p>{blocker.requiredAction}</p></div>)}
        </aside>

        <section className="task-cockpit-tasks" aria-labelledby="task-cockpit-tasks-title">
          <div className="task-cockpit-tasks-header">
            <div className="task-cockpit-section-heading"><h2 id="task-cockpit-tasks-title">当日任务流 · 执行进度</h2><span>{response.page.count} 项（当前页）</span></div>
          </div>
          {response.items.length === 0 ? <p className="task-cockpit-empty" role="status">当前权威 Task 集合为空；没有使用示例任务填充。</p> : null}
          {response.items.map((task) => {
          const detailId = `task-cockpit-run-${task.run?.runId ?? task.taskId}`;
          const isOpen = Boolean(task.run && detail?.runId === task.run.runId);
          return <article className={`task-cockpit-card is-${task.status}`} key={task.taskId}>
            <div className="task-cockpit-card-heading"><div><p>{task.taskType} · {task.taskId}</p><h3>{task.title}</h3></div><span>{task.status}</span></div>
            <div className="task-cockpit-progress" aria-label={`优先级 ${task.priority}`}><span style={{ width: `${Math.max(4, Math.min(100, task.priority))}%` }} /></div>
            <dl><div><dt>优先级</dt><dd>{task.priority}</dd></div><div><dt>Task 版本</dt><dd>v{task.version}</dd></div><div><dt>最近更新</dt><dd>{formatTime(task.updatedAt)}</dd></div><div><dt>Run</dt><dd>{task.run ? `${task.run.status} · v${task.run.version}` : "尚无 Run"}</dd></div></dl>
            {task.run ? <button type="button" aria-expanded={isOpen} aria-controls={detailId} onClick={() => toggleDetails(task.taskId, task.run!.runId)}>{isOpen ? "收起运行明细" : "查看运行明细"}</button> : null}
            {isOpen ? <div id={detailId} className="task-cockpit-run-detail">
              {detail?.phase === "loading" ? <div role="status">正在读取 Stage、职责交接、审批复核、Step 与 Checkpoint…</div> : null}
              {detail?.phase === "failed" ? <div role="alert">运行明细读取失败；未使用空集合代替。</div> : null}
              {detail?.skillContributions.phase === "loading" ? <section className="task-cockpit-skill-contributions is-loading" aria-label="本 Run 的专业 Skill 贡献"><strong>正在独立读取专业 Skill 贡献…</strong><p>该读取不阻塞原有运行明细。</p></section> : null}
              {detail?.skillContributions.phase === "failed" ? <section className="task-cockpit-skill-contributions is-failed" aria-label="本 Run 的专业 Skill 贡献" role="alert"><strong>专业 Skill 贡献读取失败</strong><p>原有 Stage、职责、审批、回执、Step 与 Checkpoint 保持可用；未用空集合掩盖失败。</p></section> : null}
              {detail?.skillContributions.phase === "ready" && detail.skillContributions.response ? <section className={`task-cockpit-skill-contributions is-${detail.skillContributions.response.projectionStatus}`} aria-label="本 Run 的专业 Skill 贡献">
                <div className="task-cockpit-production-refs"><strong>专业 Skill 贡献 · 只读</strong><span>{detail.skillContributions.response.items.length} 项 canonical AgentRun</span><span>评估于 {formatTime(detail.skillContributions.response.evaluatedAt)}</span></div>
                {detail.skillContributions.response.blockerCodes.length ? <p className="task-cockpit-approval-boundary">失败关闭：{detail.skillContributions.response.blockerCodes.join("、")}</p> : null}
                {detail.skillContributions.response.items.length ? <ul>{detail.skillContributions.response.items.map((contribution) => <li className={`is-${contribution.readiness.status}`} key={contribution.contributionId}>
                  <div><strong>{contribution.displayName}</strong><span>{contribution.runProjection.status} · {contribution.readiness.status}/{contribution.readiness.freshness}</span></div>
                  <p>{contribution.purpose}</p>
                  <small>角色 {contribution.roleRef.resourceId} · 实例 {contribution.assigneeRef.resourceId} · Skill {contribution.skillRevisionRef.resourceId}@{contribution.skillRevisionRef.revision}</small>
                  <small>Logic {contribution.logicRevisionRef.resourceId}@{contribution.logicRevisionRef.revision} · Binding {contribution.bindingRef.resourceId}@{contribution.bindingRef.revision ?? "未版本化"}</small>
                  <small>输入 {contribution.inputRefs.length} · 输出产物 {contribution.outputArtifactRefs.length} · 允许命令 {contribution.allowedCommands.length}</small>
                  {contribution.readiness.reasonCodes.length ? <em>等待：{contribution.readiness.reasonCodes.join("、")}</em> : <em>Binding 新鲜有效；仍仅展示贡献，不开放命令。</em>}
                </li>)}</ul> : <p>当前 Run 无 canonical AgentRun 贡献；没有制造六数字同事或示例 Skill。</p>}
              </section> : null}
              {detail?.phase === "ready" && detail.steps && detail.checkpoints && detail.productionContext && detail.responsibilityHandoffs && detail.approvalReview && detail.actionReceipts ? <>
                <section className="task-cockpit-production-context" aria-label="本 Run 的精确 Stage 编排">
                  <div className="task-cockpit-production-refs"><strong>Stage 编排 · {detail.productionContext.compilerVersion}</strong><span>Plan {detail.productionContext.planRef.resourceId} · v{detail.productionContext.planRef.revision}</span><span>模板 {detail.productionContext.stageTemplateRef.resourceId} · 职责 {detail.productionContext.responsibilityPlanRef.resourceId}</span></div>
                  <ol>{detail.productionContext.stages.map((stage) => <li className={`is-${stage.applicabilityResult}`} key={stage.stageId}><div><strong>{stage.title}</strong><span>{stage.stageId}</span></div><span>{stage.applicabilityResult === "applicable" ? "适用" : "不适用"}</span><small>依赖：{stage.dependsOn.length ? stage.dependsOn.join("、") : "无"} · 必需槽位：{stage.requiredSlotIds.length ? stage.requiredSlotIds.join("、") : "无"}</small></li>)}</ol>
                </section>
                <section className="task-cockpit-approval-review" aria-label="本 Run 的审批与 ReviewIssue 证据">
                  <div className="task-cockpit-production-refs"><strong>审批与复核</strong><span>Plan {detail.approvalReview.planApproval.approvalStatus} · v{detail.approvalReview.planApproval.planRef.revision}</span><span>{detail.approvalReview.actionApprovalCount} 个 Action Proposal · {detail.approvalReview.reviewIssueCount} 个 ReviewIssue</span></div>
                  <p className="task-cockpit-approval-boundary">打开不等于批准；批准不等于应用。这里只提供只读定位，目的页仍须重新鉴权。</p>
                  <div className="task-cockpit-approval-review-grid">
                    <div><h4>Action 审批证据</h4>{detail.approvalReview.actionApprovals.length ? <ul>{detail.approvalReview.actionApprovals.map((approval) => <li key={approval.proposalRef.resourceId}><strong>{approval.actionTypeId}</strong><span>{approval.proposalRef.resourceId} · v{approval.proposalRef.revision} · {approval.status}</span><small>{approval.decisions.length ? approval.decisions.map((decision) => `${decision.decision} · ${decision.actorId}`).join(" → ") : "尚无 canonical ApprovalEvent"}</small><em>{approval.navigation.commandReadiness === "destination_reauthorization_required" ? "目的页重新鉴权" : "只读事实"}</em></li>)}</ul> : <p>当前 Run 无 canonical Action Proposal。</p>}</div>
                    <div><h4>ReviewIssue 归因</h4>{detail.approvalReview.reviewIssues.length ? <ul>{detail.approvalReview.reviewIssues.map((issue) => <li key={issue.issueId}><strong>{issue.severity} · {issue.status}</strong><span>{issue.issueId} · v{issue.version} · {issue.returnStage}</span><small>{issue.artifactId} · evidence {issue.evidenceCount} · {issue.events.map((event) => `${event.sequence}:${event.eventType}${event.payloadReadiness === "exact" ? "(可回读)" : "(历史不可回读)"}`).join(" → ")}</small><em>{issue.lineageReadiness === "attempt_exact" && issue.returnLineage ? `${issue.returnLineage.stepRunId} · attempt ${issue.returnLineage.attempt} · ${issue.returnLineage.impactReadiness === "exact" ? issue.returnLineage.impactDecisions.map((item) => `${item.stepKey}:${item.action}`).join(" / ") : "历史影响范围不可回读"}` : "attempt 未解析；保持失败关闭"}</em></li>)}</ul> : <p>当前 Run 无 canonical ReviewIssue。</p>}</div>
                  </div>
                </section>
                <section className={`task-cockpit-dispatch-control is-${detail.dispatchObservation.phase}`} aria-label="派发意图 优先级与审批导航控制面">
                  <div className="task-cockpit-production-refs"><strong>派发、优先级与审批导航 · canonical 只读</strong><span>{detail.dispatchObservation.phase === "ready" && detail.dispatchObservation.response ? `${detail.dispatchObservation.response.dispatchIntents.length} 个 Intent · ${detail.dispatchObservation.response.priorityDecisions.length} 个 Priority Decision` : "独立 authority 未就绪"}</span><span>审批打开不等于批准；确认不等于下游命令已执行</span></div>
                  {detail.dispatchObservation.phase === "loading" ? <p>正在读取独立 Dispatch authority；不以空集合代替。</p> : null}
                  {detail.dispatchObservation.phase === "failed" ? <p role="alert">Dispatch authority 读取失败；派发与改优先级按钮保持禁用。</p> : null}
                  {detail.dispatchObservation.phase === "ready" && detail.dispatchObservation.response ? <>
                    <dl><div><dt>当前 Task exact version</dt><dd>v{detail.dispatchObservation.response.taskRef.version}</dd></div><div><dt>已确认 Intent</dt><dd>{detail.dispatchObservation.response.confirmations.length}</dd></div><div><dt>最新业务优先级决定</dt><dd>{detail.dispatchObservation.response.priorityDecisions.length ? `${detail.dispatchObservation.response.priorityDecisions[detail.dispatchObservation.response.priorityDecisions.length - 1].oldPriority} → ${detail.dispatchObservation.response.priorityDecisions[detail.dispatchObservation.response.priorityDecisions.length - 1].newPriority}` : "无"}</dd></div><div><dt>审批目的页</dt><dd>{detail.approvalReview.planApproval.navigation.commandReadiness === "destination_reauthorization_required" ? "需目的页重新鉴权" : "只读定位"}</dd></div></dl>
                    {detail.dispatchObservation.response.dispatchIntents.length ? <ul>{detail.dispatchObservation.response.dispatchIntents.map((intent) => <li className={`is-${intent.readiness}`} key={intent.intentId}><strong>{intent.command.commandKind}</strong><span>{intent.sourceIdentity} → {intent.targetIdentity}</span><small>{intent.intentId} · r{intent.revision} · {intent.reasonCode}</small><em>{intent.readiness === "ready" ? "建议已冻结；确认后仍须调用 canonical command 并回读 Receipt" : `阻断：${intent.blockers.map((blocker) => blocker.code).join("、")}`}</em></li>)}</ul> : <p>当前 Task 无 immutable DispatchIntent；没有从页面状态推导派发成功。</p>}
                    <div className="task-cockpit-assignment-actions"><button type="button" disabled>新建派发建议</button><small>本页只消费 canonical Intent；创建需完整 exact refs、权限与 policy。</small><button type="button" disabled>调整业务优先级</button><small>禁止用拖拽或个人排序偏好直接修改 Task priority。</small></div>
                  </> : null}
                </section>
                <section className="task-cockpit-action-receipts" aria-label="本 Run 的 Action 回执与对账证据">
                  <div className="task-cockpit-production-refs"><strong>Action 回执与对账</strong><span>{detail.actionReceipts.proposalCount} 个 Proposal · {detail.actionReceipts.receiptCount} 个 Receipt</span><span>{detail.actionReceipts.reconcileRequiredCount} 个 unknown 待对账 · {detail.actionReceipts.reconciledReceiptCount} 个已追加对账回执</span></div>
                  <p className="task-cockpit-approval-boundary">unknown 不等于失败；禁止重复执行。只有新的 immutable reconcile Receipt 才能关闭待对账状态。</p>
                  {detail.actionReceipts.executions.length ? <ul>{detail.actionReceipts.executions.map((execution) => <li className={`is-${execution.reconciliationState}`} key={execution.proposalRef.resourceId}><strong>{execution.actionTypeId}</strong><span>{execution.proposalRef.resourceId} · v{execution.proposalRef.revision} · {execution.proposalStatus}</span><small>{execution.leaseId ? `attempt ${execution.attempt} · ${execution.receipts.length} 条回执` : "尚无 ExecutionLease/Receipt"}</small><em>{execution.reconciliationState === "required" ? "unknown：仅允许授权 provider 回读对账" : execution.reconciliationState === "resolved" ? `已对账：${execution.receipts.find((receipt) => receipt.receiptKind === "reconcile")?.resolvedStatus ?? "terminal"}` : execution.reconciliationState === "not_required" ? "回执已明确，无需对账" : "尚未执行"}</em>{execution.receipts.length ? <ol>{execution.receipts.map((receipt) => <li key={receipt.receiptId}><span>{receipt.receiptKind} · {receipt.status}</span><small>{receipt.providerRequestPresent ? "provider request ref 已封存" : "provider request ref 缺失"} · evidence {receipt.evidenceCount}</small></li>)}</ol> : null}</li>)}</ul> : <p>当前 Run 无 canonical Action Receipt；没有用示例回执填充。</p>}
                </section>
                <section className="task-cockpit-responsibility" aria-label="本 Run 的精确职责与交接">
                  <div className="task-cockpit-production-refs"><strong>职责与交接 · {detail.responsibilityHandoffs.profile}</strong><span>{detail.responsibilityHandoffs.responsibilityPlanRef.resourceId} · v{detail.responsibilityHandoffs.responsibilityPlanRef.revision}</span><span>编译时就绪；运行就绪需独立验证</span></div>
                  <div className="task-cockpit-responsibility-grid">
                    <div><h4>职责槽位</h4><p className="task-cockpit-approval-boundary">只认带 snapshot hash 且在 evaluatedAt 前未过期的 exact Receipt；历史 Receipt 仅兼容可读，不代表 ready。</p><ul>{detail.responsibilityHandoffs.slots.map((slot) => {
                      const latestReceipt = slot.assignee.resolutionReceipts[slot.assignee.resolutionReceipts.length - 1];
                      const readinessLabel = slot.assignee.operationalReadiness === "resolved_at_observation" ? "观测时已解析" : slot.assignee.operationalReadiness === "blocked_at_observation" ? "观测时阻断" : "未验证";
                      return <li className={`is-${slot.assignee.operationalReadiness}`} key={slot.slotId}><strong>{slot.responsibilityType}</strong><span>{slot.slotId} → {slot.assignee.resourceId} · v{slot.assignee.version}</span><small>所需能力：{slot.requiredCapabilityIds.join("、")} · 返回阶段：{slot.returnStage}</small><em>{readinessLabel}{latestReceipt ? ` · ${formatTime(latestReceipt.createdAt)} · ${latestReceipt.snapshotStatus}` : " · 无 exact Receipt"}</em>{latestReceipt?.snapshotHash ? <small>snapshot {latestReceipt.snapshotHash.slice(0, 12)}… · {latestReceipt.requiredCapabilityCount} 能力 / {latestReceipt.bindingCount} 绑定 · 有效至 {latestReceipt.expiresAt ? formatTime(latestReceipt.expiresAt) : "未知"}</small> : latestReceipt ? <small>legacy/unverified：缺少精确快照或有效期。</small> : null}{latestReceipt?.blockerCodes.length ? <small>阻断：{latestReceipt.blockerCodes.join("、")}</small> : null}</li>;
                    })}</ul></div>
                    <div><h4>交接决定链</h4>{detail.responsibilityHandoffs.handoffs.length ? <ul>{detail.responsibilityHandoffs.handoffs.map((handoff) => <li key={handoff.handoffId}><strong>{handoff.senderInstanceRef.resourceId} → {handoff.receiverInstanceRef.resourceId}</strong><span>{handoff.handoffId} · {handoff.status} · v{handoff.version}</span><small>{handoff.decisions.length ? handoff.decisions.map((decision) => `r${decision.revision} ${decision.decision}`).join(" → ") : "尚无业务决定；consumed 不等于 accepted"}</small></li>)}</ul> : <p>当前 Run 无 canonical Handoff；未使用示例交接填充。</p>}</div>
                  </div>
                  <div className={`task-cockpit-assignment-control is-${detail.assignmentObservation.phase}`} aria-label="职责覆盖 Readiness 改派与人工接管四轴">
                    <h4>职责控制四轴</h4>
                    <dl>
                      <div><dt>结构覆盖</dt><dd>{detail.responsibilityHandoffs.compiledRequiredSlotIds.length} / {detail.responsibilityHandoffs.compiledRequiredSlotIds.length} 必需槽位已覆盖</dd></div>
                      <div><dt>当前可执行</dt><dd>{detail.responsibilityHandoffs.slots.every((slot) => slot.assignee.operationalReadiness === "resolved_at_observation") ? "仅观测时已解析；当前时刻仍须重验" : "未证实；保持失败关闭"}</dd></div>
                      <div><dt>启动前改派</dt><dd>TaskRun 已存在；禁止改写 frozen Plan，必须使用运行中接管</dd></div>
                      <div><dt>运行中接管</dt><dd>{detail.assignmentObservation.phase === "ready" && detail.assignmentObservation.response ? `${detail.assignmentObservation.response.takeoverRequests.length} 个请求 · ${detail.assignmentObservation.response.takeoverDecisions.length} 个决定 · ${detail.assignmentObservation.response.assignmentLeases.length} 个当前 Lease` : detail.assignmentObservation.phase === "loading" ? "正在读取独立 authority" : "独立 authority 不可用；不解释为空"}</dd></div>
                    </dl>
                    {detail.assignmentObservation.phase === "ready" && detail.assignmentObservation.response?.takeoverRequests.some((request) => request.safetyState === "provider_outcome_unknown") ? <p role="alert">Provider outcome unknown：必须先追加对账证据，禁止接管或重放。</p> : null}
                    <div className="task-cockpit-assignment-actions"><button type="button" disabled aria-describedby={`reassign-blocker-${task.taskId}`}>生成改派后继</button><small id={`reassign-blocker-${task.taskId}`}>TASK_RUN_EXISTS_USE_TAKEOVER：当前 Run 已存在。</small><button type="button" disabled aria-describedby={`takeover-blocker-${task.taskId}`}>申请人工接管</button><small id={`takeover-blocker-${task.taskId}`}>命令入口尚未取得 exact Step、Resolution Receipt、maker-checker 与安全点重验，不执行副作用。</small></div>
                  </div>
                  <ModuleHandoffCommandPanel task={task} run={task.run!} responsibility={detail.responsibilityHandoffs} workshopClient={client} commandClient={handoffClient} onRefresh={() => toggleDetails(task.taskId, task.run!.runId)} />
                </section>
                <table><caption>Step 执行权（{detail.steps.page.count} 项，当前页）</caption><thead><tr><th scope="col">步骤</th><th scope="col">尝试 / fence</th><th scope="col">状态 / 安全点</th><th scope="col">Owner / Lease / 对账</th></tr></thead><tbody>{detail.steps.items.length ? detail.steps.items.map((step) => <tr key={step.stepRunId}><th scope="row">{step.stepKey}</th><td>{step.attempt} / {step.fence ?? "未建立"}</td><td>{step.status} / {step.safePoint ? "已到安全点" : "未到安全点"}</td><td>{step.leaseOwner ?? "未建立 owner"} / {step.assignmentLeaseId ?? "未建立 lease"} / {step.reconcileRequired ? "必须对账，禁止重放" : "无需对账"}</td></tr>) : <tr><td colSpan={4}>当前权威 Step 集合为空</td></tr>}</tbody></table>
                <table><caption>Checkpoint 恢复事实（{detail.checkpoints.page.count} 项，当前页）</caption><thead><tr><th scope="col">序号</th><th scope="col">步骤 / attempt</th><th scope="col">状态哈希</th><th scope="col">恢复判定基础</th></tr></thead><tbody>{detail.checkpoints.items.length ? detail.checkpoints.items.map((checkpoint) => <tr key={checkpoint.checkpointId}><th scope="row">{checkpoint.sequence}</th><td>{checkpoint.stepKey ?? "未绑定步骤"} / {checkpoint.attempt ?? "历史未知"}</td><td>{checkpoint.stateHash}</td><td>{checkpoint.resumeReadiness === "checkpoint_exact" ? "exact input / dependency / provider fingerprint 已封存" : "历史断点未完整封存；恢复失败关闭"}</td></tr>) : <tr><td colSpan={4}>当前权威 Checkpoint 集合为空</td></tr>}</tbody></table>
                {detail.steps.page.hasMore || detail.checkpoints.page.hasMore ? <p role="status">运行明细仍有后续页；本子波不截断冒充完整集合。</p> : null}
              </> : null}
            </div> : null}
          </article>;
        })}
        {response.page.hasMore && response.page.nextCursor ? <button type="button" onClick={() => load(status, response.page.nextCursor ?? undefined)}>读取下一页</button> : null}
        </section>

        <aside className="task-cockpit-role-lane" aria-labelledby="task-cockpit-planning-title">
          <h2 id="task-cockpit-planning-title">策划组</h2>
          <div className="task-cockpit-lane-state">
            <span aria-hidden="true">◇</span>
            <strong>Stage 按 Run 精确展开</strong>
            <p>仅在 Run 携带 canonical productionContract 时展示；业务上下文见独立 SourceReadiness 快照，不与 Task cutoff 混算。</p>
          </div>
          {planningBlockers.map((blocker) => <div className="task-cockpit-lane-blocker" key={blocker.code}><span>{blocker.dependency}</span><p>{blocker.requiredAction}</p></div>)}
        </aside>

        <aside className="task-cockpit-review" aria-labelledby="task-cockpit-review-title">
          <div className="task-cockpit-section-heading"><h2 id="task-cockpit-review-title">复盘 · 权威缺口</h2><span>{response.blockers.length} 项</span></div>
          <p>没有用静态复盘示例代替真实 EffectReview；以下内容逐项来自当前响应。</p>
          <ul>{response.blockers.map((blocker) => <li className={`is-${blocker.severity}`} key={blocker.code}><strong>{blocker.code}</strong><span>{blocker.severity} · {blocker.dependency}</span><p>{blocker.requiredAction}</p></li>)}</ul>
        </aside>
      </div>

      <section className="task-cockpit-capabilities" aria-labelledby="task-cockpit-capabilities-title">
        <h2 id="task-cockpit-capabilities-title">共享能力 · 待接入</h2>
        <div>{dependencyTags.map((dependency) => <span key={dependency}>{dependency}</span>)}</div>
        <p>这里只展示 blocker dependency，不声明 Agent、Binding 或 Capability 可运行。</p>
      </section>
    </div>;
  })() : null;

  return <section className="task-cockpit-page" aria-label="日常任务总控只读视图">
    <TaskCockpitVisualSurface response={response} analystSuggestions={analystSuggestions} phase={phase} status={status} onStatusChange={(next) => { setStatus(next); load(next); }} onReload={() => load(status, undefined, Boolean(response))} onCreateTask={createInternalTask} />
    <details className="task-cockpit-audit-context">
      <summary><span>运行、发布与审计上下文</span><small>保持原完整功能；默认收起以恢复视觉稿首屏结构</small></summary>
      <div>
        <WorkshopOperatingReadinessCard />
        <WorkshopDisasterRecoveryCard />
        <WorkshopCumulativeReleaseGateCard />
        <WorkshopOperationalReleaseDecisionCard />
        <AsyncStateBoundary state={stateFor(phase)} dataCutoff={response?.taskCutoff} title={phase === "stale" ? "游标或当前快照已变化" : undefined} description={phase === "stale" ? "保留已标记内容；请重新读取首屏，不会自动重放旧游标。" : undefined} action={phase === "stale" || phase === "failed" ? <button type="button" onClick={() => load(status)}>重新读取首屏</button> : undefined}>{content}</AsyncStateBoundary>
      </div>
    </details>
  </section>;
}
