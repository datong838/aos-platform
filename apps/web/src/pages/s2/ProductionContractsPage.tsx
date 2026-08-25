import { useCallback, useEffect, useRef, useState } from "react";
import {
  aipProductionContracts,
  type ContractBlocker,
  type ArtifactRelationListResponse,
  type EvalContractListResponse,
  type EvalContractDiff,
  type EvidenceBundleListResponse,
  type ExactRevisionRef,
  type ImpactDimension,
  type ImpactPreviewListResponse,
  type ImpactPreviewRevision,
  type ProductionContextListResponse,
  type ProductionStartDecisionListResponse,
  type ProfileConfirmationListResponse,
  type ProfileRecommendationListResponse,
  type ProfileRecommendationRevision,
  type ProjectedCostRange,
  type ResponsibilityPlanListResponse,
  type ReviewIssueListResponse,
  type StageTemplateListResponse,
  type StageCompilationResult,
  type TaskBriefListResponse,
} from "../../api/aipProductionContracts";
import { aipAgentControl, type CapabilityCatalogResponse } from "../../api/aipAgentControl";
import { aipActionsSdk, type ActionProposalList } from "../../api/aipActions";
import { apiGet } from "../../api/client";
import { PageChrome } from "../../components/PageChrome";
import { BlockerList as ProductionBlockerList, EvidenceBundleDrawer } from "../../components/workshop/production";
import { actionDisplayName, businessDisplayName, capabilityDisplayName, contractSectionDisplayName, statusDisplayName } from "../../lib/aipChineseLabels";

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
  profileRecommendations: ProfileRecommendationListResponse;
  profileConfirmations: ProfileConfirmationListResponse;
  capabilities: CapabilityCatalogResponse;
};

const grid = { display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(300px,1fr))", gap: 16 } as const;
const itemStyle = { padding: "14px 0", borderTop: "1px solid var(--aos-border)" } as const;
const label: Record<string, string> = { ready: "就绪", blocked: "阻断", stale: "过期", unknown: "未知", measured: "实测", estimated: "估算", draft: "草稿", frozen: "已冻结", complete: "完整", partial: "部分" };
const impactLabels: Record<string,string>={objectScope:"对象范围",channelScope:"渠道范围",cost:"成本",budget:"预算余量",risks:"主要风险",reversibility:"回滚/补偿",approvalChain:"审批链",rateCapacityKill:"限速/容量/熔断"};
const profileLabels={LITE:"轻量档",STANDARD:"标准档",FULL:"完整档"} as const;

function projectedCostText(item:ProjectedCostRange){return item.unknownCodes.length?`未知（不以 0 代替） · ${item.unknownCodes.join("、")}`:`${item.currency} ${item.lowerAmount}–${item.upperAmount}`;}

function Blockers({ items }: { items: ContractBlocker[] }) {
  if (!items.length) return null;
  return <ProductionBlockerList items={items.map(item => {
    const action = blockerAction(item.code);
    return { code: item.code, message: contractBusinessText(item.message), owner: action.owner, requiredAction: action.label, cutoffAt: null, href: action.href };
  })} />;
}
function blockerAction(code: string): { owner: string; href: string; label: string } {
  if (/ROUTE|PROVIDER|MODEL|HEALTH|CAPACITY|PRICE/i.test(code)) return { owner: "模型与路由负责人", href: "/aip/model-runtime", label: "检查模型运行准备" };
  if (/BINDING|CAPABILITY|SKILL/i.test(code)) return { owner: "AIP 智能体运行平台", href: "/aip/agent-registry", label: "刷新智能体运行准备" };
  if (/EVAL|RELEASE|PUBLICATION/i.test(code)) return { owner: "评测与发布负责人", href: "/aip/evals", label: "检查评测与发布状态" };
  if (/EVIDENCE|BUNDLE|SOURCE/i.test(code)) return { owner: "数据与证据负责人", href: "/aip/observability", label: "检查证据与可观测信息" };
  return { owner: "AIP 上线审批负责人", href: "/aip/production-contracts", label: "刷新上线执行审批" };
}
function Quality({name,item}:{name:string;item:ImpactDimension}){return <div style={{padding:"8px 10px",border:"1px solid var(--aos-border)",borderRadius:6}}><strong>{impactLabels[name]??name}</strong><div>{item.quality==="unknown"?"未知（不以 0 代替）":label[item.quality]??item.quality}</div><small>{item.sourceRefs.length} 条来源{item.cutoffAt?` · 截止 ${new Date(item.cutoffAt).toLocaleString()}`:""}</small></div>}
function diffValue(value:unknown){if(value===null)return"未设置";if(typeof value==="string"||typeof value==="number"||typeof value==="boolean")return String(value);try{return JSON.stringify(value)}catch{return"无法安全展示"}}
function sameExact(left:ExactRevisionRef|null|undefined,right:ExactRevisionRef|null|undefined){return Boolean(left&&right&&left.resourceType===right.resourceType&&left.resourceId===right.resourceId&&left.revision===right.revision&&left.contentHash===right.contentHash);}

function contractBusinessText(value: string): string {
  const raw = String(value || "");
  if (/w-e4 bootstrap: link two sealed pilot artifacts as variants/i.test(raw)) {
    return "将两个已封存的试运行产物登记为同类变体，供评审台对照。";
  }
  return raw
    .replace(/content\.review/g, "内容审核")
    .replace(/CapabilityBinding/g, "能力绑定")
    .replace(/ResponsibilityPlanRevision/g, "职责计划修订")
    .replace(/readiness/g, "就绪状态")
    .replace(/operational/g, "可运行")
    .replace(/frozen/g, "已冻结")
    .replace(/Bundle exact ref/g, "证据包精确引用")
    .replace(/impact/g, "影响")
    .replace(/unknown/g, "未知");
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
  const [compileProductionContextId,setCompileProductionContextId]=useState("");
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
  const [evidenceDrawerBundleId, setEvidenceDrawerBundleId] = useState("");
  const [evalDiff,setEvalDiff]=useState<EvalContractDiff|null>(null);
  const [lastCompilation,setLastCompilation]=useState<StageCompilationResult|null>(null);
  const evidenceDrawerTriggerRef = useRef<HTMLElement | null>(null);
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [briefs, bundles, evals, plans, stages, relations, reviews, contexts, previews, starts, profileRecommendations, profileConfirmations, capabilities, actionProposals, logicList] = await Promise.all([
        aipProductionContracts.listBriefs(), aipProductionContracts.listBundles(),
        aipProductionContracts.listEvalContracts(), aipProductionContracts.listResponsibilityPlans(),
        aipProductionContracts.listStageTemplates(), aipProductionContracts.listArtifactRelations(),
        aipProductionContracts.listReviewIssues(), aipProductionContracts.listProductionContexts(), aipProductionContracts.listImpactPreviews(),
        aipProductionContracts.listProductionStartDecisions(),
        aipProductionContracts.listProfileRecommendations(),
        aipProductionContracts.listProfileConfirmations(),
        aipAgentControl.listCapabilities(),
        aipActionsSdk.list(500),
        apiGet<{items?:Array<{id:string;name:string;revision:number;graph_hash:string;published_version?:number|null;persisted?:boolean}>}>("/v1/aip/logic/graphs").catch(()=>({items:[] as Array<{id:string;name:string;revision:number;graph_hash:string;published_version?:number|null;persisted?:boolean}>})),
      ]);
      setPublishedLogic((logicList.items||[]).filter(item=>item.persisted!==false && Number(item.published_version||0)>0 && /^[0-9a-f]{64}$/.test(item.graph_hash)));
      setState({ briefs, bundles, evals, plans, stages, relations, reviews, contexts, previews, starts, profileRecommendations, profileConfirmations, capabilities, actionProposals });
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
  const loadEvalDiff=async(id:string,revision:number)=>{if(revision<=1)return;setBusy(`eval-diff:${id}`);try{setEvalDiff(await aipProductionContracts.diffEvalContract(id,revision-1,revision));setError("");}catch(e){setEvalDiff(null);setError(String((e as Error).message||e));}finally{setBusy("");}};
  const freezePlan = (id: string, version: number) => run(`plan:${id}`, () => aipProductionContracts.freezeResponsibilityPlan(id, version, `w2-ui-plan-freeze-${crypto.randomUUID()}`));
  const freezeStage = (id: string, version: number) => run(`stage:${id}`, () => aipProductionContracts.freezeStageTemplate(id, version, `w2-ui-stage-freeze-${crypto.randomUUID()}`));
  const confirmProfile=(item:ProfileRecommendationRevision)=>run(`profile:${item.recommendationId}`,()=>aipProductionContracts.confirmMediaProfile({recommendationId:item.recommendationId,recommendationRevision:item.revision,recommendationHash:item.contentHash,selectedProfile:item.recommendedProfile,reason:"接受当前建议与预计成本区间"},`w7-ui-profile-confirm-${crypto.randomUUID()}`,item.contentHash));

  const selectedTemplate = state?.stages.items.find(item => item.templateId === templateId);
  const evidenceDrawerBundle = state?.bundles.items.find(item => item.bundleId === evidenceDrawerBundleId);
  const selectedPlan = state?.plans.items.find(item => item.planId === planId);
  const selectedCompileProductionContext=state?.contexts.items.find(item=>item.contextId===compileProductionContextId);
  const selectedPlanRef=selectedPlan?{resourceType:"ResponsibilityPlanRevision",resourceId:selectedPlan.planId,revision:selectedPlan.revision,contentHash:selectedPlan.contentHash}:null;
  const governedCompile=["LITE","STANDARD","FULL"].includes(selectedTemplate?.profile??"");
  const selectedRecommendation=selectedPlan?.profileRecommendationRef?state?.profileRecommendations.items.find(item=>sameExact(selectedPlan.profileRecommendationRef,item?{resourceType:"ProfileRecommendationRevision",resourceId:item.recommendationId,revision:item.revision,contentHash:item.contentHash}:null)):undefined;
  const selectedConfirmation=selectedPlan?.profileConfirmationId?state?.profileConfirmations.items.find(item=>item.confirmationId===selectedPlan.profileConfirmationId):undefined;
  const requiredCapabilityIds=[...new Set(selectedPlan?.slots.flatMap(item=>item.requiredCapabilityIds)??[])].sort();
  const selectedCapabilities=requiredCapabilityIds.map(capabilityId=>state?.capabilities.items.find(item=>item.capabilityId===capabilityId&&item.lifecycle==="published"&&item.readiness==="available"));
  const capabilityRefs=Object.fromEntries(selectedCapabilities.filter((item):item is NonNullable<typeof item>=>Boolean(item)).map(item=>[item.capabilityId,{resourceType:"CapabilityRevision",resourceId:item.capabilityId,revision:item.revision,contentHash:item.contentHash}]));
  const governedCompileDisabledReason=(()=>{if(!governedCompile)return"";if(!selectedRecommendation)return"缺少职责计划锁定的档位建议精确修订";if(!selectedPlan?.mergePolicyRef)return"缺少职责计划锁定的合并策略精确修订";if(!selectedConfirmation)return"缺少职责计划锁定的人工确认";if(selectedConfirmation.recommendationId!==selectedRecommendation.recommendationId||selectedConfirmation.recommendationRevision!==selectedRecommendation.revision||selectedConfirmation.recommendationHash!==selectedRecommendation.contentHash)return"人工确认与档位建议精确修订不一致";if(selectedConfirmation.selectedProfile!==selectedTemplate?.profile)return"人工确认档位与阶段模板不一致";if(!sameExact(selectedConfirmation.policyRef,selectedPlan.mergePolicyRef))return"人工确认与合并策略精确修订不一致";if(requiredCapabilityIds.length===0)return"职责计划未声明原子 Capability";if(selectedCapabilities.some(item=>!item))return`缺少可用 Capability 精确修订：${requiredCapabilityIds.filter((_,index)=>!selectedCapabilities[index]).join("、")}`;return"";})();
  const canCompile = Boolean(selectedTemplate && selectedPlan && selectedCompileProductionContext && taskId.trim() && Number.isInteger(Number(taskVersion)) && Number(taskVersion) > 0 && selectedTemplate.lifecycle === "frozen" && selectedTemplate.readiness === "ready" && selectedPlan.lifecycle === "frozen" && selectedPlan.readiness === "ready" && selectedPlan.coverage === "complete" && selectedTemplate.profile === selectedPlan.profile && selectedCompileProductionContext.lifecycle === "frozen" && selectedCompileProductionContext.readiness === "ready" && selectedCompileProductionContext.blockers.length === 0 && selectedCompileProductionContext.taskId === taskId.trim() && selectedCompileProductionContext.profile === selectedTemplate.profile && sameExact(selectedCompileProductionContext.responsibilityPlanRef,selectedPlanRef) && !governedCompileDisabledReason);
  const compile = () => {
    if (!selectedTemplate || !selectedPlan || !selectedCompileProductionContext || !canCompile) return;
    void run("stage:compile", async () => {
      const result=await aipProductionContracts.compileStageTemplate(selectedTemplate.templateId, {
      taskId: taskId.trim(), expectedTaskVersion: Number(taskVersion), templateRevision: selectedTemplate.revision,
      templateContentHash: selectedTemplate.contentHash, profile: selectedTemplate.profile,
      responsibilityPlanRef: { resourceType: "ResponsibilityPlanRevision", resourceId: selectedPlan.planId, revision: selectedPlan.revision, contentHash: selectedPlan.contentHash },
      productionContextRef:{resourceType:"ProductionContextRevision",resourceId:selectedCompileProductionContext.contextId,revision:selectedCompileProductionContext.revision,contentHash:selectedCompileProductionContext.contentHash},
      ...(governedCompile?{briefRef:selectedCompileProductionContext.briefRef,evidenceBundleRef:selectedCompileProductionContext.evidenceBundleRef,evalContractRef:selectedCompileProductionContext.evalContractRef,profileRecommendationRef:selectedPlan.profileRecommendationRef,profileConfirmationId:selectedPlan.profileConfirmationId,mergePolicyRef:selectedPlan.mergePolicyRef,capabilityRefs}:{}),
      }, `w7-ui-stage-compile-${crypto.randomUUID()}`);
      setLastCompilation(result);
      return result;
    });
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
  const startDisabledReason=(()=>{if(!selectedPreview)return"请选择影响预览的精确修订";if(!selectedPreview.productionContextRef)return"该历史影响预览未固定生产上下文，禁止启动";if(!selectedProductionContext)return"请选择生产上下文的精确修订";if(!sameExact(selectedPreview.productionContextRef,{resourceType:"ProductionContextRevision",resourceId:selectedProductionContext.contextId,revision:selectedProductionContext.revision,contentHash:selectedProductionContext.contentHash}))return"所选生产上下文与影响预览固定的精确修订不一致";if(selectedProductionContext.lifecycle!=="frozen"||selectedProductionContext.readiness!=="ready"||selectedProductionContext.blockers.length)return"生产上下文尚未冻结并就绪";if(selectedProductionContext.taskId!==selectedPreview.taskId)return"生产上下文与影响预览不属于同一任务";if(selectedPreview.lifecycle!=="frozen")return"影响预览尚未冻结";if(selectedPreview.readiness!=="ready")return`影响预览当前为${label[selectedPreview.readiness]??selectedPreview.readiness}`;if(selectedPreview.blockers.length)return"影响预览仍有权威阻断";if(new Date(selectedPreview.expiresAt).getTime()<=Date.now())return"影响预览已过期，请刷新并重新评估";if(!positiveInteger(startTaskVersion))return"任务版本必须大于 0";if(eligibleActionProposals.length===0)return"当前影响预览没有同任务、同精确修订、已批准且未过期的执行提案";if(!selectedActionProposal)return"请选择可启动的执行提案精确修订";if(!logicGraphId.trim()||!positiveInteger(logicRevision)||!/^[0-9a-f]{64}$/.test(logicGraphHash.trim()))return"请选择已发布业务逻辑，并确认其精确修订和内容摘要";if(publishedLogic.length===0)return"当前组织尚无已发布业务逻辑；空白或未发布修订不能启动";return"";})();
  const freezePreview=(item:ImpactPreviewRevision)=>run(`preview:${item.previewId}`,()=>aipProductionContracts.freezeImpactPreview(item.previewId,item.version,`w2-ui-preview-freeze-${crypto.randomUUID()}`));
  const applyPublishedLogic=(graphId:string)=>{
    const hit=publishedLogic.find(item=>item.id===graphId);
    if(!hit){setLogicGraphId("");return;}
    setLogicGraphId(hit.id);
    setLogicRevision(String(hit.revision));
    setLogicGraphHash(hit.graph_hash);
  };
  const startProduction=()=>{if(!selectedPreview||!selectedProductionContext||!selectedActionProposal||startDisabledReason)return;const proposal=selectedActionProposal.proposal;void run("production:start",()=>aipProductionContracts.startProduction({taskId:selectedPreview.taskId,expectedTaskVersion:Number(startTaskVersion),productionContextRef:{resourceType:"ProductionContextRevision",resourceId:selectedProductionContext.contextId,revision:selectedProductionContext.revision,contentHash:selectedProductionContext.contentHash},planRef:selectedPreview.planRef,previewRef:{resourceType:"ImpactPreviewRevision",resourceId:selectedPreview.previewId,revision:selectedPreview.revision,contentHash:selectedPreview.contentHash},actionProposalRef:{proposalId:proposal.id,version:proposal.version,proposalHash:proposal.proposalHash},logicGraphId:logicGraphId.trim(),logicRevision:Number(logicRevision),logicGraphHash:logicGraphHash.trim()},`w2-ui-production-start-${crypto.randomUUID()}`));};

  return <PageChrome title="上线执行审批" lede="统一查看任务目标、证据、评测、职责、阶段、产物关系和评审；审批资料冻结只表示内容不可变，不代表已经启动运行。">
    {error && <div role="alert" className="notice bad">上线执行审批读取或操作失败：{error}</div>}
    {loading ? <div role="status" className="card">正在读取上线执行审批权威记录…</div> : null}
    {!loading && state ? <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(110px,1fr))", gap: 10, marginBottom: 16 }}>
        {[
          ["任务简报", state.briefs.count],
          ["证据包", state.bundles.count],
          ["评测契约", state.evals.count],
          ["职责计划", state.plans.count],
          ["档位建议", state.profileRecommendations.count],
          ["人工确认", state.profileConfirmations.count],
          ["阶段模板", state.stages.count],
          ["产物关系", state.relations.count],
          ["评审", state.reviews.count],
          ["影响预览", state.previews.count],
          ["执行提案", state.actionProposals.count],
          ["启动决策", state.starts.count],
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
        <span className="notice" style={{ padding: "6px 10px" }}>权威记录只读汇总 · 信息不足时禁止启动</span>
      </div>
      <section className="card" style={{ padding:18,marginBottom:16 }} aria-label="媒体生产档位建议与成本预检">
        <h2 style={{marginTop:0}}>媒体生产档位建议与成本预检</h2>
        <p>原子 Skill 成本快照经 Logic 与策略形成 LITE、STANDARD、FULL 建议，再由用户确认数字同事职责档位；确认只固定建议和预计区间，不启动模型、智能体或外部动作。</p>
        {state.profileRecommendations.count===0?<div className="notice">当前组织尚无媒体生产档位建议。建议必须绑定任务简报、证据包、评测契约、职责模板、阶段模板和价格快照的精确修订；本页不生成样例成本。</div>:state.profileRecommendations.items.map(item=>{
          const confirmation=state.profileConfirmations.items.find(candidate=>candidate.recommendationId===item.recommendationId&&candidate.recommendationRevision===item.revision&&candidate.recommendationHash===item.contentHash);
          const expired=new Date(item.expiresAt).getTime()<=Date.now();
          const canConfirm=item.readiness==="ready"&&!item.blockers.length&&!expired&&!confirmation;
          return <article key={`${item.recommendationId}@${item.revision}`} style={itemStyle} data-testid={`profile-recommendation-${item.recommendationId}`}>
            <div style={{display:"flex",justifyContent:"space-between",gap:12,flexWrap:"wrap"}}><strong>建议 {profileLabels[item.recommendedProfile]}</strong><span>{confirmation?"已人工确认":expired?"已过期":label[item.readiness]??item.readiness}</span></div>
            <p>{item.reasonCodes.join("、")||"由当前策略和任务范围计算"} · 有效期至 {new Date(item.expiresAt).toLocaleString()}</p>
            <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(200px,1fr))",gap:8}}>{item.projectedCostRanges.map(cost=><div key={`${cost.profile}:${cost.currency}`} style={{padding:"8px 10px",border:"1px solid var(--aos-border)",borderRadius:6}}><strong>{profileLabels[cost.profile]} · {cost.currency}</strong><div>{projectedCostText(cost)}</div><small>{cost.componentCount} 个计价组件 · {cost.priceSnapshotRefs.length} 个价格快照</small></div>)}</div>
            <p>预计时长：{item.projectedDuration?(item.projectedDuration.unknownCodes.length?`未知（不以 0 代替） · ${item.projectedDuration.unknownCodes.join("、")}`:`${item.projectedDuration.lowerSeconds}–${item.projectedDuration.upperSeconds} 秒`):"未提供"}</p>
            {item.assumptions.length?<p>关键假设：{item.assumptions.join("；")}</p>:null}
            {item.blockers.length?<div className="notice bad">阻断：{item.blockers.join("、")}</div>:null}
            <details><summary>精确依赖（审计用）</summary><code>{item.recommendationId}@{item.revision}</code> · {item.dependencyRefs.length} 个精确依赖 · 内容摘要 <code>{item.contentHash.slice(0,12)}…</code></details>
            {confirmation?<div className="notice" data-testid={`profile-confirmation-${item.recommendationId}`}>用户已确认 {profileLabels[confirmation.selectedProfile]}；预计成本区间已随确认回执冻结，实际成本仍以用量账本为准。</div>:<button className="btn primary" disabled={!canConfirm||busy===`profile:${item.recommendationId}`} title={canConfirm?"确认当前建议和预计区间；不会启动生产":"建议被阻断、已过期或已有确认，禁止提交"} onClick={()=>void confirmProfile(item)} style={{marginTop:10}}>{busy===`profile:${item.recommendationId}`?"确认中…":"确认建议档位与预计区间"}</button>}
          </article>;
        })}
      </section>
      <section style={grid}>
        <div className="card" style={{ padding: 18 }}><h2 style={{ marginTop: 0 }}>{contractSectionDisplayName("Task Brief")}</h2>
          {state.briefs.count === 0 ? <div className="notice">当前组织尚无任务简报。请从真实任务进入创建流程；本页不生成演示任务。</div> : state.briefs.items.map(item => <article key={item.briefId} style={itemStyle}><div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><strong>{businessDisplayName(item.briefType)}</strong><span>{label[item.lifecycle] ?? statusDisplayName(item.lifecycle)}</span></div><p>关联真实任务 · 修订 {item.revision}</p><details><summary>技术标识（审计用）</summary><code>{item.briefId}@{item.revision}</code> · 任务 <code>{item.taskId}</code><br/><small>版本 {item.version} · 内容摘要 {item.contentHash.slice(0, 12)}…</small></details>{item.lifecycle === "draft" ? <button className="btn" disabled={busy === `brief:${item.briefId}`} onClick={() => void freezeBrief(item.briefId, item.version)} style={{ marginTop: 10 }}>{busy === `brief:${item.briefId}` ? "冻结中…" : "冻结当前修订"}</button> : null}</article>)}
        </div>
        <div className="card" style={{ padding: 18 }}><h2 style={{ marginTop: 0 }}>{contractSectionDisplayName("Evidence Bundle")}</h2>
          {state.bundles.count === 0 ? <div className="notice">当前组织尚无证据包。证据包只能引用已授权事实，不能复制受限正文或用摘要冒充事实。</div> : state.bundles.items.map(item => <article key={`${item.bundleId}@${item.revision}`} style={itemStyle}><div style={{ display: "flex", justifyContent: "space-between" }}><strong>{item.itemRefs.length} 条授权证据</strong><span>{statusDisplayName(item.freshness)}</span></div><p>覆盖情况：{label[item.coverage] ?? statusDisplayName(item.coverage)}</p><details><summary>技术标识（审计用）</summary><code>{item.bundleId}@{item.revision}</code><br/><small>任务简报 {item.briefRef.resourceId}@{item.briefRef.revision}</small></details><button className="btn" type="button" style={{ marginTop: 10 }} onClick={(event) => { evidenceDrawerTriggerRef.current = event.currentTarget; setEvidenceDrawerBundleId(item.bundleId); }}>查看受控证据披露</button></article>)}
        </div>
        <div className="card" style={{ padding: 18 }}><h2 style={{ marginTop: 0 }}>{contractSectionDisplayName("Eval Contract")}</h2>
          {state.evals.count === 0 ? <div className="notice">当前组织尚无评测契约。必须绑定真实评测套件、发布事件和发布门决策后才能就绪；没有修订时不生成本地差异。</div> : state.evals.items.map(item => { const canFreeze = item.lifecycle === "draft" && item.readiness === "ready" && item.blockers.length === 0; return <article key={item.contractId} style={itemStyle}><div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><strong>评测阈值 {Object.keys(item.severityThresholds).length} 项</strong><span>{label[item.readiness] ?? statusDisplayName(item.readiness)}</span></div><p>{label[item.lifecycle] ?? statusDisplayName(item.lifecycle)}</p><details><summary>技术标识（审计用）</summary><code>{item.contractId}@{item.revision}</code><br/>评测套件 <code>{item.suiteRef.resourceId}@{item.suiteRef.revision}</code><br/><small>版本 {item.version}</small></details><Blockers items={item.blockers} />{item.revision>1?<button className="btn" type="button" disabled={busy===`eval-diff:${item.contractId}`} onClick={()=>void loadEvalDiff(item.contractId,item.revision)} style={{marginTop:10}}>{busy===`eval-diff:${item.contractId}`?"读取差异中…":"查看与上一修订的权威差异"}</button>:<p className="notice">首个修订暂无可比较版本；差异保持空态。</p>}{item.lifecycle === "draft" ? <button className="btn" disabled={!canFreeze || busy === `eval:${item.contractId}`} title={canFreeze ? "冻结当前就绪修订" : "存在阻断或状态未就绪，禁止冻结"} onClick={() => void freezeEval(item.contractId, item.version)} style={{ marginTop: 10,marginLeft:10 }}>{busy === `eval:${item.contractId}` ? "冻结中…" : "冻结评测契约"}</button> : null}</article>; })}
          {evalDiff?<section aria-label="评测契约权威差异" className="notice" style={{marginTop:12}}><strong>{evalDiff.summary}</strong><p>比较修订 {evalDiff.fromRevision} → {evalDiff.toRevision}；差异由服务端生成，本页不重算。</p>{evalDiff.changes.length?<ul>{evalDiff.changes.map(change=><li key={change.field}><strong>{change.label}</strong>：{diffValue(change.before)} → {diffValue(change.after)}<br/><small>{change.impact}</small></li>)}</ul>:<p>服务端确认无语义差异。</p>}</section>:null}
        </div>
        <div className="card" style={{ padding: 18 }}><h2 style={{ marginTop: 0 }}>{contractSectionDisplayName("Responsibility Plan")}</h2>
          {state.plans.count === 0 ? <div className="notice bad">当前组织尚无职责计划。职责模板权威未接入前保持关闭，不用本地清单伪造职责覆盖。</div> : state.plans.items.map(item => { const canFreeze = item.lifecycle === "draft" && item.readiness === "ready" && item.coverage === "complete" && item.blockers.length === 0; const governed=Boolean(item.profileRecommendationRef&&item.profileConfirmationId&&item.mergePolicyRef); return <article key={item.planId} style={itemStyle}><div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><strong>{businessDisplayName(item.profile)}</strong><span>{label[item.readiness] ?? statusDisplayName(item.readiness)}</span></div><p>{item.slots.length} 个职责位置 · 覆盖 {label[item.coverage] ?? statusDisplayName(item.coverage)}</p>{item.uncoveredSlots.length ? <p>未覆盖：{item.uncoveredSlots.map(capabilityDisplayName).join("、")}</p> : null}<div className={`notice${governed?"":" bad"}`} data-testid={`profile-governance-${item.planId}`}><strong>{governed?"职责档位已由建议、确认与合并策略共同固定":"历史职责计划：未固定档位建议与合并策略"}</strong><p>{governed?`已记录 ${item.mergeDecisionReceiptIds?.length??0} 条合并预检回执；本页只读展示，不自动改档或合并。`:"兼容读取不代表可用于新生产组合；修订为 LITE、STANDARD 或 FULL 时必须补齐治理引用。"}</p></div><details><summary>技术标识（审计用）</summary>模板 <code>{item.templateRef.resourceId}@{item.templateRef.revision}</code> · 版本 {item.version}<br/>计划 <code>{item.planId}</code>{governed?<><br/>档位建议 <code>{item.profileRecommendationRef?.resourceId}@{item.profileRecommendationRef?.revision}</code><br/>人工确认 <code>{item.profileConfirmationId}</code><br/>合并策略 <code>{item.mergePolicyRef?.resourceId}@{item.mergePolicyRef?.revision}</code></>:null}</details><Blockers items={item.blockers} />{item.lifecycle === "draft" ? <button className="btn" disabled={!canFreeze || busy === `plan:${item.planId}`} title={canFreeze ? "冻结完整且就绪的职责计划" : "职责覆盖不完整、存在阻断或状态未就绪"} onClick={() => void freezePlan(item.planId, item.version)} style={{ marginTop: 10 }}>{busy === `plan:${item.planId}` ? "冻结中…" : "冻结职责计划"}</button> : null}</article>; })}
        </div>
        <div className="card" style={{ padding: 18 }}><h2 style={{ marginTop: 0 }}>{contractSectionDisplayName("Stage Template")}</h2>
          {state.stages.count === 0 ? <div className="notice">当前组织尚无阶段模板。模板必须来自已验证资产包，本页不生成隐式阶段。</div> : state.stages.items.map(item => { const canFreeze = item.lifecycle === "draft" && item.readiness === "ready" && item.blockers.length === 0; return <article key={item.templateId} style={itemStyle}><div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><strong>{businessDisplayName(item.profile)}</strong><span>{label[item.readiness] ?? statusDisplayName(item.readiness)}</span></div><p>{item.stages.length} 个执行阶段 · {label[item.lifecycle] ?? statusDisplayName(item.lifecycle)}</p><details><summary>技术标识（审计用）</summary><code>{item.templateId}@{item.revision}</code><br/>来源 <code>{item.sourceBundleRef.resourceId}@{item.sourceBundleRef.revision}</code></details><Blockers items={item.blockers} />{item.lifecycle === "draft" ? <button className="btn" disabled={!canFreeze || busy === `stage:${item.templateId}`} title={canFreeze ? "冻结当前就绪模板" : "来源引用缺失、漂移或存在其他阻断"} onClick={() => void freezeStage(item.templateId, item.version)} style={{ marginTop: 10 }}>{busy === `stage:${item.templateId}` ? "冻结中…" : "冻结阶段模板"}</button> : null}</article>; })}
        </div>
        <div className="card" style={{ padding: 18 }}><h2 style={{ marginTop: 0 }}>{contractSectionDisplayName("Artifact Relation")}</h2>
          {state.relations.count === 0 ? <div className="notice">当前组织尚无产物关系。只有两端产物标识和内容摘要都匹配权威记录时才能建立关系。</div> : state.relations.items.map(item => <article key={item.relationId} style={itemStyle}><strong>{item.relationType === "variant_of" ? "同类变体" : businessDisplayName(item.relationType)}</strong><p>{contractBusinessText(item.reason)}</p><details><summary>技术标识（审计用）</summary><code>{item.fromArtifact.artifactId}</code> → <code>{item.toArtifact.artifactId}</code><br/><small>{item.createdBy}</small></details></article>)}
        </div>
        <div className="card" style={{ padding: 18 }}><h2 style={{ marginTop: 0 }}>{contractSectionDisplayName("Review Issue")}</h2>
          {state.reviews.count === 0 ? <div className="notice">当前组织尚无评审问题。问题必须绑定真实产物、评测报告和证据。</div> : state.reviews.items.map(item => <article key={item.issueId} style={itemStyle}><div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><strong>{item.severity === "warning" ? "警告级问题" : `${statusDisplayName(item.severity)}级问题`}</strong><span>{statusDisplayName(item.status)}</span></div><p>{contractBusinessText(item.suggestedFix)}</p><p>需要退回：{capabilityDisplayName(item.returnStage)}</p><details><summary>技术标识（审计用）</summary><code>{item.issueId}</code> · 版本 {item.version}</details></article>)}
        </div>
      </section>
      <section className="card" style={{ padding:18,marginTop:16 }} aria-label="影响预览与启动组合门">
        <h2 style={{marginTop:0}}>影响预览与启动组合门</h2>
        <p>影响预览只呈现权威评估；未知项不会显示为零。只有已冻结且就绪的精确修订才能提交，成功也只代表创建任务运行记录，不代表智能体或模型已经运行。</p>
        {state.previews.count===0?<div className="notice">当前组织尚无影响预览。请从真实任务、执行计划与冻结的上线审批资料创建；本页不生成样例费用或运行状态。</div>:state.previews.items.map(item=>{const canFreeze=item.lifecycle==="draft"&&item.readiness==="ready"&&!item.blockers.length;return <article key={`${item.previewId}@${item.revision}`} style={itemStyle}>
          <div style={{display:"flex",justifyContent:"space-between",gap:12,flexWrap:"wrap"}}><strong>任务影响评估</strong><span>{label[item.lifecycle]??item.lifecycle} · {label[item.readiness]??item.readiness}</span></div>
          <p>有效期至 {new Date(item.expiresAt).toLocaleString()}</p><details><summary>技术标识（审计用）</summary>影响预览 <code>{item.previewId}@{item.revision}</code> · 任务 <code>{item.taskId}</code></details>
          <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(170px,1fr))",gap:8}}>{Object.entries(item.impact).map(([name,dimension])=><Quality key={name} name={name} item={dimension}/>)}</div>
          <Blockers items={item.blockers}/>
          <details style={{marginTop:10}}><summary>精确引用（审计用）</summary><ul><li>执行计划 <code>{item.planRef.resourceId}@{item.planRef.revision}</code></li><li>{item.productionContextRef?<>生产上下文 <code>{item.productionContextRef.resourceId}@{item.productionContextRef.revision}</code></>:<>历史记录未固定生产上下文；禁止启动</>}</li><li>任务简报 <code>{item.briefRef.resourceId}@{item.briefRef.revision}</code></li><li>证据包 <code>{item.evidenceBundleRef.resourceId}@{item.evidenceBundleRef.revision}</code></li><li>评测契约 <code>{item.evalContractRef.resourceId}@{item.evalContractRef.revision}</code></li><li>职责计划 <code>{item.responsibilityPlanRef.resourceId}@{item.responsibilityPlanRef.revision}</code></li><li>阶段模板 <code>{item.stageTemplateRef.resourceId}@{item.stageTemplateRef.revision}</code></li><li>依赖快照 <code>{item.dependencySnapshotHash.slice(0,16)}…</code></li><li>动作绑定摘要 <code>{item.actionBindingHash.slice(0,16)}…</code>（服务端只读）</li></ul></details>
          {item.lifecycle==="draft"?<button className="btn" disabled={!canFreeze||busy===`preview:${item.previewId}`} title={canFreeze?"冻结当前就绪的影响预览精确修订":"影响预览未就绪或仍有阻断，禁止冻结"} onClick={()=>void freezePreview(item)} style={{marginTop:10}}>{busy===`preview:${item.previewId}`?"冻结中…":"冻结影响预览"}</button>:null}
        </article>})}
        <h3>受控创建任务运行记录</h3>
        <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(220px,1fr))",gap:12}}>
          <label>影响预览<select aria-label="影响预览修订" value={previewId} onChange={event=>{setPreviewId(event.target.value);setActionProposalId("");}}><option value="">选择精确修订</option>{state.previews.items.map(item=><option key={`${item.previewId}@${item.revision}`} value={item.previewId}>影响评估 · 修订 {item.revision} · {label[item.lifecycle]??item.lifecycle}/{label[item.readiness]??item.readiness}</option>)}</select></label>
          <label>生产上下文<select aria-label="生产上下文修订" value={productionContextId} onChange={event=>setProductionContextId(event.target.value)}><option value="">选择已冻结且就绪的精确修订</option>{state.contexts.items.map(item=><option key={`${item.contextId}@${item.revision}`} value={item.contextId}>生产上下文 · 修订 {item.revision} · {label[item.lifecycle]??item.lifecycle}/{label[item.readiness]??item.readiness}</option>)}</select></label>
          <label>任务版本<input aria-label="启动 Task version" type="number" min="1" value={startTaskVersion} onChange={event=>setStartTaskVersion(event.target.value)}/></label>
          <label>执行提案<select aria-label="执行提案修订" value={actionProposalId} onChange={event=>setActionProposalId(event.target.value)} data-testid="start-action-proposal-select"><option value="">选择同一影响预览下已批准的精确修订</option>{eligibleActionProposals.map(({proposal})=><option key={proposal.id} value={proposal.id}>{actionDisplayName(proposal.actionType.actionTypeId)} · 版本 {proposal.version}</option>)}</select></label>
          <label>业务逻辑标识<input aria-label="业务逻辑标识" value={logicGraphId} onChange={event=>setLogicGraphId(event.target.value)} placeholder="由已发布列表自动带入" data-testid="start-logic-graph-id"/></label>
          <label>业务逻辑修订<input aria-label="Logic revision" type="number" min="1" value={logicRevision} onChange={event=>setLogicRevision(event.target.value)} data-testid="start-logic-revision"/></label>
          <label>内容摘要<input aria-label="业务逻辑内容摘要" value={logicGraphHash} onChange={event=>setLogicGraphHash(event.target.value.trim())} placeholder="由已发布列表自动带入" data-testid="start-logic-hash"/></label>
          <label>已发布业务逻辑<select aria-label="已发布 Logic" value={logicGraphId} onChange={event=>applyPublishedLogic(event.target.value)} data-testid="start-logic-published-select"><option value="">从已发布列表选用</option>{publishedLogic.map(item=><option key={item.id} value={item.id}>{businessDisplayName(item.name)} · 修订 {item.revision}</option>)}</select></label>
        </div>
        {selectedPreview&&eligibleActionProposals.length===0?<div className="notice" role="status" style={{marginTop:12}} data-testid="start-action-proposal-empty">当前影响预览没有同任务、同精确修订、已批准且未过期的执行提案；请回到草稿审批台处理真实提案，本页不生成或批准样例。</div>:null}
        {selectedActionProposal?<div className="notice" style={{marginTop:12}} data-testid="start-action-proposal-exact">已锁定执行提案（版本 {selectedActionProposal.proposal.version}）<details><summary>技术标识（审计用）</summary><code>{selectedActionProposal.proposal.id}</code> · 摘要 <code>{selectedActionProposal.proposal.proposalHash.slice(0,12)}…</code></details></div>:null}
        {publishedLogic.length===0?<div className="notice" role="status" style={{marginTop:12}} data-testid="start-logic-empty">尚无已发布业务逻辑；空白或未发布修订不能进入生产启动。</div>:null}
        {startDisabledReason?<div className="notice" role="status" style={{marginTop:12}}>启动门保持关闭：{startDisabledReason}。可先刷新权威状态；若依赖漂移，请回到对应权威记录修订后创建新的影响预览。</div>:<div className="notice" style={{marginTop:12}}>组合门输入完整；服务端仍会重新核验影响预览、提案、审批、租约、路由、绑定与容量。</div>}
        <button className="btn primary" disabled={Boolean(startDisabledReason)||busy==="production:start"} title={startDisabledReason||"只创建任务运行记录；不启动智能体或模型供应商"} onClick={startProduction} style={{marginTop:12}}>{busy==="production:start"?"组合门核验中…":"通过组合门并创建任务运行记录"}</button>
        <h3>启动决策审计记录</h3>
        {state.starts.count===0?<div className="notice">当前组织尚无启动决策；这表示没有提交过组合门，不等于运行成功。</div>:state.starts.items.map(item=><article key={item.decisionId} style={itemStyle}><div style={{display:"flex",justifyContent:"space-between",gap:12}}><strong>启动决策</strong><span>{item.status==="started"?"已创建任务运行记录（尚未启动智能体）":label[item.status]??statusDisplayName(item.status)}</span></div><details><summary>技术标识（审计用）</summary>决策 <code>{item.decisionId}</code><br/>任务 <code>{item.taskId}</code> · 影响预览 <code>{item.previewRef.resourceId}@{item.previewRef.revision}</code><br/>{item.productionContextRef?<>生产上下文 <code>{item.productionContextRef.resourceId}@{item.productionContextRef.revision}</code></>:<>历史决策未记录生产上下文精确引用</>}{item.taskRunRef?<><br/>任务运行 <code>{item.taskRunRef.resourceId}</code></>:null}</details><Blockers items={item.blockers}/></article>)}
      </section>
      <section className="card" style={{ padding: 18, marginTop: 16 }} aria-label="阶段模板编译命令">
        <h2 style={{ marginTop: 0 }}>从阶段模板编译执行计划草稿</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 12 }}>
          <label>阶段模板<select aria-label="阶段模板修订" value={templateId} onChange={event => setTemplateId(event.target.value)}><option value="">选择已冻结模板</option>{state.stages.items.map(item => <option key={item.templateId} value={item.templateId}>{businessDisplayName(item.profile)} · 修订 {item.revision}</option>)}</select></label>
          <label>职责计划<select aria-label="职责计划修订" value={planId} onChange={event => setPlanId(event.target.value)}><option value="">选择已冻结职责计划</option>{state.plans.items.map(item => <option key={item.planId} value={item.planId}>{businessDisplayName(item.profile)} · 修订 {item.revision}</option>)}</select></label>
          <label>生产上下文<select aria-label="编译生产上下文修订" value={compileProductionContextId} onChange={event=>setCompileProductionContextId(event.target.value)}><option value="">选择与任务、职责计划一致的精确修订</option>{state.contexts.items.map(item=><option key={`${item.contextId}@${item.revision}`} value={item.contextId}>生产上下文 · 修订 {item.revision} · {label[item.lifecycle]??item.lifecycle}/{label[item.readiness]??item.readiness}</option>)}</select></label>
          <label>真实任务标识<input aria-label="编译真实 Task ID" value={taskId} onChange={event => setTaskId(event.target.value)} placeholder="输入真实任务标识" /></label>
          <label>任务版本<input aria-label="编译 Task version" type="number" min="1" value={taskVersion} onChange={event => setTaskVersion(event.target.value)} /></label>
        </div>
        {governedCompile?(governedCompileDisabledReason?<div className="notice" role="status" style={{marginTop:12}} data-testid="governed-compile-blocked">受治理编译门保持关闭：{governedCompileDisabledReason}。</div>:<div className="notice" style={{marginTop:12}} data-testid="governed-compile-ready">受治理编译输入已锁定：档位建议、人工确认、合并策略与 {requiredCapabilityIds.length} 项原子 Capability 精确修订；服务端仍会独立复核。</div>):null}
        <button className="btn primary" disabled={!canCompile || busy === "stage:compile"} title={canCompile ? "只创建执行计划草稿，不启动任务" : governedCompileDisabledReason||"需选择同一任务、业务场景与职责计划下已冻结且就绪的生产上下文、阶段模板和职责计划"} onClick={compile} style={{ marginTop: 12 }}>{busy === "stage:compile" ? "编译中…" : "编译为执行计划草稿"}</button>
        {lastCompilation?<div className="notice" role="status" style={{marginTop:12}} data-testid="stage-compilation-result"><strong>执行计划草稿已编译，未创建任务运行。</strong><br/>规范化阶段 {lastCompilation.normalizedStageIds.length} 项 · 适用 {lastCompilation.applicableStageIds.length} 项 · 跳过 {lastCompilation.notApplicableStageIds.length} 项<details><summary>技术摘要（审计用）</summary>输入 <code>{lastCompilation.inputHash}</code><br/>编译 <code>{lastCompilation.compilationHash}</code><br/>Plan <code>{lastCompilation.planRef.resourceId}@{lastCompilation.planRef.revision}</code></details></div>:null}
      </section>
      <section className="card" style={{ padding: 18, marginTop: 16 }} aria-label="评审问题处置命令">
        <h2 style={{ marginTop: 0 }}>评审问题处置</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 12 }}>
          <label>待处置问题<select aria-label="待处置 Open Issue" value={reviewIssueId} onChange={event => setReviewIssueId(event.target.value)}><option value="">选择待处置问题</option>{state.reviews.items.filter(item => item.status === "open").map(item => <option key={item.issueId} value={item.issueId}>{item.severity}级问题</option>)}</select></label>
          <label>真实运行标识<input aria-label="Review 真实运行 ID" value={reviewRunId} onChange={event => setReviewRunId(event.target.value)} placeholder="仅退回时必填" /></label>
          <label>处置原因<input aria-label="Review 处置原因" value={reviewReason} onChange={event => setReviewReason(event.target.value)} placeholder="必填，并写入审计事件" /></label>
        </div>
        <div style={{ display: "flex", gap: 10, marginTop: 12 }}><button className="btn" disabled={!canReviewCommand || Boolean(busy)} title={busy ? "正在提交处置，请稍候" : canReviewCommand ? "将当前问题标记为已解决并写入审计事件" : "请选择待处置问题并填写处置原因"} onClick={resolveReview}>标记已解决</button><button className="btn primary" disabled={!canReviewCommand || !reviewRunId.trim() || Boolean(busy)} title="只向真实运行任务的目标阶段追加排队中的尝试" onClick={returnReview}>退回目标阶段</button></div>
      </section>
      <div className="notice" style={{ marginTop: 16 }}>影响预览与启动组合门已接入权威数据源；即使启动决策通过，也只创建任务运行记录。智能体运行、模型路由、供应商、绑定与容量仍由独立服务端门禁控制。</div>
      {evidenceDrawerBundle ? <EvidenceBundleDrawer
        title="受控证据披露"
        state={evidenceDrawerBundle.revoked ? "blocked" : evidenceDrawerBundle.freshness === "fresh" ? "ready" : evidenceDrawerBundle.freshness}
        lineage={{ atomicSkillRef: null, logicRef: null, coworker: null, workshopContribution: "按服务端决策逐层展示证据，不推断未返回的贡献归因" }}
        blockers={evidenceDrawerBundle.revoked ? [{ code: "EVIDENCE_BUNDLE_REVOKED", message: evidenceDrawerBundle.revokeReason || "证据包已撤销", owner: "数据与证据负责人", requiredAction: "创建引用当前有效证据的新修订", cutoffAt: null }] : []}
        bundleRef={{ resourceType: "EvidenceBundleRevision", resourceId: evidenceDrawerBundle.bundleId, revision: evidenceDrawerBundle.revision, contentHash: evidenceDrawerBundle.contentHash }}
        evidenceRefs={evidenceDrawerBundle.itemRefs}
        open
        onClose={() => setEvidenceDrawerBundleId("")}
        returnFocusRef={evidenceDrawerTriggerRef}
      /> : null}
    </> : null}
  </PageChrome>;
}
