import { useEffect, useRef, useState } from "react";

import { EcommerceWorkshopClientError, ecommerceWorkshopClient, type AnalystViewId, type AnalystViewResponse } from "../../api/ecommerceWorkshop";
import { AsyncStateBoundary, type AsyncState } from "./AsyncStateBoundary";
import { ContributionLineage } from "./production";

type Client = Pick<typeof ecommerceWorkshopClient, "getAnalystView">;
type Phase = "loading" | "ready" | "empty" | "forbidden" | "failed";
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
const stateFor = (phase: Phase): AsyncState => phase === "ready" || phase === "empty" ? "ready" : phase;

export function AnalystPage({ client = ecommerceWorkshopClient }: { client?: Client }) {
  const [phase, setPhase] = useState<Phase>("loading"); const [response, setResponse] = useState<AnalystViewResponse | null>(null); const [selected, setSelected] = useState<AnalystViewId>("overview"); const request = useRef(0);
  const load = () => { const id = ++request.current; setPhase("loading"); setResponse(null); void client.getAnalystView().then((next) => { if (id !== request.current) return; setResponse(next); setSelected(next.views.find((item) => item.status === "blocked")?.viewId ?? "overview"); setPhase(next.page.count === 0 && next.views.every((item) => item.status === "ready") ? "empty" : "ready"); }, (error: unknown) => { if (id === request.current) setPhase(error instanceof EcommerceWorkshopClientError && (error.status === 401 || error.status === 403) ? "forbidden" : "failed"); }); };
  useEffect(() => { load(); return () => { request.current += 1; }; }, [client]);
  const view = response?.views.find((item) => item.viewId === selected); const readyMetrics = response?.views.reduce((sum, item) => sum + item.countLedger.ready, 0) ?? 0; const totalMetrics = response?.views.reduce((sum, item) => sum + item.countLedger.denominator, 0) ?? 0;
  const content = response && view ? <div className="analyst-read-model">
    <section className="analyst-hero"><div><span>经营参谋 · 增长指挥中心</span><h2>用同一截止面的指标、证据与质量理解经营变化</h2><p>Observation ≠ attribution ≠ causal claim；只展示决策摘要、证据链、归因路径、关键假设和不确定性。</p></div><strong>只读</strong></section>
    <section className="creator-growth-axis"><div><span>只读视图</span><strong>7</strong></div><div><span>可信指标</span><strong>{readyMetrics}/{totalMetrics}</strong></div><div><span>资源 revision</span><strong>r{response.resourceRevision}</strong></div><div><span>写入口</span><strong>0</strong></div></section>
    <div className="analyst-tabs" role="tablist" aria-label="经营参谋只读视图">{response.views.map((item, index) => <button type="button" role="tab" aria-selected={selected === item.viewId} tabIndex={selected === item.viewId ? 0 : -1} key={item.viewId} onClick={() => setSelected(item.viewId)} onKeyDown={(event) => { if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return; event.preventDefault(); const nextIndex = event.key === "Home" ? 0 : event.key === "End" ? response.views.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + response.views.length) % response.views.length; setSelected(response.views[nextIndex]!.viewId); event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>("button")[nextIndex]?.focus(); }}><strong>{LABELS[item.viewId]}</strong><span>{item.status}</span></button>)}</div>
    <section className="analyst-panel" role="tabpanel" aria-label={LABELS[selected]}><header><div><span>{view.viewId}</span><h2>{LABELS[view.viewId]}</h2></div><strong className={`content-campaign-status is-${view.status}`}>{view.status === "ready" ? "同截止面可读" : "失败关闭"}</strong></header><div className="analyst-readiness-grid">{view.readinessAxes.map((axis) => <article key={axis.axis} className={`is-${axis.status}`}><strong>{axis.axis}</strong><span>{axis.status}</span><p>{axis.exactRef ? `${axis.exactRef.resourceType} · r${axis.exactRef.revision}` : "无 exact authority"}</p></article>)}</div><section className="analyst-metrics">{view.metrics.length ? view.metrics.map((metric) => <article key={metric.metricId} className={`is-${metric.status}`}><header><strong>{metric.metricId}</strong><span>{metric.status}</span></header>{metric.status === "ready" ? <><b>{metric.value} {metric.unit}</b><p>{metric.grain} · {metric.window} · {metric.timezone}</p><small>denominator {metric.denominator} · lineage {metric.lineageId}</small></> : <p>当前值未知，不以 0 代替。</p>}</article>) : <p>当前没有可挂接的经营指标；可信空与 blocked/unknown 分开表达。</p>}</section><aside className="media-studio-blockers"><h3>阻断与下一证据</h3>{view.blockers.length ? view.blockers.map((item) => <div key={item.code}><strong>{item.code}</strong><span>{item.dependency}</span><p>{item.requiredAction}</p></div>) : <p>本视图当前无 blocker。</p>}<section><h3>专业贡献归因</h3><ContributionLineage value={{ atomicSkillRef: null, logicRef: null, coworker: null, workshopContribution: CONTRIBUTIONS[view.viewId] }} /><p>当前只读 View 没有 exact AgentRun、SkillBinding 或 LogicRevision；保持 unknown，不把 Analyst authority 冒充数字同事运行事实。</p></section><section><h3>决策摘要</h3><p>{view.status === "ready" ? "当前 exact refs 与同截止面指标可读。" : "依赖 authority 不完整，本视图失败关闭。"}</p></section><section><h3>关键假设和不确定性</h3><p>相关不等于归因，归因不等于因果；页面不展示模型私有思维链，也不授权计划物化或业务动作。</p></section></aside></section>
    <footer className="content-campaign-footnote"><span>租户 {response.tenant.orgId}/{response.tenant.projectId}</span><span>统一 cutoff {new Date(response.dataCutoff).toLocaleString("zh-CN", { hour12: false })}</span><span>unknown 不显示 0</span></footer>
  </div> : null;
  return <section className="analyst-page" aria-label="经营参谋只读视图"><div className="content-campaign-toolbar"><span>Analyst v1 · canonical read model</span><button type="button" onClick={load}>重新读取</button></div><AsyncStateBoundary state={stateFor(phase)} dataCutoff={response?.dataCutoff} action={phase === "failed" ? <button type="button" onClick={load}>重新读取</button> : undefined}>{content}</AsyncStateBoundary></section>;
}
