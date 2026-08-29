import { useEffect, useRef, useState } from "react";

import { EcommerceWorkshopClientError, ecommerceWorkshopClient, type ContentCampaignItem, type ContentCampaignSlice, type ContentCampaignSliceId, type ContentCampaignViewResponse } from "../../api/ecommerceWorkshop";
import { AsyncStateBoundary, type AsyncState } from "./AsyncStateBoundary";
import { ContributionLineage } from "./production";

type Client = Pick<typeof ecommerceWorkshopClient, "getContentCampaignView">;
type Phase = "loading" | "ready" | "empty" | "forbidden" | "failed";
const LABELS: Record<ContentCampaignSliceId, string> = { plan: "活动计划", calendar: "内容日历", content: "主内容与变体" };
const TAB_LABELS: Record<ContentCampaignSliceId, string> = { plan: "活动策划", calendar: "内容日历", content: "日常模板" };
const DESCRIPTIONS: Record<ContentCampaignSliceId, string> = { plan: "活动目标与节奏", calendar: "日期、渠道与负责人", content: "主内容与渠道版本" };
const CONTRIBUTIONS: Record<ContentCampaignSliceId, string> = {
  plan: "以正式活动计划作为内容与活动规划依据",
  calendar: "呈现活动排期意图，不代表已经发布",
  content: "按主内容与渠道版本展示内容关系",
};
const stateFor = (phase: Phase): AsyncState => phase === "ready" || phase === "empty" ? "ready" : phase;
const formatTime = (value: string) => new Date(value).toLocaleString("zh-CN", { hour12: false });
const short = (value: string) => value.length > 34 ? `${value.slice(0, 15)}…${value.slice(-12)}` : value;

function ItemCard({ item }: { item: ContentCampaignItem }) {
  const variant = "intentRef" in item;
  return <article className={`content-campaign-item${variant ? " is-variant" : ""}`}>
    <header><strong>正式活动数据</strong><span>第 {item.revision} 版</span></header>
    <p>该业务记录已通过当前租户的数据边界校验。</p>
    <details><summary>查看数据审计信息</summary><dl><div><dt>数据类型</dt><dd>{item.resourceType}</dd></div><div><dt>数据编号</dt><dd title={item.resourceId}>{item.resourceId}</dd></div><div><dt>内容校验</dt><dd title={item.contentHash}>{short(item.contentHash)}</dd></div><div><dt>读取凭证</dt><dd title={item.receiptId}>{short(item.receiptId)}</dd></div>{variant ? <><div><dt>归因路径</dt><dd>{item.relationType} · {item.relationId}</dd></div><div><dt>主内容与渠道版本</dt><dd>{short(item.masterArtifactRef.artifactId)} → {short(item.variantArtifactRef.artifactId)}</dd></div></> : null}</dl></details>
  </article>;
}

export function ContentCampaignPage({ client = ecommerceWorkshopClient }: { client?: Client }) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [response, setResponse] = useState<ContentCampaignViewResponse | null>(null);
  const [selected, setSelected] = useState<ContentCampaignSliceId>("plan");
  const [safeAction, setSafeAction] = useState("");
  const request = useRef(0);
  const load = () => { const id = ++request.current; setPhase("loading"); setResponse(null); void client.getContentCampaignView().then((next) => { if (id !== request.current) return; setResponse(next); setSelected(next.slices.find((item) => item.status === "blocked")?.sliceId ?? next.slices.find((item) => item.items.length > 0)?.sliceId ?? "plan"); setPhase(next.page.count === 0 && next.slices.every((item) => item.status === "ready") ? "empty" : "ready"); }, (error: unknown) => { if (id === request.current) setPhase(error instanceof EcommerceWorkshopClientError && (error.status === 401 || error.status === 403) ? "forbidden" : "failed"); }); };
  useEffect(() => { load(); return () => { request.current += 1; }; }, [client]);
  const slice: ContentCampaignSlice | undefined = response?.slices.find((item) => item.sliceId === selected);
  const ready = response?.slices.filter((item) => item.status === "ready").length ?? 0;
  const eligible = response?.slices.reduce((sum, item) => sum + item.countLedger.eligible, 0) ?? 0;
  const unmatched = response?.slices.reduce((sum, item) => sum + item.countLedger.unmatched + item.countLedger.conflicted, 0) ?? 0;
  const content = response && slice ? <div className="content-campaign-read-model">
    <div className="content-campaign-board">
      <aside className="content-campaign-nav"><header><h2>主视图</h2><span>{3 - ready} 项待补条件</span></header>{response.slices.map((item) => <button type="button" key={item.sliceId} className={`content-campaign-slice is-${item.status}${item.sliceId === slice.sliceId ? " is-selected" : ""}`} aria-pressed={item.sliceId === slice.sliceId} onClick={() => setSelected(item.sliceId)}><strong>{LABELS[item.sliceId]}</strong><small>{DESCRIPTIONS[item.sliceId]}</small><span>{item.countLedger.attached} / {item.countLedger.eligible}</span></button>)}</aside>
      <section className="content-campaign-detail" aria-label="内容与活动详情">
        <section className="content-campaign-visual-intent"><div><strong>AI 策划助手</strong><span>仅消费当前正式业务数据</span></div><div><textarea aria-label="活动意图" readOnly value="当前没有可编辑活动意图；请选择具有可验证来源的计划" /><button type="button" onClick={() => setSafeAction("生成方案预检：当前没有可提交的活动意图，因此未生成内容、预算或发布任务。")}>生成方案</button></div></section>
        <section className={`content-campaign-assistant-summary is-${slice.status}`} aria-label="AI 策划结论"><div><strong>{slice.status === "ready" ? "当前正式数据可供审阅" : "尚未形成可审阅方案"}</strong><span>{slice.status === "ready" ? "只读呈现正式业务事实，不代表已批准或发布。" : "正式数据来源未闭合，助手不生成活动、预算、经营指标或风险建议。"}</span></div><em>{slice.status === "ready" ? "只读" : "等待数据"}</em></section>
        <section className="content-campaign-overview" aria-label="活动概览"><header><div><span>当前业务视图</span><h2>活动概览</h2></div><strong className={`content-campaign-status is-${slice.status}`}>{slice.status === "ready" ? "正式数据可读" : "等待数据"}</strong></header><p className="content-campaign-overview-title"><strong>{LABELS[slice.sliceId]}</strong><span>{slice.status === "ready" ? "正式业务数据已挂接" : "等待正式业务数据"}</span></p><section className="content-campaign-ledger"><div><span>可评估</span><strong>{slice.countLedger.eligible}</strong></div><div><span>已挂接</span><strong>{slice.countLedger.attached}</strong></div><div><span>未匹配</span><strong>{slice.countLedger.unmatched}</strong></div><div><span>冲突</span><strong>{slice.countLedger.conflicted}</strong></div></section><section className="content-campaign-items" aria-label={`${LABELS[slice.sliceId]}正式数据`}>{slice.items.length ? slice.items.map((item) => <ItemCard item={item} key={`${item.resourceType}:${item.resourceId}:${item.revision}`} />) : <p>当前没有合格的正式业务数据；空数据与待补条件由右侧证据区分。</p>}</section></section>
        <footer className="content-campaign-actionbar" aria-label="活动审批操作"><div><strong>{slice.status === "ready" ? "只读审阅" : "等待正式数据"}</strong><span>操作会先执行安全预检；当前不会创建草稿、重新生成或发布。</span></div><div><button type="button" onClick={() => setSafeAction("保存草稿预检：当前没有可保存的正式活动内容，未创建草稿。")}>保存为草稿</button><button type="button" onClick={() => setSafeAction("重新生成预检：当前没有可回链的活动意图，未启动生成任务。")}>重新生成</button><button type="button" onClick={() => setSafeAction("发布预检：当前缺少可验证方案与审批结果，未发布任何内容。")}>批准并发布</button></div></footer>
      </section>
      <aside className="content-campaign-evidence"><header><h2>证据链 · 边界</h2><span>{slice.blockers.length} 项待补条件</span></header>{slice.blockers.length ? <ul>{slice.blockers.map((blocker) => <li key={blocker.code}><strong>补充同一数据截止面的正式业务数据</strong><span>当前不能形成活动方案</span><details><summary>查看数据审计信息</summary><p>{blocker.requiredAction}</p><p>{blocker.dependency}</p><code>{blocker.code}</code></details></li>)}</ul> : <div className="content-campaign-evidence-clear"><strong>{slice.items.length ? "当前读取链闭合" : "可信空集合"}</strong><p>只证明当前数据截止面的正式读取结果，不授权内容生产、排期或发布。</p></div>}<section><h3>专业贡献归因</h3><ContributionLineage value={{ atomicSkillRef: null, logicRef: null, coworker: null, workshopContribution: CONTRIBUTIONS[slice.sliceId] }} /><p>当前视图没有可验证的数字同事运行记录，因此不制造运行事实。</p></section><section><h3>决策摘要</h3><p>{slice.status === "blocked" ? "所需证据不完整，当前保持可信空。" : "正式数据来源与数量账本可读取。"}</p></section><section><h3>关键假设和不确定性</h3><p>页面不展示正文、提示词、外部服务信息或客户敏感信息，也不把代码通过推断为运营可用。</p></section><details className="content-campaign-audit-context"><summary>数量守恒与只读边界</summary><p className="content-campaign-audit-compat">原子 Skill · Logic 编排 · Master → Variant</p><section className="content-campaign-metrics" aria-label="内容活动数量守恒"><div><span>权威切片</span><strong>3</strong><small>固定 canonical order</small></div><div><span>读取可用</span><strong>{ready}</strong><small>其余失败关闭</small></div><div><span>可评估</span><strong>{eligible}</strong><small>非示例业务数</small></div><div><span>已挂接</span><strong>{response.page.count}</strong><small>等于三切片 items</small></div><div><span>待核对</span><strong>{unmatched}</strong><small>未匹配 + 冲突</small></div><div><span>数据截止</span><strong>{formatTime(response.dataCutoff)}</strong><small>统一 cutoff</small></div></section><section className="content-campaign-readonly"><div><h2>内容与活动 · 权威只读</h2><p>仅呈现 Campaign、Calendar、Master Intent 与 ContentVariant exact lineage；不批准、不排期、不发布。</p></div><strong>无写入口</strong></section></details><footer className="content-campaign-footnote"><span>租户 {response.tenant.orgId}/{response.tenant.projectId}</span><span>评估 {formatTime(response.evaluatedAt)}</span><span>无后续页：是</span><button type="button" onClick={load}>重新读取</button></footer></aside>
    </div>
  </div> : null;
  return <section className="content-campaign-page" aria-label="内容与活动工作台只读视图"><nav className="content-campaign-toolbar" aria-label="内容与活动主视图"><div>{(["plan", "calendar", "content"] as const).map((sliceId) => <button type="button" className={selected === sliceId ? "is-active" : ""} key={sliceId} onClick={() => setSelected(sliceId)}>{TAB_LABELS[sliceId]}</button>)}</div><span>栖月汇微商城</span><button type="button" title="先执行安全预检" onClick={() => setSafeAction("新建活动预检：当前没有可提交的活动意图，未创建业务记录。")}>＋ 新建活动</button></nav>{safeAction ? <div className="content-campaign-safe-action" role="status"><span>{safeAction}</span><button type="button" aria-label="关闭操作提示" onClick={() => setSafeAction("")}>×</button></div> : null}<AsyncStateBoundary state={stateFor(phase)} dataCutoff={response?.dataCutoff} action={phase === "failed" ? <button type="button" onClick={load}>重新读取</button> : undefined}>{content}</AsyncStateBoundary></section>;
}
