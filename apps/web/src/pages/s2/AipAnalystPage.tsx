/**
 * E2.5 — AIP 分析师工作台（深度完善）
 *
 * 三栏全屏布局：左 SQL 查询树 + 中 SQL 编辑器 + 右 结果地图
 * 底部状态栏：行数 / 耗时 / 缓存命中 / 导出
 *
 * 纯函数集中在文件顶部（SQL 解析 / 图表数据转换 / 地图坐标映射），便于测试。
 */
import { useMemo, useState } from "react";
import { PageChrome } from "../../components/PageChrome";
import { BpBadge } from "../../components/bp";

/* ----------------------------------------------------------------------------
 * 类型
 * ------------------------------------------------------------------------- */
export type ResultTab = "table" | "chart" | "map" | "raw";
export type ChartType = "bar" | "line" | "pie";
export type QueryCategory = "favorites" | "history" | "recent";

export type SavedQuery = {
  id: string;
  name: string;
  sql: string;
  category: QueryCategory;
  updatedAt: string;
};

export type ResultColumn = {
  name: string;
  type: "string" | "number" | "coords";
};

export type ResultRow = {
  [key: string]: string | number;
};

export type QueryResult = {
  columns: ResultColumn[];
  rows: ResultRow[];
  durationMs: number;
  cacheHit: boolean;
};

export type MapMarker = {
  id: string;
  name: string;
  lat: number;
  lng: number;
  intensity: number;
};

/* ----------------------------------------------------------------------------
 * 纯函数：SQL 解析
 * ------------------------------------------------------------------------- */

/**提取 SQL 中 SELECT 与 FROM 之间的列（简易实现，逗号分隔）。*/
export function extractColumns(sql: string): string[] {
  const m = sql.match(/select\s+(.+?)\s+from/is);
  if (!m) return [];
  const raw = m[1].trim();
  if (raw === "*") return ["*"];
  return raw
    .split(",")
    .map((s) => s.trim().replace(/.*\.\w+\s+as\s+/i, "").replace(/\s+as\s+\w+/i, ""))
    .filter(Boolean);
}

/**提取 SQL 中的 FROM 目标表名。*/
export function extractTable(sql: string): string {
  const m = sql.match(/from\s+([a-zA-Z_][\w.]*)/is);
  return m ? m[1].trim() : "";
}

/**提取 SQL 中的 WHERE 条件（简易，返回第一个 WHERE 到结尾/ORDER 前的文本）。*/
export function extractWhere(sql: string): string {
  const m = sql.match(/where\s+(.+?)(\s+(order|group|limit)\s+|$)/is);
  return m ? m[1].trim() : "";
}

/**判断 SQL 是否包含 LIMIT。*/
export function hasLimit(sql: string): boolean {
  return /\blimit\s+\d+/i.test(sql);
}

/**简易 SQL 格式化：关键字大写 + 去除多余空行。*/
export function formatSql(sql: string): string {
  const keywords = ["select", "from", "where", "and", "or", "order by", "group by", "limit", "join", "on"];
  let out = sql.replace(/\s+/g, " ").trim();
  for (const kw of keywords) {
    const re = new RegExp(`\\b${kw}\\b`, "gi");
    out = out.replace(re, kw.toUpperCase());
  }
  return out + ";";
}

/**校验 SQL 是否为查询语句（以 SELECT 开头）。*/
export function isSelectQuery(sql: string): boolean {
  return /^\s*select\b/i.test(sql.trim());
}

/* ----------------------------------------------------------------------------
 * 纯函数：图表数据转换
 * ------------------------------------------------------------------------- */

/**从结果行中提取某列的所有数值，用于柱状图/折线图。*/
export function columnToNumbers(rows: ResultRow[], col: string): number[] {
  return rows.map((r) => Number(r[col] ?? 0)).filter((n) => !Number.isNaN(n));
}

/**把数字序列归一化到 0-100 高度百分比（用于柱状图）。*/
export function normalizeBars(values: number[]): number[] {
  const max = Math.max(...values, 1);
  return values.map((v) => (v / max) * 100);
}

/**把数值序列转 SVG path（折线图）。*/
export function linePath(values: number[], width = 200, height = 60): string {
  if (values.length === 0) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const step = values.length > 1 ? width / (values.length - 1) : 0;
  return values
    .map((v, i) => {
      const x = i * step;
      const y = height - ((v - min) / range) * height;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

/**饼图：把数值序列转成 [{value, percent, color}]。*/
export function toPieSlices(values: number[]): { value: number; percent: number; color: string }[] {
  const total = values.reduce((a, b) => a + b, 0) || 1;
  const palette = ["#6366F1", "#06B6D4", "#F59E0B", "#10B981", "#EF4444", "#8B5CF6"];
  return values.map((v, i) => ({
    value: v,
    percent: (v / total) * 100,
    color: palette[i % palette.length],
  }));
}

/* ----------------------------------------------------------------------------
 * 纯函数：地图坐标映射
 * ------------------------------------------------------------------------- */

/**解析 "lat,lng" 字符串为 {lat, lng}；失败返回 null。*/
export function parseCoords(s: string): { lat: number; lng: number } | null {
  const m = String(s).match(/^(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)$/);
  if (!m) return null;
  const lat = parseFloat(m[1]);
  const lng = parseFloat(m[2]);
  if (Math.abs(lat) > 90 || Math.abs(lng) > 180) return null;
  return { lat, lng };
}

/**把 lat/lng 投影到 SVG viewport（默认 0-100 的相对坐标）。*/
export function projectToMap(
  lat: number,
  lng: number,
  bounds: { latMin: number; latMax: number; lngMin: number; lngMax: number },
  size = 100,
): { x: number; y: number } {
  const { latMin, latMax, lngMin, lngMax } = bounds;
  const x = ((lng - lngMin) / (lngMax - lngMin || 1)) * size;
  const y = size - ((lat - latMin) / (latMax - latMin || 1)) * size;
  return { x, y };
}

/**把结果行批量转成地图标记。*/
export function rowsToMarkers(
  rows: ResultRow[],
  coordsCol: string,
  nameCol: string,
): MapMarker[] {
  const out: MapMarker[] = [];
  for (const r of rows) {
    const parsed = parseCoords(String(r[coordsCol] ?? ""));
    if (!parsed) continue;
    out.push({
      id: String(r.id ?? `m${out.length}`),
      name: String(r[nameCol] ?? ""),
      lat: parsed.lat,
      lng: parsed.lng,
      intensity: Number(r.rating ?? 1),
    });
  }
  return out;
}

/* ----------------------------------------------------------------------------
 * 纯函数：表格操作
 * ------------------------------------------------------------------------- */

/**按某列排序（asc/desc），返回新数组。*/
export function sortRows(rows: ResultRow[], col: string, dir: "asc" | "desc" = "asc"): ResultRow[] {
  const factor = dir === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const av = a[col];
    const bv = b[col];
    if (typeof av === "number" && typeof bv === "number") return (av - bv) * factor;
    return String(av).localeCompare(String(bv)) * factor;
  });
}

/**按关键字过滤行（任一列包含即命中）。*/
export function filterRows(rows: ResultRow[], q: string): ResultRow[] {
  const k = q.trim().toLowerCase();
  if (!k) return rows;
  return rows.filter((r) =>
    Object.values(r).some((v) => String(v).toLowerCase().includes(k)),
  );
}

/**分页：返回 [start, end) 切片。*/
export function paginate<T>(arr: T[], page: number, pageSize: number): T[] {
  const start = (page - 1) * pageSize;
  return arr.slice(start, start + pageSize);
}

/**计算总页数。*/
export function totalPages(total: number, pageSize: number): number {
  return Math.max(1, Math.ceil(total / pageSize));
}

/* ----------------------------------------------------------------------------
 * Mock 数据
 * ------------------------------------------------------------------------- */
export const MOCK_QUERIES: SavedQuery[] = [
  { id: "q1", name: "北安普顿咖啡店", sql: "SELECT name, coords, rating FROM shops WHERE city = 'Northampton'", category: "favorites", updatedAt: "10:42" },
  { id: "q2", name: "高评分店铺", sql: "SELECT name, rating FROM shops WHERE rating >= 4 ORDER BY rating DESC", category: "recent", updatedAt: "10:30" },
  { id: "q3", name: "库存预警", sql: "SELECT sku, stock FROM inventory WHERE stock < 10", category: "history", updatedAt: "09:15" },
  { id: "q4", name: "销售趋势", sql: "SELECT date, revenue FROM sales ORDER BY date DESC LIMIT 30", category: "favorites", updatedAt: "昨天" },
];

export const DEFAULT_SQL = `SELECT name, coords, rating
FROM shops
WHERE city = 'Northampton'
ORDER BY rating DESC`;

export const MOCK_RESULT: QueryResult = {
  columns: [
    { name: "name", type: "string" },
    { name: "coords", type: "coords" },
    { name: "rating", type: "number" },
  ],
  rows: [
    { id: "s1", name: "Walter and Sons", coords: "52.21345,-0.94540", rating: 5 },
    { id: "s2", name: "Kuhic, Murphy and Shan", coords: "52.18096,-1.00509", rating: 4 },
    { id: "s3", name: "Hickle - Blick", coords: "52.19575,-0.81793", rating: 5 },
    { id: "s4", name: "Strosin Group", coords: "52.20895,-0.88012", rating: 3 },
    { id: "s5", name: "Hansen LLC", coords: "52.23101,-0.86555", rating: 4 },
  ],
  durationMs: 348,
  cacheHit: true,
};

// 英国中部 bounds（用于地图投影）
export const UK_MID_BOUNDS = { latMin: 52.0, latMax: 52.4, lngMin: -1.2, lngMax: -0.6 };

/* ----------------------------------------------------------------------------
 * 组件
 * ------------------------------------------------------------------------- */
export function AipAnalystPage() {
  const [sql, setSql] = useState(DEFAULT_SQL);
  const [queries] = useState<SavedQuery[]>(MOCK_QUERIES);
  const [activeCategory, setActiveCategory] = useState<QueryCategory | "all">("all");
  const [activeQueryId, setActiveQueryId] = useState<string | null>("q1");
  const [result, setResult] = useState<QueryResult | null>(MOCK_RESULT);
  const [resultTab, setResultTab] = useState<ResultTab>("table");
  const [chartType, setChartType] = useState<ChartType>("bar");
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 10;

  const filteredQueries = useMemo(
    () => (activeCategory === "all" ? queries : queries.filter((q) => q.category === activeCategory)),
    [queries, activeCategory],
  );

  const processedRows = useMemo(() => {
    let rows = result?.rows ?? [];
    if (filter) rows = filterRows(rows, filter);
    if (sortCol) rows = sortRows(rows, sortCol, sortDir);
    return rows;
  }, [result, filter, sortCol, sortDir]);

  const pagedRows = useMemo(
    () => paginate(processedRows, page, pageSize),
    [processedRows, page],
  );
  const pages = totalPages(processedRows.length, pageSize);

  const markers = useMemo(() => {
    if (!result) return [];
    return rowsToMarkers(result.rows, "coords", "name");
  }, [result]);

  function runQuery() {
    if (!isSelectQuery(sql)) return;
    // 模拟执行：直接使用 mock 结果
    setResult({ ...MOCK_RESULT, durationMs: Math.round(200 + Math.random() * 400), cacheHit: Math.random() > 0.5 });
    setPage(1);
  }

  function selectQuery(q: SavedQuery) {
    setSql(q.sql);
    setActiveQueryId(q.id);
  }

  function toggleSort(col: string) {
    if (sortCol === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortCol(col);
      setSortDir("asc");
    }
  }

  return (
    <PageChrome title="AIP 分析师" lede="SQL 查询 · 图表 · 地理可视化 · 原始数据">
      <div
        data-testid="analyst-root"
        style={{
          display: "flex",
          flexDirection: "column",
          height: "calc(100vh - 160px)",
          minHeight: 520,
        }}
      >
        <div style={{ flex: 1, display: "flex", overflow: "hidden", minHeight: 0 }}>
          {/* 左栏：SQL 查询树 */}
          <aside
            data-testid="left-panel"
            style={{
              width: 220,
              flexShrink: 0,
              borderRight: "1px solid var(--aos-border)",
              background: "#fff",
              overflow: "auto",
              display: "flex",
              flexDirection: "column",
            }}
          >
            <div style={{ padding: 10, borderBottom: "1px solid #F3F4F6", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: "var(--aos-text)" }}>查询</span>
              <button
                type="button"
                data-testid="btn-new-query"
                title="新建查询"
                style={iconBtn}
              >
                +
              </button>
            </div>
            {/* 分类筛选 */}
            <div style={{ display: "flex", gap: 2, padding: 6 }}>
              {(["all", "favorites", "history", "recent"] as const).map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setActiveCategory(c)}
                  data-testid={`cat-${c}`}
                  style={{
                    flex: 1,
                    padding: "3px 4px",
                    fontSize: 11,
                    borderRadius: 4,
                    border: "none",
                    background: activeCategory === c ? "#EEF2FF" : "transparent",
                    color: activeCategory === c ? "var(--aos-indigo)" : "var(--aos-muted)",
                    cursor: "pointer",
                  }}
                >
                  {c === "all" ? "全部" : c === "favorites" ? "收藏" : c === "history" ? "历史" : "最近"}
                </button>
              ))}
            </div>
            {/* 查询列表 */}
            <div style={{ flex: 1, overflow: "auto", padding: "0 6px" }}>
              {filteredQueries.map((q) => (
                <button
                  key={q.id}
                  type="button"
                  onClick={() => selectQuery(q)}
                  data-testid={`query-${q.id}`}
                  style={{
                    width: "100%",
                    textAlign: "left",
                    padding: "8px 10px",
                    marginBottom: 2,
                    borderRadius: 6,
                    border: "none",
                    background: activeQueryId === q.id ? "#F3F4F6" : "transparent",
                    cursor: "pointer",
                  }}
                >
                  <div style={{ fontSize: 12, fontWeight: 500, color: "var(--aos-text)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {q.name}
                  </div>
                  <div style={{ fontSize: 10, color: "var(--aos-muted)" }}>{q.updatedAt}</div>
                </button>
              ))}
            </div>
          </aside>

          {/* 中栏：SQL 编辑器 */}
          <div
            data-testid="middle-panel"
            style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, background: "#FAFAFA" }}
          >
            {/* 编辑器工具栏 */}
            <div style={{ padding: "6px 10px", borderBottom: "1px solid var(--aos-border)", background: "#fff", display: "flex", gap: 6, alignItems: "center" }}>
              <button type="button" onClick={runQuery} data-testid="btn-run" style={btnPrimary}>▶ 运行</button>
              <button
                type="button"
                onClick={() => setSql((s) => formatSql(s))}
                data-testid="btn-format"
                style={btnSecondary}
              >
                格式化
              </button>
              <button type="button" data-testid="btn-save" style={btnSecondary}>保存</button>
              <div style={{ flex: 1 }} />
              <BpBadge variant="info" size="sm">SQL</BpBadge>
            </div>
            {/* SQL 编辑区（textarea 模拟） */}
            <textarea
              value={sql}
              onChange={(e) => setSql(e.target.value)}
              data-testid="sql-editor"
              spellCheck={false}
              style={{
                flex: 1,
                border: "none",
                outline: "none",
                padding: 12,
                fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                fontSize: 13,
                lineHeight: 1.6,
                background: "#0D1117",
                color: "#C9D1D9",
                resize: "none",
                minHeight: 0,
              }}
            />
            {/* 参数 + 执行计划 */}
            <div style={{ padding: "8px 10px", borderTop: "1px solid var(--aos-border)", background: "#fff", display: "flex", gap: 12, fontSize: 11, color: "var(--aos-muted)" }}>
              <div>
                <strong>表：</strong>{extractTable(sql) || "—"}
              </div>
              <div>
                <strong>列：</strong>{extractColumns(sql).join(", ") || "—"}
              </div>
              <div>
                <strong>WHERE：</strong>{extractWhere(sql) || "无"}
              </div>
            </div>
          </div>

          {/* 右栏：结果 / 地图 */}
          <aside
            data-testid="right-panel"
            style={{
              width: 380,
              flexShrink: 0,
              borderLeft: "1px solid var(--aos-border)",
              background: "#fff",
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
            }}
          >
            {/* 结果 Tab */}
            <div style={{ display: "flex", borderBottom: "1px solid var(--aos-border)" }}>
              {(["table", "chart", "map", "raw"] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setResultTab(t)}
                  data-testid={`result-tab-${t}`}
                  style={{
                    flex: 1,
                    padding: "8px 0",
                    fontSize: 12,
                    fontWeight: resultTab === t ? 500 : 400,
                    border: "none",
                    borderBottom: resultTab === t ? "2px solid var(--aos-indigo)" : "2px solid transparent",
                    background: "none",
                    color: resultTab === t ? "var(--aos-indigo)" : "var(--aos-muted)",
                    cursor: "pointer",
                    textTransform: "capitalize",
                  }}
                >
                  {t}
                </button>
              ))}
            </div>

            {/* 结果内容 */}
            <div style={{ flex: 1, overflow: "auto", padding: 8 }}>
              {!result ? (
                <div style={{ textAlign: "center", padding: 40, color: "var(--aos-muted)", fontSize: 12 }}>
                  点击运行查看结果
                </div>
              ) : resultTab === "table" ? (
                <ResultTable
                  columns={result.columns}
                  rows={pagedRows}
                  sortCol={sortCol}
                  sortDir={sortDir}
                  onSort={toggleSort}
                  filter={filter}
                  onFilter={setFilter}
                />
              ) : resultTab === "chart" ? (
                <ChartView type={chartType} onChange={setChartType} result={result} />
              ) : resultTab === "map" ? (
                <MapView markers={markers} />
              ) : (
                <RawView result={result} />
              )}
            </div>

            {/* 分页 */}
            {resultTab === "table" && result && (
              <div style={{ padding: "6px 10px", borderTop: "1px solid var(--aos-border)", display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 11, color: "var(--aos-muted)" }}>
                <span>第 {page} / {pages} 页</span>
                <div style={{ display: "flex", gap: 4 }}>
                  <button type="button" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1} data-testid="page-prev" style={{ ...btnXS, opacity: page <= 1 ? 0.4 : 1 }}>
                    上一页
                  </button>
                  <button type="button" onClick={() => setPage((p) => Math.min(pages, p + 1))} disabled={page >= pages} data-testid="page-next" style={{ ...btnXS, opacity: page >= pages ? 0.4 : 1 }}>
                    下一页
                  </button>
                </div>
              </div>
            )}
          </aside>
        </div>

        {/* 底部状态栏 */}
        <StatusBar result={result} total={processedRows.length} />
      </div>
    </PageChrome>
  );
}

/* ----------------------------------------------------------------------------
 * 子组件：结果表格
 * ------------------------------------------------------------------------- */
function ResultTable(props: {
  columns: ResultColumn[];
  rows: ResultRow[];
  sortCol: string | null;
  sortDir: "asc" | "desc";
  onSort: (col: string) => void;
  filter: string;
  onFilter: (q: string) => void;
}) {
  return (
    <div data-testid="result-table">
      <input
        type="text"
        value={props.filter}
        onChange={(e) => props.onFilter(e.target.value)}
        placeholder="过滤行..."
        data-testid="row-filter"
        style={{
          width: "100%",
          padding: "6px 8px",
          fontSize: 12,
          border: "1px solid var(--aos-border)",
          borderRadius: 4,
          outline: "none",
          marginBottom: 8,
        }}
      />
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
        <thead>
          <tr>
            {props.columns.map((c) => (
              <th
                key={c.name}
                onClick={() => props.onSort(c.name)}
                data-testid={`th-${c.name}`}
                style={{
                  ...thStyle,
                  cursor: "pointer",
                  userSelect: "none",
                }}
              >
                {c.name}
                {props.sortCol === c.name && (props.sortDir === "asc" ? " ▲" : " ▼")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {props.rows.map((r, i) => (
            <tr key={i} data-testid={`row-${i}`}>
              {props.columns.map((c) => (
                <td
                  key={c.name}
                  style={{
                    ...tdStyle,
                    fontFamily: c.type === "coords" ? "monospace" : undefined,
                    color: c.type === "number" ? "#0891B2" : undefined,
                  }}
                >
                  {String(r[c.name] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ----------------------------------------------------------------------------
 * 子组件：图表视图
 * ------------------------------------------------------------------------- */
function ChartView(props: {
  type: ChartType;
  onChange: (t: ChartType) => void;
  result: QueryResult;
}) {
  const numCol = props.result.columns.find((c) => c.type === "number")?.name ?? "rating";
  const values = columnToNumbers(props.result.rows, numCol);
  const types: ChartType[] = ["bar", "line", "pie"];
  return (
    <div data-testid="chart-view">
      <div style={{ display: "flex", gap: 4, marginBottom: 12 }}>
        {types.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => props.onChange(t)}
            data-testid={`chart-type-${t}`}
            style={{
              padding: "4px 10px",
              fontSize: 11,
              borderRadius: 4,
              border: props.type === t ? "1px solid var(--aos-indigo)" : "1px solid var(--aos-border)",
              background: props.type === t ? "#EEF2FF" : "#fff",
              color: props.type === t ? "var(--aos-indigo)" : "var(--aos-muted)",
              cursor: "pointer",
            }}
          >
            {t === "bar" ? "柱状图" : t === "line" ? "折线图" : "饼图"}
          </button>
        ))}
      </div>
      <div style={{ fontSize: 11, color: "var(--aos-muted)", marginBottom: 8 }}>
        数据列：{numCol}
      </div>
      {props.type === "bar" && (
        <div style={{ display: "flex", alignItems: "flex-end", gap: 4, height: 120 }}>
          {normalizeBars(values).map((h, i) => (
            <div
              key={i}
              data-testid={`bar-${i}`}
              style={{ flex: 1, height: `${h}%`, background: "linear-gradient(180deg, #818CF8, #6366F1)", borderRadius: 3 }}
            />
          ))}
        </div>
      )}
      {props.type === "line" && (
        <svg viewBox="0 0 200 60" width="100%" height={60} data-testid="line-svg">
          <path d={linePath(values)} fill="none" stroke="#6366F1" strokeWidth={1.5} />
        </svg>
      )}
      {props.type === "pie" && (
        <div data-testid="pie-view">
          <PieChart slices={toPieSlices(values)} />
          <ul style={{ margin: "8px 0 0", paddingLeft: 16, fontSize: 11 }}>
            {toPieSlices(values).map((s, i) => (
              <li key={i} style={{ color: s.color }}>
                {props.result.rows[i]?.name ?? `#${i}`}：{s.percent.toFixed(1)}%
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function PieChart(props: { slices: { value: number; percent: number; color: string }[] }) {
  let acc = 0;
  const r = 30;
  const cx = 40;
  const cy = 40;
  const toXY = (deg: number) => {
    const rad = (deg - 90) * (Math.PI / 180);
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  };
  return (
    <svg viewBox="0 0 80 80" width={120} height={120}>
      {props.slices.map((s, i) => {
        const start = (acc / (props.slices.reduce((a, b) => a + b.value, 0) || 1)) * 360;
        acc += s.value;
        const end = (acc / (props.slices.reduce((a, b) => a + b.value, 0) || 1)) * 360;
        const large = end - start > 180 ? 1 : 0;
        const a = toXY(start);
        const b = toXY(end);
        return (
          <path
            key={i}
            d={`M${cx},${cy} L${a.x},${a.y} A${r},${r} 0 ${large} 1 ${b.x},${b.y} Z`}
            fill={s.color}
          />
        );
      })}
    </svg>
  );
}

/* ----------------------------------------------------------------------------
 * 子组件：地图视图
 * ------------------------------------------------------------------------- */
function MapView(props: { markers: MapMarker[] }) {
  return (
    <div data-testid="map-view">
      <div
        style={{
          height: 260,
          background: "linear-gradient(135deg, #E0F2FE 0%, #F0FDF4 100%)",
          position: "relative",
          borderRadius: 8,
          overflow: "hidden",
        }}
      >
        <svg viewBox="0 0 100 100" width="100%" height="100%" preserveAspectRatio="none">
          {props.markers.map((m) => {
            const p = projectToMap(m.lat, m.lng, UK_MID_BOUNDS);
            return (
              <g key={m.id} data-testid={`marker-${m.id}`}>
                <circle cx={p.x} cy={p.y} r={Math.max(1, m.intensity)} fill="#F97316" fillOpacity={0.7} />
                <text x={p.x} y={p.y - 2} fontSize={2} fill="#374151" textAnchor="middle">
                  {m.name.slice(0, 8)}
                </text>
              </g>
            );
          })}
        </svg>
        <div style={{ position: "absolute", bottom: 4, left: 6, fontSize: 9, color: "#9CA3AF" }}>
          © Mapbox © OSM
        </div>
      </div>
      <div style={{ marginTop: 8, fontSize: 11, color: "var(--aos-muted)" }}>
        {props.markers.length} 个标记 · 热力半径由 rating 决定
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------------------
 * 子组件：原始 JSON 视图
 * ------------------------------------------------------------------------- */
function RawView(props: { result: QueryResult }) {
  return (
    <pre
      data-testid="raw-view"
      style={{
        margin: 0,
        padding: 8,
        background: "#0D1117",
        color: "#C9D1D9",
        borderRadius: 6,
        fontSize: 11,
        fontFamily: "ui-monospace, monospace",
        overflow: "auto",
        maxHeight: 400,
      }}
    >
      {JSON.stringify({ columns: props.result.columns, rows: props.result.rows }, null, 2)}
    </pre>
  );
}

/* ----------------------------------------------------------------------------
 * 子组件：底部状态栏
 * ------------------------------------------------------------------------- */
function StatusBar(props: { result: QueryResult | null; total: number }) {
  return (
    <div
      data-testid="status-bar"
      style={{
        borderTop: "1px solid var(--aos-border)",
        background: "#F9FAFB",
        padding: "6px 12px",
        display: "flex",
        alignItems: "center",
        gap: 16,
        fontSize: 11,
        color: "var(--aos-muted)",
        flexShrink: 0,
      }}
    >
      {props.result ? (
        <>
          <span>{props.total} 行</span>
          <span>·</span>
          <span>{formatDurationMs(props.result.durationMs)}</span>
          <span>·</span>
          <span data-testid="cache-hit">
            {props.result.cacheHit ? "缓存命中" : "未命中缓存"}
          </span>
          <div style={{ flex: 1 }} />
          <button type="button" data-testid="btn-export-csv" style={btnXS}>
            导出 CSV
          </button>
          <button type="button" data-testid="btn-export-json" style={btnXS}>
            导出 JSON
          </button>
        </>
      ) : (
        <span>未运行查询</span>
      )}
    </div>
  );
}

function formatDurationMs(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)}s`;
  return `${Math.round(ms)}ms`;
}

/* ----------------------------------------------------------------------------
 * 共享 style 常量
 * ------------------------------------------------------------------------- */
const btnPrimary: React.CSSProperties = {
  padding: "5px 12px",
  fontSize: 12,
  fontWeight: 500,
  color: "#fff",
  background: "var(--aos-indigo)",
  border: "none",
  borderRadius: 6,
  cursor: "pointer",
};

const btnSecondary: React.CSSProperties = {
  padding: "5px 12px",
  fontSize: 12,
  color: "var(--aos-text)",
  background: "#fff",
  border: "1px solid var(--aos-border)",
  borderRadius: 6,
  cursor: "pointer",
};

const btnXS: React.CSSProperties = {
  padding: "3px 8px",
  fontSize: 11,
  color: "var(--aos-indigo)",
  background: "#EEF2FF",
  border: "none",
  borderRadius: 4,
  cursor: "pointer",
};

const iconBtn: React.CSSProperties = {
  width: 22,
  height: 22,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: 14,
  color: "var(--aos-indigo)",
  background: "#EEF2FF",
  border: "none",
  borderRadius: 4,
  cursor: "pointer",
};

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "6px 8px",
  background: "#F9FAFB",
  borderBottom: "1px solid var(--aos-border)",
  fontWeight: 500,
  color: "var(--aos-muted)",
  fontSize: 11,
};

const tdStyle: React.CSSProperties = {
  padding: "6px 8px",
  borderBottom: "1px solid #F3F4F6",
  color: "var(--aos-text)",
  fontSize: 12,
};
