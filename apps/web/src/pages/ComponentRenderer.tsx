/**
 * 动态渲染引擎 · 根据 module.components 组件树渲染运行态页面
 *
 * 支持的组件类型：
 *   - page-layout        页面布局容器
 *   - page-header        页面标题栏
 *   - horizontal-grid    水平栅格布局
 *   - stat-card          统计卡片（支持真实 objectType 查询）
 *   - filter-bar         筛选栏（tabs + search + filters）
 *   - object-table       对象表格（真实 API 查询）
 *   - detail-drawer      详情抽屉
 *
 * 数据来源：调用 /v1/objects/{objectType} 或 /v1/object-sets/query
 */
import { useEffect, useState, type ReactNode } from "react";
import { apiGet, apiPost } from "../api/client";
import { getWidgetPlugin } from "./widgets";

// ── Types ───────────────────────────────────────────────────────────────────

export type ComponentNode = {
  type: string;
  config?: Record<string, any>;
  children?: string[];
};

export type ComponentTree = Record<string, ComponentNode>;

type RuntimeObject = {
  id?: string;
  objectId?: string;
  title?: string;
  status?: string;
  site?: string;
  props?: Record<string, unknown>;
  [key: string]: unknown;
};

type QueryResponse = {
  items?: RuntimeObject[];
  objects?: RuntimeObject[];
  total?: number;
};

// ── Main Renderer ───────────────────────────────────────────────────────────

export function ComponentRenderer({
  components,
  rootId = "root",
}: {
  components: ComponentTree;
  rootId?: string;
}) {
  const root = components[rootId];
  if (!root) {
    return (
      <div style={{ padding: 24, color: "var(--aos-text-muted)", textAlign: "center" }}>
        组件树缺少 root 节点
      </div>
    );
  }
  return <RenderNode node={root} components={components} depth={0} />;
}

function RenderNode({
  node,
  components,
  depth,
}: {
  node: ComponentNode;
  components: ComponentTree;
  depth: number;
}) {
  const children = (node.children || [])
    .map((id) => components[id])
    .filter((c): c is ComponentNode => !!c);

  switch (node.type) {
    case "page-layout": {
      const childIds = node.children || [];
      const pair = detectTableDrawerPairByIds(components, childIds);
      if (pair) {
        const tableNode = components[pair.tableId];
        const drawerNode = components[pair.drawerId];
        const beforeNodes = pair.beforeIds
          .map((id) => components[id])
          .filter((c): c is ComponentNode => !!c);
        const afterNodes = pair.afterIds
          .map((id) => components[id])
          .filter((c): c is ComponentNode => !!c);
        return (
          <div
            style={{
              padding: node.config?.padding ?? 24,
              display: "flex",
              flexDirection: "column",
              gap: node.config?.gap ?? 16,
            }}
          >
            {beforeNodes.map((c, i) => (
              <RenderNode key={`b-${i}`} node={c} components={components} depth={depth + 1} />
            ))}
            <TableWithDrawerLayout
              tableNode={tableNode}
              drawerNode={drawerNode}
            />
            {afterNodes.map((c, i) => (
              <RenderNode key={`a-${i}`} node={c} components={components} depth={depth + 1} />
            ))}
          </div>
        );
      }
      return (
        <div
          style={{
            padding: node.config?.padding ?? 24,
            display: "flex",
            flexDirection: "column",
            gap: node.config?.gap ?? 16,
          }}
        >
          {children.map((c, i) => (
            <RenderNode key={i} node={c} components={components} depth={depth + 1} />
          ))}
        </div>
      );
    }

    case "page-header":
      return <PageHeader config={node.config || {}} />;

    case "horizontal-grid":
      return (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: `repeat(${node.config?.cols ?? 4}, 1fr)`,
            gap: node.config?.gap ?? 16,
          }}
        >
          {children.map((c, i) => (
            <RenderNode key={i} node={c} components={components} depth={depth + 1} />
          ))}
        </div>
      );

    case "stat-card":
      return <StatCardWidget config={node.config || {}} />;

    case "filter-bar":
      return <FilterBarWidget config={node.config || {}} />;

    case "object-table":
      return <ObjectTableWidget config={node.config || {}} />;

    case "detail-drawer":
      return <DetailDrawerWidget config={node.config || {}} />;

    case "trend-chart":
      return <TrendChartWidget config={node.config || {}} />;

    default: {
      // 从 WidgetPluginRegistry 找插件渲染
      const plugin = getWidgetPlugin(node.type);
      if (plugin) {
        const childElements = children.map((c, i) => (
          <RenderNode key={i} node={c} components={components} depth={depth + 1} />
        ));
        return (
          <>{plugin.render(node.config || {}, { components, depth }, childElements)}</>
        );
      }
      return (
        <div
          style={{
            padding: 12,
            border: "1px dashed var(--aos-border)",
            borderRadius: 2,
            color: "var(--aos-text-muted)",
            fontSize: 12,
          }}
        >
          未知组件类型: <code>{node.type}</code>
        </div>
      );
    }
  }
}

// ── Sub-renderers ───────────────────────────────────────────────────────────

export function PageHeader({ config }: { config: Record<string, any> }) {
  return (
    <header
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "8px 0",
        borderBottom: "1px solid var(--aos-border)",
      }}
    >
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0, color: "var(--aos-text)" }}>
          {config.title || "未命名页面"}
        </h1>
        {config.subtitle && (
          <p style={{ fontSize: 12, color: "var(--aos-text-muted)", margin: "4px 0 0" }}>
            {config.subtitle}
          </p>
        )}
      </div>
      {Array.isArray(config.actions) && (
        <div style={{ display: "flex", gap: 8 }}>
          {config.actions.map((a: any, i: number) => (
            <button
              key={i}
              type="button"
              style={{
                padding: "6px 14px",
                fontSize: 12,
                borderRadius: 4,
                cursor: "pointer",
                border: a.variant === "primary" ? "none" : "1px solid var(--aos-border)",
                background:
                  a.variant === "primary"
                    ? "var(--aos-accent, #4f46e5)"
                    : "var(--aos-surface)",
                color: a.variant === "primary" ? "#fff" : "var(--aos-text)",
              }}
            >
              {a.label}
            </button>
          ))}
        </div>
      )}
    </header>
  );
}

export function StatCardWidget({ config }: { config: Record<string, any> }) {
  const [value, setValue] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const objectType = config.objectType;

  useEffect(() => {
    if (!objectType) {
      setValue(config.value ?? "—");
      return;
    }
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const filters: any[] = [];
        if (config.filter) {
          filters.push({
            field: config.filter.field,
            op: config.filter.op || "eq",
            value: config.filter.value,
          });
        }
        const res = await apiPost<QueryResponse>("/v1/object-sets/query", {
          objectType,
          filters,
          pageSize: 500,
        });
        if (cancelled) return;
        const items = res.items || res.objects || [];
        const total = res.total ?? items.length;
        if (config.metric === "sum" && config.field) {
          const sum = items.reduce((acc, it) => {
            const v = (it.props?.[config.field] as number) ?? (it[config.field] as number) ?? 0;
            return acc + Number(v);
          }, 0);
          setValue(formatCurrency(sum));
        } else {
          setValue(formatNumber(total));
        }
      } catch {
        if (!cancelled) setValue(config.value ?? "—");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [objectType, config.field, config.metric, JSON.stringify(config.filter)]);

  const colorMap: Record<string, string> = {
    blue: "#3B82F6",
    amber: "#F59E0B",
    green: "#10B981",
    indigo: "#6366F1",
    violet: "#8B5CF6",
  };
  const color = colorMap[config.color] || "#3B82F6";

  return (
    <div
      style={{
        padding: 16,
        borderRadius: 2,
        border: "1px solid var(--aos-border)",
        background: "var(--aos-surface)",
        display: "flex",
        flexDirection: "column",
        gap: 4,
      }}
    >
      <div style={{ fontSize: 11, color: "var(--aos-text-muted)" }}>{config.title}</div>
      <div style={{ fontSize: 26, fontWeight: 700, color }}>
        {loading ? "..." : value ?? "—"}
      </div>
      {config.sublabel && (
        <div style={{ fontSize: 11, color: "var(--aos-text-muted)" }}>{config.sublabel}</div>
      )}
      {config.trend && (
        <div
          style={{
            fontSize: 11,
            color: config.trendUp ? "#10B981" : "#EF4444",
          }}
        >
          {config.trendUp ? "↑" : "↓"} {config.trend}
        </div>
      )}
    </div>
  );
}

export function FilterBarWidget({ config }: { config: Record<string, any> }) {
  const [activeTab, setActiveTab] = useState("all");
  const [search, setSearch] = useState("");
  const tabs: any[] = config.tabs || [];

  return (
    <div
      style={{
        padding: "8px 12px",
        borderRadius: 2,
        border: "1px solid var(--aos-border)",
        background: "var(--aos-surface)",
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setActiveTab(t.key)}
            style={{
              padding: "4px 10px",
              fontSize: 11,
              borderRadius: 4,
              cursor: "pointer",
              border:
                activeTab === t.key
                  ? "1px solid var(--aos-accent, #4f46e5)"
                  : "1px solid var(--aos-border)",
              background:
                activeTab === t.key
                  ? "var(--aos-accent, #4f46e5)"
                  : "var(--aos-surface)",
              color: activeTab === t.key ? "#fff" : "var(--aos-text)",
            }}
          >
            {t.label}
            {typeof t.count === "number" ? ` (${t.count})` : ""}
          </button>
        ))}
      </div>
      <input
        type="search"
        placeholder={config.search?.placeholder || "搜索..."}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        style={{
          width: "100%",
          padding: "6px 10px",
          fontSize: 12,
          border: "1px solid var(--aos-border)",
          borderRadius: 4,
          background: "var(--aos-aside)",
          color: "var(--aos-text)",
          boxSizing: "border-box",
        }}
      />
    </div>
  );
}

export function ObjectTableWidget({
  config,
  externalSelected,
  onSelectRow,
}: {
  config: Record<string, any>;
  externalSelected?: RuntimeObject | null;
  onSelectRow?: (row: RuntimeObject | null) => void;
}) {
  const [rows, setRows] = useState<RuntimeObject[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [internalSelected, setInternalSelected] = useState<RuntimeObject | null>(null);
  const selected = externalSelected !== undefined ? externalSelected : internalSelected;
  const objectType = config.objectType;
  const columns: any[] = config.columns || [];

  const handleSelect = (row: RuntimeObject | null) => {
    if (onSelectRow) {
      onSelectRow(row);
    } else {
      setInternalSelected(row);
    }
  };

  useEffect(() => {
    if (!objectType) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    apiGet<QueryResponse>(`/v1/objects/${encodeURIComponent(objectType)}`)
      .then((res) => {
        if (cancelled) return;
        setRows(res.items || res.objects || []);
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
  }, [objectType]);

  const cellValue = (row: RuntimeObject, key: string) => {
    if (row.props && key in row.props) return (row.props as Record<string, unknown>)[key];
    if (key in row) return row[key];
    return undefined;
  };

  const formatCell = (v: unknown, col: any): ReactNode => {
    if (v === undefined || v === null || v === "") return <span style={{ color: "var(--aos-text-muted)" }}>—</span>;
    if (col.format === "currency") {
      const n = Number(v);
      return Number.isFinite(n) ? `¥${n.toLocaleString()}` : String(v);
    }
    return String(v);
  };

  return (
    <div
      style={{
        borderRadius: 2,
        border: "1px solid var(--aos-border)",
        background: "var(--aos-surface)",
        overflow: "hidden",
      }}
    >
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ background: "var(--aos-aside)" }}>
              {columns.map((c) => (
                <th
                  key={c.key}
                  style={{
                    textAlign: c.align || "left",
                    padding: "8px 12px",
                    fontWeight: 600,
                    color: "var(--aos-text)",
                    borderBottom: "1px solid var(--aos-border)",
                    width: c.width,
                  }}
                >
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td
                  colSpan={columns.length || 1}
                  style={{ padding: 24, textAlign: "center", color: "var(--aos-text-muted)" }}
                >
                  加载中...
                </td>
              </tr>
            )}
            {error && (
              <tr>
                <td
                  colSpan={columns.length || 1}
                  style={{ padding: 24, textAlign: "center", color: "#EF4444" }}
                >
                  加载失败: {error}
                </td>
              </tr>
            )}
            {!loading && !error && rows.length === 0 && (
              <tr>
                <td
                  colSpan={columns.length || 1}
                  style={{ padding: 24, textAlign: "center", color: "var(--aos-text-muted)" }}
                >
                  无数据
                </td>
              </tr>
            )}
            {!loading &&
              !error &&
              rows.slice(0, config.pagination?.pageSize ?? 20).map((row, idx) => {
                const id = String(row.id || row.objectId || `row-${idx}`);
                const isSel = selected?.id === row.id;
                return (
                  <tr
                    key={id}
                    onClick={() => handleSelect(row)}
                    style={{
                      cursor: "pointer",
                      background: isSel ? "rgba(79,70,229,0.08)" : undefined,
                      borderBottom: "1px solid var(--aos-border-light, var(--aos-border))",
                    }}
                  >
                    {columns.map((c) => {
                      const raw = cellValue(row, c.key);
                      if (c.type === "status") {
                        return (
                          <td
                            key={c.key}
                            style={{ padding: "8px 12px", textAlign: c.align || "left" }}
                          >
                            <StatusBadge value={String(raw ?? "")} />
                          </td>
                        );
                      }
                      return (
                        <td
                          key={c.key}
                          style={{
                            padding: "8px 12px",
                            textAlign: c.align || "left",
                            color: "var(--aos-text)",
                            fontFamily: c.mono ? "monospace" : undefined,
                          }}
                        >
                          {formatCell(raw, c)}
                          {c.subKey && cellValue(row, c.subKey) !== undefined && (
                            <span style={{ fontSize: 10, color: "var(--aos-text-muted)", marginLeft: 6 }}>
                              {String(cellValue(row, c.subKey))}
                            </span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>

      {selected && config.rowActions && (
        <div
          style={{
            padding: "8px 12px",
            borderTop: "1px solid var(--aos-border)",
            display: "flex",
            gap: 8,
            background: "var(--aos-aside)",
            fontSize: 11,
            color: "var(--aos-text-muted)",
          }}
        >
          <span>已选中: {String(selected.id || selected.objectId)}</span>
          {(config.rowActions as any[]).map((a) => (
            <button
              key={a.key}
              type="button"
              style={{
                padding: "3px 8px",
                fontSize: 11,
                cursor: "pointer",
                border: "1px solid var(--aos-border)",
                borderRadius: 3,
                background: "var(--aos-surface)",
                color: "var(--aos-text)",
              }}
            >
              {a.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function DetailDrawerWidget({ config, external }: { config: Record<string, any>; external?: RuntimeObject | null }) {
  const sections: any[] = config.sections || [];
  const [internalSelected, setInternalSelected] = useState<RuntimeObject | null>(null);
  const objectType = config.objectType;
  const selected = external !== undefined ? external : internalSelected;

  useEffect(() => {
    if (external !== undefined || !objectType) return;
    let cancelled = false;
    apiGet<QueryResponse>(`/v1/objects/${encodeURIComponent(objectType)}`)
      .then((res) => {
        if (cancelled) return;
        const items = res.items || res.objects || [];
        if (items.length > 0) setInternalSelected(items[0]);
      })
      .catch(() => {
        /* drawer 是预览，加载失败不报错 */
      });
    return () => {
      cancelled = true;
    };
  }, [objectType, external]);

  const renderField = (field: any) => {
    if (!selected) return "—";
    const raw = (selected as Record<string, unknown>)[field.key];
    if (raw === undefined || raw === null || raw === "") return "—";
    if (field.type === "status") return <StatusBadge value={String(raw)} />;
    if (field.format === "currency") {
      const n = Number(raw);
      return Number.isFinite(n) ? `¥${n.toLocaleString()}` : String(raw);
    }
    return String(raw);
  };

  return (
    <div
      style={{
        borderRadius: 2,
        border: "1px solid var(--aos-border)",
        background: "var(--aos-aside)",
        padding: 12,
        fontSize: 12,
        height: "100%",
        boxSizing: "border-box",
      }}
    >
      <div
        style={{
          fontWeight: 600,
          marginBottom: 8,
          color: "var(--aos-text)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <span>详情抽屉 · {objectType || "—"}</span>
        <span style={{ fontSize: 10, fontWeight: 400, color: "var(--aos-text-muted)" }}>
          {selected ? `当前: ${String(selected.id ?? "")}` : "点击表格行"}
        </span>
      </div>

      {!selected ? (
        <div style={{ padding: 16, textAlign: "center", color: "var(--aos-text-muted)", fontSize: 11 }}>
          请点击表格中的订单查看详情
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {sections.map((s, i) => (
            <div
              key={i}
              style={{
                padding: 8,
                background: "var(--aos-surface)",
                borderRadius: 4,
                border: "1px solid var(--aos-border-light, var(--aos-border))",
              }}
            >
              <div style={{ fontSize: 11, fontWeight: 600, marginBottom: 6, color: "var(--aos-text)" }}>{s.title}</div>
              {s.type === "table" ? (
                <ItemsTable
                  rows={(selected?.[s.objectKey || "items"] as any[]) || []}
                  columns={s.columns || []}
                />
              ) : (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px 12px", fontSize: 11 }}>
                  {(s.fields || []).map((f: any) => (
                    <div key={f.key} style={{ display: "flex", gap: 6 }}>
                      <span style={{ color: "var(--aos-text-muted)", minWidth: 60 }}>{f.label}:</span>
                      <span
                        style={{
                          color: "var(--aos-text)",
                          fontFamily: f.mono ? "monospace" : undefined,
                        }}
                      >
                        {renderField(f)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {Array.isArray(config.actions) && (
        <div style={{ marginTop: 10, display: "flex", gap: 6 }}>
          {config.actions.map((a: any, i: number) => (
            <button
              key={i}
              type="button"
              style={{
                padding: "4px 10px",
                fontSize: 11,
                borderRadius: 4,
                cursor: "pointer",
                border: a.variant === "primary" ? "none" : "1px solid var(--aos-border)",
                background:
                  a.variant === "primary"
                    ? "var(--aos-accent, #4f46e5)"
                    : "var(--aos-surface)",
                color: a.variant === "primary" ? "#fff" : "var(--aos-text)",
              }}
            >
              {a.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function TableWithDrawerLayout({
  tableNode,
  drawerNode,
}: {
  tableNode: ComponentNode;
  drawerNode: ComponentNode;
}) {
  const [selected, setSelected] = useState<RuntimeObject | null>(null);
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: selected ? "1fr 320px" : "1fr",
        gap: 12,
        alignItems: "start",
      }}
    >
      <ObjectTableWidget
        config={tableNode.config || {}}
        externalSelected={selected}
        onSelectRow={setSelected}
      />
      {selected && (
        <DetailDrawerWidget config={drawerNode.config || {}} external={selected} />
      )}
    </div>
  );
}

function ItemsTable({ rows, columns }: { rows: any[]; columns: any[] }) {
  if (!rows.length) {
    return <div style={{ fontSize: 11, color: "var(--aos-text-muted)", padding: 4 }}>无明细</div>;
  }
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
      <thead>
        <tr>
          {columns.map((c: any) => (
            <th
              key={c.key}
              style={{ textAlign: c.align || "left", padding: "4px 6px", color: "var(--aos-text-muted)", fontWeight: 500 }}
            >
              {c.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            {columns.map((c: any) => {
              const v = r[c.key];
              if (c.format === "currency") {
                const n = Number(v);
                return (
                  <td key={c.key} style={{ padding: "4px 6px", color: "var(--aos-text)" }}>
                    {Number.isFinite(n) ? `¥${n.toLocaleString()}` : String(v ?? "—")}
                  </td>
                );
              }
              return (
                <td key={c.key} style={{ padding: "4px 6px", color: "var(--aos-text)" }}>
                  {String(v ?? "—")}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function TrendChartWidget({ config }: { config: Record<string, any> }) {
  const [data, setData] = useState<{ date: string; count: number }[]>([]);
  const [loading, setLoading] = useState(false);
  const objectType = config.objectType;
  const dateField = config.dateField || "createdAt";
  const days = config.days || 7;

  useEffect(() => {
    if (!objectType) return;
    let cancelled = false;
    setLoading(true);
    apiGet<QueryResponse>(`/v1/objects/${encodeURIComponent(objectType)}`)
      .then((res) => {
        if (cancelled) return;
        const items = res.items || res.objects || [];
        const end = config.endDate ? new Date(config.endDate) : new Date();
        const buckets: { date: string; count: number }[] = [];
        for (let i = days - 1; i >= 0; i--) {
          const d = new Date(end);
          d.setDate(d.getDate() - i);
          const key = d.toISOString().slice(0, 10);
          buckets.push({ date: key.slice(5), count: 0 });
        }
        const idx: Record<string, number> = {};
        buckets.forEach((b, i) => (idx[b.date] = i));
        for (const it of items) {
          let raw = (it as Record<string, unknown>)[dateField];
          if (raw === undefined && (it as Record<string, unknown>).props) {
            raw = ((it as Record<string, unknown>).props as Record<string, unknown>)[dateField];
          }
          if (typeof raw === "string") {
            const day = raw.slice(5, 10);
            if (day in idx) buckets[idx[day]].count += 1;
          }
        }
        setData(buckets);
      })
      .catch(() => {
        if (!cancelled) setData([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [objectType, dateField, days, config.endDate]);

  const hasData = data.length > 0 && data.some((d) => d.count > 0);
  const max = Math.max(1, ...data.map((d) => d.count));
  const W = 520;
  const H = 140;
  const pad = 28;
  const stepX = data.length > 1 ? (W - pad * 2) / (data.length - 1) : 0;
  const points = data
    .map((d, i) => {
      const x = pad + i * stepX;
      const y = H - pad - (d.count / max) * (H - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const areaPath = data.length
    ? `M ${pad},${H - pad} L ${points.split(" ").join(" L ")} L ${pad + (data.length - 1) * stepX},${H - pad} Z`
    : "";

  return (
    <div
      style={{
        borderRadius: 2,
        border: "1px solid var(--aos-border)",
        background: "var(--aos-surface)",
        padding: 12,
      }}
    >
      <div style={{ fontSize: 12, fontWeight: 600, color: "var(--aos-text)", marginBottom: 8 }}>
        {config.title || "近 7 天趋势"}
      </div>
      {loading ? (
        <div style={{ padding: 16, textAlign: "center", color: "var(--aos-text-muted)", fontSize: 11 }}>
          加载中...
        </div>
      ) : data.length === 0 ? (
        <div style={{ padding: 16, textAlign: "center", color: "var(--aos-text-muted)", fontSize: 11 }}>
          暂无数据
        </div>
      ) : !hasData ? (
        <div style={{ padding: 16, textAlign: "center", color: "var(--aos-text-muted)", fontSize: 11 }}>
          暂无趋势数据
        </div>
      ) : (
        <svg width="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet">
          <defs>
            <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3B82F6" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#3B82F6" stopOpacity="0" />
            </linearGradient>
            <filter id="trendShadow" x="-10%" y="-10%" width="120%" height="120%">
              <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor="#3B82F6" floodOpacity="0.25" />
            </filter>
          </defs>
          {[0.25, 0.5, 0.75, 1].map((r) => (
            <line
              key={r}
              x1={pad}
              x2={W - pad}
              y1={H - pad - r * (H - pad * 2)}
              y2={H - pad - r * (H - pad * 2)}
              stroke="var(--aos-border-light, #E5E7EB)"
              strokeWidth="1"
              strokeDasharray="2 3"
            />
          ))}
          {/* 面积填充 */}
          {areaPath && <path d={areaPath} fill="url(#trendFill)" />}
          {/* 折线 */}
          {points && (
            <polyline
              points={points}
              fill="none"
              stroke="#3B82F6"
              strokeWidth="2.5"
              strokeLinejoin="round"
              strokeLinecap="round"
              filter="url(#trendShadow)"
            />
          )}
          {data.map((d, i) => {
            const x = pad + i * stepX;
            const y = H - pad - (d.count / max) * (H - pad * 2);
            return (
              <g key={i}>
                <circle cx={x} cy={y} r="4" fill="#3B82F6" stroke="#fff" strokeWidth="1.5" />
                <text x={x} y={H - pad + 14} textAnchor="middle" fontSize="9" fill="var(--aos-text-muted)">
                  {d.date}
                </text>
                <text x={x} y={y - 10} textAnchor="middle" fontSize="9" fill="var(--aos-text)" fontWeight="600">
                  {d.count}
                </text>
              </g>
            );
          })}
        </svg>
      )}
    </div>
  );
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function StatusBadge({ value }: { value: string }) {
  const map: Record<string, { bg: string; text: string; label: string }> = {
    pending: { bg: "#FEF3C7", text: "#D97706", label: "待处理" },
    paid: { bg: "#DBEAFE", text: "#2563EB", label: "已付款" },
    shipped: { bg: "#FEF3C7", text: "#D97706", label: "已发货" },
    delivered: { bg: "#D1FAE5", text: "#059669", label: "已签收" },
    cancelled: { bg: "#FEE2E2", text: "#DC2626", label: "已取消" },
    refunded: { bg: "#EDE9FE", text: "#7C3AED", label: "已退款" },
    done: { bg: "#D1FAE5", text: "#059669", label: "完成" },
    open: { bg: "#DBEAFE", text: "#2563EB", label: "进行中" },
  };
  const v = (value || "").toLowerCase();
  const cfg = map[v] || { bg: "#F3F4F6", text: "#6B7280", label: value };
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: 4,
        fontSize: 11,
        fontWeight: 500,
        background: cfg.bg,
        color: cfg.text,
      }}
    >
      {cfg.label}
    </span>
  );
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

function formatCurrency(n: number): string {
  if (n >= 1_000_000) return `¥${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `¥${(n / 1_000).toFixed(1)}K`;
  return `¥${n.toLocaleString()}`;
}

// ── Pure helpers (exported for unit testing) ────────────────────────────────

export type TreeAnalysis = {
  totalNodes: number;
  hasRoot: boolean;
  rootType: string | null;
  typeCounts: Record<string, number>;
  orphanChildren: string[];
  cycleDetected: boolean;
};

/** 分析组件树结构 · 用于单元测试与运行时校验 */
export function analyzeComponentTree(
  tree: ComponentTree,
  rootId: string = "root",
): TreeAnalysis {
  const typeCounts: Record<string, number> = {};
  const orphanChildren: string[] = [];
  const allKeys = new Set(Object.keys(tree));
  const visited = new Set<string>();
  const stack = [rootId];
  let cycleDetected = false;

  while (stack.length) {
    const id = stack.pop()!;
    if (visited.has(id)) {
      cycleDetected = true;
      continue;
    }
    visited.add(id);
    const node = tree[id];
    if (!node) continue;
    typeCounts[node.type] = (typeCounts[node.type] || 0) + 1;
    for (const childId of node.children || []) {
      if (!allKeys.has(childId)) orphanChildren.push(childId);
      else stack.push(childId);
    }
  }

  const root = tree[rootId];
  return {
    totalNodes: Object.keys(tree).length,
    hasRoot: !!root,
    rootType: root?.type ?? null,
    typeCounts,
    orphanChildren,
    cycleDetected,
  };
}

/** 把 widgets 字符串数组降级为简单 components 树（兜底） */
export function widgetsToComponents(widgets: string[]): ComponentTree {
  const tree: ComponentTree = {
    root: {
      type: "page-layout",
      config: { padding: 16, gap: 12 },
      children: widgets.map((_, i) => `w-${i}`),
    },
  };
  widgets.forEach((w, i) => {
    const lower = w.toLowerCase();
    let type = "object-table";
    if (lower.includes("filter")) type = "filter-bar";
    else if (lower.includes("stat")) type = "stat-card";
    else if (lower.includes("table")) type = "object-table";
    else if (lower.includes("chart") || lower.includes("graph")) type = "horizontal-grid";
    tree[`w-${i}`] = { type, config: { title: w } };
  });
  return tree;
}

export type TableDrawerPair = {
  tableId: string;
  drawerId: string;
  otherIds: string[];
  beforeIds: string[];
  afterIds: string[];
};

/** 检测组件树某个 page-layout 节点是否存在 table+drawer 配对 */
export function detectTableDrawerPair(
  tree: ComponentTree,
  rootId: string = "root",
): TableDrawerPair | null {
  const node = tree[rootId];
  if (!node) return null;
  return detectTableDrawerPairByIds(tree, node.children || []);
}

/** 根据 children ID 列表检测 table+drawer 配对 */
export function detectTableDrawerPairByIds(
  tree: ComponentTree,
  childIds: string[],
): TableDrawerPair | null {
  const tableId = childIds.find((id) => tree[id]?.type === "object-table");
  const drawerId = childIds.find((id) => tree[id]?.type === "detail-drawer");
  if (!tableId || !drawerId) return null;
  const otherIds = childIds.filter((id) => id !== tableId && id !== drawerId);
  const tableIdx = childIds.indexOf(tableId);
  const beforeIds = childIds
    .slice(0, tableIdx)
    .filter((id) => id !== drawerId);
  const afterIds = childIds
    .slice(tableIdx + 1)
    .filter((id) => id !== drawerId);
  return { tableId, drawerId, otherIds, beforeIds, afterIds };
}
