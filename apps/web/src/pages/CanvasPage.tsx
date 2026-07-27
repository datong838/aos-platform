import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPatch, apiPost } from "../api/client";
import { PageChrome } from "../components/PageChrome";
import { NavIcon } from "../shell/icons";
import { BpBanner } from "./s2/blueprintUi";
import { ActionFormWidget, GraphViewWidget, MetricCardWidget, resolveRenderKind } from "./canvasWidgets";
import { ComponentRenderer, type ComponentTree } from "./ComponentRenderer";
import { ComponentTreeEditor } from "./ComponentTreeEditor";
import {
  DashboardTab,
  DataTab,
  DependenciesTab,
  EventsTab,
  FunctionsTab,
  QueriesTab,
  StylesTab,
  VariablesTab,
  WorkflowMode,
} from "./CanvasTabs";
import {
  DndContext,
  DragOverlay,
  pointerWithin,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  useDraggable,
  useDroppable,
  type DragStartEvent,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

export type CanvasKind =
  | "table"
  | "filter"
  | "buddy"
  | "overlay"
  | "stub"
  | "action"
  | "graph"
  | "metric"
  | "page-header"
  | "stat-card"
  | "filter-bar"
  | "detail-drawer"
  | "trend-chart";

export type CanvasNode = {
  id: string;
  kind: CanvasKind;
  title: string;
  pluginId?: string;
  config?: {
    site?: string;
    objectType?: string;
    objectId?: string;
    actionTypeId?: string;
    groupBy?: string;
    title?: string;
    subtitle?: string;
    icon?: string;
    metric?: string;
    field?: string;
    filter?: Record<string, unknown>;
    tabs?: Array<Record<string, unknown>>;
    search?: Record<string, unknown>;
    filters?: Array<Record<string, unknown>>;
    width?: number;
    sections?: Array<Record<string, unknown>>;
    actions?: Array<Record<string, unknown>>;
    dateField?: string;
    days?: number;
    endDate?: string;
    [key: string]: unknown;
  };
};

type PaletteItem = {
  kind: CanvasKind;
  label: string;
  tone?: "violet";
  pluginId?: string;
  runtime?: string;
  stub?: boolean;
};

const DEFAULT_LAYOUT: CanvasNode[] = [
  { id: "n-filter", kind: "filter", title: "Filter · site", pluginId: "filter-list", config: { site: "DC-East" } },
  {
    id: "n-table",
    kind: "table",
    title: "Object Table · WorkOrder",
    pluginId: "object-table",
    config: { objectType: "WorkOrder" },
  },
  { id: "n-buddy", kind: "buddy", title: "Buddy Chip", pluginId: "buddy-chip" },
];

type ModuleRow = {
  id: string;
  name: string;
  widgets?: unknown[];
  components?: ComponentTree;
  objectType?: string;
};

type Row = {
  objectId?: string;
  id?: string;
  props?: Record<string, unknown>;
  title?: string;
  status?: string;
  site?: string;
};

const KIND_SET = new Set<CanvasKind>([
  "table",
  "filter",
  "buddy",
  "overlay",
  "stub",
  "action",
  "graph",
  "metric",
  "page-header",
  "stat-card",
  "filter-bar",
  "detail-drawer",
  "trend-chart",
]);

/** Widget emoji 图标映射 · 由 kind 查 emoji（唯一来源：palette API） */
const KIND_ICON: Record<CanvasKind, string> = {
  table: "📊",
  graph: "📈",
  action: "📝",
  stub: "🔘",
  overlay: "🗺",
  metric: "📄",
  filter: "🔽",
  buddy: "💬",
  "page-header": "🏷",
  "stat-card": "🔢",
  "filter-bar": "📋",
  "detail-drawer": "🗂",
  "trend-chart": "📉",
};

export function normalizeLayout(widgets: unknown, objectType?: string): CanvasNode[] {
  if (!Array.isArray(widgets) || widgets.length === 0) return structuredClone(DEFAULT_LAYOUT);
  if (typeof widgets[0] === "string") {
    return (widgets as string[]).map((w, i) => {
      const lower = w.toLowerCase();
      const kind: CanvasKind = lower.includes("filter")
        ? "filter"
        : lower.includes("buddy") || lower.includes("chat")
          ? "buddy"
          : lower.includes("action")
            ? "action"
            : lower.includes("graph") || lower.includes("chart") || lower.includes("trend")
              ? "graph"
              : lower.includes("metric") || lower.includes("stat") || lower.includes("kpi")
                ? "metric"
                : lower.includes("overlay") || lower.includes("detail") || lower.includes("drawer") || (lower.includes("view") && !lower.includes("graph"))
                  ? "overlay"
                  : lower.includes("stub")
                    ? "stub"
                    : lower.includes("header") || lower.includes("page")
                      ? "page-header"
                      : "table";
      const objType = objectType || "WorkOrder";
      return {
        id: `n-${i}-${kind}`,
        kind,
        title: w,
        pluginId:
          kind === "action"
            ? "action-form"
            : kind === "graph"
              ? "graph-view"
              : kind === "metric"
                ? "metric-card"
                : undefined,
        config:
          kind === "filter"
            ? { site: "DC-East" }
            : kind === "table"
              ? { objectType: objType }
              : kind === "action"
                ? { actionTypeId: "CloseWorkOrder" }
                : kind === "graph"
                  ? { objectType: objType, objectId: "wo-1001" }
                  : kind === "metric"
                    ? { objectType: objType, groupBy: "status" }
                    : kind === "overlay"
                      ? { objectType: objType, objectId: "wo-1001" }
                      : undefined,
      };
    });
  }
  return (widgets as CanvasNode[]).map((n, i) => {
    const rawKind = (KIND_SET.has(n.kind as CanvasKind) ? n.kind : "table") as CanvasKind;
    const kind = resolveRenderKind({ kind: rawKind, pluginId: n.pluginId }) as CanvasKind;
    return {
      id: n.id || `n-${i}`,
      kind,
      title: n.title || n.kind || `node-${i}`,
      pluginId: n.pluginId,
      config: n.config,
    };
  });
}

const FALLBACK_PALETTE: PaletteItem[] = [
  { kind: "filter", label: "+ Filter List", pluginId: "filter-list" },
  { kind: "table", label: "+ Object Table", pluginId: "object-table" },
  { kind: "buddy", label: "+ Buddy Chip", pluginId: "buddy-chip" },
  { kind: "overlay", label: "+ Object View · Wiki", tone: "violet", pluginId: "object-view" },
];

function sectionLabel(kind: CanvasKind): string {
  if (kind === "filter") return "筛选";
  if (kind === "table") return "主表";
  if (kind === "buddy") return "Buddy";
  if (kind === "action") return "Action 表单";
  if (kind === "graph") return "关系图";
  if (kind === "metric") return "指标卡";
  if (kind === "stub") return "Stub 插件";
  if (kind === "page-header") return "页面头";
  if (kind === "stat-card") return "统计卡";
  if (kind === "filter-bar") return "筛选栏";
  if (kind === "detail-drawer") return "详情抽屉";
  if (kind === "trend-chart") return "趋势图";
  return "Overlay 详情";
}

function WidgetPreview({
  node,
  rows,
  onConfig,
}: {
  node: CanvasNode;
  rows: Row[];
  onConfig?: (patch: Partial<NonNullable<CanvasNode["config"]>>) => void;
}) {
  const renderKind = resolveRenderKind(node) as CanvasKind;
  if (renderKind === "action") {
    return (
      <ActionFormWidget
        node={node}
        onConfig={onConfig ? (p) => onConfig(p) : undefined}
      />
    );
  }
  if (renderKind === "graph") {
    const fallbackId = String(rows[0]?.id || rows[0]?.objectId || "wo-1001");
    return (
      <GraphViewWidget
        node={node}
        fallbackObjectId={fallbackId}
        onConfig={onConfig ? (p) => onConfig(p) : undefined}
      />
    );
  }
  if (renderKind === "metric") {
    return (
      <MetricCardWidget
        node={node}
        onConfig={onConfig ? (p) => onConfig(p) : undefined}
      />
    );
  }
  if (renderKind === "stub") {
    return (
      <div className="bp-canvas-widget">
        <BpBanner tone="warn">
          <strong>{node.title || node.pluginId || "Widget"}</strong>
          <p className="muted" style={{ margin: "0.35rem 0 0", fontSize: "0.8rem" }}>
            runtime=stub · pluginId={node.pluginId || "—"} · 尚未实现真渲染
          </p>
        </BpBanner>
      </div>
    );
  }
  if (node.kind === "filter") {
    return (
      <div className="bp-canvas-widget">
        <span className="bp-tag">Filter List</span>
        <span className="muted">site = {node.config?.site || "DC-East"}</span>
      </div>
    );
  }
  if (node.kind === "table") {
    const previewRows = rows.slice(0, 3);
    return (
      <div className="bp-canvas-widget bp-canvas-widget-table">
        <div className="bp-canvas-widget-row bp-canvas-widget-head">
          <span>id</span>
          <span>title</span>
          <span>status</span>
        </div>
        {previewRows.length === 0 ? (
          <div className="bp-canvas-widget-row muted">
            <span>—</span>
            <span>无预览行 · 刷新 Object Table</span>
            <span>—</span>
          </div>
        ) : (
          previewRows.map((row, i) => {
            const id = String(row.id || row.objectId || `row-${i}`);
            const title = String(row.title || (row.props?.title as string) || "—");
            const status = String(row.status || (row.props?.status as string) || "—");
            return (
              <div key={id} className="bp-canvas-widget-row muted">
                <span>{id}</span>
                <span>{title}</span>
                <span>{status}</span>
              </div>
            );
          })
        )}
      </div>
    );
  }
  if (node.kind === "buddy") {
    return (
      <div className="bp-canvas-widget bp-canvas-widget-buddy">
        <span className="bp-tag bp-tag-ok">Buddy</span>
        <span className="muted">Assist · 选中 Object 上下文</span>
      </div>
    );
  }
  if (node.kind === "page-header") {
    return (
      <div className="bp-canvas-widget">
        <strong style={{ fontSize: "1.05rem" }}>{node.config?.title || "页面标题"}</strong>
        <span className="muted" style={{ display: "block", marginTop: 4 }}>
          {node.config?.subtitle || "副标题"}
        </span>
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          {(node.config?.actions as Array<{ label?: string; variant?: string }> | undefined)?.map((a, i) => (
            <span
              key={i}
              className="bp-tag"
              style={{
                background: a?.variant === "primary" ? "var(--aos-accent)" : undefined,
                color: a?.variant === "primary" ? "var(--text-on-brand)" : undefined,
              }}
            >
              {a?.label || `按钮${i + 1}`}
            </span>
          )) || <span className="muted">无操作按钮</span>}
        </div>
      </div>
    );
  }
  if (node.kind === "stat-card") {
    return (
      <div className="bp-canvas-widget" style={{ borderLeft: "3px solid var(--aos-accent)", padding: "8px 12px" }}>
        <div className="muted" style={{ fontSize: "11px" }}>
          {node.config?.title || "统计卡"} · {node.config?.objectType || "Order"}
        </div>
        <div style={{ fontSize: "1.3rem", fontWeight: 600, margin: "4px 0" }}>
          {node.config?.metric === "sum" ? "Σ" : "#"} —
        </div>
        <div className="muted" style={{ fontSize: "10px" }}>
          metric={node.config?.metric || "count"}
          {node.config?.field ? ` · field=${node.config.field}` : ""}
        </div>
      </div>
    );
  }
  if (node.kind === "filter-bar") {
    const tabs = (node.config?.tabs as Array<{ key?: string; label?: string }> | undefined) || [
      { key: "all", label: "全部" },
    ];
    return (
      <div className="bp-canvas-widget">
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 6 }}>
          {tabs.slice(0, 5).map((t, i) => (
            <span key={t.key || i} className="bp-tag" style={i === 0 ? { background: "var(--aos-accent)", color: "var(--text-on-brand)" } : undefined}>
              {t.label || t.key}
            </span>
          ))}
          {tabs.length > 5 && <span className="muted">+{tabs.length - 5}</span>}
        </div>
        <span className="muted" style={{ fontSize: "11px" }}>
          🔍 搜索 · {node.config?.objectType || "Order"}
        </span>
      </div>
    );
  }
  if (node.kind === "detail-drawer") {
    const sections = (node.config?.sections as Array<{ title?: string }> | undefined) || [];
    return (
      <div className="bp-canvas-widget" style={{ borderLeft: "3px solid var(--aos-accent)", padding: "8px 12px" }}>
        <span className="bp-tag">详情抽屉</span>
        <span className="muted" style={{ marginLeft: 6, fontSize: "11px" }}>
          {node.config?.objectType || "Order"} · width={node.config?.width || 400}
        </span>
        <div style={{ marginTop: 6, fontSize: "11px" }}>
          {sections.length > 0
            ? sections.map((s, i) => (
                <div key={i} className="muted">· {s.title || `section-${i + 1}`}</div>
              ))
            : <span className="muted">无 section</span>}
        </div>
      </div>
    );
  }
  if (node.kind === "trend-chart") {
    return (
      <div className="bp-canvas-widget">
        <strong>{node.config?.title || "趋势图"}</strong>
        <span className="muted" style={{ marginLeft: 6, fontSize: "11px" }}>
          {node.config?.objectType || "Order"} · {node.config?.days || 7} 天
        </span>
        <div
          style={{
            marginTop: 8,
            height: 60,
            background: "var(--aos-surface-hover)",
            borderRadius: 4,
            display: "flex",
            alignItems: "flex-end",
            padding: "4px 8px",
            gap: 3,
          }}
        >
          {[12, 28, 18, 40, 30, 52, 36].map((h, i) => (
            <div
              key={i}
              style={{
                flex: 1,
                height: `${h * 1.2}%`,
                background: "var(--aos-accent)",
                opacity: 0.5 + i * 0.07,
                borderRadius: 2,
              }}
            />
          ))}
        </div>
        <div className="muted" style={{ fontSize: "10px", marginTop: 4 }}>
          dateField={node.config?.dateField || "order_date"}
        </div>
      </div>
    );
  }
  return (
    <div className="bp-canvas-widget bp-canvas-widget-overlay">
      <span className="bp-tag">Object View</span>
      <span className="muted">Wiki · Properties · Actions</span>
    </div>
  );
}

/** 90 · Layout 三栏壳 + Widget 调色板 + Module 持久化 · 对齐 workshop-canvas */
export function CanvasPage() {
  const [modules, setModules] = useState<ModuleRow[]>([]);
  const [moduleId, setModuleId] = useState<string>("");
  const [nodes, setNodes] = useState<CanvasNode[]>(() => structuredClone(DEFAULT_LAYOUT));
  const [selected, setSelected] = useState(DEFAULT_LAYOUT[0].id);
  const [rows, setRows] = useState<Row[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [previewOn, setPreviewOn] = useState(true);
  const [dirty, setDirty] = useState(false);
  const [propTab, setPropTab] = useState<"content" | "style" | "events" | "data">("content");
  const [palette, setPalette] = useState(FALLBACK_PALETTE);
  const [paletteNote, setPaletteNote] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>("objects");
  const [canvasMode, setCanvasMode] = useState<"widget" | "workflow" | "preview">("widget");
  const [bottomPanelCollapsed, setBottomPanelCollapsed] = useState(true);
  const [bottomPanelHeight, setBottomPanelHeight] = useState<number>(280);
  const [componentTree, setComponentTree] = useState<ComponentTree | null>(null);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(
    () => typeof document !== "undefined" && !!document.fullscreenElement,
  );
  useEffect(() => {
    if (typeof document === "undefined") return;
    const onChange = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);
  const toggleFullscreen = () => {
    if (typeof document === "undefined") return;
    if (document.fullscreenElement) {
      void document.exitFullscreen();
    } else {
      void document.documentElement.requestFullscreen();
    }
  };
  const [leftCollapsed, setLeftCollapsed] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem("canvas.sidebar.leftCollapsed") === "1";
  });
  const [rightCollapsed, setRightCollapsed] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem("canvas.sidebar.rightCollapsed") === "1";
  });

  const [activeItem, setActiveItem] = useState<PaletteItem | null>(null);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 0 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handleDragStart = (event: DragStartEvent) => {
    const { active } = event;
    const item = palette.find((p) => p.kind === active.id);
    if (item) {
      setActiveItem(item);
    }
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveItem(null);

    const activeKind = active.id as CanvasKind;
    if (KIND_SET.has(activeKind)) {
      const isOverCanvas = over?.id === "canvas-drop-zone" || nodes.some((n) => n.id === over?.id);
      if (isOverCanvas) {
        addNode(activeKind);
        setDirty(true);
      }
      return;
    }

    if (over && active.id !== over.id) {
      setNodes((items) => {
        const oldIndex = items.findIndex((item) => item.id === active.id);
        const newIndex = items.findIndex((item) => item.id === over.id);
        if (oldIndex >= 0 && newIndex >= 0) {
          return arrayMove(items, oldIndex, newIndex);
        }
        return items;
      });
      setDirty(true);
    }
  };

  const draggingRef = useRef<{ startY: number; startH: number } | null>(null);

  useEffect(() => {
    window.localStorage.setItem("canvas.sidebar.leftCollapsed", leftCollapsed ? "1" : "0");
  }, [leftCollapsed]);

  useEffect(() => {
    window.localStorage.setItem("canvas.sidebar.rightCollapsed", rightCollapsed ? "1" : "0");
  }, [rightCollapsed]);

  useEffect(() => {
    function onMove(e: MouseEvent) {
      const drag = draggingRef.current;
      if (!drag) return;
      const delta = drag.startY - e.clientY;
      const next = Math.max(120, Math.min(window.innerHeight * 0.7, drag.startH + delta));
      setBottomPanelHeight(next);
    }
    function onUp() {
      draggingRef.current = null;
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  const node = useMemo(
    () => nodes.find((n) => n.id === selected) ?? nodes[0],
    [nodes, selected],
  );
  const site =
    nodes.find((n) => n.kind === "filter")?.config?.site ||
    node?.config?.site ||
    "DC-East";
  const objectType =
    nodes.find((n) => n.kind === "table")?.config?.objectType || "WorkOrder";

  const loadModules = useCallback(async () => {
    const res = await apiGet<{ items: ModuleRow[] }>("/v1/modules");
    const all = res.items || [];
    const valid = all.filter((m) => {
      if (!m.id || !m.name) return false;
      const blacklist = ["to-publish", "pg-mod", "Idem Module", "pgmod"];
      const lowerId = m.id.toLowerCase();
      const lowerName = m.name.toLowerCase();
      for (const b of blacklist) {
        if (lowerId.includes(b.toLowerCase()) || lowerName.includes(b.toLowerCase())) {
          return false;
        }
      }
      return true;
    });
    setModules(valid);
    const prefer =
      valid.find((m) => m.components && Object.keys(m.components).length > 0) ||
      valid.find((m) => m.id.includes("canvas") || (m.widgets || []).length > 0) ||
      valid[0];
    if (prefer) {
      setModuleId(prefer.id);
      const layout = normalizeLayout(prefer.widgets, prefer.objectType);
      setNodes(layout);
      setSelected(layout[0]?.id || "");
      const tree = prefer.components && Object.keys(prefer.components).length > 0 ? prefer.components : null;
      setComponentTree(tree);
      setCanvasMode("widget");
      setDirty(false);
    }
  }, []);

  useEffect(() => {
    loadModules().catch((e) => setErr(String(e.message || e)));
  }, [loadModules]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiGet<{
          palette?: {
            kind?: string;
            label?: string;
            id?: string;
            pluginId?: string;
            runtime?: string;
            stub?: boolean;
          }[];
        }>("/v1/widget-plugins");
        if (cancelled) return;
        const items = (res.palette || [])
          .map((p) => {
            const kind = p.kind as CanvasKind | undefined;
            if (!kind || !KIND_SET.has(kind)) return null;
            return {
              kind,
              label: p.label || `+ ${p.id || kind}`,
              tone: kind === "overlay" ? ("violet" as const) : undefined,
              pluginId: p.pluginId || p.id,
              runtime: p.runtime,
              stub: !!p.stub || kind === "stub",
            } satisfies PaletteItem;
          })
          .filter(Boolean) as PaletteItem[];
        if (items.length) {
          setPalette(items);
          setPaletteNote(null);
        } else {
          setPalette(FALLBACK_PALETTE);
          setPaletteNote("Widget 插件目录为空 · 暂用本地兜底调色板");
        }
      } catch {
        if (!cancelled) {
          setPalette(FALLBACK_PALETTE);
          setPaletteNote("无法加载 widget-plugins · 暂用本地兜底调色板");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSelectModule(id: string) {
    setModuleId(id);
    setErr(null);
    try {
      const mod = await apiGet<ModuleRow>(`/v1/modules/${encodeURIComponent(id)}`);
      const layout = normalizeLayout(mod.widgets, mod.objectType);
      setNodes(layout);
      setSelected(layout[0]?.id || "");
      const tree =
        mod.components && Object.keys(mod.components).length > 0 ? mod.components : null;
      setComponentTree(tree);
      setCanvasMode("widget");
      setDirty(false);
      setMsg(
        tree
          ? `已加载 ${mod.name || id} · 应用预览（${Object.keys(tree).length} 组件）`
          : `已加载 ${mod.name || id} · widgets 模式`,
      );
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  async function runPreview() {
    setErr(null);
    try {
      const r = await apiPost<{ items?: Row[]; objects?: Row[] }>("/v1/object-sets/query", {
        objectType,
        filters: site ? [{ field: "site", op: "eq", value: site }] : [],
        pageSize: 10,
      });
      setRows(r.items || r.objects || []);
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  useEffect(() => {
    if (previewOn) void runPreview();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [site, objectType, previewOn]);

  function updateNode(id: string, patch: Partial<CanvasNode>) {
    setNodes((prev) => prev.map((n) => (n.id === id ? { ...n, ...patch, config: { ...n.config, ...patch.config } } : n)));
    setDirty(true);
  }

  function addNode(item: PaletteItem | CanvasKind) {
    const pal = typeof item === "string" ? { kind: item, label: item } : item;
    const kind = pal.kind;
    const id = `n-${kind}-${Date.now().toString(36)}`;
    const title =
      pal.label?.replace(/^\+\s*/, "") ||
      (kind === "filter"
        ? "Filter · site"
        : kind === "table"
          ? "Object Table"
          : kind === "buddy"
            ? "Buddy Chip"
            : kind === "action"
              ? "Action Form"
              : kind === "graph"
                ? "Graph View"
                : kind === "metric"
                  ? "Metric Card"
                  : kind === "stub"
                    ? pal.pluginId || "Stub Widget"
                    : kind === "page-header"
                      ? "页面头"
                      : kind === "stat-card"
                        ? "统计卡"
                        : kind === "filter-bar"
                          ? "筛选栏"
                          : kind === "detail-drawer"
                            ? "详情抽屉"
                            : kind === "trend-chart"
                              ? "趋势图"
                              : "Overlay · Object View");
    const config =
      kind === "filter"
        ? { site: "DC-East" }
        : kind === "table"
          ? { objectType: "WorkOrder" }
          : kind === "action" || pal.pluginId === "action-form"
            ? { actionTypeId: "CloseWorkOrder" }
            : kind === "graph" || pal.pluginId === "graph-view"
              ? { objectType: "WorkOrder", objectId: "wo-1001" }
              : kind === "metric" || pal.pluginId === "metric-card"
                ? { objectType: "WorkOrder", groupBy: "status" }
                : kind === "page-header"
                  ? { title: "页面标题", subtitle: "副标题" }
                  : kind === "stat-card"
                    ? { objectType: "Order", metric: "count", title: "统计卡" }
                    : kind === "filter-bar"
                      ? { objectType: "Order" }
                      : kind === "detail-drawer"
                        ? { objectType: "Order", width: 400 }
                        : kind === "trend-chart"
                          ? { objectType: "Order", dateField: "order_date", days: 7, title: "趋势图" }
                          : undefined;
    const pluginId =
      pal.pluginId ||
      (kind === "action"
        ? "action-form"
        : kind === "graph"
          ? "graph-view"
          : kind === "metric"
            ? "metric-card"
            : kind === "page-header"
              ? "page-header"
              : kind === "stat-card"
                ? "stat-card"
                : kind === "filter-bar"
                  ? "filter-bar"
                  : kind === "detail-drawer"
                    ? "detail-drawer"
                    : kind === "trend-chart"
                      ? "trend-chart"
                      : undefined);
    setNodes((prev) => [...prev, { id, kind, title, pluginId, config }]);
    setSelected(id);
    setDirty(true);
  }

  function removeNode(id: string) {
    setNodes((prev) => {
      const next = prev.filter((n) => n.id !== id);
      if (selected === id && next[0]) setSelected(next[0].id);
      return next;
    });
    setDirty(true);
  }

  function moveNode(id: string, dir: -1 | 1) {
    setNodes((prev) => {
      const i = prev.findIndex((n) => n.id === id);
      if (i < 0) return prev;
      const j = i + dir;
      if (j < 0 || j >= prev.length) return prev;
      const copy = [...prev];
      [copy[i], copy[j]] = [copy[j], copy[i]];
      return copy;
    });
    setDirty(true);
  }

  async function saveLayout() {
    if (!moduleId) {
      setErr("请先选择 Module");
      return;
    }
    setErr(null);
    try {
      if (componentTree) {
        await apiPatch(`/v1/modules/${encodeURIComponent(moduleId)}`, { components: componentTree });
      } else {
        await apiPatch(`/v1/modules/${encodeURIComponent(moduleId)}`, { widgets: nodes });
      }
      const rt = await apiGet<{ layout?: { widgets?: unknown } }>(
        `/v1/modules/${encodeURIComponent(moduleId)}/runtime`,
      );
      setDirty(false);
      setMsg(
        componentTree
          ? `已保存组件树 · ${Object.keys(componentTree).length} 个组件 · 可打开模块接口页核对`
          : `已保存 Layout · runtime widgets=${Array.isArray(rt.layout?.widgets) ? rt.layout!.widgets!.length : "?"} · 可打开模块接口页核对`,
      );
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  async function publishModule() {
    if (!moduleId) {
      setErr("请先选择 Module");
      return;
    }
    setErr(null);
    try {
      await apiPatch(`/v1/modules/${encodeURIComponent(moduleId)}`, { status: "published" });
      setMsg(`模块「${currentModule?.name || moduleId}」已发布`);
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  const TOOLBAR_TABS = [
    { id: "dashboard", label: "Dashboard" },
    { id: "queries", label: "Queries" },
    { id: "functions", label: "Functions" },
    { id: "objects", label: "Objects" },
    { id: "events", label: "Events" },
    { id: "data", label: "Data" },
    { id: "dependencies", label: "Dependencies" },
    { id: "styles", label: "Styles" },
    { id: "variables", label: "Variables" },
  ];

  const currentModule = modules.find((m) => m.id === moduleId);

  return (
    <PageChrome
      title="画布编辑"
      lede="90 · Layout 树 / Widget 调色板 / 配置面板 · 构建态非运行态"
    >
      {msg && <p className="aos-text">{msg}</p>}
      {err && <p className="error">{err}</p>}

      <DndContext
          sensors={sensors}
          collisionDetection={pointerWithin}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
        <div className="p-slate-app" style={{ minHeight: "calc(100vh - 200px)" }}>
        <header className="p-slate-topbar">
          <div className="p-slate-topbar-left">
            <span className="p-slate-breadcrumb">Workshop</span>
            <NavIcon name="chevron" style={{ width: "12px", height: "12px", color: "var(--aos-text-tertiary)" }} />
            <h1 className="p-slate-title">
              {currentModule?.name || "画布编辑"}
              <NavIcon name="star" style={{ width: "12px", height: "12px", color: "var(--aos-text-tertiary)" }} />
            </h1>
          </div>
          <nav className="p-slate-tabs">
            <button type="button" className="p-slate-tab">File</button>
            <button type="button" className="p-slate-tab">Help</button>
            <button type="button" className="p-slate-tab is-active">
              {currentModule?.name || "Module"} <span className="p-slate-version">v1</span>
            </button>
          </nav>
          <div className="p-slate-topbar-right">
            <select
              aria-label="module"
              value={moduleId}
              onChange={(e) => void onSelectModule(e.target.value)}
              style={{
                fontSize: "12px",
                padding: "4px 8px",
                borderRadius: "4px",
                border: "1px solid var(--aos-border)",
                background: "var(--aos-aside)",
                color: "var(--aos-text)",
              }}
            >
              {modules.length === 0 && <option value="">（无模块）</option>}
              {modules.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
            <button
              type="button"
              disabled={!dirty}
              onClick={() => void saveLayout()}
              style={{
                fontSize: "12px",
                padding: "5px 12px",
                borderRadius: "4px",
                border: "1px solid var(--aos-border)",
                background: dirty ? "var(--aos-accent)" : "var(--aos-aside)",
                color: dirty ? "var(--text-on-brand)" : "var(--aos-text-secondary)",
                cursor: dirty ? "pointer" : "default",
              }}
            >
              {dirty ? "保存 *" : "已保存"}
            </button>
            <button
              type="button"
              onClick={() => void publishModule()}
              style={{
                fontSize: "12px",
                padding: "5px 12px",
                borderRadius: "4px",
                border: "none",
                background: "var(--aos-green)",
                color: "var(--text-on-brand)",
                cursor: "pointer",
              }}
            >
              发布
            </button>
            <button type="button" className="p-slate-close" title="关闭">
              <NavIcon name="close" style={{ width: "14px", height: "14px" }} />
            </button>
          </div>
        </header>

        <div className="p-slate-toolbar">
          <div className="p-slate-toolbar-left" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                background: "var(--aos-aside)",
                borderRadius: "4px",
                border: "1px solid var(--aos-border)",
                overflow: "hidden",
              }}
            >
              <button
                type="button"
                onClick={() => setCanvasMode("widget")}
                style={{
                  fontSize: "12px",
                  padding: "4px 12px",
                  border: "none",
                  background: canvasMode === "widget" ? "var(--aos-accent)" : "transparent",
                  color: canvasMode === "widget" ? "var(--text-on-brand)" : "var(--aos-text)",
                  cursor: "pointer",
                  fontWeight: canvasMode === "widget" ? 500 : 400,
                }}
              >
                模块
              </button>
              <button
                type="button"
                onClick={() => setCanvasMode("workflow")}
                style={{
                  fontSize: "12px",
                  padding: "4px 12px",
                  border: "none",
                  background: canvasMode === "workflow" ? "var(--aos-accent)" : "transparent",
                  color: canvasMode === "workflow" ? "var(--text-on-brand)" : "var(--aos-text)",
                  cursor: "pointer",
                  fontWeight: canvasMode === "workflow" ? 500 : 400,
                }}
              >
                工作流
              </button>
              <button
                type="button"
                onClick={() => setCanvasMode("preview")}
                style={{
                  fontSize: "12px",
                  padding: "4px 12px",
                  border: "none",
                  background: canvasMode === "preview" ? "var(--aos-accent)" : "transparent",
                  color: canvasMode === "preview" ? "var(--text-on-brand)" : "var(--aos-text)",
                  cursor: "pointer",
                  fontWeight: canvasMode === "preview" ? 500 : 400,
                }}
              >
                预览
              </button>
            </div>
            <div style={{ width: "1px", height: "16px", background: "var(--aos-border)" }} />
            <button
              type="button"
              onClick={() => setMsg("撤销功能开发中")}
              title="撤销"
              style={{
                fontSize: "12px",
                padding: "4px 8px",
                borderRadius: "4px",
                border: "1px solid var(--aos-border)",
                background: "var(--aos-surface)",
                color: "var(--aos-text)",
                cursor: "pointer",
              }}
            >
              ↶ 撤销
            </button>
            <button
              type="button"
              onClick={() => setMsg("重做功能开发中")}
              title="重做"
              style={{
                fontSize: "12px",
                padding: "4px 8px",
                borderRadius: "4px",
                border: "1px solid var(--aos-border)",
                background: "var(--aos-surface)",
                color: "var(--aos-text)",
                cursor: "pointer",
              }}
            >
              ↷ 重做
            </button>
          </div>
          <div className="p-slate-toolbar-tabs">
            {TOOLBAR_TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                className={`p-slate-toolbar-tab${t.id === activeTab ? " is-active" : ""}`}
                onClick={() => {
                  setActiveTab(t.id);
                  setBottomPanelCollapsed(t.id === "objects");
                }}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <div className="p-slate-main">
          <div className={`p-slate-canvas-area${bottomPanelCollapsed ? " is-full" : ""}`}>
            {canvasMode === "preview" ? (
              <div className="p-slate-body">
                <div className="p-slate-canvas" style={{ padding: 16 }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      padding: "6px 10px",
                      borderRadius: 2,
                      background: "var(--aos-indigo-bg)",
                      border: "1px solid var(--aos-indigo-border)",
                      fontSize: 11,
                      color: "var(--aos-indigo-600)",
                      marginBottom: 12,
                    }}
                  >
                    <span>
                      ● 应用预览（运行态）·
                      {componentTree ? `${Object.keys(componentTree).length} 组件 · root=${componentTree.root?.type || "—"}` : `${nodes.length} widgets`}
                    </span>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 10, opacity: 0.7 }}>
                        可编辑应用（运行态只读预览）
                      </span>
                      <button
                        type="button"
                        onClick={() => setCanvasMode("widget")}
                        title="切回编辑态"
                        aria-label="切回编辑态"
                        style={{
                          fontSize: 11,
                          padding: "3px 10px",
                          borderRadius: 4,
                          background: "var(--aos-indigo-600)",
                          color: "var(--text-on-brand)",
                          border: "none",
                          cursor: "pointer",
                          fontWeight: 500,
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 4,
                        }}
                      >
                        ✎ 编辑
                      </button>
                    </div>
                  </div>

                  {componentTree ? (
                    <ComponentRenderer components={componentTree} />
                  ) : nodes.length === 0 ? (
                    <p className="muted" style={{ textAlign: "center", padding: "40px" }}>
                      当前模块没有可预览的内容，请先在编辑态添加 Widget
                    </p>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                      {nodes.map((n) => (
                        <div key={n.id} className="p-slate-widget">
                          <div className="p-slate-widget-header">
                            <span className="p-slate-widget-title">{n.title}</span>
                          </div>
                          <div className="p-slate-widget-body">
                            <WidgetPreview node={n} rows={rows} />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ) : canvasMode === "workflow" ? (
              <div className="p-slate-body">
                <WorkflowMode moduleId={moduleId || "mod-canvas-draft"} />
              </div>
            ) : (
            <div className="p-slate-body">
          {!componentTree && (
            <aside className={`p-slate-tree${leftCollapsed ? " is-collapsed" : ""}`}>
            {leftCollapsed ? (
              <button
                type="button"
                className="p-slate-side-restore"
                onClick={() => setLeftCollapsed(false)}
                title="展开组件列表"
                aria-label="展开组件列表"
              >
                <NavIcon name="chevron" style={{ width: "12px", height: "12px", color: "var(--aos-text-tertiary)" }} />
                <span className="p-slate-side-restore-label">组件</span>
              </button>
            ) : (
              <>
            <div className="p-slate-side-pin">
              <button
                type="button"
                className="p-slate-side-collapse-btn"
                onClick={() => setLeftCollapsed(true)}
                title="折叠组件列表（向左收起）"
                aria-label="折叠组件列表"
              >
                <NavIcon name="chevron" style={{ width: "12px", height: "12px", transform: "rotate(180deg)" }} />
              </button>
            </div>
            <div className="p-slate-tree-search">
              <NavIcon name="search" />
              <input type="search" placeholder="Search widgets..." />
            </div>

            <div className="p-slate-tree-section-title">Layout</div>
            <button
              type="button"
              className="p-slate-tree-item"
              onClick={toggleFullscreen}
              title={isFullscreen ? "退出浏览器全屏" : "进入浏览器全屏"}
              aria-label={isFullscreen ? "退出全屏" : "进入全屏"}
              style={{ cursor: "pointer" }}
            >
              <NavIcon name="menu" style={{ width: "12px", height: "12px" }} />
              <span>{isFullscreen ? "fullscreen · 已开启" : "fullscreen"}</span>
            </button>
            <button
              type="button"
              className="p-slate-tree-item is-expanded"
              onClick={() => addNode("page-header")}
              title="添加页面头 Widget（page-header）"
              aria-label="添加页面头 Widget"
              style={{ cursor: "pointer" }}
            >
              <NavIcon name="chevron" style={{ width: "12px", height: "12px", transform: "rotate(90deg)" }} />
              <NavIcon name="apps" style={{ width: "14px", height: "14px", color: "var(--aos-accent)" }} />
              <span>w_nav_bar · 点击添加</span>
            </button>
            {nodes.map((n) => (
              <button
                key={n.id}
                type="button"
                className={`p-slate-tree-item is-child${n.id === selected ? " is-selected" : ""}`}
                onClick={() => setSelected(n.id)}
              >
                <NavIcon name="menu" style={{ width: "12px", height: "12px" }} />
                <NavIcon
                  name={n.kind === "table" ? "table" : n.kind === "graph" ? "graph" : "apps"}
                  style={{ width: "14px", height: "14px", color: "var(--aos-accent)" }}
                />
                <span style={{ fontSize: "11px" }}>{sectionLabel(n.kind)}</span>
              </button>
            ))}

            <div className="p-slate-tree-section-title" style={{ marginTop: "8px" }}>
              Widget 组件
            </div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: "4px",
                padding: "4px",
                borderRadius: "2px",
                background: "var(--aos-aside)",
                border: "1px dashed var(--aos-border)",
              }}
            >
              {palette.length === 0 && (
                <div style={{ gridColumn: "1 / -1", fontSize: "10px", opacity: 0.6, padding: "4px" }}>
                  {paletteNote || "调色板为空"}
                </div>
              )}
              {palette.map((w) => (
                <DraggablePaletteItem key={`${w.pluginId || w.kind}-${w.label}`} item={w} onClick={() => addNode(w)} />
              ))}
            </div>
            {paletteNote && (
              <div className="p-slate-tree-item is-child" style={{ opacity: 0.6, fontSize: "10px" }}>
                {paletteNote}
              </div>
            )}

            <Link
              to="/workshop/widget-registry"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                padding: "6px 10px",
                marginTop: "6px",
                borderRadius: "2px",
                background: "var(--aos-indigo-bg)",
                color: "var(--aos-indigo-600)",
                fontSize: "11px",
                fontWeight: 500,
                textDecoration: "none",
                border: "1px dashed var(--aos-indigo-border)",
              }}
            >
              <span style={{ fontSize: "14px" }}>+</span>
              添加组件 · 浏览注册表
            </Link>

            <button
              type="button"
              className="p-slate-tree-footer"
              onClick={() => node && removeNode(node.id)}
              disabled={!node}
              style={{ opacity: node ? 1 : 0.5, cursor: node ? "pointer" : "not-allowed" }}
            >
              <NavIcon name="trash" style={{ width: "14px", height: "14px" }} />
              Delete widget
            </button>
              </>
            )}
          </aside>
          )}

          {componentTree ? (
            <ComponentTreeEditor
              tree={componentTree}
              onChange={(tree) => {
                setComponentTree(tree);
                setDirty(true);
              }}
              rightCollapsed={rightCollapsed}
              onToggleRight={() => setRightCollapsed((v) => !v)}
            />
          ) : (
          <>
          <CanvasDropZone disabled={false}>
            {nodes.length === 0 ? (
              <p className="muted" style={{ textAlign: "center", padding: "40px" }}>
                从左侧调色板添加 Widget 开始构建
              </p>
            ) : (
              <SortableContext items={nodes.map((n) => n.id)} strategy={verticalListSortingStrategy}>
                {nodes.map((n) => (
                  <div
                    key={n.id}
                    className={`p-slate-widget${n.id === selected ? " is-selected" : ""}`}
                    style={{ marginBottom: "16px" }}
                  >
                    <SortableCanvasNode
                      node={n}
                      onClick={() => setSelected(n.id)}
                      onRemove={() => removeNode(n.id)}
                      rows={rows}
                      moveNode={moveNode}
                    />
                  </div>
                ))}
              </SortableContext>
            )}

            <div style={{ marginTop: "24px", paddingTop: "16px", borderTop: "1px solid var(--aos-border)" }}>
              <div className="p-slate-tree-section-title" style={{ padding: "0", marginBottom: "12px" }}>
                预览运行态
              </div>
              <p className="muted" style={{ marginBottom: "8px" }}>
                Filter site=<strong>{site}</strong> · Table=<strong>{objectType}</strong>
              </p>
              <button
                type="button"
                onClick={() => void runPreview()}
                style={{
                  fontSize: "12px",
                  padding: "5px 12px",
                  borderRadius: "4px",
                  border: "1px solid var(--aos-border)",
                  background: "var(--aos-aside)",
                  color: "var(--aos-text)",
                  cursor: "pointer",
                  marginRight: "8px",
                }}
              >
                刷新 Object Table
              </button>
              <button
                type="button"
                onClick={() => setPreviewOn((v) => !v)}
                style={{
                  fontSize: "12px",
                  padding: "5px 12px",
                  borderRadius: "4px",
                  border: "1px solid var(--aos-border)",
                  background: "var(--aos-aside)",
                  color: "var(--aos-text)",
                  cursor: "pointer",
                }}
              >
                {previewOn ? "暂停预览" : "开启预览"}
              </button>
              <ul className="card-list" style={{ marginTop: "12px" }}>
                {rows.map((row, i) => {
                  const id = String(row.id || row.objectId || `row-${i}`);
                  const title = String(row.title || (row.props?.title as string) || id);
                  const status = String(row.status || (row.props?.status as string) || "");
                  return (
                    <li key={id} className="card">
                      <strong>{id}</strong>{" "}
                      <span className="muted">
                        {title} · {status}
                      </span>
                    </li>
                  );
                })}
              </ul>
              {rows.length === 0 && !err && (
                <p className="muted">无行 · 改 Filter site 或到数据连接接入源后刷新</p>
              )}
            </div>

            {/* 底部相关配置链接 · 对齐视觉稿 */}
            <div style={{ padding: "8px 16px", borderTop: "1px solid var(--aos-border)", fontSize: "12px", color: "var(--aos-text-muted)", display: "flex", gap: "16px", flexWrap: "wrap", alignItems: "center" }}>
              <span>相关配置:</span>
              <Link to="/workshop/events" style={{ color: "var(--aos-accent)", textDecoration: "none" }}>事件配置 →</Link>
              <Link to="/workshop/module-interface" style={{ color: "var(--aos-accent)", textDecoration: "none" }}>模块接口 →</Link>
            </div>
          </CanvasDropZone>

          <aside className={`p-slate-props${rightCollapsed ? " is-collapsed" : ""}`}>
            {rightCollapsed ? (
              <button
                type="button"
                className="p-slate-side-restore"
                onClick={() => setRightCollapsed(false)}
                title="展开属性面板"
                aria-label="展开属性面板"
              >
                <span className="p-slate-side-restore-label">属性</span>
                <NavIcon name="chevron" style={{ width: "12px", height: "12px", color: "var(--aos-text-tertiary)" }} />
              </button>
            ) : (
              <>
            <div className="p-slate-props-header">
              <NavIcon name="apps" style={{ width: "14px", height: "14px", color: "var(--aos-accent)" }} />
              <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {node ? node.title : "未选中 Widget"}
              </span>
              <button
                type="button"
                className="p-slate-side-collapse-btn"
                onClick={() => setRightCollapsed(true)}
                title="折叠属性面板（向右收起）"
                aria-label="折叠属性面板"
                style={{ position: "static", width: 22, height: 22 }}
              >
                <NavIcon name="chevron" style={{ width: "12px", height: "12px" }} />
              </button>
            </div>

            {/* 属性面板 Tab 切换 · 对齐视觉稿 */}
            <div style={{ display: "flex", borderBottom: "1px solid var(--aos-border)", padding: "0 4px" }}>
              {([
                { id: "content", label: "内容" },
                { id: "style", label: "样式" },
                { id: "events", label: "事件" },
                { id: "data", label: "数据" },
              ] as const).map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setPropTab(tab.id)}
                  style={{
                    padding: "6px 10px",
                    fontSize: "11px",
                    fontWeight: propTab === tab.id ? 500 : 400,
                    borderBottom: propTab === tab.id ? "2px solid var(--aos-accent)" : "none",
                    color: propTab === tab.id ? "var(--aos-accent)" : "var(--aos-text-muted)",
                    background: "none",
                    border: "none",
                    borderTop: "none",
                    borderLeft: "none",
                    borderRight: "none",
                    cursor: "pointer",
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {!node ? (
              <div className="p-slate-props-section">
                <p className="muted" style={{ fontSize: "12px" }}>选择左侧画布中的 Widget 查看配置</p>
              </div>
            ) : (
              <>
                {/* 内容 Tab */}
                {propTab === "content" && (
                  <>
                    <div className="p-slate-props-section">
                      <div className="p-slate-props-label">CONTENT</div>
                      <div className="p-slate-props-toggle">
                        <button type="button">Markdown</button>
                        <button type="button" className="is-active">HTML</button>
                      </div>
                      <div className="p-slate-props-code">
                        {`// ${node.kind} · ${node.id}\n// plugin: ${node.pluginId || "built-in"}`}
                      </div>
                    </div>

                <div className="p-slate-props-section" style={{ paddingTop: "0" }}>
                  <div className="p-slate-props-label">WIDGET CONFIG</div>
                  <div style={{ marginBottom: "10px" }}>
                    <label className="p-slate-props-label" style={{ display: "block", marginBottom: "6px" }}>
                      标题
                    </label>
                    <input
                      value={node.title}
                      onChange={(e) => updateNode(node.id, { title: e.target.value })}
                      style={{
                        width: "100%",
                        padding: "6px 8px",
                        fontSize: "12px",
                        border: "1px solid var(--aos-border)",
                        borderRadius: "4px",
                        background: "var(--aos-aside)",
                        color: "var(--aos-text)",
                        boxSizing: "border-box",
                      }}
                    />
                  </div>

                  {node.kind === "filter" && (
                    <div style={{ marginBottom: "10px" }}>
                      <label className="p-slate-props-label" style={{ display: "block", marginBottom: "6px" }}>
                        site
                      </label>
                      <input
                        value={node.config?.site || ""}
                        onChange={(e) =>
                          updateNode(node.id, { config: { ...node.config, site: e.target.value } })
                        }
                        style={{
                          width: "100%",
                          padding: "6px 8px",
                          fontSize: "12px",
                          border: "1px solid var(--aos-border)",
                          borderRadius: "4px",
                          background: "var(--aos-aside)",
                          color: "var(--aos-text)",
                          boxSizing: "border-box",
                        }}
                      />
                    </div>
                  )}

                  {node.kind === "table" && (
                    <div style={{ marginBottom: "10px" }}>
                      <label className="p-slate-props-label" style={{ display: "block", marginBottom: "6px" }}>
                        objectType
                      </label>
                      <input
                        value={node.config?.objectType || "WorkOrder"}
                        onChange={(e) =>
                          updateNode(node.id, {
                            config: { ...node.config, objectType: e.target.value },
                          })
                        }
                        style={{
                          width: "100%",
                          padding: "6px 8px",
                          fontSize: "12px",
                          border: "1px solid var(--aos-border)",
                          borderRadius: "4px",
                          background: "var(--aos-aside)",
                          color: "var(--aos-text)",
                          boxSizing: "border-box",
                        }}
                      />
                    </div>
                  )}

                  {(node.kind === "action" || node.pluginId === "action-form") && (
                    <>
                      <div style={{ marginBottom: "10px" }}>
                        <label className="p-slate-props-label" style={{ display: "block", marginBottom: "6px" }}>
                          actionTypeId
                        </label>
                        <input
                          value={node.config?.actionTypeId || "CloseWorkOrder"}
                          onChange={(e) =>
                            updateNode(node.id, {
                              config: { ...node.config, actionTypeId: e.target.value },
                            })
                          }
                          style={{
                            width: "100%",
                            padding: "6px 8px",
                            fontSize: "12px",
                            border: "1px solid var(--aos-border)",
                            borderRadius: "4px",
                            background: "var(--aos-aside)",
                            color: "var(--aos-text)",
                            boxSizing: "border-box",
                          }}
                        />
                      </div>
                      <div style={{ marginBottom: "10px" }}>
                        <label className="p-slate-props-label" style={{ display: "block", marginBottom: "6px" }}>
                          objectType
                        </label>
                        <input
                          value={node.config?.objectType || "WorkOrder"}
                          onChange={(e) =>
                            updateNode(node.id, {
                              config: { ...node.config, objectType: e.target.value },
                            })
                          }
                          style={{
                            width: "100%",
                            padding: "6px 8px",
                            fontSize: "12px",
                            border: "1px solid var(--aos-border)",
                            borderRadius: "4px",
                            background: "var(--aos-aside)",
                            color: "var(--aos-text)",
                            boxSizing: "border-box",
                          }}
                        />
                      </div>
                      <div style={{ marginBottom: "10px" }}>
                        <label className="p-slate-props-label" style={{ display: "block", marginBottom: "6px" }}>
                          objectId
                        </label>
                        <input
                          value={node.config?.objectId || ""}
                          onChange={(e) =>
                            updateNode(node.id, {
                              config: { ...node.config, objectId: e.target.value },
                            })
                          }
                          style={{
                            width: "100%",
                            padding: "6px 8px",
                            fontSize: "12px",
                            border: "1px solid var(--aos-border)",
                            borderRadius: "4px",
                            background: "var(--aos-aside)",
                            color: "var(--aos-text)",
                            boxSizing: "border-box",
                          }}
                        />
                      </div>
                    </>
                  )}

                  {(node.kind === "graph" || node.pluginId === "graph-view") && (
                    <>
                      <div style={{ marginBottom: "10px" }}>
                        <label className="p-slate-props-label" style={{ display: "block", marginBottom: "6px" }}>
                          objectType
                        </label>
                        <input
                          value={node.config?.objectType || "WorkOrder"}
                          onChange={(e) =>
                            updateNode(node.id, {
                              config: { ...node.config, objectType: e.target.value },
                            })
                          }
                          style={{
                            width: "100%",
                            padding: "6px 8px",
                            fontSize: "12px",
                            border: "1px solid var(--aos-border)",
                            borderRadius: "4px",
                            background: "var(--aos-aside)",
                            color: "var(--aos-text)",
                            boxSizing: "border-box",
                          }}
                        />
                      </div>
                      <div style={{ marginBottom: "10px" }}>
                        <label className="p-slate-props-label" style={{ display: "block", marginBottom: "6px" }}>
                          objectId
                        </label>
                        <input
                          value={node.config?.objectId || "wo-1001"}
                          onChange={(e) =>
                            updateNode(node.id, {
                              config: { ...node.config, objectId: e.target.value },
                            })
                          }
                          style={{
                            width: "100%",
                            padding: "6px 8px",
                            fontSize: "12px",
                            border: "1px solid var(--aos-border)",
                            borderRadius: "4px",
                            background: "var(--aos-aside)",
                            color: "var(--aos-text)",
                            boxSizing: "border-box",
                          }}
                        />
                      </div>
                    </>
                  )}

                  {(node.kind === "metric" || node.pluginId === "metric-card") && (
                    <>
                      <div style={{ marginBottom: "10px" }}>
                        <label className="p-slate-props-label" style={{ display: "block", marginBottom: "6px" }}>
                          objectType
                        </label>
                        <input
                          value={node.config?.objectType || "WorkOrder"}
                          onChange={(e) =>
                            updateNode(node.id, {
                              config: { ...node.config, objectType: e.target.value },
                            })
                          }
                          style={{
                            width: "100%",
                            padding: "6px 8px",
                            fontSize: "12px",
                            border: "1px solid var(--aos-border)",
                            borderRadius: "4px",
                            background: "var(--aos-aside)",
                            color: "var(--aos-text)",
                            boxSizing: "border-box",
                          }}
                        />
                      </div>
                      <div style={{ marginBottom: "10px" }}>
                        <label className="p-slate-props-label" style={{ display: "block", marginBottom: "6px" }}>
                          groupBy
                        </label>
                        <input
                          value={node.config?.groupBy || "status"}
                          onChange={(e) =>
                            updateNode(node.id, {
                              config: { ...node.config, groupBy: e.target.value },
                            })
                          }
                          style={{
                            width: "100%",
                            padding: "6px 8px",
                            fontSize: "12px",
                            border: "1px solid var(--aos-border)",
                            borderRadius: "4px",
                            background: "var(--aos-aside)",
                            color: "var(--aos-text)",
                            boxSizing: "border-box",
                          }}
                        />
                      </div>
                      <div style={{ marginBottom: "10px" }}>
                        <label className="p-slate-props-label" style={{ display: "block", marginBottom: "6px" }}>
                          site
                        </label>
                        <input
                          value={node.config?.site || ""}
                          onChange={(e) =>
                            updateNode(node.id, {
                              config: { ...node.config, site: e.target.value },
                            })
                          }
                          style={{
                            width: "100%",
                            padding: "6px 8px",
                            fontSize: "12px",
                            border: "1px solid var(--aos-border)",
                            borderRadius: "4px",
                            background: "var(--aos-aside)",
                            color: "var(--aos-text)",
                            boxSizing: "border-box",
                          }}
                        />
                      </div>
                    </>
                  )}
                </div>
                  </>
                )}

                {/* 样式 Tab · 对齐视觉稿 */}
                {propTab === "style" && (
                  <div style={{ padding: "8px" }}>
                    <div style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--aos-text-muted)", marginBottom: "8px" }}>布局</div>
                    <div style={{ display: "flex", gap: "4px", marginBottom: "8px" }}>
                      <button style={{ flex: 1, padding: "4px", fontSize: "10px", border: "1px solid var(--aos-border)", borderRadius: "4px", background: "var(--aos-surface)", cursor: "pointer", color: "var(--aos-text)" }}>横向</button>
                      <button style={{ flex: 1, padding: "4px", fontSize: "10px", border: "1px solid var(--aos-indigo-border)", borderRadius: "4px", background: "var(--aos-indigo-bg)", color: "var(--aos-indigo-600)", cursor: "pointer" }}>纵向</button>
                      <button style={{ flex: 1, padding: "4px", fontSize: "10px", border: "1px solid var(--aos-border)", borderRadius: "4px", background: "var(--aos-surface)", cursor: "pointer", color: "var(--aos-text)" }}>栅格</button>
                    </div>
                    <div style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--aos-text-muted)", marginBottom: "4px" }}>间距</div>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "8px" }}>
                      <input type="range" min={0} max={40} defaultValue={16} style={{ flex: 1, colorScheme: "dark" }} />
                      <span style={{ fontSize: "10px", color: "var(--aos-text-muted)" }}>16px</span>
                    </div>
                    <div style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--aos-text-muted)", marginBottom: "4px" }}>背景色</div>
                    <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                      <div style={{ width: 20, height: 20, borderRadius: "4px", border: "1px solid var(--aos-border)", background: "var(--aos-surface)" }} />
                      <span style={{ fontSize: "10px", color: "var(--aos-text-muted)", fontFamily: "monospace" }}>#FFFFFF</span>
                    </div>
                  </div>
                )}

                {/* 事件 Tab · 对齐视觉稿 */}
                {propTab === "events" && (
                  <div style={{ padding: "8px" }}>
                    <div style={{ fontSize: "11px", color: "var(--aos-text-muted)", marginBottom: "6px" }}>绑定此组件的事件处理：</div>
                    <div style={{ border: "1px solid var(--aos-border)", borderRadius: "2px", padding: "6px", marginBottom: "4px" }}>
                      <div style={{ fontSize: "11px", fontWeight: 500, color: "var(--aos-text)" }}>onPageLoad</div>
                      <div style={{ fontSize: "10px", color: "var(--aos-text-muted)" }}>→ initDefaultFilter()</div>
                    </div>
                    <div style={{ border: "1px solid var(--aos-border)", borderRadius: "2px", padding: "6px", marginBottom: "4px" }}>
                      <div style={{ fontSize: "11px", fontWeight: 500, color: "var(--aos-text)" }}>onResize</div>
                      <div style={{ fontSize: "10px", color: "var(--aos-text-muted)" }}>→ setBreakpoint(width)</div>
                    </div>
                    <Link to="/workshop/events" style={{ display: "block", fontSize: "11px", color: "var(--aos-indigo-600)", textAlign: "center", padding: "4px", border: "1px dashed var(--aos-indigo-border)", borderRadius: "2px", textDecoration: "none", marginTop: "4px" }}>
                      + 绑定新事件 →
                    </Link>
                  </div>
                )}

                {/* 数据 Tab · 对齐视觉稿 */}
                {propTab === "data" && (
                  <div style={{ padding: "8px" }}>
                    <div style={{ fontSize: "11px", color: "var(--aos-text-muted)", marginBottom: "6px" }}>绑定数据源：</div>
                    <div style={{ border: "1px solid var(--aos-border)", borderRadius: "2px", padding: "6px", marginBottom: "4px" }}>
                      <div style={{ fontSize: "11px", fontWeight: 500, color: "var(--aos-text)" }}>ObjectSet: {node.config?.objectType || "WorkOrder"}</div>
                      <div style={{ fontSize: "10px", color: "var(--aos-text-muted)" }}>属性: id, title, site, status</div>
                    </div>
                    <div style={{ border: "1px solid var(--aos-border)", borderRadius: "2px", padding: "6px", marginBottom: "4px" }}>
                      <div style={{ fontSize: "11px", fontWeight: 500, color: "var(--aos-text)" }}>变量: $selected_site</div>
                      <div style={{ fontSize: "10px", color: "var(--aos-text-muted)" }}>类型: String · 默认: "DC-East"</div>
                    </div>
                    <Link to="/workshop/variables" style={{ display: "block", fontSize: "11px", color: "var(--aos-indigo-600)", textAlign: "center", padding: "4px", border: "1px dashed var(--aos-indigo-border)", borderRadius: "2px", textDecoration: "none", marginTop: "4px" }}>
                      + 绑定变量或 ObjectSet
                    </Link>
                  </div>
                )}

                <div className="p-slate-props-section" style={{ marginTop: "auto", borderTop: "1px solid var(--aos-border-light)" }}>
                  <p className="muted" style={{ fontSize: "10px", margin: 0 }}>
                    构建态 · 非运行态
                  </p>
                </div>
              </>
            )}
              </>
            )}
          </aside>
          </>
          )}
        </div>
            )}
          </div>

          {/* 下半屏 · Tab 内容面板（与画布正交展示） */}
          <div
            className={`p-slate-bottom-panel${bottomPanelCollapsed ? " is-collapsed" : ""}`}
            style={!bottomPanelCollapsed ? { height: bottomPanelHeight, flex: "0 0 auto" } : undefined}
          >
            {!bottomPanelCollapsed && (
              <div
                className="p-slate-bottom-panel-resizer"
                onMouseDown={(e) => {
                  draggingRef.current = { startY: e.clientY, startH: bottomPanelHeight };
                  document.body.style.userSelect = "none";
                  document.body.style.cursor = "row-resize";
                }}
              >
                <span className="p-slate-bottom-panel-resizer-grip" />
              </div>
            )}
            <div className="p-slate-bottom-panel-header">
              <div className="p-slate-bottom-panel-title">
                <span>{TOOLBAR_TABS.find((t) => t.id === activeTab)?.label || "Objects"}</span>
                <span className="muted" style={{ fontSize: "11px", fontWeight: 400 }}>
                  · 与上方画布正交展示 · 切换 Tab 不影响画布
                </span>
              </div>
              <button
                type="button"
                className="p-slate-bottom-panel-toggle"
                onClick={() => setBottomPanelCollapsed((v) => !v)}
                title={bottomPanelCollapsed ? "展开面板" : "折叠面板"}
              >
                {bottomPanelCollapsed ? "▲ 展开" : "▼ 折叠"}
              </button>
            </div>
            {!bottomPanelCollapsed && (
              <div className="p-slate-bottom-panel-content">
                {activeTab === "objects" && (
                  <div style={{ padding: "12px", fontSize: "12px" }}>
                    <div className="muted" style={{ marginBottom: "10px" }}>
                      当前画布对象（{nodes.length}）· 选中后在上方画布中编辑
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: "6px" }}>
                      {nodes.map((n) => (
                        <button
                          key={n.id}
                          type="button"
                          onClick={() => setSelected(n.id)}
                          style={{
                            padding: "8px 10px",
                            borderRadius: "4px",
                            background: n.id === selected ? "var(--aos-accent-light)" : "var(--aos-surface)",
                            border: `1px solid ${n.id === selected ? "var(--aos-accent)" : "var(--aos-border)"}`,
                            color: n.id === selected ? "var(--aos-accent)" : "var(--aos-text)",
                            cursor: "pointer",
                            textAlign: "left",
                            display: "flex",
                            flexDirection: "column",
                            gap: "2px",
                          }}
                        >
                          <span style={{ fontSize: "11px", fontWeight: 500 }}>{n.title}</span>
                          <span style={{ fontSize: "10px", opacity: 0.7 }}>
                            {sectionLabel(n.kind)} · {n.pluginId || "built-in"}
                          </span>
                        </button>
                      ))}
                      {nodes.length === 0 && (
                        <span className="muted" style={{ fontSize: "11px" }}>画布为空，从左侧调色板添加 Widget</span>
                      )}
                    </div>
                  </div>
                )}
                {activeTab === "dashboard" && <DashboardTab moduleId={moduleId || "mod-canvas-draft"} />}
                {activeTab === "queries" && <QueriesTab moduleId={moduleId || "mod-canvas-draft"} />}
                {activeTab === "functions" && <FunctionsTab moduleId={moduleId || "mod-canvas-draft"} />}
                {activeTab === "events" && <EventsTab moduleId={moduleId || "mod-canvas-draft"} />}
                {activeTab === "data" && <DataTab moduleId={moduleId || "mod-canvas-draft"} />}
                {activeTab === "dependencies" && <DependenciesTab moduleId={moduleId || "mod-canvas-draft"} />}
                {activeTab === "styles" && <StylesTab moduleId={moduleId || "mod-canvas-draft"} />}
                {activeTab === "variables" && <VariablesTab moduleId={moduleId || "mod-canvas-draft"} />}
              </div>
            )}
          </div>
        </div>
        </div>

        <DragOverlay>
          {activeItem && (
            <div
              style={{
                padding: "8px 12px",
                borderRadius: "2px",
                background: "var(--aos-surface)",
                border: "1px solid var(--aos-accent)",
                fontSize: "12px",
                display: "flex",
                alignItems: "center",
                gap: "6px",
                boxShadow: "var(--shadow-lg)",
              }}
            >
              <span>{KIND_ICON[activeItem.kind] || "📦"}</span>
              <span>{activeItem.label.replace(/^\+\s*/, "")}</span>
            </div>
          )}
        </DragOverlay>
      </DndContext>

      <div style={{ marginTop: "12px", display: "flex", gap: "12px", fontSize: "12px" }}>
        <Link to="/workshop/module-interface" className="btn-nav" style={{ textDecoration: "none" }}>
          模块接口 →
        </Link>
        <Link to="/workshop/inbox" className="btn-nav" style={{ textDecoration: "none" }}>
          运营 Inbox →
        </Link>
      </div>
    </PageChrome>
  );
}

function CanvasDropZone({ children, disabled }: { children: React.ReactNode; disabled: boolean }) {
  const { setNodeRef, isOver } = useDroppable({
    id: "canvas-drop-zone",
    disabled,
  });

  return (
    <div
      ref={setNodeRef}
      className="p-slate-canvas"
      style={{
        border: isOver && !disabled ? "2px dashed var(--aos-accent)" : undefined,
        background: isOver && !disabled ? "var(--aos-indigo-bg)" : undefined,
      }}
    >
      {children}
    </div>
  );
}

function DraggablePaletteItem({ item, onClick }: { item: PaletteItem; onClick: () => void }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: item.kind,
    data: { item },
  });

  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      onClick={onClick}
      title={item.runtime ? `runtime=${item.runtime}` : undefined}
      style={{
        padding: "5px 6px",
        borderRadius: "4px",
        background: isDragging ? "var(--aos-accent-light)" : "var(--aos-surface)",
        border: `0.5px solid ${isDragging ? "var(--aos-accent)" : "var(--aos-border)"}`,
        fontSize: "10px",
        cursor: "grab",
        display: "flex",
        alignItems: "center",
        gap: "4px",
        color: "var(--aos-text)",
        opacity: isDragging ? 0.5 : 1,
        touchAction: "none",
      }}
    >
      <span style={{ fontSize: "12px" }}>{KIND_ICON[item.kind] || "📦"}</span>
      <span style={{ fontSize: "11px" }}>
        {item.label.replace(/^\+\s*/, "")}
        {item.stub ? " · stub" : ""}
      </span>
    </div>
  );
}

function SortableCanvasNode({ node, onClick, onRemove, rows, moveNode }: { node: CanvasNode; onClick: () => void; onRemove: () => void; rows: Row[]; moveNode: (id: string, dir: -1 | 1) => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: node.id,
    data: { node },
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div ref={setNodeRef} style={style} className="p-slate-widget">
      <div className="p-slate-widget-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <button type="button" className="p-slate-widget-title" {...attributes} {...listeners} onClick={onClick} style={{ background: "none", border: "none", cursor: "grab", display: "flex", alignItems: "center", gap: "4px" }}>
          <span>{KIND_ICON[node.kind] || "📦"}</span>
          <span>{node.title || node.kind}</span>
        </button>
        <div style={{ display: "flex", gap: "4px" }}>
          <button type="button" onClick={(e) => { e.stopPropagation(); moveNode(node.id, -1); }} style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", opacity: 0.7, padding: "2px 4px" }} title="上移">↑</button>
          <button type="button" onClick={(e) => { e.stopPropagation(); moveNode(node.id, 1); }} style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", opacity: 0.7, padding: "2px 4px" }} title="下移">↓</button>
          <button type="button" onClick={(e) => { e.stopPropagation(); onRemove(); }} style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", opacity: 0.7, padding: "2px 4px" }} title="删除">
            <NavIcon name="trash" style={{ width: "12px", height: "12px" }} />
          </button>
        </div>
      </div>
      <div className="p-slate-widget-body">
        <WidgetPreview node={node} rows={rows} />
      </div>
    </div>
  );
}

export function layoutNodeCount(nodes: CanvasNode[] = DEFAULT_LAYOUT): number {
  return nodes.length;
}
