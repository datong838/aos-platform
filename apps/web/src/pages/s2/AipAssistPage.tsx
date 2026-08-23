import { useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import { PageChrome } from "../../components/PageChrome";
import { cancelAssistTaskRun, createAssistThread, newIdempotencyKey, streamAssistTurn, type AssistEvent, type AssistSubject, type AssistThread, type ResourceRef, type TaskRunControlResult } from "../../api/aipWorkbench";

function ref(search: URLSearchParams, prefix: string, expectedType: string): ResourceRef | null {
  const resourceId = search.get(`${prefix}Id`), revision = search.get(`${prefix}Revision`), authority = search.get(`${prefix}Authority`);
  return resourceId && revision && authority ? { resourceType: expectedType, resourceId, revision, authority } : null;
}
export function subjectFromSearch(search: URLSearchParams): AssistSubject | null {
  const taskRef = ref(search, "task", "Task"), taskRunRef = ref(search, "taskRun", "TaskRun"), agentRunRef = ref(search, "agentRun", "AgentRun"), cutoffAt = search.get("cutoffAt");
  if (!taskRef || !taskRunRef || !agentRunRef || !cutoffAt || Number.isNaN(Date.parse(cutoffAt))) return null;
  return { taskRef, taskRunRef, agentRunRef, selectionRefs: [], cutoffAt };
}

function EventCard({ event }: { event: AssistEvent }) {
  if (event.eventType === "start") return <div style={system}>已受理 Turn · sequence {event.sequence}</div>;
  if (event.eventType === "context") return <div style={system}><strong>权威上下文已冻结</strong><br />context {event.context?.contextHash.slice(0, 16)} · cutoff {event.context && new Date(event.context.cutoffAt).toLocaleString()}</div>;
  if (event.eventType === "delta") return <div style={answer}>{event.content}</div>;
  if (event.eventType === "proposal") return <div style={system}>提案引用：{event.proposalRef?.resourceType}/{event.proposalRef?.resourceId}@{event.proposalRef?.revision}</div>;
  if (event.eventType === "done") return <div style={system}>完成 · usage {event.usageRefs.length} · lineage {event.lineageRefs.length}</div>;
  return <div style={blocked}><strong>{event.blocker?.code || event.eventType.toUpperCase()}</strong><br />{event.blocker?.message || "运行时返回错误"}<br />{event.blocker?.retryable ? "依赖恢复后可创建新 Turn" : "需先解决权威依赖"}</div>;
}

type AssistPageClient = {
  createThread: typeof createAssistThread;
  streamTurn: typeof streamAssistTurn;
  cancelTaskRun: typeof cancelAssistTaskRun;
  newKey: typeof newIdempotencyKey;
};
const defaultClient: AssistPageClient = { createThread: createAssistThread, streamTurn: streamAssistTurn, cancelTaskRun: cancelAssistTaskRun, newKey: newIdempotencyKey };
function positiveRevision(value: string): number | null { const parsed = Number(value); return Number.isInteger(parsed) && parsed > 0 ? parsed : null; }
function activateToggle(event: KeyboardEvent<HTMLButtonElement>, action: () => void) { if (event.key !== "Enter" && event.key !== " ") return; event.preventDefault(); action(); }

export function AipAssistPage({ client = defaultClient }: { client?: AssistPageClient } = {}) {
  const search = useMemo(() => new URLSearchParams(window.location.search), []), subject = useMemo(() => subjectFromSearch(search), [search]);
  const [thread, setThread] = useState<AssistThread | null>(null), [events, setEvents] = useState<AssistEvent[]>([]), [message, setMessage] = useState(""), [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null), [focus, setFocus] = useState(false), [contextOpen, setContextOpen] = useState(true), [cancelResult, setCancelResult] = useState<TaskRunControlResult | null>(null), [cancelling, setCancelling] = useState(false);
  const pending = useRef<{ message: string; threadKey: string; turnKey: string } | null>(null), cancelKey = useRef<string | null>(null), sendInFlight = useRef(false), cancelInFlight = useRef(false);
  const taskVersion = subject ? positiveRevision(subject.taskRef.revision) : null, runVersion = subject ? positiveRevision(subject.taskRunRef.revision) : null;
  const cancelDisabled = !subject ? "缺少精确运行上下文" : !taskVersion || !runVersion ? "任务或任务运行的版本不可用于并发安全校验" : null;
  async function ensureThread(threadKey: string): Promise<AssistThread> { if (thread) return thread; if (!subject) throw new Error("缺少精确的任务、任务运行、智能体运行与数据截止时间"); const created = await client.createThread({ ...subject, title: "AIP 助手工作线程" }, threadKey); setThread(created); return created; }
  async function submit(event: FormEvent) { event.preventDefault(); const clean = message.trim(); if (clean.length < 2 || sendInFlight.current || !subject) return; sendInFlight.current = true; const request = pending.current?.message === clean ? pending.current : { message: clean, threadKey: client.newKey(), turnKey: client.newKey() }; pending.current = request; setBusy(true); setError(null); setEvents([]); try { const active = await ensureThread(request.threadKey); setEvents(await client.streamTurn(active.threadId, { message: clean, expectedThreadVersion: active.version, cutoffAt: active.subject.cutoffAt }, request.turnKey)); setThread({ ...active, version: active.version + 1 }); setMessage(""); pending.current = null; } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); } finally { sendInFlight.current = false; setBusy(false); } }
  async function cancel() { if (!subject || !taskVersion || !runVersion || cancelInFlight.current || cancelResult) return; cancelInFlight.current = true; const key = cancelKey.current || client.newKey(); cancelKey.current = key; setCancelling(true); setError(null); try { const result = await client.cancelTaskRun(subject.taskRunRef.resourceId, { expectedRunVersion: runVersion, expectedTaskVersion: taskVersion, reason: "AIP Assist 用户取消" }, key); setCancelResult(result); cancelKey.current = null; } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); } finally { cancelInFlight.current = false; setCancelling(false); } }
  const taskRunLineagePath = subject
    ? `/aip/lineage?rootType=task_run&rootId=${encodeURIComponent(subject.taskRunRef.resourceId)}`
    : null;
  return <PageChrome title="AIP 助手" lede="围绕真实任务持续对话，并保留可审计的服务端事件；缺少运行上下文时明确关闭输入。">
    <div data-testid="assist-ops-stats" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(110px,1fr))", gap: 10, marginBottom: 12 }}>
      {[
        { label: "上下文", value: subject ? "已绑定" : "缺失" },
        { label: "对话线程", value: thread ? "已建立" : "未建立" },
        { label: "事件数", value: String(events.length) },
        { label: "侧栏", value: focus || !contextOpen ? "收起" : "展开" },
        { label: "取消任务", value: cancelResult ? "已取消" : cancelDisabled ? "不可用" : "可取消" },
        { label: "输入", value: !subject ? "禁用" : busy ? "运行中" : "可发" },
      ].map((s) => (
        <div key={s.label} className="card" style={{ padding: "10px 12px" }}>
          <div style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>{s.label}</div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>{s.value}</div>
        </div>
      ))}
    </div>
    <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}><button type="button" aria-expanded={contextOpen} onClick={() => setContextOpen((v) => !v)} onKeyDown={(event) => activateToggle(event, () => setContextOpen((v) => !v))}>{contextOpen ? "收起上下文" : "展开上下文"}</button><button type="button" aria-pressed={focus} onClick={() => setFocus((v) => !v)} onKeyDown={(event) => activateToggle(event, () => setFocus((v) => !v))}>{focus ? "退出专注" : "专注模式"}</button><button type="button" onClick={() => void cancel()} disabled={Boolean(cancelDisabled) || cancelling || Boolean(cancelResult)} title={cancelDisabled || undefined}>{cancelling ? "取消中…" : cancelResult ? `已取消运行 ${cancelResult.run.id}` : "取消任务运行"}</button>{taskRunLineagePath ? <Link to={taskRunLineagePath} data-testid="assist-jump-lineage" style={ctaLink}>当前任务运行的谱系与可观测信息 →</Link> : <span data-testid="assist-lineage-blocked" title="缺少精确任务运行引用，不能猜测谱系标识" style={muted}>缺少任务运行引用，暂不能查看谱系</span>}</div><div style={{ display: "grid", gridTemplateColumns: `${focus || !contextOpen ? "0" : "320px"} minmax(0,1fr)`, gap: 16, minHeight: 620 }}><aside style={{ ...panel, display: focus || !contextOpen ? "none" : "block", overflow: "hidden" }}><h3>运行上下文</h3>{subject ? <div style={{ display: "grid", gap: 12 }}><RefFact label="任务" value={subject.taskRef} /><RefFact label="任务运行" value={subject.taskRunRef} /><RefFact label="智能体运行" value={subject.agentRunRef} /><div><strong>数据截止时间</strong><p style={muted}>{new Date(subject.cutoffAt).toLocaleString()}</p></div>{thread && <details><summary>对话线程技术标识（审计用）</summary><p style={muted}>{thread.threadId} · 版本 {thread.version}</p></details>}{cancelResult && <div role="status" style={system}>任务运行已取消 · 版本 {cancelResult.run.version}</div>}</div> : <div style={blocked} data-testid="assist-no-subject"><strong>尚无可执行上下文</strong><p>请从真实任务或智能体运行工作流进入。页面不会创建默认测试智能体，也不会猜测缺失引用。</p><div style={{ display: "flex", flexWrap: "wrap", gap: 8, margin: "10px 0" }}><Link to="/aip/agents" data-testid="assist-cta-agents" style={ctaLink}>智能体列表</Link><Link to="/aip/logic" data-testid="assist-cta-logic" style={ctaLink}>业务逻辑编排</Link><Link to="/aip/agent-registry" data-testid="assist-cta-registry" style={ctaLink}>智能体目录</Link><Link to="/aip/observability" data-testid="assist-cta-observability" style={ctaLink}>可观测性</Link></div><details><summary>所需技术引用（审计用）</summary><code>taskId + taskRevision + taskAuthority<br />taskRunId + taskRunRevision + taskRunAuthority<br />agentRunId + agentRunRevision + agentRunAuthority + cutoffAt</code></details></div>}</aside><main style={{ ...panel, display: "grid", gridTemplateRows: "1fr auto", gap: 16 }}><section style={{ overflow: "auto", display: "grid", alignContent: "start", gap: 10 }}>{!events.length && !error && <div style={empty}><h3>{subject ? "准备创建权威对话线程" : "等待上游上下文"}</h3><p>{subject ? "发送问题后只展示服务端已持久化事件。" : "缺少精确引用时输入和发送保持禁用。可先从智能体列表或业务逻辑编排进入真实工作流。"}</p>{!subject && <p style={{ marginTop: 8 }}><Link to="/aip/agents" style={ctaLink}>打开智能体列表</Link></p>}</div>}{error && <div role="alert" style={blocked}><strong>请求失败</strong><br />{error}<br />未生成本地回答。</div>}{events.map((item) => <EventCard key={`${item.turnId}:${item.sequence}`} event={item} />)}</section><form onSubmit={(event) => void submit(event)} style={{ display: "flex", gap: 10 }}><input aria-label="向当前智能体运行提问" value={message} onChange={(event) => setMessage(event.target.value)} disabled={!subject || busy} placeholder={subject ? "向当前智能体提问…" : "请先从真实任务进入"} style={input} /><button type="submit" disabled={!subject || busy || message.trim().length < 2} title={!subject ? "缺少精确运行上下文" : undefined} style={{ ...primary, opacity: !subject || busy || message.trim().length < 2 ? .5 : 1 }}>{busy ? "运行中…" : "发送"}</button></form></main></div></PageChrome>;
}
function RefFact({ label, value }: { label: string; value: ResourceRef }) { return <div><strong>{label}</strong><p style={muted}>{value.resourceId}@{value.revision}<br />{value.authority}</p></div>; }
const panel = { background: "var(--aos-surface, #fff)", border: "1px solid var(--aos-border, #dbe2ea)", borderRadius: 10, padding: 18 }, muted = { color: "var(--aos-text-secondary, #64748b)", overflowWrap: "anywhere" as const }, input = { flex: 1, padding: "12px 14px", border: "1px solid var(--aos-border, #cbd5e1)", borderRadius: 8, background: "var(--aos-surface, transparent)", color: "inherit" }, primary = { background: "var(--aos-accent, #2563eb)", color: "white", border: 0, borderRadius: 8, padding: "10px 18px" }, empty = { display: "grid", placeContent: "center", textAlign: "center" as const, minHeight: 360, color: "var(--aos-text-secondary, #64748b)" }, system = { padding: 10, color: "var(--aos-text-secondary, #475569)", background: "var(--aos-surface-hover, #f8fafc)", border: "1px solid var(--aos-border, #e2e8f0)", borderRadius: 8, overflowWrap: "anywhere" as const }, answer = { padding: 14, background: "var(--aos-accent-light, #eff6ff)", border: "1px solid var(--aos-accent-border, #bfdbfe)", borderRadius: 8, whiteSpace: "pre-wrap" as const }, blocked = { padding: 12, color: "var(--aos-amber, #92400e)", background: "var(--aos-amber-bg, #fffbeb)", border: "1px solid var(--aos-amber-border, #f59e0b)", borderRadius: 8, overflowWrap: "anywhere" as const }, ctaLink = { display: "inline-block", padding: "6px 10px", borderRadius: 6, background: "var(--aos-accent, #2563eb)", color: "#fff", textDecoration: "none", fontSize: 13 };
