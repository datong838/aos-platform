import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import {
  aipMemorySdk,
  type KnowledgePipelineAlert,
  type KnowledgePipelineCheckpoint,
  type KnowledgePipelinePolicy,
  type KnowledgePipelineOperationalReadinessEnvelope,
  type KnowledgePipelineReceipt,
  type KnowledgePipelineRun,
  type KnowledgePipelineSchedule,
  type KnowledgeQueryResult,
  type KnowledgeReadiness,
  type MemoryAuthorityItem,
  type MemoryAgentInstance,
  type MemoryAgentProjection,
  type MemoryExposure,
  type MemoryImprovementObservation,
  type MemoryRevocationImpact,
  type MemoryCandidate,
  type MemoryCandidateEvent,
} from "../../api/aipMemory";
import { PageChrome } from "../../components/PageChrome";

type View = "candidates" | "memories" | "agents" | "query" | "pipelines" | "readiness";
type LoadState = "loading" | "loaded" | "error";

export type MemoryContributionContext = {
  subjectType: string;
  subjectId: string;
  taskId: string;
  skillId: string;
  logicId: string;
  coworkerId: string;
  moduleId: string;
};

function exactContextValue(params: URLSearchParams, key: string): string {
  const value = params.get(key)?.trim() || "";
  return value.length <= 200 ? value : "";
}

export function parseMemoryContributionContext(params: URLSearchParams): MemoryContributionContext {
  return {
    subjectType: exactContextValue(params, "subjectType") || "Product",
    subjectId: exactContextValue(params, "subjectId"),
    taskId: exactContextValue(params, "taskId"),
    skillId: exactContextValue(params, "skillId"),
    logicId: exactContextValue(params, "logicId"),
    coworkerId: exactContextValue(params, "coworkerId"),
    moduleId: exactContextValue(params, "moduleId"),
  };
}

const panel = { border: "1px solid var(--aos-border)", background: "var(--aos-panel)", borderRadius: 6, padding: 18 } as const;
const blockerText = { overflowWrap: "anywhere" } as const;
const statusLabels: Record<string, string> = {
  pending: "待治理", quarantined: "已隔离", rejected: "已拒绝", approved: "已批准", promoted: "已晋升",
  provisioning: "准备中", active: "生效中", suspended: "已暂停", deleted: "已删除",
  stale: "已过期", revoked: "已撤销", expired: "已失效",
  queued: "排队中", running: "运行中", paused: "已暂停", succeeded: "已成功", partial: "部分成功",
  failed: "已失败", cancelled: "已取消", unknown: "状态未知", disabled: "已停用",
  complete: "完整", degraded: "降级回源", blocked: "已阻断",
  ready: "运行就绪", unconfigured: "未配置",
};

const pipelineKindLabels: Record<string, string> = {
  seed_import: "种子知识导入",
  operational_learning: "运营经验学习",
  network_learning: "网络知识学习",
  competitor_analysis: "竞品情报分析",
  professional_database: "专业数据库接入",
  customer_feedback: "客户反馈学习",
  human_experience: "人工经验沉淀",
};

const viewLabels: Record<View, string> = {
  candidates: "知识候选",
  memories: "正式记忆",
  agents: "数字同事记忆",
  query: "知识检索",
  pipelines: "知识管道",
  readiness: "冷启动与检索",
};

export function memoryStatusLabel(status: string): string {
  return statusLabels[status] || status;
}

export function authoritySubjectLabel(subject: { resourceType: string; resourceId: string }): string {
  return `${subject.resourceType} · ${subject.resourceId}`;
}

function memoryLayerLabel(layer: string): string {
  return ({ semantic: "事实与概念", episodic: "经验与事件", procedural: "流程与做法" } as Record<string, string>)[layer] || layer;
}

function memorySubjectTypeLabel(type: string): string {
  const normalized = type.toLowerCase();
  if (normalized.includes("product")) return "商品";
  if (normalized.includes("customer")) return "客户";
  if (normalized.includes("campaign")) return "活动";
  if (normalized.includes("order")) return "订单";
  if (normalized.includes("content")) return "内容";
  return "业务对象";
}

function sourceKindLabel(kind: string): string {
  return ({ authorized_document: "授权文档", human_observation: "人工经验", operational_receipt: "运营凭证", trusted_adapter: "可信适配器" } as Record<string, string>)[kind] || kind;
}

export function MemoryGovernancePage() {
  const [searchParams] = useSearchParams();
  const contributionContext = parseMemoryContributionContext(searchParams);
  const initialView = (searchParams.get("view") as View | null) || "candidates";
  const [view, setView] = useState<View>(
    ["candidates", "memories", "agents", "query", "pipelines", "readiness"].includes(initialView)
      ? initialView
      : "candidates"
  );
  const [candidates, setCandidates] = useState<MemoryCandidate[]>([]);
  const [memories, setMemories] = useState<MemoryAuthorityItem[]>([]);
  const [events, setEvents] = useState<MemoryCandidateEvent[]>([]);
  const [selectedCandidate, setSelectedCandidate] = useState<MemoryCandidate | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [error, setError] = useState("");
  const [subjectType, setSubjectType] = useState(contributionContext.subjectType);
  const [subjectId, setSubjectId] = useState(contributionContext.subjectId);
  const [taskId, setTaskId] = useState(contributionContext.taskId);
  const [skillId, setSkillId] = useState(contributionContext.skillId);
  const [markings, setMarkings] = useState("internal");
  const [queryState, setQueryState] = useState<"idle" | "loading" | "complete" | "degraded" | "blocked" | "error">("idle");
  const [queryResult, setQueryResult] = useState<KnowledgeQueryResult | null>(null);
  const [queryError, setQueryError] = useState("");
  const [pipelinePolicies, setPipelinePolicies] = useState<KnowledgePipelinePolicy[]>([]);
  const [pipelineSchedules, setPipelineSchedules] = useState<KnowledgePipelineSchedule[]>([]);
  const [pipelineRuns, setPipelineRuns] = useState<KnowledgePipelineRun[]>([]);
  const [pipelineReadiness, setPipelineReadiness] = useState<KnowledgePipelineOperationalReadinessEnvelope | null>(null);
  const [pipelineLoadState, setPipelineLoadState] = useState<LoadState>("loading");
  const [pipelineError, setPipelineError] = useState("");
  const [busyScheduleId, setBusyScheduleId] = useState("");
  const [selectedRun, setSelectedRun] = useState<KnowledgePipelineRun | null>(null);
  const [selectedReceipt, setSelectedReceipt] = useState<KnowledgePipelineReceipt | null>(null);
  const [selectedCheckpoint, setSelectedCheckpoint] = useState<KnowledgePipelineCheckpoint | null>(null);
  const [selectedAlerts, setSelectedAlerts] = useState<KnowledgePipelineAlert[]>([]);
  const [readiness, setReadiness] = useState<KnowledgeReadiness | null>(null);
  const [readinessState, setReadinessState] = useState<LoadState>("loading");
  const [readinessError, setReadinessError] = useState("");
  const [governanceBusy, setGovernanceBusy] = useState("");
  const [governanceMessage, setGovernanceMessage] = useState("");
  const [requiredApplicability, setRequiredApplicability] = useState("");
  const [evalReportId, setEvalReportId] = useState("");
  const [evalReportRevision, setEvalReportRevision] = useState("");
  const [evalReportHash, setEvalReportHash] = useState("");
  const [draftId, setDraftId] = useState("");
  const [draftRevision, setDraftRevision] = useState("");
  const [approvalEventId, setApprovalEventId] = useState("");
  const [approvalEventRevision, setApprovalEventRevision] = useState("");
  const [rejectionReason, setRejectionReason] = useState("quality_review_failed");
  const [memoryItemId, setMemoryItemId] = useState("");
  const [memoryExpiresAt, setMemoryExpiresAt] = useState("");
  const [revocationReason, setRevocationReason] = useState("contamination_confirmed");

  async function reload() {
    setLoadState("loading");
    setError("");
    setSelectedCandidate(null);
    setEvents([]);
    try {
      const [nextCandidates, nextMemories] = await Promise.all([aipMemorySdk.candidates(), aipMemorySdk.memories()]);
      setCandidates(nextCandidates);
      setMemories(nextMemories);
      setLoadState("loaded");
    } catch (caught) {
      setCandidates([]);
      setMemories([]);
      setError(String((caught as Error).message || caught));
      setLoadState("error");
    }
  }

  async function reloadPipelines() {
    setPipelineLoadState("loading");
    setPipelineError("");
    try {
      const [policies, schedules, runs, operational] = await Promise.all([
        aipMemorySdk.pipelinePolicies(),
        aipMemorySdk.pipelineSchedules(),
        aipMemorySdk.pipelineRuns(),
        aipMemorySdk.pipelineReadiness(),
      ]);
      setPipelinePolicies(policies);
      setPipelineSchedules(schedules);
      setPipelineRuns(runs);
      setPipelineReadiness(operational);
      setPipelineLoadState("loaded");
    } catch (caught) {
      setPipelinePolicies([]);
      setPipelineSchedules([]);
      setPipelineRuns([]);
      setPipelineReadiness(null);
      setPipelineError(String((caught as Error).message || caught));
      setPipelineLoadState("error");
    }
  }

  async function reloadReadiness() {
    setReadinessState("loading"); setReadinessError("");
    try { setReadiness(await aipMemorySdk.knowledgeReadiness()); setReadinessState("loaded"); }
    catch (caught) { setReadiness(null); setReadinessError(String((caught as Error).message || caught)); setReadinessState("error"); }
  }

  useEffect(() => { void reload(); void reloadPipelines(); void reloadReadiness(); }, []);

  async function transitionSchedule(schedule: KnowledgePipelineSchedule) {
    const toStatus = schedule.status === "active" ? "paused" : schedule.status === "paused" ? "active" : "paused";
    setBusyScheduleId(schedule.scheduleId);
    setPipelineError("");
    try {
      await aipMemorySdk.transitionPipelineSchedule(schedule.scheduleId, {
        expectedVersion: schedule.version,
        fromStatus: schedule.status,
        toStatus,
        reasonCode: `ui_${schedule.status}_to_${toStatus}`,
      });
      await reloadPipelines();
    } catch (caught) {
      setPipelineError(`Schedule 状态变更被阻断：${String((caught as Error).message || caught)}`);
    } finally {
      setBusyScheduleId("");
    }
  }

  async function inspectPipelineRun(run: KnowledgePipelineRun) {
    setSelectedRun(run);
    setSelectedReceipt(null);
    setSelectedCheckpoint(null);
    setSelectedAlerts([]);
    setPipelineError("");
    try {
      const schedule = pipelineSchedules.find((item) => item.scheduleId === run.scheduleId);
      const [receipt, checkpoint, alerts] = await Promise.all([
        aipMemorySdk.pipelineReceipt(run.pipelineRunId),
        schedule ? aipMemorySdk.pipelineCheckpoint(schedule.scheduleId) : Promise.resolve(null),
        aipMemorySdk.pipelineAlerts(run.pipelineRunId),
      ]);
      setSelectedReceipt(receipt);
      setSelectedCheckpoint(checkpoint);
      setSelectedAlerts(alerts);
    } catch (caught) {
      setPipelineError(`Pipeline 证据读取失败：${String((caught as Error).message || caught)}`);
    }
  }

  async function inspectCandidate(candidate: MemoryCandidate) {
    setSelectedCandidate(candidate);
    setEvents([]);
    setError("");
    setGovernanceMessage("");
    setRequiredApplicability(candidate.request.source.applicability.join(","));
    setMemoryItemId(`memory-${candidate.candidateId}`);
    try {
      setEvents(await aipMemorySdk.candidateEvents(candidate.candidateId));
    } catch (caught) {
      setError(`Candidate 事件读取失败：${String((caught as Error).message || caught)}`);
    }
  }

  function applicabilityList(): string[] {
    return requiredApplicability.split(",").map((value) => value.trim()).filter(Boolean);
  }

  async function governCandidate(operation: "approve" | "reject" | "promote") {
    if (!selectedCandidate) return;
    const applicability = applicabilityList();
    if (!applicability.length) {
      setGovernanceMessage("请填写至少一个适用范围。");
      return;
    }
    setGovernanceBusy(operation);
    setGovernanceMessage("");
    try {
      let updatedCandidate: MemoryCandidate | null = null;
      if (operation === "approve") {
        if (!evalReportId.trim() || !evalReportRevision.trim() || !/^[0-9a-f]{64}$/.test(evalReportHash.trim()) || !draftId.trim() || !draftRevision.trim() || !approvalEventId.trim() || !approvalEventRevision.trim()) {
          throw new Error("批准前必须完整填写评测报告、草稿和审批事件的精确引用及评测内容摘要");
        }
        updatedCandidate = await aipMemorySdk.approveCandidate(selectedCandidate.candidateId, {
          expectedVersion: selectedCandidate.version,
          governance: {
            evalReport: { artifactType: "aip.eval_report", artifactId: evalReportId.trim(), revision: evalReportRevision.trim(), contentHash: evalReportHash.trim() },
            draft: { resourceType: "aip.draft", resourceId: draftId.trim(), revision: draftRevision.trim(), authority: "postgresql" },
            approvalEvent: { resourceType: "aip.approval_event", resourceId: approvalEventId.trim(), revision: approvalEventRevision.trim(), authority: "postgresql" },
          },
          requiredApplicability: applicability,
        });
      } else if (operation === "reject") {
        if (!rejectionReason.trim()) throw new Error("驳回必须填写原因");
        updatedCandidate = await aipMemorySdk.rejectCandidate(selectedCandidate.candidateId, { expectedVersion: selectedCandidate.version, reasonCodes: [rejectionReason.trim()] });
      } else {
        if (!memoryItemId.trim()) throw new Error("晋升必须填写正式记忆标识");
        await aipMemorySdk.promoteCandidate(selectedCandidate.candidateId, {
          memoryItemId: memoryItemId.trim(), expectedVersion: selectedCandidate.version, requiredApplicability: applicability,
          ...(memoryExpiresAt ? { expiresAt: new Date(memoryExpiresAt).toISOString() } : {}),
        });
      }
      await reload();
      if (updatedCandidate) {
        setSelectedCandidate(updatedCandidate);
        setEvents(await aipMemorySdk.candidateEvents(updatedCandidate.candidateId));
      } else {
        setView("memories");
      }
      setGovernanceMessage(operation === "approve" ? "候选已提交批准并重新读取权威事件。" : operation === "reject" ? "候选已驳回并保留不可变事件。" : "候选已晋升为正式记忆并重新读取权威修订。");
    } catch (caught) {
      setGovernanceMessage(`治理操作未完成：${String((caught as Error).message || caught)}`);
    } finally {
      setGovernanceBusy("");
    }
  }

  async function revokeMemory(memory: MemoryAuthorityItem) {
    if (!revocationReason.trim() || memory.item.status !== "active") return;
    setGovernanceBusy(`revoke:${memory.item.memoryItemId}`);
    setGovernanceMessage("");
    try {
      await aipMemorySdk.revokeMemory(memory.item.memoryItemId, { expectedVersion: memory.item.version, reasonCode: revocationReason.trim() });
      await reload();
      setGovernanceMessage("正式记忆已撤销；历史修订继续保留用于审计，后续检索将按权威状态排除。");
    } catch (caught) {
      setGovernanceMessage(`撤销未完成：${String((caught as Error).message || caught)}`);
    } finally {
      setGovernanceBusy("");
    }
  }

  async function runKnowledgeQuery() {
    const required = [subjectType, subjectId, taskId, skillId].map((value) => value.trim());
    if (required.some((value) => !value)) {
      setQueryError("请完整填写主体类型、主体 ID、Task ID 和技能 ID。");
      setQueryState("idle");
      return;
    }
    const markingList = markings.split(",").map((value) => value.trim()).filter(Boolean);
    if (!markingList.length) {
      setQueryError("至少需要一个服务端可授权的 marking。");
      setQueryState("idle");
      return;
    }
    setQueryState("loading");
    setQueryError("");
    setQueryResult(null);
    try {
      const result = await aipMemorySdk.query({
        subject: { resourceType: required[0], resourceId: required[1], authority: "postgresql" },
        taskId: required[2],
        skillRef: { resourceType: "aip.skill", resourceId: required[3], authority: "postgresql" },
        objectRefs: [],
        timeCutoff: new Date().toISOString(),
        markings: markingList,
        maxTokens: 2048,
      });
      setQueryResult(result);
      setQueryState(result.status);
    } catch (caught) {
      setQueryError(String((caught as Error).message || caught));
      setQueryState("error");
    }
  }

  return (
    <PageChrome title="记忆与知识治理" lede="知识候选 → 审批证据 → 正式记忆 → 带来源引用的知识检索；全部来自权威链，不回填示例知识。">
      <div
        data-testid="memory-ops-stats"
        style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(110px,1fr))", gap: 10, marginBottom: 12 }}
      >
        {[
          { label: "当前视图", value: viewLabels[view] },
          { label: "加载", value: loadState === "loaded" ? "就绪" : loadState === "loading" ? "读取中" : "失败" },
          { label: "候选", value: String(candidates.length) },
          { label: "正式记忆", value: String(memories.length) },
          { label: "管道运行", value: String(pipelineRuns.length) },
          { label: "查询状态", value: memoryStatusLabel(queryState) },
        ].map((s) => (
          <div key={s.label} className="card" style={{ padding: "10px 12px" }}>
            <div style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>{s.label}</div>
            <div style={{ fontSize: 18, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{s.value}</div>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 16 }}>
        {(["candidates", "memories", "agents", "query", "pipelines", "readiness"] as const).map((item) => (
          <button key={item} type="button" className={`btn ${view === item ? "primary" : ""}`} onClick={() => setView(item)} data-testid={`memory-tab-${item}`}>
            {item === "candidates" ? `知识候选（${candidates.length}）` : item === "memories" ? `正式记忆（${memories.length}）` : item === "agents" ? "数字同事记忆" : item === "query" ? "知识检索" : item === "pipelines" ? `知识管道（${pipelineSchedules.length}）` : "冷启动与检索"}
          </button>
        ))}
        <button type="button" className="btn" onClick={() => { void reload(); void reloadPipelines(); void reloadReadiness(); }} disabled={loadState === "loading" || pipelineLoadState === "loading" || readinessState === "loading"}>{loadState === "loading" || pipelineLoadState === "loading" || readinessState === "loading" ? "读取中…" : "刷新权威状态"}</button>
        <Link to="/ontology/wiki" className="btn-nav">活知识 Wiki →</Link>
      </div>

      {loadState === "loading" && <div data-testid="memory-loading" className="callout info">正在读取当前组织与工作区的权威记忆…</div>}
      {loadState === "error" && <div data-testid="memory-error" className="callout warning">记忆权威读取失败：{error}</div>}
      {error && loadState !== "error" && <div className="callout warning">{error}</div>}

      {loadState === "loaded" && view === "candidates" && (
        <div style={{ display: "grid", gridTemplateColumns: "minmax(320px, 1fr) minmax(360px, 1.2fr)", gap: 16, alignItems: "start" }}>
          <section style={panel}>
            <h2 style={{ marginTop: 0, fontSize: 17 }}>知识候选</h2>
            {!candidates.length ? (
              <div data-testid="memory-candidates-empty" className="callout info">
                <strong>当前没有待治理知识</strong>
                <p>可从运营复盘、客户反馈或经营分析生成真实候选；页面不注入演示知识。</p>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}><button type="button" className="btn primary" onClick={() => setView("pipelines")}>查看知识生成管道</button><Link to="/aip/evals" className="btn">进入评测与复盘</Link></div>
              </div>
            ) : candidates.map((candidate) => (
              <button key={candidate.candidateId} type="button" className="btn" onClick={() => void inspectCandidate(candidate)} style={{ width: "100%", display: "grid", textAlign: "left", gap: 5, marginBottom: 8, padding: 12 }}>
                <strong>{memorySubjectTypeLabel(candidate.request.subject.resourceType)}{memoryLayerLabel(candidate.request.candidateLayer)}候选</strong>
                <span>{memoryStatusLabel(candidate.status)} · 来源 {candidate.request.source.provider} · 可信度 {(candidate.request.confidence * 100).toFixed(0)}%</span>
                <span className="muted">用途 {candidate.request.source.applicability.join("、")} · 敏感标记 {candidate.request.marking.join("、")}</span>
              </button>
            ))}
          </section>
          <section style={panel}>
            <h2 style={{ marginTop: 0, fontSize: 17 }}>治理证据与事件</h2>
            {!selectedCandidate ? <div className="muted">选择记忆候选项，查看内容摘要、来源、新鲜度、适用范围及不可变事件。</div> : <>
              <dl style={{ display: "grid", gridTemplateColumns: "150px 1fr", gap: "8px 12px", margin: 0 }}>
                <dt>业务主体</dt><dd>{memorySubjectTypeLabel(selectedCandidate.request.subject.resourceType)}</dd>
                <dt>知识类型</dt><dd>{memoryLayerLabel(selectedCandidate.request.candidateLayer)}</dd>
                <dt>来源</dt><dd>{selectedCandidate.request.source.provider} · {sourceKindLabel(selectedCandidate.request.source.sourceKind)}</dd>
                <dt>可信度</dt><dd>{(selectedCandidate.request.confidence * 100).toFixed(0)}%</dd>
                <dt>敏感标记</dt><dd>{selectedCandidate.request.marking.join("、")}</dd>
                <dt>适用范围</dt><dd>{selectedCandidate.request.source.applicability.join("、")}</dd>
                <dt>有效期</dt><dd>{new Date(selectedCandidate.request.source.freshnessExpiresAt).toLocaleString()}</dd>
                <dt>隔离原因</dt><dd>{selectedCandidate.quarantineReasons.join("、") || "无"}</dd>
              </dl>
              <details style={{ marginTop: 12 }}><summary>审计技术标识</summary><div style={{ overflowWrap: "anywhere", marginTop: 8 }}>租户 {selectedCandidate.tenant.orgId}/{selectedCandidate.tenant.projectId}<br />候选 {selectedCandidate.candidateId} · v{selectedCandidate.version}<br />主体 {authoritySubjectLabel(selectedCandidate.request.subject)}<br />载荷 {selectedCandidate.request.payload.artifactId} · {selectedCandidate.request.payload.revision}<br /><code>{selectedCandidate.request.payload.contentHash}</code></div></details>
              <h3 style={{ fontSize: 15 }}>事件时间线</h3>
              {!events.length ? <div className="muted">暂无可见事件，或事件仍在读取。</div> : events.map((event) => <div key={event.eventId} style={{ borderTop: "1px solid var(--aos-border)", padding: "10px 0" }}>
                <strong>#{event.sequence} {memoryStatusLabel(event.toStatus)}</strong> · {event.actor}<br /><span className="muted">{new Date(event.occurredAt).toLocaleString()} · {event.reasonCodes.join("、") || "无原因码"}</span>
              </div>)}
              <details style={{ ...panel, marginTop: 12 }} data-testid="memory-candidate-governance"><summary style={{ cursor: "pointer", fontWeight: 700 }}>治理操作</summary>
                <p className="muted">系统自动提交当前候选版本；CAS 冲突、引用不完整或评测未通过时服务端会拒绝，不会覆盖新版本。</p>
                <label>适用范围（逗号分隔）<input aria-label="memory-required-applicability" value={requiredApplicability} onChange={(event) => setRequiredApplicability(event.target.value)} /></label>
                {(selectedCandidate.status === "pending" || selectedCandidate.status === "quarantined") && <>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(190px,1fr))", gap: 8, marginTop: 10 }}>
                    <label>评测报告标识<input aria-label="memory-eval-report-id" value={evalReportId} onChange={(event) => setEvalReportId(event.target.value)} /></label>
                    <label>评测修订<input aria-label="memory-eval-report-revision" value={evalReportRevision} onChange={(event) => setEvalReportRevision(event.target.value)} /></label>
                    <label>评测内容摘要<input aria-label="memory-eval-report-hash" value={evalReportHash} onChange={(event) => setEvalReportHash(event.target.value)} /></label>
                    <label>草稿标识<input aria-label="memory-draft-id" value={draftId} onChange={(event) => setDraftId(event.target.value)} /></label>
                    <label>草稿修订<input aria-label="memory-draft-revision" value={draftRevision} onChange={(event) => setDraftRevision(event.target.value)} /></label>
                    <label>审批事件标识<input aria-label="memory-approval-event-id" value={approvalEventId} onChange={(event) => setApprovalEventId(event.target.value)} /></label>
                    <label>审批事件修订<input aria-label="memory-approval-event-revision" value={approvalEventRevision} onChange={(event) => setApprovalEventRevision(event.target.value)} /></label>
                    <label>驳回原因<select aria-label="memory-rejection-reason" value={rejectionReason} onChange={(event) => setRejectionReason(event.target.value)}><option value="quality_review_failed">质量评审未通过</option><option value="source_not_trusted">来源不可信</option><option value="sensitive_scope_mismatch">敏感范围不匹配</option><option value="applicability_incomplete">适用范围不完整</option></select></label>
                  </div>
                  <div style={{ display: "flex", gap: 8, marginTop: 10 }}><button type="button" className="btn primary" disabled={!!governanceBusy} onClick={() => void governCandidate("approve")}>批准候选</button><button type="button" className="btn" disabled={!!governanceBusy} onClick={() => void governCandidate("reject")}>驳回候选</button></div>
                </>}
                {selectedCandidate.status === "approved" && <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(210px,1fr))", gap: 8, marginTop: 10 }}><label>正式记忆标识<input aria-label="memory-promote-id" value={memoryItemId} onChange={(event) => setMemoryItemId(event.target.value)} /></label><label>有效期（可选）<input aria-label="memory-promote-expires" type="datetime-local" value={memoryExpiresAt} onChange={(event) => setMemoryExpiresAt(event.target.value)} /></label><button type="button" className="btn primary" disabled={!!governanceBusy} onClick={() => void governCandidate("promote")}>晋升为正式记忆</button></div>}
                {governanceMessage && <div className="callout info" style={{ marginTop: 10 }}>{governanceMessage}</div>}
              </details>
            </>}
          </section>
        </div>
      )}

      {loadState === "loaded" && view === "memories" && <section style={panel}>
        <h2 style={{ marginTop: 0, fontSize: 17 }}>正式记忆</h2>
        {!memories.length ? (
          <div data-testid="memory-items-empty" className="callout info">
            <strong>空态策略：</strong>
            当前租户尚无正式记忆。冷启动或知识候选治理晋升完成后才会出现；不以知识库示例或本地种子数据冒充权威记忆。
          </div>
        ) : <><div style={{ display: "flex", gap: 8, alignItems: "end", marginBottom: 12 }}><label>撤销原因<select aria-label="memory-revocation-reason" value={revocationReason} onChange={(event) => setRevocationReason(event.target.value)}><option value="contamination_confirmed">确认知识污染</option><option value="source_withdrawn">来源已撤回</option><option value="applicability_changed">适用范围已变化</option><option value="manual_governance_revoke">人工治理撤销</option></select></label>{governanceMessage && <span className="muted">{governanceMessage}</span>}</div><div style={{ overflowX: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead><tr><th>主体</th><th>状态 / 范围</th><th>修订</th><th>来源</th><th>适用范围</th><th>有效期</th><th>治理</th></tr></thead>
          <tbody>{memories.map(({ item, revision }) => <tr key={item.memoryItemId}>
            <td>{memorySubjectTypeLabel(item.subject.resourceType)}{memoryLayerLabel(item.memoryLayer)}记忆<details><summary>审计标识</summary>{authoritySubjectLabel(item.subject)}<br />{item.memoryItemId}</details></td>
            <td>{memoryStatusLabel(item.status)} / {item.scope}</td><td>r{revision.revision}<details><summary>内容摘要</summary><code>{revision.contentHash}</code></details></td>
            <td>{revision.sourceId} · r{revision.sourceRevision}</td><td>{revision.applicability.join("、")}</td><td>{new Date(revision.effectiveAt).toLocaleString()}{revision.expiresAt ? ` → ${new Date(revision.expiresAt).toLocaleString()}` : " · 长期有效"}</td>
            <td><button type="button" className="btn" disabled={item.status !== "active" || governanceBusy === `revoke:${item.memoryItemId}`} onClick={() => void revokeMemory({ item, revision })}>{governanceBusy === `revoke:${item.memoryItemId}` ? "提交中…" : "撤销/污染处置"}</button></td>
          </tr>)}</tbody>
        </table></div></>}
      </section>}

      {loadState === "loaded" && view === "agents" && <AgentMemoryPanel memories={memories} />}

      {view === "query" && <section style={panel}>
        <h2 style={{ marginTop: 0, fontSize: 17 }}>知识检索</h2>
        <p className="muted">请求只描述业务主体与任务；组织、工作区和最终数据标记权限由当前认证身份决定。</p>
        <div data-testid="memory-contribution-context" className="callout info" style={{ marginBottom: 14 }}>
          <strong>工作台贡献上下文</strong>
          <div style={{ marginTop: 6, overflowWrap: "anywhere" }}>
            原子 Skill：{skillId || "待指定"} → Logic 编排：{contributionContext.logicId || "未绑定"} → 数字同事：{contributionContext.coworkerId || "未绑定"} → 工作台模块：{contributionContext.moduleId || "通用治理视图"}
          </div>
          <div className="muted" style={{ marginTop: 4 }}>
            此处只消费精确引用并展示贡献；MemoryCandidate 提交、评测、批准和晋升仍由服务端权威链裁决。
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
          <label>主体类型<input value={subjectType} onChange={(event) => setSubjectType(event.target.value)} aria-label="memory-subject-type" /></label>
          <label>主体 ID<input value={subjectId} onChange={(event) => setSubjectId(event.target.value)} aria-label="memory-subject-id" placeholder="真实 Object ID" /></label>
          <label>任务标识<input value={taskId} onChange={(event) => setTaskId(event.target.value)} aria-label="memory-task-id" placeholder="输入权威任务标识" /></label>
          <label>技能 ID<input value={skillId} onChange={(event) => setSkillId(event.target.value)} aria-label="memory-skill-id" placeholder="例如 content.strategy" /></label>
          <label>请求 markings<input value={markings} onChange={(event) => setMarkings(event.target.value)} aria-label="memory-markings" /></label>
        </div>
        <button type="button" className="btn primary" style={{ marginTop: 14 }} onClick={() => void runKnowledgeQuery()} disabled={queryState === "loading"}>{queryState === "loading" ? "检索中…" : "执行权威检索"}</button>
        {queryState === "idle" && !queryError && <div data-testid="memory-query-idle" className="callout info" style={{ marginTop: 14 }}>填写真实任务、技能和主体后检索；页面不会在未查询时展示示例结果。</div>}
        {queryState === "error" && <div data-testid="memory-query-error" className="callout warning" style={{ marginTop: 14 }}>知识检索失败：{queryError}</div>}
        {queryError && queryState === "idle" && <div className="callout warning" style={{ marginTop: 14 }}>{queryError}</div>}
        {queryResult && <div data-testid={`memory-query-${queryResult.status}`} className={`callout ${queryResult.status === "complete" ? "info" : "warning"}`} style={{ marginTop: 14 }}>
          状态：{memoryStatusLabel(queryResult.status)} · {queryResult.citations.length} 条来源引用 · {queryResult.assembledTokens} 个模型用量单位
          {queryResult.blockedReasons.length ? ` · 原因：${queryResult.blockedReasons.join("、")}` : ""}
        </div>}
        {queryResult?.chunks.map((chunk) => <article key={`${chunk.citation.memoryItemId}:${chunk.citation.revision}`} style={{ ...panel, marginTop: 12 }}>
          <strong>{authoritySubjectLabel(chunk.citation.subject)}</strong> · {chunk.citation.scope} · r{chunk.citation.revision}
          <p style={{ whiteSpace: "pre-wrap" }}>{chunk.content}</p>
          <div className="muted">来源：{chunk.citation.source.provider} · hash {chunk.citation.contentHash.slice(0, 12)}… · freshness {memoryStatusLabel(chunk.citation.freshness)}</div>
        </article>)}
      </section>}

      {view === "pipelines" && <section data-testid="memory-pipelines" style={panel}>
        <h2 style={{ marginTop: 0, fontSize: 17 }}>七条知识管道控制面</h2>
        <p className="muted">这里只展示权威计划、运行、凭证、检查点与告警。外部知识必须经可信适配器生成记忆候选项；本页不直连外部系统，也不把供应商检查点当作正式记忆。</p>
        {pipelineLoadState === "loading" && <div data-testid="pipeline-loading" className="callout info">正在读取知识管道权威状态…</div>}
        {pipelineLoadState === "error" && <div data-testid="pipeline-error" className="callout warning">知识管道读取失败：{pipelineError}</div>}
        {pipelineError && pipelineLoadState !== "error" && <div className="callout warning">{pipelineError}</div>}
        {pipelineLoadState === "loaded" && <>
          {!pipelinePolicies.length ? <div className="callout warning">服务端未返回冻结的管道策略；为避免把未知配置当作可运行状态，所有操作已失败关闭。</div> : <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 12 }}>
            {pipelinePolicies.map((policy) => {
              const schedules = pipelineSchedules.filter((item) => item.pipelineKind === policy.pipelineKind);
              const operational = pipelineReadiness?.pipelines.find((item) => item.pipelineKind === policy.pipelineKind);
              return <article key={policy.pipelineKind} style={{ border: "1px solid var(--aos-border)", borderRadius: 6, padding: 14 }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center" }}>
                  <strong>{pipelineKindLabels[policy.pipelineKind] || policy.pipelineKind}</strong>
                  <span className="tag" data-testid={`pipeline-operational-${policy.pipelineKind}`}>{operational ? memoryStatusLabel(operational.operationalStatus) : "权威未返回"}</span>
                </div>
                <div className="muted" style={{ marginTop: 5 }}>触发：{policy.allowedTriggers.join(" / ")} · 默认：{memoryStatusLabel(policy.defaultStatus)}</div>
                <div className="muted">必需依赖：{policy.requiredDependencies.join("、")}</div>
                {operational && <div data-testid={`pipeline-blockers-${policy.pipelineKind}`} style={{ marginTop: 8 }}>
                  <div className="muted">Schedule：{operational.scheduleCounts.map(item => `${memoryStatusLabel(item.status)} ${item.count}`).join(" / ") || "0"} · Run：{operational.runCounts.map(item => `${memoryStatusLabel(item.status)} ${item.count}`).join(" / ") || "0"} · Alert：{operational.alertCount}</div>
                  <div className="muted">Adapter：{operational.adapterRequired ? (operational.adapterRegistered ? "已注册" : "未注册") : "不要求"} · 最近 Receipt：{operational.lastReceipt ? memoryStatusLabel(operational.lastReceipt.status) : "无"}</div>
                  {!!operational.blockerCodes.length && <div className="callout warning" style={{ marginTop: 8, padding: 8 }}>阻断：{operational.blockerCodes.join("、")}</div>}
                </div>}
                {!schedules.length ? <div style={{ marginTop: 10 }}>
                  <span className="tag">未注册 Schedule</span>
                  <button type="button" className="btn" style={{ marginTop: 8, width: "100%" }} disabled title="需管理员提交带精确 revision/hash 的权威 config Artifact">等待权威配置</button>
                  <small className="muted">需管理员提交精确 config Artifact；页面不会临时拼装配置或伪造就绪状态。</small>
                </div> : schedules.map((schedule) => <div key={schedule.scheduleId} data-testid={`pipeline-schedule-${schedule.scheduleId}`} style={{ marginTop: 10, borderTop: "1px solid var(--aos-border)", paddingTop: 10 }}>
                  <div><span className="tag">{memoryStatusLabel(schedule.status)}</span> · {schedule.scheduleId} · v{schedule.version}</div>
                  <div className="muted">checkpoint v{schedule.checkpointVersion}{schedule.nextRunAt ? ` · 下次 ${new Date(schedule.nextRunAt).toLocaleString()}` : ""}</div>
                  <button type="button" className="btn" style={{ marginTop: 8 }} onClick={() => void transitionSchedule(schedule)} disabled={busyScheduleId === schedule.scheduleId}>
                    {busyScheduleId === schedule.scheduleId ? "提交中…" : schedule.status === "active" ? "暂停" : schedule.status === "paused" ? "尝试启用" : "恢复为暂停"}
                  </button>
                  {schedule.status !== "active" && <small className="muted" style={{ display: "block", marginTop: 5 }}>启用/恢复会由服务端重新核验依赖快照；未知或过期依赖将返回阻断，不会前端放行。</small>}
                </div>)}
              </article>;
            })}
          </div>}

          <h3 style={{ fontSize: 16, marginTop: 22 }}>最近运行</h3>
          {!pipelineRuns.length ? <div data-testid="pipeline-runs-empty" className="callout info">当前组织没有权威知识管道运行；未以示例运行填充页面。</div> : <div style={{ overflowX: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead><tr><th>运行</th><th>计划</th><th>状态</th><th>任务 / 运行</th><th>计划时间</th><th>证据</th></tr></thead>
            <tbody>{pipelineRuns.map((run) => <tr key={run.pipelineRunId}>
              <td>{run.pipelineRunId}<br /><span className="muted">attempt {run.attempt} · v{run.version}</span></td>
              <td>{run.scheduleId}</td><td>{memoryStatusLabel(run.status)}</td><td>{run.taskId}<br />{run.runId}</td><td>{new Date(run.scheduledFor).toLocaleString()}</td>
              <td><button type="button" className="btn" onClick={() => void inspectPipelineRun(run)}>查看证据</button></td>
            </tr>)}</tbody>
          </table></div>}

          {selectedRun && <div data-testid="pipeline-run-evidence" style={{ ...panel, marginTop: 16 }}>
            <strong>{selectedRun.pipelineRunId} 权威证据</strong>
            <dl style={{ display: "grid", gridTemplateColumns: "140px 1fr", gap: "6px 12px" }}>
              <dt>Receipt</dt><dd>{selectedReceipt ? `${selectedReceipt.receiptId} · ${memoryStatusLabel(selectedReceipt.status)} · 产出 ${selectedReceipt.producedCount}` : "尚未生成"}</dd>
              <dt>Checkpoint</dt><dd>{selectedCheckpoint ? `r${selectedCheckpoint.revision} · ${selectedCheckpoint.checkpoint.artifactId}` : "尚未推进"}</dd>
              <dt>Alert</dt><dd>{selectedAlerts.length ? selectedAlerts.map((alert) => `${alert.severity}:${alert.code}`).join("、") : "无"}</dd>
            </dl>
          </div>}
        </>}
      </section>}

      {view === "readiness" && <section data-testid="memory-readiness" style={panel}>
        <h2 style={{ marginTop: 0, fontSize: 17 }}>知识冷启动与检索就绪度</h2>
        <p className="muted">只读展示当前组织与工作区的真实权威状态；缺少 package/Eval registry 时明确显示权威缺口，不以 0 或示例数据代替。</p>
        {readinessState === "loading" && <div className="callout info">正在读取知识就绪度…</div>}
        {readinessState === "error" && <div data-testid="readiness-error" className="callout warning">知识就绪度读取失败：{readinessError}</div>}
        {readiness && <>
          <div className="callout info">租户：{readiness.tenant.orgId} / {readiness.tenant.projectId} · 观测时间：{new Date(readiness.observedAt).toLocaleString()}</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: 12, marginTop: 14 }}>
            <article style={panel}><strong>知识包安装权威</strong><p>{readiness.package.status === "available" ? `${readiness.package.count} 个` : "权威映射尚未建立"}</p><span className="muted" style={blockerText}>{readiness.package.blocker || "无阻断"}</span></article>
            <article style={panel}><strong>知识 Source</strong><p>{readiness.sources.length} 组来源策略</p><span className="muted" style={blockerText}>{readiness.sourceBlockers.join("、") || "已读取真实来源"}</span></article>
            <article style={panel}><strong>检索 Reference</strong><p>{readiness.search.referenceCount} 条</p><span className="muted">fulltext provider：{readiness.search.providerConfigured ? "capability 已确认" : "未就绪"}</span></article>
            <article style={panel}><strong>检索 Eval</strong><p>{readiness.eval.status === "available" ? `${readiness.eval.count} 条 Gold` : "GoldSet 权威尚未建立"}</p><span className="muted" style={blockerText}>{readiness.eval.blocker || "无阻断"}</span></article>
          </div>
          <h3 style={{ fontSize: 16, marginTop: 22 }}>检索通道</h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(180px, 1fr))", gap: 12 }}>
            {readiness.search.capabilities.map((item) => <article key={item.lane} style={panel}><strong>{item.lane}</strong><p><span className="tag">{memoryStatusLabel(item.status)}</span></p><span className="muted" style={blockerText}>{item.provider ? `${item.provider} · ${item.providerRevision}` : item.reasonCode}</span></article>)}
          </div>
          {!!readiness.sources.length && <><h3 style={{ fontSize: 16, marginTop: 22 }}>来源与使用政策</h3>{readiness.sources.map((source) => <article key={`${source.provider}:${source.providerVersion}:${source.licenseId}:${source.usagePolicy}`} style={{ borderTop: "1px solid var(--aos-border)", padding: "10px 0" }}><strong>{source.provider} · {source.providerVersion}</strong><div>license：{source.licenseId} · usage：{source.usagePolicy}</div><span className="muted">revision {source.revisionCount} · stale {source.staleCount}</span></article>)}</>}
          {!!readiness.search.blockers.length && <div data-testid="readiness-blockers" className="callout warning" style={{ marginTop: 14 }}>当前阻断：{readiness.search.blockers.join("、")}</div>}
        </>}
      </section>}
    </PageChrome>
  );
}

function AgentMemoryPanel({ memories }: { memories: MemoryAuthorityItem[] }) {
  const [instances, setInstances] = useState<MemoryAgentInstance[]>([]);
  const [projections, setProjections] = useState<MemoryAgentProjection[]>([]);
  const [exposures, setExposures] = useState<MemoryExposure[]>([]);
  const [observations, setObservations] = useState<MemoryImprovementObservation[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [kind, setKind] = useState<"personal" | "shared">("personal");
  const [memoryId, setMemoryId] = useState("");
  const [recipientId, setRecipientId] = useState("");
  const [purpose, setPurpose] = useState("skill:content");
  const [busy, setBusy] = useState("");
  const [impact, setImpact] = useState<MemoryRevocationImpact | null>(null);

  async function reloadAgentMemory() {
    setState("loading"); setError(""); setImpact(null);
    try {
      const [nextInstances, nextProjections, nextExposures, nextObservations] = await Promise.all([
        aipMemorySdk.agentInstances(), aipMemorySdk.agentProjections(), aipMemorySdk.memoryExposures(), aipMemorySdk.improvementObservations(),
      ]);
      setInstances(nextInstances); setProjections(nextProjections); setExposures(nextExposures); setObservations(nextObservations);
      const instanceIds = nextInstances.map((item) => item.instanceId);
      const activeIds = nextInstances.filter((item) => item.status === "active").map((item) => item.instanceId);
      setSelectedId((current) => instanceIds.includes(current) ? current : activeIds[0] || instanceIds[0] || "");
      setRecipientId((current) => activeIds.includes(current) ? current : "");
      setState("loaded");
    } catch (caught) {
      setInstances([]); setProjections([]); setExposures([]); setObservations([]);
      setError(String((caught as Error).message || caught)); setState("error");
    }
  }
  useEffect(() => { void reloadAgentMemory(); }, []);

  const activeInstances = instances.filter((item) => item.status === "active");
  const selected = instances.find((item) => item.instanceId === selectedId);
  const selectedMemory = memories.find((item) => item.item.memoryItemId === memoryId && item.item.status === "active");
  const recipient = activeInstances.find((item) => item.instanceId === recipientId && item.instanceId !== selectedId);
  const selectedProjections = projections.filter((item) => item.ownerInstanceRef.assetId === selectedId || item.recipientInstanceRefs.some((ref) => ref.assetId === selectedId));
  const personal = selectedProjections.filter((item) => item.kind === "personal");
  const shared = selectedProjections.filter((item) => item.kind === "shared");
  const selectedExposures = exposures.filter((item) => item.agentInstanceRef.assetId === selectedId);
  const selectedObservations = observations.filter((item) => item.agentInstanceRef.assetId === selectedId);
  const disabledReason = !selected ? "当前租户没有真实数字同事实例" : selected.status !== "active" ? `当前实例状态为 ${selected.status}，尚不可创建记忆投影` : !selectedMemory ? "请选择当前租户的生效 Memory exact revision" : kind === "shared" && !recipient ? "共享必须选择另一位生效中的真实接收实例" : !purpose.trim() ? "必须填写用途 allowlist" : "";

  async function createProjection() {
    if (disabledReason || !selected || !selectedMemory) return;
    const now = new Date(); const expires = new Date(now.getTime() + 90 * 24 * 60 * 60 * 1000);
    const projectionId = `ui-${crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}`}`; setBusy("create"); setError("");
    try {
      await aipMemorySdk.createAgentProjection({ projectionId, kind, ownerInstanceRef: selected.instanceRef, memoryRef: { memoryItemId: selectedMemory.item.memoryItemId, revision: selectedMemory.revision.revision, contentHash: selectedMemory.revision.contentHash }, recipientInstanceRefs: kind === "shared" && recipient ? [recipient.instanceRef] : [], allowedPurposes: [purpose.trim()], allowedMarkings: selectedMemory.revision.markings, disclosure: "citation_only", effectiveAt: now.toISOString(), expiresAt: expires.toISOString() }, projectionId);
      await reloadAgentMemory();
    } catch (caught) { setError(`创建/共享被权威服务阻断：${String((caught as Error).message || caught)}`); }
    finally { setBusy(""); }
  }
  async function revokeProjection(projection: MemoryAgentProjection) {
    setBusy(projection.projectionRef.projectionId); setError("");
    try {
      const reasonHash = await sha256("memory-governance-ui-revoke");
      await aipMemorySdk.revokeAgentProjection(projection, reasonHash, `revoke-${projection.projectionRef.projectionId}-${projection.projectionRef.version}`);
      await reloadAgentMemory();
    } catch (caught) { setError(`撤回被权威服务阻断：${String((caught as Error).message || caught)}`); }
    finally { setBusy(""); }
  }
  async function loadImpact(projection: MemoryAgentProjection) {
    setBusy(`impact:${projection.projectionRef.projectionId}`); setError(""); setImpact(null);
    try { setImpact(await aipMemorySdk.agentProjectionImpact(projection.projectionRef.projectionId, new Date().toISOString())); }
    catch (caught) { setError(`撤回影响读取失败：${String((caught as Error).message || caught)}`); }
    finally { setBusy(""); }
  }

  return <section data-testid="agent-memory-panel" style={panel}>
    <h2 style={{ marginTop: 0, fontSize: 17 }}>数字同事个人记忆与共享投影</h2>
    <p className="muted">投影只保存 exact Memory citation 与授权范围，不复制正文；实例、状态、版本和改进事实均来自当前租户权威 API。</p>
    {state === "loading" && <div data-testid="agent-memory-loading" className="callout info">正在读取真实数字同事实例、投影、Exposure 与 Observation…</div>}
    {state === "error" && <div data-testid="agent-memory-error" className="callout warning">数字同事记忆读取失败：{error}</div>}
    {state === "loaded" && <>
      {!instances.length ? <div data-testid="agent-memory-empty" className="callout info">当前租户没有真实数字同事实例；不以六角色静态卡片或测试组织数据替代。</div> : <>
        {!activeInstances.length && <div data-testid="agent-memory-no-active" className="callout warning">当前租户有 {instances.length} 个真实数字同事实例，但尚无 active 实例；页面展示权威状态并禁用投影写操作。</div>}
        <div style={{ display: "flex", gap: 12, alignItems: "end", flexWrap: "wrap" }}>
          <label>数字同事实例<select aria-label="agent-memory-instance" value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>{instances.map((item) => <option key={item.instanceId} value={item.instanceId}>{item.overlay.displayName || item.instanceId} · {memoryStatusLabel(item.status)}</option>)}</select></label>
          {selected && <div className="callout info">{selected.tenant.orgId} / {selected.tenant.projectId} · {selected.instanceId} · v{selected.version} · {memoryStatusLabel(selected.status)}<br /><code>{selected.instanceRef.contentHash.slice(0, 12)}…</code></div>}
          <button type="button" className="btn" onClick={() => void reloadAgentMemory()}>刷新数字同事记忆</button>
        </div>

        <div style={{ ...panel, marginTop: 14 }}>
          <strong>创建引用投影</strong>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 10, marginTop: 10 }}>
            <label>类型<select aria-label="agent-memory-kind" value={kind} onChange={(event) => setKind(event.target.value as "personal" | "shared")}><option value="personal">个人记忆</option><option value="shared">显式共享</option></select></label>
            <label>正式 Memory<select aria-label="agent-memory-authority" value={memoryId} onChange={(event) => setMemoryId(event.target.value)}><option value="">请选择</option>{memories.filter((item) => item.item.status === "active").map((item) => <option key={item.item.memoryItemId} value={item.item.memoryItemId}>{item.item.memoryItemId} · r{item.revision.revision}</option>)}</select></label>
            {kind === "shared" && <label>接收实例<select aria-label="agent-memory-recipient" value={recipientId} onChange={(event) => setRecipientId(event.target.value)}><option value="">请选择</option>{activeInstances.filter((item) => item.instanceId !== selectedId).map((item) => <option key={item.instanceId} value={item.instanceId}>{item.overlay.displayName || item.instanceId} · v{item.version}</option>)}</select></label>}
            <label>允许用途<input aria-label="agent-memory-purpose" value={purpose} onChange={(event) => setPurpose(event.target.value)} /></label>
          </div>
          <button type="button" className="btn primary" style={{ marginTop: 10 }} disabled={!!disabledReason || busy === "create"} title={disabledReason} onClick={() => void createProjection()}>{busy === "create" ? "提交中…" : kind === "personal" ? "创建个人引用" : "显式共享引用"}</button>
          {disabledReason && <small data-testid="agent-memory-create-blocker" className="muted" style={{ display: "block", marginTop: 6 }}>{disabledReason}</small>}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: 14, marginTop: 14 }}>
          <ProjectionColumn title="个人记忆" items={personal} selectedId={selectedId} busy={busy} onImpact={loadImpact} onRevoke={revokeProjection} />
          <ProjectionColumn title="共享记忆" items={shared} selectedId={selectedId} busy={busy} onImpact={loadImpact} onRevoke={revokeProjection} />
        </div>
        {impact && <div data-testid="agent-memory-impact" className="callout info" style={{ marginTop: 14 }}>撤回影响：recipient {impact.recipientCount} · Exposure {impact.exposureCount} · AgentRun {impact.affectedAgentRunCount} · 重评估 {impact.reEvaluationStatus}{impact.blockerCodes.length ? ` · ${impact.blockerCodes.join("、")}` : ""}</div>}

        <h3 style={{ fontSize: 16, marginTop: 22 }}>改进度量</h3>
        {!selectedObservations.length ? <div data-testid="agent-memory-observations-empty" className="callout info">当前实例没有权威 Observation；不以 0 或“已提升”替代未知。</div> : selectedObservations.map((item) => <article key={item.observationId} style={{ borderTop: "1px solid var(--aos-border)", padding: "10px 0" }}>
          <strong>{item.quality === "unknown" ? "证据不足（unknown）· 不可判定提升" : `${item.quality} · ${item.conclusion}`}</strong>
          <div className="muted">{item.observationId} · {new Date(item.observedAt).toLocaleString()} · Exposure ref {item.exposureRefs.length}</div>
          {item.metrics.map((metric) => <div key={metric.metricName}>{metric.metricName}：baseline {(metric.baselineValue * 100).toFixed(1)}% / treatment {(metric.treatmentValue * 100).toFixed(1)}% · n={metric.baselineSampleSize}/{metric.treatmentSampleSize}</div>)}
          {!!item.limitations.length && <div className="muted">限制：{item.limitations.join("、")}</div>}
        </article>)}

        <h3 style={{ fontSize: 16, marginTop: 22 }}>最近接受的引用</h3>
        {!selectedExposures.length ? <div className="callout info">当前实例没有 Memory Exposure；页面不会创建或模拟使用记录。</div> : selectedExposures.map((item) => <div key={item.exposureId} style={{ borderTop: "1px solid var(--aos-border)", padding: "8px 0" }}>{item.memoryRef.memoryItemId} · r{item.memoryRef.revision} · AgentRun {item.agentRunRef.resourceId} · Skill {item.skillRef.assetId}<br /><span className="muted">accepted {new Date(item.acceptedAt).toLocaleString()} · hash {item.exposureHash.slice(0, 12)}…</span></div>)}
      </>}
      {error && <div className="callout warning" style={{ marginTop: 14 }}>{error}</div>}
    </>}
  </section>;
}

function ProjectionColumn({ title, items, selectedId, busy, onImpact, onRevoke }: { title: string; items: MemoryAgentProjection[]; selectedId: string; busy: string; onImpact: (item: MemoryAgentProjection) => Promise<void>; onRevoke: (item: MemoryAgentProjection) => Promise<void> }) {
  return <section style={panel}><h3 style={{ marginTop: 0, fontSize: 16 }}>{title}（{items.length}）</h3>{!items.length ? <div className="muted">没有真实投影。</div> : items.map((item) => {
    const direction = item.ownerInstanceRef.assetId === selectedId ? "我创建" : "共享给我";
    const blocker = item.status === "stale" ? "Memory/实例 exact ref 已漂移" : item.status === "revoked" ? "投影已撤回，仅保留历史审计" : item.status === "expired" ? "授权有效期已结束" : item.status === "suspended" ? "投影已暂停" : "";
    return <article key={item.projectionRef.projectionId} data-testid={`agent-projection-${item.projectionRef.projectionId}`} style={{ borderTop: "1px solid var(--aos-border)", padding: "10px 0" }}>
      <strong>{item.memoryRef.memoryItemId} · r{item.memoryRef.revision}</strong> <span className="tag">{memoryStatusLabel(item.status)}</span>
      <div>{direction} · owner {item.ownerInstanceRef.assetId} · recipient {item.recipientInstanceRefs.map((ref) => ref.assetId).join("、") || "无"}</div>
      <div className="muted">marking {item.allowedMarkings.join("、")} · applicability {item.allowedPurposes.join("、")} · {item.disclosure}</div>
      <div className="muted">有效 {new Date(item.effectiveAt).toLocaleString()} → {new Date(item.expiresAt).toLocaleString()} · v{item.projectionRef.version} · {item.projectionRef.contentHash.slice(0, 12)}…</div>
      {blocker && <div className="callout warning" style={{ marginTop: 6 }}>{blocker}</div>}
      <div style={{ display: "flex", gap: 8, marginTop: 8 }}><button type="button" className="btn" onClick={() => void onImpact(item)} disabled={busy === `impact:${item.projectionRef.projectionId}`}>查看撤回影响</button><button type="button" className="btn" onClick={() => void onRevoke(item)} disabled={!(["active", "suspended"] as string[]).includes(item.status) || busy === item.projectionRef.projectionId} title={!(["active", "suspended"] as string[]).includes(item.status) ? "当前状态不可撤回" : "提交真实撤回 API"}>撤回</button></div>
    </article>;
  })}</section>;
}

async function sha256(value: string): Promise<string> {
  const bytes = new TextEncoder().encode(value); const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest)).map((byte) => byte.toString(16).padStart(2, "0")).join("");
}
