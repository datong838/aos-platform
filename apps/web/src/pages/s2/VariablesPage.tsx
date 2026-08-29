import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { PageChrome } from "../../components/PageChrome";
import { apiDelete, apiGet, apiPost, apiPut } from "../../api/client";

type VarType = "ObjectSet" | "Object" | "String" | "Number" | "Boolean" | "DateRange" | "Array";
type VarScope = "page" | "app" | "global";

type VariableItem = {
  id: string;
  name: string;
  type: VarType;
  scope: VarScope;
  initialValue: string;
  bindings: string[];
  description?: string;
  isSystem?: boolean;
  readOnlyReason?: string;
};

type ModuleOption = { id: string; name: string };

type ApiVariable = {
  id?: string;
  name?: string;
  varType?: string;
  group?: string;
  initialValue?: unknown;
  currentValue?: unknown;
  description?: string;
  bindings?: string[];
};

type EditorState = {
  mode: "create" | "edit";
  id?: string;
  name: string;
  type: VarType;
  scope: VarScope;
  initialValue: string;
  description: string;
};

/**按类型分组的类别（合并为 5 大组，便于左侧分组导航）*/
export type VarTypeGroup = "data" | "scalar" | "flag" | "time" | "list";

/**将 VarType 映射到 5 大分组（纯函数，便于测试）*/
export function classifyVarType(type: VarType): VarTypeGroup {
  switch (type) {
    case "ObjectSet":
    case "Object":
      return "data";
    case "String":
    case "Number":
      return "scalar";
    case "Boolean":
      return "flag";
    case "DateRange":
      return "time";
    case "Array":
      return "list";
  }
}

export const VAR_TYPE_GROUP_LABELS: Record<VarTypeGroup, string> = {
  data: "数据对象",
  scalar: "标量",
  flag: "布尔",
  time: "时间",
  list: "数组",
};

/** API varType → UI VarType */
export function normalizeVarType(raw: string | undefined | null): VarType {
  const key = String(raw || "string").trim().toLowerCase();
  switch (key) {
    case "objectset":
    case "object_set":
      return "ObjectSet";
    case "object":
      return "Object";
    case "number":
    case "int":
    case "float":
      return "Number";
    case "boolean":
    case "bool":
      return "Boolean";
    case "daterange":
    case "date_range":
    case "date":
      return "DateRange";
    case "array":
    case "list":
      return "Array";
    case "string":
    default:
      return "String";
  }
}

/** UI VarType → API varType（后端存小写） */
export function toApiVarType(type: VarType): string {
  switch (type) {
    case "ObjectSet":
      return "objectset";
    case "Object":
      return "object";
    case "Number":
      return "number";
    case "Boolean":
      return "boolean";
    case "DateRange":
      return "daterange";
    case "Array":
      return "array";
    case "String":
    default:
      return "string";
  }
}

/** API group → UI scope；非标准值默认 page */
export function normalizeScope(raw: string | undefined | null): VarScope {
  const key = String(raw || "page").trim().toLowerCase();
  if (key === "app" || key === "application" || key === "应用级" || key === "应用") return "app";
  if (key === "global" || key === "全局") return "global";
  if (key === "page" || key === "页面级" || key === "页面") return "page";
  return "page";
}

/** 初始值展示 / 提交序列化 */
export function formatInitialValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

export function parseInitialValueInput(raw: string, type: VarType): unknown {
  const text = raw.trim();
  if (text === "") return type === "String" ? "" : null;
  if (type === "Number") {
    const n = Number(text);
    return Number.isFinite(n) ? n : text;
  }
  if (type === "Boolean") {
    if (text === "true" || text === "false") return text === "true";
    return text;
  }
  if (type === "Array" || type === "Object" || type === "ObjectSet" || type === "DateRange") {
    try {
      return JSON.parse(text);
    } catch {
      return text;
    }
  }
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export function mapApiVariable(item: ApiVariable): VariableItem {
  const type = normalizeVarType(item.varType);
  const scope = normalizeScope(item.group);
  const desc = item.description || "";
  const id = String(item.id || "").trim();
  return {
    id,
    name: item.name || "未命名变量",
    type,
    scope,
    initialValue: formatInitialValue(item.initialValue ?? item.currentValue),
    bindings: Array.isArray(item.bindings) ? item.bindings.filter((binding) => typeof binding === "string" && binding.trim()).map((binding) => binding.trim()) : [],
    description: desc,
    isSystem: false,
    readOnlyReason: id ? undefined : "标识缺失（只读）",
  };
}

export function filterVariablesByScope(items: VariableItem[], scope: string): VariableItem[] {
  if (scope === "all") return items;
  return items.filter((v) => v.scope === scope);
}

export function countVariablesByScope(items: VariableItem[]) {
  return {
    total: items.length,
    page: items.filter((v) => v.scope === "page").length,
    app: items.filter((v) => v.scope === "app").length,
    global: items.filter((v) => v.scope === "global").length,
  };
}

const TYPE_LABELS: Record<VarType, string> = {
  ObjectSet: "▢ 对象集",
  Object: "● 单个对象",
  String: "Aa 文本",
  Number: "# 数值",
  Boolean: "✓ 是 / 否",
  DateRange: "📅 日期范围",
  Array: "[] 列表",
};

const SCOPE_LABELS: Record<VarScope, string> = {
  page: "页面级",
  app: "应用级",
  global: "全局",
};

const SCOPE_TABS = [
  { id: "all", label: "全部" },
  { id: "page", label: "页面级" },
  { id: "app", label: "应用级" },
  { id: "global", label: "全局" },
];

const VAR_TYPE_OPTIONS: VarType[] = ["String", "Number", "Boolean", "Object", "ObjectSet", "Array", "DateRange"];

function VarTypeIcon({ type }: { type: VarType }) {
  const colors: Record<VarType, string> = {
    ObjectSet: "#60A5FA",
    Object: "#818CF8",
    String: "#34D399",
    Number: "#FBBF24",
    Boolean: "#F472B6",
    DateRange: "#A78BFA",
    Array: "#F87171",
  };
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke={colors[type]} strokeWidth={1.5} style={{ width: 16, height: 16 }}>
      {type === "ObjectSet" && (
        <>
          <rect x="3" y="3" width="7" height="7" rx="1" />
          <rect x="14" y="3" width="7" height="7" rx="1" />
          <rect x="3" y="14" width="7" height="7" rx="1" />
          <rect x="14" y="14" width="7" height="7" rx="1" />
        </>
      )}
      {type === "Object" && (
        <>
          <circle cx="12" cy="12" r="3" />
          <circle cx="12" cy="12" r="9" />
        </>
      )}
      {type === "String" && (
        <path d="M4 7V5a1 1 0 011-1h14a1 1 0 011 1v2M4 7h16M4 7l2 13h12l2-13M9 11v5M15 11v5" strokeLinecap="round" />
      )}
      {type === "Number" && (
        <path d="M12 2v20M2 12h20" strokeLinecap="round" />
      )}
      {type === "Boolean" && (
        <path d="M9 12l2 2 4-4M12 2a10 10 0 100 20 10 10 0 000-20z" strokeLinecap="round" strokeLinejoin="round" />
      )}
      {type === "DateRange" && (
        <>
          <rect x="3" y="4" width="18" height="16" rx="1" />
          <path d="M3 9h18M8 4V2M16 4V2" strokeLinecap="round" />
        </>
      )}
      {type === "Array" && (
        <path d="M4 6h16v12H4zM8 10h2v4H8zM14 10h2v4h-2z" strokeLinecap="round" />
      )}
    </svg>
  );
}

function emptyEditor(mode: "create" | "edit" = "create"): EditorState {
  return {
    mode,
    name: "",
    type: "String",
    scope: "page",
    initialValue: "",
    description: "",
  };
}

export function VariablesPage() {
  const [scope, setScope] = useState<string>("all");
  const [modules, setModules] = useState<ModuleOption[]>([]);
  const [moduleId, setModuleId] = useState<string>("");
  const [variables, setVariables] = useState<VariableItem[]>([]);
  const [dataMode, setDataMode] = useState<"api" | "unavailable">("unavailable");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [editor, setEditor] = useState<EditorState | null>(null);

  const loadVariables = useCallback(async (mid: string) => {
    if (!mid) {
      setVariables([]);
      setDataMode("unavailable");
      return;
    }
    setLoading(true);
    setError(null);
    setFeedback(null);
    try {
      const res = await apiGet<{ items?: ApiVariable[] }>(
        `/v1/modules/${encodeURIComponent(mid)}/variables`,
      );
      const items = (res.items || []).map(mapApiVariable);
      setVariables(items);
      setDataMode("api");
    } catch (e) {
      setVariables([]);
      setDataMode("unavailable");
      setError(String((e as Error).message || e));
    } finally {
      setLoading(false);
    }
  }, []);

  /* 加载 modules 列表，再按选中 module 拉变量 */
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const res = await apiGet<{ items?: Array<{ id?: string; name?: string }> }>("/v1/modules");
        if (cancelled) return;
        const opts = (res.items || [])
          .filter((m) => m.id)
          .map((m) => ({ id: String(m.id), name: m.name || String(m.id) }));
        setModules(opts);
        const preferred =
          opts.find((m) => m.id.includes("order"))?.id ||
          opts[0]?.id ||
          "";
        setModuleId(preferred);
        if (preferred) {
          await loadVariables(preferred);
        } else {
          setVariables([]);
          setDataMode("unavailable");
          setLoading(false);
        }
      } catch (e) {
        if (cancelled) return;
        setModules([]);
        setModuleId("");
        setVariables([]);
        setDataMode("unavailable");
        setError(String((e as Error).message || e));
        setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loadVariables]);

  const filtered = useMemo(() => filterVariablesByScope(variables, scope), [variables, scope]);
  const stats = useMemo(() => countVariablesByScope(variables), [variables]);

  function openCreate() {
    setEditor(emptyEditor("create"));
  }

  function openEdit(v: VariableItem) {
    setEditor({
      mode: "edit",
      id: v.id,
      name: v.name,
      type: v.type,
      scope: v.scope,
      initialValue: v.initialValue,
      description: v.description || "",
    });
  }

  async function submitEditor() {
    if (!editor || !editor.name.trim()) return;
    const payload = {
      name: editor.name.trim(),
      varType: toApiVarType(editor.type),
      group: editor.scope,
      initialValue: parseInitialValueInput(editor.initialValue, editor.type),
      description: editor.description.trim(),
    };

    if (dataMode !== "api" || !moduleId) {
      setError("请先选择可读取的真实模块，再维护变量");
      return;
    }

    setBusy(true);
    setError(null);
    setFeedback(null);
    try {
      if (editor.mode === "create") {
        await apiPost(`/v1/modules/${encodeURIComponent(moduleId)}/variables`, payload);
      } else if (editor.id) {
        await apiPut(
          `/v1/modules/${encodeURIComponent(moduleId)}/variables/${encodeURIComponent(editor.id)}`,
          payload,
        );
      }
      setEditor(null);
      await loadVariables(moduleId);
    } catch (e) {
      setError(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  async function removeVariable(v: VariableItem) {
    if (v.isSystem) return;
    if (!window.confirm(`确认删除变量「${v.name}」？`)) return;

    if (dataMode !== "api" || !moduleId) {
      setError("当前没有可写的真实模块变量权威");
      return;
    }

    setBusy(true);
    setError(null);
    setFeedback(null);
    try {
      await apiDelete(
        `/v1/modules/${encodeURIComponent(moduleId)}/variables/${encodeURIComponent(v.id)}`,
      );
      await loadVariables(moduleId);
    } catch (e) {
      setError(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  async function onModuleChange(nextId: string) {
    setModuleId(nextId);
    setScope("all");
    await loadVariables(nextId);
  }

  return (
    <PageChrome title="变量管理器" lede="集中管理页面级、应用级和当前工作区范围内的共享变量。">
      <div className="vr-page">
        {dataMode === "unavailable" && (
          <div className="vr-demo-banner" role={error ? "alert" : "status"}>
            {error ? `变量权威读取失败：${error}` : "请先创建或选择真实模块，再维护变量。"}
          </div>
        )}
        {dataMode === "api" && (
          <details className="vr-api-banner">
            <summary>变量已从当前模块读取</summary>
            <code>GET/POST/PUT/DELETE /v1/modules/:id/variables</code>
          </details>
        )}
        {error && dataMode === "api" && (
          <div className="vr-error-banner" role="alert">
            {error}
          </div>
        )}
        {feedback && (
          <div className="vr-demo-banner" role="status">
            {feedback}
          </div>
        )}

        <div className="vr-toolbar">
          <div className="vr-header-actions">
            <label className="vr-module-pick">
              <span className="vr-module-label">模块</span>
              <select
                className="vr-module-select"
                value={moduleId}
                onChange={(e) => void onModuleChange(e.target.value)}
                disabled={modules.length === 0}
                aria-label="选择模块"
              >
                {modules.length === 0 ? (
                  <option value="">无可用模块</option>
                ) : (
                  modules.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))
                )}
              </select>
            </label>
            <Link to="/workshop/canvas" className="vr-btn vr-btn-secondary">
              返回编辑器
            </Link>
            <button type="button" className="vr-btn vr-btn-primary" onClick={openCreate} disabled={busy || dataMode !== "api" || !moduleId} title={dataMode !== "api" || !moduleId ? "请先选择真实模块" : undefined}>
              + 新建变量
            </button>
          </div>
          <div className="vr-scope-seg" role="tablist" aria-label="变量作用域">
            {SCOPE_TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={scope === tab.id}
                className={scope === tab.id ? "vr-scope-tab is-active" : "vr-scope-tab"}
                onClick={() => setScope(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        <div className="vr-stats">
          <div className="vr-stat-card">
            <div className="vr-stat-label">总变量数</div>
            <div className="vr-stat-value">{loading ? "…" : stats.total}</div>
          </div>
          <div className="vr-stat-card">
            <div className="vr-stat-label">页面级</div>
            <div className="vr-stat-value is-page">{stats.page}</div>
          </div>
          <div className="vr-stat-card">
            <div className="vr-stat-label">应用级</div>
            <div className="vr-stat-value is-app">{stats.app}</div>
          </div>
          <div className="vr-stat-card">
            <div className="vr-stat-label">全局</div>
            <div className="vr-stat-value is-global">{stats.global}</div>
          </div>
        </div>

        <div className="vr-table-wrap">
          <table className="vr-table">
            <thead>
              <tr>
                <th className="vr-th-icon" aria-hidden="true" />
                <th>名称</th>
                <th>类型</th>
                <th>作用域</th>
                <th>初始值 / 数据源</th>
                <th>绑定组件</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {!loading && filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="vr-empty">
                    {dataMode === "api" && moduleId ? "当前模块暂无变量，可新建变量" : "当前没有可读取的真实模块变量"}
                  </td>
                </tr>
              )}
              {filtered.map((v, index) => (
                <tr
                  key={v.id || `missing-${index}`}
                  style={{
                    borderLeft: `3px solid ${
                      v.scope === "page"
                        ? "var(--aos-blue)"
                        : v.scope === "app"
                          ? "var(--aos-green)"
                          : "var(--aos-amber)"
                    }`,
                  }}
                >
                  <td className="vr-td-icon">
                    <VarTypeIcon type={v.type} />
                  </td>
                  <td className="vr-name">{v.name}</td>
                  <td>
                    <span className={`vr-type-badge vr-type-${v.type}`}>{TYPE_LABELS[v.type]}</span>
                  </td>
                  <td>
                    <span className={`vr-scope-text is-${v.scope}`}>{SCOPE_LABELS[v.scope]}</span>
                  </td>
                  <td className="vr-value">{v.initialValue}</td>
                  <td>
                    <div className="vr-bindings">
                      {v.bindings.length === 0 ? (
                        <span className="vr-binding is-muted">—</span>
                      ) : (
                        v.bindings.map((b, i) => (
                          <span key={i} className="vr-binding">
                            {b}
                          </span>
                        ))
                      )}
                    </div>
                  </td>
                  <td>
                    {v.isSystem || v.readOnlyReason ? (
                      <span className="vr-system">{v.readOnlyReason || "系统变量"}</span>
                    ) : (
                      <div className="vr-row-actions">
                        <button type="button" className="vr-edit" onClick={() => openEdit(v)} disabled={busy}>
                          编辑
                        </button>
                        <button type="button" className="vr-delete" onClick={() => void removeVariable(v)} disabled={busy}>
                          删除
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="vr-flow">
          <h3>数据流图</h3>
          <div className="vr-flow-body">
            {variables.length ? variables.slice(0, 6).map((variable) => (
              <div className="vr-flow-row" key={variable.id}>
                <span className="vr-flow-chip is-blue">{variable.name}</span>
                <span className="vr-flow-arrow">→ {variable.bindings.length ? "已绑定" : "尚未绑定"} →</span>
                <span className="vr-flow-chip is-outline">{variable.bindings.join("、") || "无绑定目标"}</span>
              </div>
            )) : <p className="muted">当前没有可绘制的真实变量绑定。</p>}
            <div className="vr-flow-hint">
              💡 页面级变量仅当前页面可见；应用级变量可在当前应用内跨页面共享；全局变量受当前租户与工作区边界约束。绑定关系与画布使用同一份变量记录。
            </div>
          </div>
        </div>

        {editor && (
          <div className="vr-modal-backdrop" role="presentation" onClick={() => !busy && setEditor(null)}>
            <div
              className="vr-modal"
              role="dialog"
              aria-modal="true"
              aria-label={editor.mode === "create" ? "新建变量" : "编辑变量"}
              onClick={(e) => e.stopPropagation()}
            >
              <h3 className="vr-modal-title">{editor.mode === "create" ? "新建变量" : "编辑变量"}</h3>
              <label className="vr-field">
                <span>名称</span>
                <input
                  value={editor.name}
                  onChange={(e) => setEditor({ ...editor, name: e.target.value })}
                  placeholder="如：选中状态"
                  autoFocus
                />
              </label>
              <label className="vr-field">
                <span>类型</span>
                <select
                  value={editor.type}
                  onChange={(e) => setEditor({ ...editor, type: e.target.value as VarType })}
                >
                  {VAR_TYPE_OPTIONS.map((t) => (
                    <option key={t} value={t}>
                      {TYPE_LABELS[t]}
                    </option>
                  ))}
                </select>
              </label>
              <label className="vr-field">
                <span>作用域</span>
                <select
                  value={editor.scope}
                  onChange={(e) => setEditor({ ...editor, scope: e.target.value as VarScope })}
                >
                  <option value="page">页面级</option>
                  <option value="app">应用级</option>
                  <option value="global">全局</option>
                </select>
              </label>
              <label className="vr-field">
                <span>初始值</span>
                <input
                  value={editor.initialValue}
                  onChange={(e) => setEditor({ ...editor, initialValue: e.target.value })}
                  placeholder="请输入与变量类型匹配的初始值"
                />
              </label>
              <label className="vr-field">
                <span>描述</span>
                <input
                  value={editor.description}
                  onChange={(e) => setEditor({ ...editor, description: e.target.value })}
                  placeholder="可选说明"
                />
              </label>
              <div className="vr-modal-actions">
                <button type="button" className="vr-btn vr-btn-secondary" onClick={() => setEditor(null)} disabled={busy}>
                  取消
                </button>
                <button
                  type="button"
                  className="vr-btn vr-btn-primary"
                  onClick={() => void submitEditor()}
                  disabled={busy || !editor.name.trim()}
                >
                  {busy ? "保存中…" : "保存"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </PageChrome>
  );
}
