import { useEffect, useRef, useState } from "react";

import { EcommerceWorkshopClientError, ecommerceWorkshopClient, type CustomerContactContributionViewResponse, type CustomerLifecycleContributionViewResponse, type CustomerViewId, type CustomerViewResponse, type ThreeModuleClosureContributionViewResponse } from "../../api/ecommerceWorkshop";
import { AsyncStateBoundary, type AsyncState } from "./AsyncStateBoundary";
import { ThreeModuleClosureCard, unavailableThreeModuleClosure } from "./ThreeModuleClosureCard";

type Client = Pick<typeof ecommerceWorkshopClient, "getCustomerView" | "getCustomerLifecycleContributionView" | "getCustomerContactContributionView"> & Partial<Pick<typeof ecommerceWorkshopClient, "getThreeModuleClosureContributionView">>;
type Phase = "loading" | "ready" | "empty" | "forbidden" | "failed";
const LABELS: Record<CustomerViewId, string> = { customer: "客户最小投影", segment: "客户分群", journey: "生命周期旅程", dialogue: "对话与批次" };
const CUSTOMER_VIEW_IDS: CustomerViewId[] = ["customer", "segment", "journey", "dialogue"];
const AXIS_LABELS = { customer_lite: "客户最小集", consent: "同意依据", segment: "分群投影", journey: "旅程投影", dialogue: "对话摘要", outreach_batch: "触达批次" } as const;
const STATUS_LABELS: Record<string, string> = { ready: "可读取", blocked: "等待条件", unknown: "待核对", partial: "部分可用", failed: "读取失败", forbidden: "无权访问", eligible: "符合条件", excluded: "已排除", needsReview: "待复核", deduplicated: "已去重", reserved: "已预留", skippedWithdrawn: "已撤回跳过", cancelled: "已取消", accepted: "已受理", applied: "已应用", disputed: "有争议" };
const labelStatus = (value: string) => STATUS_LABELS[value] ?? value;
const stateFor = (phase: Phase): AsyncState => phase === "ready" || phase === "empty" ? "ready" : phase;
const unavailableLifecycle = (next: CustomerViewResponse): CustomerLifecycleContributionViewResponse => ({
  schemaVersion: "aos.ecommerce-workshop.customer-lifecycle/v1", tenant: next.tenant, evaluatedAt: next.evaluatedAt,
  atomicSkillIds: ["build-evidence-pack", "segment-entities", "consent-and-purpose-check", "needs-discovery", "customer-journey-plan", "response-or-outreach-draft", "verify-claims", "review-outcomes"],
  logicId: "ecommerce-customer-relationship", primaryColleague: "私域管家", collaboratorColleagues: ["内容官", "客服专员", "导购顾问", "数据参谋"],
  consentPolicyCount: 0, segmentCount: 0, journeyCount: 0, dialogueCount: 0, latestBatch: null,
  blockers: ["CUSTOMER_LIFECYCLE_CONTRIBUTION_UNAVAILABLE"], allowedCommands: [], contactResolutionAllowed: false, startAllowed: false, sendAllowed: false, externalEffectsAllowed: false,
});
const unavailableContact = (next: CustomerViewResponse): CustomerContactContributionViewResponse => ({
  schemaVersion: "aos.ecommerce-workshop.customer-contact-governance/v1", tenant: next.tenant, evaluatedAt: next.evaluatedAt,
  atomicSkillIds: ["build-evidence-pack", "segment-entities", "consent-and-purpose-check", "needs-discovery", "customer-journey-plan", "response-or-outreach-draft", "verify-claims", "review-outcomes"],
  logicId: "ecommerce-customer-relationship", primaryColleague: "私域管家", collaboratorColleagues: ["内容官", "客服专员", "导购顾问", "数据参谋"],
  latestStart: null, ledger: { frozenEligible: 0, reserved: 0, skippedWithdrawn: 0, cancelled: 0, accepted: 0, applied: 0, failed: 0, unknown: 0, disputed: 0 },
  frequencyPolicyCount: 0, withdrawalCount: 0, blockers: ["CUSTOMER_CONTACT_CONTRIBUTION_UNAVAILABLE"], allowedCommands: [], permitRedemptionAllowed: false, contactResolutionAllowed: false, providerDispatchAllowed: false, sendAllowed: false, externalEffectsAllowed: false,
});

function CustomerFailureSurface() {
  const [selected, setSelected] = useState<CustomerViewId>("customer");
  const [safeAction, setSafeAction] = useState("");
  return <div className="customer-read-model is-failed-read">
    <div className="customer-tabs customer-failure-taskrail" role="tablist" aria-label="客户关系只读视图"><header><strong>今日任务与客户分群</strong><span>数据读取失败 · 可信空</span></header>{CUSTOMER_VIEW_IDS.map((viewId, index) => <button id={`customer-failure-tab-${viewId}`} aria-controls={`customer-failure-panel-${viewId}`} type="button" role="tab" aria-selected={selected === viewId} tabIndex={selected === viewId ? 0 : -1} key={viewId} onClick={() => setSelected(viewId)} onKeyDown={(event) => { if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return; event.preventDefault(); const nextIndex = event.key === "Home" ? 0 : event.key === "End" ? CUSTOMER_VIEW_IDS.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + CUSTOMER_VIEW_IDS.length) % CUSTOMER_VIEW_IDS.length; setSelected(CUSTOMER_VIEW_IDS[nextIndex]!); event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[nextIndex]?.focus(); }}><strong>{LABELS[viewId]}</strong><span>待读取</span></button>)}<section className="customer-failure-segments"><strong>客户分群</strong><div><span>高价值待核对</span><span>潜力待核对</span><span>活跃待核对</span><span>沉睡待核对</span></div><small>当前没有可验证的分群依据，因此不显示人数。</small></section></div>
    <section id={`customer-failure-panel-${selected}`} aria-labelledby={`customer-failure-tab-${selected}`} className="customer-panel" role="tabpanel" aria-label={LABELS[selected]}><header><div><span>客户关系视图</span><h2>{LABELS[selected]}</h2></div><strong className="content-campaign-status is-blocked">读取失败</strong></header>
      <div className="customer-readiness customer-failure-plan"><header><div><span>只读计划</span><h2>客户关系处理计划</h2></div><strong>等待数据</strong></header><p>正式服务未返回可验证客户投影；不以演示客户、联系方式或 0 值补齐。</p>{Object.entries(AXIS_LABELS).map(([axis, label], index) => <article className="is-unknown" key={axis}><i>{index + 1}</i><div><strong>{label}</strong><span>待核对 · 暂无可验证来源</span></div></article>)}<div className="customer-failure-actions"><button type="button" onClick={() => setSafeAction("暂停计划预检：当前没有可暂停的正式计划，未变更任何客户状态。")}>暂停计划</button><button type="button" onClick={() => setSafeAction("重新执行预检：当前没有可执行的正式计划，未创建任务或触发客户触达。")}>重新执行</button><small>操作会先检查正式计划与授权；当前只返回安全预检结果。</small>{safeAction ? <p role="status">{safeAction}</p> : null}</div></div>
      <section className="customer-items" aria-hidden="true" />
      <aside className="media-studio-blockers customer-failure-artifacts"><section><header><span>客户产物</span><h3>可回链产物</h3></header><strong>当前没有可回链产物</strong><p>话术、名单与客户全景均未从正式数据来源返回。</p></section><section><header><span>客户分群</span><h3>客户分层结果</h3></header><div className="customer-failure-segment-grid"><span>高价值<br /><b>待核对</b></span><span>潜力<br /><b>待核对</b></span><span>活跃<br /><b>待核对</b></span><span>沉睡<br /><b>待核对</b></span></div></section><section><header><span>下一步</span><h3>所需数据</h3></header><div><strong>重新读取客户关系数据</strong><span>同一租户、同一数据截止时间</span><p>读取隐私最小化投影，不补造客户记录。</p><details><summary>查看审计状态码</summary><code>CUSTOMER_VIEW_READ_FAILED</code></details></div></section></aside>
    </section>
  </div>;
}

export function CustomerPage({ client = ecommerceWorkshopClient }: { client?: Client }) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [response, setResponse] = useState<CustomerViewResponse | null>(null);
  const [contribution, setContribution] = useState<CustomerLifecycleContributionViewResponse | null>(null);
  const [contact, setContact] = useState<CustomerContactContributionViewResponse | null>(null);
  const [closure, setClosure] = useState<ThreeModuleClosureContributionViewResponse | null>(null);
  const [selected, setSelected] = useState<CustomerViewId>("customer");
  const request = useRef(0);
  const load = () => {
    const id = ++request.current; setPhase("loading"); setResponse(null); setContribution(null); setContact(null); setClosure(null);
    void Promise.all([client.getCustomerView(), client.getCustomerLifecycleContributionView().catch(() => null), client.getCustomerContactContributionView().catch(() => null), client.getThreeModuleClosureContributionView?.("customer").catch(() => null) ?? Promise.resolve(null)]).then(([next, nextContribution, nextContact, nextClosure]) => {
      if (id !== request.current) return;
      setResponse(next); setContribution(nextContribution ?? unavailableLifecycle(next)); setContact(nextContact ?? unavailableContact(next)); setClosure(nextClosure ?? unavailableThreeModuleClosure("customer", next.tenant, next.evaluatedAt));
      setSelected(next.views.find((item) => item.status === "blocked")?.viewId ?? "customer");
      setPhase(next.page.count === 0 && next.views.every((item) => item.status === "ready") ? "empty" : "ready");
    }, (error: unknown) => { if (id === request.current) setPhase(error instanceof EcommerceWorkshopClientError && (error.status === 401 || error.status === 403) ? "forbidden" : "failed"); });
  };
  useEffect(() => { load(); return () => { request.current += 1; }; }, [client]);
  const view = response?.views.find((item) => item.viewId === selected);
  const eligible = response?.views.reduce((sum, item) => sum + item.countLedger.eligible, 0) ?? 0;
  const total = response?.views.reduce((sum, item) => sum + item.countLedger.input, 0) ?? 0;
  const content = response && contribution && contact && closure && view ? <div className="customer-read-model">
    <details className="customer-audit-context">
      <summary>客户治理全过程与累计审计</summary>
      <div className="customer-audit-stack">
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
      {contribution.latestBatch ? <div className="customer-batch-evidence"><header><strong>最近批次 · {labelStatus(contribution.latestBatch.lifecycle)}</strong><span>{contribution.latestBatch.batchId} · r{contribution.latestBatch.revision}</span></header><div>{(["eligible", "excluded", "needsReview", "unknown", "deduplicated"] as const).map((bucket) => <article key={bucket}><span>{labelStatus(bucket)}</span><strong>{contribution.latestBatch!.ledger[bucket]}</strong></article>)}</div><p>联系方式解析 {contribution.latestBatch.contactResolutionCount} · 操作 {contribution.latestBatch.actionCount} · 外部服务调用 {contribution.latestBatch.providerCallCount} · 发送 {contribution.latestBatch.sendCount} · 外部副作用 {contribution.latestBatch.externalEffectCount}</p></div> : <div className="customer-contribution-empty"><strong>尚无可信批次</strong><p>没有可验证的外部策略依据时保持失败关闭；不解析联系方式、不启动、不发送。</p></div>}
      <aside><strong>安全边界</strong><span>联系方式解析：禁用</span><span>启动：禁用</span><span>发送：禁用</span>{contribution.blockers.map((blocker) => <code key={blocker}>{blocker}</code>)}</aside>
    </section>
    <section className="customer-contact-governance" aria-label="客户受控触达治理">
      <header><div><span>受控 Tool / Capability / Action</span><h2>Start、频控、撤回竞态与触达预检</h2></div><strong>{contact.latestStart?.lifecycle ?? "失败关闭"}</strong></header>
      <div className="customer-contribution-counts"><div><span>频控策略</span><strong>{contact.frequencyPolicyCount}</strong></div><div><span>撤回观察</span><strong>{contact.withdrawalCount}</strong></div><div><span>冻结 eligible</span><strong>{contact.ledger.frozenEligible}</strong></div><div><span>治理序号</span><strong>{contact.latestStart?.startSequence ?? "—"}</strong></div></div>
      <div className="customer-contact-ledger">{(["reserved", "skippedWithdrawn", "cancelled", "accepted", "applied", "failed", "unknown", "disputed"] as const).map((bucket) => <article key={bucket}><span>{labelStatus(bucket)}</span><strong>{contact.ledger[bucket]}</strong></article>)}</div>
      <aside><strong>失败关闭安全线</strong><span>Permit 兑换 0 · 联系方式解析 0 · Provider 0 · 发送 0 · 外部副作用 0</span>{contact.blockers.map((blocker) => <code key={blocker}>{blocker}</code>)}</aside>
    </section>
    <ThreeModuleClosureCard value={closure} />
      </div>
    </details>
    <div className="customer-tabs" role="tablist" aria-label="客户关系只读视图">{response.views.map((item, index) => <button id={`customer-tab-${item.viewId}`} aria-controls={`customer-panel-${item.viewId}`} type="button" role="tab" aria-selected={selected === item.viewId} tabIndex={selected === item.viewId ? 0 : -1} key={item.viewId} onClick={() => setSelected(item.viewId)} onKeyDown={(event) => { if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return; event.preventDefault(); const nextIndex = event.key === "Home" ? 0 : event.key === "End" ? response.views.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + response.views.length) % response.views.length; setSelected(response.views[nextIndex]!.viewId); event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>("button")[nextIndex]?.focus(); }}><strong>{LABELS[item.viewId]}</strong><span>{labelStatus(item.status)}</span></button>)}</div>
    <section id={`customer-panel-${selected}`} aria-labelledby={`customer-tab-${selected}`} className="customer-panel" role="tabpanel" aria-label={LABELS[selected]}><header><div><span>客户关系视图</span><h2>{LABELS[view.viewId]}</h2></div><strong className={`content-campaign-status is-${view.status}`}>{view.status === "ready" ? "同截止面可读" : "等待必要条件"}</strong></header>
      <div className="customer-readiness">{view.readinessAxes.map((axis) => <article key={axis.axis} className={`is-${axis.status}`}><strong>{AXIS_LABELS[axis.axis]}</strong><span>{labelStatus(axis.status)}</span><p>{axis.exactRef ? `${axis.exactRef.resourceType} · r${axis.exactRef.revision}` : "暂无可验证来源"}</p></article>)}</div>
      <section className="customer-items">{view.items.length ? view.items.map((item) => <article key={`${item.customerRef.resourceId}:${item.customerRef.revision}`} className={`is-${item.disclosure}`}><header><div><strong>{item.customerRef.resourceType}</strong><span>{item.customerRef.resourceId} · r{item.customerRef.revision}</span></div><b>{item.disclosure}</b></header><dl><div><dt>目的</dt><dd>{item.purpose}</dd></div><div><dt>新鲜度 / 质量</dt><dd>{item.freshness} / {item.quality}</dd></div><div><dt>同意 / 留存</dt><dd>{item.consent} / {item.retention}</dd></div><div><dt>k 匿名 / 原始证据</dt><dd>{item.kAnonymitySatisfied === null ? "待核对" : String(item.kAnonymitySatisfied)} / {item.originalRefs.length}</dd></div></dl></article>) : <p>当前没有可披露的客户最小投影；可信空、等待条件与待核对分别表达。</p>}</section>
      <aside className="media-studio-blockers"><h3>所需条件与下一步</h3>{view.blockers.length ? view.blockers.map((item) => <div key={item.code}><strong>补充同租户、同数据截止的客户最小化正式数据</strong><span>客户关系正式数据来源</span><details><summary>查看审计状态码</summary><code>{item.code}</code><p>{item.requiredAction}</p><p>{item.dependency}</p></details></div>) : <p>本视图当前没有待补条件。</p>}</aside>
    </section>
    <footer className="content-campaign-footnote"><span>租户 {response.tenant.orgId}/{response.tenant.projectId}</span><span>统一数据截止 {new Date(response.dataCutoff).toLocaleString("zh-CN", { hour12: false })}</span><span>同意与留存规则已执行</span></footer>
  </div> : null;
  return <section className="customer-page" aria-label="客户关系只读视图"><div className="content-campaign-toolbar customer-context-strip"><button className="customer-reload-control" type="button" onClick={load}>重新读取</button><span>栖月汇 · 客户状态待核对</span><span>私域管家（负责人未绑定）</span><small>任务驱动 · 只读计划 · 客户产物</small><i aria-hidden="true" /><b>高价值待核对 · 潜力待核对 · 活跃待核对</b><em>沉睡待核对 · 流失预警待核对</em></div>{phase === "failed" ? <CustomerFailureSurface /> : <AsyncStateBoundary state={stateFor(phase)} dataCutoff={response?.dataCutoff}>{content}</AsyncStateBoundary>}</section>;
}
