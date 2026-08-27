import { useEffect, useRef, useState } from "react";

import { EcommerceWorkshopClientError, ecommerceWorkshopClient, type ContentCampaignItem, type ContentCampaignSlice, type ContentCampaignSliceId, type ContentCampaignViewResponse } from "../../api/ecommerceWorkshop";
import { AsyncStateBoundary, type AsyncState } from "./AsyncStateBoundary";
import { ContributionLineage } from "./production";

type Client = Pick<typeof ecommerceWorkshopClient, "getContentCampaignView">;
type Phase = "loading" | "ready" | "empty" | "forbidden" | "failed";
const LABELS: Record<ContentCampaignSliceId, string> = { plan: "活动计划", calendar: "内容日历", content: "主内容与变体" };
const TAB_LABELS: Record<ContentCampaignSliceId, string> = { plan: "活动策划", calendar: "内容日历", content: "日常模板" };
const DESCRIPTIONS: Record<ContentCampaignSliceId, string> = { plan: "CampaignRevision", calendar: "CalendarEntryRevision", content: "MasterContentIntentRevision · ContentVariant" };
const CONTRIBUTIONS: Record<ContentCampaignSliceId, string> = {
  plan: "以 CampaignRevision 为内容与活动规划的领域事实输入",
  calendar: "以 CalendarEntryRevision 表达排期意图；不等同于发布",
  content: "以 MasterContentIntent 与 Artifact lineage 重建 ContentVariant",
};
const stateFor = (phase: Phase): AsyncState => phase === "ready" || phase === "empty" ? "ready" : phase;
const formatTime = (value: string) => new Date(value).toLocaleString("zh-CN", { hour12: false });
const short = (value: string) => value.length > 34 ? `${value.slice(0, 15)}…${value.slice(-12)}` : value;

function ItemCard({ item }: { item: ContentCampaignItem }) {
  const variant = "intentRef" in item;
  return <article className={`content-campaign-item${variant ? " is-variant" : ""}`}>
    <header><strong>{item.resourceType}</strong><span>r{item.revision}</span></header>
    <p title={item.resourceId}>{item.resourceId}</p>
    <dl><div><dt>Exact hash</dt><dd title={item.contentHash}>{short(item.contentHash)}</dd></div><div><dt>Receipt</dt><dd title={item.receiptId}>{short(item.receiptId)}</dd></div>{variant ? <><div><dt>归因路径</dt><dd>{item.relationType} · {item.relationId}</dd></div><div><dt>Master → Variant</dt><dd>{short(item.masterArtifactRef.artifactId)} → {short(item.variantArtifactRef.artifactId)}</dd></div></> : null}</dl>
  </article>;
}

export function ContentCampaignPage({ client = ecommerceWorkshopClient }: { client?: Client }) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [response, setResponse] = useState<ContentCampaignViewResponse | null>(null);
  const [selected, setSelected] = useState<ContentCampaignSliceId>("plan");
  const request = useRef(0);
  const load = () => { const id = ++request.current; setPhase("loading"); setResponse(null); void client.getContentCampaignView().then((next) => { if (id !== request.current) return; setResponse(next); setSelected(next.slices.find((item) => item.status === "blocked")?.sliceId ?? next.slices.find((item) => item.items.length > 0)?.sliceId ?? "plan"); setPhase(next.page.count === 0 && next.slices.every((item) => item.status === "ready") ? "empty" : "ready"); }, (error: unknown) => { if (id === request.current) setPhase(error instanceof EcommerceWorkshopClientError && (error.status === 401 || error.status === 403) ? "forbidden" : "failed"); }); };
  useEffect(() => { load(); return () => { request.current += 1; }; }, [client]);
  const slice: ContentCampaignSlice | undefined = response?.slices.find((item) => item.sliceId === selected);
  const ready = response?.slices.filter((item) => item.status === "ready").length ?? 0;
  const eligible = response?.slices.reduce((sum, item) => sum + item.countLedger.eligible, 0) ?? 0;
  const unmatched = response?.slices.reduce((sum, item) => sum + item.countLedger.unmatched + item.countLedger.conflicted, 0) ?? 0;
  const content = response && slice ? <div className="content-campaign-read-model">
    <div className="content-campaign-board">
      <aside className="content-campaign-nav"><header><h2>主视图</h2><span>{3 - ready} 项阻断</span></header>{response.slices.map((item) => <button type="button" key={item.sliceId} className={`content-campaign-slice is-${item.status}${item.sliceId === slice.sliceId ? " is-selected" : ""}`} aria-pressed={item.sliceId === slice.sliceId} onClick={() => setSelected(item.sliceId)}><strong>{LABELS[item.sliceId]}</strong><small>{DESCRIPTIONS[item.sliceId]}</small><span>{item.countLedger.attached} / {item.countLedger.eligible}</span></button>)}</aside>
      <section className="content-campaign-detail" aria-label="内容与活动详情"><section className="content-campaign-visual-intent"><div><strong>AI 策划助手</strong><span>仅消费当前 canonical authority</span></div><div><textarea aria-label="活动意图" readOnly value="当前没有可编辑活动意图；请选择具有 exact authority 的计划" /><button type="button" disabled>生成方案</button></div></section><header><div><span>{slice.sliceId}</span><h2>{LABELS[slice.sliceId]}</h2></div><strong className={`content-campaign-status is-${slice.status}`}>{slice.status === "ready" ? "权威读取可用" : "失败关闭"}</strong></header><section className="content-campaign-ledger"><div><span>可评估</span><strong>{slice.countLedger.eligible}</strong></div><div><span>已挂接</span><strong>{slice.countLedger.attached}</strong></div><div><span>未匹配</span><strong>{slice.countLedger.unmatched}</strong></div><div><span>冲突</span><strong>{slice.countLedger.conflicted}</strong></div></section><section className="content-campaign-items" aria-label={`${LABELS[slice.sliceId]} exact facts`}>{slice.items.length ? slice.items.map((item) => <ItemCard item={item} key={`${item.resourceType}:${item.resourceId}:${item.revision}`} />) : <p>当前没有合格的已挂接事实；可信空与阻断由右侧证据区分。</p>}</section></section>
      <aside className="content-campaign-evidence"><header><h2>证据链 · 边界</h2><span>{slice.blockers.length} blocker</span></header>{slice.blockers.length ? <ul>{slice.blockers.map((blocker) => <li key={blocker.code}><strong>{blocker.code}</strong><span>{blocker.dependency}</span><p>{blocker.requiredAction}</p></li>)}</ul> : <div className="content-campaign-evidence-clear"><strong>{slice.items.length ? "当前读取链闭合" : "可信空集合"}</strong><p>只证明当前 cutoff 的 canonical reader 结果，不授权内容生产、排期或发布。</p></div>}<section><h3>专业贡献归因</h3><ContributionLineage value={{ atomicSkillRef: null, logicRef: null, coworker: null, workshopContribution: CONTRIBUTIONS[slice.sliceId] }} /><p>当前 View 没有 exact AgentRun、SkillBinding 或 LogicRevision；保持 unknown，不制造数字同事运行事实。</p></section><section><h3>决策摘要</h3><p>{slice.status === "blocked" ? "依赖证据不完整，切片失败关闭。" : "exact authority 与数量账本可读取。"}</p></section><section><h3>关键假设和不确定性</h3><p>页面不展示正文、prompt、Provider、客户 PII，也不把代码 GREEN 推断为运营 GREEN。</p></section></aside>
    </div><details className="content-campaign-audit-context"><summary>数量守恒与只读边界</summary><section className="content-campaign-metrics" aria-label="内容活动数量守恒"><div><span>权威切片</span><strong>3</strong><small>固定 canonical order</small></div><div><span>读取可用</span><strong>{ready}</strong><small>其余失败关闭</small></div><div><span>可评估</span><strong>{eligible}</strong><small>非示例业务数</small></div><div><span>已挂接</span><strong>{response.page.count}</strong><small>等于三切片 items</small></div><div><span>待核对</span><strong>{unmatched}</strong><small>未匹配 + 冲突</small></div><div><span>数据截止</span><strong>{formatTime(response.dataCutoff)}</strong><small>统一 cutoff</small></div></section><section className="content-campaign-readonly"><div><h2>内容与活动 · 权威只读</h2><p>仅呈现 Campaign、Calendar、Master Intent 与 ContentVariant exact lineage；不批准、不排期、不发布。</p></div><strong>无写入口</strong></section></details><footer className="content-campaign-footnote"><span>租户 {response.tenant.orgId}/{response.tenant.projectId}</span><span>评估 {formatTime(response.evaluatedAt)}</span><span>无后续页：是</span></footer>
  </div> : null;
  return <section className="content-campaign-page" aria-label="内容与活动工作台只读视图"><nav className="content-campaign-toolbar" aria-label="内容与活动主视图"><div>{(["plan", "calendar", "content"] as const).map((sliceId) => <button type="button" className={selected === sliceId ? "is-active" : ""} key={sliceId} onClick={() => setSelected(sliceId)}>{TAB_LABELS[sliceId]}</button>)}</div><span>canonical read-only</span><button type="button" onClick={load}>重新读取</button></nav><AsyncStateBoundary state={stateFor(phase)} dataCutoff={response?.dataCutoff} action={phase === "failed" ? <button type="button" onClick={load}>重新读取</button> : undefined}>{content}</AsyncStateBoundary></section>;
}
