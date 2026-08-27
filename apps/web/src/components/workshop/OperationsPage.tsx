import { useEffect, useRef, useState } from "react";

import { EcommerceWorkshopClientError, ecommerceWorkshopClient, type OperationCommandObservationResponse, type OperationCommandReadinessResponse, type OperationsSlice, type OperationsSliceId, type OperationsViewResponse } from "../../api/ecommerceWorkshop";
import { AsyncStateBoundary, type AsyncState } from "./AsyncStateBoundary";
import { ContributionLineage } from "./production";

type OperationsClient = Pick<typeof ecommerceWorkshopClient, "getOperationsView" | "getOperationCommandReadiness" | "getOperationCommandObservation">;
type Phase = "loading" | "ready" | "empty" | "forbidden" | "failed";
const LABELS: Record<OperationsSliceId, string> = { orders: "订单", orderLines: "订单明细", inventory: "库存", shipments: "履约", payments: "支付", aftersaleEvents: "售后事件", operationCases: "运营工单" };
const CONTRIBUTIONS: Record<OperationsSliceId, string> = {
  orders: "以正式订单数据支撑跨域运营分诊",
  orderLines: "以正式订单明细支撑逐项核对",
  inventory: "以正式商品库存数据支撑风险识别，不执行库存调整",
  shipments: "以正式履约数据支撑异常识别",
  payments: "以正式支付数据支撑状态核对",
  aftersaleEvents: "以正式售后事件数据支撑售后事件分类",
  operationCases: "以正式运营事件聚合支撑可逆分诊与时效观察",
};

function stateFor(phase: Phase): AsyncState { return phase === "ready" || phase === "empty" ? "ready" : phase; }
function formatTime(value: string): string { return new Date(value).toLocaleString("zh-CN", { hour12: false }); }
function short(value: string): string { return value.length > 30 ? `${value.slice(0, 14)}…${value.slice(-10)}` : value; }
function phaseFor(error: unknown): Phase { return error instanceof EcommerceWorkshopClientError && (error.status === 401 || error.status === 403) ? "forbidden" : "failed"; }

function SliceDetail({ slice }: { slice: OperationsSlice }) {
  return <>
    <header className="operations-detail-heading"><div><span>当前业务视图</span><h2>{LABELS[slice.sliceId]}</h2></div><strong className={`operations-status is-${slice.status}`}>{slice.status === "ready" ? "正式数据可读" : "等待业务条件"}</strong></header>
    <section className="operations-ledger" aria-label="数量守恒账本"><div><span>来源总量</span><strong>{slice.countLedger.sourceTotal}</strong></div><div><span>已挂接</span><strong>{slice.countLedger.attached}</strong></div><div><span>未匹配</span><strong>{slice.countLedger.unmatched}</strong></div><div><span>冲突</span><strong>{slice.countLedger.conflicted}</strong></div></section>
    <section className="operations-detail-section"><h3>同一数据截止</h3><p>{formatTime(slice.dataCutoff)}</p><small>各业务视图的数据截止时间必须完全一致。</small></section>
    <section className="operations-detail-section"><h3>正式数据来源</h3>{slice.authorityRefs.length ? <ul>{slice.authorityRefs.map((ref) => <li key={`${ref.resourceType}:${ref.resourceId}:${ref.revision}`}><strong>{LABELS[slice.sliceId]}数据 · 第 {ref.revision} 版</strong><span>已通过当前租户边界校验</span><details><summary>查看数据审计信息</summary><small>{ref.resourceType} · {ref.resourceId}</small><small title={ref.contentHash}>{short(ref.contentHash)}</small><small title={ref.receiptId}>回读凭证 {short(ref.receiptId)}</small></details></li>)}</ul> : <p className="operations-no-authority">当前没有合格的正式数据来源，未以计划、提交或零值替代。</p>}</section>
  </>;
}

export function OperationsPage({ client = ecommerceWorkshopClient }: { client?: OperationsClient }) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [response, setResponse] = useState<OperationsViewResponse | null>(null);
  const [commandReadiness, setCommandReadiness] = useState<OperationCommandReadinessResponse | null>(null);
  const [selected, setSelected] = useState<OperationsSliceId>("orders");
  const [proposalId, setProposalId] = useState("");
  const [leaseId, setLeaseId] = useState("");
  const [observation, setObservation] = useState<OperationCommandObservationResponse | null>(null);
  const [observationState, setObservationState] = useState<"idle" | "loading" | "ready" | "failed">("idle");
  const [observationError, setObservationError] = useState("");
  const [commandNotice, setCommandNotice] = useState("");
  const request = useRef(0);
  const load = () => {
    const id = ++request.current; setPhase("loading"); setResponse(null); setCommandReadiness(null); setObservation(null); setObservationState("idle"); setObservationError("");
    void Promise.all([client.getOperationsView(), client.getOperationCommandReadiness()]).then(([next, nextCommands]) => { if (id !== request.current) return; if (next.tenant.orgId !== nextCommands.tenant.orgId || next.tenant.projectId !== nextCommands.tenant.projectId) throw new TypeError("operations command readiness tenant 漂移"); setResponse(next); setCommandReadiness(nextCommands); setSelected(next.slices.find((item) => item.status === "blocked")?.sliceId ?? next.slices[0]?.sliceId ?? "orders"); setPhase(next.page.count === 0 ? "empty" : "ready"); }, (error: unknown) => { if (id === request.current) setPhase(phaseFor(error)); });
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
    const blocked = response.slices.length - ready;
    const totals = response.slices.reduce((value, item) => ({ source: value.source + item.countLedger.sourceTotal, attached: value.attached + item.countLedger.attached, unmatched: value.unmatched + item.countLedger.unmatched, conflicted: value.conflicted + item.countLedger.conflicted }), { source: 0, attached: 0, unmatched: 0, conflicted: 0 });
    return <div className="operations-read-model">
      <section className="operations-metrics" aria-label="运营驾驶舱业务指标"><div><span>业务视图</span><strong>7</strong><small>固定展示顺序</small></div><div className="is-ready"><span>读取可用</span><strong>{ready}</strong><small>正式来源闭合</small></div><div className={blocked ? "is-blocked" : "is-ready"}><span>待补条件</span><strong>{blocked}</strong><small>未伪装为可操作</small></div><div><span>来源总量</span><strong>{totals.source}</strong><small>七类业务合计</small></div><div><span>已挂接</span><strong>{totals.attached}</strong><small>当前页 {response.page.count}</small></div><div className={totals.unmatched || totals.conflicted ? "is-warning" : "is-ready"}><span>待核对</span><strong>{totals.unmatched + totals.conflicted}</strong><small>未匹配 + 冲突</small></div><div className="operations-cutoff"><span>数据截止</span><strong>{formatTime(response.dataCutoff)}</strong><small>评估 {formatTime(response.evaluatedAt)}</small></div></section>
      <section className="operations-readonly"><span aria-hidden="true">✦</span><div><h2>跨域只读分诊</h2><p>页面只汇总正式业务数据、数量守恒与待补条件；未接入退款、发货、库存调整或 AI 代执行。</p></div><strong>保持待核对</strong></section>
      <div className="operations-board">
        <aside className="operations-inbox"><header><h2>统一待办 · 业务切片</h2><span>{blocked} 项待补条件</span></header>{response.slices.map((item) => <button type="button" className={`operations-slice-card is-${item.status}${item.sliceId === slice.sliceId ? " is-selected" : ""}`} aria-pressed={item.sliceId === slice.sliceId} key={item.sliceId} onClick={() => setSelected(item.sliceId)}><span><strong>{LABELS[item.sliceId]}</strong><small>业务视图</small></span><b>{item.countLedger.attached}</b><em>{item.status === "ready" ? "可读" : "等待条件"}</em></button>)}</aside>
        <section className="operations-detail" aria-label="运营详情"><SliceDetail slice={slice} /></section>
        <aside className="operations-evidence"><header><h2>证据链 · 边界</h2><span>{slice.blockers.length} 项待补条件</span></header>{slice.blockers.length ? <ul>{slice.blockers.map((blocker) => <li key={blocker.code}><strong>需要补充同租户、同数据截止的正式业务来源</strong><span>当前业务视图保持待核对</span><details><summary>查看审计状态码</summary><code>{blocker.code}</code><small>{blocker.dependency}</small><p>{blocker.requiredAction}</p></details></li>)}</ul> : <div className="operations-evidence-clear"><strong>当前读取链闭合</strong><p>只证明该业务视图在当前截止面可读取；不授权任何外部操作。</p></div>}<section><h3>专业贡献归因</h3><ContributionLineage value={{ atomicSkillRef: null, logicRef: null, coworker: null, workshopContribution: CONTRIBUTIONS[slice.sliceId] }} /><p>当前视图没有可验证的数字同事运行记录，因此不制造运行事实。</p></section><section className="operations-command-drawer" aria-label="统一运营动作建议"><header><div><small>动作安全预检</small><h3>运营动作建议</h3></div><span>0 / {commandReadiness.commands.length} 可提交</span></header><p>客户、金额、建议或执行授权缺失时，点击动作只返回安全预检结果，不生成示例事实。</p><div>{commandReadiness.commands.map((command) => <button type="button" className={`operations-command is-${command.risk}`} key={command.commandId} title={command.blockers.map((blocker) => blocker.requiredAction).join("；")} onClick={() => setCommandNotice(`${command.label}预检：当前业务条件不足。未触发业务操作。`)}><span><strong>{command.label}</strong><small>{command.sideEffect === "external" ? "涉及外部操作" : "涉及内部业务状态"}</small></span><em>安全预检</em></button>)}</div>{commandNotice ? <p role="status">{commandNotice}</p> : null}</section><section className="operations-observation" aria-label="请求级命令证据"><h3>请求级命令证据</h3><p>仅按当前租户的正式提案与租约读取回执；结果待核对时不自动重放。</p><form className="operations-observation-form" onSubmit={readObservation}><label><span>提案编号</span><input value={proposalId} onChange={(event) => setProposalId(event.target.value)} maxLength={300} autoComplete="off" /></label><label><span>租约编号</span><input value={leaseId} onChange={(event) => setLeaseId(event.target.value)} maxLength={300} autoComplete="off" /></label><button type="submit" disabled={!proposalId || !leaseId || observationState === "loading"}>{observationState === "loading" ? "读取中…" : "读取证据"}</button></form>{observationState === "idle" ? <div className="operations-observation-empty">尚未提供请求级引用；不从页面、清单或提交推断执行状态。</div> : null}{observationState === "failed" ? <div className="operations-observation-error"><strong>{observationError}</strong><span>读取失败关闭；未执行重放或补偿。</span></div> : null}{observation ? <dl className={`operations-observation-result is-${observation.status}`}><div><dt>决策摘要</dt><dd>{observation.commandId} · {observation.status}</dd></div><div><dt>证据链</dt><dd title={observation.receiptId ?? undefined}>{observation.receiptId ? short(observation.receiptId) : "尚无回执"}</dd></div><div><dt>归因路径</dt><dd title={observation.operationReceiptId ?? undefined}>{observation.operationReceiptId ? short(observation.operationReceiptId) : "未形成运营回执"}</dd></div><div><dt>关键假设和不确定性</dt><dd>{observation.status === "unknown" ? "结果待核对，必须另行对账" : "仅陈述当前正式观察"}</dd></div><div><dt>提案摘要</dt><dd title={observation.proposalHash}>{short(observation.proposalHash)}</dd></div><div><dt>重放策略</dt><dd>禁止自动重放</dd></div></dl> : null}</section><section><h3>不可推断</h3><p>页面可读不等于发布、迁移、外部服务或真实业务动作已获授权。</p></section></aside>
      </div>
      <footer className="operations-footnote"><span>租户 {response.tenant.orgId}/{response.tenant.projectId}</span><span>来源 {totals.source}</span><span>已挂接 {totals.attached}</span><span>未匹配 {totals.unmatched}</span><span>冲突 {totals.conflicted}</span><span>无后续页：{response.page.hasMore ? "否" : "是"}</span></footer>
    </div>;
  })() : null;
  return <section className="operations-page" aria-label="统一运营驾驶舱只读视图"><div className="operations-toolbar"><span>统一运营 · 正式业务只读模型</span><button type="button" onClick={load}>重新读取</button></div><AsyncStateBoundary state={stateFor(phase)} dataCutoff={response?.dataCutoff} action={phase === "failed" ? <button type="button" onClick={load}>重新读取</button> : undefined}>{content}</AsyncStateBoundary></section>;
}
