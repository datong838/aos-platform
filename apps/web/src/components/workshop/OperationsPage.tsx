import { useEffect, useRef, useState } from "react";

import { EcommerceWorkshopClientError, ecommerceWorkshopClient, type OperationCommandObservationResponse, type OperationCommandReadinessResponse, type OperationsSlice, type OperationsSliceId, type OperationsViewResponse } from "../../api/ecommerceWorkshop";
import { AsyncStateBoundary, type AsyncState } from "./AsyncStateBoundary";
import { ContributionLineage } from "./production";
import { deriveWorkshopViewState, pickPreferredWorkshopView } from "./workshopViewState";

type OperationsClient = Pick<typeof ecommerceWorkshopClient, "getOperationsView" | "getOperationCommandReadiness" | "getOperationCommandObservation">;
type Phase = AsyncState;
type QueueFilter = "all" | "orders" | "inventory" | "alerts";
type DetailPanel = "source" | "log" | null;

const LABELS: Record<OperationsSliceId, string> = { orders: "订单", orderLines: "订单明细", inventory: "库存", shipments: "履约", payments: "支付", aftersaleEvents: "售后事件", operationCases: "运营工单" };
const QUEUE_FILTERS: ReadonlyArray<{ id: QueueFilter; label: string; slices: readonly OperationsSliceId[] }> = [
  { id: "all", label: "全部", slices: [] },
  { id: "orders", label: "订单与履约", slices: ["orders", "orderLines", "payments", "shipments"] },
  { id: "inventory", label: "库存与告警", slices: ["inventory"] },
  { id: "alerts", label: "售后与工单", slices: ["aftersaleEvents", "operationCases"] },
];
const CONTRIBUTIONS: Record<OperationsSliceId, string> = {
  orders: "以正式订单数据支撑跨域运营分诊",
  orderLines: "以正式订单明细支撑逐项核对",
  inventory: "以正式商品库存数据支撑风险识别，不执行库存调整",
  shipments: "以正式履约数据支撑异常识别",
  payments: "以正式支付数据支撑状态核对",
  aftersaleEvents: "以正式售后事件数据支撑售后事件分类",
  operationCases: "以正式运营事件聚合支撑可逆分诊与时效观察",
};

function stateFor(phase: Phase): AsyncState { return phase; }
function formatTime(value: string): string { return new Date(value).toLocaleString("zh-CN", { hour12: false }); }
function short(value: string): string { return value.length > 30 ? `${value.slice(0, 14)}…${value.slice(-10)}` : value; }
function phaseFor(error: unknown): Phase { return error instanceof EcommerceWorkshopClientError && (error.status === 401 || error.status === 403) ? "forbidden" : "failed"; }
function queueLabel(sliceId: OperationsSliceId): string { return QUEUE_FILTERS.find((item) => item.slices.includes(sliceId))?.label ?? "统一待办"; }

function ProcessSteps({ slice, caseCount }: { slice: OperationsSlice; caseCount: number }) {
  const reconciled = slice.countLedger.unmatched === 0 && slice.countLedger.conflicted === 0;
  const steps = [
    { title: "读取正式业务数据", detail: slice.authorityRefs.length ? `已核对 ${slice.authorityRefs.length} 个当前租户正式来源` : "当前视图需补充正式业务来源", done: slice.authorityRefs.length > 0 },
    { title: "数量守恒核对", detail: reconciled ? "未匹配与冲突均为 0" : `需复核 ${slice.countLedger.unmatched} 条未匹配、${slice.countLedger.conflicted} 条冲突`, done: reconciled },
    { title: "运营处理关联", detail: caseCount ? `当前截止面有 ${caseCount} 条正式运营工单聚合` : "当前截止面没有已关联的正式运营工单", done: caseCount > 0 },
    { title: "人工业务处置", detail: "核对证据与安全预检后，由运营人员决定内部处理路径", done: false },
  ];
  return <section className="operations-process" aria-label="业务处理流程"><h3>业务处理流程</h3><ol>{steps.map((step, index) => <li className={step.done ? "is-done" : "is-current"} key={step.title}><span>{step.done ? "✓" : index + 1}</span><div><strong>{step.title}</strong><small>{step.detail}</small></div></li>)}</ol></section>;
}

function SliceDetail({ slice, caseCount, panel, setPanel }: { slice: OperationsSlice; caseCount: number; panel: DetailPanel; setPanel: (panel: DetailPanel) => void }) {
  return <>
    <header className="operations-detail-heading"><div><span>{queueLabel(slice.sliceId)}</span><h2>{LABELS[slice.sliceId]} · 业务处理</h2></div><strong className={`operations-status is-${slice.status}`}>{slice.status === "ready" ? "正式数据可读" : "需业务复核"}</strong></header>
    <div className="operations-detail-actions"><button type="button" aria-expanded={panel === "source"} onClick={() => setPanel(panel === "source" ? null : "source")}>查看原始数据</button><button type="button" aria-expanded={panel === "log"} onClick={() => setPanel(panel === "log" ? null : "log")}>处理日志</button></div>
    {panel ? <section className="operations-inline-dialog" role="dialog" aria-label={panel === "source" ? "原始数据" : "处理日志"}><header><strong>{panel === "source" ? "正式数据来源" : "当前处理日志"}</strong><button type="button" onClick={() => setPanel(null)} aria-label="关闭详情">×</button></header>{panel === "source" ? (slice.authorityRefs.length ? <ul>{slice.authorityRefs.map((ref) => <li key={`${ref.resourceType}:${ref.resourceId}:${ref.revision}`}><strong>{ref.resourceType}</strong><span>{ref.resourceId} · 第 {ref.revision} 版</span><small title={ref.receiptId}>回读凭证 {short(ref.receiptId)}</small></li>)}</ul> : <p>当前没有可展示的正式数据来源。</p>) : <dl><div><dt>同一数据截止</dt><dd>{formatTime(slice.dataCutoff)}</dd></div><div><dt>读取状态</dt><dd>{slice.status === "ready" ? "正式读取成功" : "业务证据需复核"}</dd></div><div><dt>数量记录</dt><dd>来源 {slice.countLedger.sourceTotal} · 已挂接 {slice.countLedger.attached} · 未匹配 {slice.countLedger.unmatched} · 冲突 {slice.countLedger.conflicted}</dd></div></dl>}</section> : null}
    <section className="operations-ledger" aria-label="数量守恒账本"><div><span>来源总量</span><strong>{slice.countLedger.sourceTotal}</strong></div><div><span>已挂接</span><strong>{slice.countLedger.attached}</strong></div><div><span>未匹配</span><strong>{slice.countLedger.unmatched}</strong></div><div><span>冲突</span><strong>{slice.countLedger.conflicted}</strong></div></section>
    <section className="operations-detail-section"><h3>正式数据来源</h3>{slice.authorityRefs.length ? <ul>{slice.authorityRefs.map((ref) => <li key={`${ref.resourceType}:${ref.resourceId}:${ref.revision}`}><strong>{LABELS[slice.sliceId]}数据 · 第 {ref.revision} 版</strong><span>已通过当前租户边界校验</span><details><summary>查看数据审计信息</summary><small>{ref.resourceType} · {ref.resourceId}</small><small title={ref.contentHash}>{short(ref.contentHash)}</small><small title={ref.receiptId}>回读凭证 {short(ref.receiptId)}</small></details></li>)}</ul> : <p className="operations-no-authority">当前没有合格的正式数据来源，未以计划、提交或零值替代。</p>}</section>
    <ProcessSteps slice={slice} caseCount={caseCount} />
  </>;
}

export function OperationsPage({ client = ecommerceWorkshopClient }: { client?: OperationsClient }) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [response, setResponse] = useState<OperationsViewResponse | null>(null);
  const [commandReadiness, setCommandReadiness] = useState<OperationCommandReadinessResponse | null>(null);
  const [selected, setSelected] = useState<OperationsSliceId>("orders");
  const [queueFilter, setQueueFilter] = useState<QueueFilter>("all");
  const [query, setQuery] = useState("");
  const [detailPanel, setDetailPanel] = useState<DetailPanel>(null);
  const [showSuggestionBasis, setShowSuggestionBasis] = useState(false);
  const [showSop, setShowSop] = useState(false);
  const [proposalId, setProposalId] = useState("");
  const [leaseId, setLeaseId] = useState("");
  const [observation, setObservation] = useState<OperationCommandObservationResponse | null>(null);
  const [observationState, setObservationState] = useState<"idle" | "loading" | "ready" | "failed">("idle");
  const [observationError, setObservationError] = useState("");
  const [commandNotice, setCommandNotice] = useState("");
  const request = useRef(0);
  const load = () => {
    const id = ++request.current; setPhase("loading"); setResponse(null); setCommandReadiness(null); setObservation(null); setObservationState("idle"); setObservationError(""); setDetailPanel(null);
    void Promise.all([client.getOperationsView(), client.getOperationCommandReadiness()]).then(([next, nextCommands]) => { if (id !== request.current) return; if (next.tenant.orgId !== nextCommands.tenant.orgId || next.tenant.projectId !== nextCommands.tenant.projectId) throw new TypeError("operations command readiness tenant 漂移"); setResponse(next); setCommandReadiness(nextCommands); setSelected(pickPreferredWorkshopView(next.slices, (item) => item.countLedger.attached > 0)?.sliceId ?? "orders"); setPhase(deriveWorkshopViewState(next.slices, next.page.count)); }, (error: unknown) => { if (id === request.current) setPhase(phaseFor(error)); });
  };
  useEffect(() => { load(); return () => { request.current += 1; }; }, [client]);
  const readObservation = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!response || !proposalId || !leaseId) return;
    const tenant = response.tenant;
    const id = request.current;
    setObservation(null); setObservationState("loading"); setObservationError("");
    void client.getOperationCommandObservation(proposalId, leaseId).then((next) => {
      if (id !== request.current) return;
      if (next.tenant.orgId !== tenant.orgId || next.tenant.projectId !== tenant.projectId) throw new TypeError("operation command observation tenant 漂移");
      setObservation(next); setObservationState("ready");
    }).catch((error: unknown) => {
      if (id !== request.current) return;
      const code = error instanceof EcommerceWorkshopClientError ? error.body.code : "OBSERVATION_FAILED_CLOSED";
      setObservationError(code); setObservationState("failed");
    });
  };
  const slice = response?.slices.find((item) => item.sliceId === selected) ?? response?.slices[0];
  const content = response && commandReadiness && slice ? (() => {
    const ready = response.slices.filter((item) => item.status === "ready").length;
    const review = response.slices.length - ready;
    const totals = response.slices.reduce((value, item) => ({ source: value.source + item.countLedger.sourceTotal, attached: value.attached + item.countLedger.attached, unmatched: value.unmatched + item.countLedger.unmatched, conflicted: value.conflicted + item.countLedger.conflicted }), { source: 0, attached: 0, unmatched: 0, conflicted: 0 });
    const normalizedQuery = query.trim().toLocaleLowerCase("zh-CN");
    const activeFilter = QUEUE_FILTERS.find((item) => item.id === queueFilter) ?? QUEUE_FILTERS[0];
    const visibleSlices = response.slices.filter((item) => (activeFilter!.id === "all" || activeFilter!.slices.includes(item.sliceId)) && (!normalizedQuery || `${LABELS[item.sliceId]} ${item.sliceId} ${item.authorityRefs.map((ref) => ref.resourceId).join(" ")}`.toLocaleLowerCase("zh-CN").includes(normalizedQuery)));
    const activeSlice = visibleSlices.find((item) => item.sliceId === selected) ?? visibleSlices[0] ?? slice;
    const caseCount = response.slices.find((item) => item.sliceId === "operationCases")?.countLedger.attached ?? 0;
    const discrepancy = activeSlice.countLedger.unmatched + activeSlice.countLedger.conflicted;
    return <div className="operations-read-model">
      <section className="operations-metrics" aria-label="运营驾驶舱业务指标"><div><span>业务待办</span><strong>{response.slices.length}</strong><small>七类正式视图</small></div><div className="is-ready"><span>正式可读</span><strong>{ready}</strong><small>来源闭合</small></div><div className={review ? "is-warning" : "is-ready"}><span>需业务复核</span><strong>{review}</strong><small>不替代为已处理</small></div><div><span>来源总量</span><strong>{totals.source}</strong><small>七类业务合计</small></div><div><span>已挂接</span><strong>{totals.attached}</strong><small>当前页 {response.page.count}</small></div><div className={totals.unmatched || totals.conflicted ? "is-warning" : "is-ready"}><span>数据差异</span><strong>{totals.unmatched + totals.conflicted}</strong><small>未匹配 + 冲突</small></div><div className="operations-cutoff"><span>数据截止</span><strong>{formatTime(response.dataCutoff)}</strong><small>评估 {formatTime(response.evaluatedAt)}</small></div></section>
      <section className="operations-readonly"><span aria-hidden="true">✶</span><div><h2>跨域只读分诊</h2><p>按正式订单、库存、履约、支付、售后和运营工单核对待办，不自动执行外部业务操作。</p></div><strong>保持待核对</strong></section>
      <section className="operations-queue-toolbar"><label><span aria-hidden="true">⌕</span><input aria-label="搜索运营待办" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索业务类型、正式对象标识…" /></label><nav aria-label="统一待办分类">{QUEUE_FILTERS.map((item) => <button type="button" className={`operations-queue-filter${queueFilter === item.id ? " is-active" : ""}`} aria-pressed={queueFilter === item.id} key={item.id} onClick={() => { setQueueFilter(item.id); setDetailPanel(null); }}>{item.label}<span>{item.id === "all" ? response.slices.length : response.slices.filter((sliceItem) => item.slices.includes(sliceItem.sliceId)).length}</span></button>)}</nav></section>
      <div className="operations-board">
        <aside className="operations-inbox"><header><h2>统一待办 · 业务切片</h2><span>{visibleSlices.length} 个正式业务视图</span></header>{visibleSlices.length ? visibleSlices.map((item) => <button type="button" className={`operations-slice-card is-${item.status}${item.sliceId === activeSlice.sliceId ? " is-selected" : ""}`} aria-pressed={item.sliceId === activeSlice.sliceId} key={item.sliceId} onClick={() => { setSelected(item.sliceId); setDetailPanel(null); }}><span><strong>{LABELS[item.sliceId]}</strong><small>{queueLabel(item.sliceId)}</small></span><b>{item.countLedger.attached}</b><em>{item.status === "ready" ? "正式可读" : "需业务复核"}</em></button>) : <div className="operations-filter-empty">当前筛选下没有匹配的正式业务视图</div>}</aside>
        <section className="operations-detail" aria-label="运营详情"><SliceDetail slice={activeSlice} caseCount={caseCount} panel={detailPanel} setPanel={setDetailPanel} /></section>
        <aside className="operations-evidence"><header><h2>业务证据</h2><span>{activeSlice.blockers.length ? `${activeSlice.blockers.length} 项需复核` : "当前读取链闭合"}</span></header>{activeSlice.blockers.length ? <ul>{activeSlice.blockers.map((blocker) => <li key={blocker.code}><strong>需要补充同租户、同数据截止的正式业务来源</strong><span>当前业务视图保持待核对</span><details><summary>查看审计状态码</summary><code>{blocker.code}</code><small>{blocker.dependency}</small><p>{blocker.requiredAction}</p></details></li>)}</ul> : <div className="operations-evidence-clear"><strong>当前读取链闭合</strong><p>只证明该业务视图在当前截止面可读取；不授权任何外部操作。</p></div>}
          <section className="operations-advice"><h3>处理建议</h3><strong>{activeSlice.blockers.length ? "先补齐正式来源再进入处理" : discrepancy ? `先核对 ${discrepancy} 条数据差异` : "当前可继续证据复核"}</strong><p>{activeSlice.blockers.length ? activeSlice.blockers[0]?.requiredAction : discrepancy ? "未匹配或冲突记录不应直接进入业务处置。" : "数量守恒且正式来源已闭合，仍需运营人员确认处理路径。"}</p><button type="button" aria-expanded={showSuggestionBasis} onClick={() => setShowSuggestionBasis((value) => !value)}>查看建议依据</button>{showSuggestionBasis ? <small>建议仅根据当前数量守恒和正式来源生成，未使用虚构客户、订单或 AI 执行结果。</small> : null}</section>
          <section className="operations-sop"><h3>处理 SOP</h3><p>先核对数据截止和数量守恒，再审阅内部处理预检。</p><button type="button" aria-expanded={showSop} onClick={() => setShowSop((value) => !value)}>查看完整 SOP</button>{showSop ? <ol><li>核对订单、支付、履约和售后的同一截止面。</li><li>确认未匹配、冲突和缺失来源的影响。</li><li>查看内部处理预检和请求级回执。</li><li>任何外部操作均另行审批，不在本页自动执行。</li></ol> : null}</section>
          <section className="operations-similar"><h3>相似经验</h3>{caseCount ? <p>当前截止面有 {caseCount} 条正式运营工单聚合；仅在获取工单明细后展示单条经验。</p> : <p>当前没有可展示的正式运营工单经验。</p>}</section>
          <section><h3>专业贡献归因</h3><ContributionLineage value={{ atomicSkillRef: null, logicRef: null, coworker: null, workshopContribution: CONTRIBUTIONS[activeSlice.sliceId] }} /><p>当前视图没有可验证的数字同事运行记录，因此不制造运行事实。</p></section>
          <section className="operations-command-drawer" aria-label="统一运营动作建议"><header><div><small>动作安全预检</small><h3>运营动作建议</h3></div><span>0 / {commandReadiness.commands.length} 可提交</span></header><p>客户、金额、建议或执行授权缺失时，点击动作只返回安全预检结果，不生成示例事实。</p><div>{commandReadiness.commands.map((command) => <button type="button" className={`operations-command is-${command.risk}`} key={command.commandId} title={command.blockers.map((blocker) => blocker.requiredAction).join("；")} onClick={() => setCommandNotice(`${command.label}预检：当前业务条件不足。未触发业务操作。`)}><span><strong>{command.label}</strong><small>{command.sideEffect === "external" ? "涉及外部操作" : "涉及内部业务状态"}</small></span><em>安全预检</em></button>)}</div>{commandNotice ? <p role="status">{commandNotice}</p> : null}</section>
          <section className="operations-observation" aria-label="请求级命令证据"><h3>请求级命令证据</h3><p>仅按当前租户的正式提案与租约读取回执；结果待核对时不自动重放。</p><form className="operations-observation-form" onSubmit={readObservation}><label><span>提案编号</span><input value={proposalId} onChange={(event) => setProposalId(event.target.value)} maxLength={300} autoComplete="off" /></label><label><span>租约编号</span><input value={leaseId} onChange={(event) => setLeaseId(event.target.value)} maxLength={300} autoComplete="off" /></label><button type="submit" disabled={!proposalId || !leaseId || observationState === "loading"}>{observationState === "loading" ? "读取中…" : "读取证据"}</button></form>{observationState === "idle" ? <div className="operations-observation-empty">尚未提供请求级引用；不从页面、清单或提交推断执行状态。</div> : null}{observationState === "failed" ? <div className="operations-observation-error"><strong>{observationError}</strong><span>读取失败关闭；未执行重放或补偿。</span></div> : null}{observation ? <dl className={`operations-observation-result is-${observation.status}`}><div><dt>决策摘要</dt><dd>{observation.commandId} · {observation.status}</dd></div><div><dt>证据链</dt><dd title={observation.receiptId ?? undefined}>{observation.receiptId ? short(observation.receiptId) : "尚无回执"}</dd></div><div><dt>归因路径</dt><dd title={observation.operationReceiptId ?? undefined}>{observation.operationReceiptId ? short(observation.operationReceiptId) : "未形成运营回执"}</dd></div><div><dt>关键假设和不确定性</dt><dd>{observation.status === "unknown" ? "结果待核对，必须另行对账" : "仅陈述当前正式观察"}</dd></div><div><dt>提案摘要</dt><dd title={observation.proposalHash}>{short(observation.proposalHash)}</dd></div><div><dt>重放策略</dt><dd>禁止自动重放</dd></div></dl> : null}</section>
          <section><h3>不可推断</h3><p>页面可读不等于发布、迁移、外部服务或真实业务动作已获授权。</p></section></aside>
      </div>
      <footer className="operations-footnote"><span>租户 {response.tenant.orgId}/{response.tenant.projectId}</span><span>来源 {totals.source}</span><span>已挂接 {totals.attached}</span><span>未匹配 {totals.unmatched}</span><span>冲突 {totals.conflicted}</span><span>无后续页：{response.page.hasMore ? "否" : "是"}</span></footer>
    </div>;
  })() : null;
  return <section className="operations-page" aria-label="统一运营驾驶舱只读视图"><div className="operations-toolbar"><span>统一运营 · 正式业务处理视图</span><button type="button" onClick={load}>重新读取</button></div><AsyncStateBoundary state={stateFor(phase)} dataCutoff={response?.dataCutoff} action={phase === "failed" ? <button type="button" onClick={load}>重新读取</button> : undefined}>{content}</AsyncStateBoundary></section>;
}
