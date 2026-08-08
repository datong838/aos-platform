/**
 * 187w/188w · Source 详情（连接器页）· 对齐 source-detail.html
 * 统一壳：Tab · 探索两栏（左树 + 中预览）；探索区仅为采样预览，不冒充全量。
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
  comment?: string;
};

export type SchemaTable = {
  name: string;
  row_count?: number;
  columns?: SchemaColumn[];
  comment?: string;
  // D4 Phase C · C1: 302 表分类标签 A/B/C/D/E
  classification?: string;
};

// D4 Phase C · C1: 302 表分类标签映射
export const CLASSIFICATION_LABELS: Record<string, string> = {
  A: "OT源表",
  B: "JOIN维度",
  C: "明细扩展",
  D: "配置·按需",
  E: "系统·不落孪生",
};

// 分类标签的颜色映射（用于内联样式）
export const CLASSIFICATION_COLORS: Record<string, { bg: string; fg: string }> = {
  A: { bg: "#ddf4ff", fg: "#0969da" }, // 蓝色 · 核心源表
  B: { bg: "#dafbe1", fg: "#1a7f37" }, // 绿色 · JOIN 维度
  C: { bg: "#fff8c5", fg: "#9a6700" }, // 黄色 · 明细扩展
  D: { bg: "#f6f8fa", fg: "#57606a" }, // 灰色 · 配置按需
  E: { bg: "#ffebe9", fg: "#cf222e" }, // 红色 · 系统·不落孪生
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
const SAMPLE_COL_LIMIT = 0; // 0 = 显示全部字段

function cellText(v: unknown): string {
  if (v == null) return "—";
  const s = typeof v === "object" ? JSON.stringify(v) : String(v);
  return s.length > 48 ? `${s.slice(0, 45)}…` : s;
}

/** D2.6 · Niushop 微商城专属 Demo Schema（8 张 ns_xxx 表 + 真实字段）。
 *
 * 字段映射参考 scripts/d2_qiyuehui_init_load.py 的 8 OT mapper：
 * - ns_site (Shop) / ns_goods_category (Category) / ns_goods (Product) /
 *   ns_goods_sku (ProductSku) / ns_member (CustomerLite) / ns_order (Order) /
 *   ns_order_goods (OrderLine) / ns_express_delivery_package (Shipment)
 *
 * 注：ns_member 包含 PII 字段（mobile/nickname 等）用于在 UI 可视化标记隐私字段，
 * 实际接入时由 SourceAdapter 层显式 drop（_PII_DROP_FIELDS）。
 */
const NIUSHOP_DEMO_SCHEMA: SchemaNode[] = [
  {
    name: "niushop_b2c_v5",
    description: "演示路径 · Niushop 微商城数据库",
    tables: [
      {
        name: "ns_shop",
        row_count: 1,
        columns: [
          { name: "site_id", datatype: "INT", primary_key: true },
          { name: "site_name", datatype: "VARCHAR" },
          { name: "create_time", datatype: "INT" },
          { name: "modify_time", datatype: "INT" },
        ],
      },
      {
        name: "ns_goods_category",
        row_count: 11,
        columns: [
          { name: "category_id", datatype: "INT", primary_key: true },
          { name: "category_name", datatype: "VARCHAR" },
          { name: "parent_id", datatype: "INT" },
          { name: "sort", datatype: "INT", nullable: true },
        ],
      },
      {
        name: "ns_goods",
        row_count: 65,
        columns: [
          { name: "goods_id", datatype: "INT", primary_key: true },
          { name: "goods_name", datatype: "VARCHAR" },
          { name: "category_id", datatype: "INT" },
          { name: "sku_price", datatype: "DECIMAL", nullable: true },
          { name: "market_price", datatype: "DECIMAL", nullable: true },
          { name: "evaluate", datatype: "INT" },
          { name: "evaluate_haoping", datatype: "INT" },
          { name: "create_time", datatype: "INT" },
          { name: "modify_time", datatype: "INT" },
        ],
      },
      {
        name: "ns_goods_sku",
        row_count: 73,
        columns: [
          { name: "sku_id", datatype: "INT", primary_key: true },
          { name: "goods_id", datatype: "INT" },
          { name: "sku_name", datatype: "VARCHAR" },
          { name: "price", datatype: "DECIMAL" },
          { name: "stock", datatype: "INT" },
          { name: "alarm_stock", datatype: "INT", nullable: true },
          { name: "create_time", datatype: "INT" },
          { name: "modify_time", datatype: "INT" },
        ],
      },
      {
        name: "ns_member",
        row_count: 53,
        columns: [
          { name: "member_id", datatype: "INT", primary_key: true },
          { name: "member_level", datatype: "INT" },
          { name: "status", datatype: "INT" },
          { name: "mobile", datatype: "VARCHAR", nullable: true },
          { name: "wx_openid", datatype: "VARCHAR", nullable: true },
          { name: "nickname", datatype: "VARCHAR", nullable: true },
          { name: "avatar", datatype: "VARCHAR", nullable: true },
          { name: "reg_address", datatype: "VARCHAR", nullable: true },
          { name: "last_login_ip", datatype: "VARCHAR", nullable: true },
          { name: "site_id", datatype: "INT" },
          { name: "is_delete", datatype: "INT" },
        ],
      },
      {
        name: "ns_order",
        row_count: 177,
        columns: [
          { name: "order_id", datatype: "BIGINT", primary_key: true },
          { name: "order_no", datatype: "VARCHAR" },
          { name: "member_id", datatype: "INT" },
          { name: "order_money", datatype: "DECIMAL" },
          { name: "pay_money", datatype: "DECIMAL", nullable: true },
          { name: "order_status", datatype: "INT" },
          { name: "pay_status", datatype: "INT" },
          { name: "refund_status", datatype: "INT" },
          { name: "is_lock", datatype: "INT" },
          { name: "commission_risk_flag", datatype: "INT", nullable: true },
          { name: "create_time", datatype: "INT" },
          { name: "modify_time", datatype: "INT" },
        ],
      },
      {
        name: "ns_order_goods",
        row_count: 227,
        columns: [
          { name: "order_goods_id", datatype: "BIGINT", primary_key: true },
          { name: "order_id", datatype: "BIGINT" },
          { name: "goods_id", datatype: "INT" },
          { name: "sku_id", datatype: "INT" },
          { name: "goods_name", datatype: "VARCHAR" },
          { name: "goods_money", datatype: "DECIMAL" },
          { name: "real_goods_money", datatype: "DECIMAL" },
          { name: "num", datatype: "INT" },
          { name: "create_time", datatype: "INT" },
        ],
      },
      {
        name: "ns_express_delivery_package",
        row_count: 19,
        columns: [
          { name: "id", datatype: "BIGINT", primary_key: true },
          { name: "order_id", datatype: "BIGINT" },
          { name: "express_company_id", datatype: "INT", nullable: true },
          { name: "express_no", datatype: "VARCHAR", nullable: true },
          { name: "delivery_time", datatype: "INT", nullable: true },
          { name: "member_id", datatype: "INT" },
          { name: "site_id", datatype: "INT" },
        ],
      },
    ],
  },
];

/** W3-C7 · 按连接器类型的本地演示 Schema（API 全失败时） */
export function demoSchemaTree(connectorType?: string): SchemaNode[] {
  const t = (connectorType || "jdbc").toLowerCase();
  // D4 Phase C: niushop-mysql 已废弃，不再根据连接器类型返回专属 schema
  // 所有 JDBC 连接器（包括 jdbc-mysql-ssh）都走默认 demo schema
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
  return demo ? "数据源连接" : "连接器 Schema";
}

export function schemaSourceLabel(source: SchemaTreeSource): string {
  if (source.mode === "fallback") return "连接失败";
  if (source.mode === "api_demo") return "连接器 Schema";
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

  const [tab, setTab] = useState<"overview" | "explore" | "sync" | "credentials">("overview");
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
  const [columnsLoading, setColumnsLoading] = useState(false);
  const [columnsError, setColumnsError] = useState<string | null>(null);
  const loadedColumnsRef = useRef<Map<string, SchemaColumn[]>>(new Map());
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
  // 优化：优先使用 _tables 字段一次性加载，避免 N+1 请求。
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
        const schRes = await apiGet<{
          items?: {
            name: string;
            description?: string;
            _tables?: {
              name: string;
              row_count?: number;
              comment?: string;
              // D4 Phase C · C1: 302 表分类标签
              classification?: string;
              columns?: { name: string; datatype?: string; primary_key?: boolean; nullable?: boolean; comment?: string }[];
            }[];
          }[];
          demo?: boolean;
        }>(`/api/datasource/sources/${encodeURIComponent(sourceId)}/schemas`);
        const schemas = schRes.items || [];
        const demo = Boolean(schRes.demo);
        const tree: SchemaNode[] = [];

        // 检查是否有 _tables 字段（一次性加载优化）
        const hasEmbeddedTables = schemas.some((s) => s._tables && s._tables.length > 0);

        if (hasEmbeddedTables) {
          // 路径 A：使用 _tables 字段（轻量版：只有表名+注释，字段在点击时按需加载）
          for (const sch of schemas) {
            const tables: SchemaTable[] = (sch._tables || []).map((tbl) => ({
              name: tbl.name,
              row_count: tbl.row_count,
              comment: tbl.comment,
              // D4 Phase C · C1: 透传 302 表分类标签
              classification: tbl.classification,
              columns: [],
            }));
            tree.push({ name: sch.name, description: sch.description, tables });
          }
        } else {
          // 路径 B：回退到逐个请求表名（字段在点击时按需加载）
          for (const sch of schemas) {
            const tblRes = await apiGet<{ items?: { name: string; row_count?: number; comment?: string; classification?: string }[] }>(
              `/api/datasource/sources/${encodeURIComponent(sourceId)}/schemas/${encodeURIComponent(sch.name)}/tables`,
            );
            const tables: SchemaTable[] = (tblRes.items || []).map((t) => ({
              name: t.name,
              row_count: t.row_count,
              comment: t.comment,
              // D4 Phase C · C1: 透传 302 表分类标签
              classification: t.classification,
              columns: [],
            }));
            tree.push({ name: sch.name, description: sch.description, tables });
          }
        }

        if (!isCurrent()) return;
        if (tree.length === 0 && demo) {
          // 接口返回 demo 标记但没有真实数据，显示错误
          applySchemaSnapshot([], {
            mode: "fallback",
            primaryError: "数据源连接失败：无法获取 Schema 信息",
          });
        } else {
          applySchemaSnapshot(tree, {
            mode: "live",
          });
        }
      } catch (error) {
        if (!isCurrent()) return;
        applySchemaSnapshot([], {
          mode: "fallback",
          primaryError: `Schema 加载失败：${String((error as Error).message || error)}`,
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
      setColumnsError(null);
      return;
    }
    const cacheKey = `${activeSchemaTable.schema}.${activeSchemaTable.table}`;
    const cached = loadedColumnsRef.current.get(cacheKey);
    if (cached) {
      setActiveColumns(cached);
      setColumnsError(null);
      return;
    }
    // 按需从 API 加载单表字段
    let cancelled = false;
    setColumnsLoading(true);
    setColumnsError(null);
    (async () => {
      try {
        const colRes = await apiGet<{ items?: SchemaColumn[] }>(
          `/api/datasource/sources/${encodeURIComponent(sourceId)}/schemas/${encodeURIComponent(activeSchemaTable.schema)}/tables/${encodeURIComponent(activeSchemaTable.table)}/columns`,
        );
        if (cancelled) return;
        const cols = (colRes.items || []).map((c) => ({
          name: c.name,
          datatype: c.datatype,
          primary_key: c.primary_key,
          nullable: c.nullable,
          comment: c.comment || c.description || undefined,
        }));
        loadedColumnsRef.current.set(cacheKey, cols);
        setActiveColumns(cols);
      } catch (error) {
        if (cancelled) return;
        setActiveColumns([]);
        const errMsg = error instanceof Error ? error.message : String(error);
        setColumnsError(errMsg);
      } finally {
        if (!cancelled) setColumnsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [activeSchemaTable, sourceId]);

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
          setPreviewDemo(false);
          setPreviewSource("live");
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
      // 没有可加载的数据源，显示空状态
      if (!isCurrent()) return;
      setPreview(null);
      setPreviewSource("none");
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
  }, [activeSchemaTable, activeEntry?.datasetRid, activeEntry?.ot, schemaSource.mode, sourceId]);

  useEffect(() => {
    void loadSample();
  }, [loadSample, sampleTick]);

  const cols = SAMPLE_COL_LIMIT > 0
    ? (preview?.columns?.slice(0, SAMPLE_COL_LIMIT) || [])
    : (preview?.columns || []);
  const rows = preview?.rows || [];
  const sampleShown = rows.length;
  const libraryTotal = preview?.total;
  const plugins = pluginData?.items;

  const sampleLede = previewBusy && columnsLoading
    ? "加载字段与采样…"
    : previewBusy
      ? "加载采样…"
      : columnsLoading
        ? "加载字段中…"
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
          ← 数据源管理
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
                                <span className="mono" style={{ color: "#1f2328" }}>{tbl.name}</span>
                                {/* D4 Phase C · C1: 302 表分类标签（A/B/C/D/E） */}
                                {tbl.classification && (() => {
                                  const cls = tbl.classification!;
                                  const color = CLASSIFICATION_COLORS[cls] || CLASSIFICATION_COLORS.D;
                                  return (
                                    <span
                                      title={CLASSIFICATION_LABELS[cls] || cls}
                                      style={{
                                        marginLeft: 6,
                                        padding: "0 6px",
                                        fontSize: "0.7rem",
                                        fontWeight: 600,
                                        background: color.bg,
                                        color: color.fg,
                                        borderRadius: 8,
                                        border: `1px solid ${color.fg}33`,
                                      }}
                                    >
                                      {cls}
                                    </span>
                                  );
                                })()}
                                {tbl.comment && (
                                  <>
                                    <span style={{ marginLeft: 6, fontSize: "0.8rem", color: "#57606a", fontWeight: 500 }}>·</span>
                                    <span style={{ marginLeft: 4, fontSize: "0.8rem", color: "#24292f", fontWeight: 500 }}>
                                      {tbl.comment}
                                    </span>
                                  </>
                                )}
                                {tbl.row_count != null && (
                                  <span style={{ marginLeft: 8, fontSize: "0.7rem", color: "#6e7781" }}>
                                    [{tbl.row_count}条]
                                  </span>
                                )}
                              </button>
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
                    </p>
                  </div>
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    {primaryDatasetRid && (
                      <Link
                        to={`/data/datasets?rid=${encodeURIComponent(primaryDatasetRid)}`}
                        className="btn"
                        style={{ textDecoration: "none", fontSize: "0.8rem" }}
                      >
                        打开数据集
                      </Link>
                    )}
                    <Link
                      to={`/data/schedules?sourceId=${encodeURIComponent(sourceId)}`}
                      className="btn-primary"
                      style={{ textDecoration: "none", fontSize: "0.8rem" }}
                    >
                      创建批量同步
                    </Link>
                    <button
                      type="button"
                      className="btn"
                      disabled={previewBusy}
                      onClick={() => setSampleTick((n) => n + 1)}
                    >
                      刷新采样
                    </button>
                  </div>
                </div>
                <div className="bp-src-detail-preview">
                  {previewPrimaryErr && (
                    <p className="error" role="alert">
                      连接器采样失败：{previewPrimaryErr}；当前来源：
                      {previewSource === "dataset"
                        ? "Dataset"
                        : previewSource === "object"
                          ? "对象实例"
                          : "连接器"}
                    </p>
                  )}
                  {previewErr && <p className="error">{previewErr}</p>}
                  {columnsError && (
                    <p className="error" style={{ padding: "var(--space-3)" }}>
                      字段加载失败：{columnsError}
                    </p>
                  )}
                  {columnsLoading && !previewErr && !columnsError && (
                    <p className="muted" style={{ padding: "var(--space-3)" }}>加载字段中…</p>
                  )}
                  {!columnsLoading && !previewErr && cols.length > 0 && (
                    <table className="bp-pipe-preview-table">
                      <thead>
                        <tr>
                          {cols.map((c) => {
                            const meta = activeColumns.find((x) => x.name === c);
                            const displayComment = meta?.comment || "";
                            return (
                              <th key={c} style={{ whiteSpace: "nowrap", minWidth: "120px" }}>
                                <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: "3px" }}>
                                  {displayComment && (
                                    <span style={{ fontSize: "0.8rem", color: "#1f2328", fontWeight: 600, lineHeight: 1.3 }}>
                                      {displayComment}
                                    </span>
                                  )}
                                  <span style={{ fontSize: "0.72rem", color: "#57606a", fontFamily: "monospace" }}>
                                    {c}
                                    {meta?.datatype && (
                                      <span style={{ marginLeft: 6, color: "#0969da", fontWeight: 500 }}>
                                        : {meta.datatype}{meta.primary_key ? " 🔑PK" : ""}
                                      </span>
                                    )}
                                  </span>
                                </div>
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
              {schemaTree.length > 0 && (
                <div className="bp-src-detail-schema-stats" style={{ marginTop: 12, padding: 12, background: "var(--bp-surface-muted, #f5f5f5)", borderRadius: 8 }}>
                  <p className="aos-text" style={{ fontSize: "0.85rem", marginBottom: 8 }}>
                    <strong>Schema 统计</strong>
                  </p>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, fontSize: "0.8rem" }}>
                    <div>
                      <span className="muted">Schema 数量</span>
                      <div style={{ fontWeight: 600, fontSize: "1.1rem" }}>{schemaTree.length}</div>
                    </div>
                    <div>
                      <span className="muted">表数量</span>
                      <div style={{ fontWeight: 600, fontSize: "1.1rem" }}>
                        {schemaTree.reduce((sum, s) => sum + s.tables.length, 0)}
                      </div>
                    </div>
                    <div>
                      <span className="muted">当前列数</span>
                      <div style={{ fontWeight: 600, fontSize: "1.1rem" }}>
                        {activeColumns.length || "—"}
                      </div>
                    </div>
                  </div>
                  {schemaSource.mode !== "live" && (
                    <p className="muted" style={{ fontSize: "0.75rem", marginTop: 8 }}>
                      当前来源：{schemaSourceLabel(schemaSource)}
                    </p>
                  )}
                </div>
              )}
              {(() => {
                const plugin = plugins?.find((p) => p.id === source.type);
                const schema = plugin?.configSchema;
                if (!schema?.properties) return null;
                const entries = Object.entries(schema.properties);
                if (entries.length === 0) return null;
                // 敏感字段判断
                const isSensitive = (key: string, prop?: { format?: string }) =>
                  prop?.format === "password" ||
                  /password|secret|key|token/i.test(key);
                // 生成与实际密码长度匹配的脱敏字符串
                const maskValue = (val: string) => "•".repeat(Math.min(val.length, 12));
                // 字段分组：SSH 隧道 / 远程数据库 / 凭据
                const groups: { label: string; fields: [string, typeof entries[number][1]][] }[] = [
                  { label: "SSH 隧道连接", fields: [] },
                  { label: "远程 MySQL", fields: [] },
                  { label: "凭据", fields: [] },
                ];
                // 只处理 configSchema.properties 中定义的字段，过滤遗留字段
                for (const [key, prop] of entries) {
                  if (key.startsWith("ssh")) groups[0].fields.push([key, prop]);
                  else if (isSensitive(key, prop)) groups[2].fields.push([key, prop]);
                  else groups[1].fields.push([key, prop]);
                }
                return (
                  <div className="bp-src-detail-config" style={{ marginTop: 16 }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                      <p className="aos-text" style={{ fontSize: "0.85rem" }}>
                        <strong>插件配置实例</strong>
                      </p>
                      <span className="muted" style={{ fontSize: "0.7rem" }}>只读展示 · 不可保存</span>
                    </div>
                    {groups.filter((g) => g.fields.length > 0).map((group) => (
                      <div key={group.label} style={{ marginBottom: 12 }}>
                        <p className="muted" style={{ fontSize: "0.75rem", marginBottom: 4 }}>{group.label}</p>
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 8 }}>
                          {group.fields.map(([key, prop]) => {
                            const rawVal = source[key] ?? prop?.default ?? "";
                            const valStr = String(rawVal ?? "");
                            const displayVal = isSensitive(key, prop) && valStr
                              ? maskValue(valStr)
                              : valStr;
                            return (
                              <label key={key} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                                <span className="muted" style={{ fontSize: "0.7rem" }}>
                                  {prop?.description || prop?.title || key}
                                </span>
                                <input
                                  type={isSensitive(key, prop) ? "password" : "text"}
                                  value={displayVal}
                                  readOnly
                                  style={{
                                    padding: "4px 8px",
                                    fontSize: "0.8rem",
                                    border: "1px solid var(--bp-border, #d0d7de)",
                                    borderRadius: 4,
                                    background: "var(--bp-surface, #fff)",
                                    color: "var(--bp-text, #1f2328)",
                                  }}
                                />
                              </label>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                );
              })()}
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
