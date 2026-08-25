import { useEffect, useRef, useState } from "react";

import { EcommerceWorkshopClientError, ecommerceWorkshopClient, type CustomerContactContributionViewResponse, type CustomerLifecycleContributionViewResponse, type CustomerViewId, type CustomerViewResponse } from "../../api/ecommerceWorkshop";
import { AsyncStateBoundary, type AsyncState } from "./AsyncStateBoundary";

type Client = Pick<typeof ecommerceWorkshopClient, "getCustomerView" | "getCustomerLifecycleContributionView" | "getCustomerContactContributionView">;
type Phase = "loading" | "ready" | "empty" | "forbidden" | "failed";
const LABELS: Record<CustomerViewId, string> = { customer: "客户最小投影", segment: "客户分群", journey: "生命周期旅程", dialogue: "对话与批次" };
const AXIS_LABELS = { customer_lite: "客户最小集", consent: "同意依据", segment: "分群投影", journey: "旅程投影", dialogue: "对话摘要", outreach_batch: "触达批次" } as const;
const stateFor = (phase: Phase): AsyncState => phase === "ready" || phase === "empty" ? "ready" : phase;

export function CustomerPage({ client = ecommerceWorkshopClient }: { client?: Client }) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [response, setResponse] = useState<CustomerViewResponse | null>(null);
  const [contribution, setContribution] = useState<CustomerLifecycleContributionViewResponse | null>(null);
  const [contact, setContact] = useState<CustomerContactContributionViewResponse | null>(null);
  const [selected, setSelected] = useState<CustomerViewId>("customer");
  const request = useRef(0);
  const load = () => {
    const id = ++request.current; setPhase("loading"); setResponse(null); setContribution(null); setContact(null);
    void Promise.all([client.getCustomerView(), client.getCustomerLifecycleContributionView(), client.getCustomerContactContributionView()]).then(([next, nextContribution, nextContact]) => {
      if (id !== request.current) return;
      setResponse(next); setContribution(nextContribution); setContact(nextContact);
      setSelected(next.views.find((item) => item.status === "blocked")?.viewId ?? "customer");
      setPhase(next.page.count === 0 && next.views.every((item) => item.status === "ready") ? "empty" : "ready");
    }, (error: unknown) => { if (id === request.current) setPhase(error instanceof EcommerceWorkshopClientError && (error.status === 401 || error.status === 403) ? "forbidden" : "failed"); });
  };
  useEffect(() => { load(); return () => { request.current += 1; }; }, [client]);
  const view = response?.views.find((item) => item.viewId === selected);
  const eligible = response?.views.reduce((sum, item) => sum + item.countLedger.eligible, 0) ?? 0;
  const total = response?.views.reduce((sum, item) => sum + item.countLedger.input, 0) ?? 0;
  const content = response && contribution && contact && view ? <div className="customer-read-model">
    <section className="customer-hero"><div><span>客户关系工作台 · 最小披露</span><h2>只在目的、同意与留存边界内阅读客户关系</h2><p>同意撤回、留存到期、质量失败或来源不可核验都会失败关闭；页面不展示联系方式和身份字段。</p></div><strong>只读 · 零触达</strong></section>
    <section className="creator-growth-axis"><div><span>只读视图</span><strong>4</strong></div><div><span>允许披露</span><strong>{eligible}/{total}</strong></div><div><span>资源 revision</span><strong>r{response.resourceRevision}</strong></div><div><span>写入口</span><strong>0</strong></div></section>
    <section className="customer-contribution" aria-label="客户关系贡献视图">
      <header><div><span>原子 Skill → Logic → 数字同事</span><h2>客户关系生产贡献链</h2></div><strong>外部副作用 0</strong></header>
      <div className="customer-contribution-flow">
        <article><span>原子 Skill · {contribution.atomicSkillIds.length}</span><div>{contribution.atomicSkillIds.map((skillId) => <code key={skillId}>{skillId}</code>)}</div></article>
        <article><span>Logic 编排</span><strong>{contribution.logicId}</strong><p>同意与目的校验贯穿分群、旅程、对话草案和批次准备。</p></article>
        <article><span>主责数字同事</span><strong>{contribution.primaryColleague}</strong><p>协作：{contribution.collaboratorColleagues.join(" · ")}</p></article>
      </div>
      <div className="customer-contribution-counts"><div><span>同意策略</span><strong>{contribution.consentPolicyCount}</strong></div><div><span>分群</span><strong>{contribution.segmentCount}</strong></div><div><span>旅程</span><strong>{contribution.journeyCount}</strong></div><div><span>对话策略</span><strong>{contribution.dialogueCount}</strong></div></div>
      {contribution.latestBatch ? <div className="customer-batch-evidence"><header><strong>最近批次 · {contribution.latestBatch.lifecycle}</strong><span>{contribution.latestBatch.batchId} · r{contribution.latestBatch.revision}</span></header><div>{(["eligible", "excluded", "needsReview", "unknown", "deduplicated"] as const).map((bucket) => <article key={bucket}><span>{bucket}</span><strong>{contribution.latestBatch!.ledger[bucket]}</strong></article>)}</div><p>联系方式解析 {contribution.latestBatch.contactResolutionCount} · Action {contribution.latestBatch.actionCount} · Provider {contribution.latestBatch.providerCallCount} · 发送 {contribution.latestBatch.sendCount} · 外部副作用 {contribution.latestBatch.externalEffectCount}</p></div> : <div className="customer-contribution-empty"><strong>尚无可信批次</strong><p>没有 exact 外部策略 authority 时保持失败关闭；不解析联系方式、不启动、不发送。</p></div>}
      <aside><strong>安全边界</strong><span>联系方式解析：禁用</span><span>启动：禁用</span><span>发送：禁用</span>{contribution.blockers.map((blocker) => <code key={blocker}>{blocker}</code>)}</aside>
    </section>
    <section className="customer-contact-governance" aria-label="客户受控触达治理">
      <header><div><span>受控 Tool / Capability / Action</span><h2>Start、频控、撤回竞态与触达预检</h2></div><strong>{contact.latestStart?.lifecycle ?? "失败关闭"}</strong></header>
      <div className="customer-contribution-counts"><div><span>频控策略</span><strong>{contact.frequencyPolicyCount}</strong></div><div><span>撤回观察</span><strong>{contact.withdrawalCount}</strong></div><div><span>冻结 eligible</span><strong>{contact.ledger.frozenEligible}</strong></div><div><span>治理序号</span><strong>{contact.latestStart?.startSequence ?? "—"}</strong></div></div>
      <div className="customer-contact-ledger">{(["reserved", "skippedWithdrawn", "cancelled", "accepted", "applied", "failed", "unknown", "disputed"] as const).map((bucket) => <article key={bucket}><span>{bucket}</span><strong>{contact.ledger[bucket]}</strong></article>)}</div>
      <aside><strong>失败关闭安全线</strong><span>Permit 兑换 0 · 联系方式解析 0 · Provider 0 · 发送 0 · 外部副作用 0</span>{contact.blockers.map((blocker) => <code key={blocker}>{blocker}</code>)}</aside>
    </section>
    <div className="customer-tabs" role="tablist" aria-label="客户关系只读视图">{response.views.map((item, index) => <button type="button" role="tab" aria-selected={selected === item.viewId} tabIndex={selected === item.viewId ? 0 : -1} key={item.viewId} onClick={() => setSelected(item.viewId)} onKeyDown={(event) => { if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return; event.preventDefault(); const nextIndex = event.key === "Home" ? 0 : event.key === "End" ? response.views.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + response.views.length) % response.views.length; setSelected(response.views[nextIndex]!.viewId); event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>("button")[nextIndex]?.focus(); }}><strong>{LABELS[item.viewId]}</strong><span>{item.status}</span></button>)}</div>
    <section className="customer-panel" role="tabpanel" aria-label={LABELS[selected]}><header><div><span>{view.viewId}</span><h2>{LABELS[view.viewId]}</h2></div><strong className={`content-campaign-status is-${view.status}`}>{view.status === "ready" ? "同截止面可读" : "失败关闭"}</strong></header>
      <div className="customer-readiness">{view.readinessAxes.map((axis) => <article key={axis.axis} className={`is-${axis.status}`}><strong>{AXIS_LABELS[axis.axis]}</strong><span>{axis.status}</span><p>{axis.exactRef ? `${axis.exactRef.resourceType} · r${axis.exactRef.revision}` : "无 exact authority"}</p></article>)}</div>
      <section className="customer-items">{view.items.length ? view.items.map((item) => <article key={`${item.customerRef.resourceId}:${item.customerRef.revision}`} className={`is-${item.disclosure}`}><header><div><strong>{item.customerRef.resourceType}</strong><span>{item.customerRef.resourceId} · r{item.customerRef.revision}</span></div><b>{item.disclosure}</b></header><dl><div><dt>目的</dt><dd>{item.purpose}</dd></div><div><dt>新鲜度 / 质量</dt><dd>{item.freshness} / {item.quality}</dd></div><div><dt>同意 / 留存</dt><dd>{item.consent} / {item.retention}</dd></div><div><dt>k 匿名 / 原始证据</dt><dd>{item.kAnonymitySatisfied === null ? "unknown" : String(item.kAnonymitySatisfied)} / {item.originalRefs.length}</dd></div></dl></article>) : <p>当前没有可披露的客户最小投影；可信空与 blocked/unknown 分开表达。</p>}</section>
      <aside className="media-studio-blockers"><h3>阻断与下一证据</h3>{view.blockers.length ? view.blockers.map((item) => <div key={item.code}><strong>{item.code}</strong><span>{item.dependency}</span><p>{item.requiredAction}</p></div>) : <p>本视图当前无 blocker。</p>}</aside>
    </section>
    <footer className="content-campaign-footnote"><span>租户 {response.tenant.orgId}/{response.tenant.projectId}</span><span>统一 cutoff {new Date(response.dataCutoff).toLocaleString("zh-CN", { hour12: false })}</span><span>consent + retention enforced</span></footer>
  </div> : null;
  return <section className="customer-page" aria-label="客户关系只读视图"><div className="content-campaign-toolbar"><span>Customer View v1 · privacy-minimized</span><button type="button" onClick={load}>重新读取</button></div><AsyncStateBoundary state={stateFor(phase)} dataCutoff={response?.dataCutoff} action={phase === "failed" ? <button type="button" onClick={load}>重新读取</button> : undefined}>{content}</AsyncStateBoundary></section>;
}
