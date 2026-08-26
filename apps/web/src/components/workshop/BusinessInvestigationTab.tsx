import { useEffect, useMemo, useRef, useState } from "react";

import {
  EcommerceInvestigationClientError,
  ecommerceInvestigationClient,
  type InvestigationCaseRevision,
  type InvestigationReadClient,
  type InvestigationRunView,
  type InvestigationTenant,
  type InvestigationWorkbenchView,
} from "../../api/ecommerceInvestigation";
import { BUSINESS_INVESTIGATION_READ_FLAG } from "./businessInvestigationFeatureFlags";

type Phase = "loading" | "ready" | "empty" | "forbidden" | "failed";
type RunPhase = "idle" | "loading" | "ready" | "empty" | "forbidden" | "failed";
type ViewPhase = "idle" | "loading" | "ready" | "forbidden" | "failed";
type EntityChoice = { key: string; channelId: string; entityId: string };

const ANALYSIS_LABELS: Record<InvestigationCaseRevision["analysisType"], string> = {
  initial_store_analysis: "首次全店经营分析",
  weekly_business_review: "每周经营复盘",
  experience_growth: "体验增长",
  creator_sales: "达人销售",
  product_structure: "商品结构",
};
const entityKey = (channelId: string, entityId: string) => `${encodeURIComponent(channelId)}/${encodeURIComponent(entityId)}`;

function entityChoices(cases: InvestigationCaseRevision[], channelId: string): EntityChoice[] {
  const seen = new Set<string>(); const result: EntityChoice[] = [];
  for (const item of cases) {
    const itemChannel = item.channelRef.resourceId; if (channelId && itemChannel !== channelId) continue;
    const key = entityKey(itemChannel, item.businessEntityRef.resourceId); if (seen.has(key)) continue;
    seen.add(key); result.push({ key, channelId: itemChannel, entityId: item.businessEntityRef.resourceId });
  }
  return result;
}
function casesForEntity(cases: InvestigationCaseRevision[], selectedEntityKey: string): InvestigationCaseRevision[] {
  return cases.filter((item) => entityKey(item.channelRef.resourceId, item.businessEntityRef.resourceId) === selectedEntityKey);
}

export function BusinessInvestigationTab({ id, labelledBy, client = ecommerceInvestigationClient }: { id: string; labelledBy: string; client?: InvestigationReadClient }) {
  const [phase, setPhase] = useState<Phase>("loading"); const [tenant, setTenant] = useState<InvestigationTenant | null>(null); const [cases, setCases] = useState<InvestigationCaseRevision[]>([]);
  const [selectedChannelId, setSelectedChannelId] = useState(""); const [selectedEntityKey, setSelectedEntityKey] = useState(""); const [selectedCaseId, setSelectedCaseId] = useState("");
  const [runPhase, setRunPhase] = useState<RunPhase>("idle"); const [runs, setRuns] = useState<InvestigationRunView[]>([]); const [selectedRunId, setSelectedRunId] = useState("");
  const [viewPhase, setViewPhase] = useState<ViewPhase>("idle"); const [workbenchView, setWorkbenchView] = useState<InvestigationWorkbenchView | null>(null);
  const caseRequest = useRef(0); const runRequest = useRef(0); const viewRequest = useRef(0);
  const channels = useMemo(() => Array.from(new Set(cases.map((item) => item.channelRef.resourceId))), [cases]);
  const entities = useMemo(() => entityChoices(cases, selectedChannelId), [cases, selectedChannelId]);
  const visibleCases = useMemo(() => casesForEntity(cases, selectedEntityKey), [cases, selectedEntityKey]);
  const selectedCase = visibleCases.find((item) => item.caseId === selectedCaseId) ?? null;

  const clearView = () => { viewRequest.current += 1; setWorkbenchView(null); setViewPhase("idle"); };
  const clearRuns = () => { runRequest.current += 1; setRuns([]); setSelectedRunId(""); setRunPhase("idle"); clearView(); };
  const selectFromCases = (nextCases: InvestigationCaseRevision[]) => {
    const channelId = nextCases[0]?.channelRef.resourceId ?? ""; const nextEntities = entityChoices(nextCases, channelId); const nextEntityKey = nextEntities[0]?.key ?? ""; const nextCasesForEntity = casesForEntity(nextCases, nextEntityKey);
    setSelectedChannelId(channelId); setSelectedEntityKey(nextEntityKey); setSelectedCaseId(nextCasesForEntity[0]?.caseId ?? ""); clearRuns();
  };
  const loadCases = () => {
    const requestId = ++caseRequest.current; setPhase("loading"); setTenant(null); setCases([]); setSelectedChannelId(""); setSelectedEntityKey(""); setSelectedCaseId(""); clearRuns();
    void client.listCases().then((response) => { if (requestId !== caseRequest.current) return; setTenant(response.tenant); setCases(response.items); selectFromCases(response.items); setPhase(response.items.length ? "ready" : "empty"); }, (error: unknown) => { if (requestId !== caseRequest.current || (error instanceof DOMException && error.name === "AbortError")) return; setPhase(error instanceof EcommerceInvestigationClientError && (error.status === 401 || error.status === 403) ? "forbidden" : "failed"); });
  };

  useEffect(() => { loadCases(); return () => { caseRequest.current += 1; runRequest.current += 1; viewRequest.current += 1; }; }, [client]);
  useEffect(() => {
    if (!selectedCaseId) { setRuns([]); setSelectedRunId(""); setRunPhase("idle"); return; }
    const requestId = ++runRequest.current; const controller = new AbortController(); setRuns([]); setSelectedRunId(""); setRunPhase("loading");
    void client.listRuns(selectedCaseId, controller.signal).then((response) => { if (requestId !== runRequest.current) return; if (tenant && (tenant.orgId !== response.tenant.orgId || tenant.projectId !== response.tenant.projectId)) { setRunPhase("failed"); return; } setRuns(response.items); setSelectedRunId(response.items[0]?.authority.runId ?? ""); setRunPhase(response.items.length ? "ready" : "empty"); }, (error: unknown) => { if (requestId !== runRequest.current || (error instanceof DOMException && error.name === "AbortError")) return; setRunPhase(error instanceof EcommerceInvestigationClientError && (error.status === 401 || error.status === 403) ? "forbidden" : "failed"); });
    return () => controller.abort();
  }, [client, selectedCaseId, tenant]);
  useEffect(() => {
    if (!selectedRunId) { clearView(); return; }
    if (!client.getRunView) { setWorkbenchView(null); setViewPhase("failed"); return; }
    const requestId = ++viewRequest.current; const controller = new AbortController(); setWorkbenchView(null); setViewPhase("loading");
    void client.getRunView(selectedRunId, controller.signal).then((response) => { if (requestId !== viewRequest.current) return; if (tenant && (tenant.orgId !== response.tenant.orgId || tenant.projectId !== response.tenant.projectId)) { setViewPhase("failed"); return; } setWorkbenchView(response); setViewPhase("ready"); }, (error: unknown) => { if (requestId !== viewRequest.current || (error instanceof DOMException && error.name === "AbortError")) return; setViewPhase(error instanceof EcommerceInvestigationClientError && (error.status === 401 || error.status === 403) ? "forbidden" : "failed"); });
    return () => controller.abort();
  }, [client, selectedRunId, tenant]);

  const onChannelChange = (channelId: string) => { const nextEntities = entityChoices(cases, channelId); const nextEntityKey = nextEntities[0]?.key ?? ""; const nextCases = casesForEntity(cases, nextEntityKey); setSelectedChannelId(channelId); setSelectedEntityKey(nextEntityKey); setSelectedCaseId(nextCases[0]?.caseId ?? ""); clearRuns(); };
  const onEntityChange = (key: string) => { const nextCases = casesForEntity(cases, key); setSelectedEntityKey(key); setSelectedCaseId(nextCases[0]?.caseId ?? ""); clearRuns(); };
  const onCaseChange = (caseId: string) => { setSelectedCaseId(caseId); clearRuns(); };

  return (
    <section id={id} aria-labelledby={labelledBy} className="analyst-panel business-investigation-tab" role="tabpanel">
      <header><div><span>Business Investigation · BI-W7-03</span><h2>生意探究</h2></div><strong className="content-campaign-status is-blocked">只读</strong></header>
      <div className="business-investigation-boundary"><article><span>能力开关</span><strong>{BUSINESS_INVESTIGATION_READ_FLAG}</strong><p>仅消费 Principal 可见的 canonical Case/Run；不提交租户和源系统参数。</p></article><article><span>选择一致性</span><strong>原子切换</strong><p>切换渠道、实体或 Case 时立即清空下游，晚到响应不可覆盖当前选择。</p></article><article><span>写入口</span><strong>0</strong><p>命令、周期计划、评审与 Handoff 继续关闭。</p></article></div>

      {phase === "loading" ? <div className="business-investigation-state" role="status"><strong>正在读取分析记录…</strong><p>等待 tenant-scoped canonical Case 列表。</p></div> : null}
      {phase === "empty" ? <div className="business-investigation-state is-empty"><strong>当前没有可见分析记录</strong><p>未知或未创建不能显示为 0，也不以演示 Case 补齐。</p></div> : null}
      {phase === "forbidden" ? <div className="business-investigation-state is-forbidden" role="alert"><strong>无权读取生意探究</strong><p>未泄露其他租户的渠道、实体或分析记录。</p></div> : null}
      {phase === "failed" ? <div className="business-investigation-state is-failed" role="alert"><strong>分析记录读取失败</strong><p>页面已失败关闭，未保留旧选择。</p><button type="button" onClick={loadCases}>重新读取</button></div> : null}

      {phase === "ready" ? <div className="business-investigation-selector" aria-label="生意探究三级选择">
        <label><span>1 · 渠道视角</span><select aria-label="渠道视角" value={selectedChannelId} onChange={(event) => onChannelChange(event.currentTarget.value)}>{channels.map((channelId) => <option key={channelId} value={channelId}>{channelId}</option>)}</select><small>来自 Case 的 exact ChannelRevision，不推测渠道名称。</small></label>
        <fieldset><legend>2 · 经营实体</legend><div className="business-investigation-entities">{entities.map((entity) => <button type="button" role="radio" aria-checked={selectedEntityKey === entity.key} className={selectedEntityKey === entity.key ? "is-selected" : ""} key={entity.key} onClick={() => onEntityChange(entity.key)}><strong>{entity.entityId}</strong><span>{entity.channelId}</span></button>)}</div><small>同名实体按渠道隔离；上游切换后旧实体内容立即清空。</small></fieldset>
        <label><span>3 · 分析记录</span><select aria-label="分析记录" value={selectedCaseId} onChange={(event) => onCaseChange(event.currentTarget.value)}>{visibleCases.map((item) => <option key={item.caseId} value={item.caseId}>{item.title} · {ANALYSIS_LABELS[item.analysisType]}</option>)}</select><small>Case revision、生命周期和运行记录均来自 canonical authority。</small></label>
      </div> : null}

      {phase === "ready" && selectedCase ? <section className="business-investigation-current" aria-label="当前分析记录">
        <header><div><span>{selectedCase.analysisType}</span><h3>{selectedCase.title}</h3></div><strong className={`is-${selectedCase.lifecycle.toLowerCase()}`}>{selectedCase.lifecycle}</strong></header>
        <dl><div><dt>Case</dt><dd>{selectedCase.caseId} · r{selectedCase.revision}</dd></div><div><dt>渠道</dt><dd>{selectedCase.channelRef.resourceId}</dd></div><div><dt>经营实体</dt><dd>{selectedCase.businessEntityRef.resourceId}</dd></div><div><dt>创建时间</dt><dd>{new Date(selectedCase.createdAt).toLocaleString("zh-CN", { hour12: false })}</dd></div></dl>
        {runPhase === "loading" ? <p role="status">正在读取当前 Case 的 Run…</p> : null}
        {runPhase === "empty" ? <p className="is-empty">当前 Case 尚无 Run；不生成演示记录。</p> : null}
        {runPhase === "forbidden" ? <p className="is-forbidden" role="alert">Run 不可见；Case 保持只读且不泄露其他租户状态。</p> : null}
        {runPhase === "failed" ? <p className="is-failed" role="alert">Run 读取失败；旧 Run 已清空。</p> : null}
        {runPhase === "ready" ? <label><span>Run 记录</span><select aria-label="Run 记录" value={selectedRunId} onChange={(event) => { clearView(); setSelectedRunId(event.currentTarget.value); }}>{runs.map((item) => <option key={item.authority.runId} value={item.authority.runId}>{item.authority.runId} · {item.state.lifecycle}/{item.state.control}</option>)}</select></label> : null}
      </section> : null}
      {phase === "ready" && selectedCase && selectedRunId ? <section className="business-investigation-workbench" aria-label="生意探究运行进度">
        {viewPhase === "loading" ? <div className="business-investigation-state" role="status"><strong>正在读取 Case 信封与运行进度…</strong><p>进度由服务端 canonical projection 计算。</p></div> : null}
        {viewPhase === "forbidden" ? <div className="business-investigation-state is-forbidden" role="alert"><strong>运行进度不可见</strong><p>未保留上一 Run 的 StageRail。</p></div> : null}
        {viewPhase === "failed" ? <div className="business-investigation-state is-failed" role="alert"><strong>运行进度读取失败</strong><p>页面失败关闭，不本地推演 x/y。</p></div> : null}
        {viewPhase === "ready" && workbenchView ? <>
          <article className="business-investigation-envelope"><header><div><span>Case 信封 · cutoff {new Date(workbenchView.observedAt).toLocaleString("zh-CN", { hour12: false })}</span><h3>{workbenchView.caseEnvelope.title}</h3></div><strong>{workbenchView.lifecycle}/{workbenchView.control}</strong></header><dl><div><dt>Case exact</dt><dd>{workbenchView.caseRef.resourceId} · r{workbenchView.caseRef.revision}</dd></div><div><dt>Run exact</dt><dd>{workbenchView.runRef.resourceId} · v{workbenchView.runRef.revision}</dd></div><div><dt>Scope</dt><dd>{workbenchView.caseEnvelope.scopeRef.resourceId} · r{workbenchView.caseEnvelope.scopeRef.revision}</dd></div><div><dt>Profile</dt><dd>{workbenchView.caseEnvelope.investigationProfileRef.resourceId} · r{workbenchView.caseEnvelope.investigationProfileRef.revision}</dd></div><div><dt>Schedule</dt><dd>{workbenchView.caseEnvelope.schedulePolicyRef ? `${workbenchView.caseEnvelope.schedulePolicyRef.resourceId} · r${workbenchView.caseEnvelope.schedulePolicyRef.revision}` : "未绑定"}</dd></div><div><dt>Checkpoint</dt><dd>{workbenchView.runtime.checkpoint ? `${workbenchView.runtime.checkpoint.checkpointId} · #${workbenchView.runtime.checkpoint.sequence}` : "尚无 Checkpoint"}</dd></div></dl></article>
          <article className="business-investigation-progress"><header><div><span>服务端进度</span><h3>{workbenchView.runtime.completed}/{workbenchView.runtime.total} 波完成</h3></div><strong className={`is-${workbenchView.runtime.bindingStatus}`}>{workbenchView.runtime.bindingStatus === "unbound" ? "尚未绑定" : workbenchView.runtime.bindingStatus === "task_pending" ? "等待 TaskRun" : workbenchView.runtime.taskRunStatus}</strong></header><ol>{workbenchView.runtime.stages.map((stage, index) => <li key={stage.stageId} className={`is-${stage.status}`} aria-current={workbenchView.runtime.currentStageId === stage.stageId ? "step" : undefined}><span>{index + 1}</span><div><strong>{stage.title}</strong><small>{stage.stageId} · {stage.status}{stage.attempt ? ` · attempt ${stage.attempt}` : ""}</small></div></li>)}</ol><p>Stage 完成仅表示 canonical StepRun 通过阶段门，不代表真实业务方案已执行。</p></article>
        </> : null}
      </section> : null}
      {tenant ? <footer className="business-investigation-tenant">租户 {tenant.orgId}/{tenant.projectId} · canonical GET-only · 未读取真实源系统</footer> : null}
    </section>
  );
}
