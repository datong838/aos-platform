import { useEffect, useRef, useState } from "react";

import { EcommerceWorkshopClientError, ecommerceWorkshopClient, type MediaStudioSliceId, type MediaStudioViewResponse } from "../../api/ecommerceWorkshop";
import { AsyncStateBoundary, type AsyncState } from "./AsyncStateBoundary";

type Client = Pick<typeof ecommerceWorkshopClient, "getMediaStudioView">;
type Phase = "loading" | "ready" | "empty" | "forbidden" | "failed";
const LABELS: Record<MediaStudioSliceId, string> = { context: "生产上下文", execution: "职责与执行", delivery: "交付与复盘" };
const stateFor = (phase: Phase): AsyncState => phase === "ready" || phase === "empty" ? "ready" : phase;
const short = (value: string) => value.length > 32 ? `${value.slice(0, 14)}…${value.slice(-11)}` : value;

export function MediaStudioPage({ client = ecommerceWorkshopClient }: { client?: Client }) {
  const [phase, setPhase] = useState<Phase>("loading"); const [response, setResponse] = useState<MediaStudioViewResponse | null>(null); const [selected, setSelected] = useState<MediaStudioSliceId>("context"); const request = useRef(0);
  const load = () => { const id = ++request.current; setPhase("loading"); setResponse(null); void client.getMediaStudioView().then((next) => { if (id !== request.current) return; setResponse(next); setSelected(next.slices.find((item) => item.status === "blocked")?.sliceId ?? "context"); setPhase(next.page.count === 0 && next.slices.every((item) => item.status === "ready") ? "empty" : "ready"); }, (error: unknown) => { if (id === request.current) setPhase(error instanceof EcommerceWorkshopClientError && (error.status === 401 || error.status === 403) ? "forbidden" : "failed"); }); };
  useEffect(() => { load(); return () => { request.current += 1; }; }, [client]);
  const slice = response?.slices.find((item) => item.sliceId === selected); const blocked = response?.slices.reduce((sum, item) => sum + item.blockers.length, 0) ?? 0; const readyAxes = response?.slices.reduce((sum, item) => sum + item.countLedger.ready, 0) ?? 0;
  const content = response && slice ? <div className="media-studio-read-model">
    <section className="media-lifecycle" aria-label="媒体生命周期"><span>prepare</span><span>freeze / confirm</span><span>compile / approve</span><span>start / run</span><span>review / return</span><span>deliver / publish</span><span>reconcile / effect</span></section>
    <section className="creator-growth-axis"><div><span>只读切片</span><strong>3</strong></div><div><span>Ready 轴</span><strong>{readyAxes}/18</strong></div><div><span>独立阻断</span><strong>{blocked}</strong></div><div><span>写入口</span><strong>0</strong></div></section>
    <section className="content-campaign-readonly"><span aria-hidden="true">◇</span><div><h2>媒体生产 · 权威只读</h2><p>target ≠ achieved；Provider submitted ≠ delivered；published、settled 与 effect-reviewed 分轴。</p></div><strong>无写入口</strong></section>
    <section className="content-campaign-items" aria-label="媒体 Provider Job 贡献">
      <header><strong>原子 Skill → Logic 编排 → 数字同事 → 工作台贡献</strong><span>{response.providerJobsStatus}</span></header>
      {response.providerJobs.length ? response.providerJobs.map((job) => <article className="content-campaign-item" key={job.jobId}>
        <header><strong>{job.primaryColleague} · {job.status}</strong><span>seq {job.sequence}</span></header>
        <p>{job.jobId}</p>
        <dl><div><dt>原子能力</dt><dd>{job.atomicCapabilityRef.resourceId}</dd></div><div><dt>Logic / TaskRun</dt><dd>{job.logicRef.resourceId}</dd></div><div><dt>数字同事绑定</dt><dd>{job.colleagueBindingRef.resourceId}</dd></div><div><dt>Provider / Model</dt><dd>{job.providerRef.resourceId} / {job.modelRef.resourceId}</dd></div><div><dt>扫描证据</dt><dd>{job.scanRefs.length}</dd></div><div><dt>外部副作用</dt><dd>关闭</dd></div></dl>
        <small>协作：{job.collaboratorColleagues.join("、")}{job.blockerCodes.length ? `；阻断：${job.blockerCodes.join("、")}` : ""}</small>
      </article>) : <p>{response.providerJobBlockers.map((item) => item.code).join("；") || "当前没有 Provider Job。"}</p>}
    </section>
    <section className="content-campaign-items" aria-label="媒体容量预算用量与结算">
      <header><strong>Capacity / Budget / Usage / Cancel / Settlement</strong><span>{response.mediaFinanceStatus}</span></header>
      {response.mediaFinance.length ? response.mediaFinance.map((item) => <article className="content-campaign-item" key={item.financeId}>
        <header><strong>{item.projectedCurrency} {item.projectedMinMinor}–{item.projectedMaxMinor}</strong><span>{item.settlementStatus}</span></header>
        <p>{item.jobId} · v{item.version}</p>
        <dl><div><dt>Capacity</dt><dd>{item.reservationsActive ? "reserved" : "inactive"}</dd></div><div><dt>Budget</dt><dd>{item.budgetReservationRef.resourceId}</dd></div><div><dt>取消</dt><dd>{item.cancelOutcome ?? "未请求"}</dd></div><div><dt>费用结论</dt><dd>{item.feeConclusion}</dd></div><div><dt>币种桶</dt><dd>{item.currencyBuckets.length}</dd></div><div><dt>外部副作用</dt><dd>关闭</dd></div></dl>
        {item.currencyBuckets.map((bucket) => <small key={bucket.currency}>{bucket.currency}：measured {bucket.measuredMinor} / estimated {bucket.estimatedMinor} / unknown {bucket.unknownCount} / adjustment {bucket.adjustmentMinor} / refund {bucket.refundMinor} / residual {bucket.residualMinor ?? "unknown"}</small>)}
        {item.blockerCodes.length ? <small>阻断：{item.blockerCodes.join("、")}</small> : null}
      </article>) : <p>{response.mediaFinanceBlockers.map((item) => item.code).join("；") || "当前没有媒体财务 attempt。"}</p>}
    </section>
    <div className="media-studio-tabs" role="tablist" aria-label="媒体只读切片">{response.slices.map((item) => <button role="tab" aria-selected={selected === item.sliceId} type="button" key={item.sliceId} onClick={() => setSelected(item.sliceId)}><strong>{LABELS[item.sliceId]}</strong><span>{item.status}</span></button>)}</div>
    <section className="media-studio-panel" role="tabpanel" aria-label={LABELS[selected]}><header><div><span>{slice.sliceId}</span><h2>{LABELS[slice.sliceId]}</h2></div><strong className={`content-campaign-status is-${slice.status}`}>{slice.status === "ready" ? "权威读取可用" : "失败关闭"}</strong></header><div className="media-readiness-grid">{slice.readinessAxes.map((axis) => <article key={axis.axis} className={`is-${axis.status}`}><header><strong>{axis.axis}</strong><span>{axis.status}</span></header>{axis.exactRef ? <p>{axis.exactRef.resourceType} · {short(axis.exactRef.contentHash)}</p> : <p>{axis.targetContractRef ?? "无 exact authority"}</p>}<small>{axis.gaps.join("；") || "exact authority 已校验"}</small></article>)}</div><section className="content-campaign-items">{slice.authorityRefs.length ? slice.authorityRefs.map((item) => <article className="content-campaign-item" key={`${item.resourceType}:${item.resourceId}:${item.revision}`}><header><strong>{item.resourceType}</strong><span>r{item.revision}</span></header><p>{item.resourceId}</p><dl><div><dt>Exact hash</dt><dd>{short(item.contentHash)}</dd></div><div><dt>Receipt</dt><dd>{short(item.receiptId)}</dd></div></dl></article>) : <p>当前没有可挂接的媒体 authority；可信空与 target/blocked 不混淆。</p>}</section><aside className="media-studio-blockers"><h3>阻断与所需证据</h3>{slice.blockers.length ? slice.blockers.map((item) => <div key={item.code}><strong>{item.code}</strong><span>{item.dependency}</span><p>{item.requiredAction}</p></div>) : <p>本切片当前无 blocker。</p>}</aside></section>
    <footer className="content-campaign-footnote"><span>租户 {response.tenant.orgId}/{response.tenant.projectId}</span><span>统一 cutoff {new Date(response.dataCutoff).toLocaleString("zh-CN", { hour12: false })}</span><span>无后续页：是</span></footer>
  </div> : null;
  return <section className="media-studio-page" aria-label="多媒体工作台只读视图"><div className="content-campaign-toolbar"><span>Media Studio v3 · canonical contribution and settlement read model</span><button type="button" onClick={load}>重新读取</button></div><AsyncStateBoundary state={stateFor(phase)} dataCutoff={response?.dataCutoff} action={phase === "failed" ? <button type="button" onClick={load}>重新读取</button> : undefined}>{content}</AsyncStateBoundary></section>;
}
