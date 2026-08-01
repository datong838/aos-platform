import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiGet } from "../../api/client";
import {
  BpBanner,
  BpMetricGrid,
  BpTable,
  BpTabs,
  BpToolbar,
} from "./blueprintUi";
import { S2Chrome } from "./shared";

// ── Types ──────────────────────────────────────────────────────

export type ColumnType = "STRING" | "INTEGER" | "DECIMAL" | "BOOLEAN" | "TIMESTAMP";

export type ColumnInfo = {
  name: string;
  type: ColumnType;
  nullable: boolean;
  nullRate: number; // 0..1
  uniqueCount: number;
  stats?: { min?: number; max?: number; avg?: number; stddev?: number };
};

export type DatasetRow = Record<string, string | number | boolean | null>;

export type DatasetPreview = {
  id: string;
  name: string;
  path: string;
  format: string;
  rowCount: number;
  sizeBytes: number;
  lastUpdatedAt: string;
  branch: string;
  transactionId: string;
  columns: ColumnInfo[];
  rows: DatasetRow[];
};

export type DatasetPreviewApiResponse = {
  id?: string;
  dataset_id?: string;
  name?: string;
  path?: string;
  format?: string;
  rowCount?: number;
  total?: number;
  sizeBytes?: number;
  lastUpdatedAt?: string;
  branch?: string;
  transactionId?: string;
  columns?: Array<ColumnInfo | string>;
  rows?: DatasetRow[];
  mode?: string;
  synthetic?: boolean;
};

export type DatasetPreviewSource = "primary-live" | "primary-demo" | "fallback-demo";

export type SortDir = "asc" | "desc";

export type SortState = { col: string; dir: SortDir } | null;

// ── Pure functions ─────────────────────────────────────────────

export const TYPE_LABELS: Record<ColumnType, string> = {
  STRING: "字符串",
  INTEGER: "整数",
  DECIMAL: "小数",
  BOOLEAN: "布尔",
  TIMESTAMP: "时间戳",
};

export const TYPE_TONE: Record<ColumnType, "ok" | "warn" | "bad" | "muted"> = {
  STRING: "muted",
  INTEGER: "ok",
  DECIMAL: "warn",
  BOOLEAN: "muted",
  TIMESTAMP: "ok",
};

export function formatBytes(bytes: number): string {
  if (bytes <= 0) return "—";
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  const gb = mb / 1024;
  return `${gb.toFixed(2)} GB`;
}

export function formatNumber(n: number): string {
  return n.toLocaleString("en-US");
}

export function formatTimestamp(iso: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "刚刚";
  if (mins < 60) return `${mins} 分钟前`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} 小时前`;
  return `${Math.floor(hours / 24)} 天前`;
}

export function formatNullRate(rate: number): string {
  if (rate <= 0) return "0%";
  if (rate < 0.001) return "<0.1%";
  return `${(rate * 100).toFixed(1)}%`;
}

export function sortRows(
  rows: DatasetRow[],
  sort: SortState,
): DatasetRow[] {
  if (!sort) return rows;
  const { col, dir } = sort;
  return [...rows].sort((a, b) => {
    const av = a[col];
    const bv = b[col];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (typeof av === "number" && typeof bv === "number") {
      return dir === "asc" ? av - bv : bv - av;
    }
    const cmp = String(av).localeCompare(String(bv));
    return dir === "asc" ? cmp : -cmp;
  });
}

export function filterRows(rows: DatasetRow[], query: string): DatasetRow[] {
  const q = query.trim().toLowerCase();
  if (!q) return rows;
  return rows.filter((r) =>
    Object.values(r).some((v) =>
      v != null && String(v).toLowerCase().includes(q),
    ),
  );
}

export function filterColumns(columns: ColumnInfo[], query: string): ColumnInfo[] {
  const q = query.trim().toLowerCase();
  if (!q) return columns;
  return columns.filter((c) => c.name.toLowerCase().includes(q));
}

export function numericColumns(columns: ColumnInfo[]): ColumnInfo[] {
  return columns.filter((c) => c.type === "INTEGER" || c.type === "DECIMAL");
}

export function computeColumnStats(values: number[]): {
  min: number;
  max: number;
  avg: number;
  stddev: number;
} | null {
  const clean = values.filter((v) => typeof v === "number" && !isNaN(v));
  if (clean.length === 0) return null;
  const min = Math.min(...clean);
  const max = Math.max(...clean);
  const sum = clean.reduce((a, b) => a + b, 0);
  const avg = sum / clean.length;
  const variance =
    clean.reduce((a, b) => a + (b - avg) ** 2, 0) / clean.length;
  const stddev = Math.sqrt(variance);
  return { min, max, avg, stddev };
}

export function toCsv(rows: DatasetRow[], columns: ColumnInfo[]): string {
  if (rows.length === 0 || columns.length === 0) return "";
  const header = columns.map((c) => c.name).join(",");
  const body = rows.map((r) =>
    columns
      .map((c) => {
        const v = r[c.name];
        if (v == null) return "";
        const s = String(v);
        return s.includes(",") || s.includes('"') ? `"${s.replace(/"/g, '""')}"` : s;
      })
      .join(","),
  );
  return [header, ...body].join("\n");
}

export function nextSortDir(current: SortState, col: string): SortState {
  if (!current || current.col !== col) return { col, dir: "asc" };
  if (current.dir === "asc") return { col, dir: "desc" };
  return null;
}

function inferColumnType(rows: DatasetRow[], name: string): ColumnType {
  const value = rows.map((row) => row[name]).find((item) => item != null);
  if (typeof value === "boolean") return "BOOLEAN";
  if (typeof value === "number") return Number.isInteger(value) ? "INTEGER" : "DECIMAL";
  return "STRING";
}

export function normalizeDatasetPreview(
  raw: DatasetPreviewApiResponse,
  requestedId: string,
): { data: DatasetPreview; source: Exclude<DatasetPreviewSource, "fallback-demo"> } {
  const rows = Array.isArray(raw.rows) ? raw.rows : [];
  const rawColumns = Array.isArray(raw.columns) ? raw.columns : [];
  const columns = rawColumns.map((column): ColumnInfo => {
    if (typeof column !== "string") {
      return {
        name: column.name,
        type: column.type || inferColumnType(rows, column.name),
        nullable: Boolean(column.nullable),
        nullRate: typeof column.nullRate === "number" ? column.nullRate : 0,
        uniqueCount: typeof column.uniqueCount === "number" ? column.uniqueCount : 0,
        stats: column.stats,
      };
    }
    const nonNull = rows.map((row) => row[column]).filter((item) => item != null);
    return {
      name: column,
      type: inferColumnType(rows, column),
      nullable: nonNull.length < rows.length,
      nullRate: rows.length > 0 ? (rows.length - nonNull.length) / rows.length : 0,
      uniqueCount: new Set(nonNull.map(String)).size,
    };
  });
  const id = raw.id || raw.dataset_id || requestedId;
  const synthetic = raw.synthetic === true || raw.mode === "demo";
  return {
    data: {
      id,
      name: raw.name || id,
      path: raw.path || "—",
      format: raw.format || (synthetic ? "API demo" : "API preview"),
      rowCount: typeof raw.rowCount === "number" ? raw.rowCount : (raw.total ?? rows.length),
      sizeBytes: typeof raw.sizeBytes === "number" ? raw.sizeBytes : 0,
      lastUpdatedAt: raw.lastUpdatedAt || "",
      branch: raw.branch || "—",
      transactionId: raw.transactionId || "—",
      columns,
      rows,
    },
    source: synthetic ? "primary-demo" : "primary-live",
  };
}

export function emptyDatasetPreview(datasetId: string): DatasetPreview {
  return {
    id: datasetId,
    name: datasetId,
    path: "—",
    format: "—",
    rowCount: 0,
    sizeBytes: 0,
    lastUpdatedAt: "",
    branch: "—",
    transactionId: "—",
    columns: [],
    rows: [],
  };
}

export function datasetPreviewDemoFallbackEnabled(
  value: string | undefined = import.meta.env.VITE_AOS_DATASET_PREVIEW_DEMO_FALLBACK,
): boolean {
  return value?.trim().toLowerCase() === "true";
}

export function datasetPreviewEmptyMessage(source: DatasetPreviewSource | null): string {
  if (source === "fallback-demo") return "回落来源暂无行";
  if (source === "primary-demo") return "API 演示预览成功但暂无行";
  if (source === "primary-live") return "预览成功但暂无行";
  return "没有可确认的预览行";
}

export function buildDatasetCsvExport(
  data: DatasetPreview,
  source: DatasetPreviewSource | null,
  generatedAt = new Date().toISOString(),
): string {
  if (source !== "primary-live" || data.rows.length === 0) {
    throw new Error("仅可导出主预览 API 返回的非空真实数据");
  }
  const csv = toCsv(data.rows.slice(0, 100), data.columns);
  return [
    `# source=${source}`,
    `# datasetId=${data.id}`,
    `# generatedAt=${generatedAt}`,
    csv,
  ].join("\n");
}

// ── Mock data ──────────────────────────────────────────────────

const DEMO_COLUMNS: ColumnInfo[] = [
  { name: "order_id", type: "STRING", nullable: false, nullRate: 0, uniqueCount: 892104 },
  { name: "amount", type: "DECIMAL", nullable: true, nullRate: 0.001, uniqueCount: 845000, stats: { min: 0.01, max: 9999.99, avg: 456.78, stddev: 312.4 } },
  { name: "currency", type: "STRING", nullable: false, nullRate: 0, uniqueCount: 5 },
  { name: "customer", type: "STRING", nullable: true, nullRate: 0.012, uniqueCount: 45000 },
  { name: "region", type: "STRING", nullable: false, nullRate: 0, uniqueCount: 3 },
  { name: "qty", type: "INTEGER", nullable: false, nullRate: 0, uniqueCount: 120, stats: { min: 1, max: 500, avg: 3.2, stddev: 8.7 } },
  { name: "total", type: "DECIMAL", nullable: true, nullRate: 0.001, uniqueCount: 830000, stats: { min: 0.01, max: 50000, avg: 912.45, stddev: 620.1 } },
];

const DEMO_ROWS: DatasetRow[] = [
  { order_id: "ORD-0721-001", amount: 129.99, currency: "USD", customer: "Alice Chen", region: "NA", qty: 2, total: 259.98 },
  { order_id: "ORD-0721-002", amount: 899.0, currency: "GBP", customer: "James Wright", region: "EU", qty: 1, total: 899.0 },
  { order_id: "ORD-0721-003", amount: 156.2, currency: "CAD", customer: "Marie Dubois", region: "EU", qty: 3, total: 468.6 },
  { order_id: "ORD-0721-004", amount: 449.0, currency: "CNY", customer: "张伟", region: "APAC", qty: 1, total: 449.0 },
  { order_id: "ORD-0721-005", amount: 2100.0, currency: "USD", customer: "John Smith", region: "NA", qty: 5, total: 10500.0 },
  { order_id: "ORD-0721-006", amount: 78.5, currency: "USD", customer: "Sarah Kim", region: "NA", qty: 1, total: 78.5 },
  { order_id: "ORD-0721-007", amount: 1299.0, currency: "EUR", customer: "Hans Mueller", region: "EU", qty: 2, total: 2598.0 },
  { order_id: "ORD-0721-008", amount: 320.0, currency: "CNY", customer: "李娜", region: "APAC", qty: 4, total: 1280.0 },
];

const DEMO_DATASET: DatasetPreview = {
  id: "curated_orders",
  name: "curated_orders",
  path: "/Curated/Ecom/orders",
  format: "Parquet + Iceberg",
  rowCount: 892104,
  sizeBytes: 134217728, // 128 MB
  lastUpdatedAt: new Date(Date.now() - 2 * 60000).toISOString(),
  branch: "master",
  transactionId: "tx-847",
  columns: DEMO_COLUMNS,
  rows: DEMO_ROWS,
};

// ── Page Component ─────────────────────────────────────────────

const PREVIEW_LIMIT = 100;

export function DatasetPreviewPage() {
  const { datasetId } = useParams<{ datasetId: string }>();
  const requestedId = datasetId || "unknown";
  const [ds, setDs] = useState<DatasetPreview>(() => emptyDatasetPreview(requestedId));
  const [source, setSource] = useState<DatasetPreviewSource | null>(null);
  const [primaryErr, setPrimaryErr] = useState("");
  const [loading, setLoading] = useState(true);
  const requestRef = useRef(0);
  const [tab, setTab] = useState("preview");
  const [sort, setSort] = useState<SortState>(null);
  const [rowQuery, setRowQuery] = useState("");
  const [colQuery, setColQuery] = useState("");
  const [msg, setMsg] = useState("");

  const loadPreview = useCallback(async () => {
    const requestId = ++requestRef.current;
    setLoading(true);
    setMsg("");
    try {
      const raw = await apiGet<DatasetPreviewApiResponse>(
        `/v1/datasets/${encodeURIComponent(requestedId)}/preview`,
      );
      if (requestId !== requestRef.current) return;
      const normalized = normalizeDatasetPreview(raw, requestedId);
      setDs(normalized.data);
      setSource(normalized.source);
      setPrimaryErr("");
    } catch (e) {
      if (requestId !== requestRef.current) return;
      const message = String((e as Error).message || e);
      setPrimaryErr(message);
      if (datasetPreviewDemoFallbackEnabled()) {
        setDs({
          ...DEMO_DATASET,
          id: requestedId,
          name: `${requestedId}（演示回落）`,
          path: `内置演示数据 · ${DEMO_DATASET.path}`,
        });
        setSource("fallback-demo");
      } else {
        setDs(emptyDatasetPreview(requestedId));
        setSource(null);
      }
    } finally {
      if (requestId === requestRef.current) setLoading(false);
    }
  }, [requestedId]);

  useEffect(() => {
    setDs(emptyDatasetPreview(requestedId));
    setSource(null);
    setPrimaryErr("");
    setRowQuery("");
    setColQuery("");
    setSort(null);
    void loadPreview();
  }, [loadPreview, requestedId]);

  const filteredRows = useMemo(() => {
    const filtered = filterRows(ds.rows, rowQuery);
    const sorted = sortRows(filtered, sort);
    return sorted.slice(0, PREVIEW_LIMIT);
  }, [ds.rows, rowQuery, sort]);

  const filteredCols = useMemo(
    () => filterColumns(ds.columns, colQuery),
    [ds.columns, colQuery],
  );

  const numericCols = useMemo(() => numericColumns(ds.columns), [ds.columns]);

  async function handleExport() {
    setMsg("");
    try {
      const csv = buildDatasetCsvExport(ds, source);
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${ds.id.replace(/[^a-zA-Z0-9_-]/g, "_")}-preview.csv`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setMsg("CSV 已生成（含 source/datasetId/generatedAt 元数据）");
    } catch (e) {
      setMsg(String((e as Error).message || e));
    }
  }

  return (
    <S2Chrome title={`数据集预览 · ${ds.name}`} lede={`路径 ${ds.path} · 格式 ${ds.format}`}>
      <BpToolbar>
        <Link to="/data/datasets" className="btn-nav">← 数据集列表</Link>
        <button
          type="button"
          className="btn-primary"
          data-testid="dataset-export"
          disabled={source !== "primary-live" || ds.rows.length === 0}
          title={source === "primary-live" && ds.rows.length > 0 ? "导出当前真实预览行" : "只有主预览 API 的非空真实数据可导出"}
          onClick={() => void handleExport()}
        >
          导出 CSV
        </button>
        <button type="button" className="btn-nav" disabled={loading} onClick={() => void loadPreview()}>
          {loading ? "刷新中…" : "刷新预览"}
        </button>
        <Link to="/data/queries/new" className="btn-nav">新建查询</Link>
        <span className="muted mono" style={{ marginLeft: "auto" }}>tx: {ds.transactionId}</span>
      </BpToolbar>

      {loading && <p className="muted">加载中…</p>}
      {primaryErr && source === "fallback-demo" && (
        <BpBanner tone="warn">
          主预览失败：{primaryErr}；当前来自内置演示数据（配置已显式允许，不代表服务端数据）。
        </BpBanner>
      )}
      {primaryErr && source !== "fallback-demo" && (
        <BpBanner tone="warn">
          主预览失败：{primaryErr}；未启用演示回落，当前不展示替代数据。
        </BpBanner>
      )}
      {!primaryErr && source === "primary-live" && <BpBanner tone="info">来源：主预览 API</BpBanner>}
      {!primaryErr && source === "primary-demo" && (
        <BpBanner tone="info">来源：主预览 API 返回的 synthetic 演示数据</BpBanner>
      )}
      {msg && <p className="aos-text">{msg}</p>}

      <BpMetricGrid
        items={[
          { label: "行数", value: formatNumber(ds.rowCount), tone: "ok" },
          { label: "列数", value: ds.columns.length, tone: "muted" },
          { label: "大小", value: formatBytes(ds.sizeBytes), tone: "muted" },
          { label: "上次更新", value: formatTimestamp(ds.lastUpdatedAt), tone: "ok" },
        ]}
      />

      <BpTabs
        tabs={[
          { id: "preview", label: "预览" },
          { id: "details", label: "详情" },
          { id: "stats", label: "统计信息" },
        ]}
        active={tab}
        onChange={setTab}
      />

      {tab === "preview" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: "0.75rem" }}>
          <div>
            {!loading && ds.rows.length === 0 && (
              <BpBanner tone={source ? "info" : "warn"}>{datasetPreviewEmptyMessage(source)}</BpBanner>
            )}
            <BpToolbar>
              <input
                type="search"
                placeholder="搜索行数据…"
                value={rowQuery}
                onChange={(e) => setRowQuery(e.target.value)}
                style={{ minWidth: 180 }}
              />
              <span className="muted" style={{ fontSize: "0.75rem" }}>
                显示前 {filteredRows.length} 行 · 共 {formatNumber(ds.rowCount)} 行
              </span>
            </BpToolbar>
            <div style={{ marginBottom: "0.25rem", display: "flex", gap: 4, flexWrap: "wrap" }}>
              {ds.columns.map((c) => (
                <button
                  key={c.name}
                  type="button"
                  onClick={() => setSort((prev) => nextSortDir(prev, c.name))}
                  style={{
                    fontSize: "0.7rem",
                    padding: "2px 6px",
                    border: "1px solid var(--aos-border)",
                    background: sort?.col === c.name ? "var(--aos-accent-light)" : "transparent",
                    cursor: "pointer",
                  }}
                >
                  {c.name}
                  {sort?.col === c.name ? ` ${sort.dir === "asc" ? "↑" : "↓"}` : ""}
                </button>
              ))}
            </div>
            <BpTable
              columns={ds.columns.map((c) => `${c.name} [${c.type}]`)}
              rows={filteredRows.map((r) =>
                ds.columns.map((c) => {
                  const v = r[c.name];
                  if (v == null) return <span className="muted">—</span>;
                  return String(v);
                }),
              )}
            />
            <div style={{ marginTop: "0.5rem" }}>
              <p className="muted" style={{ fontSize: "0.7rem" }}>
                当前排序: {sort ? `${sort.col} ${sort.dir}` : "无"}
              </p>
            </div>
          </div>
          <div className="bp-object-panel">
            <h2 className="aos-text" style={{ fontSize: "0.85rem", marginBottom: "0.5rem" }}>列信息 ({ds.columns.length})</h2>
            <input
              type="search"
              placeholder="搜索列名…"
              value={colQuery}
              onChange={(e) => setColQuery(e.target.value)}
              style={{ width: "100%", marginBottom: "0.5rem" }}
            />
            {filteredCols.map((c) => (
              <div key={c.name} style={{ padding: "0.4rem 0", borderBottom: "1px solid var(--aos-border)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <strong className="mono">{c.name}</strong>
                  <span className={`bp-discover-badge bp-discover-badge-${TYPE_TONE[c.type]}`}>
                    {c.type}
                  </span>
                </div>
                <div className="muted" style={{ fontSize: "0.7rem", marginTop: 2 }}>
                  空值 {formatNullRate(c.nullRate)} · 唯一 ~{formatNumber(c.uniqueCount)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === "details" && (
        <BpTable
          columns={["列名", "类型", "可空", "唯一值数"]}
          rows={ds.columns.map((c) => [
            <span className="mono">{c.name}</span>,
            <span className={`bp-discover-badge bp-discover-badge-${TYPE_TONE[c.type]}`}>{c.type}</span>,
            c.nullable ? "是" : "否",
            formatNumber(c.uniqueCount),
          ])}
        />
      )}

      {tab === "stats" && (
        <div>
          {numericCols.length === 0 ? (
            <BpBanner tone="warn">无数值列可统计</BpBanner>
          ) : (
            <BpTable
              columns={["列名", "Min", "Max", "Avg", "Stddev"]}
              rows={numericCols.map((c) => {
                const s = c.stats;
                return [
                  <span className="mono">{c.name}</span>,
                  s?.min != null ? s.min.toFixed(2) : "—",
                  s?.max != null ? s.max.toFixed(2) : "—",
                  s?.avg != null ? s.avg.toFixed(2) : "—",
                  s?.stddev != null ? s.stddev.toFixed(2) : "—",
                ];
              })}
            />
          )}
        </div>
      )}

      <BpBanner tone="info">
        对齐 <code>dataset.html</code> · 预览/详情/统计三 Tab ·{" "}
        <Link to="/data/health">数据健康</Link> ·{" "}
        <Link to="/data/lineage">数据沿袭</Link>
      </BpBanner>
    </S2Chrome>
  );
}
