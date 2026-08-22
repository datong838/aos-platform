import { useCallback, useEffect, useState } from "react";
import {
  aipProductionContracts,
  type ContractBlocker,
  type ArtifactRelationListResponse,
  type EvalContractListResponse,
  type EvidenceBundleListResponse,
  type ImpactDimension,
  type ImpactPreviewListResponse,
  type ImpactPreviewRevision,
  type ProductionContextListResponse,
  type ProductionStartDecisionListResponse,
  type ResponsibilityPlanListResponse,
  type ReviewIssueListResponse,
  type StageTemplateListResponse,
  type TaskBriefListResponse,
} from "../../api/aipProductionContracts";
import { aipActionsSdk, type ActionProposalList } from "../../api/aipActions";
import { apiGet } from "../../api/client";
import { PageChrome } from "../../components/PageChrome";

type AuthorityState = {
  briefs: TaskBriefListResponse;
  bundles: EvidenceBundleListResponse;
  evals: EvalContractListResponse;
  plans: ResponsibilityPlanListResponse;
  stages: StageTemplateListResponse;
  relations: ArtifactRelationListResponse;
  reviews: ReviewIssueListResponse;
  previews: ImpactPreviewListResponse;
  starts: ProductionStartDecisionListResponse;
  contexts: ProductionContextListResponse;
  actionProposals: ActionProposalList;
};

const grid = { display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(300px,1fr))", gap: 16 } as const;
const itemStyle = { padding: "14px 0", borderTop: "1px solid var(--aos-border)" } as const;
const label: Record<string, string> = { ready: "就绪", blocked: "阻断", stale: "过期", unknown: "未知", measured: "实测", estimated: "估算", draft: "草稿", frozen: "已冻结", complete: "完整", partial: "部分" };
const impactLabels: Record<string,string>={objectScope:"对象范围",channelScope:"渠道范围",cost:"成本",budget:"预算余量",risks:"主要风险",reversibility:"回滚/补偿",approvalChain:"审批链",rateCapacityKill:"限速/容量/熔断"};

function Blockers({ items }: { items: ContractBlocker[] }) {
  if (!items.length) return null;
  return <ul aria-label="阻断原因" style={{ margin: "8px 0 0", paddingLeft: 20 }}>{items.map(item => <li key={`${item.code}:${item.message}`}><code>{item.code}</code> · {item.message}</li>)}</ul>;
}
function Quality({name,item}:{name:string;item:ImpactDimension}){return <div style={{padding:"8px 10px",border:"1px solid var(--aos-border)",borderRadius:6}}><strong>{impactLabels[name]??name}</strong><div>{item.quality==="unknown"?"未知（不以 0 代替）":label[item.quality]??item.quality}</div><small>{item.sourceRefs.length} 条来源{item.cutoffAt?` · 截止 ${new Date(item.cutoffAt).toLocaleString()}`:""}</small></div>}

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
  const [previewId,setPreviewId]=useState("");
  const [productionContextId,setProductionContextId]=useState("");
  const [startTaskVersion,setStartTaskVersion]=useState("1");
  const [actionProposalId,setActionProposalId]=useState("");
  const [logicGraphId,setLogicGraphId]=useState("");
  const [logicRevision,setLogicRevision]=useState("1");
  const [logicGraphHash,setLogicGraphHash]=useState("");
  const [publishedLogic,setPublishedLogic]=useState<Array<{id:string;name:string;revision:number;graph_hash:string;published_version?:number|null}>>([]);
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [briefs, bundles, evals, plans, stages, relations, reviews, contexts, previews, starts, actionProposals, logicList] = await Promise.all([
        aipProductionContracts.listBriefs(), aipProductionContracts.listBundles(),
        aipProductionContracts.listEvalContracts(), aipProductionContracts.listResponsibilityPlans(),
        aipProductionContracts.listStageTemplates(), aipProductionContracts.listArtifactRelations(),
        aipProductionContracts.listReviewIssues(), aipProductionContracts.listProductionContexts(), aipProductionContracts.listImpactPreviews(),
        aipProductionContracts.listProductionStartDecisions(),
        aipActionsSdk.list(500),
        apiGet<{items?:Array<{id:string;name:string;revision:number;graph_hash:string;published_version?:number|null;persisted?:boolean}>}>("/v1/aip/logic/graphs").catch(()=>({items:[] as Array<{id:string;name:string;revision:number;graph_hash:string;published_version?:number|null;persisted?:boolean}>})),
      ]);
      setPublishedLogic((logicList.items||[]).filter(item=>item.persisted!==false && Number(item.published_version||0)>0 && /^[0-9a-f]{64}$/.test(item.graph_hash)));
      setState({ briefs, bundles, evals, plans, stages, relations, reviews, contexts, previews, starts, actionProposals });
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
  const selectedPreview=state?.previews.items.find(item=>item.previewId===previewId);
  const selectedProductionContext=state?.contexts.items.find(item=>item.contextId===productionContextId);
  const eligibleActionProposals=(state?.actionProposals.items??[]).filter(({proposal})=>{
    const ref=proposal.impactPreviewRef;
    return Boolean(selectedPreview&&proposal.status==="approved"&&new Date(proposal.expiresAt).getTime()>Date.now()&&proposal.taskId===selectedPreview.taskId&&ref?.resourceType==="ImpactPreviewRevision"&&ref.resourceId===selectedPreview.previewId&&ref.revision===selectedPreview.revision&&ref.contentHash===selectedPreview.contentHash);
  });
  const selectedActionProposal=eligibleActionProposals.find(({proposal})=>proposal.id===actionProposalId);
  const positiveInteger=(value:string)=>Number.isInteger(Number(value))&&Number(value)>0;
  const startDisabledReason=(()=>{if(!selectedPreview)return"请选择 ImpactPreview exact revision";if(!selectedProductionContext)return"请选择 ProductionContext exact revision";if(selectedProductionContext.lifecycle!=="frozen"||selectedProductionContext.readiness!=="ready"||selectedProductionContext.blockers.length)return"ProductionContext 尚未 frozen + ready";if(selectedProductionContext.taskId!==selectedPreview.taskId)return"ProductionContext 与 Preview 不属于同一 Task";if(selectedPreview.lifecycle!=="frozen")return"Preview 尚未冻结";if(selectedPreview.readiness!=="ready")return`Preview 当前为${label[selectedPreview.readiness]??selectedPreview.readiness}`;if(selectedPreview.blockers.length)return"Preview 仍有权威阻断";if(new Date(selectedPreview.expiresAt).getTime()<=Date.now())return"Preview 已过期，请刷新并重新评估";if(!positiveInteger(startTaskVersion))return"Task version 必须大于 0";if(eligibleActionProposals.length===0)return"当前 Preview 没有同 Task、同 exact revision、已批准且未过期的 ActionProposal";if(!selectedActionProposal)return"请选择可启动的 ActionProposal exact revision";if(!logicGraphId.trim()||!positiveInteger(logicRevision)||!/^[0-9a-f]{64}$/.test(logicGraphHash.trim()))return"请填写已发布 LogicGraph ID、revision 与 exact graph hash";if(publishedLogic.length===0)return"当前组织尚无已发布 Logic；空图/未发布 revision 不可 start";return"";})();
  const freezePreview=(item:ImpactPreviewRevision)=>run(`preview:${item.previewId}`,()=>aipProductionContracts.freezeImpactPreview(item.previewId,item.version,`w2-ui-preview-freeze-${crypto.randomUUID()}`));
  const applyPublishedLogic=(graphId:string)=>{
    const hit=publishedLogic.find(item=>item.id===graphId);
    if(!hit){setLogicGraphId("");return;}
    setLogicGraphId(hit.id);
    setLogicRevision(String(hit.revision));
    setLogicGraphHash(hit.graph_hash);
  };
  const startProduction=()=>{if(!selectedPreview||!selectedProductionContext||!selectedActionProposal||startDisabledReason)return;const proposal=selectedActionProposal.proposal;void run("production:start",()=>aipProductionContracts.startProduction({taskId:selectedPreview.taskId,expectedTaskVersion:Number(startTaskVersion),productionContextRef:{resourceType:"ProductionContextRevision",resourceId:selectedProductionContext.contextId,revision:selectedProductionContext.revision,contentHash:selectedProductionContext.contentHash},planRef:selectedPreview.planRef,previewRef:{resourceType:"ImpactPreviewRevision",resourceId:selectedPreview.previewId,revision:selectedPreview.revision,contentHash:selectedPreview.contentHash},actionProposalRef:{proposalId:proposal.id,version:proposal.version,proposalHash:proposal.proposalHash},logicGraphId:logicGraphId.trim(),logicRevision:Number(logicRevision),logicGraphHash:logicGraphHash.trim()},`w2-ui-production-start-${crypto.randomUUID()}`));};

  return <PageChrome title="生产契约" lede="任务简报、证据包、评测契约、职责计划、阶段模板、产物关系与评审的租户权威视图；冻结不等于启动运行">
    {error && <div role="alert" className="notice bad">生产契约读取或操作失败：{error}</div>}
    {loading ? <div role="status" className="card">正在读取 PostgreSQL Production Contract authority…</div> : null}
    {!loading && state ? <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(110px,1fr))", gap: 10, marginBottom: 16 }}>
        {[
          ["Brief", state.briefs.count],
          ["Bundle", state.bundles.count],
          ["Eval", state.evals.count],
          ["职责计划", state.plans.count],
          ["阶段模板", state.stages.count],
          ["产物关系", state.relations.count],
          ["评审", state.reviews.count],
          ["Preview", state.previews.count],
          ["Proposal", state.actionProposals.count],
          ["Start", state.starts.count],
        ].map(([name, count]) => (
          <div key={String(name)} className="card" style={{ padding: "10px 12px" }}>
            <div style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>{name}</div>
            <div style={{ fontSize: 22, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{count}</div>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 16, flexWrap: "wrap" }}>
        <button className="btn" onClick={() => void load()}>刷新权威状态</button>
        <button className="btn primary" disabled title="必须从真实 Task 与权威依赖创建；本页不生成样例或隐式权威">创建契约（需真实依赖）</button>
        <span className="notice" style={{ padding: "6px 10px" }}>密表运维台 · 空态诚实 · 启动门 fail-closed</span>
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
      <section className="card" style={{ padding:18,marginTop:16 }} aria-label="Impact Preview 与 Start 组合门">
        <h2 style={{marginTop:0}}>Impact Preview 与 Start 组合门</h2>
        <p>Preview 只呈现权威影响评估；unknown 不显示为 0。只有 frozen + ready 的 exact revision 才能提交组合门，且成功只代表创建 canonical TaskRun，不代表 AgentRun 或 Provider 已运行。</p>
        {state.previews.count===0?<div className="notice">当前组织尚无 ImpactPreview。请从真实 Task、Plan 与冻结的生产契约创建；本页不生成样例 Preview、费用或运行状态。</div>:state.previews.items.map(item=>{const canFreeze=item.lifecycle==="draft"&&item.readiness==="ready"&&!item.blockers.length;return <article key={`${item.previewId}@${item.revision}`} style={itemStyle}>
          <div style={{display:"flex",justifyContent:"space-between",gap:12,flexWrap:"wrap"}}><strong>{item.previewId}@{item.revision}</strong><span>{label[item.lifecycle]??item.lifecycle} · {label[item.readiness]??item.readiness}</span></div>
          <p>Task <code>{item.taskId}</code> · 到期 {new Date(item.expiresAt).toLocaleString()}</p>
          <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(170px,1fr))",gap:8}}>{Object.entries(item.impact).map(([name,dimension])=><Quality key={name} name={name} item={dimension}/>)}</div>
          <Blockers items={item.blockers}/>
          <details style={{marginTop:10}}><summary>展开 exact refs</summary><ul><li>Plan <code>{item.planRef.resourceId}@{item.planRef.revision}</code></li><li>Brief <code>{item.briefRef.resourceId}@{item.briefRef.revision}</code></li><li>Evidence <code>{item.evidenceBundleRef.resourceId}@{item.evidenceBundleRef.revision}</code></li><li>Eval <code>{item.evalContractRef.resourceId}@{item.evalContractRef.revision}</code></li><li>Responsibility <code>{item.responsibilityPlanRef.resourceId}@{item.responsibilityPlanRef.revision}</code></li><li>Stage <code>{item.stageTemplateRef.resourceId}@{item.stageTemplateRef.revision}</code></li><li>dependency snapshot <code>{item.dependencySnapshotHash.slice(0,16)}…</code></li><li>actionBindingHash <code>{item.actionBindingHash.slice(0,16)}…</code>（只读，服务端）</li></ul></details>
          {item.lifecycle==="draft"?<button className="btn" disabled={!canFreeze||busy===`preview:${item.previewId}`} title={canFreeze?"冻结当前就绪 Preview exact revision":"Preview 非 ready 或仍有 blocker，禁止冻结"} onClick={()=>void freezePreview(item)} style={{marginTop:10}}>{busy===`preview:${item.previewId}`?"冻结中…":"冻结 Preview"}</button>:null}
        </article>})}
        <h3>受控创建 TaskRun</h3>
        <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(220px,1fr))",gap:12}}>
          <label>ImpactPreview<select aria-label="ImpactPreview exact revision" value={previewId} onChange={event=>{setPreviewId(event.target.value);setActionProposalId("");}}><option value="">选择 exact revision</option>{state.previews.items.map(item=><option key={`${item.previewId}@${item.revision}`} value={item.previewId}>{item.previewId}@{item.revision} · {label[item.lifecycle]??item.lifecycle}/{label[item.readiness]??item.readiness}</option>)}</select></label>
          <label>ProductionContext<select aria-label="ProductionContext exact revision" value={productionContextId} onChange={event=>setProductionContextId(event.target.value)}><option value="">选择 frozen + ready exact revision</option>{state.contexts.items.map(item=><option key={`${item.contextId}@${item.revision}`} value={item.contextId}>{item.contextId}@{item.revision} · {label[item.lifecycle]??item.lifecycle}/{label[item.readiness]??item.readiness}</option>)}</select></label>
          <label>Task version<input aria-label="启动 Task version" type="number" min="1" value={startTaskVersion} onChange={event=>setStartTaskVersion(event.target.value)}/></label>
          <label>ActionProposal<select aria-label="ActionProposal exact revision" value={actionProposalId} onChange={event=>setActionProposalId(event.target.value)} data-testid="start-action-proposal-select"><option value="">选择同 Preview 的 approved exact revision</option>{eligibleActionProposals.map(({proposal})=><option key={proposal.id} value={proposal.id}>{proposal.actionType.actionTypeId} · {proposal.id}@v{proposal.version}</option>)}</select></label>
          <label>LogicGraph ID<input aria-label="LogicGraph ID" value={logicGraphId} onChange={event=>setLogicGraphId(event.target.value)} placeholder="logic-…" data-testid="start-logic-graph-id"/></label>
          <label>Logic revision<input aria-label="Logic revision" type="number" min="1" value={logicRevision} onChange={event=>setLogicRevision(event.target.value)} data-testid="start-logic-revision"/></label>
          <label>Logic exact hash<input aria-label="Logic exact hash" value={logicGraphHash} onChange={event=>setLogicGraphHash(event.target.value.trim())} placeholder="64 位 graph_hash" data-testid="start-logic-hash"/></label>
          <label>已发布 Logic<select aria-label="已发布 Logic" value={logicGraphId} onChange={event=>applyPublishedLogic(event.target.value)} data-testid="start-logic-published-select"><option value="">从已发布列表选用</option>{publishedLogic.map(item=><option key={item.id} value={item.id}>{item.name} · {item.id}@r{item.revision}</option>)}</select></label>
        </div>
        {selectedPreview&&eligibleActionProposals.length===0?<div className="notice" role="status" style={{marginTop:12}} data-testid="start-action-proposal-empty">当前 Preview 没有同 Task、同 exact revision、已批准且未过期的 ActionProposal；请回到 Draft 审批台处理真实 Proposal，本页不生成或批准样例。</div>:null}
        {selectedActionProposal?<div className="notice" style={{marginTop:12}} data-testid="start-action-proposal-exact">已锁定 Proposal <code>{selectedActionProposal.proposal.id}@v{selectedActionProposal.proposal.version}</code> · hash <code>{selectedActionProposal.proposal.proposalHash.slice(0,12)}…</code></div>:null}
        {publishedLogic.length===0?<div className="notice" role="status" style={{marginTop:12}} data-testid="start-logic-empty">尚无已发布 LogicGraph；空图或未发布 revision 不能进入 ProductionStart。</div>:null}
        {startDisabledReason?<div className="notice" role="status" style={{marginTop:12}}>启动门保持关闭：{startDisabledReason}。可先刷新权威状态；若依赖漂移，请回到对应 authority 修订后创建新 Preview。</div>:<div className="notice" style={{marginTop:12}}>组合门输入完整；服务端仍会重新核验 Preview、Proposal、Approval、Lease、Route、Binding 与容量。</div>}
        <button className="btn primary" disabled={Boolean(startDisabledReason)||busy==="production:start"} title={startDisabledReason||"只创建 canonical TaskRun；不启动 AgentRun/Provider"} onClick={startProduction} style={{marginTop:12}}>{busy==="production:start"?"组合门核验中…":"通过组合门并创建 TaskRun"}</button>
        <h3>Start Decision 审计记录</h3>
        {state.starts.count===0?<div className="notice">当前组织尚无 Start Decision；这表示没有提交过组合门，不等于运行成功。</div>:state.starts.items.map(item=><article key={item.decisionId} style={itemStyle}><div style={{display:"flex",justifyContent:"space-between",gap:12}}><strong>{item.decisionId}</strong><span>{item.status==="started"?"已创建 TaskRun（尚未启动 AgentRun）":label[item.status]??item.status}</span></div><p>Task <code>{item.taskId}</code> · Preview <code>{item.previewRef.resourceId}@{item.previewRef.revision}</code></p>{item.taskRunRef?<small>TaskRun <code>{item.taskRunRef.resourceId}</code></small>:null}<Blockers items={item.blockers}/></article>)}
      </section>
      <section className="card" style={{ padding: 18, marginTop: 16 }} aria-label="Stage 编译命令">
        <h2 style={{ marginTop: 0 }}>Stage 编译为 canonical Plan 草稿</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 12 }}>
          <label>StageTemplate<select aria-label="StageTemplate exact revision" value={templateId} onChange={event => setTemplateId(event.target.value)}><option value="">选择已冻结模板</option>{state.stages.items.map(item => <option key={item.templateId} value={item.templateId}>{item.profile} · {item.templateId}@{item.revision}</option>)}</select></label>
          <label>ResponsibilityPlan<select aria-label="ResponsibilityPlan exact revision" value={planId} onChange={event => setPlanId(event.target.value)}><option value="">选择已冻结职责计划</option>{state.plans.items.map(item => <option key={item.planId} value={item.planId}>{item.profile} · {item.planId}@{item.revision}</option>)}</select></label>
          <label>真实 Task ID<input aria-label="编译真实 Task ID" value={taskId} onChange={event => setTaskId(event.target.value)} placeholder="task-…" /></label>
          <label>Task version<input aria-label="编译 Task version" type="number" min="1" value={taskVersion} onChange={event => setTaskVersion(event.target.value)} /></label>
        </div>
        <button className="btn primary" disabled={!canCompile || busy === "stage:compile"} title={canCompile ? "只创建 draft PlanRevision，不启动 TaskRun" : "需选择同 profile、已冻结且就绪的 StageTemplate/ResponsibilityPlan，并填写真实 Task"} onClick={compile} style={{ marginTop: 12 }}>{busy === "stage:compile" ? "编译中…" : "编译为 Plan 草稿"}</button>
      </section>
      <section className="card" style={{ padding: 18, marginTop: 16 }} aria-label="Review 处置命令">
        <h2 style={{ marginTop: 0 }}>Review 处置</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 12 }}>
          <label>Open Issue<select aria-label="待处置 Open Issue" value={reviewIssueId} onChange={event => setReviewIssueId(event.target.value)}><option value="">选择待处置问题</option>{state.reviews.items.filter(item => item.status === "open").map(item => <option key={item.issueId} value={item.issueId}>{item.severity} · {item.issueId}</option>)}</select></label>
          <label>真实运行 ID<input aria-label="Review 真实运行 ID" value={reviewRunId} onChange={event => setReviewRunId(event.target.value)} placeholder="仅退回时必填 run-…" /></label>
          <label>处置原因<input aria-label="Review 处置原因" value={reviewReason} onChange={event => setReviewReason(event.target.value)} placeholder="必填，进入审计事件" /></label>
        </div>
        <div style={{ display: "flex", gap: 10, marginTop: 12 }}><button className="btn" disabled={!canReviewCommand || Boolean(busy)} title={busy ? "正在提交处置，请稍候" : canReviewCommand ? "将当前 Open Issue 标记为已解决并写入审计事件" : "请选择待处置 Open Issue 并填写处置原因"} onClick={resolveReview}>标记已解决</button><button className="btn primary" disabled={!canReviewCommand || !reviewRunId.trim() || Boolean(busy)} title="只向真实 running TaskRun 的目标 Stage 追加 queued attempt" onClick={returnReview}>退回目标 Stage</button></div>
      </section>
      <div className="notice" style={{ marginTop: 16 }}>W2-D Preview / Start 组合门已接入 PostgreSQL authority；即使 Start Decision 为 started，也只创建 canonical TaskRun。AgentRun、Route、Provider、Binding 与容量仍由独立服务端门禁控制。</div>
    </> : null}
  </PageChrome>;
}
