/**
 * 187w/188w · Source 详情（连接器页）· 对齐 source-detail.html
 * 统一壳：Tab · 探索三栏 · 右侧信息；探索区仅为采样预览，不冒充全量。
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiPost } from "../../api/client";
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
};

/** 探索页只读采样窗口（非 ingest 上限） */
const SAMPLE_ROW_LIMIT = 50;
const SAMPLE_COL_LIMIT = 20;

function cellText(v: unknown): string {
  if (v == null) return "—";
  const s = typeof v === "object" ? JSON.stringify(v) : String(v);
  return s.length > 48 ? `${s.slice(0, 45)}…` : s;
}

export function SourceDetailPage() {
  const { sourceId = "" } = useParams();
  const { data: srcData, err: srcErr, reload } = useJsonGet<{ items: SourceRow[] }>("/v1/sources");
  const { data: pipeData } = useJsonGet<{ items: PipelineRow[] }>("/v1/pipelines");
  const { data: dsData } = useJsonGet<{ items: DatasetRow[] }>("/v1/datasets");
  const { data: syncData } = useJsonGet<{ items: SyncRow[] }>("/v1/syncs");
  const { data: pluginData } = useJsonGet<{ items: { id: string; nameZh?: string; name?: string }[] }>(
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

  useEffect(() => {
    if (tableEntries[0]?.id) setActiveTable(tableEntries[0].id);
  }, [sourceId, tableEntries]);

  const loadSample = useCallback(async () => {
    if (!activeEntry?.datasetRid && !activeEntry?.ot) {
      setPreview(null);
      return;
    }
    setPreviewBusy(true);
    setPreviewErr(null);
    try {
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
      setPreview(result);
    } catch (e) {
      setPreviewErr(e instanceof Error ? e.message : String(e));
    } finally {
      setPreviewBusy(false);
    }
  }, [activeEntry?.datasetRid, activeEntry?.ot]);

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
        <button type="button" className="btn" onClick={() => reload()}>
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
                <input className="bp-src-detail-search" placeholder="搜索表…" aria-label="搜索表" />
                <div className="bp-section-label">{sourceId}</div>
                <nav className="bp-src-detail-nav">
                  {tableEntries.length === 0 && <p className="muted">暂无关联管道/表</p>}
                  {tableEntries.map((t) => (
                    <button
                      key={t.id}
                      type="button"
                      className={`bp-src-detail-tree-item${activeEntry?.id === t.id ? " is-active" : ""}`}
                      onClick={() => setActiveTable(t.id)}
                    >
                      {t.label}
                    </button>
                  ))}
                </nav>
              </aside>

              <div className="bp-src-detail-center">
                <div className="bp-src-detail-center-bar">
                  <div>
                    <h2 className="bp-src-detail-table-title">{activeEntry?.label || "—"}</h2>
                    <p className="muted" style={{ fontSize: "0.75rem", marginTop: 4 }}>
                      {sampleLede}
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
                  {previewErr && <p className="error">{previewErr}</p>}
                  {!previewErr && cols.length > 0 && (
                    <table className="bp-pipe-preview-table">
                      <thead>
                        <tr>
                          {cols.map((c) => (
                            <th key={c}>{c}</th>
                          ))}
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
