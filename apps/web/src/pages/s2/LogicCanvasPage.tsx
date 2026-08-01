import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { PageChrome } from "../../components/PageChrome";
import { DEFAULT_LOGIC_PALETTE, LogicGraphCanvas } from "./LogicGraphCanvas";
import { LogicGraphInspector } from "./LogicGraphInspector";
import {
  type LogicBlockKind,
  type LogicGraphEdge,
  type LogicGraphNode,
  type LogicGraphSnapshot,
} from "./logicCanvasGraph";
import {
  createLogicGraph,
  getLogicGraph,
  replaceLogicGraph,
  type LogicGraphDraft,
} from "./logicGraphApi";
import { LogicRunPanel, type LogicRunLoadState } from "./LogicRunPanel";
import {
  dryRunLogicGraph,
  getLogicRun,
  listLogicRuns,
} from "./logicRunApi";
import type {
  JsonObject,
  LogicDryRun,
  LogicRunSummary,
} from "./logicRunContracts";

/** 向后兼容：旧测试和外部引用仍使用这些导出。 */
export interface BranchPath {
  id: string;
  label: string;
  condition: string;
  color: string;
  default?: boolean;
}

export interface HandoffConfig {
  decision: string;
  artifacts: string[];
  open_qs: string[];
  handoff_to: "risk_agent" | "draft_inbox" | "webhook";
}

export const PALETTE = DEFAULT_LOGIC_PALETTE.map((item) => ({
  kind: item.kind,
  title: item.title,
  zh: item.label,
  desc: item.description,
  icon: item.icon,
}));

export const KIND_META: Record<LogicBlockKind, { label: string; color: string; bg: string; border: string }> = {
  input: { label: "输入", color: "var(--aos-indigo-600)", bg: "var(--aos-indigo-bg)", border: "var(--aos-indigo-border)" },
  create_variable: { label: "创建变量", color: "var(--color-info)", bg: "var(--aos-accent-light)", border: "var(--aos-green-border)" },
  get_property: { label: "获取属性", color: "var(--aos-amber)", bg: "var(--aos-amber-bg)", border: "var(--aos-amber-border)" },
  use_llm: { label: "使用 LLM", color: "var(--aos-purple-600)", bg: "var(--aos-indigo-bg)", border: "var(--aos-indigo-border)" },
  use_tool: { label: "使用工具", color: "var(--aos-purple-600)", bg: "var(--aos-indigo-bg)", border: "var(--aos-indigo-border)" },
  transform: { label: "数据变换", color: "var(--color-info)", bg: "var(--aos-accent-light)", border: "var(--aos-accent-border)" },
  apply_action: { label: "应用动作", color: "var(--aos-amber-600)", bg: "var(--aos-amber-bg)", border: "var(--aos-amber-border)" },
  execute: { label: "执行", color: "var(--aos-green)", bg: "var(--aos-green-bg)", border: "var(--aos-green-border)" },
  branch: { label: "分支", color: "var(--aos-red)", bg: "var(--aos-red-bg)", border: "var(--aos-red-border)" },
  handoff: { label: "汇聚", color: "var(--aos-indigo-600)", bg: "var(--aos-indigo-bg)", border: "var(--aos-indigo-border)" },
};

export interface LogicCanvasPageProps {
  flowId?: string;
}

let nextTemplateId = 0;

function createTemplate(): LogicGraphSnapshot {
  nextTemplateId += 1;
  const id = `logic-${Date.now().toString(36)}-${nextTemplateId}`;
  const nodes: LogicGraphNode[] = [
    {
      id: "template-input",
      kind: "input",
      label: "WorkOrder 输入",
      position_x: 80,
      position_y: 140,
      config: { schema: { type: "object", properties: { objectId: { type: "string" } } } },
    },
    {
      id: "template-property",
      kind: "get_property",
      label: "获取状态",
      position_x: 340,
      position_y: 140,
      config: { property: "status" },
    },
    {
      id: "template-llm",
      kind: "use_llm",
      label: "LLM 分析",
      position_x: 600,
      position_y: 140,
      config: { prompt: "分析工单状态并给出建议", model: "k-LLM router" },
    },
    {
      id: "template-action",
      kind: "apply_action",
      label: "提议更新 note",
      position_x: 860,
      position_y: 140,
      config: { action: "WorkOrder.updateNote" },
    },
  ];
  const edges: LogicGraphEdge[] = [
    { id: "template-edge-1", source_node_id: nodes[0].id, source_port: "out", target_node_id: nodes[1].id, target_port: "in", branch_path: "", order: 0 },
    { id: "template-edge-2", source_node_id: nodes[1].id, source_port: "out", target_node_id: nodes[2].id, target_port: "in", branch_path: "", order: 1 },
    { id: "template-edge-3", source_node_id: nodes[2].id, source_port: "out", target_node_id: nodes[3].id, target_port: "in", branch_path: "", order: 2 },
  ];
  return {
    id,
    name: "未保存 Logic 模板",
    description: "从 WorkOrder 输入生成受治理的 Action 提议",
    status: "draft",
    schema_version: 1,
    revision: 0,
    published_version: null,
    graph_hash: "",
    persisted: false,
    demo: true,
    nodes,
    edges,
    entry_node_ids: [nodes[0].id],
  };
}

function cloneGraph(graph: LogicGraphSnapshot): LogicGraphSnapshot {
  return structuredClone(graph);
}

function toDraft(graph: LogicGraphSnapshot): LogicGraphDraft {
  return {
    id: graph.id,
    name: graph.name,
    description: graph.description,
    status: graph.status === "archived" ? "archived" : "draft",
    schema_version: graph.schema_version,
    nodes: graph.nodes,
    edges: graph.edges,
    entry_node_ids: graph.entry_node_ids,
  };
}

function errorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  const status = (error as { status?: number } | null)?.status;
  return status === 409 ? `版本冲突：${message}` : message;
}

const GRAPH_HASH_RE = /^[0-9a-f]{64}$/i;
const HISTORY_PAGE_SIZE = 20;

export function LogicCanvasPage({ flowId }: LogicCanvasPageProps = {}) {
  const params = useParams<{ flowId?: string }>();
  const navigate = useNavigate();
  const activeFlowId = flowId ?? params.flowId;
  const templateRef = useRef<LogicGraphSnapshot | null>(null);
  if (!templateRef.current) templateRef.current = createTemplate();

  const [graph, setGraph] = useState<LogicGraphSnapshot | null>(() => cloneGraph(templateRef.current!));
  const [dirty, setDirty] = useState(true);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState("");
  const [zoom, setZoom] = useState(1);
  const [inspectorCollapsed, setInspectorCollapsed] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [inputsDraft, setInputsDraft] = useState("{}");
  const [appliedInputs, setAppliedInputs] = useState<JsonObject | null>(null);
  const [inputsError, setInputsError] = useState("");
  const [running, setRunning] = useState(false);
  const [run, setRun] = useState<LogicDryRun | null>(null);
  const [runState, setRunState] = useState<LogicRunLoadState>("idle");
  const [runError, setRunError] = useState("");
  const [history, setHistory] = useState<LogicRunSummary[]>([]);
  const [historyState, setHistoryState] = useState<LogicRunLoadState>("idle");
  const [historyError, setHistoryError] = useState("");
  const [historyCursor, setHistoryCursor] = useState<string | null>(null);
  const [loadingMoreHistory, setLoadingMoreHistory] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const requestGeneration = useRef(0);
  const runRequestGeneration = useRef(0);
  const detailRequestGeneration = useRef(0);
  const runningRef = useRef(false);

  const selectedNode = useMemo(
    () => graph?.nodes.find((node) => node.id === selectedNodeId) ?? null,
    [graph, selectedNodeId],
  );

  useEffect(() => {
    const generation = ++requestGeneration.current;
    runRequestGeneration.current += 1;
    detailRequestGeneration.current += 1;
    setSelectedNodeId("");
    setError("");
    setMessage("");
    setSaving(false);
    setInputsDraft("{}");
    setAppliedInputs(null);
    setInputsError("");
    setRunning(false);
    runningRef.current = false;
    setRun(null);
    setRunState("idle");
    setRunError("");
    setHistory([]);
    setHistoryState(activeFlowId ? "loading" : "idle");
    setHistoryError("");
    setHistoryCursor(null);
    setLoadingMoreHistory(false);
    setSelectedRunId(null);
    if (!activeFlowId) {
      setGraph(cloneGraph(templateRef.current!));
      setDirty(true);
      setLoading(false);
      return;
    }

    setGraph(null);
    setDirty(false);
    setLoading(true);
    void getLogicGraph(activeFlowId)
      .then((loaded) => {
        if (requestGeneration.current !== generation) return;
        setGraph(loaded);
        setDirty(false);
        void listLogicRuns(loaded.id, { limit: HISTORY_PAGE_SIZE })
          .then((response) => {
            if (requestGeneration.current !== generation) return;
            setHistory(response.items);
            setHistoryCursor(response.next_cursor);
            setHistoryState("ready");
          })
          .catch((historyLoadError: unknown) => {
            if (requestGeneration.current !== generation) return;
            setHistoryState("error");
            setHistoryError(errorMessage(historyLoadError));
          });
      })
      .catch((loadError: unknown) => {
        if (requestGeneration.current !== generation) return;
        setError(`加载失败：${errorMessage(loadError)}`);
        setHistoryState("error");
        setHistoryError("Logic Graph 加载失败，未读取运行历史");
      })
      .finally(() => {
        if (requestGeneration.current === generation) setLoading(false);
      });
  }, [activeFlowId]);

  const dryRunDisabledReason = loading
    ? "Logic Graph 正在加载"
    : !graph
      ? "Logic Graph 尚未加载"
      : saving
        ? "请等待保存与回读完成"
        : running
          ? "安全试跑正在运行，请勿重复提交"
          : !graph.persisted
            ? "请先保存 Logic Graph"
            : dirty
              ? "存在未保存更改，请先保存并完成回读"
              : graph.revision < 1
                ? "服务端 revision 无效"
                : !GRAPH_HASH_RE.test(graph.graph_hash)
                  ? "服务端 graph hash 无效"
                  : appliedInputs === null
                    ? "请先显式应用 Dry-Run Inputs"
                    : "";

  function mutateGraph(mutator: (current: LogicGraphSnapshot) => LogicGraphSnapshot): void {
    setGraph((current) => current ? mutator(current) : current);
    setDirty(true);
    setError("");
    setMessage("");
  }

  async function saveGraph(): Promise<void> {
    if (!graph || saving || running || !dirty) return;
    const generation = ++requestGeneration.current;
    detailRequestGeneration.current += 1;
    const wasPersisted = graph.persisted;
    const expectedRevision = graph.revision;
    const draft = toDraft(graph);
    setSaving(true);
    setRun(null);
    setRunState("idle");
    setRunError("");
    setSelectedRunId(null);
    setError("");
    setMessage("");
    try {
      const saved = wasPersisted
        ? await replaceLogicGraph(draft, expectedRevision)
        : await createLogicGraph(draft);
      if (requestGeneration.current !== generation) return;
      setGraph(saved);
      setDirty(false);
      setMessage(`已保存并回读确认 · revision ${saved.revision}`);
      if (!wasPersisted) navigate(`/aip/logic/${encodeURIComponent(saved.id)}`, { replace: true });
      else void refreshHistory();
    } catch (saveError: unknown) {
      if (requestGeneration.current !== generation) return;
      setError(`保存失败：${errorMessage(saveError)}`);
      setDirty(true);
    } finally {
      if (requestGeneration.current === generation) setSaving(false);
    }
  }

  async function refreshGraph(): Promise<void> {
    if (!graph || loading || saving || running) return;
    setError("");
    setMessage("");
    setSelectedNodeId("");
    if (!graph.persisted) {
      setGraph(cloneGraph(templateRef.current!));
      setDirty(true);
      setMessage("已丢弃本地改动并恢复未保存模板");
      return;
    }

    const generation = ++requestGeneration.current;
    detailRequestGeneration.current += 1;
    const graphId = graph.id;
    const wasDirty = dirty;
    setLoading(true);
    setRun(null);
    setRunState("idle");
    setRunError("");
    setSelectedRunId(null);
    try {
      const loaded = await getLogicGraph(graphId);
      if (requestGeneration.current !== generation) return;
      setGraph(loaded);
      setDirty(false);
      setMessage(`已从服务端刷新 · revision ${loaded.revision}`);
      void refreshHistory();
    } catch (loadError: unknown) {
      if (requestGeneration.current !== generation) return;
      setError(`刷新失败：${errorMessage(loadError)}`);
      setDirty(wasDirty);
    } finally {
      if (requestGeneration.current === generation) setLoading(false);
    }
  }

  function applyDryRunInputs(): void {
    try {
      const parsed: unknown = JSON.parse(inputsDraft);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("Inputs 必须是 JSON 对象");
      }
      setAppliedInputs(parsed as JsonObject);
      setInputsError("");
      setMessage("Dry-Run Inputs 已显式应用；未写入 Logic Graph");
    } catch (inputError: unknown) {
      setAppliedInputs(null);
      setInputsError(errorMessage(inputError));
      setMessage("");
    }
  }

  async function refreshHistory(): Promise<void> {
    if (!graph?.persisted) return;
    const generation = requestGeneration.current;
    const graphId = graph.id;
    setHistoryState("loading");
    setHistoryError("");
    try {
      const response = await listLogicRuns(graphId, { limit: HISTORY_PAGE_SIZE });
      if (requestGeneration.current !== generation) return;
      setHistory(response.items);
      setHistoryCursor(response.next_cursor);
      setHistoryState("ready");
    } catch (historyLoadError: unknown) {
      if (requestGeneration.current !== generation) return;
      setHistoryState("error");
      setHistoryError(errorMessage(historyLoadError));
    }
  }

  async function loadRunDetail(runId: string): Promise<void> {
    if (!graph?.persisted) return;
    const generation = requestGeneration.current;
    const detailGeneration = ++detailRequestGeneration.current;
    const graphId = graph.id;
    setSelectedRunId(runId);
    setRun(null);
    setRunState("loading");
    setRunError("");
    try {
      const detail = await getLogicRun(graphId, runId);
      if (requestGeneration.current !== generation || detailRequestGeneration.current !== detailGeneration) return;
      setRun(detail);
      setRunState("ready");
    } catch (detailError: unknown) {
      if (requestGeneration.current !== generation || detailRequestGeneration.current !== detailGeneration) return;
      setRunState("error");
      setRunError(errorMessage(detailError));
    }
  }

  async function runDryRun(): Promise<void> {
    if (!graph || dryRunDisabledReason || appliedInputs === null || runningRef.current) return;
    const generation = requestGeneration.current;
    const runGeneration = ++runRequestGeneration.current;
    const graphId = graph.id;
    const revision = graph.revision;
    const graphHash = graph.graph_hash;
    const expectedNodeIds = graph.nodes.map((node) => node.id);
    const inputs = structuredClone(appliedInputs);
    detailRequestGeneration.current += 1;
    runningRef.current = true;
    setRunning(true);
    setRun(null);
    setSelectedRunId(null);
    setRunState("loading");
    setRunError("");
    setError("");
    setMessage("");
    try {
      const result = await dryRunLogicGraph(graphId, {
        expected_revision: revision,
        dry_run: true,
        expected_graph_hash: graphHash,
        inputs,
      }, expectedNodeIds);
      if (requestGeneration.current !== generation || runRequestGeneration.current !== runGeneration) return;
      setRun(result);
      setSelectedRunId(result.run_id);
      setRunState("ready");
      setMessage(`安全试跑已完成 · revision ${result.evaluated_revision} · 不写生产`);
      void refreshHistory();
    } catch (runFailure: unknown) {
      if (requestGeneration.current !== generation || runRequestGeneration.current !== runGeneration) return;
      setRunState("error");
      setRunError(errorMessage(runFailure));
    } finally {
      if (requestGeneration.current === generation && runRequestGeneration.current === runGeneration) {
        runningRef.current = false;
        setRunning(false);
      }
    }
  }

  async function loadMoreHistory(): Promise<void> {
    if (!graph?.persisted || !historyCursor || loadingMoreHistory) return;
    const generation = requestGeneration.current;
    const graphId = graph.id;
    const cursor = historyCursor;
    setLoadingMoreHistory(true);
    setHistoryError("");
    try {
      const response = await listLogicRuns(graphId, { limit: HISTORY_PAGE_SIZE, before: cursor });
      if (requestGeneration.current !== generation) return;
      setHistory((current) => {
        const known = new Set(current.map((item) => item.run_id));
        return [...current, ...response.items.filter((item) => !known.has(item.run_id))];
      });
      setHistoryCursor(response.next_cursor);
      setHistoryState("ready");
    } catch (historyLoadError: unknown) {
      if (requestGeneration.current !== generation) return;
      setHistoryState("error");
      setHistoryError(errorMessage(historyLoadError));
    } finally {
      if (requestGeneration.current === generation) setLoadingMoreHistory(false);
    }
  }

  function locateRunNode(nodeId: string): void {
    if (!graph?.nodes.some((node) => node.id === nodeId)) {
      setError(`历史运行节点 ${nodeId} 不在当前 revision，未修改画布。`);
      return;
    }
    setSelectedNodeId(nodeId);
    setInspectorCollapsed(false);
  }

  return (
    <PageChrome
      title="AIP Logic 无代码编辑器"
      lede="自由编排 canonical Logic Graph；保存仅在服务端提交与严格 GET 回读一致后确认。"
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
        <button type="button" className="btn btn-primary" disabled={!graph || loading || saving || running || !dirty} onClick={() => void saveGraph()}>
          {saving ? "保存并回读中…" : `保存${dirty ? " *" : ""}`}
        </button>
        <button type="button" className="btn" disabled={!graph || loading || saving || running} onClick={() => void refreshGraph()}>
          {loading ? "读取中…" : "刷新"}
        </button>
        <button
          type="button"
          className="btn"
          disabled={Boolean(dryRunDisabledReason)}
          title={dryRunDisabledReason || "使用已确认 revision/hash 进行只读安全试跑"}
          onClick={() => void runDryRun()}
        >
          {running ? "安全试跑中…" : "安全试跑"}
        </button>
        <span data-testid="dry-run-gate-reason" style={{ color: dryRunDisabledReason ? "var(--aos-muted)" : "var(--aos-green-700)", fontSize: "0.72rem" }}>
          {dryRunDisabledReason || "已满足可信试跑门禁"}
        </span>
        <Link to="/aip/drafts" className="btn" style={{ textDecoration: "none" }}>Draft 审批台</Link>
        <Link to="/aip/evals" className="btn" style={{ textDecoration: "none" }}>Evals 门控</Link>
        <span style={{ marginLeft: "auto", fontSize: "0.76rem", color: dirty ? "var(--aos-amber-700)" : "var(--aos-green-700)" }}>
          {dirty ? "未保存更改" : graph ? `已确认 revision ${graph.revision}` : "未加载"}
        </span>
      </div>

      {graph && (
        <div style={{ display: "grid", gridTemplateColumns: "minmax(220px, 1fr) minmax(220px, 1fr)", gap: 8, marginBottom: 10 }}>
          <label style={{ fontSize: "0.75rem" }}>
            Logic 名称
            <input
              aria-label="Logic 名称"
              value={graph.name}
              disabled={loading || saving || running}
              onChange={(event) => mutateGraph((current) => ({ ...current, name: event.target.value }))}
              style={{ display: "block", width: "100%", marginTop: 3 }}
            />
          </label>
          <label style={{ fontSize: "0.75rem" }}>
            描述
            <input
              aria-label="Logic 描述"
              value={graph.description}
              disabled={loading || saving || running}
              onChange={(event) => mutateGraph((current) => ({ ...current, description: event.target.value }))}
              style={{ display: "block", width: "100%", marginTop: 3 }}
            />
          </label>
        </div>
      )}

      {graph && !graph.persisted && (
        <div style={{ background: "var(--aos-amber-bg)", color: "var(--aos-amber-700)", padding: "8px 12px", marginBottom: 10, borderRadius: 2, fontSize: "0.78rem" }}>
          未保存模板：当前 4 节点、3 连接仅在本地；点击“保存”显式创建服务端 Logic Graph。
        </div>
      )}
      {error && <div role="alert" style={{ background: "var(--aos-red-bg)", color: "var(--aos-red)", padding: "8px 12px", marginBottom: 10 }}>{error}</div>}
      {message && <div role="status" style={{ background: "var(--aos-green-bg)", color: "var(--aos-green-700)", padding: "8px 12px", marginBottom: 10 }}>{message}</div>}

      {graph && (
        <section style={{ border: "1px solid var(--aos-border)", padding: 12, borderRadius: 2, marginBottom: 10 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 6 }}>
            <div>
              <h3 style={{ margin: 0, fontSize: "0.84rem" }}>Dry-Run Inputs</h3>
              <p style={{ margin: "3px 0 0", color: "var(--aos-muted)", fontSize: "0.72rem" }}>独立 JSON 对象；仅显式应用后用于安全试跑，不写入画布或生产数据。</p>
            </div>
            <button type="button" className="btn" disabled={loading || saving || running} onClick={applyDryRunInputs}>应用 Inputs</button>
          </div>
          <textarea
            aria-label="Dry-Run Inputs JSON"
            value={inputsDraft}
            disabled={loading || saving || running}
            rows={4}
            spellCheck={false}
            onChange={(event) => {
              setInputsDraft(event.target.value);
              setAppliedInputs(null);
              setInputsError("");
              setMessage("");
            }}
            style={{ display: "block", width: "100%", resize: "vertical", fontFamily: "monospace" }}
          />
          {inputsError && <div role="alert" style={{ marginTop: 6, color: "var(--aos-red)", fontSize: "0.74rem" }}>{inputsError}</div>}
          <div role="status" style={{ marginTop: 6, color: appliedInputs === null ? "var(--aos-muted)" : "var(--aos-green-700)", fontSize: "0.72rem" }}>
            {appliedInputs === null ? "Inputs 尚未应用" : "Inputs 已显式应用"}
          </div>
        </section>
      )}

      {loading && !graph && <p>正在加载 canonical Logic Graph…</p>}
      {!loading && !graph && !error && <p>Logic Graph 不可用</p>}

      {graph && (
        <LogicGraphCanvas
          nodes={graph.nodes}
          edges={graph.edges}
          selectedNodeId={selectedNodeId}
          zoom={zoom}
          inspectorCollapsed={inspectorCollapsed}
          disabled={loading || saving || running}
          onNodesChange={(nodes) => setGraph((current) => {
            if (!current) return current;
            const nodeIds = new Set(nodes.map((node) => node.id));
            const retainedEntries = current.entry_node_ids.filter((nodeId) => nodeIds.has(nodeId));
            const fallbackEntry = nodes.find((node) => node.kind === "input")?.id ?? nodes[0]?.id;
            return {
              ...current,
              nodes,
              entry_node_ids: retainedEntries.length > 0 || !fallbackEntry ? retainedEntries : [fallbackEntry],
            };
          })}
          onEdgesChange={(edges) => setGraph((current) => current ? { ...current, edges } : current)}
          onSelectNode={setSelectedNodeId}
          onDirty={() => {
            setDirty(true);
            setError("");
            setMessage("");
          }}
          onEdgeRejected={(reason) => setError(reason)}
          onZoomChange={setZoom}
          onInspectorCollapsedChange={setInspectorCollapsed}
          inspector={(
            <LogicGraphInspector
              selectedNode={selectedNode}
              entryNodeIds={graph.entry_node_ids}
              disabled={loading || saving || running}
              onNodeChange={(node) => setGraph((current) => current ? {
                ...current,
                nodes: current.nodes.map((candidate) => candidate.id === node.id ? node : candidate),
              } : current)}
              onEntryNodeIdsChange={(entryNodeIds) => setGraph((current) => current ? {
                ...current,
                entry_node_ids: entryNodeIds,
              } : current)}
              onDirty={() => {
                setDirty(true);
                setError("");
                setMessage("");
              }}
              onValidationError={setError}
            />
          )}
        />
      )}

      <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
        {graph?.persisted ? (
          <LogicRunPanel
            run={run}
            runState={runState}
            runError={runError}
            history={history}
            historyState={historyState}
            historyError={historyError}
            selectedRunId={selectedRunId}
            hasMoreHistory={Boolean(historyCursor)}
            loadingMoreHistory={loadingMoreHistory}
            onSelectRun={(runId) => void loadRunDetail(runId)}
            onLocateNode={locateRunNode}
            onRetryRun={selectedRunId ? () => void loadRunDetail(selectedRunId) : undefined}
            onRetryHistory={() => void refreshHistory()}
            onLoadMoreHistory={() => void loadMoreHistory()}
          />
        ) : (
          <section style={{ border: "1px solid var(--aos-border)", padding: 12, borderRadius: 2 }}>
            <h3 style={{ margin: "0 0 6px", fontSize: "0.84rem" }}>运行历史</h3>
            <p style={{ margin: 0, color: "var(--aos-muted)", fontSize: "0.75rem" }}>保存并回读确认后，才从服务端读取不可变运行历史。</p>
          </section>
        )}
        <section style={{ border: "1px solid var(--aos-border)", padding: 12, borderRadius: 2 }}>
          <h3 style={{ margin: "0 0 6px", fontSize: "0.84rem" }}>自动化</h3>
          <p style={{ margin: 0, color: "var(--aos-muted)", fontSize: "0.75rem" }}>自动化尚未接入发布版本契约；完成 Evals 与 Draft 门控前保持禁用。</p>
        </section>
      </div>
    </PageChrome>
  );
}
