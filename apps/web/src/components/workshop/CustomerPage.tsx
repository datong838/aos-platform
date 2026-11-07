import { useEffect, useRef, useState } from "react";

import { aipActionsSdk, type AipActionsSdk } from "../../api/aipActions/client";
import type { ActionDraftBundle, ActionProposalTimeline } from "../../api/aipActions/contracts";
import { EcommerceWorkshopClientError, ecommerceWorkshopClient, type CustomerContactContributionViewResponse, type CustomerLifecycleContributionViewResponse, type CustomerProjection, type CustomerViewId, type CustomerViewResponse, type CustomerViewSlice, type ThreeModuleClosureContributionViewResponse } from "../../api/ecommerceWorkshop";
import { AsyncStateBoundary, type AsyncState } from "./AsyncStateBoundary";
import { ThreeModuleClosureCard, unavailableThreeModuleClosure } from "./ThreeModuleClosureCard";
import { deriveWorkshopViewState, pickPreferredWorkshopView } from "./workshopViewState";

type Client = Pick<typeof ecommerceWorkshopClient, "getCustomerView" | "getCustomerLifecycleContributionView" | "getCustomerContactContributionView"> & Partial<Pick<typeof ecommerceWorkshopClient, "getThreeModuleClosureContributionView">>;
type CustomerActions = Pick<AipActionsSdk, "createProposal" | "createReplacementProposal" | "withdraw" | "timeline">;
type Phase = AsyncState;
type CustomerFilter = "all" | "allowed" | "review" | "excluded";
const LABELS: Record<CustomerViewId, string> = { customer: "客户最小投影", segment: "客户分群", journey: "生命周期旅程", dialogue: "对话与批次" };
const CUSTOMER_VIEW_IDS: CustomerViewId[] = ["customer", "segment", "journey", "dialogue"];
const AXIS_LABELS = { customer_lite: "客户最小集", consent: "同意依据", segment: "分群投影", journey: "旅程投影", dialogue: "对话摘要", outreach_batch: "触达批次" } as const;
const STATUS_LABELS: Record<string, string> = { ready: "可读取", blocked: "等待条件", unknown: "待核对", partial: "部分可用", failed: "读取失败", forbidden: "无权访问", eligible: "符合条件", excluded: "已排除", needsReview: "待复核", deduplicated: "已去重", reserved: "已预留", skippedWithdrawn: "已撤回跳过", cancelled: "已取消", accepted: "已受理", applied: "已应用", disputed: "有争议" };
const labelStatus = (value: string) => STATUS_LABELS[value] ?? value;
const stateFor = (phase: Phase): AsyncState => phase;
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

function CustomerPlanWorkspace({ view, customer, actions }: { view: CustomerViewSlice; customer: CustomerProjection | null; actions: CustomerActions }) {
  const [editing, setEditing] = useState(false);
  const [recovering, setRecovering] = useState(false);
  const [planType, setPlanType] = useState("journey");
  const [title, setTitle] = useState("客户复购旅程草稿");
  const [purpose, setPurpose] = useState("customer-retention");
  const [segmentRule, setSegmentRule] = useState("已同意且留存有效的客户最小投影");
  const [journeyStage, setJourneyStage] = useState("复购教育");
  const [contentDraft, setContentDraft] = useState("提供与当前旅程相关的商品使用说明；不承诺功效，不强制转化。");
  const [proposal, setProposal] = useState<ActionDraftBundle | null>(null);
  const [timeline, setTimeline] = useState<ActionProposalTimeline | null>(null);
  const [showImpact, setShowImpact] = useState(false);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const source = customer?.customerRef ?? view.authorityRefs[0] ?? view.readinessAxes.find((axis) => axis.exactRef)?.exactRef ?? null;
  useEffect(() => { setProposal(null); setTimeline(null); setEditing(false); setRecovering(false); setShowImpact(false); setNotice(""); }, [view.viewId]);
  const submit = async () => {
    if (!source || !title.trim() || !purpose.trim() || !segmentRule.trim() || !journeyStage.trim() || !contentDraft.trim()) { setNotice("缺少 exact 客户来源或计划必要字段，保存失败关闭。"); return; }
    setBusy(true); setNotice("");
    try {
      const expiresAt = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();
      if (proposal && proposal.proposal.status !== "withdrawn") {
        const next = await actions.createReplacementProposal(proposal, { purpose: title.trim(), diff: { planType: { from: proposal.proposal.payload.planType ?? null, to: planType }, journeyStage: { from: proposal.proposal.payload.journeyStage ?? null, to: journeyStage.trim() }, contentDraft: { from: proposal.proposal.payload.contentDraft ?? null, to: contentDraft.trim() } }, expiresAt });
        setProposal(next); setEditing(false); setNotice(`计划修改已形成替代提案 ${next.proposal.id}，旧版本保持可追溯。`);
      } else {
        const objectRef = { resourceType: source.resourceType, resourceId: source.resourceId, revision: String(source.revision), authority: "ecommerce-workshop.customer-view" };
        const next = await actions.createProposal({ actionTypeId: "ecommerce.customer.prepare-outreach-draft", objectRef, purpose: title.trim(), riskHint: "R2", payload: { viewId: view.viewId, planType, purpose: purpose.trim(), segmentRule: segmentRule.trim(), journeyStage: journeyStage.trim(), contentDraft: contentDraft.trim(), customerRef: customer?.customerRef ?? null, contactResolutionAllowed: false, providerDispatchAllowed: false, sendAllowed: false, externalEffectAllowed: false }, diff: { status: { from: null, to: "待审批" }, journeyStage: { from: null, to: journeyStage.trim() } }, evidenceRefs: [objectRef], expiresAt });
        setProposal(next); setEditing(false); setRecovering(false); setNotice(`内部客户经营草稿已形成：${next.proposal.id}。未解析联系方式、未发送。`);
      }
    } catch (error) { setNotice(error instanceof Error ? error.message : "内部客户经营草稿保存失败关闭"); }
    finally { setBusy(false); }
  };
  const readTimeline = async () => {
    if (!proposal) { setNotice("当前尚未形成提案，执行记录保持可信空。"); return; }
    setBusy(true); try { const next = await actions.timeline(proposal.proposal.id); setTimeline(next); setNotice(`已回读 ${next.events.length} 条正式内部事件。`); } catch (error) { setNotice(error instanceof Error ? error.message : "执行记录读取失败关闭"); } finally { setBusy(false); }
  };
  const withdraw = async () => {
    if (!proposal) return; setBusy(true); try { const next = await actions.withdraw(proposal, "运营人员撤回内部客户经营草稿"); setProposal(next); setNotice(`计划 ${next.proposal.id} 已撤回；Permit、Provider、发送与外部效果仍为 0。`); } catch (error) { setNotice(error instanceof Error ? error.message : "计划撤回失败关闭"); } finally { setBusy(false); }
  };
  return <section className="customer-plan-workspace" aria-label="内部客户经营计划">
    <header><div><span>Segment → Journey → Dialogue Draft</span><h3>内部客户经营计划</h3></div><strong>{proposal ? `${proposal.proposal.status} · v${proposal.proposal.version}` : recovering ? "恢复编辑中" : "尚未提交"}</strong></header>
    <p>{customer ? `当前依据：${customer.customerRef.resourceId} · ${customer.purpose}` : "请选择当前视图中的最小客户投影；无 exact ref 时不生成计划。"}</p>
    {editing ? <form onSubmit={(event) => { event.preventDefault(); void submit(); }}><label>计划类型<select aria-label="客户计划类型" value={planType} onChange={(event) => setPlanType(event.target.value)}><option value="segment">客户分群</option><option value="journey">生命周期旅程</option><option value="dialogue">对话草稿</option></select></label><label>计划标题<input aria-label="客户计划标题" value={title} onChange={(event) => setTitle(event.target.value)} maxLength={120} /></label><label>用途<input aria-label="客户计划用途" value={purpose} onChange={(event) => setPurpose(event.target.value)} maxLength={120} /></label><label>分群条件<textarea aria-label="客户分群条件" value={segmentRule} onChange={(event) => setSegmentRule(event.target.value)} maxLength={300} /></label><label>旅程阶段<input aria-label="客户旅程阶段" value={journeyStage} onChange={(event) => setJourneyStage(event.target.value)} maxLength={120} /></label><label>合规内容草稿<textarea aria-label="客户内容草稿" value={contentDraft} onChange={(event) => setContentDraft(event.target.value)} maxLength={500} /></label><footer><button type="button" onClick={() => { setContentDraft("先确认 purpose、Consent、留存与频控，再提供相关说明；不强制转化。"); setNotice("已采纳合规建议，尚未提交。"); }}>采纳合规建议</button><button type="button" onClick={() => setEditing(false)}>取消</button><button className="is-primary" type="submit" disabled={busy || !source}>{proposal && proposal.proposal.status !== "withdrawn" ? "提交计划修改" : recovering ? "保存恢复草稿" : "保存内部草稿"}</button></footer></form> : <div className="customer-plan-actions"><button type="button" onClick={() => setEditing(true)}>{proposal ? "修改计划" : "新建经营计划"}</button><button type="button" onClick={() => setShowImpact((value) => !value)} disabled={!proposal}>影响预览</button><button type="button" onClick={readTimeline}>执行记录</button><button type="button" onClick={() => setNotice(proposal ? `审批前预览：${proposal.proposal.purpose}；需复验 Consent、留存、频控、独立审批、短时租约、Permit 与渠道门，当前禁止发送。` : "请先形成内部客户经营草稿。")}>审批预览</button><button type="button" onClick={withdraw} disabled={!proposal || busy || proposal.proposal.status === "withdrawn"}>撤回计划</button>{proposal?.proposal.status === "withdrawn" ? <button type="button" onClick={() => { setProposal(null); setTimeline(null); setShowImpact(false); setRecovering(true); setEditing(true); setNotice("已恢复为独立编辑草稿；保存时使用新提案和新幂等键。"); }}>恢复为新草稿</button> : null}</div>}
    {showImpact && proposal ? <dl className="customer-plan-impact" aria-label="客户经营影响预览"><div><dt>对象范围</dt><dd>stable Customer ref 1 · protected contact 0</dd></div><div><dt>计划版本</dt><dd>{proposal.proposal.id} · v{proposal.proposal.version}</dd></div><div><dt>执行影响</dt><dd>Permit 0 · Provider 0 · 发送 0</dd></div></dl> : null}
    {proposal ? <section className="customer-plan-receipt" aria-label="内部客户经营凭证"><strong>内部草稿凭证</strong><span>{proposal.proposal.id} · 第 {proposal.proposal.version} 版</span><small title={proposal.proposal.proposalHash}>{proposal.proposal.proposalHash.slice(0, 16)}…</small><small>审批 {proposal.approvals.length} · 发送 0 · 外部效果 0</small></section> : null}
    {timeline ? <ol className="customer-plan-timeline">{timeline.events.map((event) => <li key={event.id}><strong>{event.type}</strong><span>{new Date(event.createdAt).toLocaleString("zh-CN", { hour12: false })}</span></li>)}</ol> : null}
    <div className="customer-plan-preflights"><button type="button" onClick={() => setNotice("导入客户预检：source mapping、purpose 与 PII contract 未齐；导入 0，客户状态变更 0。")}>导入客户预检</button><button type="button" onClick={() => setNotice("发送预检：contact resolver、Permit、Provider 与单独发送许可未齐；发送 0，外部效果 0。")}>发送预检</button></div>
    {notice ? <p className="customer-plan-notice" role="status">{notice}</p> : null}
  </section>;
}

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

export function CustomerPage({ client = ecommerceWorkshopClient, actions = aipActionsSdk }: { client?: Client; actions?: CustomerActions }) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [response, setResponse] = useState<CustomerViewResponse | null>(null);
  const [contribution, setContribution] = useState<CustomerLifecycleContributionViewResponse | null>(null);
  const [contact, setContact] = useState<CustomerContactContributionViewResponse | null>(null);
  const [closure, setClosure] = useState<ThreeModuleClosureContributionViewResponse | null>(null);
  const [selected, setSelected] = useState<CustomerViewId>("customer");
  const [customerFilter, setCustomerFilter] = useState<CustomerFilter>("all");
  const [selectedCustomerId, setSelectedCustomerId] = useState<string | null>(null);
  const request = useRef(0);
  const load = () => {
    const id = ++request.current; setPhase("loading"); setResponse(null); setContribution(null); setContact(null); setClosure(null);
    void Promise.all([client.getCustomerView(), client.getCustomerLifecycleContributionView().catch(() => null), client.getCustomerContactContributionView().catch(() => null), client.getThreeModuleClosureContributionView?.("customer").catch(() => null) ?? Promise.resolve(null)]).then(([next, nextContribution, nextContact, nextClosure]) => {
      if (id !== request.current) return;
      setResponse(next); setContribution(nextContribution ?? unavailableLifecycle(next)); setContact(nextContact ?? unavailableContact(next)); setClosure(nextClosure ?? unavailableThreeModuleClosure("customer", next.tenant, next.evaluatedAt));
      setSelected(pickPreferredWorkshopView(next.views, (item) => item.countLedger.eligible > 0)?.viewId ?? "customer");
      setPhase(deriveWorkshopViewState(next.views, next.page.count));
    }, (error: unknown) => { if (id === request.current) setPhase(error instanceof EcommerceWorkshopClientError && (error.status === 401 || error.status === 403) ? "forbidden" : "failed"); });
  };
  useEffect(() => { load(); return () => { request.current += 1; }; }, [client]);
  const view = response?.views.find((item) => item.viewId === selected);
  const visibleCustomers = view?.items.filter((item) => customerFilter === "all" || (customerFilter === "allowed" && item.disclosure === "allowed") || (customerFilter === "review" && item.disclosure === "unknown") || (customerFilter === "excluded" && item.disclosure === "blocked")) ?? [];
  const selectedCustomer = view?.items.find((item) => item.customerRef.resourceId === selectedCustomerId) ?? view?.items[0] ?? null;
  const eligible = response?.views.reduce((sum, item) => sum + item.countLedger.eligible, 0) ?? 0;
  const total = response?.views.reduce((sum, item) => sum + item.countLedger.input, 0) ?? 0;
  const content = response && contribution && contact && closure && view ? <div className="customer-read-model">
    <details className="customer-audit-context">
      <summary>客户治理全过程与累计审计</summary>
      <div className="customer-audit-stack">
    <section className="customer-hero"><div><span>客户关系工作台 · 最小披露</span><h2>只在目的、同意与留存边界内阅读客户关系</h2><p>同意撤回、留存到期、质量失败或来源不可核验都会失败关闭；页面不展示联系方式和身份字段。</p></div><strong>只读 · 零触达</strong></section>
    <section className="creator-growth-axis"><div><span>只读视图</span><strong>4</strong></div><div><span>允许披露</span><strong>{eligible}/{total}</strong></div><div><span>资源 revision</span><strong>r{response.resourceRevision}</strong></div><div><span>外部写入口</span><strong>0</strong></div></section>
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
    <div className="customer-tabs" role="tablist" aria-label="客户关系只读视图">{response.views.map((item, index) => <button id={`customer-tab-${item.viewId}`} aria-controls={`customer-panel-${item.viewId}`} type="button" role="tab" aria-selected={selected === item.viewId} tabIndex={selected === item.viewId ? 0 : -1} key={item.viewId} onClick={() => setSelected(item.viewId)} onKeyDown={(event) => { if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return; event.preventDefault(); const nextIndex = event.key === "Home" ? 0 : event.key === "End" ? response.views.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + response.views.length) % response.views.length; setSelected(response.views[nextIndex]!.viewId); event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>("button")[nextIndex]?.focus(); }}><strong>{LABELS[item.viewId]}</strong><span>{labelStatus(item.status)} · 正式来源 {item.countLedger.input}</span></button>)}</div>
    <section id={`customer-panel-${selected}`} aria-labelledby={`customer-tab-${selected}`} className="customer-panel" role="tabpanel" aria-label={LABELS[selected]}><header><div><span>客户关系视图</span><h2>{LABELS[view.viewId]}</h2></div><strong className={`content-campaign-status is-${view.status}`}>{view.status === "ready" ? "同截止面可读" : "等待必要条件"}</strong></header>
      <div className="customer-readiness">{view.readinessAxes.map((axis) => <article key={axis.axis} className={`is-${axis.status}`}><strong>{AXIS_LABELS[axis.axis]}</strong><span>{labelStatus(axis.status)}</span><p>{axis.exactRef ? `${axis.exactRef.resourceType} · r${axis.exactRef.revision}` : "暂无可验证来源"}</p><details><summary>查看数据审计信息</summary><p>{axis.exactRef ? `${axis.exactRef.receiptId} · ${axis.exactRef.contentHash.slice(0, 18)}…` : axis.blockers[0]?.code ?? "authority unavailable"}</p></details></article>)}</div>
      <section className="customer-items"><nav aria-label="客户最小投影筛选">{([['all', '全部'], ['allowed', '可披露'], ['review', '待复核'], ['excluded', '已排除']] as const).map(([id, label]) => <button type="button" aria-pressed={customerFilter === id} key={id} onClick={() => setCustomerFilter(id)}>{label}</button>)}</nav>{visibleCustomers.length ? visibleCustomers.map((item) => <article key={`${item.customerRef.resourceId}:${item.customerRef.revision}`} className={`is-${item.disclosure}${selectedCustomer?.customerRef.resourceId === item.customerRef.resourceId ? " is-selected" : ""}`}><header><div><strong>{item.customerRef.resourceType}</strong><span>{item.customerRef.resourceId} · r{item.customerRef.revision}</span></div><b>{labelStatus(item.disclosure)}</b></header><dl><div><dt>目的</dt><dd>{item.purpose}</dd></div><div><dt>新鲜度 / 质量</dt><dd>{item.freshness} / {item.quality}</dd></div><div><dt>同意 / 留存</dt><dd>{item.consent} / {item.retention}</dd></div><div><dt>k 匿名 / 原始证据</dt><dd>{item.kAnonymitySatisfied === null ? "待核对" : String(item.kAnonymitySatisfied)} / {item.originalRefs.length}</dd></div></dl><button type="button" aria-pressed={selectedCustomer?.customerRef.resourceId === item.customerRef.resourceId} onClick={() => setSelectedCustomerId(item.customerRef.resourceId)}>选择此最小投影</button></article>) : <p>{view.items.length ? "当前筛选没有匹配的最小客户投影；可切换筛选继续核对。" : `已读取正式来源 ${view.countLedger.input} 条；允许披露 ${view.countLedger.eligible} 条，${view.countLedger.unknown} 条因同意、目的或留存条件未闭合而不展示客户明细。`}</p>}</section>
      <aside className="media-studio-blockers"><CustomerPlanWorkspace view={view} customer={selectedCustomer} actions={actions} /><h3>所需条件与下一步</h3>{view.blockers.length ? view.blockers.map((item) => <div key={item.code}><strong>补充同租户、同数据截止的客户最小化正式数据</strong><span>客户关系正式数据来源</span><details><summary>查看审计状态码</summary><code>{item.code}</code><p>{item.requiredAction}</p><p>{item.dependency}</p></details></div>) : <p>本视图当前没有待补条件。</p>}</aside>
    </section>
    <footer className="content-campaign-footnote"><span>租户 {response.tenant.orgId}/{response.tenant.projectId}</span><span>统一数据截止 {new Date(response.dataCutoff).toLocaleString("zh-CN", { hour12: false })}</span><span>同意与留存规则已执行</span></footer>
  </div> : null;
  return <section className="customer-page" aria-label="客户关系只读视图"><div className="content-campaign-toolbar customer-context-strip"><button className="customer-reload-control" type="button" onClick={load}>重新读取</button><span>栖月汇 · 客户状态待核对</span><span>私域管家（负责人未绑定）</span><small>任务驱动 · 只读计划 · 客户产物</small><i aria-hidden="true" /><b>高价值待核对 · 潜力待核对 · 活跃待核对</b><em>沉睡待核对 · 流失预警待核对</em></div>{phase === "failed" ? <CustomerFailureSurface /> : <AsyncStateBoundary state={stateFor(phase)} dataCutoff={response?.dataCutoff}>{content}</AsyncStateBoundary>}</section>;
}
