import { useEffect, useRef, useState } from "react";

import { EcommerceWorkshopClientError, ecommerceWorkshopClient, type AnalystViewId, type AnalystViewResponse, type AnalystViewSlice, type LearningScenarioContribution } from "../../api/ecommerceWorkshop";
import type { InvestigationReadClient } from "../../api/ecommerceInvestigation";
import { AsyncStateBoundary, type AsyncState } from "./AsyncStateBoundary";
import { AsyncJobDrawer, type AsyncJobLoader } from "./AsyncJobDrawer";
import { BusinessInvestigationTab } from "./BusinessInvestigationTab";
import {
  isBusinessInvestigationCommandEnabled,
  isBusinessInvestigationReadEnabled,
  resolveBusinessInvestigationFeatureFlags,
  type BusinessInvestigationFeatureFlags,
} from "./businessInvestigationFeatureFlags";
import { ContributionLineage } from "./production";

type Client = Pick<typeof ecommerceWorkshopClient, "getAnalystView"> & Partial<Pick<typeof ecommerceWorkshopClient, "getAnalystLearningScenario">>;
type Phase = "loading" | "ready" | "empty" | "forbidden" | "failed";
type LearningScenarioState = { phase: "idle" | "loading" | "ready" | "failed"; response: LearningScenarioContribution | null };
type AnalystTabId = "investigation" | AnalystViewId;
const LABELS: Record<AnalystViewId, string> = { overview: "经营总览", drivers: "驱动因素", diagnosis: "问题诊断", plan: "增长计划", effects: "效果复盘", evidence: "证据链", quality: "数据质量" };
const CONTRIBUTIONS: Record<AnalystViewId, string> = {
  overview: "汇总同一截止面的经营指标与 authority readiness",
  drivers: "以显式 observation/correlation/attribution 边界解释驱动因素",
  diagnosis: "组合 DecisionSummary 的证据链、归因路径与不确定性",
  plan: "消费 approved exact GrowthPlanRevision；不在页面物化 Task",
  effects: "读取成熟度受控的 EffectReview；unknown 不显示为 0",
  evidence: "串联 exact metric、evidence、method 与 eval refs",
  quality: "披露分母、缺失、冲突、cutoff 与失败关闭原因",
};
const SCENARIO_LABELS = { insight: "洞察", growth_plan: "GrowthPlan", content: "内容", creator: "达人", media: "媒体", publication: "发布", effect_review: "效果复盘", memory_candidate: "记忆候选" } as const;
const LEARNING_STAGE_LABELS = { effect_review: "效果复盘", maturity: "成熟度", memory_candidate: "记忆候选", governance: "治理审查", promotion: "知识晋升", knowledge_query: "查询复验", revocation_impact: "撤销影响" } as const;
const stateFor = (phase: Phase): AsyncState => phase === "ready" || phase === "empty" ? "ready" : phase;

const AXIS_LABELS = { metric_query: "指标读取", model: "分析模型", eval: "评价校验", plan_materialization: "计划物化", professional_handoff: "专业 Handoff" } as const;
const VIEW_SLOTS: Record<AnalystViewId, readonly string[]> = {
  overview: ["核心经营指标", "订单与客户指标", "转化与质量指标"],
  drivers: ["渠道贡献", "内容与活动贡献", "商品与履约贡献"],
  diagnosis: ["指标对比", "异常检测", "归因分析"],
  plan: ["目标树", "策略行动", "预算与停止条件"],
  effects: ["有效结果", "待补证结果", "风险结果"],
  evidence: ["指标证据", "模型证据", "评价证据"],
  quality: ["分母完整性", "新鲜度", "冲突与对账"],
};

function metricValue(view: AnalystViewSlice, index: number) {
  const metric = view.metrics[index];
  return {
    label: metric?.metricId ?? VIEW_SLOTS[view.viewId][index] ?? `指标槽位 ${index + 1}`,
    value: metric?.status === "ready" && metric.value !== null ? `${metric.value}${metric.unit ? ` ${metric.unit}` : ""}` : "未知",
    status: metric?.status ?? "blocked",
    note: metric?.status === "ready" ? `${metric.window ?? "窗口未知"} · ${metric.grain ?? "粒度未知"}` : "等待同截止面 exact authority",
  };
}

function AnalystExactTechnicalDetails({ view }: { view: AnalystViewSlice }) {
  return <details className="analyst-exact-technical-details">
    <summary>证据、归因与安全边界</summary>
    <div className="analyst-readiness-grid">{view.readinessAxes.map((axis) => <article key={axis.axis} className={`is-${axis.status}`}><strong>{axis.axis}</strong><span>{axis.status}</span><p>{axis.exactRef ? `${axis.exactRef.resourceType} · r${axis.exactRef.revision}` : "无 exact authority"}</p></article>)}</div>
    <section className="analyst-metrics">{view.metrics.length ? view.metrics.map((metric) => <article key={metric.metricId} className={`is-${metric.status}`}><header><strong>{metric.metricId}</strong><span>{metric.status}</span></header>{metric.status === "ready" ? <><b>{metric.value} {metric.unit}</b><p>{metric.grain} · {metric.window} · {metric.timezone}</p><small>denominator {metric.denominator} · lineage {metric.lineageId}</small></> : <p>当前值未知，不以 0 代替。</p>}</article>) : <p>当前没有可挂接的经营指标；可信空与 blocked/unknown 分开表达。</p>}</section>
    <aside className="media-studio-blockers"><h3>阻断与下一证据</h3>{view.blockers.length ? view.blockers.map((item) => <div key={item.code}><strong>{item.code}</strong><span>{item.dependency}</span><p>{item.requiredAction}</p></div>) : <p>本视图当前无 blocker。</p>}<section><h3>专业贡献归因</h3><ContributionLineage value={{ atomicSkillRef: null, logicRef: null, coworker: null, workshopContribution: CONTRIBUTIONS[view.viewId] }} /><p>当前只读 View 没有 exact AgentRun、SkillBinding 或 LogicRevision；保持 unknown，不把 Analyst authority 冒充数字同事运行事实。</p></section><section><h3>决策摘要</h3><p>{view.status === "ready" ? "当前 exact refs 与同截止面指标可读。" : "依赖 authority 不完整，本视图失败关闭。"}</p></section><section><h3>关键假设和不确定性</h3><p>相关不等于归因，归因不等于因果；页面不展示模型私有思维链，也不授权计划物化或业务动作。</p></section></aside>
  </details>;
}

function AnalystExactView({ view, selected }: { view: AnalystViewSlice; selected: AnalystViewId }) {
  const metrics = [0, 1, 2].map((index) => metricValue(view, index));
  const blockers = view.blockers.length ? view.blockers : [{ code: "CURRENTLY_CLEAR", dependency: "当前截止面", requiredAction: "保持只读回读" }];
  const common = <AnalystExactTechnicalDetails view={view} />;
  const panelProps = { id: `analyst-panel-${selected}`, "aria-labelledby": `analyst-tab-${selected}`, className: `analyst-panel analyst-exact-panel is-${view.viewId}`, role: "tabpanel" as const, "aria-label": LABELS[selected] };

  if (view.viewId === "overview") return <section {...panelProps}>
    <header className="analyst-exact-visually-hidden"><span>{view.viewId}</span><h2>{LABELS[view.viewId]}</h2></header>
    <section className="analyst-exact-cadence" aria-label="每日经营节奏">{[...view.readinessAxes, { axis: "same_cutoff" as const, status: view.status, exactRef: null }].map((axis, index) => <article className={`is-${axis.status}`} key={axis.axis}><span>{index + 1}</span><strong>{axis.axis === "same_cutoff" ? "同截止面复核" : AXIS_LABELS[axis.axis]}</strong><small>{axis.status === "ready" ? "已回读" : "待补证"}</small></article>)}</section>
    <div className="analyst-exact-overview-grid"><article><header><strong>当前经营摘要</strong><span className={`is-${view.status}`}>{view.status}</span></header><dl><div><dt>可信指标</dt><dd>{view.countLedger.ready}/{view.countLedger.denominator}</dd></div><div><dt>未知与阻断</dt><dd>{view.countLedger.unknown + view.countLedger.blocked}</dd></div><div><dt>资源 revision</dt><dd>r{view.resourceRevision}</dd></div><div><dt>业务写入</dt><dd>0</dd></div></dl><p>{view.status === "ready" ? "同一截止面的经营指标与 authority 可读。" : "exact authority 尚未闭合，经营结论保持失败关闭。"}</p></article><aside><header><strong>待补证 / 待关注</strong><span>{view.blockers.length}</span></header>{blockers.slice(0, 3).map((item) => <div key={item.code}><strong>{item.code}</strong><p>{item.requiredAction}</p></div>)}</aside></div>
    <section className="analyst-exact-coworkers" aria-label="数字同事只读协作状态">{["数据参谋", "经营参谋", "专业工作台"].map((label, index) => <article key={label}><span>{index + 1}</span><div><strong>{label}</strong><p>{index === 0 ? "指标与证据读取" : index === 1 ? "决策摘要与归因边界" : "未授权 Handoff"}</p></div><small>{view.status === "ready" ? "只读" : "等待"}</small></article>)}</section>{common}
  </section>;

  if (view.viewId === "drivers") return <section {...panelProps}>
    <header className="analyst-exact-visually-hidden"><h2>{LABELS[view.viewId]}</h2></header><section className="analyst-exact-driver-cards">{metrics.map((metric) => <article className={`is-${metric.status}`} key={metric.label}><span>{metric.label}</span><strong>{metric.value}</strong><small>{metric.note}</small><div className="analyst-exact-empty-chart">等待 observation</div></article>)}</section><div className="analyst-exact-driver-lower"><article><header><strong>驱动贡献分布</strong><span>同截止面</span></header>{VIEW_SLOTS.drivers.map((slot, index) => <div key={slot}><span>{slot}</span><strong>{metricValue(view, index).value}</strong><small>{metricValue(view, index).status}</small></div>)}</article><aside><header><strong>实时经营事件流</strong><span>只读</span></header><div className="analyst-exact-trusted-empty"><strong>当前没有可回链事件</strong><p>没有 exact observation 时不生成趋势、归因或因果结论。</p></div></aside></div>{common}
  </section>;

  if (view.viewId === "diagnosis") return <section {...panelProps}>
    <header className="analyst-exact-visually-hidden"><h2>{LABELS[view.viewId]}</h2></header><nav className="analyst-exact-subtabs" aria-label="问题诊断分视图"><span className="is-active">指标对比</span><span>异常检测</span><span>归因分析</span><span>AI 洞察</span></nav><article className="analyst-exact-diagnosis-table"><header><strong>指标深度对比 · 环比 / 同比 / 目标达成</strong><span>数据钻取只读</span></header><table><thead><tr><th>指标</th><th>当前值</th><th>对照</th><th>环比</th><th>同比</th><th>目标达成</th></tr></thead><tbody>{[...metrics, ...view.readinessAxes.slice(0, 3).map((axis) => ({ label: AXIS_LABELS[axis.axis], value: "未知", status: axis.status, note: "等待 exact authority" }))].map((metric) => <tr key={metric.label}><th>{metric.label}</th><td>{metric.value}</td><td>未知</td><td>{metric.status}</td><td>未知</td><td>待验证</td></tr>)}</tbody></table></article><div className="analyst-exact-diagnosis-lower"><article><header><strong>来源 × 指标覆盖</strong><span>只读</span></header><p>当前没有可安全展示的来源分布；分母、缺失和冲突保持显式。</p></article><aside><header><strong>异常与证据热区</strong><span>{view.blockers.length} blocker</span></header><p>{blockers[0]?.requiredAction}</p></aside></div>{common}
  </section>;

  if (view.viewId === "plan") return <section {...panelProps}>
    <header className="analyst-exact-visually-hidden"><h2>{LABELS[view.viewId]}</h2></header><div className="analyst-exact-plan-grid"><article><header><strong>GrowthPlan · exact revision 待回读</strong><span className={`is-${view.status}`}>{view.status}</span></header><div className="analyst-exact-lifecycle">{["DRAFT", "PENDING", "APPROVED", "RUNNING", "REVIEWED"].map((state) => <span key={state}>{state}</span>)}</div>{VIEW_SLOTS.plan.map((slot, index) => <section key={slot}><strong>{slot}</strong><p>{metrics[index]?.note}；当前不在页面物化 Task 或执行 Handoff。</p></section>)}</article><aside><section><header><strong>审批与精确绑定</strong><span>只读</span></header><dl><div><dt>revision</dt><dd>r{view.resourceRevision}</dd></div><div><dt>authority refs</dt><dd>{view.authorityRefs.length}</dd></div><div><dt>materialize</dt><dd>关闭</dd></div><div><dt>external effect</dt><dd>0</dd></div></dl></section><section><header><strong>证据引用</strong><span>{view.authorityRefs.length}</span></header><p>{view.authorityRefs.length ? "exact refs 已回读；仍须遵守批准与 Lease。" : "尚无可回链 exact GrowthPlanRevision。"}</p></section><section className="is-warning"><header><strong>待评审 Proposal</strong><span>{view.blockers.length}</span></header><p>{blockers[0]?.requiredAction}</p></section></aside></div>{common}
  </section>;

  if (view.viewId === "effects") return <section {...panelProps}>
    <header className="analyst-exact-visually-hidden"><h2>{LABELS[view.viewId]}</h2></header><article className="analyst-exact-review-list"><header><strong>效果复盘 · EffectReview</strong><span>同截止面只读</span></header>{metrics.map((metric, index) => <section className={`is-${metric.status}`} key={metric.label}><header><strong>{VIEW_SLOTS.effects[index]}</strong><span>{metric.status}</span></header><p>归因方法：{metric.status === "ready" ? "按 exact method ref 回读" : "未知 · 不从相关性推导因果"}</p><p>结果：{metric.value} · {metric.note}</p><small>记忆候选：未授权自动晋升</small></section>)}</article><div className="analyst-exact-review-lower"><article><header><strong>四层经验候选</strong><span>只读</span></header><p>事实、判断、规则与程序记忆分层治理；当前不生成候选事实。</p></article><aside><header><strong>记忆候选 · 审批队列</strong><span>{view.blockers.length}</span></header><p>{blockers[0]?.requiredAction}</p></aside></div>{common}
  </section>;

  if (view.viewId === "evidence") return <section {...panelProps}>
    <header className="analyst-exact-visually-hidden"><h2>{LABELS[view.viewId]}</h2></header><article className="analyst-exact-evidence-map"><header><strong>Evidence DAG · exact 引用依赖</strong><span>最小必要上下文</span></header><div className="analyst-exact-evidence-root"><strong>DecisionSummary</strong><small>{view.status}</small></div><div className="analyst-exact-evidence-nodes">{[...view.readinessAxes.slice(0, 4)].map((axis) => <section className={`is-${axis.status}`} key={axis.axis}><strong>{AXIS_LABELS[axis.axis]}</strong><span>{axis.status}</span><small>{axis.exactRef ? `r${axis.exactRef.revision}` : "无 exact ref"}</small></section>)}</div><div className="analyst-exact-evidence-terminal"><strong>评价与复核</strong><small>{view.readinessAxes[2]?.status ?? "unknown"}</small></div></article><div className="analyst-exact-evidence-lower"><article><header><strong>Handoff 契约 · 上下文传递</strong><span>未授权</span></header><p>只传 exact revision 与最小必要上下文；专业工作台继续执行各自审批、权限、Lease 与 Receipt。</p></article><aside><header><strong>证据详情 · 阻断与优先级</strong><span>{view.blockers.length}</span></header>{blockers.slice(0, 3).map((item) => <p key={item.code}><strong>{item.code}</strong> · {item.requiredAction}</p>)}</aside></div>{common}
  </section>;

  return <section {...panelProps}>
    <header className="analyst-exact-visually-hidden"><h2>{LABELS[view.viewId]}</h2></header><div className="analyst-exact-quality-grid"><article><header><strong>增长护栏 · 数据质量门</strong><span>{view.status}</span></header>{view.readinessAxes.map((axis) => <div key={axis.axis}><span>{AXIS_LABELS[axis.axis]}</span><progress value={axis.status === "ready" ? 1 : 0} max={1} /><small>{axis.status}</small></div>)}</article><aside><header><strong>先行指标 · 同截止面巡检</strong><span>只读</span></header><div className="analyst-exact-quality-metrics">{metrics.slice(0, 2).map((metric) => <section key={metric.label}><span>{metric.label}</span><strong>{metric.value}</strong><small>{metric.status}</small></section>)}</div><p>未知不显示为 0；没有 exact quality ref 时保持失败关闭。</p></aside><article><header><strong>分母与新鲜度</strong><span>{view.countLedger.denominator}</span></header><dl><div><dt>ready</dt><dd>{view.countLedger.ready}</dd></div><div><dt>unknown</dt><dd>{view.countLedger.unknown}</dd></div><div><dt>blocked</dt><dd>{view.countLedger.blocked}</dd></div></dl></article><aside><header><strong>异常与阻断</strong><span>{view.blockers.length}</span></header>{blockers.slice(0, 3).map((item) => <p key={item.code}><strong>{item.code}</strong><br />{item.requiredAction}</p>)}</aside></div>{common}
  </section>;
}

export function AnalystPage({ client = ecommerceWorkshopClient, investigationClient, loadAsyncJobs, featureFlags = resolveBusinessInvestigationFeatureFlags() }: { client?: Client; investigationClient?: InvestigationReadClient; loadAsyncJobs?: AsyncJobLoader; featureFlags?: BusinessInvestigationFeatureFlags }) {
  const investigationEnabled = isBusinessInvestigationReadEnabled(featureFlags);
  const [phase, setPhase] = useState<Phase>("loading"); const [response, setResponse] = useState<AnalystViewResponse | null>(null); const [selected, setSelected] = useState<AnalystTabId>(investigationEnabled ? "investigation" : "overview"); const [learningScenario, setLearningScenario] = useState<LearningScenarioState>({ phase: "idle", response: null }); const request = useRef(0); const learningRequest = useRef(0);
  const load = () => { const id = ++request.current; setPhase("loading"); setResponse(null); const learningId = ++learningRequest.current; if (client.getAnalystLearningScenario) { setLearningScenario({ phase: "loading", response: null }); void client.getAnalystLearningScenario().then((next) => { if (learningId === learningRequest.current) setLearningScenario({ phase: "ready", response: next }); }, () => { if (learningId === learningRequest.current) setLearningScenario({ phase: "failed", response: null }); }); } else { setLearningScenario({ phase: "idle", response: null }); } void client.getAnalystView().then((next) => { if (id !== request.current) return; setResponse(next); setSelected(investigationEnabled ? "investigation" : next.views.find((item) => item.status === "blocked")?.viewId ?? "overview"); setPhase(next.page.count === 0 && next.views.every((item) => item.status === "ready") ? "empty" : "ready"); }, (error: unknown) => { if (id === request.current) setPhase(error instanceof EcommerceWorkshopClientError && (error.status === 401 || error.status === 403) ? "forbidden" : "failed"); }); };
  useEffect(() => { load(); return () => { request.current += 1; learningRequest.current += 1; }; }, [client, investigationEnabled]);
  const view = selected === "investigation" ? undefined : response?.views.find((item) => item.viewId === selected); const readyMetrics = response?.views.reduce((sum, item) => sum + item.countLedger.ready, 0) ?? 0; const totalMetrics = response?.views.reduce((sum, item) => sum + item.countLedger.denominator, 0) ?? 0;
  const content = response ? <div className="analyst-read-model">
    <details className="analyst-hero-context"><summary><span>经营参谋说明</span><small>只读 · 指标、证据与质量同截止面</small></summary><section className="analyst-hero"><div><span>经营参谋 · 增长指挥中心</span><h2>用同一截止面的指标、证据与质量理解经营变化</h2><p>Observation ≠ attribution ≠ causal claim；只展示决策摘要、证据链、归因路径、关键假设和不确定性。</p></div><strong>只读</strong></section></details>
    <details className="analyst-supplemental-context">
      <summary><span>跨域贡献与学习治理上下文</span><small>原子 Skill → Logic → 数字同事 → 工作台贡献</small></summary>
      <div className="analyst-supplemental-context-body">
    <section className="creator-growth-axis"><div><span>只读视图</span><strong>7</strong></div><div><span>可信指标</span><strong>{readyMetrics}/{totalMetrics}</strong></div><div><span>资源 revision</span><strong>r{response.resourceRevision}</strong></div><div><span>写入口</span><strong>0</strong></div></section>
    {response.growthScenario ? <section className="content-campaign-items" aria-label="GrowthPlan跨域同链贡献">
      <header><strong>洞察 → GrowthPlan → 内容 → 达人 → 媒体 → 发布 → 复盘</strong><span>{response.growthScenario.status}</span></header>
      <article className="content-campaign-item"><header><strong>{response.growthScenario.rootPlanRef?.resourceId ?? "等待 exact GrowthPlan 根"}</strong><span>{response.growthScenario.scenarioBindingHash ? `binding ${response.growthScenario.scenarioBindingHash.slice(0, 14)}…` : "binding 未建立"}</span></header>
        <p>原子 Skill → Logic 编排 → 数字同事绑定 → 工作台贡献；页面只消费 exact refs，不复制业务真源。</p>
        <div className="media-command-grid">{response.growthScenario.stages.map((stage) => <article className={`is-${stage.status}`} key={stage.stageId}><strong>{SCENARIO_LABELS[stage.stageId]}</strong><span>{stage.status}</span><small>{stage.contribution}</small></article>)}</div>
        <section className="content-campaign-ledger"><div><span>Task</span><strong>{response.growthScenario.ledger.tasksObserved}/{response.growthScenario.ledger.tasksExpected}</strong></div><div><span>Handoff</span><strong>{response.growthScenario.ledger.handoffsObserved}/{response.growthScenario.ledger.handoffsExpected}</strong></div><div><span>Outcome ready</span><strong>{response.growthScenario.ledger.outcomesReady}/{response.growthScenario.ledger.outcomesExpected}</strong></div><div><span>写入口</span><strong>0</strong></div></section>
        <div className="analyst-readiness-grid">{response.growthScenario.outcomeAxes.map((axis) => <article className={`is-${axis.status}`} key={axis.axisId}><strong>{axis.axisId}</strong><span>{axis.status}</span><p>{axis.exactRef ? `${axis.exactRef.resourceType} · r${axis.exactRef.revision}` : axis.blocker?.code}</p></article>)}</div>
        <small>Provider applied、Usage settled、Effect mature、Memory governed 四轴独立 · 外部副作用关闭 · 不自动晋升 Wiki</small>
      </article>
    </section> : null}
    {learningScenario.phase === "loading" ? <section className="analyst-learning-scenario is-loading" aria-label="W8-04 学习治理贡献" role="status"><strong>正在独立读取学习治理场景…</strong><p>不从页面本地状态推导成熟、批准、晋升或撤销结果。</p></section> : null}
    {learningScenario.phase === "failed" ? <section className="analyst-learning-scenario is-failed" aria-label="W8-04 学习治理贡献" role="alert"><strong>学习治理场景读取失败</strong><p>原有 Analyst v2 保持可用；Candidate、Wiki 与撤销命令均不开放。</p></section> : null}
    {learningScenario.phase === "ready" && learningScenario.response ? <section className="analyst-learning-scenario is-blocked" aria-label="W8-04 学习治理贡献">
      <header><div><span>W8-04 · GET-only</span><h2>EffectReview → MemoryCandidate → Wiki 治理与撤销</h2></div><strong>运营失败关闭</strong></header>
      <p>原子 Skill → Logic 编排 → 数字同事绑定 → 工作台贡献视图；成熟、治理批准、晋升、知识有效性、撤销影响五轴独立。</p>
      {learningScenario.response.composition ? <div className="analyst-learning-layers"><div><span>原子 Skill</span><strong>{learningScenario.response.composition.atomicSkillRefs.length}</strong><small>{learningScenario.response.composition.atomicSkillRefs.map((item) => `${item.resourceId}@${item.revision}`).join("、")}</small></div><div><span>Logic</span><strong>{learningScenario.response.composition.logicRevisionRef.resourceId}</strong><small>v{learningScenario.response.composition.logicRevisionRef.revision}</small></div><div><span>数字同事绑定</span><strong>{learningScenario.response.composition.roleBindings.length}</strong><small>{learningScenario.response.composition.roleBindings.map((item) => `${item.roleRef.resourceId} → ${item.assigneeRef.resourceId}`).join("、")}</small></div></div> : <p className="task-cockpit-approval-boundary">{learningScenario.response.blockers.map((item) => item.code).join("、")}；未制造 Skill、Logic、角色或知识事实。</p>}
      <ol className="analyst-learning-stages">{learningScenario.response.stages.map((stage) => <li className={`is-${stage.status}`} key={stage.stageId}><span>{LEARNING_STAGE_LABELS[stage.stageId]}</span><strong>{stage.status}</strong><p>{stage.contribution}</p><small>{stage.exactRefs.length ? `${stage.exactRefs.length} 个 exact ref` : stage.blockers.map((item) => item.code).join("、")}</small></li>)}</ol>
      <div className="analyst-learning-ledger" aria-label="治理与撤销守恒"><div><span>EffectReview</span><strong>{learningScenario.response.ledger.reviewsObserved}/{learningScenario.response.ledger.reviewsExpected}</strong></div><div><span>Candidate</span><strong>{learningScenario.response.ledger.candidatesObserved}/{learningScenario.response.ledger.candidatesExpected}</strong></div><div><span>Promotion</span><strong>{learningScenario.response.ledger.promotionsObserved}/{learningScenario.response.ledger.promotionsExpected}</strong></div><div><span>Citation</span><strong>{learningScenario.response.ledger.citationsObserved}/{learningScenario.response.ledger.citationsExpected}</strong></div><div><span>历史 Exposure 保留</span><strong>{learningScenario.response.ledger.retainedExposures}/{learningScenario.response.ledger.historicalExposures}</strong></div><div><span>影响 refs</span><strong>{learningScenario.response.ledger.impactRefsObserved}/{learningScenario.response.ledger.impactRefsExpected}</strong></div></div>
      <div className="analyst-learning-axes">{learningScenario.response.outcomeAxes.map((axis) => <article className={`is-${axis.status}`} key={axis.axisId}><span>{axis.axisId}</span><strong>{axis.status}</strong><p>{axis.exactRef ? `${axis.exactRef.resourceType} · v${axis.exactRef.revision}` : axis.blocker?.code}</p></article>)}</div>
      <p className="task-cockpit-approval-boundary">Candidate pending/approved/promoted 与知识 active/stale/revoked/expired 不混淆；approve ≠ promote。命令：submit=false · approve=false · promote=false · publish=false · revoke=false。</p>
    </section> : null}
      </div>
    </details>
    <div className={`analyst-tabs${investigationEnabled ? " has-investigation" : ""}`} role="tablist" aria-label="经营参谋只读视图">{(investigationEnabled ? (["investigation", ...response.views.map((item) => item.viewId)] as AnalystTabId[]) : response.views.map((item) => item.viewId)).map((tabId, index, tabs) => { const item = tabId === "investigation" ? undefined : response.views.find((candidate) => candidate.viewId === tabId); return <button id={`analyst-tab-${tabId}`} aria-controls={`analyst-panel-${tabId}`} type="button" role="tab" aria-selected={selected === tabId} tabIndex={selected === tabId ? 0 : -1} key={tabId} onClick={() => setSelected(tabId)} onKeyDown={(event) => { if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return; event.preventDefault(); const nextIndex = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length; setSelected(tabs[nextIndex]!); event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>("button")[nextIndex]?.focus(); }}><strong>{tabId === "investigation" ? "生意探究" : LABELS[tabId]}</strong><span>{item?.status ?? "read-only"}</span></button>; })}</div>
    {selected === "investigation" ? <BusinessInvestigationTab id="analyst-panel-investigation" labelledBy="analyst-tab-investigation" client={investigationClient} commandsEnabled={isBusinessInvestigationCommandEnabled(featureFlags)} /> : view ? <AnalystExactView view={view} selected={selected} /> : null}
    <footer className="content-campaign-footnote"><span>租户 {response.tenant.orgId}/{response.tenant.projectId}</span><span>统一 cutoff {new Date(response.dataCutoff).toLocaleString("zh-CN", { hour12: false })}</span><span>unknown 不显示 0</span></footer>
  </div> : null;
  return <section className="analyst-page" aria-label="经营参谋只读视图"><div className="content-campaign-toolbar"><span>Analyst v2 · GrowthPlan exact-binding read model</span><button type="button" onClick={load}>重新读取</button></div><AsyncStateBoundary state={stateFor(phase)} dataCutoff={response?.dataCutoff} action={phase === "failed" ? <button type="button" onClick={load}>重新读取</button> : undefined}>{content}</AsyncStateBoundary><AsyncJobDrawer load={loadAsyncJobs} /></section>;
}
