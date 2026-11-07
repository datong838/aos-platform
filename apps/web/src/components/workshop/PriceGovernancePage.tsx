import { useEffect, useRef, useState } from "react";

import { aipActionsSdk, type AipActionsSdk } from "../../api/aipActions/client";
import type { ActionDraftBundle, ActionProposalTimeline } from "../../api/aipActions/contracts";
import { EcommerceWorkshopClientError, ecommerceWorkshopClient, type PriceDispositionContributionViewResponse, type PriceGovernanceViewId, type PriceGovernanceViewResponse, type PriceGovernanceViewSlice, type PriceObservation, type PriceResearchContributionViewResponse, type RemedyScenarioOutcomeAxisId, type RemedyScenarioStageId, type ThreeModuleClosureContributionViewResponse } from "../../api/ecommerceWorkshop";
import { AsyncStateBoundary, type AsyncState } from "./AsyncStateBoundary";
import { deriveWorkshopViewState, pickPreferredWorkshopView } from "./workshopViewState";
import { ThreeModuleClosureCard, unavailableThreeModuleClosure } from "./ThreeModuleClosureCard";

type Client = Pick<typeof ecommerceWorkshopClient, "getPriceGovernanceView"> & Partial<Pick<typeof ecommerceWorkshopClient, "getPriceResearchContributionView" | "getPriceDispositionContributionView" | "getThreeModuleClosureContributionView">>;
type PriceActions = Pick<AipActionsSdk, "createProposal" | "createReplacementProposal" | "withdraw" | "timeline">;
type Phase = AsyncState;
type ObservationFilter = "all" | "comparable" | "review" | "excluded";
const LABELS: Record<PriceGovernanceViewId, string> = { governance: "同款价格治理", competitor: "竞品比价", schedule: "调度控制台" };
const STATUS_LABELS: Record<string, string> = { ready: "可读取", blocked: "等待条件", unknown: "待核对", partial: "部分可用", failed: "读取失败" };
const labelStatus = (value: string) => STATUS_LABELS[value] ?? "待核对";
const AXIS_LABELS = { collection: "采集证据", match: "同款判定", policy_case: "策略与业务事项", notification: "通知就绪", advice_handoff: "建议交接", repricing: "自动调价" } as const;
const stateFor = (phase: Phase): AsyncState => phase;
const unavailableContribution = (next: PriceGovernanceViewResponse): PriceResearchContributionViewResponse => ({ schemaVersion: "aos.ecommerce-workshop.price-research/v1", tenant: next.tenant, evaluatedAt: next.evaluatedAt, atomicSkillRefs: [], logicRef: null, primaryColleague: "数据参谋", collaboratorColleagues: ["活动策划师", "导购顾问"], latestBatch: null, blockers: ["PRICE_RESEARCH_BATCH_NOT_AVAILABLE"], allowedCommands: ["PREPARE_PRICE_RESEARCH_BATCH", "FREEZE_PRICE_RESEARCH_BATCH"], externalEffectsAllowed: false });
const unavailableDisposition = (next: PriceGovernanceViewResponse): PriceDispositionContributionViewResponse => ({ schemaVersion: "aos.ecommerce-workshop.price-disposition/v1", tenant: next.tenant, evaluatedAt: next.evaluatedAt, atomicSkillIds: ["compile-price-case", "prepare-price-advice", "prepare-price-notice", "prepare-price-handoff", "evaluate-reprice-specialized-gate"], logicId: "ecommerce-price-governance", primaryColleague: "数据参谋", collaboratorColleagues: ["活动策划师", "导购顾问"], caseCount: 0, dispositionCounts: { internal_advice: 0, external_notice: 0, module_handoff: 0, repricing: 0 }, latestDisposition: null, latestObservation: null, blockers: ["PRICE_DISPOSITION_AUTHORITY_UNAVAILABLE", "PRICE_CASE_NOT_AVAILABLE", "PRICE_DISPOSITION_NOT_AVAILABLE", "PRICE_NOTICE_OPERATIONAL_AUTHORITY_NOT_GRANTED", "PRICE_REPRICE_OPERATIONAL_AUTHORITY_NOT_GRANTED"], allowedCommands: ["COMPILE_PRICE_CASE", "CREATE_PRICE_DISPOSITION_CONTRACT", "PREPARE_PRICE_DISPOSITION", "FREEZE_PRICE_DISPOSITION", "RECORD_PRICE_DISPOSITION_OBSERVATION"], repricingEnabled: false, externalEffectsAllowed: false });
const DISPOSITION_LABELS = { internal_advice: "内部建议", external_notice: "外部通知", module_handoff: "模块交接", repricing: "调价" } as const;
const REMEDY_STAGE_LABELS: Record<RemedyScenarioStageId, string> = { price_observation: "价格异常", match_decision: "同款判定", price_case: "PriceCase", affected_orders: "受影响订单", operation_case: "OperationCase", customer_handoff: "客户补救交接", contact_permit: "联系许可", action_outcomes: "动作结果", effect_review: "效果复核" };
const REMEDY_AXIS_LABELS: Record<RemedyScenarioOutcomeAxisId, string> = { repricing_applied: "调价已应用", refund_compensation_submitted: "退款/补偿已提交", customer_message_accepted: "客户消息已接受", operation_case_resolved: "运营 Case 已解决", effect_mature: "效果已成熟" };

function PriceStrategyWorkspace({ view, observation, actions }: { view: PriceGovernanceViewSlice; observation: PriceObservation | null; actions: PriceActions }) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState("内部价格监测策略");
  const [tolerance, setTolerance] = useState("0.08");
  const [freshnessHours, setFreshnessHours] = useState("24");
  const [summary, setSummary] = useState("核对可比报价与同款证据，形成内部监测建议。");
  const [proposal, setProposal] = useState<ActionDraftBundle | null>(null);
  const [timeline, setTimeline] = useState<ActionProposalTimeline | null>(null);
  const [showComparison, setShowComparison] = useState(false);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const source = observation?.observationRef ?? view.authorityRefs[0] ?? view.readinessAxes.find((axis) => axis.exactRef)?.exactRef ?? null;
  useEffect(() => { setProposal(null); setTimeline(null); setEditing(false); setShowComparison(false); setNotice(""); }, [view.viewId]);
  const submit = async () => {
    if (!source || !title.trim() || !summary.trim()) { setNotice("缺少当前视图的 exact 价格来源或策略说明，保存失败关闭。"); return; }
    const ratio = Number(tolerance); const hours = Number(freshnessHours);
    if (!Number.isFinite(ratio) || ratio < 0 || ratio > 1 || !Number.isSafeInteger(hours) || hours < 1 || hours > 720) { setNotice("容差必须在 0 到 1，新鲜度必须在 1 到 720 小时。"); return; }
    setBusy(true); setNotice("");
    try {
      const expiresAt = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();
      if (proposal) {
        const next = await actions.createReplacementProposal(proposal, { purpose: title.trim(), diff: { toleranceRatio: { from: proposal.proposal.payload.toleranceRatio ?? null, to: ratio }, freshnessHours: { from: proposal.proposal.payload.freshnessHours ?? null, to: hours }, summary: { from: proposal.proposal.payload.summary ?? null, to: summary.trim() } }, expiresAt });
        setProposal(next); setEditing(false); setNotice(`策略修改已形成替代提案 ${next.proposal.id}，旧版本未被覆盖。`);
      } else {
        const objectRef = { resourceType: source.resourceType, resourceId: source.resourceId, revision: String(source.revision), authority: "ecommerce-workshop.price-governance-view" };
        const next = await actions.createProposal({ actionTypeId: "ecommerce.price.prepare-strategy", objectRef, purpose: title.trim(), riskHint: "R2", payload: { viewId: view.viewId, toleranceRatio: ratio, freshnessHours: hours, summary: summary.trim(), observationRef: observation?.observationRef ?? null, externalEffectAllowed: false, repricingAllowed: false }, diff: { status: { from: null, to: "待审批" }, toleranceRatio: { from: null, to: ratio } }, evidenceRefs: [objectRef], expiresAt });
        setProposal(next); setEditing(false); setNotice(`内部策略提案已形成：${next.proposal.id}。未采集、通知或调价。`);
      }
    } catch (error) { setNotice(error instanceof Error ? error.message : "内部价格策略保存失败关闭"); }
    finally { setBusy(false); }
  };
  const readTimeline = async () => {
    if (!proposal) { setNotice("当前尚未形成策略提案，执行结果保持可信空。"); return; }
    setBusy(true);
    try { const next = await actions.timeline(proposal.proposal.id); setTimeline(next); setNotice(`已回读 ${next.events.length} 条正式策略事件。`); }
    catch (error) { setNotice(error instanceof Error ? error.message : "策略事件读取失败关闭"); }
    finally { setBusy(false); }
  };
  const withdraw = async () => {
    if (!proposal) return; setBusy(true);
    try { const next = await actions.withdraw(proposal, "运营人员撤回内部价格策略提案"); setProposal(next); setNotice(`策略 ${next.proposal.id} 已撤回，调价与外部效果仍为 0。`); }
    catch (error) { setNotice(error instanceof Error ? error.message : "策略撤回失败关闭"); }
    finally { setBusy(false); }
  };
  return <section className="price-strategy-workspace" aria-label="内部价格策略工作区">
    <header><div><span>MonitoringPolicy → Action Proposal</span><h3>内部价格策略</h3></div><strong>{proposal ? `${proposal.proposal.status} · v${proposal.proposal.version}` : "尚未提交"}</strong></header>
    <p>{observation ? `当前依据：${observation.market} · ${observation.observationRef.resourceId}` : "请选择当前视图中的价格观察；没有 exact 来源时不生成策略。"}</p>
    {editing ? <form onSubmit={(event) => { event.preventDefault(); void submit(); }}><label>策略标题<input aria-label="价格策略标题" value={title} onChange={(event) => setTitle(event.target.value)} maxLength={120} /></label><div><label>价格容差<input aria-label="价格容差" type="number" min="0" max="1" step="0.01" value={tolerance} onChange={(event) => setTolerance(event.target.value)} /></label><label>新鲜度（小时）<input aria-label="价格新鲜度小时" type="number" min="1" max="720" step="1" value={freshnessHours} onChange={(event) => setFreshnessHours(event.target.value)} /></label></div><label>策略说明<textarea aria-label="价格策略说明" value={summary} onChange={(event) => setSummary(event.target.value)} maxLength={500} /></label><footer><button type="button" onClick={() => { setSummary("先核对同款、报价口径和 originals，再形成内部价格建议。"); setNotice("已采纳异常建议，尚未提交。"); }}>采纳异常建议</button><button type="button" onClick={() => setEditing(false)}>取消</button><button className="is-primary" type="submit" disabled={busy || !source}>{proposal ? "提交策略修改" : "保存策略草稿"}</button></footer></form> : <div className="price-strategy-actions"><button type="button" onClick={() => setEditing(true)}>{proposal ? "修改策略" : "新建监测策略"}</button><button type="button" onClick={() => setShowComparison((value) => !value)} disabled={!proposal}>对比预览</button><button type="button" onClick={readTimeline}>执行结果</button><button type="button" onClick={() => setNotice(proposal ? `审批前预览：${proposal.proposal.purpose}；风险 ${proposal.proposal.riskLevel}；需独立审批、短时租约与 R4 专业调价门，当前不允许执行。` : "请先形成内部策略提案。")}>批准预览</button><button type="button" onClick={withdraw} disabled={!proposal || busy || proposal.proposal.status === "withdrawn"}>撤回策略</button></div>}
    {showComparison && proposal ? <dl className="price-strategy-comparison" aria-label="价格策略对比预览"><div><dt>当前基线</dt><dd>保持现有正式 MonitoringPolicy</dd></div><div><dt>提案版本</dt><dd>{proposal.proposal.id} · v{proposal.proposal.version}</dd></div><div><dt>影响预览</dt><dd>ResearchJob 0 · Provider 0 · 调价 0</dd></div></dl> : null}
    {proposal ? <section className="price-strategy-receipt" aria-label="内部价格策略凭证"><strong>内部策略凭证</strong><span>{proposal.proposal.id} · 第 {proposal.proposal.version} 版</span><small title={proposal.proposal.proposalHash}>{proposal.proposal.proposalHash.slice(0, 16)}…</small><small>审批 {proposal.approvals.length} · 调价 0 · 外部效果 0</small></section> : null}
    {timeline ? <ol className="price-strategy-timeline">{timeline.events.map((event) => <li key={event.id}><strong>{event.type}</strong><span>{new Date(event.createdAt).toLocaleString("zh-CN", { hour12: false })}</span></li>)}</ol> : null}
    <button type="button" className="price-collection-preflight" onClick={() => setNotice("立即采集预检：来源许可、capacity、budget 与 Provider authority 未齐；ResearchJob 0，外部调用 0。")}>立即采集预检</button>
    {notice ? <p className="price-strategy-notice" role="status">{notice}</p> : null}
  </section>;
}

export function PriceGovernancePage({ client = ecommerceWorkshopClient, actions = aipActionsSdk }: { client?: Client; actions?: PriceActions }) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [response, setResponse] = useState<PriceGovernanceViewResponse | null>(null);
  const [contribution, setContribution] = useState<PriceResearchContributionViewResponse | null>(null);
  const [disposition, setDisposition] = useState<PriceDispositionContributionViewResponse | null>(null);
  const [closure, setClosure] = useState<ThreeModuleClosureContributionViewResponse | null>(null);
  const [selected, setSelected] = useState<PriceGovernanceViewId>("governance");
  const [observationFilter, setObservationFilter] = useState<ObservationFilter>("all");
  const [selectedObservationId, setSelectedObservationId] = useState<string | null>(null);
  const request = useRef(0);
  const load = () => {
    const id = ++request.current; setPhase("loading"); setResponse(null); setContribution(null); setDisposition(null); setClosure(null);
    void Promise.all([client.getPriceGovernanceView(), client.getPriceResearchContributionView?.().catch(() => null) ?? Promise.resolve(null), client.getPriceDispositionContributionView?.().catch(() => null) ?? Promise.resolve(null), client.getThreeModuleClosureContributionView?.("price").catch(() => null) ?? Promise.resolve(null)]).then(([next, nextContribution, nextDisposition, nextClosure]) => { if (id !== request.current) return; setResponse(next); setContribution(nextContribution ?? unavailableContribution(next)); setDisposition(nextDisposition ?? unavailableDisposition(next)); setClosure(nextClosure ?? unavailableThreeModuleClosure("price", next.tenant, next.evaluatedAt)); setSelected(pickPreferredWorkshopView(next.views, (item) => item.observations.length > 0)?.viewId ?? "governance"); setPhase(deriveWorkshopViewState(next.views, next.page.count)); }, (error: unknown) => { if (id === request.current) setPhase(error instanceof EcommerceWorkshopClientError && (error.status === 401 || error.status === 403) ? "forbidden" : "failed"); });
  };
  useEffect(() => { load(); return () => { request.current += 1; }; }, [client]);
  const view = response?.views.find((item) => item.viewId === selected);
  const visibleObservations = view?.observations.filter((item) => observationFilter === "all" || (observationFilter === "comparable" && item.comparability === "comparable") || (observationFilter === "review" && (item.comparability === "unknown" || item.matchStatus === "preliminary" || item.matchStatus === "unknown")) || (observationFilter === "excluded" && item.comparability === "not_comparable")) ?? [];
  const selectedObservation = view?.observations.find((item) => item.observationRef.resourceId === selectedObservationId) ?? view?.observations[0] ?? null;
  const comparable = response?.views.reduce((sum, item) => sum + item.countLedger.eligible, 0) ?? 0;
  const total = response?.views.reduce((sum, item) => sum + item.countLedger.input, 0) ?? 0;
  const content = response && view ? <div className="price-governance-read-model">
    <details className="price-governance-audit-context">
      <summary>价格治理全过程与累计审计</summary>
      <div className="price-governance-audit-stack">
    <section className="price-governance-hero"><div><span>价格治理驾驶舱 · exact evidence</span><h2>用统一报价口径审视市场价格，而不是自动改价</h2><p>Observation 与 Match Decision 分离；陈旧、未许可、初步匹配或 original 不可达均不计可比异常。</p></div><strong>只读 · 调价禁用</strong></section>
    <section className="creator-growth-axis"><div><span>只读视图</span><strong>3</strong></div><div><span>可比报价</span><strong>{comparable}/{total}</strong></div><div><span>资源 revision</span><strong>r{response.resourceRevision}</strong></div><div><span>写入口</span><strong>0</strong></div></section>
    {contribution ? <section className="creator-contribution-card" aria-label="价格治理数字同事贡献"><header><div><span>原子 Skill → Logic → 数字同事</span><h3>{contribution.primaryColleague}主责价格调研</h3></div><strong>{contribution.latestBatch?.lifecycle ?? "未准备"}</strong></header><p>{contribution.atomicSkillRefs.length ? `${contribution.atomicSkillRefs.length} 个原子 Skill 由 ${contribution.logicRef?.resourceId ?? "未知 Logic"} 编排` : "当前未挂接 exact Skill/Logic authority，保持失败关闭。"}</p><div className="creator-contribution-grid"><span>协作：{contribution.collaboratorColleagues.join("、")}</span><span>批次：{contribution.latestBatch ? `${contribution.latestBatch.ledger.eligible}/${contribution.latestBatch.ledger.input} eligible` : "无可信批次"}</span><span>外部效果：0</span><span>ResearchJob：0</span></div><small>{contribution.blockers.length ? contribution.blockers.join(" · ") : "exact contribution chain ready"}</small></section> : null}
    {disposition ? <section className="price-disposition-card" aria-label="价格处置分门贡献"><header><div><span>PriceCase → typed contract → exact gate</span><h3>价格通知、建议、交接与调价严格分门</h3></div><strong>只读预检</strong></header><p>{disposition.atomicSkillIds.length} 个原子 Skill 经 {disposition.logicId} 编排，由{disposition.primaryColleague}主责；任何分门都不直接授予执行权。</p><div className="price-disposition-grid">{(Object.keys(DISPOSITION_LABELS) as Array<keyof typeof DISPOSITION_LABELS>).map((kind) => <article key={kind} className={`is-${kind}`}><span>{DISPOSITION_LABELS[kind]}</span><strong>{disposition.dispositionCounts[kind]}</strong><small>{kind === "repricing" ? "专业门关闭 · executionAllowed=false" : kind === "external_notice" ? "通知 authority 未授予" : kind === "module_handoff" ? "仅内部 Envelope 草案" : "仅建议草案"}</small></article>)}</div><footer><span>PriceCase：{disposition.caseCount}</span><span>通知发送：0</span><span>调价：0</span><span>外部效果：0</span></footer><small>{disposition.blockers.length ? disposition.blockers.join(" · ") : "exact disposition chain ready"}</small></section> : null}
    {response.remedyScenario ? <section className="remedy-scenario-card" aria-label="价格异常客户补救同链贡献"><header><div><span>价格异常 → PriceCase → OperationCase → 客户补救</span><h3>一个 exact 根串起运营 Case 与客户补救，但不展开受保护正文</h3></div><strong>失败关闭 · 无外部效果</strong></header><div className="remedy-scenario-binding"><span>原子 Skill → Logic 编排 → 数字同事绑定 → 工作台贡献</span><strong>{response.remedyScenario.rootCaseRef ? `${response.remedyScenario.rootCaseRef.resourceId} · r${response.remedyScenario.rootCaseRef.revision}` : "缺少 PriceCase exact 根"}</strong><small>{response.remedyScenario.remedyBindingHash ? `binding ${response.remedyScenario.remedyBindingHash.slice(0, 12)}…` : "binding 未建立"}</small></div><div className="remedy-scenario-stages">{response.remedyScenario.stages.map((stage, index) => <article key={stage.stageId} className={`is-${stage.status}`}><span>{String(index + 1).padStart(2, "0")}</span><strong>{REMEDY_STAGE_LABELS[stage.stageId]}</strong><small>{stage.status === "ready" ? `${stage.exactRefs.length} exact ref` : stage.blockers[0]?.code ?? "unknown"}</small></article>)}</div><div className="remedy-scenario-ledger"><div><span>受影响订单</span><strong>{response.remedyScenario.ledger.affectedOrdersObserved}/{response.remedyScenario.ledger.affectedOrdersExpected}</strong></div><div><span>合格客户</span><strong>{response.remedyScenario.ledger.eligibleCustomersObserved}/{response.remedyScenario.ledger.eligibleCustomersExpected}</strong></div><div><span>动作结果</span><strong>{response.remedyScenario.ledger.actionsReady}/{response.remedyScenario.ledger.actionsExpected}</strong></div><div><span>受保护联系正文</span><strong>未解析</strong></div></div><div className="remedy-scenario-axes">{response.remedyScenario.outcomeAxes.map((axis) => <article key={axis.axisId} className={`is-${axis.status}`}><strong>{REMEDY_AXIS_LABELS[axis.axisId]}</strong><span>{axis.status}</span><small>{axis.exactRef ? `${axis.exactRef.resourceType} · r${axis.exactRef.revision}` : axis.blocker?.code ?? "unknown"}</small></article>)}</div><footer><span>调价 0</span><span>退款/补偿提交 0</span><span>客户消息发送 0</span><span>Case 关闭 0</span><span>外部效果 0</span></footer></section> : null}
    {closure ? <ThreeModuleClosureCard value={closure} /> : null}
      </div>
    </details>
    <div className="price-governance-tabs" role="tablist" aria-label="价格治理只读视图">{response.views.map((item, index) => <button id={`price-governance-tab-${item.viewId}`} aria-controls={`price-governance-panel-${item.viewId}`} type="button" role="tab" aria-selected={selected === item.viewId} tabIndex={selected === item.viewId ? 0 : -1} key={item.viewId} onClick={() => setSelected(item.viewId)} onKeyDown={(event) => { if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return; event.preventDefault(); const nextIndex = event.key === "Home" ? 0 : event.key === "End" ? response.views.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + response.views.length) % response.views.length; setSelected(response.views[nextIndex]!.viewId); event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>("button")[nextIndex]?.focus(); }}><strong>{LABELS[item.viewId]}</strong><span>{labelStatus(item.status)}</span></button>)}</div>
    <section id={`price-governance-panel-${selected}`} aria-labelledby={`price-governance-tab-${selected}`} className="price-governance-panel" role="tabpanel" aria-label={LABELS[selected]}><header><div><span>当前业务视图</span><h2>{LABELS[view.viewId]}</h2></div><strong className={`content-campaign-status is-${view.status}`}>{view.status === "ready" ? "正式数据可读" : "等待数据"}</strong></header>
      <div className="price-governance-readiness"><header><span>价格治理流程</span><h2>价格治理任务链</h2></header>{view.readinessAxes.map((axis) => <article key={axis.axis} className={`is-${axis.status}`}><strong>{AXIS_LABELS[axis.axis]}</strong><span>{labelStatus(axis.status)}</span><p>{axis.exactRef ? "正式数据已挂接" : axis.axis === "repricing" ? "专业调价能力未开启" : "暂无可验证来源"}</p><details><summary>查看数据审计信息</summary><p>{axis.exactRef ? `${axis.exactRef.resourceType} · 第 ${axis.exactRef.revision} 版` : "未提供正式数据引用"}</p></details></article>)}</div>
      <section className="price-observations"><nav aria-label="价格观察筛选">{([['all', '全部'], ['comparable', '可比'], ['review', '待复核'], ['excluded', '已排除']] as const).map(([id, label]) => <button type="button" key={id} aria-pressed={observationFilter === id} onClick={() => setObservationFilter(id)}>{label}</button>)}</nav>{visibleObservations.length ? visibleObservations.map((item) => <article key={`${item.observationRef.resourceId}:${item.observationRef.revision}`} className={`is-${item.comparability}${selectedObservation?.observationRef.resourceId === item.observationRef.resourceId ? " is-selected" : ""}`}><header><div><strong>{item.market}</strong><span>{item.comparability} · {item.matchStatus}</span></div>{item.amount === null ? <b>待核对，不以 0 代替</b> : <b>{item.quoteBasis.currency} {item.amount}</b>}</header><dl><div><dt>报价口径</dt><dd>{item.quoteBasis.basis} · {item.quoteBasis.quantity} {item.quoteBasis.unit}</dd></div><div><dt>税 / 运费</dt><dd>{item.quoteBasis.tax} / {item.quoteBasis.shipping}</dd></div><div><dt>新鲜度 / 许可</dt><dd>{item.freshness} / {item.license}</dd></div><div><dt>原始证据</dt><dd>{item.originalRefs.length + item.mergedOriginalRefs.length}</dd></div></dl><small>{item.quoteBasis.promotionCondition} · {new Date(item.observedAt).toLocaleString("zh-CN", { hour12: false })}</small><button type="button" aria-pressed={selectedObservation?.observationRef.resourceId === item.observationRef.resourceId} onClick={() => setSelectedObservationId(item.observationRef.resourceId)}>选择此观察</button></article>) : <div className="price-empty-sku"><header><strong>核心商品列表</strong><span>待核对</span></header><div><b>异常候选</b><span>未挂接</span></div><div><b>待复核商品</b><span>未挂接</span></div><div><b>可比报价</b><span>待核对</span></div><p>{view.observations.length ? "当前筛选没有匹配的价格观察；可切换筛选继续核对。" : "当前没有可挂接的价格观察；可信空与待补条件分开表达。"}</p></div>}</section>
      <aside className="media-studio-blockers"><PriceStrategyWorkspace view={view} observation={selectedObservation} actions={actions} /><section className="price-colleague-summary"><span>数字同事</span><h3>数字同事协作</h3><strong>数据参谋主责 · 正式数据待挂接</strong><p>活动策划师与导购顾问只读校验，不生成价格结论。</p></section><h3>所需条件与下一步</h3>{view.blockers.length ? view.blockers.map((item) => <details key={item.code}><summary>补充正式价格数据</summary><span>当前不能形成调价结论</span><p>{item.requiredAction}</p><p>{item.dependency}</p><code>{item.code}</code></details>) : <p>本视图当前没有待补条件。</p>}</aside>
    </section>
    <footer className="content-campaign-footnote"><span>租户 {response.tenant.orgId}/{response.tenant.projectId}</span><span>统一数据截止 {new Date(response.dataCutoff).toLocaleString("zh-CN", { hour12: false })}</span><span>自动调价关闭</span></footer>
  </div> : null;
  return <section className="price-governance-page" aria-label="价格治理只读视图"><div className="content-campaign-toolbar price-governance-context-strip"><span>栖月汇 · 品牌待核对 · 核心商品待核对</span><span>数据参谋（负责人未绑定）+ 活动策划师 + 导购顾问</span><small>{response ? "价格治理视图已读取" : "价格治理视图未验证"}</small><b>{response ? `${response.views.filter((item) => item.status === "blocked").length} 个视图待复核` : "待复核数量待核对"}</b><button type="button" onClick={load}>刷新数据</button></div><AsyncStateBoundary state={stateFor(phase)} dataCutoff={response?.dataCutoff} action={phase === "failed" ? <button type="button" onClick={load}>重新读取</button> : undefined}>{content}</AsyncStateBoundary></section>;
}
