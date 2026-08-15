import { useMemo, useRef, useState } from "react";
import { PageChrome } from "../../components/PageChrome";
import { queryAnalyst, type AnalystQuery, type QueryResultRevision, type ResourceRef } from "../../api/aipWorkbench";

type View = "table" | "chart" | "map" | "raw";
type QueryKind = AnalystQuery["kind"];

function refFromSearch(search: URLSearchParams, prefix: string): ResourceRef | null {
  const resourceType = search.get(`${prefix}Type`), resourceId = search.get(`${prefix}Id`), revision = search.get(`${prefix}Revision`), authority = search.get(`${prefix}Authority`);
  return resourceType && resourceId && revision && authority ? { resourceType, resourceId, revision, authority } : null;
}

export function buildGovernedQuery(input: { kind: QueryKind; objectType: string; prompt: string; cutoffAt: string; taskRef: ResourceRef | null; skillRef: ResourceRef | null; metricRef: ResourceRef | null }): AnalystQuery | null {
  if (input.kind === "semantic") return input.objectType.trim() ? { kind: "semantic", objectType: input.objectType.trim(), filters: [], sort: [], selectionRefs: [], pageSize: 50, cutoffAt: input.cutoffAt } : null;
  if (input.kind === "knowledge") return input.prompt.trim().length >= 2 && input.taskRef && input.skillRef ? { kind: "knowledge", query: input.prompt.trim(), taskRef: input.taskRef, skillRef: input.skillRef, selectionRefs: [], markings: ["public"], maxTokens: 2048, cutoffAt: input.cutoffAt } : null;
  if (!input.metricRef) return null;
  const end = new Date(input.cutoffAt), start = new Date(end.getTime() - 86_400_000);
  return { kind: "metric", metricRef: input.metricRef, dimensions: [], filters: [], selectionRefs: [], windowStart: start.toISOString(), windowEnd: end.toISOString(), cutoffAt: input.cutoffAt };
}

function disabledReason(kind: QueryKind, objectType: string, prompt: string, task: ResourceRef | null, skill: ResourceRef | null, metric: ResourceRef | null): string | null {
  if (kind === "semantic" && !objectType.trim()) return "请选择真实 Object Type";
  if (kind === "knowledge" && (!task || !skill)) return "需要上游传入 exact Task 与 Skill refs";
  if (kind === "knowledge" && prompt.trim().length < 2) return "请输入至少 2 个字符的知识问题";
  if (kind === "metric" && !metric) return "需要上游传入 exact MetricDefinition ref";
  return null;
}

function ResultBody({ result, view }: { result: QueryResultRevision; view: View }) {
  if (result.status === "blocked") return <Empty title="查询被权威门阻断" text="页面不会生成替代数据；请查看右侧 blocker。" />;
  if (result.status === "empty") return <Empty title="真实查询返回空结果" text="来源已确认，当前截点无匹配记录。" />;
  if (view === "raw") return <pre style={raw}>{JSON.stringify(result, null, 2)}</pre>;
  if (view === "chart") {
    const numeric = result.columns.find((column) => column.valueType === "number");
    if (!numeric) return <Empty title="图表不适用" text="当前 Result revision 没有数值列。" />;
    const values = result.rows.map((row) => Number(row.values[numeric.key] ?? 0)), max = Math.max(1, ...values);
    return <div style={{ display: "flex", gap: 12, alignItems: "end", height: 300, padding: 24 }}>{values.map((value, index) => <div key={result.rows[index].rowId} title={String(value)} style={{ width: 34, minHeight: 2, height: `${value / max * 100}%`, background: "#2563eb", borderRadius: "6px 6px 0 0" }} />)}</div>;
  }
  if (view === "map") {
    const lat = result.columns.some((column) => /(^|_)lat(itude)?$/i.test(column.key)), lng = result.columns.some((column) => /(^|_)(lng|lon|longitude)$/i.test(column.key));
    return lat && lng ? <Empty title={`已识别 ${result.rows.length} 个地理对象`} text="地图底图 authority 未装配；不伪造位置。" /> : <Empty title="地图不适用" text="当前 Result revision 没有经纬度列。" />;
  }
  return <div style={{ overflow: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse" }}><thead><tr><th style={cell}>对象</th>{result.columns.map((column) => <th key={column.key} style={cell}>{column.label}</th>)}</tr></thead><tbody>{result.rows.map((row) => <tr key={row.rowId}><td style={cell}>{row.rowId}</td>{result.columns.map((column) => <td key={column.key} style={cell}>{String(row.values[column.key] ?? "—")}</td>)}</tr>)}</tbody></table></div>;
}

function Evidence({ result }: { result: QueryResultRevision | null }) {
  if (!result) return <p style={muted}>运行受治理查询后显示来源、血缘、截点与不确定性。</p>;
  return <div style={{ display: "grid", gap: 12, fontSize: 13 }}><Fact label="结果修订" value={`${result.queryId} · r${result.revision}`} /><Fact label="状态" value={result.status} /><Fact label="截点" value={new Date(result.cutoffAt).toLocaleString()} /><Fact label="内容哈希" value={result.contentHash.slice(0, 16)} /><section><strong>来源</strong>{result.sourceRefs.length ? result.sourceRefs.map((source) => <div key={`${source.ref.resourceId}:${source.ref.revision}`} style={smallCard}>{source.ref.resourceType}/{source.ref.resourceId}@{source.ref.revision}<br />{source.freshness} · {new Date(source.cutoffAt).toLocaleString()}</div>) : <p style={muted}>无来源（blocked 允许）</p>}</section>{result.uncertainties.length > 0 && <section><strong>不确定性</strong><ul>{result.uncertainties.map((item) => <li key={item}>{item}</li>)}</ul></section>}{result.blockers.map((item) => <div key={item.code} style={{ ...smallCard, borderColor: "#f59e0b" }}><strong>{item.code}</strong><br />{item.message}<br />{item.retryable ? "可重试" : "需先解决依赖"}</div>)}</div>;
}
function Empty({ title, text }: { title: string; text: string }) { return <div style={empty}><h3>{title}</h3><p>{text}</p></div>; }
function Fact({ label, value }: { label: string; value: string }) { return <div><strong>{label}</strong><div style={muted}>{value}</div></div>; }

export function AipAnalystPage({ runQuery = queryAnalyst }: { runQuery?: typeof queryAnalyst } = {}) {
  const search = useMemo(() => new URLSearchParams(window.location.search), []), taskRef = refFromSearch(search, "task"), skillRef = refFromSearch(search, "skill"), metricRef = refFromSearch(search, "metric");
  const [kind, setKind] = useState<QueryKind>("semantic"), [objectType, setObjectType] = useState(search.get("objectType") || "Order"), [prompt, setPrompt] = useState(""), [result, setResult] = useState<QueryResultRevision | null>(null), [view, setView] = useState<View>("table");
  const [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null), [focus, setFocus] = useState(false), [leftOpen, setLeftOpen] = useState(true), [rightOpen, setRightOpen] = useState(true);
  const inFlight = useRef(false);
  const disabled = disabledReason(kind, objectType, prompt, taskRef, skillRef, metricRef);
  async function run() { const query = buildGovernedQuery({ kind, objectType, prompt, cutoffAt: new Date().toISOString(), taskRef, skillRef, metricRef }); if (!query || inFlight.current) return; inFlight.current = true; setBusy(true); setError(null); setResult(null); try { setResult(await runQuery(query)); } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); } finally { inFlight.current = false; setBusy(false); } }
  return <PageChrome title="AIP 分析师" lede="受治理语义 / 知识 / 指标查询 · 单一 Result revision · 不生成演示数据"><div style={{ display: "flex", gap: 8, marginBottom: 12 }}><button type="button" aria-expanded={leftOpen} onClick={() => setLeftOpen((v) => !v)}>{leftOpen ? "收起查询" : "展开查询"}</button><button type="button" aria-expanded={rightOpen} onClick={() => setRightOpen((v) => !v)}>{rightOpen ? "收起证据" : "展开证据"}</button><button type="button" aria-pressed={focus} onClick={() => setFocus((v) => !v)}>{focus ? "退出专注" : "Focus Mode"}</button></div><div style={{ display: "grid", gridTemplateColumns: `${focus || !leftOpen ? "0" : "280px"} minmax(0,1fr) ${focus || !rightOpen ? "0" : "320px"}`, gap: 16, minHeight: 620 }}><aside style={{ ...panel, overflow: "hidden", display: focus || !leftOpen ? "none" : "block" }}><h3>查询构造器</h3><label style={label}>查询类型<select value={kind} onChange={(e) => setKind(e.target.value as QueryKind)} style={input}><option value="semantic">语义对象</option><option value="knowledge">行业知识</option><option value="metric">权威指标</option></select></label>{kind === "semantic" && <label style={label}>Object Type<select value={objectType} onChange={(e) => setObjectType(e.target.value)} style={input}><option value="Order">订单</option><option value="Product">商品</option><option value="CustomerLite">客户</option><option value="Payment">支付</option><option value="Shipment">发货</option></select></label>}{kind === "knowledge" && <label style={label}>知识问题<textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} style={{ ...input, minHeight: 100 }} /></label>}<button type="button" onClick={() => void run()} disabled={Boolean(disabled) || busy} title={disabled || undefined} style={{ ...primary, opacity: disabled || busy ? .5 : 1 }}>{busy ? "查询中…" : "运行真实查询"}</button>{disabled && <p style={warning}>{disabled}</p>}<p style={muted}>不接受任意 SQL；租户由登录 Principal 决定。</p></aside><main style={panel}>{error && <div role="alert" style={warning}>请求失败：{error}。未生成本地结果。</div>}<div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}><div>{(["table", "chart", "map", "raw"] as View[]).map((item) => <button type="button" key={item} onClick={() => setView(item)} style={view === item ? primary : undefined}>{({ table: "表格", chart: "图表", map: "地图", raw: "Raw" } as const)[item]}</button>)}</div>{result && <strong>{result.status} · {result.rows.length} 行 · r{result.revision}</strong>}</div>{result ? <ResultBody result={result} view={view} /> : <Empty title="尚未运行查询" text="选择治理查询类型后读取真实 authority；服务不可用时保持失败关闭。" />}</main><aside style={{ ...panel, overflow: "auto", display: focus || !rightOpen ? "none" : "block" }}><h3>证据详情</h3><Evidence result={result} /></aside></div></PageChrome>;
}

const panel = { background: "var(--color-surface, #fff)", border: "1px solid var(--color-border, #dbe2ea)", borderRadius: 10, padding: 18 }, label = { display: "grid", gap: 6, marginBottom: 16, fontWeight: 600 }, input = { width: "100%", padding: "9px 10px", border: "1px solid #cbd5e1", borderRadius: 7, background: "transparent", color: "inherit" }, primary = { background: "#2563eb", color: "white", border: 0, borderRadius: 7, padding: "9px 14px" }, muted = { color: "var(--color-text-muted, #64748b)", overflowWrap: "anywhere" as const }, warning = { padding: 10, color: "#92400e", background: "#fffbeb", border: "1px solid #f59e0b", borderRadius: 7 }, empty = { display: "grid", placeContent: "center", textAlign: "center" as const, minHeight: 360, color: "#64748b" }, smallCard = { padding: 9, marginTop: 7, border: "1px solid #dbe2ea", borderRadius: 7, overflowWrap: "anywhere" as const }, cell = { borderBottom: "1px solid #e2e8f0", textAlign: "left" as const, padding: "10px 12px", whiteSpace: "nowrap" as const }, raw = { maxHeight: 520, overflow: "auto", background: "#0f172a", color: "#e2e8f0", padding: 16, borderRadius: 8, fontSize: 12 };
