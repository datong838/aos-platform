/** 187w · 数据连接列表/详情共享 UI · 对齐 data-connection.html 徽标 */
import { Link } from "react-router-dom";

export type ConnectorPlugin = {
  id: string;
  nameZh?: string;
  name?: string;
  description?: string;
  installed?: boolean;
  required?: boolean;
  runtime?: string;
  capabilities?: string[];
};

export type SourceRow = { id?: string; type?: string; status?: string; runtimeMode?: string; pluginId?: string };

export function connectorLabel(t?: string, plugins?: ConnectorPlugin[]): string {
  if (!t) return "—";
  const hit = plugins?.find((p) => p.id === t);
  if (hit) return hit.nameZh || hit.name || t;
  if (t === "file" || t === "file-local") return "本地文件";
  if (t === "file-object-store") return "对象存储文件";
  if (t === "jdbc" || t === "jdbc-mysql") return "MySQL JDBC";
  if (t === "jdbc-postgres") return "PostgreSQL";
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
  if (t === "jdbc" || t === "jdbc-mysql") return "结构化入库 · MySQL";
  if (t?.includes("postgres")) return "结构化入库 · PostgreSQL";
  if (t?.startsWith("jdbc")) return "结构化入库 · JDBC";
  return "外部系统接入";
}

export function runtimeLabel(s: SourceRow): string {
  const mode = (s.runtimeMode || "").toLowerCase();
  if (mode === "agent") return "代理 · agent-local";
  if (mode === "worker") return "代理工作者";
  if (mode === "direct") return "直接连接";
  if (s.type === "jdbc") return "代理 · agent-local";
  return "直接连接";
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

export function SourceNameLink({ sourceId, subtitle }: { sourceId: string; subtitle: string }) {
  return (
    <Link to={`/data/sources/${encodeURIComponent(sourceId)}`} className="data-src-name">
      <span className="data-src-title">{sourceId}</span>
      <span className="data-src-sub">{subtitle}</span>
    </Link>
  );
}
