/** 187w · 数据连接列表/详情共享 UI · 对齐 data-connection.html 徽标 */
import { Link } from "react-router-dom";

export type ConfigSchemaProperty = {
  type?: string;
  title?: string;
  description?: string;
  default?: unknown;
  format?: string;
};

export type ConfigSchema = {
  type?: string;
  properties?: Record<string, ConfigSchemaProperty>;
  required?: string[];
};

export type ConnectorPlugin = {
  id: string;
  nameZh?: string;
  name?: string;
  description?: string;
  installed?: boolean;
  required?: boolean;
  runtime?: string;
  capabilities?: string[];
  configSchema?: ConfigSchema;
};

export type SourceRow = {
  id?: string;
  type?: string;
  status?: string;
  runtimeMode?: string;
  pluginId?: string;
  [key: string]: unknown;
};

export function connectorLabel(t?: string, plugins?: ConnectorPlugin[]): string {
  if (!t) return "—";
  const hit = plugins?.find((p) => p.id === t);
  if (hit) return hit.nameZh || hit.name || t;
  if (t === "file" || t === "file-local") return "本地文件";
  if (t === "file-object-store") return "对象存储文件";
  if (t === "jdbc-mysql-ssh") return "MySQL SSH 隧道";
  if (t === "jdbc" || t === "jdbc-mysql") return "MySQL JDBC";
  if (t === "jdbc-postgres") return "PostgreSQL";
  if (t === "jdbc-postgres-ssh") return "PostgreSQL SSH 隧道";
  return t;
}

export function connectorTone(t?: string): "sky" | "emerald" | "amber" | "muted" | "violet" | "rose" {
  if (t?.includes("postgres")) return "violet";
  if (t?.includes("oracle")) return "rose";
  if (t?.includes("jdbc") || t === "mysql") return "sky";
  if (t?.startsWith("file") || t === "file") return "emerald";
  if (t?.startsWith("rest")) return "amber";
  return "muted";
}

export function storageLabel(t?: string): { text: string; kind: "dataset" | "media" | "stream" } {
  if (t === "file" || t?.startsWith("file")) return { text: "媒体集·文档", kind: "media" };
  return { text: "数据集", kind: "dataset" };
}

export function sourceSubtitle(t?: string): string {
  if (t === "file" || t === "file-local") return "文件接入 · 本地 / 上传";
  if (t === "file-object-store") return "文件接入 · 对象存储";
  if (t === "jdbc-mysql-ssh") return "结构化入库 · MySQL SSH 隧道";
  if (t === "jdbc" || t === "jdbc-mysql") return "结构化入库 · MySQL";
  if (t === "jdbc-postgres-ssh") return "结构化入库 · PostgreSQL SSH 隧道";
  if (t?.includes("postgres")) return "结构化入库 · PostgreSQL";
  if (t?.startsWith("jdbc")) return "结构化入库 · JDBC";
  return "外部系统接入";
}

export function runtimeLabel(s: SourceRow): string {
  const mode = (s.runtimeMode || "").toLowerCase();
  if (mode === "agent") return "本机边缘代理";
  if (mode === "worker") return "代理工作者";
  if (mode === "direct") return "直接连接";
  return "历史数据 · 未设置";
}

export function sourceBusinessName(source: SourceRow, plugins?: ConnectorPlugin[]): string {
  const explicit = [source.nameZh, source.displayName, source.name]
    .find((value) => typeof value === "string" && value.trim()) as string | undefined;
  if (explicit) return explicit.trim();
  if (source.id === "niushop-qyh") return "栖月汇微商城";
  return `${connectorLabel(source.type, plugins)}数据源`;
}

export function statusZh(s?: string): string {
  const v = (s || "").toUpperCase();
  if (!s) return "—";
  if (v === "SUCCEEDED" || v === "SUCCESS" || v === "OK" || v === "ACTIVE" || v === "ONLINE" || v === "REGISTERED")
    return "在线";
  if (v === "RUNNING" || v === "IN_PROGRESS") return "同步中";
  if (v === "FAILED" || v === "ERROR") return "失败";
  return s;
}

export function ConnectorTagLink({
  sourceId,
  type,
  plugins,
}: {
  sourceId: string;
  type?: string;
  plugins?: ConnectorPlugin[];
}) {
  const tone = connectorTone(type);
  const label = connectorLabel(type, plugins);
  return (
    <Link
      to={`/data/sources/${encodeURIComponent(sourceId)}`}
      className={`data-tag data-tag-link data-tag-${tone}`}
      title={`打开连接器 · ${label}`}
      onClick={(e) => e.stopPropagation()}
    >
      {label}
    </Link>
  );
}

export function StoragePillLink({
  sourceId,
  type,
  datasetRid,
}: {
  sourceId: string;
  type?: string;
  datasetRid?: string;
}) {
  const s = storageLabel(type);
  const to =
    s.kind === "media"
      ? "/data/media-sets"
      : datasetRid
        ? `/data/datasets?rid=${encodeURIComponent(datasetRid)}`
        : `/data/datasets?sourceId=${encodeURIComponent(sourceId)}`;
  return (
    <Link
      to={to}
      className={`data-storage data-storage-link data-storage-${s.kind}`}
      title={s.kind === "media" ? "打开媒体集" : "打开数据集"}
      onClick={(e) => e.stopPropagation()}
    >
      {s.text}
    </Link>
  );
}

export function SourceNameLink({ sourceId, displayName, subtitle }: { sourceId: string; displayName: string; subtitle: string }) {
  return (
    <span className="data-src-name">
      <Link to={`/data/sources/${encodeURIComponent(sourceId)}`} className="data-src-title">{displayName}</Link>
      <span className="data-src-sub">{subtitle}</span>
      <details><summary>技术审计信息</summary><code>{sourceId}</code></details>
    </span>
  );
}
