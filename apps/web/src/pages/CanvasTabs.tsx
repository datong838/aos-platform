/**
 * Canvas Tab Panels — Phase C 222plan
 *
 * Content panels for CanvasPage's 9 toolbar tabs.
 * Each panel connects to existing backend APIs.
 */
import { useCallback, useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost, apiPut } from "../api/client";
import { NavIcon } from "../shell/icons";

// ============================================================
// Shared types
// ============================================================

type ModuleEvent = {
  id: string;
  moduleId: string;
  name: string;
  trigger: Record<string, unknown>;
  action: Record<string, unknown>;
  enabled: boolean;
  sortOrder: number;
};

type WorkshopVariable = {
  var_id: string;
  name: string;
  var_type: string;
  definition_type: string;
  value?: string;
  expression?: string;
  depends_on?: string[];
  module_id?: string;
  status?: string;
};

type WidgetPlugin = {
  pluginId: string;
  kind: string;
  label: string;
  runtime?: string;
  source?: string;
  installed?: boolean;
};

type DataSource = {
  id: string;
  name: string;
  type: string;
  status: string;
};

// ============================================================
// Dashboard Tab
// ============================================================

export function DashboardTab({ moduleId }: { moduleId: string }) {
  const { data, loading, error } = useJsonGet<{
    layout?: { widgets?: string[] };
    variables?: Record<string, unknown>;
    events?: unknown[];
    objectType?: string;
  }>(`/v1/modules/${moduleId}/runtime`);

  if (loading) return <TabLoading />;
  if (error) return <TabError msg={error} />;

  const widgets = data?.layout?.widgets || [];
  const eventCount = data?.events?.length || 0;
  const varCount = data?.variables ? Object.keys(data.variables).length : 0;

  return (
    <div className="canvas-tab-panel">
      <h3 className="canvas-tab-title">仪表盘</h3>
      <div className="canvas-stats-grid">
        <StatCard label="Widgets" value={widgets.length} icon="apps" color="#3b82f6" />
        <StatCard label="事件绑定" value={eventCount} icon="event" color="#f59e0b" />
        <StatCard label="变量" value={varCount} icon="variable" color="#10b981" />
        <StatCard label="状态" value={data ? "已加载" : "未加载"} icon="status" color="#8b5cf6" />
      </div>
      <div className="canvas-tab-section">
        <h4>Widget 列表</h4>
        {widgets.length === 0 ? (
          <p className="muted">无 Widget</p>
        ) : (
          <ul className="canvas-widget-list">
            {widgets.map((w, i) => (
              <li key={i} className="canvas-widget-item">
                <NavIcon name="apps" style={{ width: "12px", height: "12px", color: "#3b82f6" }} />
                <span>{w}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

// ============================================================
// Queries Tab
// ============================================================

export function QueriesTab({ moduleId: _moduleId }: { moduleId: string }) {
  const [sql, setSql] = useState("SELECT * FROM WorkOrder LIMIT 10;");
  const [result, setResult] = useState<unknown[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const runQuery = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const resp = await apiPost<{ rows?: unknown[]; error?: string }>(
        "/v1/sql/preview",
        { sql, limit: 10 }
      );
      if (resp.error) {
        setError(resp.error);
        setResult(null);
      } else {
        setResult(resp.rows || []);
      }
    } catch (e) {
      setError(String((e as Error).message || e));
    }
    setLoading(false);
  }, [sql]);

  const cols = result && result.length > 0 ? Object.keys(result[0] as Record<string, unknown>) : [];

  return (
    <div className="canvas-tab-panel">
      <h3 className="canvas-tab-title">SQL 查询</h3>
      <div className="canvas-query-editor">
        <textarea
          value={sql}
          onChange={(e) => setSql(e.target.value)}
          rows={4}
          className="canvas-sql-input"
          placeholder="输入 SQL 查询..."
          style={{
            width: "100%",
            fontFamily: "monospace",
            fontSize: "12px",
            padding: "8px",
            border: "1px solid var(--aos-border)",
            borderRadius: "4px",
            background: "var(--aos-aside)",
            color: "var(--aos-text)",
            boxSizing: "border-box",
            resize: "vertical",
          }}
        />
        <button
          type="button"
          onClick={() => void runQuery()}
          disabled={loading}
          className="btn btn-primary"
          style={{ marginTop: "8px", fontSize: "12px", padding: "5px 16px" }}
        >
          {loading ? "执行中..." : "执行查询"}
        </button>
      </div>
      {error && <p className="error" style={{ fontSize: "12px" }}>{error}</p>}
      {result && result.length > 0 && (
        <div className="canvas-query-result" style={{ marginTop: "12px", overflowX: "auto" }}>
          <table style={{ width: "100%", fontSize: "11px", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {cols.map((c) => (
                  <th key={c} style={{ textAlign: "left", padding: "4px 8px", borderBottom: "2px solid var(--aos-border)" }}>
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.slice(0, 10).map((row, i) => (
                <tr key={i}>
                  {cols.map((c) => (
                    <td key={c} style={{ padding: "3px 8px", borderBottom: "1px solid var(--aos-border-light)" }}>
                      {String((row as Record<string, unknown>)[c] ?? "")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted" style={{ fontSize: "10px", marginTop: "4px" }}>
            {result.length} 行
          </p>
        </div>
      )}
      {result && result.length === 0 && <p className="muted" style={{ fontSize: "12px" }}>无数据</p>}
    </div>
  );
}

// ============================================================
// Functions Tab
// ============================================================

export function FunctionsTab({ moduleId }: { moduleId: string }) {
  const { data, loading, error, refetch } = useJsonGet<{ items: WorkshopVariable[] }>(
    `/workshop-compute-api/variables?module_id=${moduleId}&definition_type=function`
  );

  const items = (data?.items || []).filter((v) => v.definition_type === "function");

  return (
    <div className="canvas-tab-panel">
      <h3 className="canvas-tab-title">函数 ({items.length})</h3>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
        <p className="muted" style={{ fontSize: "12px" }}>AIP Logic 绑定函数列表</p>
        <button type="button" className="btn" style={{ fontSize: "11px" }} onClick={() => void refetch()}>
          刷新
        </button>
      </div>
      {loading && <TabLoading />}
      {error && <TabError msg={error} />}
      {!loading && !error && items.length === 0 && (
        <p className="muted" style={{ fontSize: "12px" }}>无函数。在 AIP Logic 中创建函数后会出现在这里。</p>
      )}
      {items.length > 0 && (
        <ul className="canvas-func-list">
          {items.map((fn) => (
            <li key={fn.var_id} className="canvas-func-item">
              <div style={{ fontWeight: 500, fontSize: "12px" }}>{fn.name}</div>
              <div className="muted" style={{ fontSize: "10px" }}>
                type={fn.var_type} · {fn.expression || fn.value || "—"}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ============================================================
// Events Tab (with 3-step wizard)
// ============================================================

export function EventsTab({ moduleId }: { moduleId: string }) {
  const { data, loading, error, refetch } = useJsonGet<{ items: ModuleEvent[] }>(
    `/v1/modules/${moduleId}/events`
  );
  const [showWizard, setShowWizard] = useState(false);

  const events = data?.items || [];

  const handleDelete = useCallback(
    async (eventId: string) => {
      await apiDelete(`/v1/modules/${moduleId}/events/${eventId}`);
      void refetch();
    },
    [moduleId, refetch]
  );

  return (
    <div className="canvas-tab-panel">
      <h3 className="canvas-tab-title">事件绑定 ({events.length})</h3>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
        <p className="muted" style={{ fontSize: "12px" }}>Widget 事件 → 触发器 → 动作</p>
        <button type="button" className="btn btn-primary" style={{ fontSize: "11px" }} onClick={() => setShowWizard(true)}>
          + 添加事件
        </button>
      </div>
      {loading && <TabLoading />}
      {error && <TabError msg={error} />}
      {!loading && !error && events.length === 0 && (
        <p className="muted" style={{ fontSize: "12px" }}>无事件绑定。点击「+ 添加事件」创建。</p>
      )}
      {events.length > 0 && (
        <ul className="canvas-event-list">
          {events.map((evt) => (
            <li key={evt.id} className="canvas-event-item">
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 500, fontSize: "12px" }}>
                  {evt.name}
                  {!evt.enabled && <span style={{ marginLeft: "6px", fontSize: "10px", color: "#999" }}>（已禁用）</span>}
                </div>
                <div className="muted" style={{ fontSize: "10px" }}>
                  {String((evt.trigger as Record<string, unknown>)?.type || "—")} → {String((evt.action as Record<string, unknown>)?.type || "—")}
                </div>
              </div>
              <button
                type="button"
                onClick={() => void handleDelete(evt.id)}
                style={{ background: "none", border: "none", color: "#999", cursor: "pointer", padding: "2px" }}
                title="删除"
              >
                <NavIcon name="trash" style={{ width: "12px", height: "12px" }} />
              </button>
            </li>
          ))}
        </ul>
      )}
      {showWizard && (
        <EventWizard
          moduleId={moduleId}
          onClose={() => setShowWizard(false)}
          onCreated={() => {
            setShowWizard(false);
            void refetch();
          }}
        />
      )}
    </div>
  );
}

function EventWizard({
  moduleId,
  onClose,
  onCreated,
}: {
  moduleId: string;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [step, setStep] = useState(0);
  const [triggers, setTriggers] = useState<{ type: string; label: string; description: string }[]>([]);
  const [actions, setActions] = useState<{ type: string; label: string; description: string }[]>([]);
  const [selTrigger, setSelTrigger] = useState("");
  const [selAction, setSelAction] = useState("");
  const [name, setName] = useState("新事件");
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    void apiGet<{ items: { type: string; label: string; description: string }[] }>(
      `/v1/modules/${moduleId}/events/triggers/catalog`
    ).then((d) => setTriggers(d.items || []));
    void apiGet<{ items: { type: string; label: string; description: string }[] }>(
      `/v1/modules/${moduleId}/events/actions/catalog`
    ).then((d) => setActions(d.items || []));
  }, [moduleId]);

  const handleCreate = async () => {
    setCreating(true);
    setError("");
    try {
      await apiPost(`/v1/modules/${moduleId}/events`, {
        name,
        trigger: { type: selTrigger },
        action: { type: selAction },
        enabled: true,
      });
      onCreated();
    } catch (e) {
      setError(String((e as Error).message || e));
    }
    setCreating(false);
  };

  const steps = ["选择触发器", "选择动作", "确认创建"];

  return (
    <div className="canvas-wizard-overlay" style={overlayStyle}>
      <div className="canvas-wizard-modal" style={modalStyle}>
        <div className="canvas-wizard-header" style={headerStyle}>
          <h3 style={{ margin: 0, fontSize: "14px" }}>添加事件 — {steps[step]}</h3>
          <button type="button" onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer" }}>
            <NavIcon name="close" style={{ width: "14px", height: "14px" }} />
          </button>
        </div>
        <div style={{ display: "flex", gap: "4px", marginBottom: "12px" }}>
          {steps.map((_s, i) => (
            <div
              key={i}
              style={{
                flex: 1,
                height: "3px",
                borderRadius: "2px",
                background: i <= step ? "#3b82f6" : "#e5e7eb",
              }}
            />
          ))}
        </div>
        <div style={{ minHeight: "120px" }}>
          {step === 0 && (
            <div>
              <p className="muted" style={{ fontSize: "11px", marginBottom: "8px" }}>选择触发类型</p>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px" }}>
                {triggers.map((t) => (
                  <button
                    key={t.type}
                    type="button"
                    onClick={() => setSelTrigger(t.type)}
                    style={{
                      padding: "8px",
                      border: selTrigger === t.type ? "2px solid #3b82f6" : "1px solid #e5e7eb",
                      borderRadius: "6px",
                      background: selTrigger === t.type ? "#eff6ff" : "var(--aos-aside)",
                      cursor: "pointer",
                      textAlign: "left",
                    }}
                  >
                    <div style={{ fontWeight: 500, fontSize: "12px" }}>{t.label}</div>
                    <div className="muted" style={{ fontSize: "10px" }}>{t.description}</div>
                  </button>
                ))}
              </div>
            </div>
          )}
          {step === 1 && (
            <div>
              <p className="muted" style={{ fontSize: "11px", marginBottom: "8px" }}>选择动作类型</p>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px" }}>
                {actions.map((a) => (
                  <button
                    key={a.type}
                    type="button"
                    onClick={() => setSelAction(a.type)}
                    style={{
                      padding: "8px",
                      border: selAction === a.type ? "2px solid #10b981" : "1px solid #e5e7eb",
                      borderRadius: "6px",
                      background: selAction === a.type ? "#ecfdf5" : "var(--aos-aside)",
                      cursor: "pointer",
                      textAlign: "left",
                    }}
                  >
                    <div style={{ fontWeight: 500, fontSize: "12px" }}>{a.label}</div>
                    <div className="muted" style={{ fontSize: "10px" }}>{a.description}</div>
                  </button>
                ))}
              </div>
            </div>
          )}
          {step === 2 && (
            <div>
              <p className="muted" style={{ fontSize: "11px", marginBottom: "8px" }}>事件预览</p>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="事件名称"
                style={{
                  width: "100%",
                  padding: "6px 8px",
                  fontSize: "12px",
                  border: "1px solid #e5e7eb",
                  borderRadius: "4px",
                  marginBottom: "8px",
                  boxSizing: "border-box",
                }}
              />
              <div style={{ padding: "8px", background: "#f9fafb", borderRadius: "6px", fontSize: "12px" }}>
                <strong>{triggers.find((t) => t.type === selTrigger)?.label || selTrigger}</strong>
                <span style={{ margin: "0 8px", color: "#999" }}>→</span>
                <strong>{actions.find((a) => a.type === selAction)?.label || selAction}</strong>
              </div>
            </div>
          )}
        </div>
        {error && <p className="error" style={{ fontSize: "11px" }}>{error}</p>}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "12px" }}>
          {step > 0 && (
            <button type="button" className="btn" style={{ fontSize: "11px" }} onClick={() => setStep(step - 1)}>
              上一步
            </button>
          )}
          {step < 2 && (
            <button
              type="button"
              className="btn btn-primary"
              style={{ fontSize: "11px" }}
              disabled={(step === 0 && !selTrigger) || (step === 1 && !selAction)}
              onClick={() => setStep(step + 1)}
            >
              下一步
            </button>
          )}
          {step === 2 && (
            <button
              type="button"
              className="btn btn-primary"
              style={{ fontSize: "11px" }}
              disabled={creating}
              onClick={() => void handleCreate()}
            >
              {creating ? "创建中..." : "创建"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================
// Data Tab
// ============================================================

export function DataTab({ moduleId: _moduleId }: { moduleId: string }) {
  const { data, loading, error } = useJsonGet<{ items: DataSource[] }>("/v1/sources");

  const sources = data?.items || [];

  return (
    <div className="canvas-tab-panel">
      <h3 className="canvas-tab-title">数据源 ({sources.length})</h3>
      <p className="muted" style={{ fontSize: "12px", marginBottom: "8px" }}>Module 绑定的数据连接</p>
      {loading && <TabLoading />}
      {error && <TabError msg={error} />}
      {!loading && !error && sources.length === 0 && (
        <p className="muted" style={{ fontSize: "12px" }}>无数据源。请在数据连接中添加。</p>
      )}
      {sources.length > 0 && (
        <ul className="canvas-source-list">
          {sources.map((s) => (
            <li key={s.id} className="canvas-source-item">
              <div style={{ fontWeight: 500, fontSize: "12px" }}>{s.name}</div>
              <div className="muted" style={{ fontSize: "10px" }}>
                {s.type} · {s.status}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ============================================================
// Dependencies Tab
// ============================================================

export function DependenciesTab({ moduleId }: { moduleId: string }) {
  const { data, loading, error } = useJsonGet<{ items: WorkshopVariable[] }>(
    `/workshop-compute-api/variables?module_id=${moduleId}`
  );

  const variables = data?.items || [];
  const depEdges = variables
    .filter((v) => v.depends_on && v.depends_on.length > 0)
    .map((v) => ({
      from: v.name,
      to: v.depends_on!.map((d) => d),
    }));

  return (
    <div className="canvas-tab-panel">
      <h3 className="canvas-tab-title">依赖关系</h3>
      <p className="muted" style={{ fontSize: "12px", marginBottom: "8px" }}>
        变量依赖链 ({depEdges.length} 条边)
      </p>
      {loading && <TabLoading />}
      {error && <TabError msg={error} />}
      {!loading && !error && depEdges.length === 0 && (
        <p className="muted" style={{ fontSize: "12px" }}>无依赖关系。</p>
      )}
      {depEdges.length > 0 && (
        <div style={{ fontSize: "11px", lineHeight: "1.8" }}>
          {depEdges.map((edge, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: "6px", padding: "4px 0" }}>
              <span style={{ fontWeight: 500 }}>{edge.from}</span>
              <span style={{ color: "#999" }}>→</span>
              <span className="muted">{edge.to.join(", ")}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================================
// Styles Tab
// ============================================================

const STYLE_PRESETS = [
  { id: "light", name: "浅色", primary: "#3b82f6", bg: "#ffffff", text: "#1f2937" },
  { id: "dark", name: "深色", primary: "#6366f1", bg: "#1f2937", text: "#f9fafb" },
  { id: "compact", name: "紧凑", primary: "#059669", bg: "#ffffff", text: "#064e3b" },
  { id: "vivid", name: "鲜艳", primary: "#e11d48", bg: "#fff1f2", text: "#881337" },
];

export function StylesTab({ moduleId: _moduleId }: { moduleId: string }) {
  const [activePreset, setActivePreset] = useState("light");
  const [cssVars, setCssVars] = useState({ primary: "#3b82f6", radius: "6px", fontSize: "12px" });

  return (
    <div className="canvas-tab-panel">
      <h3 className="canvas-tab-title">样式管理</h3>
      <div style={{ marginBottom: "12px" }}>
        <p className="muted" style={{ fontSize: "12px", marginBottom: "6px" }}>主题预设</p>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px" }}>
          {STYLE_PRESETS.map((preset) => (
            <button
              key={preset.id}
              type="button"
              onClick={() => {
                setActivePreset(preset.id);
                setCssVars({ ...cssVars, primary: preset.primary });
              }}
              style={{
                padding: "8px",
                border: activePreset === preset.id ? "2px solid #3b82f6" : "1px solid #e5e7eb",
                borderRadius: "6px",
                background: preset.bg,
                color: preset.text,
                cursor: "pointer",
                textAlign: "left",
              }}
            >
              <div style={{ fontWeight: 500, fontSize: "12px" }}>{preset.name}</div>
              <div style={{ width: "20px", height: "4px", background: preset.primary, borderRadius: "2px", marginTop: "4px" }} />
            </button>
          ))}
        </div>
      </div>
      <div>
        <p className="muted" style={{ fontSize: "12px", marginBottom: "6px" }}>CSS 变量</p>
        <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
          <CssVarInput label="主色" value={cssVars.primary} onChange={(v) => setCssVars({ ...cssVars, primary: v })} type="color" />
          <CssVarInput label="圆角" value={cssVars.radius} onChange={(v) => setCssVars({ ...cssVars, radius: v })} />
          <CssVarInput label="字号" value={cssVars.fontSize} onChange={(v) => setCssVars({ ...cssVars, fontSize: v })} />
        </div>
      </div>
    </div>
  );
}

function CssVarInput({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (v: string) => void; type?: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
      <label style={{ fontSize: "11px", width: "60px" }}>{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          flex: 1,
          padding: "4px 6px",
          fontSize: "11px",
          border: "1px solid #e5e7eb",
          borderRadius: "4px",
        }}
      />
    </div>
  );
}

// ============================================================
// Variables Tab
// ============================================================

const VAR_TYPES = ["object_set", "string", "numeric", "boolean", "date", "array", "struct"];
const VAR_SCOPES = ["module", "session", "global"];

export function VariablesTab({ moduleId }: { moduleId: string }) {
  const { data, loading, error, refetch } = useJsonGet<{ items: WorkshopVariable[] }>(
    `/workshop-compute-api/variables?module_id=${moduleId}`
  );
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<WorkshopVariable | null>(null);

  const variables = data?.items || [];

  const handleSave = async (varData: Partial<WorkshopVariable>) => {
    if (editing) {
      await apiPut(`/workshop-compute-api/variables/${editing.var_id}`, { ...varData, module_id: moduleId });
    } else {
      await apiPost("/workshop-compute-api/variables", { ...varData, module_id: moduleId });
    }
    setShowForm(false);
    setEditing(null);
    void refetch();
  };

  return (
    <div className="canvas-tab-panel">
      <h3 className="canvas-tab-title">变量 ({variables.length})</h3>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
        <p className="muted" style={{ fontSize: "12px" }}>变量管理器 — 7 种类型 · 3 种作用域</p>
        <button
          type="button"
          className="btn btn-primary"
          style={{ fontSize: "11px" }}
          onClick={() => {
            setEditing(null);
            setShowForm(true);
          }}
        >
          + 新建变量
        </button>
      </div>
      {loading && <TabLoading />}
      {error && <TabError msg={error} />}
      {!loading && !error && variables.length === 0 && (
        <p className="muted" style={{ fontSize: "12px" }}>无变量。</p>
      )}
      {variables.length > 0 && (
        <table style={{ width: "100%", fontSize: "11px", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th style={thStyle}>名称</th>
              <th style={thStyle}>类型</th>
              <th style={thStyle}>定义</th>
              <th style={thStyle}>值/表达式</th>
              <th style={thStyle}>操作</th>
            </tr>
          </thead>
          <tbody>
            {variables.map((v) => (
              <tr key={v.var_id}>
                <td style={tdStyle}>{v.name}</td>
                <td style={tdStyle}><span className="badge">{v.var_type}</span></td>
                <td style={tdStyle}>{v.definition_type}</td>
                <td style={tdStyle} className="muted">{v.value || v.expression || "—"}</td>
                <td style={tdStyle}>
                  <button
                    type="button"
                    onClick={() => {
                      setEditing(v);
                      setShowForm(true);
                    }}
                    style={{ background: "none", border: "none", color: "#3b82f6", cursor: "pointer", fontSize: "11px" }}
                  >
                    编辑
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {showForm && (
        <VariableForm
          variable={editing}
          onSave={handleSave}
          onCancel={() => {
            setShowForm(false);
            setEditing(null);
          }}
        />
      )}
    </div>
  );
}

function VariableForm({
  variable,
  onSave,
  onCancel,
}: {
  variable: WorkshopVariable | null;
  onSave: (data: Partial<WorkshopVariable>) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(variable?.name || "");
  const [varType, setVarType] = useState(variable?.var_type || "string");
  const [defType, setDefType] = useState(variable?.definition_type || "static");
  const [value, setValue] = useState(variable?.value || "");
  const [expression, setExpression] = useState(variable?.expression || "");
  const [scope, setScope] = useState("module");

  return (
    <div className="canvas-wizard-overlay" style={overlayStyle}>
      <div style={{ ...modalStyle, maxWidth: "400px" }}>
        <div style={headerStyle}>
          <h3 style={{ margin: 0, fontSize: "14px" }}>{variable ? "编辑变量" : "新建变量"}</h3>
          <button type="button" onClick={onCancel} style={{ background: "none", border: "none", cursor: "pointer" }}>
            <NavIcon name="close" style={{ width: "14px", height: "14px" }} />
          </button>
        </div>
        <FormField label="名称">
          <input value={name} onChange={(e) => setName(e.target.value)} style={inputStyle} />
        </FormField>
        <FormField label="类型">
          <select value={varType} onChange={(e) => setVarType(e.target.value)} style={inputStyle}>
            {VAR_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </FormField>
        <FormField label="作用域">
          <select value={scope} onChange={(e) => setScope(e.target.value)} style={inputStyle}>
            {VAR_SCOPES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </FormField>
        <FormField label="定义方式">
          <select value={defType} onChange={(e) => setDefType(e.target.value)} style={inputStyle}>
            <option value="static">静态值</option>
            <option value="function">函数</option>
            <option value="object_set_aggregation">聚合</option>
            <option value="object_property">对象属性</option>
            <option value="variable_transformation">变量变换</option>
          </select>
        </FormField>
        {defType === "static" ? (
          <FormField label="值">
            <input value={value} onChange={(e) => setValue(e.target.value)} style={inputStyle} />
          </FormField>
        ) : (
          <FormField label="表达式">
            <textarea value={expression} onChange={(e) => setExpression(e.target.value)} rows={3} style={{ ...inputStyle, resize: "vertical" }} />
          </FormField>
        )}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "12px" }}>
          <button type="button" className="btn" style={{ fontSize: "11px" }} onClick={onCancel}>取消</button>
          <button type="button" className="btn btn-primary" style={{ fontSize: "11px" }} disabled={!name} onClick={() => onSave({ name, var_type: varType, definition_type: defType, value, expression })}>
            保存
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// Widget Registry Tab
// ============================================================

export function WidgetRegistryTab() {
  const { data, loading, error } = useJsonGet<{ items: WidgetPlugin[]; palette?: WidgetPlugin[] }>(
    "/v1/widget-plugins"
  );
  const plugins = data?.items || data?.palette || [];

  return (
    <div className="canvas-tab-panel">
      <h3 className="canvas-tab-title">组件注册表 ({plugins.length})</h3>
      <p className="muted" style={{ fontSize: "12px", marginBottom: "8px" }}>可用的 Widget 插件</p>
      {loading && <TabLoading />}
      {error && <TabError msg={error} />}
      {!loading && !error && plugins.length === 0 && (
        <p className="muted" style={{ fontSize: "12px" }}>无组件。使用 install_plugin 安装新插件。</p>
      )}
      {plugins.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "6px" }}>
          {plugins.map((p) => (
            <div key={`${p.pluginId}-${p.kind}`} style={{ padding: "8px", border: "1px solid #e5e7eb", borderRadius: "6px" }}>
              <div style={{ fontWeight: 500, fontSize: "11px" }}>{p.label}</div>
              <div className="muted" style={{ fontSize: "10px" }}>
                {p.pluginId} · {p.kind}
                {p.runtime ? ` · ${p.runtime}` : ""}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================================
// Shared helpers
// ============================================================

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "4px 8px",
  borderBottom: "2px solid var(--aos-border)",
  fontSize: "11px",
  fontWeight: 600,
};

const tdStyle: React.CSSProperties = {
  padding: "4px 8px",
  borderBottom: "1px solid var(--aos-border-light)",
};

const overlayStyle: React.CSSProperties = {
  position: "fixed",
  top: 0, left: 0, right: 0, bottom: 0,
  background: "rgba(0,0,0,0.3)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  zIndex: 1000,
};

const modalStyle: React.CSSProperties = {
  background: "var(--aos-aside, #fff)",
  borderRadius: "8px",
  padding: "16px",
  minWidth: "420px",
  maxWidth: "600px",
  maxHeight: "80vh",
  overflowY: "auto",
  boxShadow: "0 8px 32px rgba(0,0,0,0.15)",
};

const headerStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  marginBottom: "12px",
  paddingBottom: "8px",
  borderBottom: "1px solid var(--aos-border)",
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "6px 8px",
  fontSize: "12px",
  border: "1px solid #e5e7eb",
  borderRadius: "4px",
  boxSizing: "border-box",
};

function FormField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: "8px" }}>
      <label style={{ display: "block", fontSize: "11px", marginBottom: "4px", fontWeight: 500 }}>{label}</label>
      {children}
    </div>
  );
}

function StatCard({ label, value, icon, color }: { label: string; value: string | number; icon: string; color: string }) {
  return (
    <div style={{ padding: "12px", borderRadius: "8px", background: "var(--aos-aside)", border: "1px solid var(--aos-border-light)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: "11px", color: "#999" }}>{label}</span>
        <NavIcon name={icon as "apps"} style={{ width: "14px", height: "14px", color }} />
      </div>
      <div style={{ fontSize: "20px", fontWeight: 700, color }}>{value}</div>
    </div>
  );
}

function TabLoading() {
  return <p className="muted" style={{ fontSize: "12px", padding: "12px" }}>加载中...</p>;
}

function TabError({ msg }: { msg: string }) {
  return <p className="error" style={{ fontSize: "12px", padding: "12px" }}>加载失败：{msg}</p>;
}

// ============================================================
// useJsonGet hook (local copy for this module)
// ============================================================

function useJsonGet<T>(url: string): {
  data: T | null;
  loading: boolean;
  error: string;
  refetch: () => void;
} {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    apiGet<T>(url)
      .then((d) => {
        if (!cancelled) {
          setData(d);
          setError("");
        }
      })
      .catch((e) => {
        if (!cancelled) setError(String((e as Error).message || e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [url, nonce]);

  return {
    data,
    loading,
    error,
    refetch: () => setNonce((n) => n + 1),
  };
}

// ============================================================
// Workflow Mode — SVG 事件编排图
// ============================================================

type WorkflowNode = {
  id: string;
  type: "trigger" | "condition" | "action";
  label: string;
  icon: string;
  detail?: string;
  enabled?: boolean;
};

type WorkflowEdge = {
  from: string;
  to: string;
  condition?: "true" | "false" | "always";
};

export function WorkflowMode({ moduleId }: { moduleId: string }) {
  const { data, loading, error } = useJsonGet<{ items: ModuleEvent[] }>(
    `/v1/modules/${moduleId}/events`
  );

  const events = data?.items || [];
  const [selectedNode, setSelectedNode] = useState<string>("");

  // Build workflow nodes and edges from events
  const { nodes, edges } = buildWorkflowGraph(events);

  return (
    <div style={{ display: "flex", height: "100%", minHeight: "400px" }}>
      {/* Left: Trigger List */}
      <aside style={{ width: "200px", borderRight: "1px solid var(--aos-border)", padding: "8px", overflowY: "auto" }}>
        <div style={{ fontSize: "11px", fontWeight: 600, marginBottom: "8px", color: "var(--aos-text-secondary)" }}>
          事件触发器 ({events.length})
        </div>
        {loading && <TabLoading />}
        {error && <TabError msg={error} />}
        {!loading && !error && events.length === 0 && (
          <p className="muted" style={{ fontSize: "11px" }}>无触发器</p>
        )}
        {events.map((evt) => {
          const trigType = String((evt.trigger as Record<string, unknown>)?.type || "unknown");
          const actType = String((evt.action as Record<string, unknown>)?.type || "unknown");
          const icon = TRIGGER_ICONS[trigType] || "⚡";
          return (
            <div
              key={evt.id}
              onClick={() => setSelectedNode(evt.id)}
              style={{
                padding: "6px 8px",
                borderRadius: "6px",
                marginBottom: "4px",
                cursor: "pointer",
                background: selectedNode === evt.id ? "#EFF6FF" : "var(--aos-aside)",
                border: selectedNode === evt.id ? "1px solid #BFDBFE" : "1px solid transparent",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                <span style={{ fontSize: "12px" }}>{icon}</span>
                <span style={{ fontSize: "11px", fontWeight: 600, color: evt.enabled ? "#1E40AF" : "#999" }}>
                  {evt.name}
                </span>
              </div>
              <div className="muted" style={{ fontSize: "10px" }}>
                {trigType} → {actType}
              </div>
            </div>
          );
        })}
      </aside>

      {/* Center: SVG Canvas */}
      <div style={{ flex: 1, padding: "12px", overflow: "auto", position: "relative" }}>
        <svg width="100%" height="100%" viewBox="0 0 600 400" style={{ minWidth: "500px" }}>
          {/* Render edges (connection lines) */}
          {edges.map((edge, i) => {
            const fromNode = nodes.find((n) => n.id === edge.from);
            const toNode = nodes.find((n) => n.id === edge.to);
            if (!fromNode || !toNode) return null;
            const fx = fromNode.x + 80;
            const fy = fromNode.y + 20;
            const tx = toNode.x;
            const ty = toNode.y + 20;
            const midX = (fx + tx) / 2;
            const color = edge.condition === "false" ? "#ef4444" : "#10b981";
            const dashArray = edge.condition === "false" ? "4 4" : "none";
            return (
              <g key={`edge-${i}`}>
                <path
                  d={`M ${fx} ${fy} C ${midX} ${fy}, ${midX} ${ty}, ${tx} ${ty}`}
                  fill="none"
                  stroke={color}
                  strokeWidth="2"
                  strokeDasharray={dashArray}
                  markerEnd={`url(#arrow-${color === "#ef4444" ? "red" : "green"})`}
                />
                {edge.condition && edge.condition !== "always" && (
                  <text x={midX} y={(fy + ty) / 2 - 5} fill={color} fontSize="9" textAnchor="middle">
                    {edge.condition}
                  </text>
                )}
              </g>
            );
          })}

          {/* Arrow markers */}
          <defs>
            <marker id="arrow-green" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">
              <polygon points="0 0, 7 3, 0 6" fill="#10b981" />
            </marker>
            <marker id="arrow-red" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">
              <polygon points="0 0, 7 3, 0 6" fill="#ef4444" />
            </marker>
            <marker id="arrow-blue" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">
              <polygon points="0 0, 7 3, 0 6" fill="#3b82f6" />
            </marker>
          </defs>

          {/* Render nodes */}
          {nodes.map((node) => {
            const colors = NODE_COLORS[node.type];
            return (
              <g
                key={node.id}
                transform={`translate(${node.x}, ${node.y})`}
                onClick={() => setSelectedNode(node.id)}
                style={{ cursor: "pointer" }}
              >
                {node.type === "trigger" && (
                  <circle cx="40" cy="20" r="24" fill={colors.fill} stroke={colors.stroke} strokeWidth="2" />
                )}
                {node.type === "condition" && (
                  <rect x="10" y="0" width="60" height="40" rx="4" fill={colors.fill} stroke={colors.stroke} strokeWidth="2" transform="rotate(45 40 20)" />
                )}
                {node.type === "action" && (
                  <rect x="8" y="2" width="64" height="36" rx="6" fill={colors.fill} stroke={colors.stroke} strokeWidth="2" />
                )}
                <text x="40" y="16" textAnchor="middle" fontSize="14" fill={colors.text}>
                  {node.icon}
                </text>
                <text x="40" y="32" textAnchor="middle" fontSize="8" fill={colors.text} fontWeight="600">
                  {node.label.length > 12 ? node.label.slice(0, 10) + "…" : node.label}
                </text>
              </g>
            );
          })}
        </svg>
        {nodes.length === 0 && !loading && (
          <p className="muted" style={{ textAlign: "center", fontSize: "12px", marginTop: "40px" }}>
            无事件。在 Events Tab 添加事件后，工作流图将自动生成。
          </p>
        )}
      </div>

      {/* Right: Node Detail */}
      <aside style={{ width: "200px", borderLeft: "1px solid var(--aos-border)", padding: "8px" }}>
        {selectedNode ? (
          <NodeDetail node={nodes.find((n) => n.id === selectedNode)} event={events.find((e) => e.id === selectedNode)} />
        ) : (
          <p className="muted" style={{ fontSize: "11px" }}>选择一个节点查看详情</p>
        )}
      </aside>
    </div>
  );
}

function NodeDetail({ node, event }: { node: WorkflowNode | undefined; event: ModuleEvent | undefined }) {
  if (!node) return <p className="muted" style={{ fontSize: "11px" }}>节点不存在</p>;
  return (
    <div>
      <div style={{ fontSize: "11px", fontWeight: 600, marginBottom: "8px" }}>
        {node.icon} {node.label}
      </div>
      <div className="muted" style={{ fontSize: "10px", marginBottom: "6px" }}>
        类型: {node.type}
      </div>
      {event && (
        <>
          <div style={{ fontSize: "10px", marginBottom: "4px" }}>
            <strong>触发器:</strong> {String((event.trigger as Record<string, unknown>)?.type || "—")}
          </div>
          <div style={{ fontSize: "10px", marginBottom: "4px" }}>
            <strong>动作:</strong> {String((event.action as Record<string, unknown>)?.type || "—")}
          </div>
          <div style={{ fontSize: "10px", marginBottom: "4px" }}>
            <strong>状态:</strong> {event.enabled ? "✅ 启用" : "⏸ 禁用"}
          </div>
        </>
      )}
    </div>
  );
}

const TRIGGER_ICONS: Record<string, string> = {
  on_click: "🖱",
  on_select: "👆",
  on_change: "✏️",
  on_load: "🕐",
  interval: "⏰",
  custom: "⚙️",
};

const NODE_COLORS = {
  trigger: { fill: "#DBEAFE", stroke: "#3B82F6", text: "#1E40AF" },
  condition: { fill: "#FEF3C7", stroke: "#F59E0B", text: "#92400E" },
  action: { fill: "#D1FAE5", stroke: "#10B981", text: "#065F46" },
};

function buildWorkflowGraph(events: ModuleEvent[]): { nodes: (WorkflowNode & { x: number; y: number })[]; edges: WorkflowEdge[] } {
  const nodes: (WorkflowNode & { x: number; y: number })[] = [];
  const edges: WorkflowEdge[] = [];

  events.forEach((evt, idx) => {
    const trigType = String((evt.trigger as Record<string, unknown>)?.type || "unknown");
    const actType = String((evt.action as Record<string, unknown>)?.type || "unknown");
    const y = idx * 80 + 20;
    const trigId = `trig-${evt.id}`;
    const actId = `act-${evt.id}`;

    nodes.push({
      id: trigId,
      type: "trigger",
      label: evt.name,
      icon: TRIGGER_ICONS[trigType] || "⚡",
      x: 40,
      y,
      enabled: evt.enabled,
    });
    nodes.push({
      id: actId,
      type: "action",
      label: actType,
      icon: "▶",
      x: 300,
      y,
      enabled: evt.enabled,
    });
    edges.push({ from: trigId, to: actId, condition: "always" });
  });

  return { nodes, edges };
}

