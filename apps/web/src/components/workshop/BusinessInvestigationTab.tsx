import { useEffect, useMemo, useRef, useState } from "react";

import {
  EcommerceInvestigationClientError,
  ecommerceInvestigationClient,
  type InvestigationCaseRevision,
  type InvestigationCommandClient,
  type InvestigationControlCommand,
  type InvestigationMissingDataInput,
  type InvestigationReadClient,
  type InvestigationRunView,
  type InvestigationTenant,
  type InvestigationWorkbenchView,
} from "../../api/ecommerceInvestigation";
import type { SourceReadinessExactRef } from "../../api/ecommerceWorkshop";
import { AsyncStateBoundary, type AsyncState } from "./AsyncStateBoundary";
import { BUSINESS_INVESTIGATION_COMMAND_FLAG, BUSINESS_INVESTIGATION_READ_FLAG, isBusinessInvestigationCommandEnabled, resolveBusinessInvestigationFeatureFlags } from "./businessInvestigationFeatureFlags";
import { type SourceReadinessSnapshot, useSourceReadinessSnapshot } from "./SourceReadinessContext";

type Phase = "loading" | "ready" | "empty" | "forbidden" | "failed";
type RunPhase = "idle" | "loading" | "ready" | "empty" | "forbidden" | "failed";
type ViewPhase = "idle" | "loading" | "ready" | "forbidden" | "failed";
type CommandPhase = "idle" | "pending" | "succeeded" | "failed" | "unknown";
type EntityChoice = { key: string; channelId: string; entityId: string };
type InvestigationTabClient = InvestigationReadClient & Partial<Pick<InvestigationCommandClient, "executeRunCommand" | "requestMissingData" | "confirmDataRequirement">>;

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
function canonicalHash(value: string): string { return value.startsWith("sha256:") ? value.slice(7) : value; }
function sameRequirement(left: InvestigationWorkbenchView["pendingRequirementRef"], right: SourceReadinessExactRef | null): boolean {
  return Boolean(left && right && left.resourceType === right.resourceType && left.resourceId === right.resourceId && String(left.revision) === String(right.revision) && canonicalHash(left.contentHash) === canonicalHash(right.contentHash));
}

export function BusinessInvestigationTab({ id, labelledBy, client = ecommerceInvestigationClient, sourceReadinessSnapshot, commandsEnabled = isBusinessInvestigationCommandEnabled(resolveBusinessInvestigationFeatureFlags()), createCommandId = () => globalThis.crypto.randomUUID() }: { id: string; labelledBy: string; client?: InvestigationTabClient; sourceReadinessSnapshot?: SourceReadinessSnapshot; commandsEnabled?: boolean; createCommandId?: () => string }) {
  const [phase, setPhase] = useState<Phase>("loading"); const [tenant, setTenant] = useState<InvestigationTenant | null>(null); const [cases, setCases] = useState<InvestigationCaseRevision[]>([]);
  const [selectedChannelId, setSelectedChannelId] = useState(""); const [selectedEntityKey, setSelectedEntityKey] = useState(""); const [selectedCaseId, setSelectedCaseId] = useState("");
  const [runPhase, setRunPhase] = useState<RunPhase>("idle"); const [runs, setRuns] = useState<InvestigationRunView[]>([]); const [selectedRunId, setSelectedRunId] = useState("");
  const [viewPhase, setViewPhase] = useState<ViewPhase>("idle"); const [workbenchView, setWorkbenchView] = useState<InvestigationWorkbenchView | null>(null);
  const [commandPhase, setCommandPhase] = useState<CommandPhase>("idle"); const [commandMessage, setCommandMessage] = useState("");
  const [missingFacts, setMissingFacts] = useState("Order.daily_amount\nProduct.active_count"); const [dataReason, setDataReason] = useState("人工范围复核完成");
  const [runReloadRevision, setRunReloadRevision] = useState(0); const [viewReloadRevision, setViewReloadRevision] = useState(0);
  const contextReadinessSnapshot = useSourceReadinessSnapshot(); const readinessSnapshot = sourceReadinessSnapshot ?? contextReadinessSnapshot;
  const caseRequest = useRef(0); const runRequest = useRef(0); const viewRequest = useRef(0);
  const channels = useMemo(() => Array.from(new Set(cases.map((item) => item.channelRef.resourceId))), [cases]);
  const entities = useMemo(() => entityChoices(cases, selectedChannelId), [cases, selectedChannelId]);
  const visibleCases = useMemo(() => casesForEntity(cases, selectedEntityKey), [cases, selectedEntityKey]);
  const selectedCase = visibleCases.find((item) => item.caseId === selectedCaseId) ?? null;

  const clearView = () => { viewRequest.current += 1; setWorkbenchView(null); setViewPhase("idle"); setCommandPhase("idle"); setCommandMessage(""); };
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
  }, [client, selectedCaseId, tenant, runReloadRevision]);
  useEffect(() => {
    if (!selectedRunId) { clearView(); return; }
    if (!client.getRunView) { setWorkbenchView(null); setViewPhase("failed"); return; }
    const requestId = ++viewRequest.current; const controller = new AbortController(); setWorkbenchView(null); setViewPhase("loading");
    void client.getRunView(selectedRunId, controller.signal).then((response) => { if (requestId !== viewRequest.current) return; if (tenant && (tenant.orgId !== response.tenant.orgId || tenant.projectId !== response.tenant.projectId)) { setViewPhase("failed"); return; } setWorkbenchView(response); setViewPhase("ready"); }, (error: unknown) => { if (requestId !== viewRequest.current || (error instanceof DOMException && error.name === "AbortError")) return; setViewPhase(error instanceof EcommerceInvestigationClientError && (error.status === 401 || error.status === 403) ? "forbidden" : "failed"); });
    return () => controller.abort();
  }, [client, selectedRunId, tenant, viewReloadRevision]);

  const onChannelChange = (channelId: string) => { const nextEntities = entityChoices(cases, channelId); const nextEntityKey = nextEntities[0]?.key ?? ""; const nextCases = casesForEntity(cases, nextEntityKey); setSelectedChannelId(channelId); setSelectedEntityKey(nextEntityKey); setSelectedCaseId(nextCases[0]?.caseId ?? ""); clearRuns(); };
  const onEntityChange = (key: string) => { const nextCases = casesForEntity(cases, key); setSelectedEntityKey(key); setSelectedCaseId(nextCases[0]?.caseId ?? ""); clearRuns(); };
  const onCaseChange = (caseId: string) => { setSelectedCaseId(caseId); clearRuns(); };
  const canonicalDataState = useMemo<AsyncState>(() => {
    if (!workbenchView || !readinessSnapshot || readinessSnapshot.phase !== "ready" || !readinessSnapshot.response) return "ready";
    const investigation = readinessSnapshot.response.investigation;
    if (workbenchView.pendingRequirementRef && investigation && sameRequirement(workbenchView.pendingRequirementRef, investigation.requirementRef)) {
      if (investigation.status === "stale" || readinessSnapshot.response.status === "stale") return "stale";
      if (investigation.status === "degraded" || investigation.coveredFactCount < investigation.requiredFactCount) return "partial";
    }
    return "ready";
  }, [readinessSnapshot, workbenchView]);
  const executeRunCommand = (command: InvestigationControlCommand) => {
    const projection = workbenchView?.commandProjection;
    if (!commandsEnabled || !projection || !projection.allowedCommands.includes(command) || !client.executeRunCommand || commandPhase === "pending" || commandPhase === "unknown" || commandPhase === "failed") return;
    const commandId = createCommandId();
    setCommandPhase("pending"); setCommandMessage(`${command} 正在提交；不会自动重试。`);
    void client.executeRunCommand({ runId: selectedRunId, command, commandId, expectedStateVersion: projection.expectedStateVersion }).then((result) => {
      setWorkbenchView(result.view); setCommandPhase("succeeded"); setCommandMessage(`${command} 已按 exact state v${result.authority.version} 回读闭合${result.replayed ? "（幂等重放）" : ""}。`);
    }, (error: unknown) => {
      const unknown = error instanceof EcommerceInvestigationClientError && error.code === "COMMAND_OUTCOME_UNKNOWN";
      setCommandPhase(unknown ? "unknown" : "failed");
      setCommandMessage(unknown ? "命令结果未知；已锁定写入口，只允许 GET 重新核验，禁止再次 POST。" : "命令被服务端拒绝或 exact 回读冲突；已锁定写入口，请先重新读取。" );
    });
  };
  const executeDataCommand = (command: "REQUEST_DATA" | "CONFIRM_DATA_REQUIREMENT", decision?: "accept" | "reject") => {
    const projection = workbenchView?.commandProjection;
    if (!commandsEnabled || !projection || !projection.allowedCommands.includes(command) || commandPhase === "pending" || commandPhase === "unknown" || commandPhase === "failed") return;
    const commandId = createCommandId(); setCommandPhase("pending"); setCommandMessage(`${command} 正在提交；不会自动重试。`);
    const now = new Date(); const start = new Date(now.getTime() - 30 * 86_400_000); const expires = new Date(now.getTime() + 86_400_000);
    const facts = missingFacts.split(/\r?\n|,/).map((item) => item.trim()).filter(Boolean);
    const body: InvestigationMissingDataInput = { purposeCode: "business_portrait_gap", requiredFacts: facts, timeWindow: { startAt: start.toISOString(), endAt: now.toISOString() }, grain: "day", cutoffAt: now.toISOString(), freshnessMaxAgeSeconds: 3600, qualityThreshold: 0.95, markings: ["INTERNAL"], minPopulation: 20, acceptableDegradation: ["narrow_time_window"], requestedOutputs: ["DataProductRevision", "EvidenceBundleRevision"], budgetMinor: 1000, expiresAt: expires.toISOString() };
    const operation = command === "REQUEST_DATA" ? client.requestMissingData?.({ runId: selectedRunId, commandId, expectedStateVersion: projection.expectedStateVersion, body }) : client.confirmDataRequirement?.({ runId: selectedRunId, commandId, expectedStateVersion: projection.expectedStateVersion, decision: decision ?? "accept", ...(decision === "reject" ? { reason: dataReason } : {}) });
    if (!operation) { setCommandPhase("failed"); setCommandMessage("当前客户端未提供 canonical DataRequirement 命令；已失败关闭。"); return; }
    void operation.then((result) => { setWorkbenchView(result.view); setCommandPhase("succeeded"); setCommandMessage(`${command} 已按 DataRequirement ${result.response.requirementRef.resourceId} · r${result.response.requirementRef.revision} 回读闭合${result.response.dataReplayed || result.response.runReplayed ? "（幂等重放）" : ""}。`); }, (error: unknown) => { const unknown = error instanceof EcommerceInvestigationClientError && error.code === "COMMAND_OUTCOME_UNKNOWN"; setCommandPhase(unknown ? "unknown" : "failed"); setCommandMessage(unknown ? "数据命令结果未知；已锁定写入口，只允许 GET 重新核验，禁止再次 POST。" : "数据命令被拒绝或 exact 回读冲突；已锁定写入口，请先重新读取。"); });
  };

  return (
    <section id={id} aria-labelledby={labelledBy} className="analyst-panel business-investigation-tab" role="tabpanel">
      <header><div><span>Business Investigation · BI-W8-01</span><h2>生意探究</h2></div><strong className="content-campaign-status is-blocked">{commandsEnabled ? "受控命令" : "只读"}</strong></header>
      <aside className="business-investigation-boundary" aria-label="生意探究只读边界">
        <strong>只读边界</strong>
        <span>{BUSINESS_INVESTIGATION_READ_FLAG}</span>
        <span>Principal 可见 canonical Case/Run</span>
        <span>三级选择原子切换</span>
        <span>{commandsEnabled ? BUSINESS_INVESTIGATION_COMMAND_FLAG : "写入口 0"} · 周期计划、评审与 Handoff 关闭</span>
      </aside>

      {phase === "loading" ? <div className="business-investigation-state is-loading" role="status"><strong>正在读取分析记录…</strong><p>等待 tenant-scoped canonical Case 列表。</p><span className="business-investigation-skeleton" aria-hidden="true" /></div> : null}
      {phase === "empty" ? <div className="business-investigation-state is-empty"><strong>当前没有可见分析记录</strong><p>未知或未创建不能显示为 0，也不以演示 Case 补齐。</p><button type="button" onClick={loadCases}>重新读取列表</button></div> : null}
      {phase === "forbidden" ? <div className="business-investigation-state is-forbidden" role="alert"><strong>无权读取生意探究</strong><p>未泄露其他租户的渠道、实体或分析记录。</p></div> : null}
      {phase === "failed" ? <div className="business-investigation-state is-failed" role="alert"><strong>分析记录读取失败</strong><p>页面已失败关闭，未保留旧选择。</p><button type="button" onClick={loadCases}>重新读取</button></div> : null}

      {phase === "ready" ? <div className="business-investigation-selector" aria-label="生意探究三级选择">
        <label><span>1 · 渠道视角</span><select aria-label="渠道视角" value={selectedChannelId} onChange={(event) => onChannelChange(event.currentTarget.value)}>{channels.map((channelId) => <option key={channelId} value={channelId}>{channelId}</option>)}</select><small>来自 Case 的 exact ChannelRevision，不推测渠道名称。</small></label>
        <fieldset><legend>2 · 经营实体</legend><div className="business-investigation-entities">{entities.map((entity, index) => <button type="button" role="radio" aria-checked={selectedEntityKey === entity.key} tabIndex={selectedEntityKey === entity.key ? 0 : -1} className={selectedEntityKey === entity.key ? "is-selected" : ""} key={entity.key} onClick={() => onEntityChange(entity.key)} onKeyDown={(event) => {
          if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) return;
          event.preventDefault();
          const nextIndex = event.key === "Home" ? 0 : event.key === "End" ? entities.length - 1 : (index + (event.key === "ArrowRight" || event.key === "ArrowDown" ? 1 : -1) + entities.length) % entities.length;
          const next = entities[nextIndex];
          if (!next) return;
          onEntityChange(next.key);
          event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="radio"]')[nextIndex]?.focus();
        }}><strong>{entity.entityId}</strong><span>{entity.channelId}</span></button>)}</div><small>同名实体按渠道隔离；上游切换后旧实体内容立即清空。</small></fieldset>
        <label><span>3 · 分析记录</span><select aria-label="分析记录" value={selectedCaseId} onChange={(event) => onCaseChange(event.currentTarget.value)}>{visibleCases.map((item) => <option key={item.caseId} value={item.caseId}>{item.title} · {ANALYSIS_LABELS[item.analysisType]}</option>)}</select><small>Case revision、生命周期和运行记录均来自 canonical authority。</small></label>
      </div> : null}

      {phase === "ready" && selectedCase ? <section className="business-investigation-current" aria-label="当前分析记录">
        <header><div><span>{selectedCase.analysisType}</span><h3>{selectedCase.title}</h3></div><strong className={`is-${selectedCase.lifecycle.toLowerCase()}`}>{selectedCase.lifecycle}</strong></header>
        <dl><div><dt>Case</dt><dd>{selectedCase.caseId} · r{selectedCase.revision}</dd></div><div><dt>渠道</dt><dd>{selectedCase.channelRef.resourceId}</dd></div><div><dt>经营实体</dt><dd>{selectedCase.businessEntityRef.resourceId}</dd></div><div><dt>创建时间</dt><dd>{new Date(selectedCase.createdAt).toLocaleString("zh-CN", { hour12: false })}</dd></div></dl>
        {runPhase === "loading" ? <p className="is-loading" role="status">正在读取当前 Case 的 Run…</p> : null}
        {runPhase === "empty" ? <p className="is-empty">当前 Case 尚无 Run；不生成演示记录。<button type="button" onClick={() => setRunReloadRevision((value) => value + 1)}>重新读取 Run</button></p> : null}
        {runPhase === "forbidden" ? <p className="is-forbidden" role="alert">Run 不可见；Case 保持只读且不泄露其他租户状态。</p> : null}
        {runPhase === "failed" ? <p className="is-failed" role="alert">Run 读取失败；旧 Run 已清空。<button type="button" onClick={() => setRunReloadRevision((value) => value + 1)}>重新读取 Run</button></p> : null}
        {runPhase === "ready" ? <label><span>Run 记录</span><select aria-label="Run 记录" value={selectedRunId} onChange={(event) => { clearView(); setSelectedRunId(event.currentTarget.value); }}>{runs.map((item) => <option key={item.authority.runId} value={item.authority.runId}>{item.authority.runId} · {item.state.lifecycle}/{item.state.control}</option>)}</select></label> : null}
      </section> : null}
      {phase === "ready" && selectedCase && selectedRunId ? <section className="business-investigation-workbench" aria-label="生意探究运行进度">
        {viewPhase === "loading" ? <div className="business-investigation-state" role="status"><strong>正在读取 Case 信封与运行进度…</strong><p>进度由服务端 canonical projection 计算。</p></div> : null}
        {viewPhase === "forbidden" ? <div className="business-investigation-state is-forbidden" role="alert"><strong>运行进度不可见</strong><p>未保留上一 Run 的 StageRail。</p></div> : null}
        {viewPhase === "failed" ? <div className="business-investigation-state is-failed" role="alert"><strong>运行进度读取失败</strong><p>页面失败关闭，不本地推演 x/y。</p><button type="button" onClick={() => setViewReloadRevision((value) => value + 1)}>重新读取运行进度</button></div> : null}
        {viewPhase === "ready" && workbenchView ? <>
          {canonicalDataState !== "ready" ? <AsyncStateBoundary state={canonicalDataState} title={canonicalDataState === "stale" ? "数据截止面已过期" : "当前仅有部分事实可用"} description={canonicalDataState === "stale" ? "仅保留已标记的 canonical 快照，不把旧数据冒充当前事实。" : "仅展示已覆盖事实，未满足范围保持缺口，不以零值代替。"} dataCutoff={readinessSnapshot?.response?.cutoffAt ?? workbenchView.observedAt} action={<button type="button" onClick={() => readinessSnapshot?.reload()}>重新核验数据状态</button>} /> : null}
          <article className="business-investigation-envelope"><header><div><span>Case 信封 · cutoff {new Date(workbenchView.observedAt).toLocaleString("zh-CN", { hour12: false })}</span><h3>{workbenchView.caseEnvelope.title}</h3></div><strong>{workbenchView.lifecycle}/{workbenchView.control}</strong></header><dl><div><dt>Case exact</dt><dd>{workbenchView.caseRef.resourceId} · r{workbenchView.caseRef.revision}</dd></div><div><dt>Run exact</dt><dd>{workbenchView.runRef.resourceId} · v{workbenchView.runRef.revision}</dd></div><div><dt>Scope</dt><dd>{workbenchView.caseEnvelope.scopeRef.resourceId} · r{workbenchView.caseEnvelope.scopeRef.revision}</dd></div><div><dt>Profile</dt><dd>{workbenchView.caseEnvelope.investigationProfileRef.resourceId} · r{workbenchView.caseEnvelope.investigationProfileRef.revision}</dd></div><div><dt>Schedule</dt><dd>{workbenchView.caseEnvelope.schedulePolicyRef ? `${workbenchView.caseEnvelope.schedulePolicyRef.resourceId} · r${workbenchView.caseEnvelope.schedulePolicyRef.revision}` : "未绑定"}</dd></div><div><dt>Checkpoint</dt><dd>{workbenchView.runtime.checkpoint ? `${workbenchView.runtime.checkpoint.checkpointId} · #${workbenchView.runtime.checkpoint.sequence}` : "尚无 Checkpoint"}</dd></div></dl></article>
          {commandsEnabled && workbenchView.commandProjection && client.executeRunCommand ? <article className={`business-investigation-commands is-${commandPhase}`} aria-label="Run 受控命令">
            <header><div><span>canonical Run control · state v{workbenchView.commandProjection.expectedStateVersion}</span><h3>受控命令</h3></div><strong>{workbenchView.commandProjection.externalEffectsAllowed ? "外部副作用开启" : "无外部副作用"}</strong></header>
            {workbenchView.commandProjection.allowedCommands.some((command) => ["PAUSE_RUN", "RESUME_RUN", "CANCEL_RUN"].includes(command)) && commandPhase !== "unknown" && commandPhase !== "failed" ? <div>{workbenchView.commandProjection.allowedCommands.filter((command): command is InvestigationControlCommand => ["PAUSE_RUN", "RESUME_RUN", "CANCEL_RUN"].includes(command)).map((command) => <button type="button" key={command} disabled={commandPhase === "pending"} onClick={() => executeRunCommand(command)}>{command === "PAUSE_RUN" ? "暂停 Run" : command === "RESUME_RUN" ? "继续 Run" : "取消 Run"}</button>)}</div> : <p>服务端当前未授权 Run control；页面不按 control/lifecycle 本地推演。</p>}
            {commandMessage ? <p role={commandPhase === "failed" || commandPhase === "unknown" ? "alert" : "status"}>{commandMessage}</p> : null}
            {commandPhase === "failed" || commandPhase === "unknown" ? <button type="button" onClick={() => { setCommandPhase("idle"); setCommandMessage(""); setViewReloadRevision((value) => value + 1); }}>仅 GET 重新核验</button> : null}
          </article> : null}
          <article className="business-investigation-progress"><header><div><span>服务端进度</span><h3>{workbenchView.runtime.completed}/{workbenchView.runtime.total} 波完成</h3></div><strong className={`is-${workbenchView.runtime.bindingStatus}`}>{workbenchView.runtime.bindingStatus === "unbound" ? "尚未绑定" : workbenchView.runtime.bindingStatus === "task_pending" ? "等待 TaskRun" : workbenchView.runtime.taskRunStatus}</strong></header><ol>{workbenchView.runtime.stages.map((stage, index) => <li key={stage.stageId} className={`is-${stage.status}`} aria-current={workbenchView.runtime.currentStageId === stage.stageId ? "step" : undefined}><span>{index + 1}</span><div><strong>{stage.title}</strong><small>{stage.stageId} · {stage.status}{stage.attempt ? ` · attempt ${stage.attempt}` : ""}</small></div></li>)}</ol><p>Stage 完成仅表示 canonical StepRun 通过阶段门，不代表真实业务方案已执行。</p></article>
          <article className="business-investigation-stage-workspace"><header><div><span>当前阶段工作区 · {workbenchView.currentWorkspace.stageId ?? "unbound"}</span><h3>{workbenchView.currentWorkspace.title}</h3></div><strong className={`is-${workbenchView.currentWorkspace.status}`}>{workbenchView.currentWorkspace.status}</strong></header><p className="business-investigation-question">{workbenchView.currentWorkspace.question}</p><dl className="business-investigation-responsibility"><div><dt>责任槽</dt><dd>{workbenchView.currentWorkspace.responsibilitySlotIds.length ? workbenchView.currentWorkspace.responsibilitySlotIds.join(" · ") : "未知/未绑定"}</dd></div><div><dt>承担者</dt><dd>{workbenchView.currentWorkspace.assigneeRefs.length ? workbenchView.currentWorkspace.assigneeRefs.map((item) => item.resourceId).join(" · ") : "未知/未绑定"}</dd></div><div><dt>输入 refs</dt><dd>{workbenchView.currentWorkspace.inputRefs.length ? workbenchView.currentWorkspace.inputRefs.map((item) => item.resourceId).join(" · ") : "未知/缺证据"}</dd></div><div><dt>输出 refs</dt><dd>{workbenchView.currentWorkspace.outputRefs.length ? workbenchView.currentWorkspace.outputRefs.map((item) => item.resourceId).join(" · ") : "未知/缺证据"}</dd></div></dl><div className="business-investigation-contributions">{workbenchView.currentWorkspace.areas.map((area) => <section key={area.area} className={`is-${area.status}`}><header><strong>{area.title}</strong><span>{area.status === "reference_only" ? "仅可回链" : area.status === "present" ? "已声明缺口" : "未知/缺证据"}</span></header><p>{area.summary}</p>{area.resourceRefs.length || area.exactRefs.length ? <small>{[...area.resourceRefs.map((item) => item.resourceId), ...area.exactRefs.map((item) => `${item.resourceId} · r${item.revision}`)].join(" · ")}</small> : null}</section>)}</div><ul className="business-investigation-nonclaims">{workbenchView.currentWorkspace.nonClaims.map((item) => <li key={item}>{item}</li>)}</ul></article>
          <article className="business-investigation-drilldowns"><header><div><span>服务端可回链投影 · {workbenchView.drilldownVersion}</span><h3>Evidence / Artifact / Timeline</h3></div><strong className={workbenchView.drilldownVersion === "canonical-v4" ? "is-bound" : "is-unbound"}>{workbenchView.drilldownVersion === "canonical-v4" ? "canonical" : "legacy"}</strong></header><div className="business-investigation-drilldown-grid">
            <section aria-label="Evidence 下钻"><h4>Evidence</h4><p>{workbenchView.evidence.status === "exact" ? "可核验 exact refs" : "缺少可核验 Evidence exact ref"}</p>{workbenchView.evidence.exactRefs.map((item) => <details key={`${item.resourceType}:${item.resourceId}:${item.revision}`}><summary>{item.resourceType} · {item.resourceId}</summary><dl><div><dt>revision</dt><dd>{String(item.revision)}</dd></div><div><dt>hash</dt><dd>{item.contentHash}</dd></div></dl></details>)}{workbenchView.evidence.locatorRefs.length ? <details><summary>仅定位 refs · 非 exact</summary><ul>{workbenchView.evidence.locatorRefs.map((item) => <li key={`${item.resourceType}:${item.resourceId}:${item.revision ?? "_"}`}>{item.resourceType} · {item.resourceId} · {item.revision ?? "无 revision"}</li>)}</ul></details> : null}</section>
            <section aria-label="Artifact 下钻"><h4>Artifact</h4><p>四类领域槽位；missing 不继承旧 Run。</p>{workbenchView.artifacts.map((item) => <details key={item.artifactType}><summary>{item.artifactType} · {item.status}</summary>{item.status === "bound" && item.artifactRef ? <dl><div><dt>exact</dt><dd>{item.artifactRef.resourceId} · r{String(item.artifactRef.revision)}</dd></div><div><dt>hash</dt><dd>{item.artifactRef.contentHash}</dd></div><div><dt>binding</dt><dd>{item.bindingId} · selection r{item.selectionRevision}</dd></div><div><dt>cutoff</dt><dd>{item.dataCutoff ? new Date(item.dataCutoff).toLocaleString("zh-CN", { hour12: false }) : "未知"}</dd></div><div><dt>lineage</dt><dd>{item.lineageRef ? `${item.lineageRef.resourceId} · r${String(item.lineageRef.revision)}` : "未知"}</dd></div></dl> : <p>尚无 canonical binding。</p>}</details>)}</section>
            <section aria-label="Timeline 下钻"><h4>Timeline</h4><p>{workbenchView.timeline.length ? "按服务端时间与稳定键排序" : "legacy v3 未提供 canonical Timeline"}</p><ol>{workbenchView.timeline.map((item) => <li key={item.eventId}><time dateTime={item.occurredAt}>{new Date(item.occurredAt).toLocaleString("zh-CN", { hour12: false })}</time><strong>{item.title}</strong><details><summary>{item.exactRef.resourceType} · {item.exactRef.resourceId}</summary><small>r{String(item.exactRef.revision)} · {item.exactRef.contentHash}{item.relatedRef ? ` · related ${item.relatedRef.resourceType}/${item.relatedRef.resourceId}` : ""}</small></details></li>)}</ol></section>
          </div><p className="business-investigation-drilldown-boundary">下钻只展示服务端 exact refs 与 locator-only 差异；不存在本地拼接时间线、模型私有过程或业务写入口。</p></article>
          {(() => {
            const pending = workbenchView.pendingRequirementRef; const source = readinessSnapshot?.phase === "ready" ? readinessSnapshot.response : null; const investigation = source?.investigation ?? null; const matches = sameRequirement(pending, investigation?.requirementRef ?? null);
            const sourceStatus = source?.status ?? (readinessSnapshot?.phase === "forbidden" ? "forbidden" : readinessSnapshot?.phase === "failed" ? "failed" : "unknown");
            const requirementStatus = !pending ? "unknown" : !investigation ? "unknown" : matches ? investigation.status : "conflict";
            const analysisStatus = workbenchView.runtime.taskRunStatus === "running" ? "running" : workbenchView.runtime.taskRunStatus === "succeeded" ? "ready" : ["failed", "cancelled", "unknown"].includes(workbenchView.runtime.taskRunStatus ?? "") ? "blocked" : "unknown";
            const axes = [{ id: "source", title: "SourceReadiness", status: sourceStatus }, { id: "semantic", title: "SemanticReadiness", status: "unknown" }, { id: "evidence", title: "EvidenceReadiness", status: "unknown" }, { id: "analysis", title: "AnalysisReadiness", status: analysisStatus }, { id: "handoff", title: "HandoffReadiness", status: "unknown" }, { id: "action", title: "ActionReadiness", status: "unknown" }];
            return <article className="business-investigation-gates"><header><div><span>数据与运行门 · canonical SourceReadiness</span><h3>阻断与 DataRequirement</h3></div><strong className={`is-${requirementStatus}`}>{requirementStatus}</strong></header><div className="business-investigation-gate-axes">{axes.map((axis) => <section key={axis.id} className={`is-${axis.status}`}><strong>{axis.title}</strong><span>{axis.status === "unknown" ? "未知/缺证据" : axis.status}</span></section>)}</div><dl className="business-investigation-requirement"><div><dt>当前 DataRequirement</dt><dd>{pending ? `${pending.resourceId} · r${pending.revision}` : "未知/当前 Run 未声明待补数需求"}</dd></div><div><dt>exact 对账</dt><dd>{!pending ? "无当前待对账 ref" : !investigation ? "缺 SourceReadiness investigation 投影" : matches ? "同一 requirement revision/hash" : "冲突：readiness 不属于当前 Run requirement"}</dd></div><div><dt>事实覆盖</dt><dd>{matches && investigation ? `${investigation.coveredFactCount}/${investigation.requiredFactCount}` : "未知/缺证据"}</dd></div><div><dt>新鲜度</dt><dd>{matches && investigation?.freshnessExpiresAt ? `有效至 ${new Date(investigation.freshnessExpiresAt).toLocaleString("zh-CN", { hour12: false })}` : "未知/缺证据"}</dd></div></dl>{matches && investigation?.unmetFacts.length ? <p className="business-investigation-unmet"><strong>未满足事实：</strong>{investigation.unmetFacts.join(" · ")}</p> : null}<div className="business-investigation-blockers" aria-label="当前数据阻断">{matches && investigation?.blockers.length ? investigation.blockers.map((blocker) => <section key={`${blocker.code}:${blocker.fact ?? "_"}`}><strong>{blocker.code}</strong><p>{blocker.reason}</p><small>{blocker.fact ? `事实 ${blocker.fact}` : "未绑定单一事实"}{blocker.sourceIds.length ? ` · 来源 ${blocker.sourceIds.join(" / ")}` : " · 来源未知"}</small></section>) : <p>{pending ? investigation ? "requirement exact ref 冲突，未消费其他 Run 的 blocker。" : "当前 requirement 缺同版 SourceReadiness blocker 投影。" : "当前 Run 未声明待补数 requirement；不显示 0 或伪完成。"}</p>}</div>
              {commandsEnabled && workbenchView.commandProjection?.allowedCommands.includes("REQUEST_DATA") ? <form className="business-investigation-data-command" aria-label="创建补数需求" onSubmit={(event) => { event.preventDefault(); executeDataCommand("REQUEST_DATA"); }}><header><div><span>Receipt-first · 不读取源数据</span><h4>创建补数需求</h4></div><strong>需人工确认</strong></header><label><span>缺失事实标识（每行一项）</span><textarea rows={3} value={missingFacts} onChange={(event) => setMissingFacts(event.currentTarget.value)} required /></label><dl><div><dt>范围</dt><dd>近 30 天 · day grain · 1h freshness</dd></div><div><dt>质量门</dt><dd>0.95 · min population 20</dd></div><div><dt>产物</dt><dd>DataProduct + EvidenceBundle</dd></div></dl><button type="submit" disabled={commandPhase === "pending" || !missingFacts.trim()}>提交 DataRequirement</button></form> : null}
              {commandsEnabled && workbenchView.commandProjection?.allowedCommands.includes("CONFIRM_DATA_REQUIREMENT") ? <form className="business-investigation-data-command" aria-label="人工确认补数需求" onSubmit={(event) => { event.preventDefault(); executeDataCommand("CONFIRM_DATA_REQUIREMENT", "accept"); }}><header><div><span>当前 exact requirement · {pending?.resourceId}</span><h4>人工确认范围</h4></div><strong>不等于已补齐</strong></header><label><span>驳回说明（接受无需填写）</span><textarea rows={2} value={dataReason} onChange={(event) => setDataReason(event.currentTarget.value)} maxLength={500} /></label><div className="business-investigation-data-decisions"><button type="submit" disabled={commandPhase === "pending"}>接受需求范围</button><button type="button" disabled={commandPhase === "pending" || !dataReason.trim()} onClick={() => executeDataCommand("CONFIRM_DATA_REQUIREMENT", "reject")}>驳回并保留阻断</button></div></form> : null}
              <p className="business-investigation-gate-boundary">不提供“忽略阻断继续”；补数命令只创建或确认 canonical DataRequirement，不读取源数据、不 fulfill、不恢复 TaskRun。其余五轴缺专门 authority 时保持未知。</p></article>;
          })()}
        </> : null}
      </section> : null}
      {tenant ? <footer className="business-investigation-tenant">租户 {tenant.orgId}/{tenant.projectId} · {commandsEnabled ? "canonical command 单次消费" : "canonical GET-only"} · 未读取真实源系统</footer> : null}
    </section>
  );
}
