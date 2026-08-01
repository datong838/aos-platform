/**
 * 187w/188w · Source 详情（连接器页）· 对齐 source-detail.html
 * 统一壳：Tab · 探索三栏 · 右侧信息；探索区仅为采样预览，不冒充全量。
 * W3-C7：Schema 树（schema→表→列）优先接 phase6 datasource API；失败标演示路径。
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiGet, apiPost } from "../../api/client";
import { PageChrome } from "../../components/PageChrome";
import { BpBanner, BpTabs, BpToolbar } from "./blueprintUi";
import {
  ConnectorTagLink,
  connectorLabel,
  runtimeLabel,
  sourceSubtitle,
  statusZh,
  StoragePillLink,
  type SourceRow,
} from "./dataConnectionUi";
import { useJsonGet } from "./shared";
import { pipelineDisplayTitle, tableKeyFromBlob, TABLE_LABELS } from "./pipelineMeta";

type PipelineRow = {
  id: string;
  sourceId?: string;
  datasetRid?: string;
  objectTypeHint?: string;
};
type DatasetRow = { rid: string; sourceId?: string; objectTypeHint?: string; displayName?: string };
type SyncRow = { id?: string; sourceId?: string; status?: string; finishedAt?: number };
type PreviewResult = {
  columns?: string[];
  rows?: Record<string, unknown>[];
  total?: number;
  objectType?: string;
  pageSize?: number;
  demo?: boolean;
};

export type SchemaColumn = {
  name: string;
  datatype?: string;
  primary_key?: boolean;
  nullable?: boolean;
};

export type SchemaTable = {
  name: string;
  row_count?: number;
  columns?: SchemaColumn[];
};

export type SchemaNode = {
  name: string;
  description?: string;
  tables: SchemaTable[];
};

export type SchemaTreeSource = {
  mode: "live" | "api_demo" | "fallback";
  primaryError?: string;
};

export type AppliedSchemaTree = {
  schemaTree: SchemaNode[];
  expandedSchemas: Record<string, boolean>;
  activeSchemaTable: { schema: string; table: string } | null;
  activeColumns: SchemaColumn[];
  source: SchemaTreeSource;
  clearPreview: boolean;
};

/** 所有 Schema 来源都经此处同步树、首表、列和清空语义。 */
export function applySchemaTree(tree: SchemaNode[], source: SchemaTreeSource): AppliedSchemaTree {
  const firstSchema = tree.find((schema) => schema.tables.length > 0);
  const firstTable = firstSchema?.tables[0];
  return {
    schemaTree: tree,
    expandedSchemas: Object.fromEntries(tree.map((schema) => [schema.name, true])),
    activeSchemaTable: firstSchema && firstTable
      ? { schema: firstSchema.name, table: firstTable.name }
      : null,
    activeColumns: firstTable?.columns || [],
    source,
    clearPreview: !firstTable,
  };
}

/** 探索页只读采样窗口（非 ingest 上限） */
const SAMPLE_ROW_LIMIT = 50;
const SAMPLE_COL_LIMIT = 20;

function cellText(v: unknown): string {
  if (v == null) return "—";
  const s = typeof v === "object" ? JSON.stringify(v) : String(v);
  return s.length > 48 ? `${s.slice(0, 45)}…` : s;
}

/** W3-C7 · 按连接器类型的本地演示 Schema（API 全失败时） */
export function demoSchemaTree(connectorType?: string): SchemaNode[] {
  const t = (connectorType || "jdbc").toLowerCase();
  if (t.includes("kafka") || t.includes("stream")) {
    return [
      {
        name: "topics",
        description: "演示路径 · 流主题",
        tables: [
          {
            name: "events",
            row_count: 5000,
            columns: [
              { name: "event_id", datatype: "BIGINT", primary_key: true },
              { name: "ts", datatype: "TIMESTAMP" },
              { name: "payload", datatype: "JSON", nullable: true },
            ],
          },
        ],
      },
    ];
  }
  if (t.includes("s3") || t.includes("file") || t.includes("blob")) {
    return [
      {
        name: "bucket",
        description: "演示路径 · 对象存储",
        tables: [
          {
            name: "objects",
            row_count: 200,
            columns: [
              { name: "key", datatype: "VARCHAR", primary_key: true },
              { name: "size", datatype: "BIGINT" },
              { name: "etag", datatype: "VARCHAR", nullable: true },
            ],
          },
        ],
      },
    ];
  }
  return [
    {
      name: "public",
      description: "演示路径 · 默认 schema",
      tables: [
        {
          name: "orders",
          row_count: 12847,
          columns: [
            { name: "order_id", datatype: "BIGINT", primary_key: true },
            { name: "customer_id", datatype: "BIGINT" },
            { name: "amount", datatype: "DECIMAL", nullable: true },
            { name: "status", datatype: "VARCHAR", nullable: true },
          ],
        },
        {
          name: "customers",
          row_count: 8102,
          columns: [
            { name: "customer_id", datatype: "BIGINT", primary_key: true },
            { name: "name", datatype: "VARCHAR" },
            { name: "email", datatype: "VARCHAR", nullable: true },
          ],
        },
      ],
    },
    {
      name: "analytics",
      description: "演示路径 · analytics",
      tables: [
        {
          name: "events",
          row_count: 50000,
          columns: [
            { name: "event_id", datatype: "BIGINT", primary_key: true },
            { name: "ts", datatype: "TIMESTAMP" },
          ],
        },
      ],
    },
  ];
}

export function filterSchemaTree(tree: SchemaNode[], q: string): SchemaNode[] {
  const needle = q.trim().toLowerCase();
  if (!needle) return tree;
  return tree
    .map((sch) => ({
      ...sch,
      tables: sch.tables.filter(
        (t) =>
          t.name.toLowerCase().includes(needle) ||
          sch.name.toLowerCase().includes(needle) ||
          (t.columns || []).some((c) => c.name.toLowerCase().includes(needle)),
      ),
    }))
    .filter((sch) => sch.tables.length > 0 || sch.name.toLowerCase().includes(needle));
}

export function flattenTables(tree: SchemaNode[]): { schema: string; table: string; row_count?: number }[] {
  const out: { schema: string; table: string; row_count?: number }[] = [];
  for (const sch of tree) {
    for (const t of sch.tables) {
      out.push({ schema: sch.name, table: t.name, row_count: t.row_count });
    }
  }
  return out;
}

export function schemaPathLabel(demo: boolean): string {
  return demo ? "演示路径" : "连接器 Schema";
}

export function schemaSourceLabel(source: SchemaTreeSource): string {
  if (source.mode === "fallback") return "演示回落";
  if (source.mode === "api_demo") return "API 演示数据";
  return "连接器 Schema";
}

export function formatColumnBadge(col: SchemaColumn): string {
  const parts = [col.datatype || "—"];
  if (col.primary_key) parts.push("PK");
  if (col.nullable) parts.push("NULL");
  return parts.join(" · ");
}

export function SourceDetailPage() {
  const { sourceId = "" } = useParams();
  const { data: srcData, err: srcErr, reload: reloadSources } = useJsonGet<{ items: SourceRow[] }>("/v1/sources");
  const { data: pipeData, reload: reloadPipelines } = useJsonGet<{ items: PipelineRow[] }>("/v1/pipelines");
  const { data: dsData, reload: reloadDatasets } = useJsonGet<{ items: DatasetRow[] }>("/v1/datasets");
  const { data: syncData, reload: reloadSyncs } = useJsonGet<{ items: SyncRow[] }>("/v1/syncs");
  const { data: pluginData, reload: reloadPlugins } = useJsonGet<{ items: { id: string; nameZh?: string; name?: string }[] }>(
    "/v1/connector-plugins",
  );

  const source = useMemo(
    () => (srcData?.items || []).find((s) => s.id === sourceId) || null,
    [srcData?.items, sourceId],
  );
  const pipelines = useMemo(
    () => (pipeData?.items || []).filter((p) => p.sourceId === sourceId),
    [pipeData?.items, sourceId],
  );
  const datasets = useMemo(
    () => (dsData?.items || []).filter((d) => d.sourceId === sourceId),
    [dsData?.items, sourceId],
  );
  const syncs = useMemo(
    () => (syncData?.items || []).filter((s) => s.sourceId === sourceId),
    [syncData?.items, sourceId],
  );
  const primaryDatasetRid = datasets[0]?.rid || pipelines[0]?.datasetRid;

  const [tab, setTab] = useState<"overview" | "explore" | "sync" | "credentials">("explore");
  const [activeTable, setActiveTable] = useState<string>("");
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [previewErr, setPreviewErr] = useState<string | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [sampleTick, setSampleTick] = useState(0);
  const [previewDemo, setPreviewDemo] = useState(false);
  const [previewSource, setPreviewSource] = useState<"live" | "dataset" | "object" | "demo">("live");
  const [previewPrimaryErr, setPreviewPrimaryErr] = useState<string | null>(null);

  // W3-C7 schema tree
  const [schemaTree, setSchemaTree] = useState<SchemaNode[]>([]);
  const [schemaDemo, setSchemaDemo] = useState(false);
  const [schemaErr, setSchemaErr] = useState<string | null>(null);
  const [schemaSource, setSchemaSource] = useState<SchemaTreeSource>({ mode: "live" });
  const [schemaBusy, setSchemaBusy] = useState(false);
  const [schemaTick, setSchemaTick] = useState(0);
  const [tableSearch, setTableSearch] = useState("");
  const [expandedSchemas, setExpandedSchemas] = useState<Record<string, boolean>>({});
  const [activeSchemaTable, setActiveSchemaTable] = useState<{ schema: string; table: string } | null>(null);
  const [activeColumns, setActiveColumns] = useState<SchemaColumn[]>([]);
  const routeGenerationRef = useRef(0);
  const schemaRequestRef = useRef(0);
  const previewRequestRef = useRef(0);

  const tableEntries = useMemo(() => {
    return pipelines.map((p) => {
      const key = tableKeyFromBlob(p.id, p.datasetRid) || p.id;
      const mapped = key ? TABLE_LABELS[key] : undefined;
      return {
        id: p.id,
        key,
        label: pipelineDisplayTitle(p),
        ot: p.objectTypeHint || mapped?.ot,
        datasetRid: p.datasetRid,
      };
    });
  }, [pipelines]);

  const activeEntry = tableEntries.find((t) => t.id === activeTable) || tableEntries[0];
  const filteredTree = useMemo(
    () => filterSchemaTree(schemaTree, tableSearch),
    [schemaTree, tableSearch],
  );

  const applySchemaSnapshot = useCallback((tree: SchemaNode[], treeSource: SchemaTreeSource) => {
    const applied = applySchemaTree(tree, treeSource);
    setSchemaTree(applied.schemaTree);
    setExpandedSchemas(applied.expandedSchemas);
    setActiveSchemaTable(applied.activeSchemaTable);
    setActiveColumns(applied.activeColumns);
    setSchemaSource(applied.source);
    setSchemaDemo(applied.source.mode !== "live");
    setSchemaErr(applied.source.primaryError || null);
    if (applied.clearPreview) {
      previewRequestRef.current += 1;
      setPreview(null);
      setPreviewErr(null);
      setPreviewPrimaryErr(null);
      setPreviewDemo(false);
      setPreviewSource("live");
      setPreviewBusy(false);
    }
  }, []);

  useEffect(() => {
    routeGenerationRef.current += 1;
    schemaRequestRef.current += 1;
    previewRequestRef.current += 1;
    setActiveTable("");
    setSchemaTree([]);
    setExpandedSchemas({});
    setActiveSchemaTable(null);
    setActiveColumns([]);
    setSchemaErr(null);
    setSchemaSource({ mode: "live" });
    setSchemaDemo(false);
    setPreview(null);
    setPreviewErr(null);
    setPreviewPrimaryErr(null);
    setPreviewDemo(false);
    setPreviewSource("live");
    setTableSearch("");
  }, [sourceId]);

  useEffect(() => {
    if (tableEntries[0]?.id) setActiveTable(tableEntries[0].id);
  }, [sourceId, tableEntries]);

  // W3-C7 / W3C-W1 · 加载 Schema 树，隔离路由与同路由旧请求。
  useEffect(() => {
    if (!sourceId) return;
    const routeGeneration = routeGenerationRef.current;
    const requestId = ++schemaRequestRef.current;
    let cancelled = false;
    const isCurrent = () =>
      !cancelled &&
      routeGenerationRef.current === routeGeneration &&
      schemaRequestRef.current === requestId;
    (async () => {
      setSchemaBusy(true);
      try {
        const schRes = await apiGet<{ items?: { name: string; description?: string }[]; demo?: boolean }>(
          `/api/datasource/sources/${encodeURIComponent(sourceId)}/schemas`,
        );
        const schemas = schRes.items || [];
        const demo = Boolean(schRes.demo);
        const tree: SchemaNode[] = [];
        const columnErrors: string[] = [];
        for (const sch of schemas) {
          const tblRes = await apiGet<{ items?: { name: string; row_count?: number }[] }>(
            `/api/datasource/sources/${encodeURIComponent(sourceId)}/schemas/${encodeURIComponent(sch.name)}/tables`,
          );
          const tables: SchemaTable[] = [];
          for (const tbl of tblRes.items || []) {
            let columns: SchemaColumn[] = [];
            try {
              const colRes = await apiGet<{ items?: SchemaColumn[] }>(
                `/api/datasource/sources/${encodeURIComponent(sourceId)}/schemas/${encodeURIComponent(sch.name)}/tables/${encodeURIComponent(tbl.name)}/columns`,
              );
              columns = (colRes.items || []).map((c) => ({
                name: c.name,
                datatype: c.datatype,
                primary_key: c.primary_key,
                nullable: c.nullable,
              }));
            } catch (error) {
              columnErrors.push(`${sch.name}.${tbl.name}: ${String((error as Error).message || error)}`);
            }
            tables.push({ name: tbl.name, row_count: tbl.row_count, columns });
          }
          tree.push({ name: sch.name, description: sch.description, tables });
        }
        if (!isCurrent()) return;
        if (tree.length === 0 && demo) {
          applySchemaSnapshot(demoSchemaTree(source?.type), { mode: "api_demo" });
        } else {
          applySchemaSnapshot(tree, {
            mode: demo ? "api_demo" : "live",
            ...(columnErrors.length ? { primaryError: `部分列读取失败：${columnErrors.join("；")}` } : {}),
          });
        }
      } catch (error) {
        if (!isCurrent()) return;
        applySchemaSnapshot(demoSchemaTree(source?.type), {
          mode: "fallback",
          primaryError: String((error as Error).message || error),
        });
      } finally {
        if (isCurrent()) setSchemaBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [applySchemaSnapshot, schemaTick, sourceId, source?.type]);

  useEffect(() => {
    if (!activeSchemaTable) {
      setActiveColumns([]);
      return;
    }
    const sch = schemaTree.find((s) => s.name === activeSchemaTable.schema);
    const tbl = sch?.tables.find((t) => t.name === activeSchemaTable.table);
    setActiveColumns(tbl?.columns || []);
  }, [activeSchemaTable, schemaTree]);

  const loadSample = useCallback(async () => {
    const routeGeneration = routeGenerationRef.current;
    const requestId = ++previewRequestRef.current;
    const isCurrent = () =>
      routeGenerationRef.current === routeGeneration &&
      previewRequestRef.current === requestId;
    setPreviewBusy(true);
    setPreviewErr(null);
    setPreviewDemo(false);
    setPreviewPrimaryErr(null);
    let primaryError: string | null = null;
    try {
      // 优先连接器 schema preview
      if (activeSchemaTable) {
        try {
          const result = await apiPost<PreviewResult>(
            `/api/datasource/sources/${encodeURIComponent(sourceId)}/preview`,
            {
              schema_name: activeSchemaTable.schema,
              table_name: activeSchemaTable.table,
              limit: SAMPLE_ROW_LIMIT,
            },
          );
          if (!isCurrent()) return;
          setPreview(result);
          setPreviewDemo(Boolean(result.demo));
          setPreviewSource(result.demo ? "demo" : "live");
          return;
        } catch (error) {
          primaryError = String((error as Error).message || error);
        }
      }
      if (activeEntry?.datasetRid || activeEntry?.ot) {
        let result: PreviewResult;
        if (activeEntry.datasetRid) {
          result = await apiPost<PreviewResult>("/v1/analytics/datasets/preview", {
            datasetRid: activeEntry.datasetRid,
            limit: SAMPLE_ROW_LIMIT,
          });
        } else {
          result = await apiPost<PreviewResult>("/v1/analytics/objects/list", {
            objectType: activeEntry.ot,
            limit: SAMPLE_ROW_LIMIT,
          });
        }
        if (!isCurrent()) return;
        setPreview(result);
        setPreviewDemo(false);
        setPreviewSource(activeEntry.datasetRid ? "dataset" : "object");
        setPreviewPrimaryErr(primaryError);
        return;
      }
      if (schemaSource.mode === "live") {
        if (!isCurrent()) return;
        setPreview(null);
        setPreviewSource("live");
        setPreviewPrimaryErr(primaryError);
        return;
      }
      // 最终演示行
      const cols = activeColumns.length
        ? activeColumns.map((c) => c.name)
        : ["id", "name", "value"];
      const demoRows = Array.from({ length: 5 }, (_, r) => {
        const row: Record<string, unknown> = {};
        for (const col of cols) {
          row[col] = col.endsWith("_id") || col === "id" ? r + 1 : `${col}_${r}`;
        }
        return row;
      });
      setPreview({
        columns: cols,
        rows: demoRows,
        total: 5,
        demo: true,
      });
      setPreviewDemo(true);
      setPreviewSource("demo");
      setPreviewPrimaryErr(primaryError);
    } catch (e) {
      if (!isCurrent()) return;
      setPreview(null);
      setPreviewErr(e instanceof Error ? e.message : String(e));
      setPreviewDemo(false);
      setPreviewPrimaryErr(primaryError);
    } finally {
      if (isCurrent()) setPreviewBusy(false);
    }
  }, [activeSchemaTable, activeEntry?.datasetRid, activeEntry?.ot, activeColumns, schemaSource.mode, sourceId]);

  useEffect(() => {
    void loadSample();
  }, [loadSample, sampleTick]);

  const cols = preview?.columns?.slice(0, SAMPLE_COL_LIMIT) || [];
  const rows = preview?.rows || [];
  const sampleShown = rows.length;
  const libraryTotal = preview?.total;
  const plugins = pluginData?.items;

  const sampleLede = previewBusy
    ? "加载采样…"
    : libraryTotal != null
      ? `采样预览 · 显示 ${sampleShown} 行 / ${cols.length} 列（库内共 ${libraryTotal} 行）`
      : "采样预览";

  const centerTitle = activeSchemaTable
    ? `${activeSchemaTable.schema}.${activeSchemaTable.table}`
    : activeEntry?.label || "—";

  function refreshAll() {
    previewRequestRef.current += 1;
    setPreview(null);
    setPreviewErr(null);
    setPreviewPrimaryErr(null);
    setPreviewSource("live");
    reloadSources();
    reloadPipelines();
    reloadDatasets();
    reloadSyncs();
    reloadPlugins();
    setSchemaTick((tick) => tick + 1);
  }

  return (
    <PageChrome title={sourceId || "数据源"} lede={source ? sourceSubtitle(source.type) : "Source 详情 · 连接器"}>
      <BpToolbar>
        <Link to="/data" className="btn-nav">
          ← 数据连接
        </Link>
        {source && (
          <ConnectorTagLink sourceId={sourceId} type={source.type} plugins={plugins} />
        )}
        {primaryDatasetRid && (
          <StoragePillLink sourceId={sourceId} type={source?.type} datasetRid={primaryDatasetRid} />
        )}
        <Link to={`/data/pipelines?sourceId=${encodeURIComponent(sourceId)}`} className="btn-nav">
          管道 →
        </Link>
        <button type="button" className="btn" onClick={refreshAll}>
          刷新
        </button>
      </BpToolbar>

      {srcErr && <p className="error">{srcErr}</p>}
      {!srcErr && !source && <BpBanner tone="warn">未找到数据源 {sourceId}</BpBanner>}

      {source && (
        <>
          <div className="bp-src-detail-status">
            <span className={`data-status data-status-${statusZh(source.status) === "在线" ? "ok" : "muted"}`}>
              <span className="data-status-dot" aria-hidden />
              {statusZh(source.status)}
            </span>
          </div>

          <BpTabs
            tabs={[
              { id: "overview", label: "概览" },
              { id: "explore", label: "探索" },
              { id: "sync", label: "同步" },
              { id: "credentials", label: "凭证" },
            ]}
            active={tab}
            onChange={(id) => setTab(id as typeof tab)}
          />

          {tab === "explore" && (
            <div className="bp-src-detail-shell">
              <aside className="bp-src-detail-tree">
                <input
                  className="bp-src-detail-search"
                  placeholder="搜索表…"
                  aria-label="搜索表"
                  value={tableSearch}
                  onChange={(e) => setTableSearch(e.target.value)}
                />
                <div className="bp-section-label" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span>{sourceId}</span>
                  <span className={`w3-c6c7-path-badge ${schemaDemo ? "is-demo" : "is-live"}`}>
                    {schemaSourceLabel(schemaSource)}
                  </span>
                </div>
                {schemaErr && (
                  <p className="error" role="alert">
                    Schema 主路径失败：{schemaErr}；当前来源：{schemaSourceLabel(schemaSource)}
                  </p>
                )}
                <nav className="bp-src-detail-nav w3-c7-schema-nav">
                  {schemaBusy && <p className="muted">加载 Schema…</p>}
                  {!schemaBusy && filteredTree.length === 0 && <p className="muted">暂无 Schema</p>}
                  {filteredTree.map((sch) => (
                    <div key={sch.name} className="w3-c7-schema-group">
                      <button
                        type="button"
                        className="w3-c7-schema-toggle"
                        onClick={() =>
                          setExpandedSchemas((prev) => ({ ...prev, [sch.name]: !prev[sch.name] }))
                        }
                      >
                        {expandedSchemas[sch.name] !== false ? "▾" : "▸"} {sch.name}
                        <span className="muted" style={{ marginLeft: 6, fontSize: "0.7rem" }}>
                          {sch.tables.length} 表
                        </span>
                      </button>
                      {expandedSchemas[sch.name] !== false &&
                        sch.tables.map((tbl) => {
                          const active =
                            activeSchemaTable?.schema === sch.name &&
                            activeSchemaTable?.table === tbl.name;
                          return (
                            <div key={`${sch.name}.${tbl.name}`}>
                              <button
                                type="button"
                                className={`bp-src-detail-tree-item${active ? " is-active" : ""}`}
                                onClick={() => setActiveSchemaTable({ schema: sch.name, table: tbl.name })}
                              >
                                {tbl.name}
                                {tbl.row_count != null && (
                                  <span className="muted" style={{ marginLeft: 6, fontSize: "0.65rem" }}>
                                    {tbl.row_count}
                                  </span>
                                )}
                              </button>
                              {active && (tbl.columns || []).length > 0 && (
                                <ul className="w3-c7-col-list">
                                  {(tbl.columns || []).map((c) => (
                                    <li key={c.name}>
                                      <span className="mono">{c.name}</span>
                                      <span className="muted">{formatColumnBadge(c)}</span>
                                    </li>
                                  ))}
                                </ul>
                              )}
                            </div>
                          );
                        })}
                    </div>
                  ))}
                  {tableEntries.length > 0 && (
                    <>
                      <div className="bp-section-label" style={{ marginTop: 12 }}>
                        管道派生表
                      </div>
                      {tableEntries.map((t) => (
                        <button
                          key={t.id}
                          type="button"
                          className={`bp-src-detail-tree-item${
                            !activeSchemaTable && activeEntry?.id === t.id ? " is-active" : ""
                          }`}
                          onClick={() => {
                            setActiveSchemaTable(null);
                            setActiveTable(t.id);
                          }}
                        >
                          {t.label}
                        </button>
                      ))}
                    </>
                  )}
                </nav>
              </aside>

              <div className="bp-src-detail-center">
                <div className="bp-src-detail-center-bar">
                  <div>
                    <h2 className="bp-src-detail-table-title">{centerTitle}</h2>
                    <p className="muted" style={{ fontSize: "0.75rem", marginTop: 4 }}>
                      {sampleLede}
                      {previewDemo && (
                        <span className="w3-c6c7-path-badge is-demo" style={{ marginLeft: 8 }}>
                          演示路径
                        </span>
                      )}
                      {!previewDemo && previewSource !== "live" && (
                        <span className="w3-c6c7-path-badge is-live" style={{ marginLeft: 8 }}>
                          {previewSource === "dataset" ? "Dataset 回落" : "对象实例回落"}
                        </span>
                      )}
                    </p>
                  </div>
                  <button
                    type="button"
                    className="btn"
                    disabled={previewBusy}
                    onClick={() => setSampleTick((n) => n + 1)}
                  >
                    刷新采样
                  </button>
                </div>
                <div className="bp-src-detail-preview">
                  {previewPrimaryErr && (
                    <p className="error" role="alert">
                      连接器采样失败：{previewPrimaryErr}；当前来源：
                      {previewSource === "dataset"
                        ? "Dataset"
                        : previewSource === "object"
                          ? "对象实例"
                          : previewSource === "demo"
                            ? "演示路径"
                            : "无可用回落"}
                    </p>
                  )}
                  {previewErr && <p className="error">{previewErr}</p>}
                  {!previewErr && cols.length > 0 && (
                    <table className="bp-pipe-preview-table">
                      <thead>
                        <tr>
                          {cols.map((c) => {
                            const meta = activeColumns.find((x) => x.name === c);
                            return (
                              <th key={c}>
                                {c}
                                {meta?.datatype && (
                                  <span className="muted" style={{ marginLeft: 4, fontSize: "0.65rem" }}>
                                    {meta.datatype}
                                    {meta.primary_key ? " PK" : ""}
                                  </span>
                                )}
                              </th>
                            );
                          })}
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map((row, i) => (
                          <tr key={i}>
                            {cols.map((c) => (
                              <td key={c}>{cellText(row[c])}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                  {!previewErr && !previewBusy && cols.length === 0 && (
                    <p className="muted">暂无预览 · 请先跑 ingest 或选左侧表</p>
                  )}
                </div>
              </div>

              <aside className="bp-src-detail-inspector">
                <h3 className="bp-pipe-inspector-title">数据源信息</h3>
                <dl className="bp-src-detail-dl">
                  <div>
                    <dt>连接器</dt>
                    <dd>{connectorLabel(source.type, plugins)}</dd>
                  </div>
                  <div>
                    <dt>运行时</dt>
                    <dd>{runtimeLabel(source)}</dd>
                  </div>
                  <div>
                    <dt>插件</dt>
                    <dd>{source.pluginId || source.type || "—"}</dd>
                  </div>
                  <div>
                    <dt>关联管道</dt>
                    <dd>{pipelines.length}</dd>
                  </div>
                </dl>

                {activeColumns.length > 0 && (
                  <>
                    <div className="bp-src-detail-divider" />
                    <h3 className="bp-pipe-inspector-title">当前表列</h3>
                    <ul className="w3-c7-col-list w3-c7-col-list-side">
                      {activeColumns.map((c) => (
                        <li key={c.name}>
                          <span className="mono">{c.name}</span>
                          <span className="muted">{formatColumnBadge(c)}</span>
                        </li>
                      ))}
                    </ul>
                  </>
                )}

                <div className="bp-src-detail-divider" />
                <h3 className="bp-pipe-inspector-title">同步任务</h3>
                {syncs.length === 0 && <p className="muted">暂无同步记录</p>}
                {syncs.slice(0, 3).map((s) => (
                  <div key={s.id} className="bp-src-detail-sync-card">
                    <div className="bp-src-detail-sync-head">
                      <span>{s.id}</span>
                      <span className={statusZh(s.status) === "在线" ? "aos-text" : "muted"}>
                        {statusZh(s.status)}
                      </span>
                    </div>
                  </div>
                ))}

                <Link
                  to={`/data/schedules?sourceId=${encodeURIComponent(sourceId)}`}
                  className="btn-primary bp-pipe-deploy"
                >
                  创建批量同步
                </Link>
                {primaryDatasetRid && (
                  <Link
                    to={`/data/datasets?rid=${encodeURIComponent(primaryDatasetRid)}`}
                    className="btn-nav bp-pipe-deploy"
                  >
                    打开数据集 →
                  </Link>
                )}
              </aside>
            </div>
          )}

          {tab === "overview" && (
            <div className="bp-src-detail-overview">
              <p className="aos-text">
                连接器 <strong>{connectorLabel(source.type, plugins)}</strong> · 运行时{" "}
                <strong>{runtimeLabel(source)}</strong>
              </p>
              <p className="muted">
                {pipelines.length} 条管道 · {datasets.length} 个数据集 · {syncs.length} 次同步
              </p>
              <BpLinkRow
                links={[
                  { to: `/data/pipelines?sourceId=${encodeURIComponent(sourceId)}`, label: "管道构建" },
                  {
                    to: primaryDatasetRid
                      ? `/data/datasets?rid=${encodeURIComponent(primaryDatasetRid)}`
                      : `/data/datasets?sourceId=${encodeURIComponent(sourceId)}`,
                    label: "数据集",
                  },
                ]}
              />
            </div>
          )}

          {tab === "sync" && (
            <div className="bp-src-detail-overview">
              {syncs.length === 0 && <p className="muted">暂无同步 · 可到计划编辑器绑定 ingest</p>}
              <ul className="card-list">
                {syncs.map((s) => (
                  <li key={s.id} className="card">
                    {s.id} · {statusZh(s.status)}
                  </li>
                ))}
              </ul>
              <Link to="/data/schedules" className="btn-nav">
                打开计划编辑器 →
              </Link>
            </div>
          )}

          {tab === "credentials" && (
            <BpBanner tone="info">凭证走密钥引用（vault ref）· 本页不落明文；配置见新建数据源向导。</BpBanner>
          )}
        </>
      )}
    </PageChrome>
  );
}

function BpLinkRow({ links }: { links: { to: string; label: string }[] }) {
  return (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
      {links.map((l) => (
        <Link key={l.to} to={l.to} className="btn-nav">
          {l.label} →
        </Link>
      ))}
    </div>
  );
}
