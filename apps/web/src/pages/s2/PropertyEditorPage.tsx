/**
 * Phase 6 · Property Editor Page
 * 属性列表表格 + CRUD + 类型选择器 + 高级设置折叠区
 * 参考蓝图: ontology-property.html
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiGet, apiPost, apiPut } from "../../api/client";
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

export type PropertySourceMode = "loading" | "live" | "demo";

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

/** API 列映射行 */
export interface ColumnMappingRow {
  id: string;
  object_type_id: string;
  source_column: string;
  target_property: string;
  confidence: number;
  auto: boolean;
  status: string;
}

/** API 属性原始行（宽松） */
export interface ApiPropertyRow {
  id?: string;
  name?: string;
  display_name?: string;
  datatype?: string;
  type?: string;
  nullable?: boolean;
  is_primary_key?: boolean;
  is_display_name?: boolean;
  description?: string;
  column_mapping?: string;
  columnMapping?: string;
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
  { value: "active", label: "Active", color: "var(--aos-green)" },
  { value: "experimental", label: "Experimental", color: "var(--aos-amber)" },
  { value: "deprecated", label: "Deprecated", color: "var(--aos-red)" },
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
  return PROPERTY_STATUSES.find((s) => s.value === status)?.color || "var(--aos-text-tertiary)";
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

const DATATYPE_TO_UI: Record<string, PropertyType> = {
  string: "STRING",
  STRING: "STRING",
  int: "INTEGER",
  integer: "INTEGER",
  INTEGER: "INTEGER",
  double: "DECIMAL",
  decimal: "DECIMAL",
  DECIMAL: "DECIMAL",
  float: "DECIMAL",
  boolean: "BOOLEAN",
  BOOLEAN: "BOOLEAN",
  date: "DATE",
  DATE: "DATE",
  datetime: "TIMESTAMP",
  timestamp: "TIMESTAMP",
  TIMESTAMP: "TIMESTAMP",
  json: "JSON",
  JSON: "JSON",
  geo: "GEOMETRY",
  geometry: "GEOMETRY",
  GEOMETRY: "GEOMETRY",
};

const UI_TO_DATATYPE: Record<PropertyType, string> = {
  STRING: "string",
  INTEGER: "int",
  DECIMAL: "double",
  BOOLEAN: "boolean",
  DATE: "date",
  TIMESTAMP: "datetime",
  JSON: "json",
  GEOMETRY: "geo",
};

/** API datatype → UI PropertyType */
export function mapDatatypeToUiType(datatype: string | undefined): PropertyType {
  if (!datatype) return "STRING";
  return DATATYPE_TO_UI[datatype] || DATATYPE_TO_UI[datatype.toLowerCase()] || "STRING";
}

/** UI → AddPropertyRequest 字段 */
export function mapFieldToAddRequest(p: PropertyField): Record<string, unknown> {
  return {
    name: p.name.trim(),
    display_name: p.name.trim(),
    datatype: UI_TO_DATATYPE[p.type] || "string",
    nullable: !p.isRequired,
    is_primary_key: p.isPrimaryKey,
    is_display_name: p.isTitleKey,
    description: p.description || "",
  };
}

/** API 属性行 → PropertyField；可选叠加 columnMapping */
export function mapApiPropertyToField(
  row: ApiPropertyRow,
  columnByProp?: Record<string, string>,
): PropertyField {
  const name = row.name || "";
  const mapping =
    row.columnMapping ||
    row.column_mapping ||
    (columnByProp && name ? columnByProp[name] : "") ||
    "";
  return {
    id: row.id || `prop-${name || Date.now()}`,
    name,
    type: mapDatatypeToUiType(row.datatype || row.type),
    description: row.description || "",
    status: "active",
    visibility: "normal",
    isPrimaryKey: Boolean(row.is_primary_key),
    isTitleKey: Boolean(row.is_display_name),
    isRequired: row.nullable === false,
    allowMultiple: false,
    baseFormatter: "No formatting",
    columnMapping: mapping,
    defaultValue: "",
    minValue: "",
    maxValue: "",
  };
}

/** 映射行列表 → 属性名→源列 */
export function mappingTargetToSource(
  rows: ColumnMappingRow[],
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const m of rows) {
    if (m.target_property && m.source_column && m.status !== "skipped") {
      out[m.target_property] = m.source_column;
    }
  }
  return out;
}

/** 把映射写回属性列表的 columnMapping */
export function applyMappingsToProperties(
  props: PropertyField[],
  rows: ColumnMappingRow[],
): PropertyField[] {
  const byTarget = mappingTargetToSource(rows);
  return props.map((p) => ({
    ...p,
    columnMapping: byTarget[p.name] || p.columnMapping || "",
  }));
}

/** 规范化 API 映射行 */
export function normalizeMappingRow(
  raw: Partial<ColumnMappingRow> & Record<string, unknown>,
  otId: string,
): ColumnMappingRow {
  return {
    id: String(raw.id || `cm-${raw.source_column || Date.now()}`),
    object_type_id: String(raw.object_type_id || otId),
    source_column: String(raw.source_column || ""),
    target_property: String(raw.target_property || ""),
    confidence: typeof raw.confidence === "number" ? raw.confidence : 0,
    auto: Boolean(raw.auto),
    status: String(raw.status || (raw.target_property ? "mapped" : "skipped")),
  };
}

/** 映射保存 body */
export function buildMappingSaveBody(rows: ColumnMappingRow[]): {
  mappings: Array<{
    source_column: string;
    target_property: string;
    confidence: number;
    auto: boolean;
    status: string;
  }>;
} {
  return {
    mappings: rows.map((r) => ({
      source_column: r.source_column,
      target_property: r.target_property,
      confidence: r.confidence,
      auto: r.auto,
      status: r.target_property ? "mapped" : "skipped",
    })),
  };
}

/** 本地未映射属性 → 推导初始映射行（demo 回退） */
export function deriveLocalMappingRows(
  props: PropertyField[],
  otId: string,
): ColumnMappingRow[] {
  return props
    .filter((p) => p.name.trim())
    .map((p, i) => ({
      id: `cm-local-${i}-${p.id}`,
      object_type_id: otId,
      source_column: p.columnMapping || autoMapColumnName(p.name),
      target_property: p.columnMapping ? p.name : "",
      confidence: p.columnMapping ? 1 : 0,
      auto: false,
      status: p.columnMapping ? "mapped" : "skipped",
    }));
}

export function isNewPropertyId(id: string): boolean {
  return id.startsWith("new-") || /(?:^|-)new-/.test(id);
}

export function countMappedColumns(rows: ColumnMappingRow[]): {
  mapped: number;
  total: number;
} {
  const total = rows.length;
  const mapped = rows.filter((r) => r.target_property && r.status !== "skipped").length;
  return { mapped, total };
}

// ==================== 组件 ====================

export function PropertyEditorPage() {
  const { typeId = "" } = useParams();
  const [properties, setProperties] = useState<PropertyField[]>([]);
  const [mappings, setMappings] = useState<ColumnMappingRow[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [showMappedOnly, setShowMappedOnly] = useState(false);
  const [activeTab, setActiveTab] = useState<"properties" | "mapping">("properties");
  const [detailTab, setDetailTab] = useState<string>("general");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [loading, setLoading] = useState(true);
  const [sourceMode, setSourceMode] = useState<PropertySourceMode>("loading");
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState("");
  const [mapBusy, setMapBusy] = useState(false);

  useEffect(() => {
    if (!typeId) return;
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        setSourceMode("loading");
        const propRes = await apiGet<{ items?: ApiPropertyRow[] }>(
          `/v1/ontology/object-types/${encodeURIComponent(typeId)}/properties`,
        );
        if (cancelled) return;

        let mapRows: ColumnMappingRow[] = [];
        try {
          const mapRes = await apiGet<{ items?: Array<Partial<ColumnMappingRow>> }>(
            `/v1/ontology/object-types/${encodeURIComponent(typeId)}/column-mapping`,
          );
          mapRows = (mapRes.items || []).map((r) => normalizeMappingRow(r, typeId));
        } catch {
          mapRows = [];
        }

        const byTarget = mappingTargetToSource(mapRows);
        const items = (propRes.items || []).map((r) => mapApiPropertyToField(r, byTarget));
        setProperties(items);
        setMappings(
          mapRows.length > 0 ? mapRows : deriveLocalMappingRows(items, typeId),
        );
        setSourceMode("live");
        if (items.length > 0) setSelectedId(items[0].id);
      } catch (e) {
        if (cancelled) return;
        // 演示路径：空属性 + 本地推导
        setProperties([]);
        setMappings([]);
        setSourceMode("demo");
        setErr(String((e as Error).message || e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [typeId]);

  const filtered = useMemo(
    () => filterProperties(properties, searchQuery, showMappedOnly),
    [properties, searchQuery, showMappedOnly],
  );

  const summary = useMemo(() => summarizeProperties(properties), [properties]);
  const mapStats = useMemo(() => countMappedColumns(mappings), [mappings]);
  const selected = properties.find((p) => p.id === selectedId) || null;

  function patchProperty(id: string, patch: Partial<PropertyField>) {
    setProperties((prev) =>
      prev.map((p) => (p.id === id ? { ...p, ...patch } : p)),
    );
  }

  function patchMapping(id: string, patch: Partial<ColumnMappingRow>) {
    setMappings((prev) =>
      prev.map((m) => {
        if (m.id !== id) return m;
        const next = { ...m, ...patch };
        if ("target_property" in patch) {
          next.status = next.target_property ? "mapped" : "skipped";
          next.confidence = next.target_property ? Math.max(next.confidence, 0.5) : 0;
        }
        return next;
      }),
    );
  }

  function addProperty() {
    const np = emptyProperty();
    setProperties((prev) => [...prev, np]);
    setSelectedId(np.id);
    setMsg("已新增属性（待保存）");
  }

  async function saveProperty(p: PropertyField) {
    setErr(null);
    setMsg("");
    const errors = validateProperty(p);
    if (errors.length > 0) {
      setErr(errors.join("；"));
      return;
    }
    if (sourceMode === "demo") {
      setMsg(`属性 ${p.name} 已本地保存（演示路径）`);
      return;
    }
    try {
      if (isNewPropertyId(p.id)) {
        const res = await apiPost<ApiPropertyRow>(
          `/v1/ontology/object-types/${encodeURIComponent(typeId)}/properties`,
          mapFieldToAddRequest(p),
        );
        const mapped = mapApiPropertyToField(res, { [p.name]: p.columnMapping });
        setProperties((prev) => prev.map((x) => (x.id === p.id ? { ...mapped, columnMapping: p.columnMapping } : x)));
        setSelectedId(mapped.id);
        setMsg(`属性 ${p.name} 已创建`);
      } else {
        // 后端无 PUT property：本地保留，提示用映射 Tab 持久化列映射
        setMsg(
          `属性 ${p.name} 已本地更新（元数据无 PUT；列映射请用「列映射」Tab 保存）`,
        );
      }
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  async function deleteProperty(p: PropertyField) {
    if (!window.confirm(`删除属性 ${p.name}？`)) return;
    setErr(null);
    setMsg("");
    setProperties((prev) => prev.filter((x) => x.id !== p.id));
    if (selectedId === p.id) setSelectedId(null);
    setMsg(`属性 ${p.name} 已从列表移除（演示/本地）`);
  }

  async function runAutomap() {
    setErr(null);
    setMsg("");
    setMapBusy(true);
    try {
      if (sourceMode === "live") {
        const res = await apiPost<{ items?: Array<Partial<ColumnMappingRow>> }>(
          `/v1/ontology/object-types/${encodeURIComponent(typeId)}/automap`,
          {},
        );
        const rows = (res.items || []).map((r) => normalizeMappingRow(r, typeId));
        setMappings(rows);
        setProperties((prev) => applyMappingsToProperties(prev, rows));
        setMsg(`Automap 完成：${countMappedColumns(rows).mapped}/${rows.length} 列已映射`);
      } else {
        // 演示：本地 snake_case
        setProperties((prev) => {
          const next = prev.map((p) =>
            p.columnMapping
              ? p
              : { ...p, columnMapping: autoMapColumnName(p.name) },
          );
          setMappings(deriveLocalMappingRows(next, typeId).map((m) => ({
            ...m,
            target_property: m.source_column ? next.find((p) => autoMapColumnName(p.name) === m.source_column || p.columnMapping === m.source_column)?.name || m.target_property : m.target_property,
            status: "mapped",
            confidence: 0.85,
            auto: true,
          })));
          return next;
        });
        setMsg("已自动映射所有未映射列（演示路径）");
      }
    } catch (e) {
      // API 失败 → 本地回退并标演示
      setSourceMode("demo");
      setProperties((prev) =>
        prev.map((p) =>
          p.columnMapping ? p : { ...p, columnMapping: autoMapColumnName(p.name) },
        ),
      );
      setMappings(() => {
        const nextProps = properties.map((p) =>
          p.columnMapping ? p : { ...p, columnMapping: autoMapColumnName(p.name) },
        );
        return deriveLocalMappingRows(nextProps, typeId).map((m) => ({
          ...m,
          target_property: nextProps.find((p) => p.columnMapping === m.source_column)?.name || "",
          auto: true,
          status: "mapped",
          confidence: 0.8,
        }));
      });
      setMsg(`Automap API 失败，已本地映射（演示路径）：${String((e as Error).message || e)}`);
    } finally {
      setMapBusy(false);
    }
  }

  async function saveMappings() {
    setErr(null);
    setMsg("");
    setMapBusy(true);
    try {
      if (sourceMode === "live") {
        const body = buildMappingSaveBody(mappings);
        const res = await apiPut<{ items?: Array<Partial<ColumnMappingRow>> }>(
          `/v1/ontology/object-types/${encodeURIComponent(typeId)}/column-mapping`,
          body,
        );
        const rows = (res.items || []).map((r) => normalizeMappingRow(r, typeId));
        setMappings(rows.length ? rows : mappings);
        setProperties((prev) => applyMappingsToProperties(prev, rows.length ? rows : mappings));
        setMsg(`列映射已保存：${countMappedColumns(rows.length ? rows : mappings).mapped} 条`);
      } else {
        setProperties((prev) => applyMappingsToProperties(prev, mappings));
        setMsg("列映射已本地保存（演示路径）");
      }
    } catch (e) {
      setSourceMode("demo");
      setProperties((prev) => applyMappingsToProperties(prev, mappings));
      setMsg(`保存 API 失败，已本地保留（演示路径）：${String((e as Error).message || e)}`);
    } finally {
      setMapBusy(false);
    }
  }

  return (
    <S2Chrome
      title={typeId ? `${typeId} · 属性编辑器` : "属性编辑器"}
      lede="属性列表表格 · CRUD · 列映射 · Automap"
    >
      <div className="ont-page w3-c3c4-page">
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
            disabled={mapBusy}
            onClick={() => void runAutomap()}
          >
            {mapBusy ? "处理中…" : "自动映射全部"}
          </button>
          {activeTab === "mapping" && (
            <button
              type="button"
              className="btn-primary"
              disabled={mapBusy}
              onClick={() => void saveMappings()}
            >
              保存映射
            </button>
          )}
        </BpToolbar>

        {sourceMode === "demo" && (
          <div className="w3-c3c4-demo-banner" role="status">
            <span className="w3-c3c4-demo-badge">演示路径</span>
            <span className="w3-c3c4-demo-text">
              属性/列映射 API 不可用，当前为本地演示数据。
            </span>
          </div>
        )}
        {sourceMode === "live" && (
          <div className="w3-c3c4-live-banner" role="status">
            <span className="w3-c3c4-live-badge">Live</span>
            <span className="w3-c3c4-demo-text">
              已接 `/v1/ontology/object-types/:id/properties` 与 column-mapping / automap
            </span>
          </div>
        )}

        {msg && <p className="bp-prop-ok">{msg}</p>}
        {err && <p className="error">{err}</p>}

        <BpTabs
          tabs={[
            { id: "properties", label: `属性 (${summary.total})` },
            {
              id: "mapping",
              label: `列映射 (${mapStats.mapped}/${mapStats.total || summary.total})`,
            },
          ]}
          active={activeTab}
          onChange={(id) => setActiveTab(id as "properties" | "mapping")}
        />

        <div className="w3-c3c4-dataset-bar">
          <span className="muted" style={{ fontSize: "0.75rem" }}>
            类型: <code>{typeId}</code> · 总属性 {summary.total} · 主键 {summary.pkCount} · 标题键{" "}
            {summary.titleKeyCount}
            {mapStats.total > 0 && (
              <> · 已映射 {mapStats.mapped}/{mapStats.total}</>
            )}
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

        {activeTab === "mapping" ? (
          <div className="bp-table-wrap w3-c3c4-mapping-wrap">
            <table className="data-table bp-table w3-c3c4-mapping-table">
              <thead>
                <tr>
                  <th>源列</th>
                  <th>目标属性</th>
                  <th style={{ width: 90 }}>置信度</th>
                  <th style={{ width: 90 }}>状态</th>
                  <th style={{ width: 70 }}>来源</th>
                </tr>
              </thead>
              <tbody>
                {mappings.map((m) => (
                  <tr key={m.id}>
                    <td>
                      <code style={{ fontSize: "0.75rem" }}>{m.source_column || "—"}</code>
                    </td>
                    <td>
                      <select
                        className="aos-input"
                        value={m.target_property}
                        onChange={(e) =>
                          patchMapping(m.id, { target_property: e.target.value })
                        }
                        style={{ fontSize: "0.75rem", minWidth: 140 }}
                      >
                        <option value="">（未映射）</option>
                        {properties
                          .filter((p) => p.name.trim())
                          .map((p) => (
                            <option key={p.id} value={p.name}>
                              {p.name}
                            </option>
                          ))}
                      </select>
                    </td>
                    <td className="muted" style={{ fontSize: "0.75rem" }}>
                      {m.confidence > 0 ? `${Math.round(m.confidence * 100)}%` : "—"}
                    </td>
                    <td>
                      <span
                        className={
                          m.target_property ? "w3-c3c4-map-ok" : "w3-c3c4-map-skip"
                        }
                      >
                        {m.target_property ? "mapped" : "skipped"}
                      </span>
                    </td>
                    <td className="muted" style={{ fontSize: "0.7rem" }}>
                      {m.auto ? "auto" : "manual"}
                    </td>
                  </tr>
                ))}
                {mappings.length === 0 && !loading && (
                  <tr>
                    <td colSpan={5} className="muted" style={{ textAlign: "center", padding: 24 }}>
                      暂无列映射。点击「自动映射全部」或先在属性 Tab 添加属性。
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 320px",
              gap: 8,
            }}
          >
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
                            color: "var(--text-on-brand)",
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

            <aside
              style={{
                border: "1px solid var(--aos-border)",
                borderRadius: 4,
                background: "var(--aos-surface)",
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
        )}
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
        <span style={{ fontFamily: "monospace", color: "var(--aos-accent)" }}>
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
              <div style={{ marginTop: 8, paddingLeft: 12, borderLeft: "2px solid var(--aos-border)" }}>
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
