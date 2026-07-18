import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPatch, apiPost } from "../api/client";
import { PageChrome } from "../components/PageChrome";
import { BpLinkRow, BpToolbar } from "./s2/blueprintUi";

export type CanvasNode = {
  id: string;
  kind: "table" | "filter" | "buddy" | "overlay";
  title: string;
  config?: { site?: string; objectType?: string };
};

const DEFAULT_LAYOUT: CanvasNode[] = [
  { id: "n-filter", kind: "filter", title: "Filter · site", config: { site: "DC-East" } },
  { id: "n-table", kind: "table", title: "Object Table · WorkOrder", config: { objectType: "WorkOrder" } },
  { id: "n-buddy", kind: "buddy", title: "Buddy Chip" },
];

type ModuleRow = {
  id: string;
  name: string;
  widgets?: unknown[];
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

export function normalizeLayout(widgets: unknown): CanvasNode[] {
  if (!Array.isArray(widgets) || widgets.length === 0) return structuredClone(DEFAULT_LAYOUT);
  if (typeof widgets[0] === "string") {
    return (widgets as string[]).map((w, i) => {
      const lower = w.toLowerCase();
      const kind: CanvasNode["kind"] = lower.includes("filter")
        ? "filter"
        : lower.includes("buddy") || lower.includes("chat")
          ? "buddy"
          : lower.includes("overlay")
            ? "overlay"
            : "table";
      return {
        id: `n-${i}-${kind}`,
        kind,
        title: w,
        config:
          kind === "filter"
            ? { site: "DC-East" }
            : kind === "table"
              ? { objectType: "WorkOrder" }
              : undefined,
      };
    });
  }
  return (widgets as CanvasNode[]).map((n, i) => ({
    id: n.id || `n-${i}`,
    kind: n.kind || "table",
    title: n.title || n.kind || `node-${i}`,
    config: n.config,
  }));
}

const WIDGET_PALETTE: { kind: CanvasNode["kind"]; label: string; tone?: "violet" }[] = [
  { kind: "filter", label: "+ Filter List" },
  { kind: "table", label: "+ Object Table" },
  { kind: "buddy", label: "+ Buddy Chip" },
  { kind: "overlay", label: "+ Object View · Wiki", tone: "violet" },
];

function sectionLabel(kind: CanvasNode["kind"]): string {
  if (kind === "filter") return "筛选";
  if (kind === "table") return "主表";
  if (kind === "buddy") return "Buddy";
  return "Overlay 详情";
}

function WidgetPreview({ node }: { node: CanvasNode }) {
  if (node.kind === "filter") {
    return (
      <div className="bp-canvas-widget">
        <span className="bp-tag">Filter List</span>
        <span className="muted">site = {node.config?.site || "DC-East"}</span>
      </div>
    );
  }
  if (node.kind === "table") {
    return (
      <div className="bp-canvas-widget bp-canvas-widget-table">
        <div className="bp-canvas-widget-row bp-canvas-widget-head">
          <span>id</span>
          <span>title</span>
          <span>status</span>
        </div>
        <div className="bp-canvas-widget-row muted">
          <span>wo-1001</span>
          <span>泵房巡检</span>
          <span>open</span>
        </div>
        <div className="bp-canvas-widget-row muted">
          <span>wo-1002</span>
          <span>…</span>
          <span>…</span>
        </div>
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
  const [dragId, setDragId] = useState<string | null>(null);

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
    setModules(res.items || []);
    const prefer =
      res.items?.find((m) => m.id.includes("canvas") || (m.widgets || []).length > 0) ||
      res.items?.[0];
    if (prefer) {
      setModuleId(prefer.id);
      const layout = normalizeLayout(prefer.widgets);
      setNodes(layout);
      setSelected(layout[0]?.id || "");
      setDirty(false);
    }
  }, []);

  useEffect(() => {
    loadModules().catch((e) => setErr(String(e.message || e)));
  }, [loadModules]);

  async function onSelectModule(id: string) {
    setModuleId(id);
    setErr(null);
    try {
      const mod = await apiGet<ModuleRow>(`/v1/modules/${encodeURIComponent(id)}`);
      const layout = normalizeLayout(mod.widgets);
      setNodes(layout);
      setSelected(layout[0]?.id || "");
      setDirty(false);
      setMsg(`已加载 ${mod.name || id}`);
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

  function addNode(kind: CanvasNode["kind"]) {
    const id = `n-${kind}-${Date.now().toString(36)}`;
    const title =
      kind === "filter"
        ? "Filter · site"
        : kind === "table"
          ? "Object Table"
          : kind === "buddy"
            ? "Buddy Chip"
            : "Overlay · Object View";
    const config =
      kind === "filter"
        ? { site: "DC-East" }
        : kind === "table"
          ? { objectType: "WorkOrder" }
          : undefined;
    setNodes((prev) => [...prev, { id, kind, title, config }]);
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

  function onDrop(targetId: string) {
    if (!dragId || dragId === targetId) return;
    setNodes((prev) => {
      const from = prev.findIndex((n) => n.id === dragId);
      const to = prev.findIndex((n) => n.id === targetId);
      if (from < 0 || to < 0) return prev;
      const copy = [...prev];
      const [item] = copy.splice(from, 1);
      copy.splice(to, 0, item);
      return copy;
    });
    setDragId(null);
    setDirty(true);
  }

  async function saveLayout() {
    if (!moduleId) {
      setErr("请先选择 Module");
      return;
    }
    setErr(null);
    try {
      await apiPatch(`/v1/modules/${encodeURIComponent(moduleId)}`, { widgets: nodes });
      const rt = await apiGet<{ layout?: { widgets?: unknown } }>(
        `/v1/modules/${encodeURIComponent(moduleId)}/runtime`,
      );
      setDirty(false);
      setMsg(
        `已保存 Layout · runtime widgets=${Array.isArray(rt.layout?.widgets) ? rt.layout!.widgets!.length : "?"} · 可打开模块接口页核对`,
      );
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  return (
    <PageChrome
      title="画布编辑"
      lede="90 · Layout 树 / Widget 调色板 / 配置面板 · 构建态非运行态"
    >
      <BpToolbar>
        <label className="muted">
          Module{" "}
          <select
            aria-label="module"
            value={moduleId}
            onChange={(e) => void onSelectModule(e.target.value)}
          >
            {modules.length === 0 && <option value="">（无模块）</option>}
            {modules.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name} ({m.id})
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="btn" disabled={!dirty} onClick={() => void saveLayout()}>
          {dirty ? "保存 Layout *" : "已保存"}
        </button>
        <Link to="/workshop/inbox" className="btn" style={{ textDecoration: "none" }}>
          预览运行态 →
        </Link>
        <Link to="/workshop/publish" className="muted">
          发布 ▾
        </Link>
      </BpToolbar>
      {msg && <p className="aos-text">{msg}</p>}
      {err && <p className="error">{err}</p>}

      <div className="bp-canvas-shell">
        <div className="bp-canvas-tree">
          <div className="bp-ws-section-title">Layout</div>
          <div className="bp-canvas-layout-item bp-canvas-layout-active">▾ Header</div>
          <div className="bp-canvas-layout-item" style={{ paddingLeft: "0.5rem" }}>
            图标 / 标题
          </div>
          <div className="bp-canvas-layout-item bp-canvas-layout-active">▾ Page: Inbox</div>
          {nodes.map((n) => (
            <button
              key={n.id}
              type="button"
              className={
                n.id === selected
                  ? "bp-canvas-layout-item bp-canvas-layout-active"
                  : "bp-canvas-layout-item"
              }
              style={{
                paddingLeft: "0.5rem",
                background: "none",
                border: "none",
                cursor: "pointer",
                textAlign: "left",
                width: "100%",
              }}
              onClick={() => setSelected(n.id)}
            >
              {sectionLabel(n.kind)} · {n.title}
            </button>
          ))}
          {nodes.some((n) => n.kind === "overlay") && (
            <div className="bp-canvas-layout-item" style={{ paddingLeft: "0.5rem", opacity: 0.85 }}>
              Overlay 详情
            </div>
          )}
          <div className="bp-canvas-layout-item" style={{ marginTop: "0.75rem", opacity: 0.6 }}>
            变量 / Events
          </div>
        </div>

        <div className="bp-canvas-center">
          <p className="muted" style={{ fontSize: "0.75rem", marginBottom: "0.65rem" }}>
            画布 · Header / Page / Section / Overlay · 先建 Object Set 变量再拖 Widget
          </p>
          <div className="bp-canvas-palette">
            {WIDGET_PALETTE.map((w) => (
              <button
                key={w.label}
                type="button"
                className={w.tone === "violet" ? "bp-canvas-chip bp-canvas-chip-violet" : "bp-canvas-chip"}
                onClick={() => addNode(w.kind)}
              >
                {w.label}
              </button>
            ))}
          </div>

          {nodes.map((n) => (
            <div
              key={n.id}
              className={n.kind === "overlay" ? "bp-canvas-section bp-canvas-section-violet" : "bp-canvas-section"}
              draggable
              onDragStart={() => setDragId(n.id)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => onDrop(n.id)}
              style={{
                outline: n.id === selected ? "1px solid rgba(56,189,248,0.45)" : undefined,
              }}
              onClick={() => setSelected(n.id)}
            >
              <div className="bp-canvas-section-head">
                <span className="muted" style={{ fontSize: "0.625rem" }}>
                  Section · {sectionLabel(n.kind)}
                </span>
                <div className="bp-canvas-section-actions">
                  <button type="button" className="btn" onClick={(e) => { e.stopPropagation(); moveNode(n.id, -1); }}>
                    ↑
                  </button>
                  <button type="button" className="btn" onClick={(e) => { e.stopPropagation(); moveNode(n.id, 1); }}>
                    ↓
                  </button>
                  <button type="button" className="btn" onClick={(e) => { e.stopPropagation(); removeNode(n.id); }}>
                    删
                  </button>
                </div>
              </div>
              <WidgetPreview node={n} />
            </div>
          ))}

          <div className="bp-ws-section-title" style={{ marginTop: "1rem" }}>
            预览运行态
          </div>
          <p className="muted">
            Filter site=<strong>{site}</strong> · Table=<strong>{objectType}</strong>
          </p>
          <button type="button" className="btn" onClick={() => void runPreview()}>
            刷新 Object Table
          </button>
          <button
            type="button"
            className="btn"
            style={{ marginLeft: 8 }}
            onClick={() => setPreviewOn((v) => !v)}
          >
            {previewOn ? "暂停预览" : "开启预览"}
          </button>
          <ul className="card-list" style={{ marginTop: 12 }}>
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

        <div className="bp-canvas-config">
          <div className="bp-ws-section-title">配置面板</div>
          {!node ? (
            <p className="muted">未选中 Widget</p>
          ) : (
            <>
              <p className="muted">Section · 条件显隐：关</p>
              <p className="muted">列宽：Flex</p>
              <div
                className="bp-object-panel"
                style={{ padding: "0.5rem", marginTop: "0.5rem", fontSize: "0.75rem" }}
              >
                Widget 选择器
                <br />
                {node.kind} ▾
              </div>
              <p style={{ marginTop: 8 }}>
                <strong>{node.kind}</strong> · {node.id}
              </p>
              <label className="muted">
                标题{" "}
                <input
                  value={node.title}
                  onChange={(e) => updateNode(node.id, { title: e.target.value })}
                />
              </label>
              {node.kind === "filter" && (
                <label className="muted" style={{ display: "block", marginTop: 8 }}>
                  site{" "}
                  <input
                    value={node.config?.site || ""}
                    onChange={(e) =>
                      updateNode(node.id, { config: { ...node.config, site: e.target.value } })
                    }
                  />
                </label>
              )}
              {node.kind === "table" && (
                <label className="muted" style={{ display: "block", marginTop: 8 }}>
                  objectType{" "}
                  <input
                    value={node.config?.objectType || "WorkOrder"}
                    onChange={(e) =>
                      updateNode(node.id, {
                        config: { ...node.config, objectType: e.target.value },
                      })
                    }
                  />
                </label>
              )}
              <p className="muted" style={{ marginTop: 12, fontSize: "0.625rem" }}>
                构建态 · 非运行态
              </p>
            </>
          )}
        </div>
      </div>

      <BpLinkRow
        links={[
          { to: "/workshop/module-interface", label: "模块接口" },
          { to: "/workshop/inbox", label: "运营 Inbox" },
        ]}
      />
    </PageChrome>
  );
}

export function layoutNodeCount(nodes: CanvasNode[] = DEFAULT_LAYOUT): number {
  return nodes.length;
}
