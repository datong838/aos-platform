import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { aipMemorySdk, type KnowledgeQueryResult, type MemoryAuthorityItem, type MemoryCandidate, type MemoryCandidateEvent } from "../../api/aipMemory";
import { PageChrome } from "../../components/PageChrome";

type View = "candidates" | "memories" | "query";
type LoadState = "loading" | "loaded" | "error";

const panel = { border: "1px solid var(--aos-border)", background: "var(--aos-panel)", borderRadius: 6, padding: 18 } as const;
const statusLabels: Record<string, string> = {
  pending: "待治理", quarantined: "已隔离", rejected: "已拒绝", approved: "已批准", promoted: "已晋升",
  active: "生效中", stale: "已过期", revoked: "已撤销", expired: "已失效",
  complete: "完整", degraded: "降级回源", blocked: "已阻断",
};

export function memoryStatusLabel(status: string): string {
  return statusLabels[status] || status;
}

export function authoritySubjectLabel(subject: { resourceType: string; resourceId: string }): string {
  return `${subject.resourceType} · ${subject.resourceId}`;
}

export function MemoryGovernancePage() {
  const [view, setView] = useState<View>("candidates");
  const [candidates, setCandidates] = useState<MemoryCandidate[]>([]);
  const [memories, setMemories] = useState<MemoryAuthorityItem[]>([]);
  const [events, setEvents] = useState<MemoryCandidateEvent[]>([]);
  const [selectedCandidate, setSelectedCandidate] = useState<MemoryCandidate | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [error, setError] = useState("");
  const [subjectType, setSubjectType] = useState("Product");
  const [subjectId, setSubjectId] = useState("");
  const [taskId, setTaskId] = useState("");
  const [skillId, setSkillId] = useState("");
  const [markings, setMarkings] = useState("internal");
  const [queryState, setQueryState] = useState<"idle" | "loading" | "complete" | "degraded" | "blocked" | "error">("idle");
  const [queryResult, setQueryResult] = useState<KnowledgeQueryResult | null>(null);
  const [queryError, setQueryError] = useState("");

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

  useEffect(() => { void reload(); }, []);

  async function inspectCandidate(candidate: MemoryCandidate) {
    setSelectedCandidate(candidate);
    setEvents([]);
    setError("");
    try {
      setEvents(await aipMemorySdk.candidateEvents(candidate.candidateId));
    } catch (caught) {
      setError(`Candidate 事件读取失败：${String((caught as Error).message || caught)}`);
    }
  }

  async function runKnowledgeQuery() {
    const required = [subjectType, subjectId, taskId, skillId].map((value) => value.trim());
    if (required.some((value) => !value)) {
      setQueryError("请完整填写主体类型、主体 ID、Task ID 和 Skill ID。");
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
        subject: { resourceType: required[0], resourceId: required[1] },
        taskId: required[2],
        skillRef: { resourceType: "Skill", resourceId: required[3] },
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
    <PageChrome title="Memory Governance" lede="Candidate → 审批证据 → 正式 Memory → 带 Citation 的 Knowledge Query。所有状态来自 PostgreSQL 权威链，不回填示例知识。">
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 16 }}>
        {(["candidates", "memories", "query"] as const).map((item) => (
          <button key={item} type="button" className={`btn ${view === item ? "primary" : ""}`} onClick={() => setView(item)} data-testid={`memory-tab-${item}`}>
            {item === "candidates" ? `知识候选（${candidates.length}）` : item === "memories" ? `正式 Memory（${memories.length}）` : "Knowledge Query"}
          </button>
        ))}
        <button type="button" className="btn" onClick={() => void reload()} disabled={loadState === "loading"}>{loadState === "loading" ? "读取中…" : "刷新权威状态"}</button>
        <Link to="/ontology/wiki" className="btn-nav">活知识 Wiki →</Link>
      </div>

      {loadState === "loading" && <div data-testid="memory-loading" className="callout info">正在读取租户隔离的 Memory authority…</div>}
      {loadState === "error" && <div data-testid="memory-error" className="callout warning">Memory authority 读取失败：{error}</div>}
      {error && loadState !== "error" && <div className="callout warning">{error}</div>}

      {loadState === "loaded" && view === "candidates" && (
        <div style={{ display: "grid", gridTemplateColumns: "minmax(320px, 1fr) minmax(360px, 1.2fr)", gap: 16, alignItems: "start" }}>
          <section style={panel}>
            <h2 style={{ marginTop: 0, fontSize: 17 }}>知识候选</h2>
            {!candidates.length ? <div data-testid="memory-candidates-empty" className="callout info">当前租户没有待治理或历史 Candidate；页面未注入静态候选。</div> : candidates.map((candidate) => (
              <button key={candidate.candidateId} type="button" className="btn" onClick={() => void inspectCandidate(candidate)} style={{ width: "100%", display: "grid", textAlign: "left", gap: 5, marginBottom: 8, padding: 12 }}>
                <strong>{authoritySubjectLabel(candidate.request.subject)}</strong>
                <span>{memoryStatusLabel(candidate.status)} · {candidate.scope} · v{candidate.version}</span>
                <span className="muted">{candidate.candidateId}</span>
              </button>
            ))}
          </section>
          <section style={panel}>
            <h2 style={{ marginTop: 0, fontSize: 17 }}>治理证据与事件</h2>
            {!selectedCandidate ? <div className="muted">选择 Candidate 查看精确 payload hash、来源、新鲜度、适用范围及不可变事件。</div> : <>
              <dl style={{ display: "grid", gridTemplateColumns: "150px 1fr", gap: "8px 12px", margin: 0 }}>
                <dt>租户</dt><dd>{selectedCandidate.tenant.orgId} / {selectedCandidate.tenant.projectId}</dd>
                <dt>Payload</dt><dd>{selectedCandidate.request.payload.resourceId} · {selectedCandidate.request.payload.revision}<br /><code>{selectedCandidate.request.payload.contentHash}</code></dd>
                <dt>来源</dt><dd>{selectedCandidate.request.source.provider} · {selectedCandidate.request.source.sourceKind}</dd>
                <dt>Freshness</dt><dd>{new Date(selectedCandidate.request.source.freshnessExpiresAt).toLocaleString()}</dd>
                <dt>Applicability</dt><dd>{selectedCandidate.request.source.applicability.join("、")}</dd>
                <dt>隔离原因</dt><dd>{selectedCandidate.quarantineReasons.join("、") || "无"}</dd>
              </dl>
              <h3 style={{ fontSize: 15 }}>事件时间线</h3>
              {!events.length ? <div className="muted">暂无可见事件，或事件仍在读取。</div> : events.map((event) => <div key={event.eventId} style={{ borderTop: "1px solid var(--aos-border)", padding: "10px 0" }}>
                <strong>#{event.sequence} {memoryStatusLabel(event.toStatus)}</strong> · {event.actor}<br /><span className="muted">{new Date(event.occurredAt).toLocaleString()} · {event.reasonCodes.join("、") || "无原因码"}</span>
              </div>)}
              <div className="callout info" style={{ marginTop: 12 }}>批准/晋升必须绑定精确 Eval report、Draft 与 ApprovalEvent；本页不会用不完整表单绕过治理服务。</div>
            </>}
          </section>
        </div>
      )}

      {loadState === "loaded" && view === "memories" && <section style={panel}>
        <h2 style={{ marginTop: 0, fontSize: 17 }}>正式 Memory authority</h2>
        {!memories.length ? <div data-testid="memory-items-empty" className="callout info">当前租户尚无正式 Memory；冷启动或治理晋升完成后才会出现，不以 Wiki 示例替代。</div> : <div style={{ overflowX: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead><tr><th>主体</th><th>状态 / Scope</th><th>Revision</th><th>来源</th><th>适用范围</th><th>生效时间</th></tr></thead>
          <tbody>{memories.map(({ item, revision }) => <tr key={item.memoryItemId}>
            <td>{authoritySubjectLabel(item.subject)}<br /><span className="muted">{item.memoryItemId}</span></td>
            <td>{memoryStatusLabel(item.status)} / {item.scope}</td><td>r{revision.revision}<br /><code>{revision.contentHash.slice(0, 12)}…</code></td>
            <td>{revision.sourceId} · r{revision.sourceRevision}</td><td>{revision.applicability.join("、")}</td><td>{new Date(revision.effectiveAt).toLocaleString()}</td>
          </tr>)}</tbody>
        </table></div>}
      </section>}

      {view === "query" && <section style={panel}>
        <h2 style={{ marginTop: 0, fontSize: 17 }}>Knowledge Query</h2>
        <p className="muted">请求只描述业务主体与任务；组织、工作区和最终授权 markings 由认证 Principal 决定。</p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
          <label>主体类型<input value={subjectType} onChange={(event) => setSubjectType(event.target.value)} aria-label="memory-subject-type" /></label>
          <label>主体 ID<input value={subjectId} onChange={(event) => setSubjectId(event.target.value)} aria-label="memory-subject-id" placeholder="真实 Object ID" /></label>
          <label>Task ID<input value={taskId} onChange={(event) => setTaskId(event.target.value)} aria-label="memory-task-id" placeholder="权威 Task ID" /></label>
          <label>Skill ID<input value={skillId} onChange={(event) => setSkillId(event.target.value)} aria-label="memory-skill-id" placeholder="例如 content.strategy" /></label>
          <label>请求 markings<input value={markings} onChange={(event) => setMarkings(event.target.value)} aria-label="memory-markings" /></label>
        </div>
        <button type="button" className="btn primary" style={{ marginTop: 14 }} onClick={() => void runKnowledgeQuery()} disabled={queryState === "loading"}>{queryState === "loading" ? "检索中…" : "执行权威检索"}</button>
        {queryState === "idle" && !queryError && <div data-testid="memory-query-idle" className="callout info" style={{ marginTop: 14 }}>填写真实 Task、Skill 和主体后检索；页面不会在未查询时展示示例结果。</div>}
        {queryState === "error" && <div data-testid="memory-query-error" className="callout warning" style={{ marginTop: 14 }}>Knowledge Query 失败：{queryError}</div>}
        {queryError && queryState === "idle" && <div className="callout warning" style={{ marginTop: 14 }}>{queryError}</div>}
        {queryResult && <div data-testid={`memory-query-${queryResult.status}`} className={`callout ${queryResult.status === "complete" ? "info" : "warning"}`} style={{ marginTop: 14 }}>
          状态：{memoryStatusLabel(queryResult.status)} · {queryResult.citations.length} 条 Citation · {queryResult.assembledTokens} tokens
          {queryResult.blockedReasons.length ? ` · 原因：${queryResult.blockedReasons.join("、")}` : ""}
        </div>}
        {queryResult?.chunks.map((chunk) => <article key={`${chunk.citation.memoryItemId}:${chunk.citation.revision}`} style={{ ...panel, marginTop: 12 }}>
          <strong>{authoritySubjectLabel(chunk.citation.subject)}</strong> · {chunk.citation.scope} · r{chunk.citation.revision}
          <p style={{ whiteSpace: "pre-wrap" }}>{chunk.content}</p>
          <div className="muted">来源：{chunk.citation.source.provider} · hash {chunk.citation.contentHash.slice(0, 12)}… · freshness {memoryStatusLabel(chunk.citation.freshness)}</div>
        </article>)}
      </section>}
    </PageChrome>
  );
}
