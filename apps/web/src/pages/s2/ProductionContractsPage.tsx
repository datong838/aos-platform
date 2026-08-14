import { useCallback, useEffect, useState } from "react";
import {
  aipProductionContracts,
  type ContractBlocker,
  type ArtifactRelationListResponse,
  type EvalContractListResponse,
  type EvidenceBundleListResponse,
  type ResponsibilityPlanListResponse,
  type ReviewIssueListResponse,
  type StageTemplateListResponse,
  type TaskBriefListResponse,
} from "../../api/aipProductionContracts";
import { PageChrome } from "../../components/PageChrome";

type AuthorityState = {
  briefs: TaskBriefListResponse;
  bundles: EvidenceBundleListResponse;
  evals: EvalContractListResponse;
  plans: ResponsibilityPlanListResponse;
  stages: StageTemplateListResponse;
  relations: ArtifactRelationListResponse;
  reviews: ReviewIssueListResponse;
};

const grid = { display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(300px,1fr))", gap: 16 } as const;
const itemStyle = { padding: "14px 0", borderTop: "1px solid var(--aos-border)" } as const;
const label: Record<string, string> = { ready: "就绪", blocked: "阻断", stale: "过期", unknown: "未知", draft: "草稿", frozen: "已冻结", complete: "完整", partial: "部分" };

function Blockers({ items }: { items: ContractBlocker[] }) {
  if (!items.length) return null;
  return <ul aria-label="阻断原因" style={{ margin: "8px 0 0", paddingLeft: 20 }}>{items.map(item => <li key={`${item.code}:${item.message}`}><code>{item.code}</code> · {item.message}</li>)}</ul>;
}

export function ProductionContractsPage() {
  const [state, setState] = useState<AuthorityState | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [planId, setPlanId] = useState("");
  const [taskId, setTaskId] = useState("");
  const [taskVersion, setTaskVersion] = useState("1");
  const [reviewIssueId, setReviewIssueId] = useState("");
  const [reviewRunId, setReviewRunId] = useState("");
  const [reviewReason, setReviewReason] = useState("");
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [briefs, bundles, evals, plans, stages, relations, reviews] = await Promise.all([
        aipProductionContracts.listBriefs(), aipProductionContracts.listBundles(),
        aipProductionContracts.listEvalContracts(), aipProductionContracts.listResponsibilityPlans(),
        aipProductionContracts.listStageTemplates(), aipProductionContracts.listArtifactRelations(),
        aipProductionContracts.listReviewIssues(),
      ]);
      setState({ briefs, bundles, evals, plans, stages, relations, reviews });
      setError("");
    } catch (e) {
      setState(null);
      setError(String((e as Error).message || e));
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  async function run(id: string, action: () => Promise<unknown>) {
    setBusy(id);
    try { await action(); await load(); }
    catch (e) { setError(String((e as Error).message || e)); }
    finally { setBusy(""); }
  }
  const freezeBrief = (id: string, version: number) => run(`brief:${id}`, () => aipProductionContracts.freezeBrief(id, version, `w2-ui-brief-freeze-${crypto.randomUUID()}`));
  const freezeEval = (id: string, version: number) => run(`eval:${id}`, () => aipProductionContracts.freezeEvalContract(id, version, `w2-ui-eval-freeze-${crypto.randomUUID()}`));
  const freezePlan = (id: string, version: number) => run(`plan:${id}`, () => aipProductionContracts.freezeResponsibilityPlan(id, version, `w2-ui-plan-freeze-${crypto.randomUUID()}`));
  const freezeStage = (id: string, version: number) => run(`stage:${id}`, () => aipProductionContracts.freezeStageTemplate(id, version, `w2-ui-stage-freeze-${crypto.randomUUID()}`));

  const selectedTemplate = state?.stages.items.find(item => item.templateId === templateId);
  const selectedPlan = state?.plans.items.find(item => item.planId === planId);
  const canCompile = Boolean(selectedTemplate && selectedPlan && taskId.trim() && Number.isInteger(Number(taskVersion)) && Number(taskVersion) > 0 && selectedTemplate.lifecycle === "frozen" && selectedTemplate.readiness === "ready" && selectedPlan.lifecycle === "frozen" && selectedPlan.readiness === "ready" && selectedPlan.coverage === "complete" && selectedTemplate.profile === selectedPlan.profile);
  const compile = () => {
    if (!selectedTemplate || !selectedPlan || !canCompile) return;
    void run("stage:compile", () => aipProductionContracts.compileStageTemplate(selectedTemplate.templateId, {
      taskId: taskId.trim(), expectedTaskVersion: Number(taskVersion), templateRevision: selectedTemplate.revision,
      templateContentHash: selectedTemplate.contentHash, profile: selectedTemplate.profile,
      responsibilityPlanRef: { resourceType: "ResponsibilityPlanRevision", resourceId: selectedPlan.planId, revision: selectedPlan.revision, contentHash: selectedPlan.contentHash },
    }, `w2-ui-stage-compile-${crypto.randomUUID()}`));
  };
  const selectedReview = state?.reviews.items.find(item => item.issueId === reviewIssueId && item.status === "open");
  const canReviewCommand = Boolean(selectedReview && reviewReason.trim());
  const resolveReview = () => { if (selectedReview && canReviewCommand) void run(`review:${selectedReview.issueId}`, () => aipProductionContracts.resolveReviewIssue(selectedReview.issueId, { expectedVersion: selectedReview.version, reason: reviewReason.trim(), resolutionRefs: [] }, `w2-ui-review-resolve-${crypto.randomUUID()}`)); };
  const returnReview = () => { if (selectedReview && canReviewCommand && reviewRunId.trim()) void run(`review:${selectedReview.issueId}`, () => aipProductionContracts.returnReviewIssue(selectedReview.issueId, { expectedVersion: selectedReview.version, runId: reviewRunId.trim(), targetStage: selectedReview.returnStage, reason: reviewReason.trim(), attemptIdempotencyKey: `w2-ui-attempt-${crypto.randomUUID()}` }, `w2-ui-review-return-${crypto.randomUUID()}`)); };

  return <PageChrome title="生产契约" lede="Brief、Evidence、Eval、Responsibility、Stage、Artifact Relation 与 Review 的租户权威视图；冻结不等于启动运行">
    {error && <div role="alert" className="notice bad">生产契约读取或操作失败：{error}</div>}
    {loading ? <div role="status" className="card">正在读取 PostgreSQL Production Contract authority…</div> : null}
    {!loading && state ? <>
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 16, flexWrap: "wrap" }}>
        <strong>{state.briefs.count} Brief</strong><span>{state.bundles.count} Evidence</span><span>{state.evals.count} Eval</span><span>{state.plans.count} Responsibility</span><span>{state.stages.count} Stage</span><span>{state.relations.count} Relation</span><span>{state.reviews.count} Review</span>
        <button className="btn" onClick={() => void load()}>刷新权威状态</button>
        <button className="btn primary" disabled title="必须从真实 Task 与权威依赖创建；本页不生成样例或隐式权威">创建契约（需真实依赖）</button>
      </div>
      <section style={grid}>
        <div className="card" style={{ padding: 18 }}><h2 style={{ marginTop: 0 }}>Task Brief</h2>
          {state.briefs.count === 0 ? <div className="notice">当前组织尚无 Brief。请从真实 Task 进入创建流程；本页不生成 Mock Task。</div> : state.briefs.items.map(item => <article key={item.briefId} style={itemStyle}><div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><strong>{item.briefType}</strong><span>{label[item.lifecycle] ?? item.lifecycle}</span></div><p><code>{item.briefId}@{item.revision}</code> · Task <code>{item.taskId}</code></p><small>version {item.version} · hash {item.contentHash.slice(0, 12)}…</small>{item.lifecycle === "draft" ? <button className="btn" disabled={busy === `brief:${item.briefId}`} onClick={() => void freezeBrief(item.briefId, item.version)} style={{ marginTop: 10 }}>{busy === `brief:${item.briefId}` ? "冻结中…" : "冻结当前 revision"}</button> : null}</article>)}
        </div>
        <div className="card" style={{ padding: 18 }}><h2 style={{ marginTop: 0 }}>Evidence Bundle</h2>
          {state.bundles.count === 0 ? <div className="notice">当前组织尚无 Bundle。Bundle 只能聚合已授权 Evidence exact ref，不能复制正文或用摘要冒充事实。</div> : state.bundles.items.map(item => <article key={`${item.bundleId}@${item.revision}`} style={itemStyle}><div style={{ display: "flex", justifyContent: "space-between" }}><strong>{item.bundleId}</strong><span>{item.freshness}</span></div><p>{item.itemRefs.length} 条 Evidence · 覆盖 {label[item.coverage] ?? item.coverage}</p><small>Brief {item.briefRef.resourceId}@{item.briefRef.revision}</small></article>)}
        </div>
        <div className="card" style={{ padding: 18 }}><h2 style={{ marginTop: 0 }}>Eval Contract</h2>
          {state.evals.count === 0 ? <div className="notice">当前组织尚无 Eval Contract。必须绑定真实 EvalSuite、PublicationEvent 与 ReleaseGateDecision 后才能就绪。</div> : state.evals.items.map(item => { const canFreeze = item.lifecycle === "draft" && item.readiness === "ready" && item.blockers.length === 0; return <article key={item.contractId} style={itemStyle}><div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><strong>{item.contractId}@{item.revision}</strong><span>{label[item.readiness] ?? item.readiness}</span></div><p>EvalSuite <code>{item.suiteRef.resourceId}@{item.suiteRef.revision}</code></p><small>{label[item.lifecycle] ?? item.lifecycle} · version {item.version} · {Object.keys(item.severityThresholds).length} 个阈值</small><Blockers items={item.blockers} />{item.lifecycle === "draft" ? <button className="btn" disabled={!canFreeze || busy === `eval:${item.contractId}`} title={canFreeze ? "冻结当前就绪 revision" : "存在阻断或状态未就绪，禁止冻结"} onClick={() => void freezeEval(item.contractId, item.version)} style={{ marginTop: 10 }}>{busy === `eval:${item.contractId}` ? "冻结中…" : "冻结 Eval"}</button> : null}</article>; })}
        </div>
        <div className="card" style={{ padding: 18 }}><h2 style={{ marginTop: 0 }}>Responsibility Plan</h2>
          {state.plans.count === 0 ? <div className="notice bad">当前组织尚无 Responsibility Plan。ResponsibilityTemplateRevision 权威未接入前保持 fail-closed，不用本地清单伪造职责覆盖。</div> : state.plans.items.map(item => { const canFreeze = item.lifecycle === "draft" && item.readiness === "ready" && item.coverage === "complete" && item.blockers.length === 0; return <article key={item.planId} style={itemStyle}><div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><strong>{item.profile}</strong><span>{label[item.readiness] ?? item.readiness}</span></div><p>{item.slots.length} 个职责槽 · 覆盖 {label[item.coverage] ?? item.coverage}</p>{item.uncoveredSlots.length ? <p>未覆盖：{item.uncoveredSlots.join("、")}</p> : null}<small>Template {item.templateRef.resourceId}@{item.templateRef.revision} · version {item.version}</small><Blockers items={item.blockers} />{item.lifecycle === "draft" ? <button className="btn" disabled={!canFreeze || busy === `plan:${item.planId}`} title={canFreeze ? "冻结完整且就绪的职责计划" : "职责覆盖不完整、存在阻断或状态未就绪"} onClick={() => void freezePlan(item.planId, item.version)} style={{ marginTop: 10 }}>{busy === `plan:${item.planId}` ? "冻结中…" : "冻结职责计划"}</button> : null}</article>; })}
        </div>
        <div className="card" style={{ padding: 18 }}><h2 style={{ marginTop: 0 }}>Stage Template</h2>
          {state.stages.count === 0 ? <div className="notice">当前组织尚无 StageTemplate。模板必须来自已验证资产包 exact ref，本页不生成隐式 Stage。</div> : state.stages.items.map(item => { const canFreeze = item.lifecycle === "draft" && item.readiness === "ready" && item.blockers.length === 0; return <article key={item.templateId} style={itemStyle}><div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><strong>{item.profile}</strong><span>{label[item.readiness] ?? item.readiness}</span></div><p>{item.stages.length} 个 Stage · <code>{item.templateId}@{item.revision}</code></p><small>{label[item.lifecycle] ?? item.lifecycle} · source {item.sourceBundleRef.resourceId}@{item.sourceBundleRef.revision}</small><Blockers items={item.blockers} />{item.lifecycle === "draft" ? <button className="btn" disabled={!canFreeze || busy === `stage:${item.templateId}`} title={canFreeze ? "冻结当前就绪模板" : "source exact ref 缺失、漂移或存在其他阻断"} onClick={() => void freezeStage(item.templateId, item.version)} style={{ marginTop: 10 }}>{busy === `stage:${item.templateId}` ? "冻结中…" : "冻结 Stage"}</button> : null}</article>; })}
        </div>
        <div className="card" style={{ padding: 18 }}><h2 style={{ marginTop: 0 }}>Artifact Relation</h2>
          {state.relations.count === 0 ? <div className="notice">当前组织尚无 Artifact Relation。只有两端 artifactId/contentHash 均匹配权威记录时才能建立关系。</div> : state.relations.items.map(item => <article key={item.relationId} style={itemStyle}><strong>{item.relationType}</strong><p><code>{item.fromArtifact.artifactId}</code> → <code>{item.toArtifact.artifactId}</code></p><small>{item.reason} · {item.createdBy}</small></article>)}
        </div>
        <div className="card" style={{ padding: 18 }}><h2 style={{ marginTop: 0 }}>Review Issue</h2>
          {state.reviews.count === 0 ? <div className="notice">当前组织尚无 Review Issue。问题必须绑定 exact Artifact、EvalReport 与 Evidence。</div> : state.reviews.items.map(item => <article key={item.issueId} style={itemStyle}><div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><strong>{item.severity} · {item.issueId}</strong><span>{item.status}</span></div><p>{item.suggestedFix}</p><small>退回 Stage：{item.returnStage} · version {item.version}</small></article>)}
        </div>
      </section>
      <section className="card" style={{ padding: 18, marginTop: 16 }} aria-label="Stage 编译命令">
        <h2 style={{ marginTop: 0 }}>Stage 编译为 canonical Plan 草稿</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 12 }}>
          <label>StageTemplate<select value={templateId} onChange={event => setTemplateId(event.target.value)}><option value="">选择已冻结模板</option>{state.stages.items.map(item => <option key={item.templateId} value={item.templateId}>{item.profile} · {item.templateId}@{item.revision}</option>)}</select></label>
          <label>ResponsibilityPlan<select value={planId} onChange={event => setPlanId(event.target.value)}><option value="">选择已冻结职责计划</option>{state.plans.items.map(item => <option key={item.planId} value={item.planId}>{item.profile} · {item.planId}@{item.revision}</option>)}</select></label>
          <label>真实 Task ID<input value={taskId} onChange={event => setTaskId(event.target.value)} placeholder="task-…" /></label>
          <label>Task version<input type="number" min="1" value={taskVersion} onChange={event => setTaskVersion(event.target.value)} /></label>
        </div>
        <button className="btn primary" disabled={!canCompile || busy === "stage:compile"} title={canCompile ? "只创建 draft PlanRevision，不启动 TaskRun" : "需选择同 profile、已冻结且就绪的 StageTemplate/ResponsibilityPlan，并填写真实 Task"} onClick={compile} style={{ marginTop: 12 }}>{busy === "stage:compile" ? "编译中…" : "编译为 Plan 草稿"}</button>
      </section>
      <section className="card" style={{ padding: 18, marginTop: 16 }} aria-label="Review 处置命令">
        <h2 style={{ marginTop: 0 }}>Review 处置</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 12 }}>
          <label>Open Issue<select value={reviewIssueId} onChange={event => setReviewIssueId(event.target.value)}><option value="">选择待处置问题</option>{state.reviews.items.filter(item => item.status === "open").map(item => <option key={item.issueId} value={item.issueId}>{item.severity} · {item.issueId}</option>)}</select></label>
          <label>真实运行 ID<input value={reviewRunId} onChange={event => setReviewRunId(event.target.value)} placeholder="仅退回时必填 run-…" /></label>
          <label>处置原因<input value={reviewReason} onChange={event => setReviewReason(event.target.value)} placeholder="必填，进入审计事件" /></label>
        </div>
        <div style={{ display: "flex", gap: 10, marginTop: 12 }}><button className="btn" disabled={!canReviewCommand || Boolean(busy)} onClick={resolveReview}>标记已解决</button><button className="btn primary" disabled={!canReviewCommand || !reviewRunId.trim() || Boolean(busy)} title="只向真实 running TaskRun 的目标 Stage 追加 queued attempt" onClick={returnReview}>退回目标 Stage</button></div>
      </section>
      <div className="notice" style={{ marginTop: 16 }}>运行门保持阻断：Production Contract authority 齐备且冻结，仍不等于 AgentRun 可启动；W2-D Impact / Start Gate 与 AIP-7 Route / Provider / Binding 必须独立通过。</div>
    </> : null}
  </PageChrome>;
}
