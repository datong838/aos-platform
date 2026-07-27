/**
 * Phase 6 · Property Editor Page
 * 属性列表表格 + CRUD + 类型选择器 + 高级设置折叠区
 * 参考蓝图: ontology-property.html
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiGet, apiPost, apiPut, apiDelete } from "../../api/client";
import { S2Chrome } from "./shared";
import { BpToolbar, BpTabs } from "./blueprintUi";

// ==================== 类型定义 ====================

export type PropertyType =
  | "STRING"
  | "INTEGER"
  | "DECIMAL"
  | "BOOLEAN"
  | "DATE"
  | "TIMESTAMP"
  | "JSON"
  | "GEOMETRY";

export type PropertyStatus = "active" | "experimental" | "deprecated";

export type PropertyVisibility = "normal" | "hidden" | "visible";

export interface PropertyField {
  id: string;
  name: string;
  type: PropertyType;
  description: string;
  status: PropertyStatus;
  visibility: PropertyVisibility;
  isPrimaryKey: boolean;
  isTitleKey: boolean;
  isRequired: boolean;
  allowMultiple: boolean;
  baseFormatter: string;
  columnMapping: string;
  defaultValue: string;
  minValue: string;
  maxValue: string;
}

// ==================== 常量 ====================

export const PROPERTY_TYPES: { value: PropertyType; label: string; icon: string }[] = [
  { value: "STRING", label: "String", icon: "𝐒" },
  { value: "INTEGER", label: "Integer", icon: "123" },
  { value: "DECIMAL", label: "Decimal", icon: "1.0" },
  { value: "BOOLEAN", label: "Boolean", icon: "✓" },
  { value: "DATE", label: "Date", icon: "📅" },
  { value: "TIMESTAMP", label: "Timestamp", icon: "⏱" },
  { value: "JSON", label: "JSON", icon: "{}" },
  { value: "GEOMETRY", label: "Geometry", icon: "◉" },
];

export const PROPERTY_STATUSES: { value: PropertyStatus; label: string; color: string }[] = [
  { value: "active", label: "Active", color: "var(--aos-ok, #38a169)" },
  { value: "experimental", label: "Experimental", color: "var(--aos-warn, #d69e2e)" },
  { value: "deprecated", label: "Deprecated", color: "var(--aos-bad, #e53e3e)" },
];

// ==================== 纯函数 ====================

export function emptyProperty(prefix = ""): PropertyField {
  return {
    id: `${prefix}new-${Date.now()}`,
    name: "",
    type: "STRING",
    description: "",
    status: "experimental",
    visibility: "normal",
    isPrimaryKey: false,
    isTitleKey: false,
    isRequired: false,
    allowMultiple: false,
    baseFormatter: "No formatting",
    columnMapping: "",
    defaultValue: "",
    minValue: "",
    maxValue: "",
  };
}

export function validateProperty(p: PropertyField): string[] {
  const errors: string[] = [];
  if (!p.name || !p.name.trim()) errors.push("name 不能为空");
  if (p.name && !/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(p.name))
    errors.push("name 必须以字母或下划线开头，只允许字母、数字、下划线");
  if (p.type === "DECIMAL") {
    if (p.minValue && isNaN(Number(p.minValue))) errors.push("minValue 必须是数字");
    if (p.maxValue && isNaN(Number(p.maxValue))) errors.push("maxValue 必须是数字");
    if (
      p.minValue &&
      p.maxValue &&
      !isNaN(Number(p.minValue)) &&
      !isNaN(Number(p.maxValue)) &&
      Number(p.minValue) > Number(p.maxValue)
    )
      errors.push("minValue 不能大于 maxValue");
  }
  if (p.isPrimaryKey && p.type === "BOOLEAN")
    errors.push("BOOLEAN 类型不能作为主键");
  if (p.isPrimaryKey && p.isTitleKey)
    errors.push("同一属性不能同时为 primaryKey 和 titleKey");
  if (p.defaultValue && p.type === "INTEGER" && !/^-?\d+$/.test(p.defaultValue))
    errors.push("INTEGER 类型的 defaultValue 必须是整数");
  if (p.defaultValue && p.type === "BOOLEAN" && !/^(true|false)$/.test(p.defaultValue))
    errors.push("BOOLEAN 类型的 defaultValue 必须是 true/false");
  return errors;
}

export function isValidPropertyName(name: string): boolean {
  if (!name || !name.trim()) return false;
  return /^[a-zA-Z_][a-zA-Z0-9_]*$/.test(name);
}

export function typeIcon(type: PropertyType): string {
  return PROPERTY_TYPES.find((t) => t.value === type)?.icon || "?";
}

export function typeLabel(type: PropertyType): string {
  return PROPERTY_TYPES.find((t) => t.value === type)?.label || type;
}

export function statusLabel(status: PropertyStatus): string {
  return PROPERTY_STATUSES.find((s) => s.value === status)?.label || status;
}

export function statusColor(status: PropertyStatus): string {
  return PROPERTY_STATUSES.find((s) => s.value === status)?.color || "var(--aos-muted, #718096)";
}

/** 自动映射列名：属性名 -> 小写下划线 */
export function autoMapColumnName(name: string): string {
  return name
    .replace(/([A-Z])/g, "_$1")
    .toLowerCase()
    .replace(/^_/, "");
}

/** 统计属性概要 */
export function summarizeProperties(props: PropertyField[]): {
  total: number;
  pkCount: number;
  titleKeyCount: number;
  byType: Record<string, number>;
  byStatus: Record<string, number>;
} {
  const byType: Record<string, number> = {};
  const byStatus: Record<string, number> = {};
  let pkCount = 0;
  let titleKeyCount = 0;
  for (const p of props) {
    byType[p.type] = (byType[p.type] || 0) + 1;
    byStatus[p.status] = (byStatus[p.status] || 0) + 1;
    if (p.isPrimaryKey) pkCount++;
    if (p.isTitleKey) titleKeyCount++;
  }
  return { total: props.length, pkCount, titleKeyCount, byType, byStatus };
}

/** 过滤属性列表 */
export function filterProperties(
  props: PropertyField[],
  query: string,
  showMappedOnly: boolean,
): PropertyField[] {
  let result = props;
  if (showMappedOnly) {
    result = result.filter((p) => p.columnMapping.trim() !== "");
  }
  if (query.trim()) {
    const q = query.toLowerCase();
    result = result.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.type.toLowerCase().includes(q) ||
        p.columnMapping.toLowerCase().includes(q),
    );
  }
  return result;
}

// ==================== 组件 ====================

export function PropertyEditorPage() {
  const { typeId = "" } = useParams();
  const [properties, setProperties] = useState<PropertyField[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [showMappedOnly, setShowMappedOnly] = useState(false);
  const [activeTab, setActiveTab] = useState<"properties" | "mapping">("properties");
  const [detailTab, setDetailTab] = useState<string>("general");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState("");

  // 加载属性列表
  useEffect(() => {
    if (!typeId) return;
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        const res = await apiGet<{ items: PropertyField[] }>(
          `/v1/ontology/object-types/${encodeURIComponent(typeId)}/properties`,
        ).catch(() => ({ items: [] as PropertyField[] }));
        if (cancelled) return;
        setProperties(res.items || []);
        if (res.items && res.items.length > 0 && !selectedId) {
          setSelectedId(res.items[0].id);
        }
      } catch (e) {
        if (!cancelled) setErr(String((e as Error).message || e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [typeId]);

  const filtered = useMemo(
    () => filterProperties(properties, searchQuery, showMappedOnly),
    [properties, searchQuery, showMappedOnly],
  );

  const summary = useMemo(() => summarizeProperties(properties), [properties]);

  const selected = properties.find((p) => p.id === selectedId) || null;

  function patchProperty(id: string, patch: Partial<PropertyField>) {
    setProperties((prev) =>
      prev.map((p) => (p.id === id ? { ...p, ...patch } : p)),
    );
  }

  function addProperty() {
    const np = emptyProperty();
    setProperties((prev) => [...prev, np]);
    setSelectedId(np.id);
    setMsg(`已新增属性（待保存）`);
  }

  async function saveProperty(p: PropertyField) {
    setErr(null);
    setMsg("");
    const errors = validateProperty(p);
    if (errors.length > 0) {
      setErr(errors.join("；"));
      return;
    }
    try {
      const body = { ...p, objectTypeId: typeId };
      if (p.columnMapping) {
        await apiPut(
          `/v1/ontology/object-types/${encodeURIComponent(typeId)}/properties/${encodeURIComponent(p.id)}`,
          body,
        );
        setMsg(`属性 ${p.name} 已保存`);
      } else {
        const res = await apiPost<{ id: string }>(
          `/v1/ontology/object-types/${encodeURIComponent(typeId)}/properties`,
          body,
        );
        if (res.id) {
          patchProperty(p.id, { id: res.id });
          setSelectedId(res.id);
        }
        setMsg(`属性 ${p.name} 已创建`);
      }
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  async function deleteProperty(p: PropertyField) {
    if (!window.confirm(`删除属性 ${p.name}？`)) return;
    setErr(null);
    setMsg("");
    try {
      if (p.columnMapping) {
        await apiDelete(
          `/v1/ontology/object-types/${encodeURIComponent(typeId)}/properties/${encodeURIComponent(p.id)}`,
        );
      }
      setProperties((prev) => prev.filter((x) => x.id !== p.id));
      if (selectedId === p.id) setSelectedId(null);
      setMsg(`属性 ${p.name} 已删除`);
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  function autoMapAll() {
    setProperties((prev) =>
      prev.map((p) =>
        p.columnMapping
          ? p
          : { ...p, columnMapping: autoMapColumnName(p.name) },
      ),
    );
    setMsg("已自动映射所有未映射列");
  }

  return (
    <S2Chrome
      title={typeId ? `${typeId} · 属性编辑器` : "属性编辑器"}
      lede="属性列表表格 · CRUD · 类型选择器 · 高级设置折叠区"
    >
      <div className="ont-page">
        <BpToolbar>
          <Link to={`/ontology/object-types/${encodeURIComponent(typeId)}`} className="btn-nav">
            ← Object Type
          </Link>
          <button
            type="button"
            className="btn-primary"
            onClick={() => void addProperty()}
          >
            + 新建属性
          </button>
          <button
            type="button"
            className="btn-nav"
            onClick={() => void autoMapAll()}
          >
            自动映射全部
          </button>
        </BpToolbar>

        {msg && <p className="bp-prop-ok">{msg}</p>}
        {err && <p className="error">{err}</p>}

        <BpTabs
          tabs={[
            { id: "properties", label: `属性 (${summary.total})` },
            { id: "mapping", label: "列映射" },
          ]}
          active={activeTab}
          onChange={(id) => setActiveTab(id as "properties" | "mapping")}
        />

        {/* 数据源控制条 */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "8px 12px",
            background: "var(--aos-surface, #0f1419)",
            border: "1px solid var(--aos-border, #2a3540)",
            borderRadius: 4,
            marginBottom: 8,
          }}
        >
          <span className="muted" style={{ fontSize: "0.75rem" }}>
            类型: <code>{typeId}</code> · 总属性 {summary.total} · 主键 {summary.pkCount} · 标题键 {summary.titleKeyCount}
          </span>
          <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: "0.75rem" }}>
            <input
              type="checkbox"
              checked={showMappedOnly}
              onChange={(e) => setShowMappedOnly(e.target.checked)}
            />
            仅显示已映射列
          </label>
          <input
            type="search"
            placeholder="搜索属性…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="aos-input"
            style={{ flex: 1, maxWidth: 240 }}
          />
        </div>

        {loading && <p className="muted">加载中…</p>}

        {/* 主区域: 左属性表 + 右详情 */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 320px",
            gap: 8,
          }}
        >
          {/* 左: 属性表 */}
          <div className="bp-table-wrap">
            <table className="data-table bp-table">
              <thead>
                <tr>
                  <th style={{ width: 32 }}>
                    <input type="checkbox" />
                  </th>
                  <th>属性名</th>
                  <th style={{ width: 100 }}>类型</th>
                  <th style={{ width: 90 }}>状态</th>
                  <th style={{ width: 90 }}>可见性</th>
                  <th>列映射</th>
                  <th style={{ width: 60 }}></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((p) => (
                  <tr
                    key={p.id}
                    className={selectedId === p.id ? "is-selected" : ""}
                    onClick={() => setSelectedId(p.id)}
                    style={{ cursor: "pointer" }}
                  >
                    <td>
                      <input type="checkbox" />
                    </td>
                    <td>
                      <span style={{ fontWeight: p.isPrimaryKey ? 700 : 400 }}>
                        {typeIcon(p.type)} {p.name || "(unnamed)"}
                      </span>
                      {p.isPrimaryKey && (
                        <span
                          className="bp-tag bp-tag-warn"
                          style={{ marginLeft: 4, fontSize: "0.65rem" }}
                        >
                          PK
                        </span>
                      )}
                      {p.isTitleKey && (
                        <span
                          className="bp-tag bp-tag-info"
                          style={{ marginLeft: 4, fontSize: "0.65rem" }}
                        >
                          Title
                        </span>
                      )}
                    </td>
                    <td>
                      <span className="muted" style={{ fontSize: "0.75rem" }}>
                        {typeLabel(p.type)}
                      </span>
                    </td>
                    <td>
                      <span
                        style={{
                          fontSize: "0.7rem",
                          padding: "2px 6px",
                          borderRadius: 3,
                          background: statusColor(p.status),
                          color: "#fff",
                        }}
                      >
                        {statusLabel(p.status)}
                      </span>
                    </td>
                    <td>
                      <span className="muted" style={{ fontSize: "0.7rem" }}>
                        {p.visibility}
                      </span>
                    </td>
                    <td>
                      {p.columnMapping ? (
                        <code style={{ fontSize: "0.7rem" }}>{p.columnMapping}</code>
                      ) : (
                        <span className="muted" style={{ fontSize: "0.7rem" }}>—</span>
                      )}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="btn-nav"
                        style={{ fontSize: "0.65rem", padding: "2px 6px" }}
                        onClick={(e) => {
                          e.stopPropagation();
                          void deleteProperty(p);
                        }}
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && !loading && (
                  <tr>
                    <td colSpan={7} className="muted" style={{ textAlign: "center", padding: 24 }}>
                      暂无属性，点击「新建属性」添加
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* 右: 属性详情面板 */}
          <aside
            style={{
              border: "1px solid var(--aos-border, #2a3540)",
              borderRadius: 4,
              background: "var(--aos-surface, #0f1419)",
              padding: 12,
              maxHeight: 500,
              overflowY: "auto",
            }}
          >
            {!selected && (
              <p className="muted" style={{ fontSize: "0.75rem" }}>
                从左侧选择一个属性查看详情
              </p>
            )}
            {selected && (
              <PropertyDetailPanel
                key={selected.id}
                property={selected}
                detailTab={detailTab}
                setDetailTab={setDetailTab}
                showAdvanced={showAdvanced}
                setShowAdvanced={setShowAdvanced}
                onPatch={(patch) => patchProperty(selected.id, patch)}
                onSave={() => void saveProperty(selected)}
              />
            )}
          </aside>
        </div>
      </div>
    </S2Chrome>
  );
}

function PropertyDetailPanel({
  property,
  detailTab,
  setDetailTab,
  showAdvanced,
  setShowAdvanced,
  onPatch,
  onSave,
}: {
  property: PropertyField;
  detailTab: string;
  setDetailTab: (t: string) => void;
  showAdvanced: boolean;
  setShowAdvanced: (v: boolean) => void;
  onPatch: (patch: Partial<PropertyField>) => void;
  onSave: () => void;
}) {
  return (
    <div>
      {/* 标题行 */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
        <span style={{ fontFamily: "monospace", color: "var(--aos-accent, #5b8def)" }}>
          {typeIcon(property.type)}
        </span>
        <strong style={{ flex: 1 }}>{property.name || "(unnamed)"}</strong>
        {property.isPrimaryKey && (
          <span className="bp-tag bp-tag-warn">Primary key</span>
        )}
      </div>

      {/* Tab 切换 */}
      <BpTabs
        tabs={[
          { id: "general", label: "常规" },
          { id: "display", label: "显示" },
          { id: "advanced", label: "高级" },
        ]}
        active={detailTab}
        onChange={setDetailTab}
      />

      <div style={{ marginTop: 12 }}>
        {detailTab === "general" && (
          <>
            <label className="ont-form-field">
              <span>Name</span>
              <input
                className="aos-input"
                value={property.name}
                onChange={(e) => onPatch({ name: e.target.value })}
              />
            </label>
            <label className="ont-form-field">
              <span>Description</span>
              <textarea
                className="aos-input"
                rows={2}
                value={property.description}
                onChange={(e) => onPatch({ description: e.target.value })}
              />
            </label>
            <label className="ont-form-field">
              <span>Base type</span>
              <select
                className="aos-input"
                value={property.type}
                onChange={(e) => onPatch({ type: e.target.value as PropertyType })}
              >
                {PROPERTY_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.icon} {t.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="ont-form-field">
              <span>Status</span>
              <select
                className="aos-input"
                value={property.status}
                onChange={(e) => onPatch({ status: e.target.value as PropertyStatus })}
              >
                {PROPERTY_STATUSES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </label>
          </>
        )}

        {detailTab === "display" && (
          <>
            <label className="ont-form-field">
              <span>Visibility</span>
              <select
                className="aos-input"
                value={property.visibility}
                onChange={(e) =>
                  onPatch({ visibility: e.target.value as PropertyVisibility })
                }
              >
                <option value="normal">Normal</option>
                <option value="hidden">Hidden</option>
                <option value="visible">Visible</option>
              </select>
            </label>
            <label className="ont-form-field">
              <span>Base formatter</span>
              <input
                className="aos-input"
                value={property.baseFormatter}
                onChange={(e) => onPatch({ baseFormatter: e.target.value })}
              />
            </label>
            <label className="ont-form-field">
              <span>Column mapping</span>
              <input
                className="aos-input"
                value={property.columnMapping}
                onChange={(e) => onPatch({ columnMapping: e.target.value })}
                placeholder="未映射"
              />
            </label>
          </>
        )}

        {detailTab === "advanced" && (
          <>
            <div style={{ display: "flex", gap: 12, flexDirection: "column" }}>
              <label className="ont-form-check">
                <input
                  type="checkbox"
                  checked={property.isPrimaryKey}
                  onChange={(e) => onPatch({ isPrimaryKey: e.target.checked })}
                />
                Primary key
              </label>
              <label className="ont-form-check">
                <input
                  type="checkbox"
                  checked={property.isTitleKey}
                  onChange={(e) => onPatch({ isTitleKey: e.target.checked })}
                />
                Title key
              </label>
              <label className="ont-form-check">
                <input
                  type="checkbox"
                  checked={property.isRequired}
                  onChange={(e) => onPatch({ isRequired: e.target.checked })}
                />
                Required
              </label>
              <label className="ont-form-check">
                <input
                  type="checkbox"
                  checked={property.allowMultiple}
                  onChange={(e) => onPatch({ allowMultiple: e.target.checked })}
                />
                Allow multiple values
              </label>
            </div>

            <button
              type="button"
              className="btn-nav"
              style={{ marginTop: 8, fontSize: "0.7rem" }}
              onClick={() => setShowAdvanced(!showAdvanced)}
            >
              {showAdvanced ? "▼" : "▶"} 约束设置
            </button>

            {showAdvanced && (
              <div style={{ marginTop: 8, paddingLeft: 12, borderLeft: "2px solid var(--aos-border, #2a3540)" }}>
                <label className="ont-form-field">
                  <span>Default value</span>
                  <input
                    className="aos-input"
                    value={property.defaultValue}
                    onChange={(e) => onPatch({ defaultValue: e.target.value })}
                  />
                </label>
                {property.type === "DECIMAL" && (
                  <>
                    <label className="ont-form-field">
                      <span>Min value</span>
                      <input
                        className="aos-input"
                        type="number"
                        value={property.minValue}
                        onChange={(e) => onPatch({ minValue: e.target.value })}
                      />
                    </label>
                    <label className="ont-form-field">
                      <span>Max value</span>
                      <input
                        className="aos-input"
                        type="number"
                        value={property.maxValue}
                        onChange={(e) => onPatch({ maxValue: e.target.value })}
                      />
                    </label>
                  </>
                )}
              </div>
            )}
          </>
        )}
      </div>

      <button
        type="button"
        className="btn-primary"
        style={{ marginTop: 12, width: "100%" }}
        onClick={onSave}
      >
        保存属性
      </button>
    </div>
  );
}
