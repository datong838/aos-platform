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
  const requestGeneration = useRef(0);

  const selectedNode = useMemo(
    () => graph?.nodes.find((node) => node.id === selectedNodeId) ?? null,
    [graph, selectedNodeId],
  );

  useEffect(() => {
    const generation = ++requestGeneration.current;
    setSelectedNodeId("");
    setError("");
    setMessage("");
    setSaving(false);
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
      })
      .catch((loadError: unknown) => {
        if (requestGeneration.current !== generation) return;
        setError(`加载失败：${errorMessage(loadError)}`);
      })
      .finally(() => {
        if (requestGeneration.current === generation) setLoading(false);
      });
  }, [activeFlowId]);

  function mutateGraph(mutator: (current: LogicGraphSnapshot) => LogicGraphSnapshot): void {
    setGraph((current) => current ? mutator(current) : current);
    setDirty(true);
    setError("");
    setMessage("");
  }

  async function saveGraph(): Promise<void> {
    if (!graph || saving || !dirty) return;
    const generation = ++requestGeneration.current;
    const wasPersisted = graph.persisted;
    const expectedRevision = graph.revision;
    const draft = toDraft(graph);
    setSaving(true);
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
    } catch (saveError: unknown) {
      if (requestGeneration.current !== generation) return;
      setError(`保存失败：${errorMessage(saveError)}`);
      setDirty(true);
    } finally {
      if (requestGeneration.current === generation) setSaving(false);
    }
  }

  async function refreshGraph(): Promise<void> {
    if (!graph || loading || saving) return;
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
    const graphId = graph.id;
    const wasDirty = dirty;
    setLoading(true);
    try {
      const loaded = await getLogicGraph(graphId);
      if (requestGeneration.current !== generation) return;
      setGraph(loaded);
      setDirty(false);
      setMessage(`已从服务端刷新 · revision ${loaded.revision}`);
    } catch (loadError: unknown) {
      if (requestGeneration.current !== generation) return;
      setError(`刷新失败：${errorMessage(loadError)}`);
      setDirty(wasDirty);
    } finally {
      if (requestGeneration.current === generation) setLoading(false);
    }
  }

  return (
    <PageChrome
      title="AIP Logic 无代码编辑器"
      lede="自由编排 canonical Logic Graph；保存仅在服务端提交与严格 GET 回读一致后确认。"
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
        <button type="button" className="btn btn-primary" disabled={!graph || loading || saving || !dirty} onClick={() => void saveGraph()}>
          {saving ? "保存并回读中…" : `保存${dirty ? " *" : ""}`}
        </button>
        <button type="button" className="btn" disabled={!graph || loading || saving} onClick={() => void refreshGraph()}>
          {loading ? "读取中…" : "刷新"}
        </button>
        {graph?.persisted && !dirty && (
          <button type="button" className="btn" disabled title="可信图执行将在 Stage B 接入">
            canonical dry-run · Stage B 尚未开放
          </button>
        )}
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
              disabled={loading || saving}
              onChange={(event) => mutateGraph((current) => ({ ...current, name: event.target.value }))}
              style={{ display: "block", width: "100%", marginTop: 3 }}
            />
          </label>
          <label style={{ fontSize: "0.75rem" }}>
            描述
            <input
              aria-label="Logic 描述"
              value={graph.description}
              disabled={loading || saving}
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

      {loading && !graph && <p>正在加载 canonical Logic Graph…</p>}
      {!loading && !graph && !error && <p>Logic Graph 不可用</p>}

      {graph && (
        <LogicGraphCanvas
          nodes={graph.nodes}
          edges={graph.edges}
          selectedNodeId={selectedNodeId}
          zoom={zoom}
          inspectorCollapsed={inspectorCollapsed}
          disabled={loading || saving}
          onNodesChange={(nodes) => setGraph((current) => {
            if (!current) return current;
            const nodeIds = new Set(nodes.map((node) => node.id));
            return {
              ...current,
              nodes,
              entry_node_ids: current.entry_node_ids.filter((nodeId) => nodeIds.has(nodeId)),
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
              disabled={loading || saving}
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

      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(240px, 1fr))", gap: 10, marginTop: 12 }}>
        <section style={{ border: "1px solid var(--aos-border)", padding: 12, borderRadius: 2 }}>
          <h3 style={{ margin: "0 0 6px", fontSize: "0.84rem" }}>运行历史</h3>
          <p style={{ margin: 0, color: "var(--aos-muted)", fontSize: "0.75rem" }}>运行历史尚未接入 canonical API；Stage B 前不展示会话内伪历史。</p>
        </section>
        <section style={{ border: "1px solid var(--aos-border)", padding: 12, borderRadius: 2 }}>
          <h3 style={{ margin: "0 0 6px", fontSize: "0.84rem" }}>自动化</h3>
          <p style={{ margin: 0, color: "var(--aos-muted)", fontSize: "0.75rem" }}>自动化尚未接入发布版本契约；完成 Evals 与 Draft 门控前保持禁用。</p>
        </section>
      </div>
    </PageChrome>
  );
}
