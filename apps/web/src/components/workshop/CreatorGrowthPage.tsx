import { useEffect, useMemo, useRef, useState } from "react";

import {
  CREATOR_LIFECYCLE_SCHEMA_VERSION,
  CREATOR_PREPARE_SCHEMA_VERSION,
  EcommerceWorkshopClientError,
  ecommerceWorkshopClient,
  type CreatorBusinessStage,
  type CreatorContributionViewResponse,
  type CreatorGrowthSlice,
  type CreatorGrowthViewResponse,
  type CreatorInternalWorkflowCommand,
  type CreatorInternalWorkflowCommandInput,
  type CreatorInternalWorkflowDraft,
  type CreatorInternalWorkflowPurpose,
  type CreatorInternalWorkflowReceipt,
  type CreatorLifecycleViewResponse,
  type ThreeModuleClosureContributionViewResponse,
} from "../../api/ecommerceWorkshop";
import { AsyncStateBoundary, type AsyncState } from "./AsyncStateBoundary";
import { ThreeModuleClosureCard, unavailableThreeModuleClosure } from "./ThreeModuleClosureCard";

type Client = Pick<typeof ecommerceWorkshopClient, "getCreatorGrowthView" | "getCreatorContributionView" | "executeCreatorInternalWorkflow" | "getCreatorInternalWorkflowHistory" | "listCreatorInternalWorkflows"> & Partial<Pick<typeof ecommerceWorkshopClient, "getCreatorLifecycleView" | "getThreeModuleClosureContributionView">>;
type PreparationMode = CreatorInternalWorkflowPurpose | null;
const STAGES: CreatorBusinessStage[] = ["candidate", "outreach", "contract", "delivery", "relationship"];
const TABS: Record<CreatorBusinessStage, string> = { candidate: "达人库", outreach: "招募漏斗", contract: "商务签约", delivery: "履约效果", relationship: "长期关系" };
const STAGE_LABELS: Record<CreatorBusinessStage, string> = { candidate: "候选", outreach: "邀约", contract: "合作", delivery: "交付", relationship: "关系" };
const STAGE_DESCRIPTIONS: Record<CreatorBusinessStage, string> = { candidate: "达人与品牌、商品和受众的匹配", outreach: "候选去重、准备、批准与回复", contract: "意向、条款、签约与生效", delivery: "内容交付、效果窗口与异常", relationship: "分层、复邀窗口与关系事件" };
const FILTERS = ["全部", "个人达人", "机构", "有合作记录"] as const;
const short = (value: string) => value.length > 30 ? `${value.slice(0, 12)}…${value.slice(-10)}` : value;

const unavailableContribution = (next: CreatorGrowthViewResponse): CreatorContributionViewResponse => ({
  schemaVersion: CREATOR_PREPARE_SCHEMA_VERSION, tenant: next.tenant, evaluatedAt: next.evaluatedAt,
  atomicSkillRefs: [], logicRef: null, primaryColleague: "导购顾问", collaboratorColleagues: ["数据参谋", "内容官", "活动策划师"],
  latestBatch: null, blockers: ["CREATOR_PREPARE_AUTHORITY_UNAVAILABLE"], allowedCommands: [], externalEffectsAllowed: false,
});
const unavailableLifecycle = (next: CreatorGrowthViewResponse): CreatorLifecycleViewResponse => ({
  schemaVersion: CREATOR_LIFECYCLE_SCHEMA_VERSION, tenant: next.tenant, evaluatedAt: next.evaluatedAt,
  latestStart: null, ledger: { eligibleItems: 0, lanes: 0, prepared: 0, accepted: 0, applied: 0, failed: 0, unknown: 0, disputed: 0, completed: 0 },
  contracts: [], deliveries: [], relationships: [], blockers: ["CREATOR_LIFECYCLE_AUTHORITY_UNAVAILABLE"], allowedCommands: [], externalEffectsAllowed: false,
});

function MetricBar({ items }: { items: Array<[string, number | string, string?]> }) {
  return <section className="creator-growth-metrics">{items.map(([label, value, note]) => <div key={label}><strong>{value}</strong><span>{label}</span>{note ? <small>{note}</small> : null}</div>)}</section>;
}

function EmptyBusinessState({ title, description, action, onAction }: { title: string; description: string; action: string; onAction: () => void }) {
  return <section className="creator-growth-empty"><strong>{title}</strong><p>{description}</p><button type="button" onClick={onAction}>{action}</button></section>;
}

function CandidateWorkspace({ slice, onPrepare }: { slice: CreatorGrowthSlice; onPrepare: () => void }) {
  return <>
    <MetricBar items={[["候选总量", slice.countLedger.input], ["符合条件", slice.countLedger.eligible], ["需要复核", slice.countLedger.needsReview], ["已去重", slice.countLedger.deduplicated], ["当前选中", slice.authorityRefs.length ? 1 : 0]]} />
    <section className="creator-growth-workspace-section"><header><div><span>达人库</span><h2>候选匹配概览</h2></div><strong>{slice.authorityRefs.length} 条正式记录</strong></header>
      {slice.authorityRefs.length ? <div className="creator-growth-records">{slice.authorityRefs.map((item) => <article key={`${item.resourceType}:${item.resourceId}:${item.revision}`}><strong>{item.resourceId}</strong><span>{item.resourceType} · 第 {item.revision} 版</span><small>当前租户正式记录</small></article>)}</div> : <EmptyBusinessState title="当前达人库为空" description="栖月汇当前数据截止面没有可回链的达人或机构记录。可以先整理候选来源和筛选条件，再进入正式导入流程。" action="准备候选条件" onAction={onPrepare} />}
    </section>
  </>;
}

function OutreachWorkspace({ slice, lifecycle, onPrepare }: { slice: CreatorGrowthSlice; lifecycle: CreatorLifecycleViewResponse; onPrepare: () => void }) {
  const funnel: Array<[string, number]> = [["候选总量", slice.countLedger.input], ["唯一候选", Math.max(0, slice.countLedger.input - slice.countLedger.deduplicated)], ["符合条件", slice.countLedger.eligible], ["已准备", lifecycle.ledger.prepared], ["已批准", lifecycle.ledger.accepted], ["已应用", lifecycle.ledger.applied], ["有回复", lifecycle.ledger.completed], ["需要复核", slice.countLedger.needsReview]];
  const max = Math.max(1, ...funnel.map(([, value]) => value));
  return <>
    <MetricBar items={[["候选", slice.countLedger.input], ["批次", lifecycle.latestStart ? 1 : 0], ["已准备", lifecycle.ledger.prepared], ["有回复", lifecycle.ledger.completed], ["需要复核", slice.countLedger.needsReview]]} />
    <section className="creator-growth-workspace-section"><header><div><span>招募工作区</span><h2>邀约漏斗</h2></div><button type="button" onClick={onPrepare}>新建批次准备</button></header>
      <div className="creator-growth-funnel">{funnel.map(([label, value]) => <div key={label}><span>{label}</span><i><b style={{ width: `${Math.max(value ? 8 : 0, value / max * 100)}%` }} /></i><strong>{value}</strong></div>)}</div>
      <section className="creator-growth-batch-empty"><h3>批次准备</h3><p>当前没有正式邀约批次。先选择候选范围、合作目标与渠道，本页只整理本次准备内容，不会自动发送消息。</p><button type="button" onClick={onPrepare}>填写批次条件</button></section>
    </section>
  </>;
}

function ContractWorkspace({ lifecycle, onPrepare }: { lifecycle: CreatorLifecycleViewResponse; onPrepare: () => void }) {
  const columns: Array<[string, number]> = [["有意向", 0], ["谈判中", 0], ["条款确认", 0], ["签署中", 0], ["已生效", lifecycle.contracts.length]];
  return <>
    <MetricBar items={[["有意向", 0], ["谈判中", 0], ["条款确认", 0], ["签署中", 0], ["已生效", lifecycle.contracts.length]]} />
    <section className="creator-growth-workspace-section"><header><div><span>商务签约</span><h2>合作条款看板</h2></div><button type="button" onClick={onPrepare}>整理合作条件</button></header><div className="creator-growth-kanban">{columns.map(([label, count]) => <section key={label}><header><strong>{label}</strong><span>{count}</span></header><p>{count ? `${count} 条正式合同记录` : "当前为空"}</p></section>)}</div><p className="creator-growth-business-note">只有正式合同记录进入“已生效”；平台接受合作、聊天确认或页面准备内容都不会替代签署结果。</p></section>
  </>;
}

function DeliveryWorkspace({ lifecycle, onPrepare }: { lifecycle: CreatorLifecycleViewResponse; onPrepare: () => void }) {
  return <>
    <MetricBar items={[["进行中合作", 0], ["已交付", lifecycle.deliveries.length], ["效果窗口已闭", 0], ["效果观察中", 0], ["异常需核对", 0]]} />
    <section className="creator-growth-workspace-section"><header><div><span>履约效果</span><h2>履约任务列表</h2></div><button type="button" onClick={onPrepare}>准备交付检查</button></header><div className="creator-growth-table"><div className="is-head"><span>达人 / 机构</span><span>交付内容</span><span>档期</span><span>效果窗口</span><span>状态</span></div><div className="is-empty"><span>当前没有正式履约记录</span></div></div><p className="creator-growth-business-note">GMV、ROI、退货率和异常判断只在正式效果窗口与来源数据齐备后展示。</p></section>
  </>;
}

function RelationshipWorkspace({ lifecycle, onPrepare }: { lifecycle: CreatorLifecycleViewResponse; onPrepare: () => void }) {
  return <>
    <MetricBar items={[["核心关系", 0], ["活跃关系", lifecycle.relationships.length], ["沉默关系", 0], ["复邀窗口开放", 0], ["停止联系", 0]]} />
    <section className="creator-growth-workspace-section"><header><div><span>长期关系</span><h2>复邀计划</h2></div><button type="button" onClick={onPrepare}>准备复邀条件</button></header><div className="creator-growth-table"><div className="is-head"><span>达人 / 机构</span><span>关系层级</span><span>上次合作</span><span>复邀窗口</span><span>负责人</span></div><div className="is-empty"><span>当前没有正式关系记录</span></div></div><section className="creator-growth-timeline"><h3>关系事件流</h3><p>暂无可回链的感谢、复邀、冷却或停止联系事件。</p></section></section>
  </>;
}

function StageWorkspace({ stage, slice, lifecycle, onPrepare }: { stage: CreatorBusinessStage; slice: CreatorGrowthSlice; lifecycle: CreatorLifecycleViewResponse; onPrepare: (purpose: CreatorInternalWorkflowPurpose) => void }) {
  if (stage === "candidate") return <CandidateWorkspace slice={slice} onPrepare={() => onPrepare("candidate_import")} />;
  if (stage === "outreach") return <OutreachWorkspace slice={slice} lifecycle={lifecycle} onPrepare={() => onPrepare("outreach_batch")} />;
  if (stage === "contract") return <ContractWorkspace lifecycle={lifecycle} onPrepare={() => onPrepare("collaboration")} />;
  if (stage === "delivery") return <DeliveryWorkspace lifecycle={lifecycle} onPrepare={() => onPrepare("delivery_check")} />;
  return <RelationshipWorkspace lifecycle={lifecycle} onPrepare={() => onPrepare("relationship_plan")} />;
}

const PREPARATION_COPY: Record<CreatorInternalWorkflowPurpose, { title: string; defaultTitle: string; summaryLabel: string; placeholder: string }> = {
  candidate_import: { title: "导入达人准备", defaultTitle: "达人候选导入", summaryLabel: "来源与筛选条件", placeholder: "说明候选来源、内容领域、渠道、受众和合作要求" },
  outreach_batch: { title: "新建邀约批次准备", defaultTitle: "达人邀约批次", summaryLabel: "批次目标与范围", placeholder: "说明候选范围、合作目标、邀约渠道和频控要求" },
  outreach_message: { title: "编写邀约内容", defaultTitle: "达人邀约文案", summaryLabel: "沟通要点", placeholder: "说明品牌、商品、合作权益和期望回复时间" },
  collaboration: { title: "新建合作准备", defaultTitle: "达人合作方案", summaryLabel: "合作条件", placeholder: "说明交付内容、档期、预算、佣金和审核要求" },
  delivery_check: { title: "履约检查准备", defaultTitle: "达人履约检查", summaryLabel: "检查范围", placeholder: "说明交付物、档期、验收标准和效果观察窗口" },
  relationship_plan: { title: "关系维护计划", defaultTitle: "达人关系维护", summaryLabel: "维护目标", placeholder: "说明关系分层、复邀窗口、冷却期和负责人" },
};
const WORKFLOW_STATUS: Record<CreatorInternalWorkflowDraft["status"], string> = { draft: "草稿", in_review: "审核中", approved: "已批准", rejected: "已驳回" };

function PreparationPanel({ purpose, current, receipt, history, busy, error, onClose, onCommand, onNew }: { purpose: CreatorInternalWorkflowPurpose; current: CreatorInternalWorkflowDraft | null; receipt: CreatorInternalWorkflowReceipt | null; history: CreatorInternalWorkflowDraft[]; busy: boolean; error: string; onClose: () => void; onCommand: (command: CreatorInternalWorkflowCommand, values: { title: string; summary: string; details: Record<string, unknown> }, restoreRevision?: number) => void; onNew: () => void }) {
  const copy = PREPARATION_COPY[purpose];
  const [title, setTitle] = useState(current?.title ?? copy.defaultTitle);
  const [summary, setSummary] = useState(current?.summary ?? "");
  const [owner, setOwner] = useState(String(current?.details.owner ?? "经营负责人"));
  useEffect(() => { setTitle(current?.title ?? copy.defaultTitle); setSummary(current?.summary ?? ""); setOwner(String(current?.details.owner ?? "经营负责人")); }, [current?.revision, purpose]);
  const values = { title: title.trim(), summary: summary.trim(), details: { owner: owner.trim() } };
  const disabled = busy || values.title.length < 2 || values.summary.length < 2;
  return <aside className="creator-growth-preparation" aria-label={copy.title}><header><div><span>内部业务工作流</span><h2>{copy.title}</h2></div><button type="button" onClick={onClose}>关闭</button></header>
    <label>任务名称<input aria-label="任务名称" value={title} onChange={(event) => setTitle(event.target.value)} /></label>
    <label>{copy.summaryLabel}<textarea aria-label={copy.summaryLabel} value={summary} onChange={(event) => setSummary(event.target.value)} placeholder={copy.placeholder} /></label>
    <label>负责人<input aria-label="负责人" value={owner} onChange={(event) => setOwner(event.target.value)} /></label>
    <p>草稿、审核和历史版本保存在当前租户；不会自动导入、发送邀约、签署合同或产生外部触达。</p>
    {current ? <section aria-label="当前草稿"><strong>{WORKFLOW_STATUS[current.status]} · 第 {current.revision} 版</strong><small>写入基线 {current.version} · {current.resourceId}</small>{receipt ? <small>回执 {receipt.receiptId}{receipt.replay ? " · 幂等重放" : ""}</small> : null}</section> : null}
    {error ? <p role="alert">{error}</p> : null}
    <div className="creator-growth-preparation-actions">
      {!current ? <button type="button" className="is-primary" disabled={disabled} onClick={() => onCommand("create", values)}>保存草稿</button> : null}
      {current && (current.status === "draft" || current.status === "rejected") ? <><button type="button" disabled={disabled} onClick={() => onCommand("save", values)}>保存修改</button><button type="button" className="is-primary" disabled={disabled} onClick={() => onCommand("submit_review", values)}>提交审核</button></> : null}
      {current?.status === "in_review" ? <><button type="button" className="is-primary" disabled={busy} onClick={() => onCommand("approve", values)}>批准</button><button type="button" disabled={busy} onClick={() => onCommand("reject", values)}>驳回</button></> : null}
      {current ? <button type="button" disabled={busy} onClick={onNew}>新建一份</button> : null}
    </div>
    {history.length ? <details className="creator-growth-workflow-history"><summary>查看版本历史（{history.length}）</summary>{[...history].reverse().map((item) => <article key={item.revision}><div><strong>第 {item.revision} 版 · {WORKFLOW_STATUS[item.status]}</strong><span>{item.title}</span></div>{item.revision < (current?.revision ?? 0) ? <button type="button" disabled={busy} onClick={() => onCommand("restore", { title: item.title, summary: item.summary, details: item.details }, item.revision)}>恢复此版本</button> : null}</article>)}</details> : null}
  </aside>;
}

const ADVISORS: Record<CreatorBusinessStage, readonly [string, string, string]> = {
  candidate: ["AI 匹配分析 · 导购顾问", "核对候选与商品、内容领域和受众是否匹配。", "准备候选条件"],
  outreach: ["批次分析 · 数据参谋", "核对候选数量、去重、频控和批次承接能力。", "准备邀约批次"],
  contract: ["商务建议 · 活动策划师", "整理合作目标、交付要求与条款差异。", "整理合作条件"],
  delivery: ["效果核对 · 数据参谋", "核对交付证据、效果窗口和异常信号。", "准备交付检查"],
  relationship: ["关系维护 · 私域管家", "核对关系层级、冷却期和复邀窗口。", "准备复邀计划"],
};
const advisorFor = (stage: CreatorBusinessStage) => ADVISORS[stage];

export function CreatorGrowthPage({ client = ecommerceWorkshopClient }: { client?: Client }) {
  const [phase, setPhase] = useState<AsyncState>("loading"); const [response, setResponse] = useState<CreatorGrowthViewResponse | null>(null);
  const [contribution, setContribution] = useState<CreatorContributionViewResponse | null>(null); const [lifecycle, setLifecycle] = useState<CreatorLifecycleViewResponse | null>(null); const [closure, setClosure] = useState<ThreeModuleClosureContributionViewResponse | null>(null);
  const [selected, setSelected] = useState<CreatorBusinessStage>("candidate"); const [query, setQuery] = useState(""); const [filter, setFilter] = useState<(typeof FILTERS)[number]>("全部"); const [preparation, setPreparation] = useState<PreparationMode>(null); const [notice, setNotice] = useState(""); const request = useRef(0);
  const [workflowDrafts, setWorkflowDrafts] = useState<Partial<Record<CreatorInternalWorkflowPurpose, CreatorInternalWorkflowDraft>>>({});
  const [workflowHistory, setWorkflowHistory] = useState<Partial<Record<CreatorInternalWorkflowPurpose, CreatorInternalWorkflowDraft[]>>>({});
  const [workflowReceipts, setWorkflowReceipts] = useState<Partial<Record<CreatorInternalWorkflowPurpose, CreatorInternalWorkflowReceipt>>>({});
  const [workflowBusy, setWorkflowBusy] = useState(false); const [workflowError, setWorkflowError] = useState("");
  const workflowIntentKeys = useRef<Record<string, string>>({});
  const load = () => { const id = ++request.current; setPhase("loading"); void Promise.all([client.getCreatorGrowthView(), client.getCreatorContributionView().catch(() => null), client.getCreatorLifecycleView?.().catch(() => null) ?? Promise.resolve(null), client.getThreeModuleClosureContributionView?.("creator").catch(() => null) ?? Promise.resolve(null), client.listCreatorInternalWorkflows().catch(() => null)]).then(([next, nextContribution, nextLifecycle, nextClosure, workflows]) => { if (id !== request.current) return; setResponse(next); setContribution(nextContribution ?? unavailableContribution(next)); setLifecycle(nextLifecycle ?? unavailableLifecycle(next)); setClosure(nextClosure ?? unavailableThreeModuleClosure("creator", next.tenant, next.evaluatedAt)); if (workflows) { const latest: Partial<Record<CreatorInternalWorkflowPurpose, CreatorInternalWorkflowDraft>> = {}; for (const item of workflows.items) if (!latest[item.purpose]) latest[item.purpose] = item; setWorkflowDrafts(latest); } setPhase("ready"); }, (error: unknown) => { if (id === request.current) setPhase(error instanceof EcommerceWorkshopClientError && (error.status === 401 || error.status === 403) ? "forbidden" : "failed"); }); };
  useEffect(() => { load(); return () => { request.current += 1; }; }, [client]);
  useEffect(() => { const search = (event: Event) => setQuery(String((event as CustomEvent<{ value?: string }>).detail?.value ?? "")); const openImport = () => setPreparation("candidate_import"); const openBatch = () => { setSelected("outreach"); setPreparation("outreach_batch"); }; window.addEventListener("aos-workshop-creator-search", search); window.addEventListener("aos-workshop-creator-import", openImport); window.addEventListener("aos-workshop-creator-new-batch", openBatch); return () => { window.removeEventListener("aos-workshop-creator-search", search); window.removeEventListener("aos-workshop-creator-import", openImport); window.removeEventListener("aos-workshop-creator-new-batch", openBatch); }; }, []);
  const activeDraft = preparation ? workflowDrafts[preparation] : undefined;
  useEffect(() => {
    if (!preparation || !activeDraft) return;
    let active = true;
    void client.getCreatorInternalWorkflowHistory(activeDraft.resourceId).then(
      (history) => { if (active) setWorkflowHistory((previous) => ({ ...previous, [preparation]: history.items })); },
      () => { if (active) setWorkflowError("当前草稿已恢复，但版本历史暂未读取；可重新读取后再试。"); },
    );
    return () => { active = false; };
  }, [client, preparation, activeDraft?.resourceId, activeDraft?.revision]);
  const slice = response?.slices.find((item) => item.businessStage === selected); const visibleRefs = useMemo(() => slice?.authorityRefs.filter((item) => !query.trim() || `${item.resourceType} ${item.resourceId}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())) ?? [], [slice, query]);
  if (!response || !contribution || !lifecycle || !closure || !slice) return <section className="creator-growth-page"><AsyncStateBoundary state={phase} action={phase === "failed" ? <button type="button" onClick={load}>重新读取</button> : undefined} /></section>;
  const advisor = advisorFor(selected); const purposeForStage: Record<CreatorBusinessStage, CreatorInternalWorkflowPurpose> = { candidate: "candidate_import", outreach: "outreach_batch", contract: "collaboration", delivery: "delivery_check", relationship: "relationship_plan" }; const openRelevantPreparation = () => setPreparation(purposeForStage[selected]);
  const executeWorkflow = async (command: CreatorInternalWorkflowCommand, values: { title: string; summary: string; details: Record<string, unknown> }, restoreRevision?: number) => {
    if (!preparation) return;
    const current = workflowDrafts[preparation];
    const input: CreatorInternalWorkflowCommandInput = { command, purpose: preparation, ...values };
    if (command !== "create") {
      if (!current) return;
      input.draftRef = {
        resourceType: current.resourceType,
        resourceId: current.resourceId,
        revision: current.revision,
        contentHash: current.contentHash,
      };
      input.expectedVersion = current.version;
    }
    if (command === "restore") input.restoreRevision = restoreRevision;
    const intent = JSON.stringify([preparation, command, values, restoreRevision ?? null, current?.version ?? 0]);
    const idempotencyKey = workflowIntentKeys.current[intent] ?? `creator-${preparation}-${command}-${Date.now()}-${current?.version ?? 0}`;
    workflowIntentKeys.current[intent] = idempotencyKey;
    setWorkflowBusy(true); setWorkflowError("");
    try {
      const result = await client.executeCreatorInternalWorkflow(input, idempotencyKey);
      setWorkflowDrafts((previous) => ({ ...previous, [preparation]: result.draft }));
      setWorkflowReceipts((previous) => ({ ...previous, [preparation]: result.receipt }));
      setNotice(`${result.message} 当前为${WORKFLOW_STATUS[result.draft.status]}，第 ${result.draft.revision} 版。`);
      delete workflowIntentKeys.current[intent];
      try { const history = await client.getCreatorInternalWorkflowHistory(result.draft.resourceId); setWorkflowHistory((previous) => ({ ...previous, [preparation]: history.items })); }
      catch { setWorkflowError("操作已保存并取得回执，但版本历史暂未刷新；可稍后重新打开或重新读取。"); }
    } catch (error) { setWorkflowError(error instanceof Error ? `操作结果未确认：${error.message}。再次点击将复用同一请求回执键。` : "操作结果未确认；再次点击将复用同一请求回执键。"); }
    finally { setWorkflowBusy(false); }
  };
  const auditCodes = [...slice.blockers.map((item) => item.code), ...contribution.blockers, ...lifecycle.blockers];
  return <section className="creator-growth-page" aria-label="达人邀约驾驶舱">
    <nav className="creator-growth-toolbar" aria-label="达人增长主视图"><div>{STAGES.map((stage) => <button type="button" className={selected === stage ? "is-active" : ""} key={stage} onClick={() => { setSelected(stage); setNotice(""); }}>{TABS[stage]}</button>)}</div></nav>
    <div className="creator-growth-read-model"><div className="creator-growth-board">
      <aside className="creator-growth-directory"><header><div><h2>达人与机构</h2><span>{response.page.count} 条正式记录</span></div><button type="button" onClick={() => setPreparation("candidate_import")}>导入准备</button></header><label className="creator-growth-search"><input aria-label="检索达人或机构" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索达人、机构、邀约记录" /></label><div className="creator-growth-filters">{FILTERS.map((item) => <button type="button" key={item} className={filter === item ? "is-selected" : ""} aria-pressed={filter === item} onClick={() => setFilter(item)}>{item}</button>)}</div><p className="creator-growth-range">{filter} · {query || "全部关键词"} · {visibleRefs.length} 条</p><div className="creator-growth-stage-list">{response.slices.map((item) => <button type="button" className={`content-campaign-slice${selected === item.businessStage ? " is-selected" : ""}`} key={item.businessStage} onClick={() => setSelected(item.businessStage)}><strong>{STAGE_LABELS[item.businessStage]}</strong><span>{item.authorityRefs.length}</span><small>{STAGE_DESCRIPTIONS[item.businessStage]}</small></button>)}</div><section className="creator-growth-directory-empty"><strong>{visibleRefs.length ? `${visibleRefs.length} 条匹配记录` : "没有匹配记录"}</strong><p>{visibleRefs.length ? "选择业务阶段查看正式数据。" : "调整关键词或先准备候选来源与筛选条件。"}</p></section></aside>
      <main className="creator-growth-main"><StageWorkspace stage={selected} slice={{ ...slice, authorityRefs: visibleRefs }} lifecycle={lifecycle} onPrepare={setPreparation} />{notice ? <p className="creator-growth-notice" role="status">{notice}</p> : null}</main>
      <aside className="creator-growth-analysis"><header><h2>{advisor[0]}</h2><span>{slice.authorityRefs.length} 条依据</span></header><section className="creator-growth-analysis-summary"><span>当前判断</span><strong>{slice.authorityRefs.length ? "可基于正式记录继续核对" : "当前没有可验证业务对象"}</strong><p>{advisor[1]}没有正式记录时不生成姓名、联系方式、匹配分或经营结果。</p></section><section className="creator-growth-next-actions"><h3>下一步动作</h3><button type="button" onClick={openRelevantPreparation}>{advisor[2]}</button>{selected === "outreach" ? <button type="button" onClick={() => setPreparation("outreach_message")}>编写邀约内容</button> : null}<button type="button" onClick={() => { load(); setNotice("已重新读取栖月汇当前正式数据。" ); }}>重新读取业务数据</button><small>页面准备不会自动触达达人，也不会代替合同、履约或关系记录。</small></section><section className="creator-growth-colleagues"><h3>共享数字同事</h3><div><span>导购顾问</span><span>数据参谋</span><span>活动策划师</span><span>内容官</span><span>私域管家</span></div></section><details className="creator-growth-audit-context"><summary>技术与数据诊断</summary><dl><div><dt>租户</dt><dd>{response.tenant.orgId}/{response.tenant.projectId}</dd></div><div><dt>数据截止</dt><dd>{new Date(response.dataCutoff).toLocaleString("zh-CN", { hour12: false })}</dd></div><div><dt>内容校验</dt><dd>{slice.authorityRefs.length ? short(slice.authorityRefs[0]!.contentHash) : "无正式记录"}</dd></div></dl>{auditCodes.length ? <ul>{auditCodes.map((code) => <li key={code}>{code}</li>)}</ul> : <p>当前读取链无诊断项。</p>}<ThreeModuleClosureCard value={closure} /></details><footer><span>数据截止 {new Date(response.dataCutoff).toLocaleString("zh-CN", { hour12: false })}</span><button type="button" onClick={load}>重新读取</button></footer></aside>
    </div></div>{preparation ? <PreparationPanel purpose={preparation} current={workflowDrafts[preparation] ?? null} receipt={workflowReceipts[preparation] ?? null} history={workflowHistory[preparation] ?? []} busy={workflowBusy} error={workflowError} onClose={() => setPreparation(null)} onCommand={(command, values, restoreRevision) => { void executeWorkflow(command, values, restoreRevision); }} onNew={() => { setWorkflowDrafts((previous) => ({ ...previous, [preparation]: undefined })); setWorkflowHistory((previous) => ({ ...previous, [preparation]: [] })); setWorkflowReceipts((previous) => ({ ...previous, [preparation]: undefined })); setWorkflowError(""); }} /> : null}
  </section>;
}
