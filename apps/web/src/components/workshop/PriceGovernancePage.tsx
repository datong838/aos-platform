import { useEffect, useRef, useState } from "react";

import { EcommerceWorkshopClientError, ecommerceWorkshopClient, type PriceGovernanceViewId, type PriceGovernanceViewResponse } from "../../api/ecommerceWorkshop";
import { AsyncStateBoundary, type AsyncState } from "./AsyncStateBoundary";

type Client = Pick<typeof ecommerceWorkshopClient, "getPriceGovernanceView">;
type Phase = "loading" | "ready" | "empty" | "forbidden" | "failed";
const LABELS: Record<PriceGovernanceViewId, string> = { governance: "价格治理", competitor: "竞品同款", schedule: "调度与复核" };
const AXIS_LABELS = { collection: "采集证据", match: "同款判定", policy_case: "策略与 Case", notification: "通知就绪", advice_handoff: "建议交接", repricing: "自动调价" } as const;
const stateFor = (phase: Phase): AsyncState => phase === "ready" || phase === "empty" ? "ready" : phase;

export function PriceGovernancePage({ client = ecommerceWorkshopClient }: { client?: Client }) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [response, setResponse] = useState<PriceGovernanceViewResponse | null>(null);
  const [selected, setSelected] = useState<PriceGovernanceViewId>("governance");
  const request = useRef(0);
  const load = () => {
    const id = ++request.current; setPhase("loading"); setResponse(null);
    void client.getPriceGovernanceView().then((next) => { if (id !== request.current) return; setResponse(next); setSelected(next.views.find((item) => item.status === "blocked")?.viewId ?? "governance"); setPhase(next.page.count === 0 && next.views.every((item) => item.status === "ready") ? "empty" : "ready"); }, (error: unknown) => { if (id === request.current) setPhase(error instanceof EcommerceWorkshopClientError && (error.status === 401 || error.status === 403) ? "forbidden" : "failed"); });
  };
  useEffect(() => { load(); return () => { request.current += 1; }; }, [client]);
  const view = response?.views.find((item) => item.viewId === selected);
  const comparable = response?.views.reduce((sum, item) => sum + item.countLedger.eligible, 0) ?? 0;
  const total = response?.views.reduce((sum, item) => sum + item.countLedger.input, 0) ?? 0;
  const content = response && view ? <div className="price-governance-read-model">
    <section className="price-governance-hero"><div><span>价格治理驾驶舱 · exact evidence</span><h2>用统一报价口径审视市场价格，而不是自动改价</h2><p>Observation 与 Match Decision 分离；陈旧、未许可、初步匹配或 original 不可达均不计可比异常。</p></div><strong>只读 · 调价禁用</strong></section>
    <section className="creator-growth-axis"><div><span>只读视图</span><strong>3</strong></div><div><span>可比报价</span><strong>{comparable}/{total}</strong></div><div><span>资源 revision</span><strong>r{response.resourceRevision}</strong></div><div><span>写入口</span><strong>0</strong></div></section>
    <div className="price-governance-tabs" role="tablist" aria-label="价格治理只读视图">{response.views.map((item, index) => <button type="button" role="tab" aria-selected={selected === item.viewId} tabIndex={selected === item.viewId ? 0 : -1} key={item.viewId} onClick={() => setSelected(item.viewId)} onKeyDown={(event) => { if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return; event.preventDefault(); const nextIndex = event.key === "Home" ? 0 : event.key === "End" ? response.views.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + response.views.length) % response.views.length; setSelected(response.views[nextIndex]!.viewId); event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>("button")[nextIndex]?.focus(); }}><strong>{LABELS[item.viewId]}</strong><span>{item.status}</span></button>)}</div>
    <section className="price-governance-panel" role="tabpanel" aria-label={LABELS[selected]}><header><div><span>{view.viewId}</span><h2>{LABELS[view.viewId]}</h2></div><strong className={`content-campaign-status is-${view.status}`}>{view.status === "ready" ? "同截止面可读" : "失败关闭"}</strong></header>
      <div className="price-governance-readiness">{view.readinessAxes.map((axis) => <article key={axis.axis} className={`is-${axis.status}`}><strong>{AXIS_LABELS[axis.axis]}</strong><span>{axis.status}</span><p>{axis.exactRef ? `${axis.exactRef.resourceType} · r${axis.exactRef.revision}` : axis.axis === "repricing" ? "R4 专业门未开启" : "无 exact authority"}</p></article>)}</div>
      <section className="price-observations">{view.observations.length ? view.observations.map((item) => <article key={`${item.observationRef.resourceId}:${item.observationRef.revision}`} className={`is-${item.comparability}`}><header><div><strong>{item.market}</strong><span>{item.comparability} · {item.matchStatus}</span></div>{item.amount === null ? <b>未知，不以 0 代替</b> : <b>{item.quoteBasis.currency} {item.amount}</b>}</header><dl><div><dt>报价口径</dt><dd>{item.quoteBasis.basis} · {item.quoteBasis.quantity} {item.quoteBasis.unit}</dd></div><div><dt>税 / 运费</dt><dd>{item.quoteBasis.tax} / {item.quoteBasis.shipping}</dd></div><div><dt>新鲜度 / 许可</dt><dd>{item.freshness} / {item.license}</dd></div><div><dt>原始证据</dt><dd>{item.originalRefs.length + item.mergedOriginalRefs.length}</dd></div></dl><small>{item.quoteBasis.promotionCondition} · {new Date(item.observedAt).toLocaleString("zh-CN", { hour12: false })}</small></article>) : <p>当前没有可挂接的价格 Observation；可信空与 blocked/unknown 分开表达。</p>}</section>
      <aside className="media-studio-blockers"><h3>阻断与下一证据</h3>{view.blockers.length ? view.blockers.map((item) => <div key={item.code}><strong>{item.code}</strong><span>{item.dependency}</span><p>{item.requiredAction}</p></div>) : <p>本视图当前无 blocker。</p>}</aside>
    </section>
    <footer className="content-campaign-footnote"><span>租户 {response.tenant.orgId}/{response.tenant.projectId}</span><span>统一 cutoff {new Date(response.dataCutoff).toLocaleString("zh-CN", { hour12: false })}</span><span>repricing disabled</span></footer>
  </div> : null;
  return <section className="price-governance-page" aria-label="价格治理只读视图"><div className="content-campaign-toolbar"><span>Price Governance v1 · canonical read model</span><button type="button" onClick={load}>重新读取</button></div><AsyncStateBoundary state={stateFor(phase)} dataCutoff={response?.dataCutoff} action={phase === "failed" ? <button type="button" onClick={load}>重新读取</button> : undefined}>{content}</AsyncStateBoundary></section>;
}
