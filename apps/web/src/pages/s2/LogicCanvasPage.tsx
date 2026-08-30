import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { PageChrome } from "../../components/PageChrome";
import { apiGet } from "../../api/client";
import { DEFAULT_LOGIC_PALETTE, LogicGraphCanvas } from "./LogicGraphCanvas";
import { LogicGraphInspector } from "./LogicGraphInspector";
import { LogicPublicationPanel, type LogicPublicationLoadState } from "./LogicPublicationPanel";
import {
  type LogicBlockKind,
  type LogicGraphEdge,
  type LogicGraphNode,
  type LogicGraphSnapshot,
} from "./logicCanvasGraph";
import {
  createLogicGraph,
  getLogicGraph,
  listLogicGraphs,
  replaceLogicGraph,
  type LogicGraphDraft,
} from "./logicGraphApi";
import {
  getLogicPublication,
  listLogicPublications,
  publishLogicGraph,
  restoreLogicPublication,
} from "./logicPublicationApi";
import type {
  LogicPublication,
  LogicPublicationEvalGate,
} from "./logicPublicationContracts";
import { LogicRunPanel, type LogicRunLoadState } from "./LogicRunPanel";
import { CanonicalTaskRunPanel } from "./CanonicalTaskRunPanel";
import { LogicAutomationPanel } from "./LogicAutomationPanel";
import { LogicRevisionHistoryPanel } from "./LogicRevisionHistoryPanel";
import {
  dryRunLogicGraph,
  getLogicRun,
  listLogicRuns,
} from "./logicRunApi";
import type {
  JsonObject,
  LogicDryRun,
  LogicNodeRunStatus,
  LogicRunSummary,
} from "./logicRunContracts";
import { aipProductionContracts } from "../../api/aipProductionContracts";
import { aipAgentControl } from "../../api/aipAgentControl";
import {
  productionProjectionEmptyMessage,
  projectProductionProfiles,
  type ProductionProfileProjection,
} from "./logicProductionProjection";
import { businessDisplayName } from "../../lib/aipChineseLabels";

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

type ShellTab = "edit" | "history" | "automation";
const SHELL_TABS: readonly ShellTab[] = ["edit", "history", "automation"];

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

interface EvalSuiteOption {
  id: string;
  name: string;
  gate_threshold: number;
}

interface LogicEvalReport {
  report_id: string;
  suite_id: string;
  target_type: "logic_graph";
  target_id: string;
  target_revision: number;
  target_hash: string;
  gate_passed: boolean;
  pass_rate: number;
  passed: number;
  failed: number;
  total: number;
  run_at: string;
}

export function LogicCanvasPage({ flowId }: LogicCanvasPageProps = {}) {
  const params = useParams<{ flowId?: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeFlowId = flowId ?? params.flowId;
  const requestedTab = searchParams.get("tab");
  const shellTab: ShellTab = SHELL_TABS.includes(requestedTab as ShellTab)
    ? requestedTab as ShellTab
    : "edit";
  const explicitNewDraft = !activeFlowId && searchParams.get("new") === "1";
  const templateRef = useRef<LogicGraphSnapshot | null>(null);
  if (!templateRef.current) templateRef.current = createTemplate();

  const tabRefs = useRef<Partial<Record<ShellTab, HTMLButtonElement | null>>>({});
  const [graph, setGraph] = useState<LogicGraphSnapshot | null>(null);
  const [dirty, setDirty] = useState(false);
  const [undoStack, setUndoStack] = useState<LogicGraphSnapshot[]>([]);
  const [redoStack, setRedoStack] = useState<LogicGraphSnapshot[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState("");
  const [zoom, setZoom] = useState(1);
  const [inspectorCollapsed, setInspectorCollapsed] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [profileProjection, setProfileProjection] = useState<ProductionProfileProjection[]>([]);
  const [projectionStageCount, setProjectionStageCount] = useState(0);
  const [projectionPlanCount, setProjectionPlanCount] = useState(0);
  const [projectionState, setProjectionState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [projectionError, setProjectionError] = useState("");
  const [agentReadySummary, setAgentReadySummary] = useState<{ installed: number; dispatchable: number; state: "idle" | "loading" | "ready" | "error"; error: string }>({
    installed: 0, dispatchable: 0, state: "idle", error: "",
  });
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
  const [evalSuites, setEvalSuites] = useState<EvalSuiteOption[]>([]);
  const [selectedEvalSuiteId, setSelectedEvalSuiteId] = useState("");
  const [evalReport, setEvalReport] = useState<LogicEvalReport | null>(null);
  const [evalEvidenceState, setEvalEvidenceState] = useState<LogicPublicationLoadState>("idle");
  const [evalEvidenceError, setEvalEvidenceError] = useState("");
  const [publications, setPublications] = useState<LogicPublication[]>([]);
  const [publicationsState, setPublicationsState] = useState<LogicPublicationLoadState>("idle");
  const [publicationsError, setPublicationsError] = useState("");
  const [publication, setPublication] = useState<LogicPublication | null>(null);
  const [publicationState, setPublicationState] = useState<LogicPublicationLoadState>("idle");
  const [publicationError, setPublicationError] = useState("");
  const [selectedPublicationId, setSelectedPublicationId] = useState<string | null>(null);
  const [publishing, setPublishing] = useState(false);
  const [restoringPublication, setRestoringPublication] = useState(false);
  const requestGeneration = useRef(0);
  const runRequestGeneration = useRef(0);
  const detailRequestGeneration = useRef(0);
  const runningRef = useRef(false);

  const selectedNode = useMemo(
    () => graph?.nodes.find((node) => node.id === selectedNodeId) ?? null,
    [graph, selectedNodeId],
  );

  const nodeRunStates = useMemo<ReadonlyMap<string, LogicNodeRunStatus>>(() => {
    const states = new Map<string, LogicNodeRunStatus>();
    if (
      !activeFlowId
      || !graph
      || graph.id !== activeFlowId
      || runState !== "ready"
      || !run
      || run.graph_id !== graph.id
    ) return states;
    const currentNodeIds = new Set(graph.nodes.map((node) => node.id));
    run.node_results.forEach((result) => {
      if (currentNodeIds.has(result.node_id)) states.set(result.node_id, result.status);
    });
    return states;
  }, [activeFlowId, graph, run, runState]);

  useEffect(() => {
    let cancelled = false;
    setProjectionState("loading");
    setProjectionError("");
    void Promise.all([
      aipProductionContracts.listStageTemplates(),
      aipProductionContracts.listResponsibilityPlans(),
    ])
      .then(([stages, plans]) => {
        if (cancelled) return;
        setProjectionStageCount(stages.count);
        setProjectionPlanCount(plans.count);
        setProfileProjection(projectProductionProfiles(stages.items, plans.items));
        setProjectionState("ready");
      })
      .catch((cause) => {
        if (cancelled) return;
        setProfileProjection([]);
        setProjectionStageCount(0);
        setProjectionPlanCount(0);
        setProjectionError(cause instanceof Error ? cause.message : String(cause));
        setProjectionState("error");
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setAgentReadySummary((prev) => ({ ...prev, state: "loading", error: "" }));
    void aipAgentControl.runtimeReadiness()
      .then((ready) => {
        if (cancelled) return;
        setAgentReadySummary({
          installed: ready.catalog.stats.installedCount,
          dispatchable: ready.catalog.stats.runnableCount,
          state: "ready",
          error: "",
        });
      })
      .catch((cause) => {
        if (cancelled) return;
        setAgentReadySummary({
          installed: 0,
          dispatchable: 0,
          state: "error",
          error: cause instanceof Error ? cause.message : String(cause),
        });
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const generation = ++requestGeneration.current;
    runRequestGeneration.current += 1;
    detailRequestGeneration.current += 1;
    setSelectedNodeId("");
    setUndoStack([]);
    setRedoStack([]);
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
    setEvalSuites([]);
    setSelectedEvalSuiteId("");
    setEvalReport(null);
    setEvalEvidenceState(activeFlowId ? "loading" : "idle");
    setEvalEvidenceError("");
    setPublications([]);
    setPublicationsState(activeFlowId ? "loading" : "idle");
    setPublicationsError("");
    setPublication(null);
    setPublicationState("idle");
    setPublicationError("");
    setSelectedPublicationId(null);
    setPublishing(false);
    if (!activeFlowId && explicitNewDraft) {
      setGraph(cloneGraph(templateRef.current!));
      setDirty(true);
      setLoading(false);
      return;
    }

    if (!activeFlowId) {
      setGraph(null);
      setDirty(false);
      setLoading(true);
      void listLogicGraphs()
        .then((response) => {
          if (requestGeneration.current !== generation) return;
          const selected = response.items.find((item) => item.persisted && item.revision > 0);
          if (!selected) {
            setGraph(null);
            setHistoryState("idle");
            setEvalEvidenceState("idle");
            setPublicationsState("idle");
            return;
          }
          setGraph(selected);
          setDirty(false);
          setHistoryState("loading");
          setEvalEvidenceState("loading");
          setPublicationsState("loading");
          const next = new URLSearchParams(searchParams);
          next.delete("new");
          const query = next.toString();
          navigate({
            pathname: `/aip/logic/${encodeURIComponent(selected.id)}`,
            search: query ? `?${query}` : "",
          }, { replace: true });
          void loadPublicationPrerequisites(selected, generation);
          void listLogicRuns(selected.id, { limit: HISTORY_PAGE_SIZE })
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
        .catch((listError: unknown) => {
          if (requestGeneration.current !== generation) return;
          setError(`Logic Graph 列表读取失败：${errorMessage(listError)}`);
        })
        .finally(() => {
          if (requestGeneration.current === generation) setLoading(false);
        });
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
        void loadPublicationPrerequisites(loaded, generation);
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
  }, [activeFlowId, explicitNewDraft]);

  function selectShellTab(nextTab: ShellTab): void {
    const next = new URLSearchParams(searchParams);
    if (nextTab === "edit") next.delete("tab");
    else next.set("tab", nextTab);
    setSearchParams(next, { replace: true });
  }

  function handleShellTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, currentTab: ShellTab): void {
    const currentIndex = SHELL_TABS.indexOf(currentTab);
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % SHELL_TABS.length;
    if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + SHELL_TABS.length) % SHELL_TABS.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = SHELL_TABS.length - 1;
    if (nextIndex === null) return;
    event.preventDefault();
    const nextTab = SHELL_TABS[nextIndex];
    selectShellTab(nextTab);
    requestAnimationFrame(() => tabRefs.current[nextTab]?.focus());
  }

  function startNewDraft(): void {
    if (dirty) return;
    const next = new URLSearchParams(searchParams);
    next.delete("tab");
    next.set("new", "1");
    navigate({ pathname: "/aip/logic", search: `?${next.toString()}` });
  }

  async function loadPublicationPrerequisites(
    targetGraph: LogicGraphSnapshot,
    generation = requestGeneration.current,
  ): Promise<void> {
    setEvalEvidenceState("loading");
    setEvalEvidenceError("");
    setPublicationsState("loading");
    setPublicationsError("");
    const [suiteResult, publicationResult] = await Promise.allSettled([
      apiGet<{ items: EvalSuiteOption[] }>("/v1/evals/suites"),
      listLogicPublications(targetGraph.id),
    ]);
    if (requestGeneration.current !== generation) return;
    if (suiteResult.status === "fulfilled") {
      const items = Array.isArray(suiteResult.value.items) ? suiteResult.value.items : [];
      setEvalSuites(items);
      setSelectedEvalSuiteId((current) => current || items[0]?.id || "");
      setEvalEvidenceState("ready");
    } else {
      setEvalEvidenceState("error");
      setEvalEvidenceError(errorMessage(suiteResult.reason));
    }
    if (publicationResult.status === "fulfilled") {
      setPublications(publicationResult.value.items);
      setPublicationsState("ready");
    } else {
      setPublicationsState("error");
      setPublicationsError(errorMessage(publicationResult.reason));
    }
  }

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
                    ? "请先显式应用安全试跑输入"
                    : "";

  function mutateGraph(mutator: (current: LogicGraphSnapshot) => LogicGraphSnapshot): void {
    setGraph((current) => {
      if (!current) return current;
      const next = mutator(current);
      if (JSON.stringify(next) === JSON.stringify(current)) return current;
      setUndoStack((stack) => [...stack.slice(-49), cloneGraph(current)]);
      setRedoStack([]);
      return next;
    });
    setDirty(true);
    setError("");
    setMessage("");
  }

  function undoGraph(): void {
    const previous = undoStack.at(-1);
    if (!graph || !previous) return;
    setRedoStack((stack) => [...stack.slice(-49), cloneGraph(graph)]);
    setUndoStack((stack) => stack.slice(0, -1));
    setGraph(cloneGraph(previous));
    setDirty(true);
    setError("");
    setMessage("已撤销最近一次画布修改");
  }

  function redoGraph(): void {
    const next = redoStack.at(-1);
    if (!graph || !next) return;
    setUndoStack((stack) => [...stack.slice(-49), cloneGraph(graph)]);
    setRedoStack((stack) => stack.slice(0, -1));
    setGraph(cloneGraph(next));
    setDirty(true);
    setError("");
    setMessage("已重做最近一次画布修改");
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
      setUndoStack([]);
      setRedoStack([]);
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
      setUndoStack([]);
      setRedoStack([]);
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
        throw new Error("试跑输入必须是 JSON 对象");
      }
      setAppliedInputs(parsed as JsonObject);
      setInputsError("");
      setMessage("安全试跑输入已显式应用；未写入业务逻辑图");
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

  async function loadEvalEvidence(): Promise<void> {
    if (!graph?.persisted || !selectedEvalSuiteId) return;
    const generation = requestGeneration.current;
    const graphId = graph.id;
    const revision = graph.revision;
    const graphHash = graph.graph_hash;
    setEvalReport(null);
    setEvalEvidenceState("loading");
    setEvalEvidenceError("");
    try {
      const report = await apiGet<LogicEvalReport>(`/v1/evals/${encodeURIComponent(selectedEvalSuiteId)}/report`);
      const suite = evalSuites.find((item) => item.id === selectedEvalSuiteId);
      if (!suite) throw new Error("所选 Eval suite 不在服务端列表中");
      if (
        report.suite_id !== selectedEvalSuiteId
        || report.target_type !== "logic_graph"
        || report.target_id !== graphId
        || report.target_revision !== revision
        || report.target_hash !== graphHash
      ) throw new Error("Eval report 未绑定当前 Logic revision/hash");
      if (!report.report_id || report.total < 1 || report.passed + report.failed !== report.total) {
        throw new Error("Eval report 证据不完整");
      }
      if (!report.gate_passed || report.pass_rate < suite.gate_threshold) {
        throw new Error("Eval 门控未通过，禁止发布");
      }
      if (requestGeneration.current !== generation) return;
      setEvalReport(report);
      setEvalEvidenceState("ready");
    } catch (loadError: unknown) {
      if (requestGeneration.current !== generation) return;
      setEvalEvidenceState("error");
      setEvalEvidenceError(errorMessage(loadError));
    }
  }

  async function loadPublication(publicationId: string): Promise<void> {
    if (!graph?.persisted) return;
    const generation = requestGeneration.current;
    setSelectedPublicationId(publicationId);
    setPublication(null);
    setPublicationState("loading");
    setPublicationError("");
    try {
      const detail = await getLogicPublication(graph.id, publicationId);
      if (requestGeneration.current !== generation) return;
      setPublication(detail);
      setPublicationState("ready");
    } catch (loadError: unknown) {
      if (requestGeneration.current !== generation) return;
      setPublicationState("error");
      setPublicationError(errorMessage(loadError));
    }
  }

  async function refreshPublications(): Promise<void> {
    if (!graph?.persisted) return;
    const generation = requestGeneration.current;
    setPublicationsState("loading");
    setPublicationsError("");
    try {
      const response = await listLogicPublications(graph.id);
      if (requestGeneration.current !== generation) return;
      setPublications(response.items);
      setPublicationsState("ready");
    } catch (loadError: unknown) {
      if (requestGeneration.current !== generation) return;
      setPublicationsState("error");
      setPublicationsError(errorMessage(loadError));
    }
  }

  const publicationDisabledReason = loading
    ? "Logic Graph 正在加载"
    : !graph?.persisted
      ? "请先保存 Logic Graph"
      : saving || running
        ? "请等待保存或安全试跑完成"
        : dirty
          ? "存在未保存更改，请先保存并完成回读"
          : publishing
            ? "发布请求正在处理"
            : !evalReport
              ? evalEvidenceError || "请读取与当前修订和内容摘要绑定且通过的评测报告"
              : "";

  const publicationEvalGate: LogicPublicationEvalGate | null = evalReport ? {
    gate_passed: true,
    pass_rate: evalReport.pass_rate,
    threshold: evalSuites.find((item) => item.id === evalReport.suite_id)?.gate_threshold ?? 1,
    passed: evalReport.passed,
    failed: evalReport.failed,
    total: evalReport.total,
    run_at: evalReport.run_at,
  } : null;

  async function publishCurrentRevision(): Promise<void> {
    if (!graph?.persisted || !evalReport || publicationDisabledReason || publishing) return;
    const generation = requestGeneration.current;
    const graphId = graph.id;
    const revision = graph.revision;
    const graphHash = graph.graph_hash;
    setPublishing(true);
    setPublicationError("");
    setPublicationState("loading");
    setMessage("");
    try {
      const detail = await publishLogicGraph(graphId, {
        expected_revision: revision,
        expected_graph_hash: graphHash,
        eval_suite_id: evalReport.suite_id,
        eval_report_id: evalReport.report_id,
        idempotency_key: `logic-publish-${revision}-${graphHash.slice(0, 12)}-${evalReport.report_id}`.slice(0, 160),
      });
      const rereadGraph = await getLogicGraph(graphId);
      if (rereadGraph.revision !== revision || rereadGraph.graph_hash !== graphHash || rereadGraph.published_version !== revision) {
        throw new Error("发布后 Graph 回读未确认 published_version");
      }
      if (requestGeneration.current !== generation) return;
      setGraph(rereadGraph);
      setDirty(false);
      setPublication(detail);
      setPublicationState("ready");
      setSelectedPublicationId(detail.publication_id);
      setPublications((items) => [detail, ...items.filter((item) => item.publication_id !== detail.publication_id)]);
      setPublicationsState("ready");
      setMessage(`已发布并回读确认 · revision ${revision} · ${detail.publication_id}`);
    } catch (publishError: unknown) {
      if (requestGeneration.current !== generation) return;
      setPublicationState("error");
      setPublicationError(errorMessage(publishError));
    } finally {
      if (requestGeneration.current === generation) setPublishing(false);
    }
  }

  async function restorePublicationAsDraft(publicationId: string): Promise<void> {
    if (!graph?.persisted || dirty || saving || running || publishing || restoringPublication) return;
    const generation = ++requestGeneration.current;
    setRestoringPublication(true);
    setError("");
    setMessage("");
    try {
      const restored = await restoreLogicPublication(graph.id, publicationId, graph);
      if (requestGeneration.current !== generation) return;
      setGraph(restored);
      setDirty(false);
      setUndoStack([]);
      setRedoStack([]);
      setEvalReport(null);
      setEvalEvidenceState("idle");
      setEvalEvidenceError("");
      setRun(null);
      setRunState("idle");
      setSelectedRunId(null);
      setMessage(`已从不可变发布记录恢复为新草稿修订 · revision ${restored.revision}`);
      void refreshHistory();
    } catch (restoreError: unknown) {
      if (requestGeneration.current !== generation) return;
      setError(`恢复失败：${errorMessage(restoreError)}`);
    } finally {
      if (requestGeneration.current === generation) setRestoringPublication(false);
    }
  }

  return (
    <PageChrome
      title="逻辑编排"
      lede="用自由画布编排权威业务逻辑；保存后必须与服务端严格回读一致。编辑、运行历史和自动化分区各司其职。"
    >
      <div role="tablist" aria-label="逻辑页分区" style={{ display: "flex", gap: 6, marginBottom: 12, flexWrap: "wrap" }}>
        {(
          [
            ["edit", "编辑"],
            ["history", "运行历史"],
            ["automation", "自动化"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            id={`logic-tab-${id}`}
            type="button"
            role="tab"
            aria-selected={shellTab === id}
            aria-controls={`logic-panel-${id}`}
            tabIndex={shellTab === id ? 0 : -1}
            ref={(node) => { tabRefs.current[id] = node; }}
            className="btn"
            style={{
              borderBottom: shellTab === id ? "2px solid var(--aos-indigo-600,#4f46e5)" : "2px solid transparent",
              borderRadius: 0,
              fontWeight: shellTab === id ? 700 : 500,
            }}
            onClick={() => selectShellTab(id)}
            onKeyDown={(event) => handleShellTabKeyDown(event, id)}
          >
            {label}
          </button>
        ))}
      </div>

      <div
        data-testid="logic-ops-stats"
        style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(110px,1fr))", gap: 10, marginBottom: 12 }}
      >
        {[
          { label: "分区", value: shellTab === "edit" ? "编辑" : shellTab === "history" ? "历史" : "自动化" },
          { label: "图", value: graph?.persisted ? "已确认" : graph ? "未确认" : "未载" },
          { label: "历史条", value: String(history.length) },
          { label: "生产流程", value: projectionState === "ready" ? String(profileProjection.length) : projectionState === "loading" ? "…" : "—" },
          { label: "更多", value: historyCursor ? "有" : "无" },
          { label: "互跳", value: shellTab === "automation" ? "草稿/评测" : "观测/谱系" },
        ].map((s) => (
          <div key={s.label} className="card" style={{ padding: "10px 12px" }}>
            <div style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>{s.label}</div>
            <div style={{ fontSize: 18, fontWeight: 700 }}>{s.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 12 }}>
        <button
          type="button"
          className="btn"
          disabled={dirty || loading || saving || running || explicitNewDraft}
          title={dirty ? "请先保存或刷新当前草稿" : "显式创建本地草稿；默认入口不会自动生成模板"}
          onClick={startNewDraft}
        >
          新建业务逻辑草稿
        </button>
      </div>

      {shellTab === "edit" ? (
      <div role="tabpanel" id="logic-panel-edit" aria-labelledby="logic-tab-edit">
      <div
        className="notice"
        role="note"
        data-testid="logic-no-production-bypass"
        style={{ padding: 12, marginBottom: 12, borderLeft: "3px solid var(--aos-amber-700,#b45309)" }}
      >
        <strong>生产旁路已关闭：</strong>
        本画布不提供「一键创建 / 批准生产任务」。请经{" "}
        <Link to="/aip/drafts">草稿审批台</Link>
        {" · "}
        <Link to="/aip/evals">评测门控</Link>
        {" · "}
        <Link to="/aip/production-contracts">上线执行审批</Link>
        {" "}完成发布与启动；安全试跑不写生产。
      </div>
      <div
        className="notice"
        role="note"
        data-testid="logic-agent-readiness-summary"
        style={{ padding: 12, marginBottom: 12, borderLeft: "3px solid var(--aos-border)" }}
      >
        <strong>数字同事就绪（只读）：</strong>
        {agentReadySummary.state === "loading" && "正在读取目录…"}
        {agentReadySummary.state === "error" && `读取失败（未伪造可派发）：${agentReadySummary.error}`}
        {agentReadySummary.state === "ready" && (
          <>
            已安装 {agentReadySummary.installed} · 可派发 {agentReadySummary.dispatchable}
            {agentReadySummary.installed > agentReadySummary.dispatchable
              ? " · 已安装≠可派发"
              : agentReadySummary.dispatchable === 0
                ? " · 尚无可派发同事"
                : ""}
            {" · "}
            <Link to="/aip/agent-registry">打开智能体目录</Link>
          </>
        )}
      </div>
      <div
        className="notice"
        role="region"
        aria-label="上线执行审批只读投影"
        data-testid="logic-production-projection"
        style={{ padding: 12, marginBottom: 12, border: "1px solid var(--aos-border)" }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <strong>可被引用的生产流程（只读）</strong>
          <Link to="/aip/production-contracts" data-testid="logic-projection-jump-contracts" style={{ fontSize: 12 }}>
            打开上线执行审批 →
          </Link>
        </div>
        <p style={{ margin: "6px 0 0", fontSize: 12, color: "var(--aos-muted)" }}>
          来自阶段模板和职责计划权威表；空表不伪造生产流程，画布不可由此旁路启动生产。
        </p>
        {projectionState === "loading" && <p style={{ marginTop: 8, fontSize: 12 }} data-testid="logic-projection-loading">正在读取上线执行审批…</p>}
        {projectionError && (
          <p role="alert" style={{ marginTop: 8, fontSize: 12, color: "var(--aos-amber-700)" }} data-testid="logic-projection-error">
            投影读取失败：{projectionError}。未注入演示生产流程。
          </p>
        )}
        {projectionState === "ready" && productionProjectionEmptyMessage(projectionStageCount, projectionPlanCount) && (
          <p style={{ marginTop: 8, fontSize: 12 }} data-testid="logic-projection-empty">
            {productionProjectionEmptyMessage(projectionStageCount, projectionPlanCount)}
          </p>
        )}
        {profileProjection.length > 0 && (
          <ul style={{ margin: "8px 0 0", paddingLeft: 18, fontSize: 13 }} data-testid="logic-projection-profiles">
            {profileProjection.map((row) => (
              <li key={row.profile}>
                <strong>{businessDisplayName(row.profile, "生产流程")}</strong>
                {" · "}阶段 {row.stageReady}/{row.stageCount} 就绪
                {" · "}职责 {row.planReady}/{row.planCount} 就绪
              </li>
            ))}
          </ul>
        )}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
        <button
          type="button"
          className="btn btn-primary"
          disabled={!graph || loading || saving || running || !dirty}
          title={!graph ? "请先新建或选择业务逻辑草稿" : loading ? "正在读取权威业务逻辑" : saving ? "正在保存并回读确认" : running ? "安全试跑结束后可继续保存" : !dirty ? "当前没有需要保存的更改" : "保存并回读确认当前修订"}
          onClick={() => void saveGraph()}
        >
          {saving ? "保存并回读中…" : `保存${dirty ? " *" : ""}`}
        </button>
        <button type="button" className="btn" disabled={!graph || loading || saving || running} onClick={() => void refreshGraph()}>
          {loading ? "读取中…" : "刷新"}
        </button>
        <button type="button" className="btn" disabled={!graph || loading || saving || running || undoStack.length === 0} onClick={undoGraph}>撤销</button>
        <button type="button" className="btn" disabled={!graph || loading || saving || running || redoStack.length === 0} onClick={redoGraph}>重做</button>
        <button
          type="button"
          className="btn"
          disabled={Boolean(dryRunDisabledReason)}
          title={dryRunDisabledReason || "使用已确认修订和内容摘要进行只读安全试跑"}
          onClick={() => void runDryRun()}
        >
          {running ? "安全试跑中…" : "安全试跑"}
        </button>
        <span data-testid="dry-run-gate-reason" style={{ color: dryRunDisabledReason ? "var(--aos-muted)" : "var(--aos-green-700)", fontSize: "0.72rem" }}>
          {dryRunDisabledReason || "已满足可信试跑门禁"}
        </span>
        <Link to="/aip/drafts" className="btn" style={{ textDecoration: "none" }}>草稿审批台</Link>
        <Link to="/aip/evals" className="btn" style={{ textDecoration: "none" }}>评测门控</Link>
        <span style={{ marginLeft: "auto", fontSize: "0.76rem", color: dirty ? "var(--aos-amber-700)" : "var(--aos-green-700)" }}>
          {dirty ? "未保存更改" : graph ? `已确认修订 ${graph.revision}` : "未加载"}
        </span>
      </div>

      {graph && (
        <div style={{ display: "grid", gridTemplateColumns: "minmax(220px, 1fr) minmax(220px, 1fr)", gap: 8, marginBottom: 10 }}>
          <label style={{ fontSize: "0.75rem" }}>
            业务逻辑名称
            <input
              aria-label="业务逻辑名称"
              value={graph.name}
              disabled={loading || saving || running}
              onChange={(event) => mutateGraph((current) => ({ ...current, name: event.target.value }))}
              style={{ display: "block", width: "100%", marginTop: 3 }}
            />
          </label>
          <label style={{ fontSize: "0.75rem" }}>
            描述
            <input
              aria-label="业务逻辑描述"
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
          未保存模板：当前 4 个节点、3 条连接仅在本地；点击“保存”后显式创建服务端业务逻辑图。
        </div>
      )}
      {error && <div role="alert" style={{ background: "var(--aos-red-bg)", color: "var(--aos-red)", padding: "8px 12px", marginBottom: 10 }}>{error}</div>}
      {message && <div role="status" style={{ background: "var(--aos-green-bg)", color: "var(--aos-green-700)", padding: "8px 12px", marginBottom: 10 }}>{message}</div>}

      {graph && (
        <section style={{ border: "1px solid var(--aos-border)", padding: 12, borderRadius: 2, marginBottom: 10 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 6 }}>
            <div>
              <h3 style={{ margin: 0, fontSize: "0.84rem" }}>安全试运行输入</h3>
              <p style={{ margin: "3px 0 0", color: "var(--aos-muted)", fontSize: "0.72rem" }}>独立 JSON 对象；仅显式应用后用于安全试跑，不写入画布或生产数据。</p>
            </div>
            <button type="button" className="btn" disabled={loading || saving || running} onClick={applyDryRunInputs}>应用试跑输入</button>
          </div>
          <textarea
            aria-label="安全试跑输入 JSON"
            className="aos-input"
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
            style={{ display: "block", width: "100%", height: "auto", resize: "vertical", fontFamily: "monospace" }}
          />
          {inputsError && <div role="alert" style={{ marginTop: 6, color: "var(--aos-red)", fontSize: "0.74rem" }}>{inputsError}</div>}
          <div role="status" style={{ marginTop: 6, color: appliedInputs === null ? "var(--aos-muted)" : "var(--aos-green-700)", fontSize: "0.72rem" }}>
            {appliedInputs === null ? "试跑输入尚未应用" : "试跑输入已显式应用"}
          </div>
        </section>
      )}

      {loading && !graph && <p>正在加载权威业务逻辑…</p>}
      {!loading && !graph && !error && (
        <section className="card" style={{ padding: 18 }} data-testid="logic-honest-empty">
          <h2 style={{ marginTop: 0 }}>尚无已保存业务逻辑</h2>
          <p style={{ color: "var(--aos-text-secondary)" }}>
            当前组织/工作区没有可选择的已保存修订。默认入口不会生成演示图；如需创建，请显式点击“新建业务逻辑草稿”。
          </p>
        </section>
      )}

      {graph && (
        <LogicGraphCanvas
          nodes={graph.nodes}
          edges={graph.edges}
          selectedNodeId={selectedNodeId}
          nodeRunStates={nodeRunStates}
          zoom={zoom}
          inspectorCollapsed={inspectorCollapsed}
          disabled={loading || saving || running}
          onNodesChange={(nodes) => mutateGraph((current) => {
            const nodeIds = new Set(nodes.map((node) => node.id));
            const retainedEntries = current.entry_node_ids.filter((nodeId) => nodeIds.has(nodeId));
            const fallbackEntry = nodes.find((node) => node.kind === "input")?.id ?? nodes[0]?.id;
            return {
              ...current,
              nodes,
              entry_node_ids: retainedEntries.length > 0 || !fallbackEntry ? retainedEntries : [fallbackEntry],
            };
          })}
          onEdgesChange={(edges) => mutateGraph((current) => ({ ...current, edges }))}
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
              onNodeChange={(node) => mutateGraph((current) => ({
                ...current,
                nodes: current.nodes.map((candidate) => candidate.id === node.id ? node : candidate),
              }))}
              onEntryNodeIdsChange={(entryNodeIds) => mutateGraph((current) => ({
                ...current,
                entry_node_ids: entryNodeIds,
              }))}
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
        {graph?.persisted && (
          <CanonicalTaskRunPanel
            graphId={graph.id}
            graphRevision={graph.revision}
            graphName={graph.name}
          />
        )}
        {graph?.persisted && (
          <section style={{ border: "1px solid var(--aos-border)", padding: 12, borderRadius: 2 }}>
            <div style={{ display: "flex", alignItems: "end", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
              <label style={{ display: "grid", gap: 3, fontSize: "0.72rem" }}>
                发布 Eval suite
                <select
                  aria-label="发布 Eval suite"
                  value={selectedEvalSuiteId}
                  disabled={publishing || evalEvidenceState === "loading"}
                  onChange={(event) => {
                    setSelectedEvalSuiteId(event.target.value);
                    setEvalReport(null);
                    setEvalEvidenceError("");
                    setEvalEvidenceState("ready");
                  }}
                >
                  <option value="">选择评测套件</option>
                  {evalSuites.map((suite) => <option key={suite.id} value={suite.id}>{suite.name} · {suite.id}</option>)}
                </select>
              </label>
              <button type="button" className="btn" disabled={!selectedEvalSuiteId || publishing || evalEvidenceState === "loading"} onClick={() => void loadEvalEvidence()}>
                {evalEvidenceState === "loading" ? "读取证据中…" : "读取当前版本 Eval 证据"}
              </button>
              {evalEvidenceError && <span role="alert" style={{ color: "var(--aos-red)", fontSize: "0.72rem" }}>{evalEvidenceError}</span>}
            </div>
            <LogicPublicationPanel
              graphId={graph.id}
              graphRevision={graph.revision}
              graphHash={graph.graph_hash}
              evalSuiteId={evalReport?.suite_id || selectedEvalSuiteId || null}
              evalReportId={evalReport?.report_id || null}
              evalGate={publicationEvalGate}
              publishDisabledReason={publicationDisabledReason}
              publishing={publishing}
              restoring={restoringPublication}
              publication={publication}
              publicationState={publicationState}
              publicationError={publicationError}
              publications={publications}
              publicationsState={publicationsState}
              publicationsError={publicationsError}
              selectedPublicationId={selectedPublicationId}
              onPublish={() => void publishCurrentRevision()}
              onRestorePublication={(publicationId) => void restorePublicationAsDraft(publicationId)}
              onSelectPublication={(publicationId) => void loadPublication(publicationId)}
              onRetryPublication={selectedPublicationId ? () => void loadPublication(selectedPublicationId) : undefined}
              onRetryPublications={() => void refreshPublications()}
            />
          </section>
        )}
      </div>
      </div>
      ) : null}

      {shellTab === "history" ? (
        <div style={{ display: "grid", gap: 10 }} role="tabpanel" id="logic-panel-history" aria-labelledby="logic-tab-history">
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {selectedRunId ? (
              <Link
                to={`/aip/lineage?rootType=task_run&rootId=${encodeURIComponent(selectedRunId)}`}
                className="btn"
                style={{ textDecoration: "none" }}
                data-testid="history-jump-lineage"
              >
                当前 Run 谱系与可观测 →
              </Link>
            ) : (
              <span className="muted" data-testid="history-lineage-blocked" title="先选择真实 TaskRun，再从谱系进入可观测证据">
                选择 Run 后查看谱系与可观测
              </span>
            )}
            <Link to="/aip/evals" className="btn" style={{ textDecoration: "none" }}>评测门控 →</Link>
          </div>
          {graph?.persisted && <LogicRevisionHistoryPanel graphId={graph.id} />}
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
              <p style={{ margin: 0, color: "var(--aos-muted)", fontSize: "0.75rem" }}>保存并回读确认后，才从服务端读取不可变运行历史；不伪造运行列表。</p>
            </section>
          )}
        </div>
      ) : null}

      {shellTab === "automation" ? (
        <LogicAutomationPanel
          graphId={graph?.id || ""}
          graphRevision={graph?.revision || 0}
          graphHash={graph?.graph_hash || ""}
          persisted={Boolean(graph?.persisted)}
          publications={publications}
        />
      ) : null}
    </PageChrome>
  );
}
