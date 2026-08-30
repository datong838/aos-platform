import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import { apiGet } from "../../api/client";
import { createExploration, listExplorations, type ExplorationAsset } from "../../api/ontologyExplorationAssets";
import type { ExplorationCreate } from "../../api/ontologyExplorerContracts";
import { PageChrome } from "../../components/PageChrome";
import { businessDisplayName, objectTypeDisplayName, statusDisplayName } from "../../lib/aipChineseLabels";
import {
  listAnalystRoleQueryTemplates,
  queryAnalyst,
  templateBlockingReason,
  type AnalystQuery,
  type AnalystRoleQueryTemplate,
  type AnalystRoleQueryTemplateList,
  type QueryResultRevision,
  type ResourceRef,
} from "../../api/aipWorkbench";
import { readExactRef } from "../../lib/aipExactContext";

type View = "table" | "chart" | "map" | "raw";
type QueryKind = AnalystQuery["kind"];
type ObjectTypeOption = { id: string; name: string };
export type LogicGraphOption = { id: string; name: string; revision: number; graphHash: string };

async function defaultListObjectTypes(): Promise<ObjectTypeOption[]> {
  const payload = await apiGet<{ items?: Array<{ id?: string; name?: string; published?: boolean }> }>("/v1/ontology/object-types");
  return (payload.items || [])
    .filter((item) => typeof item.id === "string" && item.id.trim() && item.published !== false)
    .map((item) => ({ id: String(item.id).trim(), name: String(item.name || item.id).trim() }));
}

async function defaultListRoleTemplates(): Promise<AnalystRoleQueryTemplateList> {
  return listAnalystRoleQueryTemplates();
}

export async function defaultListLogicGraphs(): Promise<LogicGraphOption[]> {
  const payload = await apiGet<{
    items?: Array<{ id?: string; name?: string; revision?: number; graph_hash?: string; persisted?: boolean }>;
  }>("/v1/aip/logic/graphs");
  return (payload.items || [])
    .filter((item) => (
      item.persisted !== false
      && typeof item.id === "string"
      && item.id.trim()
      && typeof item.revision === "number"
      && item.revision > 0
      && typeof item.graph_hash === "string"
      && item.graph_hash.trim()
    ))
    .map((item) => ({
      id: String(item.id).trim(),
      name: businessDisplayName(String(item.name || item.id).trim()),
      revision: Number(item.revision),
      graphHash: String(item.graph_hash).trim(),
    }));
}

export function matchLogicMount(
  graphs: LogicGraphOption[],
  preferred: { id: string; revision: string; hash: string },
): LogicGraphOption | null {
  if (!graphs.length) return null;
  const byExact = graphs.find((graph) => (
    graph.id === preferred.id
    && String(graph.revision) === preferred.revision
    && (!preferred.hash || graph.graphHash === preferred.hash)
  ));
  if (byExact) return byExact;
  const byId = preferred.id ? graphs.find((graph) => graph.id === preferred.id) : undefined;
  return byId || graphs[0] || null;
}

function syncLogicMountUrl(graph: LogicGraphOption | null) {
  const next = new URL(window.location.href);
  if (!graph) {
    next.searchParams.delete("logicId");
    next.searchParams.delete("logicRevision");
    next.searchParams.delete("logicHash");
  } else {
    next.searchParams.set("logicId", graph.id);
    next.searchParams.set("logicRevision", String(graph.revision));
    next.searchParams.set("logicHash", graph.graphHash);
  }
  window.history.replaceState({}, "", `${next.pathname}${next.search}${next.hash}`);
}

function activateToggle(event: KeyboardEvent<HTMLButtonElement>, action: () => void) {
  if (event.key !== "Enter" && event.key !== " ") return;
  event.preventDefault();
  action();
}

export function buildGovernedQuery(input: { kind: QueryKind; objectType: string; prompt: string; cutoffAt: string; taskRef: ResourceRef | null; skillRef: ResourceRef | null; metricRef: ResourceRef | null; filterField?: string; filterOperator?: "eq" | "neq" | "lt" | "lte" | "gt" | "gte" | "in" | "contains"; filterValue?: string; dimensions?: string[]; pageSize?: number }): AnalystQuery | null {
  const filters = input.filterField?.trim() && input.filterValue?.trim() ? [{ field: input.filterField.trim(), operator: input.filterOperator || "eq", value: input.filterValue.trim() }] : [];
  if (input.kind === "semantic") return input.objectType.trim() ? { kind: "semantic", objectType: input.objectType.trim(), filters, sort: [], selectionRefs: [], pageSize: input.pageSize || 50, cutoffAt: input.cutoffAt } : null;
  if (input.kind === "knowledge") return input.prompt.trim().length >= 2 && input.taskRef && input.skillRef ? { kind: "knowledge", query: input.prompt.trim(), taskRef: input.taskRef, skillRef: input.skillRef, selectionRefs: [], markings: ["public"], maxTokens: 2048, cutoffAt: input.cutoffAt } : null;
  if (!input.metricRef) return null;
  const end = new Date(input.cutoffAt), start = new Date(end.getTime() - 86_400_000);
  return { kind: "metric", metricRef: input.metricRef, dimensions: input.dimensions || [], filters, selectionRefs: [], windowStart: start.toISOString(), windowEnd: end.toISOString(), cutoffAt: input.cutoffAt };
}

const BUSINESS_LABEL_KEYS = /(^|_)(name|title|subject|order_no|order_sn|product_name|goods_name|customer_name|nickname|mobile_masked|status_label)$/i;
const TECHNICAL_ID_KEYS = /(^|_)(id|uuid|hash|ref|revision)$|(?:Id|Uuid|Hash|Ref|Revision)$/;
const GENERIC_STATE_KEYS = /(^|_)(status|state|enabled|active)$/i;

export function businessRowLabel(row: QueryResultRevision["rows"][number], columns: QueryResultRevision["columns"], objectLabel = "业务记录"): string {
  const preferred = columns.find((column) => BUSINESS_LABEL_KEYS.test(column.key) && row.values[column.key] != null);
  const fallback = columns.find((column) => column.valueType === "string" && !TECHNICAL_ID_KEYS.test(column.key) && !GENERIC_STATE_KEYS.test(column.key) && row.values[column.key] != null);
  const value = row.values[(preferred || fallback)?.key || ""];
  if (value != null && String(value).trim()) return String(value);
  const suffix = row.rowId.split(":").at(-1)?.trim();
  return suffix ? `${objectLabel} ${suffix}` : objectLabel;
}

export function summarizeResult(result: QueryResultRevision, question: string): { summary: string; comparison: string; assumptions: string[] } {
  const numeric = result.columns.filter((column) => column.valueType === "number");
  const values = numeric.flatMap((column) => result.rows.map((row) => Number(row.values[column.key])).filter(Number.isFinite));
  const comparison = values.length > 1 ? `当前结果中的数值范围为 ${Math.min(...values).toLocaleString()}～${Math.max(...values).toLocaleString()}；这是描述性比较，不代表因果关系。` : "当前结果不足以形成组间比较；页面不会补造趋势或因果结论。";
  return {
    summary: `${question.trim() || "本次经营查询"}共返回 ${result.rows.length} 条业务记录、${result.columns.length} 个字段，结果状态为${statusDisplayName(result.status)}。`,
    comparison,
    assumptions: ["结论仅覆盖当前租户、当前筛选和当前数据截止时间。", "相关性、排序或差异不等于归因，也不等于因果。"],
  };
}

function disabledReason(
  kind: QueryKind,
  objectType: string,
  prompt: string,
  task: ResourceRef | null,
  skill: ResourceRef | null,
  metric: ResourceRef | null,
  objectTypesReady: boolean,
  objectTypeCount: number,
): string | null {
  if (kind === "semantic" && !objectTypesReady) return "正在读取已安装 Object Type…";
  if (kind === "semantic" && objectTypeCount === 0) return "当前租户暂无已安装 Object Type；不生成演示类型";
  if (kind === "semantic" && !objectType.trim()) return "请选择真实 Object Type";
  if (kind === "knowledge" && (!task || !skill)) return "需要上游传入 exact Task 与 Skill refs";
  if (kind === "knowledge" && prompt.trim().length < 2) return "请输入至少 2 个字符的知识问题";
  if (kind === "metric" && !metric) return "需要上游传入 exact MetricDefinition ref";
  return null;
}

function ResultBody({ result, view, objectLabel }: { result: QueryResultRevision; view: View; objectLabel: string }) {
  if (result.status === "blocked") return <Empty title="当前条件不足，未生成查询结果" text="页面不会生成替代数据；请查看右侧的数据、权限与口径说明。" />;
  if (result.status === "empty") return <Empty title="真实查询返回空结果" text="来源已确认，当前截点无匹配记录。" />;
  if (view === "raw") return <pre style={raw}>{JSON.stringify(result, null, 2)}</pre>;
  if (view === "chart") {
    const numeric = result.columns.find((column) => column.valueType === "number");
    if (!numeric) return <Empty title="图表不适用" text="当前 Result revision 没有数值列。" />;
    const values = result.rows.map((row) => Number(row.values[numeric.key] ?? 0)), max = Math.max(1, ...values);
    return <div style={{ display: "flex", gap: 12, alignItems: "end", height: 300, padding: 24 }}>{values.map((value, index) => <div key={result.rows[index].rowId} title={String(value)} style={{ width: 34, minHeight: 2, height: `${value / max * 100}%`, background: "#2563eb", borderRadius: "6px 6px 0 0" }} />)}</div>;
  }
  if (view === "map") {
    const lat = result.columns.find((column) => /(^|_)lat(itude)?$/i.test(column.key)), lng = result.columns.find((column) => /(^|_)(lng|lon|longitude)$/i.test(column.key));
    if (!lat || !lng) return <Empty title="地图不适用" text="当前结果没有经纬度字段，可切换表格或图表继续分析。" />;
    const points = result.rows.flatMap((row) => { const latitude = Number(row.values[lat.key]), longitude = Number(row.values[lng.key]); return Number.isFinite(latitude) && Number.isFinite(longitude) ? [{ row, latitude, longitude }] : []; });
    if (!points.length) return <Empty title="地图没有可绘制位置" text="经纬度字段存在，但当前结果没有合法坐标。" />;
    const minLat = Math.min(...points.map((item) => item.latitude)), maxLat = Math.max(...points.map((item) => item.latitude)), minLng = Math.min(...points.map((item) => item.longitude)), maxLng = Math.max(...points.map((item) => item.longitude));
    return <div aria-label="同一查询修订的地理分布" style={{ position: "relative", minHeight: 360, borderRadius: 10, overflow: "hidden", background: "linear-gradient(135deg,#eff6ff,#ecfeff)", border: "1px solid var(--aos-border)" }}>
      <div style={{ position: "absolute", inset: 18, border: "1px dashed #93c5fd", backgroundImage: "linear-gradient(#bfdbfe55 1px, transparent 1px),linear-gradient(90deg,#bfdbfe55 1px, transparent 1px)", backgroundSize: "40px 40px" }} />
      {points.map(({ row, latitude, longitude }) => { const left = maxLng === minLng ? 50 : 8 + (longitude - minLng) / (maxLng - minLng) * 84, top = maxLat === minLat ? 50 : 92 - (latitude - minLat) / (maxLat - minLat) * 84; return <button key={row.rowId} type="button" title={`${businessRowLabel(row, result.columns, objectLabel)} · ${latitude}, ${longitude}`} style={{ position: "absolute", left: `${left}%`, top: `${top}%`, transform: "translate(-50%,-50%)", width: 18, height: 18, padding: 0, borderRadius: "50%", border: "3px solid #fff", background: "#2563eb", boxShadow: "0 2px 8px #1e3a8a55" }} />; })}
      <span style={{ position: "absolute", left: 18, bottom: 12, fontSize: 12, color: "#475569" }}>{points.length} 个经营对象 · 结果修订 {result.revision}</span>
    </div>;
  }
  const businessColumns = result.columns.filter((column) => !TECHNICAL_ID_KEYS.test(column.key));
  const technicalColumns = result.columns.filter((column) => TECHNICAL_ID_KEYS.test(column.key));
  return <div style={{ overflow: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse" }}><thead><tr><th style={cell}>业务对象</th>{businessColumns.map((column) => <th key={column.key} style={cell}>{column.label}</th>)}</tr></thead><tbody>{result.rows.map((row) => <tr key={row.rowId}><td style={{ ...cell, fontWeight: 600 }}>{businessRowLabel(row, result.columns, objectLabel)}<details style={{ fontWeight: 400, fontSize: 11 }}><summary>技术标识（审计用）</summary><code>{row.rowId}</code>{technicalColumns.map((column) => <div key={column.key}>{column.label}：<code>{String(row.values[column.key] ?? "—")}</code></div>)}</details></td>{businessColumns.map((column) => <td key={column.key} style={cell}>{String(row.values[column.key] ?? "—")}</td>)}</tr>)}</tbody></table></div>;
}

function Evidence({ result, logicMount }: { result: QueryResultRevision | null; logicMount: LogicGraphOption | null }) {
  return (
    <div style={{ display: "grid", gap: 12, fontSize: 13 }}>
      <section data-testid="analyst-logic-mount-evidence">
        <strong>业务逻辑挂载</strong>
        {logicMount ? (
          <div style={smallCard}>
            {businessDisplayName(logicMount.name)} · 修订 {logicMount.revision}
            <br />挂载不等于已执行；不会冒充任务图已生成。
            <details style={{ marginTop: 6 }}>
              <summary>技术标识（审计用）</summary>
              <code>LogicGraph/{logicMount.id}@{logicMount.revision}</code>
              <br /><code>{logicMount.graphHash.slice(0, 16)}…</code>
            </details>
          </div>
        ) : (
          <p style={muted}>未关联已保存业务逻辑；本次仅执行受控查询，不注入演示图。</p>
        )}
      </section>
      {!result && <p style={muted}>运行受治理查询后显示来源、血缘、截点与不确定性。</p>}
      {result && (
        <>
          <Fact label="结果修订" value={`修订 ${result.revision}`} />
          <Fact label="状态" value={statusDisplayName(result.status)} />
          <Fact label="截点" value={new Date(result.cutoffAt).toLocaleString()} />
          <Fact
            label="置信度"
            value={result.confidence.status === "measured"
              ? `${Math.round((result.confidence.score || 0) * 100)}% · ${result.confidence.basis.join("、")}`
              : `${result.confidence.status} · ${result.confidence.basis.join("、")}`}
          />
          <details><summary>结果技术标识（审计用）</summary><code>{result.queryId}</code><br /><code>{result.contentHash.slice(0, 16)}…</code></details>
          <section>
            <strong>来源与新鲜度（{result.sourceRefs.length}）</strong>
            <p style={muted}>{result.sourceRefs.length ? `新鲜 ${result.sourceRefs.filter((item) => item.freshness === "fresh").length} · 陈旧 ${result.sourceRefs.filter((item) => item.freshness === "stale").length} · 未知 ${result.sourceRefs.filter((item) => item.freshness === "unknown").length}` : "无来源（仅阻断状态允许）"}</p>
            {result.sourceRefs.length ? <details><summary>查看精确来源</summary>{result.sourceRefs.map((source) => (
              <div key={`${source.ref.resourceId}:${source.ref.revision}`} style={smallCard}>
                数据新鲜度：{statusDisplayName(source.freshness)} · {new Date(source.cutoffAt).toLocaleString()}
                <details><summary>来源技术标识（审计用）</summary><code>{source.ref.resourceType}/{source.ref.resourceId}@{source.ref.revision}</code></details>
              </div>
            ))}</details> : null}
          </section>
          <section>
            <strong>谱系（{result.lineageRefs.length}）</strong>
            {result.lineageRefs.length ? <details><summary>查看权威谱系引用</summary>{result.lineageRefs.map((ref) => (
              <div key={`${ref.resourceType}:${ref.resourceId}:${ref.revision}`} style={smallCard}>
                已记录权威血缘
                <details><summary>血缘技术标识（审计用）</summary><code>{ref.resourceType}/{ref.resourceId}@{ref.revision}</code><br /><code>{ref.authority}</code></details>
              </div>
            ))}</details> : <p style={muted}>当前查询未返回权威谱系引用；不以追踪标识或本地路径代替。</p>}
          </section>
          {result.uncertainties.length > 0 && (
            <section>
              <strong>不确定性</strong>
              <ul>{result.uncertainties.map((item) => <li key={item}>{item}</li>)}</ul>
            </section>
          )}
          {result.blockers.map((item) => (
            <div key={item.code} style={{ ...smallCard, borderColor: "#f59e0b" }}>
              <strong>{item.code}</strong>
              <br />
              {item.message}
              <br />
              {item.retryable ? "可重试" : "需先解决依赖"}
            </div>
          ))}
        </>
      )}
    </div>
  );
}
function Empty({ title, text }: { title: string; text: string }) { return <div style={empty}><h3>{title}</h3><p>{text}</p></div>; }
function Fact({ label, value }: { label: string; value: string }) { return <div><strong>{label}</strong><div style={muted}>{value}</div></div>; }

export function AipAnalystPage({
  runQuery = queryAnalyst,
  listObjectTypes = defaultListObjectTypes,
  listLogicGraphs = defaultListLogicGraphs,
  listRoleTemplates = defaultListRoleTemplates,
  listSaved = listExplorations,
  saveExploration = createExploration,
}: {
  runQuery?: typeof queryAnalyst;
  listObjectTypes?: () => Promise<ObjectTypeOption[]>;
  listLogicGraphs?: () => Promise<LogicGraphOption[]>;
  listRoleTemplates?: () => Promise<AnalystRoleQueryTemplateList>;
  listSaved?: () => Promise<ExplorationAsset[]>;
  saveExploration?: (payload: ExplorationCreate) => Promise<ExplorationAsset>;
} = {}) {
  const search = useMemo(() => new URLSearchParams(window.location.search), []);
  const taskRef = readExactRef(search, "task");
  const taskRunRef = readExactRef(search, "taskRun");
  const agentRunRef = readExactRef(search, "agentRun");
  const skillRef = readExactRef(search, "skill");
  const metricRef = readExactRef(search, "metric");
  const preferredType = search.get("objectType") || "";
  const preferredTemplateId = search.get("roleTemplateId") || "";
  const preferredLogic = {
    id: search.get("logicId") || "",
    revision: search.get("logicRevision") || "",
    hash: search.get("logicHash") || "",
  };
  const [kind, setKind] = useState<QueryKind>("semantic");
  const [objectType, setObjectType] = useState(preferredType);
  const [objectTypes, setObjectTypes] = useState<ObjectTypeOption[]>([]);
  const [objectTypesReady, setObjectTypesReady] = useState(false);
  const [objectTypesError, setObjectTypesError] = useState<string | null>(null);
  const [roleTemplates, setRoleTemplates] = useState<AnalystRoleQueryTemplate[]>([]);
  const [roleTemplatesReady, setRoleTemplatesReady] = useState(false);
  const [roleTemplatesError, setRoleTemplatesError] = useState<string | null>(null);
  const [roleTemplateHash, setRoleTemplateHash] = useState("");
  const [selectedTemplateId, setSelectedTemplateId] = useState(preferredTemplateId);
  const [logicGraphs, setLogicGraphs] = useState<LogicGraphOption[]>([]);
  const [logicReady, setLogicReady] = useState(false);
  const [logicError, setLogicError] = useState<string | null>(null);
  const [logicMountId, setLogicMountId] = useState(preferredLogic.id);
  const [prompt, setPrompt] = useState("");
  const [businessQuestion, setBusinessQuestion] = useState("哪些经营对象值得优先关注？");
  const [filterField, setFilterField] = useState("");
  const [filterOperator, setFilterOperator] = useState<"eq" | "neq" | "lt" | "lte" | "gt" | "gte" | "in" | "contains">("eq");
  const [filterValue, setFilterValue] = useState("");
  const [dimensions, setDimensions] = useState("");
  const [pageSize, setPageSize] = useState(50);
  const [cutoffAt, setCutoffAt] = useState(() => new Date().toISOString().slice(0, 16));
  const [result, setResult] = useState<QueryResultRevision | null>(null);
  const [lastQuery, setLastQuery] = useState<AnalystQuery | null>(null);
  const [saved, setSaved] = useState<ExplorationAsset[]>([]);
  const [explorationName, setExplorationName] = useState("经营分析探索");
  const [saveBusy, setSaveBusy] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [view, setView] = useState<View>("table");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [focus, setFocus] = useState(false);
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const inFlight = useRef(false);

  useEffect(() => { let active = true; void listSaved().then((items) => { if (active) setSaved(items); }).catch(() => { if (active) setSaved([]); }); return () => { active = false; }; }, [listSaved]);

  useEffect(() => {
    let cancelled = false;
    setObjectTypesReady(false);
    setObjectTypesError(null);
    void listObjectTypes()
      .then((items) => {
        if (cancelled) return;
        setObjectTypes(items);
        setObjectType((current) => {
          if (current && items.some((item) => item.id === current)) return current;
          if (preferredType && items.some((item) => item.id === preferredType)) return preferredType;
          return "";
        });
        setObjectTypesReady(true);
      })
      .catch((cause) => {
        if (cancelled) return;
        setObjectTypes([]);
        setObjectType("");
        setObjectTypesError(cause instanceof Error ? cause.message : String(cause));
        setObjectTypesReady(true);
      });
    return () => { cancelled = true; };
  }, [listObjectTypes, preferredType]);

  useEffect(() => {
    let cancelled = false;
    setRoleTemplatesReady(false);
    setRoleTemplatesError(null);
    void listRoleTemplates()
      .then((catalog) => {
        if (cancelled) return;
        setRoleTemplates(catalog.items);
        setRoleTemplateHash(catalog.contentHash);
        const selected = catalog.items.find((item) => item.templateId === preferredTemplateId) || catalog.items[0] || null;
        setSelectedTemplateId(selected?.templateId || "");
        if (selected) {
          setKind(selected.queryKind);
          setObjectType(selected.defaultObjectType || "");
          setPrompt(selected.defaultPrompt);
        }
        setRoleTemplatesReady(true);
      })
      .catch((cause) => {
        if (cancelled) return;
        setRoleTemplates([]);
        setSelectedTemplateId("");
        setRoleTemplateHash("");
        setRoleTemplatesError(cause instanceof Error ? cause.message : String(cause));
        setRoleTemplatesReady(true);
      });
    return () => { cancelled = true; };
  }, [listRoleTemplates, preferredTemplateId]);

  useEffect(() => {
    let cancelled = false;
    setLogicReady(false);
    setLogicError(null);
    void listLogicGraphs()
      .then((items) => {
        if (cancelled) return;
        setLogicGraphs(items);
        const matched = matchLogicMount(items, preferredLogic);
        setLogicMountId(matched?.id || "");
        syncLogicMountUrl(matched);
        setLogicReady(true);
      })
      .catch((cause) => {
        if (cancelled) return;
        setLogicGraphs([]);
        setLogicMountId("");
        syncLogicMountUrl(null);
        setLogicError(cause instanceof Error ? cause.message : String(cause));
        setLogicReady(true);
      });
    return () => { cancelled = true; };
    // preferredLogic fields are URL bootstrap only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [listLogicGraphs]);

  const logicMount = useMemo(
    () => logicGraphs.find((graph) => graph.id === logicMountId) || null,
    [logicGraphs, logicMountId],
  );

  const selectedTemplate = useMemo(
    () => roleTemplates.find((item) => item.templateId === selectedTemplateId) || null,
    [roleTemplates, selectedTemplateId],
  );

  const queryDisabled = disabledReason(
    kind,
    objectType,
    prompt,
    taskRef,
    skillRef,
    metricRef,
    objectTypesReady,
    objectTypes.length,
  );
  const templateDisabled = templateBlockingReason(selectedTemplate);
  const objectTypeDrift = kind === "semantic" && objectTypesReady && objectType
    && !objectTypes.some((item) => item.id === objectType)
    ? `模板要求的业务对象类型未出现在当前租户目录：${objectTypeDisplayName(objectType)}`
    : null;
  const cutoffTimestamp = new Date(cutoffAt).getTime();
  const cutoffError = !cutoffAt || Number.isNaN(cutoffTimestamp) ? "请选择有效的数据截止时间" : null;
  const disabled = queryDisabled || templateDisabled || objectTypeDrift || cutoffError;

  function selectRoleTemplate(template: AnalystRoleQueryTemplate) {
    setSelectedTemplateId(template.templateId);
    setKind(template.queryKind);
    setObjectType(template.defaultObjectType || "");
    setPrompt(template.defaultPrompt);
    setResult(null);
    setError(null);
    const next = new URL(window.location.href);
    next.searchParams.set("roleTemplateId", template.templateId);
    if (template.defaultObjectType) next.searchParams.set("objectType", template.defaultObjectType);
    window.history.replaceState({}, "", `${next.pathname}${next.search}${next.hash}`);
  }

  function useCustomQuery() {
    setSelectedTemplateId("");
    const next = new URL(window.location.href);
    next.searchParams.delete("roleTemplateId");
    window.history.replaceState({}, "", `${next.pathname}${next.search}${next.hash}`);
  }

  async function run() {
    if (cutoffError) {
      setError(cutoffError);
      return;
    }
    const exactCutoff = new Date(cutoffAt).toISOString();
    const query = buildGovernedQuery({
      kind,
      objectType,
      prompt,
      cutoffAt: exactCutoff,
      taskRef,
      skillRef,
      metricRef,
      filterField,
      filterOperator,
      filterValue,
      dimensions: dimensions.split(",").map((item) => item.trim()).filter(Boolean),
      pageSize,
    });
    if (!query || inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const next = await runQuery(query);
      setResult(next);
      setLastQuery(query);
      setSaveMessage("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  function applySaved(asset: ExplorationAsset) {
    const query = asset.payload.analystQuery as AnalystQuery | undefined;
    if (!query) return;
    setKind(query.kind);
    if (query.kind === "semantic") { setObjectType(query.objectType); setFilterField(query.filters[0]?.field || ""); setFilterOperator(query.filters[0]?.operator || "eq"); setFilterValue(String(query.filters[0]?.value ?? "")); setPageSize(query.pageSize); }
    if (query.kind === "knowledge") setPrompt(query.query);
    if (query.kind === "metric") { setDimensions(query.dimensions.join(",")); setFilterField(query.filters[0]?.field || ""); setFilterOperator(query.filters[0]?.operator || "eq"); setFilterValue(String(query.filters[0]?.value ?? "")); }
    setCutoffAt(query.cutoffAt.slice(0, 16));
    setBusinessQuestion(String(asset.payload.query.businessQuestion || asset.payload.name));
    setExplorationName(asset.payload.name);
    setLastQuery(query);
    setResult(null);
    setSaveMessage(`已复用“${asset.payload.name}”修订 ${asset.revision}；请运行查询获取当前截止面的新结果。`);
  }

  async function saveCurrentExploration() {
    if (!result || !lastQuery || saveBusy || result.status === "blocked") return;
    setSaveBusy(true); setSaveMessage("");
    try {
      const created = await saveExploration({
        name: explorationName.trim() || "经营分析探索",
        objectType: lastQuery.kind === "semantic" ? lastQuery.objectType : lastQuery.kind === "metric" ? "Metric" : "Knowledge",
        viewMode: "table",
        visibility: "private",
        query: { businessQuestion: businessQuestion.trim(), queryKind: lastQuery.kind },
        columns: result.columns.map((column) => ({ key: column.key, label: column.label, valueType: column.valueType })),
        graph: {}, analystQuery: lastQuery as unknown as Record<string, unknown>,
        resultRef: { resourceType: "QueryResultRevision", resourceId: result.queryId, revision: String(result.revision), authority: "aip-analyst" },
        cutoffAt: result.cutoffAt,
        sourceRefs: result.sourceRefs,
      });
      setSaved((items) => [created, ...items.filter((item) => item.id !== created.id)]);
      setSaveMessage(`已保存并从服务端重读“${created.payload.name}”修订 ${created.revision}。`);
    } catch (cause) { setSaveMessage(`保存没有完成：${cause instanceof Error ? cause.message : String(cause)}`); }
    finally { setSaveBusy(false); }
  }

  function exportAudit() {
    if (!result || !lastQuery) return;
    const analysis = summarizeResult(result, businessQuestion);
    const body = JSON.stringify({ title: explorationName, businessQuestion, query: lastQuery, resultRef: { queryId: result.queryId, revision: result.revision, contentHash: result.contentHash }, analysis, sources: result.sourceRefs, lineage: result.lineageRefs, exportedAt: new Date().toISOString() }, null, 2);
    const url = URL.createObjectURL(new Blob([body], { type: "application/json;charset=utf-8" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = `${explorationName.trim() || "经营分析探索"}-审计说明.json`; anchor.click(); URL.revokeObjectURL(url);
  }

  const assistHref = useMemo(() => {
    if (!result || !taskRef || !taskRunRef || !agentRunRef) return null;
    const params = new URLSearchParams({ cutoffAt: result.cutoffAt });
    for (const [prefix, ref] of [["task", taskRef], ["taskRun", taskRunRef], ["agentRun", agentRunRef], ["queryResult", { resourceType: "QueryResultRevision", resourceId: result.queryId, revision: String(result.revision), authority: "aip-analyst" }]] as const) { params.set(`${prefix}Id`, ref.resourceId); params.set(`${prefix}Revision`, ref.revision); params.set(`${prefix}Authority`, ref.authority); }
    return `/aip/assist?${params.toString()}`;
  }, [agentRunRef, result, taskRef, taskRunRef]);

  function onLogicMountChange(nextId: string) {
    const next = logicGraphs.find((graph) => graph.id === nextId) || null;
    setLogicMountId(next?.id || "");
    syncLogicMountUrl(next);
  }

  return (
    <PageChrome title="AIP 分析师" lede="受治理的语义、知识和指标查询；结果绑定单一修订，不生成演示数据">
      <div data-testid="analyst-ops-stats" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(110px,1fr))", gap: 10, marginBottom: 12 }}>
        {[
          { label: "查询类型", value: kind === "semantic" ? "语义" : kind === "knowledge" ? "知识" : "指标" },
          { label: "查询准备", value: disabled ? "需补充条件" : busy ? "读取中" : "可查询" },
          { label: "结果态", value: result ? result.status : "未跑" },
          { label: "行数", value: result ? String(result.rows.length) : "—" },
          { label: "对象类型", value: objectTypesReady ? String(objectTypes.length) : "…" },
          { label: "六角色模板", value: !roleTemplatesReady ? "…" : `${roleTemplates.filter((item) => item.readiness === "ready").length}/6` },
          { label: "业务逻辑", value: !logicReady ? "…" : logicMount ? "已挂载" : "未挂载" },
        ].map((s) => (
          <div key={s.label} className="card" style={{ padding: "10px 12px" }}>
            <div style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>{s.label}</div>
            <div style={{ fontSize: 18, fontWeight: 700 }}>{s.value}</div>
          </div>
        ))}
      </div>
      <section className="card" style={{ padding: 14, marginBottom: 12 }} data-testid="analyst-role-workbench">
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "baseline", marginBottom: 10 }}>
          <div>
            <strong>六数字同事治理工作面</strong>
            <div style={muted}>模板来自已版本化电商方案包；选择角色只装配查询，不代表 Agent 已执行。</div>
          </div>
          <details style={{ ...muted, fontSize: 12 }}><summary>模板目录技术标识（审计用）</summary><code>{roleTemplateHash ? `${roleTemplateHash.slice(0, 12)}…` : "—"}</code></details>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 10 }}>
          {roleTemplates.map((template) => (
            <button
              key={template.templateId}
              type="button"
              aria-pressed={selectedTemplateId === template.templateId}
              onClick={() => selectRoleTemplate(template)}
              style={{ ...roleCard, ...(selectedTemplateId === template.templateId ? roleCardSelected : {}) }}
              data-testid={`analyst-role-${template.roleId.replace("ecommerce.", "")}`}
            >
              <span style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <strong>{template.roleName}</strong>
                <span style={{ color: template.readiness === "ready" ? "#047857" : "#b45309" }}>{template.readiness === "ready" ? "可查询" : "需补充条件"}</span>
              </span>
              <span style={{ ...muted, fontSize: 12 }}>{template.purpose}</span>
              <span style={{ ...muted, fontSize: 12 }}>{objectTypeDisplayName(template.defaultObjectType || "")} · {template.requiredLogicIds.length} 项业务逻辑</span>
            </button>
          ))}
          {roleTemplatesReady && roleTemplates.length === 0 && <div style={warning}>六角色模板未返回；未注入本地模板。</div>}
        </div>
        {roleTemplatesError && <p role="alert" style={warning}>六角色模板读取失败：{roleTemplatesError}。页面保持失败关闭。</p>}
      </section>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <button type="button" aria-expanded={leftOpen} onClick={() => setLeftOpen((v) => !v)} onKeyDown={(event) => activateToggle(event, () => setLeftOpen((v) => !v))}>{leftOpen ? "收起查询" : "展开查询"}</button>
        <button type="button" aria-expanded={rightOpen} onClick={() => setRightOpen((v) => !v)} onKeyDown={(event) => activateToggle(event, () => setRightOpen((v) => !v))}>{rightOpen ? "收起证据" : "展开证据"}</button>
        <button type="button" aria-pressed={focus} onClick={() => setFocus((v) => !v)} onKeyDown={(event) => activateToggle(event, () => setFocus((v) => !v))}>{focus ? "退出专注" : "专注模式"}</button>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: `${focus || !leftOpen ? "0" : "280px"} minmax(0,1fr) ${focus || !rightOpen ? "0" : "320px"}`, gap: 16, minHeight: 620 }}>
        <aside style={{ ...panel, overflow: "hidden", display: focus || !leftOpen ? "none" : "block" }} data-testid="analyst-query-builder">
          <h3>查询构造器</h3>
          <label style={label}>复用已保存探索
            <select value="" onChange={(event) => { const asset = saved.find((item) => item.id === event.target.value); if (asset) applySaved(asset); }} style={input} aria-label="analyst-saved-exploration">
              <option value="">选择历史探索…</option>
              {saved.map((item) => <option key={item.id} value={item.id}>{item.payload.name} · 修订 {item.revision}</option>)}
            </select>
          </label>
          <label style={label}>经营问题
            <textarea value={businessQuestion} onChange={(event) => setBusinessQuestion(event.target.value)} style={{ ...input, minHeight: 72 }} placeholder="例如：近30天哪些商品值得优先补货？" />
          </label>
          <label style={label}>查询类型
            <select value={kind} onChange={(e) => { useCustomQuery(); setKind(e.target.value as QueryKind); }} style={input} aria-label="analyst-query-kind">
              <option value="semantic">语义对象</option>
              <option value="knowledge">行业知识</option>
              <option value="metric">权威指标</option>
            </select>
          </label>
          {kind === "semantic" && (
            <label style={label}>业务对象类型
              <select
                value={objectType}
                onChange={(e) => { useCustomQuery(); setObjectType(e.target.value); }}
                style={input}
                aria-label="analyst-object-type"
                data-testid="analyst-object-type"
                disabled={!objectTypesReady || objectTypes.length === 0}
              >
                {objectTypes.length === 0 ? <option value="">暂无已安装类型</option> : null}
                {objectTypes.map((item) => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
              </select>
            </label>
          )}
          {kind === "knowledge" && (
            <label style={label}>知识问题
              <textarea value={prompt} onChange={(e) => { useCustomQuery(); setPrompt(e.target.value); }} style={{ ...input, minHeight: 100 }} />
            </label>
          )}
          {(kind === "semantic" || kind === "metric") && <>
            <h4 style={{ margin: "4px 0 8px", fontSize: 14 }}>筛选条件</h4>
            <label style={label}>字段<input value={filterField} onChange={(event) => setFilterField(event.target.value)} style={input} placeholder="例如 status" /></label>
            <label style={label}>条件<select value={filterOperator} onChange={(event) => setFilterOperator(event.target.value as typeof filterOperator)} style={input}><option value="eq">等于</option><option value="neq">不等于</option><option value="gt">大于</option><option value="gte">大于等于</option><option value="lt">小于</option><option value="lte">小于等于</option><option value="contains">包含</option><option value="in">属于集合</option></select></label>
            <label style={label}>值<input value={filterValue} onChange={(event) => setFilterValue(event.target.value)} style={input} placeholder="留空表示不筛选" /></label>
          </>}
          {kind === "metric" && <label style={label}>分析维度（逗号分隔）<input value={dimensions} onChange={(event) => setDimensions(event.target.value)} style={input} placeholder="例如 渠道,商品" /></label>}
          <label style={label}>数据截止时间<input type="datetime-local" value={cutoffAt} onChange={(event) => setCutoffAt(event.target.value)} style={input} /></label>
          {kind === "semantic" && <label style={label}>最多读取<select value={pageSize} onChange={(event) => setPageSize(Number(event.target.value))} style={input}><option value={20}>20 条</option><option value={50}>50 条</option><option value={100}>100 条</option><option value={200}>200 条</option></select></label>}
          <section data-testid="analyst-logic-mount" style={{ marginBottom: 16 }}>
            <h4 style={{ margin: "0 0 8px", fontSize: 14 }}>业务逻辑挂载点</h4>
            <label style={label}>已保存业务逻辑
              <select
                value={logicMountId}
                onChange={(e) => onLogicMountChange(e.target.value)}
                style={input}
                aria-label="analyst-logic-mount"
                data-testid="analyst-logic-mount-select"
                disabled={!logicReady || logicGraphs.length === 0}
              >
                {logicGraphs.length === 0 ? <option value="">暂无已保存业务逻辑</option> : null}
                {logicGraphs.map((graph) => (
                  <option key={graph.id} value={graph.id}>
                    {businessDisplayName(graph.name)} · 修订 {graph.revision}
                  </option>
                ))}
              </select>
            </label>
            {logicReady && logicGraphs.length === 0 && (
              <p style={warning} data-testid="analyst-logic-mount-blocked">
                当前租户暂无已保存业务逻辑；本次仅执行受控查询，不注入演示图。
              </p>
            )}
            {logicError && (
              <p style={warning} role="alert" data-testid="analyst-logic-mount-error">
                业务逻辑列表读取失败：{logicError}。未注入演示挂载。
              </p>
            )}
            {logicMount && (
              <div style={{ ...smallCard, fontSize: 12 }} data-testid="analyst-logic-mount-exact">
                精确修订 {logicMount.revision}
                <details style={{ marginTop: 6 }}>
                  <summary>技术标识（审计用）</summary>
                  <code>{logicMount.id}@r{logicMount.revision}</code>
                  <br />
                  <code>{logicMount.graphHash.slice(0, 24)}…</code>
                </details>
                <div style={{ marginTop: 8 }}>
                  <Link
                    to={`/aip/logic?graph=${encodeURIComponent(logicMount.id)}`}
                    data-testid="analyst-jump-logic"
                    style={{ color: "#2563eb" }}
                  >
                    打开业务逻辑画布 →
                  </Link>
                </div>
              </div>
            )}
          </section>
          <button type="button" onClick={() => void run()} disabled={Boolean(disabled) || busy} title={disabled || undefined} style={{ ...primary, opacity: disabled || busy ? .5 : 1 }} data-testid="analyst-run-query">
            {busy ? "查询中…" : "运行真实查询"}
          </button>
          {disabled && <p style={warning} data-testid="analyst-run-blocked">{disabled}</p>}
          {objectTypesError && <p style={warning} role="alert" data-testid="analyst-object-types-error">业务对象类型读取失败：{objectTypesError}。未注入演示类型。</p>}
          <p style={muted}>不接受任意 SQL；业务对象类型与业务逻辑均来自权威接口；租户由当前登录身份决定。</p>
        </aside>
        <section aria-label="分析结果" style={panel}>
          {error && <div role="alert" style={warning}>请求失败：{error}。未生成本地结果。</div>}
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
            <div>
              {(["table", "chart", "map", "raw"] as View[]).map((item) => (
                <button type="button" key={item} onClick={() => setView(item)} style={view === item ? primary : undefined}>
                  {({ table: "表格", chart: "图表", map: "地图", raw: "原始结果" } as const)[item]}
                </button>
              ))}
            </div>
            {result && <strong data-testid="analyst-result-meta">{statusDisplayName(result.status)} · {result.rows.length} 行 · 修订 {result.revision}</strong>}
          </div>
          {result ? <ResultBody result={result} view={view} objectLabel={objectTypeDisplayName(objectType)} /> : <Empty title="选择业务对象开始查询" text="页面只读取当前租户的权威业务对象；读取失败时不展示推测结果，并提供重新查询入口。" />}
          {result && result.status !== "blocked" && <section className="card" style={{ padding: 14, marginTop: 14 }} data-testid="analyst-readable-summary">
            <h3 style={{ marginTop: 0 }}>经营分析摘要</h3>
            <p><strong>结论摘要：</strong>{summarizeResult(result, businessQuestion).summary}</p>
            <p><strong>对比与异常：</strong>{summarizeResult(result, businessQuestion).comparison}</p>
            <p><strong>关键假设：</strong>{summarizeResult(result, businessQuestion).assumptions.join("；")}</p>
            <p><strong>不确定性：</strong>{result.uncertainties.length ? result.uncertainties.join("；") : "当前服务端没有返回额外不确定性；仍须遵守当前筛选、权限和截止时间边界。"}</p>
          </section>}
          {result && result.status !== "blocked" && <section style={{ display: "grid", gap: 10, marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--aos-border)" }} aria-label="探索后续动作">
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <input aria-label="探索名称" value={explorationName} onChange={(event) => setExplorationName(event.target.value)} style={{ ...input, width: 240 }} />
              <button type="button" onClick={() => void saveCurrentExploration()} disabled={saveBusy}>{saveBusy ? "保存中…" : "保存探索"}</button>
              <button type="button" onClick={exportAudit}>导出审计说明</button>
              {assistHref ? <Link to={assistHref} style={primary}>交给任务协作助手</Link> : <Link to="/aip/logic" style={primary}>建立任务运行后协作</Link>}
            </div>
            {saveMessage && <p role="status" style={muted}>{saveMessage}</p>}
            {!assistHref && <p style={muted}>当前分析没有上游 Task、TaskRun 和 AgentRun 精确引用；先建立真实任务运行，结果才能作为协作上下文移交。</p>}
          </section>}
        </section>
        <aside style={{ ...panel, overflow: "auto", display: focus || !rightOpen ? "none" : "block" }}>
          <h3>证据详情</h3>
          <Evidence result={result} logicMount={logicMount} />
        </aside>
      </div>
    </PageChrome>
  );
}

const panel = { background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 10, padding: 18 }, label = { display: "grid", gap: 6, marginBottom: 16, fontWeight: 600 }, input = { width: "100%", padding: "9px 10px", border: "1px solid var(--aos-border)", borderRadius: 7, background: "transparent", color: "var(--aos-text)" }, primary = { background: "var(--aos-accent, #2563eb)", color: "white", border: 0, borderRadius: 7, padding: "9px 14px" }, muted = { color: "var(--aos-text-muted)", overflowWrap: "anywhere" as const }, warning = { padding: 10, color: "var(--aos-amber)", background: "var(--aos-amber-bg)", border: "1px solid var(--aos-amber-border)", borderRadius: 7 }, empty = { display: "grid", placeContent: "center", textAlign: "center" as const, minHeight: 360, color: "var(--aos-text-muted)" }, smallCard = { padding: 9, marginTop: 7, border: "1px solid var(--aos-border)", borderRadius: 7, overflowWrap: "anywhere" as const }, cell = { borderBottom: "1px solid var(--aos-border)", textAlign: "left" as const, padding: "10px 12px", whiteSpace: "nowrap" as const }, raw = { maxHeight: 520, overflow: "auto", background: "#0f172a", color: "#e2e8f0", padding: 16, borderRadius: 8, fontSize: 12 };
const roleCard = { display: "grid", gap: 8, textAlign: "left" as const, padding: 12, border: "1px solid var(--aos-border)", borderRadius: 9, background: "var(--aos-surface)", color: "var(--aos-text)", minHeight: 126 };
const roleCardSelected = { borderColor: "var(--aos-accent, #2563eb)", boxShadow: "0 0 0 2px var(--aos-accent-light)", background: "var(--aos-accent-light)" };
