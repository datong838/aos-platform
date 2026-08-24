import { useEffect, useRef, useState } from "react";

import { EcommerceWorkshopClientError, ecommerceWorkshopClient, type OperationsSlice, type OperationsSliceId, type OperationsViewResponse } from "../../api/ecommerceWorkshop";
import { AsyncStateBoundary, type AsyncState } from "./AsyncStateBoundary";

type OperationsClient = Pick<typeof ecommerceWorkshopClient, "getOperationsView">;
type Phase = "loading" | "ready" | "empty" | "forbidden" | "failed";
const LABELS: Record<OperationsSliceId, string> = { orders: "订单", orderLines: "订单明细", inventory: "库存", shipments: "履约", payments: "支付", aftersaleEvents: "售后事件", operationCases: "运营工单" };

function stateFor(phase: Phase): AsyncState { return phase === "ready" || phase === "empty" ? "ready" : phase; }
function formatTime(value: string): string { return new Date(value).toLocaleString("zh-CN", { hour12: false }); }
function short(value: string): string { return value.length > 30 ? `${value.slice(0, 14)}…${value.slice(-10)}` : value; }
function phaseFor(error: unknown): Phase { return error instanceof EcommerceWorkshopClientError && (error.status === 401 || error.status === 403) ? "forbidden" : "failed"; }

function SliceDetail({ slice }: { slice: OperationsSlice }) {
  return <>
    <header className="operations-detail-heading"><div><span>{slice.sliceId}</span><h2>{LABELS[slice.sliceId]}</h2></div><strong className={`operations-status is-${slice.status}`}>{slice.status === "ready" ? "权威读取可用" : "失败关闭"}</strong></header>
    <section className="operations-ledger" aria-label="数量守恒账本"><div><span>来源总量</span><strong>{slice.countLedger.sourceTotal}</strong></div><div><span>已挂接</span><strong>{slice.countLedger.attached}</strong></div><div><span>未匹配</span><strong>{slice.countLedger.unmatched}</strong></div><div><span>冲突</span><strong>{slice.countLedger.conflicted}</strong></div></section>
    <section className="operations-detail-section"><h3>同一截止面</h3><p>{formatTime(slice.dataCutoff)}</p><small>各切片必须与驾驶舱 dataCutoff 完全一致。</small></section>
    <section className="operations-detail-section"><h3>Exact authority</h3>{slice.authorityRefs.length ? <ul>{slice.authorityRefs.map((ref) => <li key={`${ref.resourceType}:${ref.resourceId}:${ref.revision}`}><strong>{ref.resourceType} · r{ref.revision}</strong><span>{ref.resourceId}</span><small title={ref.contentHash}>{short(ref.contentHash)}</small><small title={ref.receiptId}>Receipt {short(ref.receiptId)}</small></li>)}</ul> : <p className="operations-no-authority">当前没有合格 exact authority，未以计划、提交或零值替代。</p>}</section>
  </>;
}

export function OperationsPage({ client = ecommerceWorkshopClient }: { client?: OperationsClient }) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [response, setResponse] = useState<OperationsViewResponse | null>(null);
  const [selected, setSelected] = useState<OperationsSliceId>("orders");
  const request = useRef(0);
  const load = () => {
    const id = ++request.current; setPhase("loading"); setResponse(null);
    void client.getOperationsView().then((next) => { if (id !== request.current) return; setResponse(next); setSelected(next.slices.find((item) => item.status === "blocked")?.sliceId ?? next.slices[0]?.sliceId ?? "orders"); setPhase(next.page.count === 0 ? "empty" : "ready"); }, (error: unknown) => { if (id === request.current) setPhase(phaseFor(error)); });
  };
  useEffect(() => { load(); return () => { request.current += 1; }; }, [client]);
  const slice = response?.slices.find((item) => item.sliceId === selected) ?? response?.slices[0];
  const content = response && slice ? (() => {
    const ready = response.slices.filter((item) => item.status === "ready").length;
    const blocked = response.slices.length - ready;
    const totals = response.slices.reduce((value, item) => ({ source: value.source + item.countLedger.sourceTotal, attached: value.attached + item.countLedger.attached, unmatched: value.unmatched + item.countLedger.unmatched, conflicted: value.conflicted + item.countLedger.conflicted }), { source: 0, attached: 0, unmatched: 0, conflicted: 0 });
    return <div className="operations-read-model">
      <section className="operations-metrics" aria-label="运营驾驶舱权威指标"><div><span>权威切片</span><strong>7</strong><small>固定 canonical order</small></div><div className="is-ready"><span>读取可用</span><strong>{ready}</strong><small>exact authority 闭合</small></div><div className={blocked ? "is-blocked" : "is-ready"}><span>失败关闭</span><strong>{blocked}</strong><small>未伪装为可操作</small></div><div><span>来源总量</span><strong>{totals.source}</strong><small>七切片合计</small></div><div><span>已挂接</span><strong>{totals.attached}</strong><small>当前页 {response.page.count}</small></div><div className={totals.unmatched || totals.conflicted ? "is-warning" : "is-ready"}><span>待核对</span><strong>{totals.unmatched + totals.conflicted}</strong><small>未匹配 + 冲突</small></div><div className="operations-cutoff"><span>数据截止</span><strong>{formatTime(response.dataCutoff)}</strong><small>评估 {formatTime(response.evaluatedAt)}</small></div></section>
      <section className="operations-readonly"><span aria-hidden="true">✦</span><div><h2>跨域只读分诊</h2><p>页面只汇总权威切片、数量守恒与阻断证据；未接入退款、发货、库存调整或 AI 代执行。</p></div><strong>只读分诊</strong></section>
      <div className="operations-board">
        <aside className="operations-inbox"><header><h2>统一待办 · 权威切片</h2><span>{blocked} 项阻断</span></header>{response.slices.map((item) => <button type="button" className={`operations-slice-card is-${item.status}${item.sliceId === slice.sliceId ? " is-selected" : ""}`} aria-pressed={item.sliceId === slice.sliceId} key={item.sliceId} onClick={() => setSelected(item.sliceId)}><span><strong>{LABELS[item.sliceId]}</strong><small>{item.sliceId}</small></span><b>{item.countLedger.attached}</b><em>{item.status === "ready" ? "可读" : "阻断"}</em></button>)}</aside>
        <main className="operations-detail"><SliceDetail slice={slice} /></main>
        <aside className="operations-evidence"><header><h2>证据链 · 边界</h2><span>{slice.blockers.length} blocker</span></header>{slice.blockers.length ? <ul>{slice.blockers.map((blocker) => <li key={blocker.code}><strong>{blocker.code}</strong><span>{blocker.dependency}</span><p>{blocker.requiredAction}</p></li>)}</ul> : <div className="operations-evidence-clear"><strong>当前读取链闭合</strong><p>只证明该切片在当前截止面可读取；不授权任何外部副作用。</p></div>}<section><h3>不可推断</h3><p>页面 GREEN 不等于发布、迁移、Provider 或真实业务动作 GREEN。</p></section></aside>
      </div>
      <footer className="operations-footnote"><span>租户 {response.tenant.orgId}/{response.tenant.projectId}</span><span>来源 {totals.source}</span><span>已挂接 {totals.attached}</span><span>未匹配 {totals.unmatched}</span><span>冲突 {totals.conflicted}</span><span>无后续页：{response.page.hasMore ? "否" : "是"}</span></footer>
    </div>;
  })() : null;
  return <section className="operations-page" aria-label="统一运营驾驶舱只读视图"><div className="operations-toolbar"><span>Operations v1 · canonical read model</span><button type="button" onClick={load}>重新读取</button></div><AsyncStateBoundary state={stateFor(phase)} dataCutoff={response?.dataCutoff} action={phase === "failed" ? <button type="button" onClick={load}>重新读取</button> : undefined}>{content}</AsyncStateBoundary></section>;
}
