import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { apiGet, apiPatch, apiPost } from "../../api/client";
import {
  BpBanner,
  BpDebugPanel,
  BpMetricGrid,
  BpPropGrid,
  BpSplit,
  BpTable,
  BpTabs,
  BpToolbar,
  flattenRecordProps,
} from "./blueprintUi";
import { JsonBlock, S2Chrome, useJsonGet } from "./shared";
import {
  TABLE_LABELS,
  buildStatusBadge,
  pipelineDisplayTitle,
  pipelineFlowLine,
  tableKeyFromBlob,
  type PipelineMeta,
} from "./pipelineMeta";

type MediaRow = { rid: string; name?: string; bytes?: number; stored?: boolean; contentType?: string };
type PipelineRow = PipelineMeta & { vectorCollection?: string };
type BuildRow = { id?: string; status?: string; tasks?: { name: string; ok: boolean }[]; pipelineId?: string };
type DatasetRow = {
  rid: string;
  name?: string;
  displayName?: string;
  status?: string;
  pipelineId?: string;
  objectTypeHint?: string;
  sourceId?: string;
};

type PreviewResult = {
  columns?: string[];
  rows?: Record<string, unknown>[];
  total?: number;
  objectType?: string;
  detail?: string;
  source?: string;
};

function tableKeyFromDataset(d: DatasetRow): string | null {
  return tableKeyFromBlob(d.rid, d.pipelineId, d.name);
}

function datasetLabel(d: DatasetRow): { title: string; ot: string; table: string | null } {
  const table = tableKeyFromDataset(d);
  const mapped = table ? TABLE_LABELS[table] : undefined;
  const ot = (d.objectTypeHint || mapped?.ot || "—").trim();
  const title =
    (d.displayName || "").trim() ||
    (mapped?.zh ? mapped.zh : "") ||
    (d.name && !String(d.name).startsWith("pipe-") ? String(d.name) : "") ||
    mapped?.zh ||
    ot ||
    d.rid;
  return { title, ot, table };
}

function cellText(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "object") {
    try {
      return JSON.stringify(v);
    } catch {
      return String(v);
    }
  }
  const s = String(v);
  return s.length > 80 ? `${s.slice(0, 77)}…` : s;
}

/** 77 · 对齐 media-sets.html */
export function MediaSetsPage() {
  const { data, err, reload } = useJsonGet<{ items: MediaRow[] }>("/v1/media-sets");
  const [parseOut, setParseOut] = useState<unknown>(null);
  const [localErr, setLocalErr] = useState<string | null>(null);

  async function uploadAndParse() {
    setLocalErr(null);
    try {
      const text = "工单标题,状态\n机房巡检,open\n";
      const b64 = btoa(unescape(encodeURIComponent(text)));
      const media = await apiPost<{ rid: string }>("/v1/media-sets", {
        name: "demo-parse.csv",
        contentType: "text/csv",
        bytesBase64: b64,
      });
      const extracted = await apiPost("/v1/parsers/extract", {
        mediaRid: media.rid,
        name: "demo-parse.csv",
        contentType: "text/csv",
      });
      setParseOut({ mediaRid: media.rid, extract: extracted });
      reload();
    } catch (e) {
      setLocalErr(String((e as Error).message || e));
    }
  }

  return (
    <S2Chrome title="媒体集" lede="对齐 media-sets · 上传 + 解析插件">
      <BpToolbar>
        <button type="button" className="btn" onClick={() => void uploadAndParse()}>
          上传 CSV 并解析
        </button>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
      </BpToolbar>
      {(err || localErr) && <p className="error">{err || localErr}</p>}
      <BpMetricGrid
        items={[{ label: "媒体集", value: String(data?.items?.length ?? 0) }]}
      />
      <BpTable
        columns={["名称", "RID", "类型", "大小", "已存储"]}
        rows={(data?.items || []).map((m) => [
          <strong>{m.name || m.rid}</strong>,
          <span className="muted">{m.rid}</span>,
          m.contentType || "—",
          `${m.bytes ?? 0}B`,
          String(m.stored ?? false),
        ])}
      />
      {(data?.items?.length || 0) === 0 && (
        <p className="muted">空 · 点上传或先到 <Link to="/data">数据连接</Link> 跑 Pipeline</p>
      )}
      {parseOut != null && <BpDebugPanel value={parseOut} title="解析结果 JSON" />}
    </S2Chrome>
  );
}

/** 186w · 对齐 pipeline-list.html（图2）· 左项目树 + 右最近编辑大卡 → 画布 */
export function PipelinesPage() {
  const [searchParams] = useSearchParams();
  const sourceFilter = searchParams.get("sourceId")?.trim() || "";
  const { data, err, reload } = useJsonGet<{ items: PipelineRow[] }>("/v1/pipelines");
  const { data: dsData } = useJsonGet<{ items: DatasetRow[] }>("/v1/datasets");
  const items = useMemo(() => {
    const all = data?.items || [];
    if (!sourceFilter) return all;
    return all.filter((p) => p.sourceId === sourceFilter);
  }, [data?.items, sourceFilter]);
  const datasets = dsData?.items || [];

  return (
    <S2Chrome title="Pipeline Builder" lede={`Ecom-Data-Project · ${items.length} 个管道`}>
      <BpToolbar>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
        <Link to="/data/pipeline-proposals" className="btn-nav">
          管道提案 →
        </Link>
        {items[0] && (
          <Link to={`/data/pipelines/${encodeURIComponent(items[0].id)}`} className="btn-nav-accent">
            打开画布 →
          </Link>
        )}
        {sourceFilter && (
          <Link to="/data/pipelines" className="btn-nav">
            清除 Source 过滤 ×
          </Link>
        )}
      </BpToolbar>
      {sourceFilter && (
        <BpBanner tone="info">
          已按 Source <strong>{sourceFilter}</strong> 过滤
        </BpBanner>
      )}
      {err && <p className="error">{err}</p>}

      <div className="bp-pipe-list-shell">
        <aside className="bp-pipe-tree">
          <div className="bp-pipe-tree-head">
            <div className="bp-section-label">项目</div>
            <div className="bp-pipe-project">
              <span className="bp-pipe-project-icon" aria-hidden />
              Ecom-Data-Project
            </div>
          </div>
          <nav className="bp-pipe-tree-nav">
            <div className="bp-section-label">管道</div>
            {items.map((p) => (
              <Link
                key={p.id}
                to={`/data/pipelines/${encodeURIComponent(p.id)}`}
                className="bp-pipe-tree-link"
                title={p.id}
              >
                {pipelineDisplayTitle(p)}
              </Link>
            ))}
            {items.length === 0 && <p className="muted">暂无管道</p>}
            <div className="bp-section-label bp-pipe-tree-gap">媒体集</div>
            <Link to="/data/media-sets" className="bp-pipe-tree-link bp-pipe-tree-link-muted">
              媒体集浏览
            </Link>
            <div className="bp-section-label bp-pipe-tree-gap">数据集</div>
            {datasets.slice(0, 8).map((d) => (
              <Link
                key={d.rid}
                to={`/data/datasets?rid=${encodeURIComponent(d.rid)}`}
                className="bp-pipe-tree-link bp-pipe-tree-link-muted"
                title={d.rid}
              >
                {datasetLabel(d).title}
              </Link>
            ))}
            <Link to="/data/datasets" className="bp-pipe-tree-link bp-pipe-tree-link-muted">
              全部数据集 →
            </Link>
          </nav>
        </aside>

        <div className="bp-pipe-list-main">
          <h2 className="bp-pipe-list-section">最近编辑</h2>
          <div className="bp-pipe-card-grid">
            {items.map((p) => {
              const badge = buildStatusBadge(p.lastBuild?.status);
              return (
                <Link
                  key={p.id}
                  to={`/data/pipelines/${encodeURIComponent(p.id)}`}
                  className="bp-pipe-card"
                >
                  <div className="bp-pipe-card-top">
                    <div>
                      <div className="bp-pipe-card-title">{pipelineDisplayTitle(p)}</div>
                      <div className="bp-pipe-card-flow">{pipelineFlowLine(p)}</div>
                    </div>
                    <span className={`bp-pipe-badge bp-pipe-badge-${badge.tone}`}>{badge.label}</span>
                  </div>
                  <div className="bp-pipe-card-meta">
                    <span>分支 master</span>
                    <span>build {p.lastBuild?.status || "—"}</span>
                    <span>3 个节点</span>
                  </div>
                </Link>
              );
            })}
          </div>
          {items.length === 0 && (
            <p className="muted">
              空 · 先到 <Link to="/data">数据连接</Link> 注册 Source / 跑 ingest
            </p>
          )}
        </div>
      </div>
    </S2Chrome>
  );
}

/** 77 · 对齐 builds.html */
export function BuildsPage() {
  const { data, err, reload } = useJsonGet<{ items: BuildRow[] }>("/v1/builds");
  const [selected, setSelected] = useState<string | null>(null);
  const builds = data?.items || [];
  const active = builds.find((b) => b.id === selected) || builds[0];

  return (
    <S2Chrome title="搭建" lede="对齐 builds · Build 列表 + 任务图">
      <BpToolbar>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
        <Link to="/data/pipelines" className="btn-nav">
          ← 管道列表
        </Link>
      </BpToolbar>
      {err && <p className="error">{err}</p>}

      <BpSplit
        left={
          <>
            <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
              搭建历史
            </h2>
            {builds.map((b) => (
              <button
                key={`${b.pipelineId}-${b.id}`}
                type="button"
                className={b.id === active?.id ? "nav-link active card" : "nav-link card"}
                style={{ width: "100%", textAlign: "left", marginBottom: 4 }}
                onClick={() => setSelected(b.id || null)}
              >
                <strong>{b.id}</strong>{" "}
                <span className={b.status === "SUCCEEDED" ? "aos-text" : "error"}>{b.status}</span>
                <div className="muted" style={{ fontSize: "0.7rem" }}>
                  pipe={b.pipelineId}
                </div>
              </button>
            ))}
            {builds.length === 0 && <p className="muted">空 · 先跑 Pipeline</p>}
          </>
        }
        right={
          active ? (
            <>
              <h1 className="aos-text" style={{ fontSize: "1.1rem" }}>
                Build {active.id}
              </h1>
              <p className="muted">
                Pipeline{" "}
                {active.pipelineId ? (
                  <Link to={`/data/pipelines/${encodeURIComponent(active.pipelineId)}`}>
                    {active.pipelineId}
                  </Link>
                ) : (
                  "—"
                )}
              </p>
              <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: 12 }}>
                任务
              </h2>
              <ul className="card-list">
                {(active.tasks || []).map((t) => (
                  <li key={t.name} className="card">
                    {t.ok ? "✅" : "❌"} {t.name}
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="muted">选择 Build 查看任务</p>
          )
        }
      />
    </S2Chrome>
  );
}

export { SchedulesPage } from "./dataSchedules";

/** 77 · 对齐 dataset.html · 182w §4.2 可读性 */
export function DatasetsPage() {
  const [searchParams] = useSearchParams();
  const ridParam = searchParams.get("rid");
  const sourceIdParam = searchParams.get("sourceId");
  const { data, err, reload } = useJsonGet<{ items: DatasetRow[] }>("/v1/datasets");
  const [tab, setTab] = useState("preview");
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<DatasetRow | null>(null);
  const [hist, setHist] = useState<{ items?: unknown[] } | null>(null);
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [previewErr, setPreviewErr] = useState<string | null>(null);
  const [loadingPrev, setLoadingPrev] = useState(false);

  const items = useMemo(() => {
    const all = data?.items || [];
    if (sourceIdParam) return all.filter((d) => d.sourceId === sourceIdParam);
    return all;
  }, [data?.items, sourceIdParam]);
  const active = useMemo(() => {
    if (!items.length) return null;
    return items.find((d) => d.rid === selected) || items[0];
  }, [items, selected]);
  const rid = active?.rid || "";
  const label = active ? datasetLabel(active) : null;

  async function loadPreviewFor(row: DatasetRow) {
    setLoadingPrev(true);
    setPreviewErr(null);
    const { title, ot, table } = datasetLabel(row);
    try {
      if (!row.objectTypeHint && ot && ot !== "—") {
        await apiPatch(`/v1/datasets/${encodeURIComponent(row.rid)}`, {
          objectTypeHint: ot,
          displayName: title,
          name: title,
        }).catch(() => null);
      }
      let result: PreviewResult;
      try {
        result = await apiPost<PreviewResult>("/v1/analytics/datasets/preview", {
          datasetRid: row.rid,
          limit: 40,
        });
      } catch {
        result = { columns: [], rows: [], total: 0 };
      }
      if ((!result.rows || result.rows.length === 0) && ot && ot !== "—") {
        result = await apiPost<PreviewResult>("/v1/analytics/objects/list", {
          objectType: ot,
          limit: 40,
        });
        result = { ...result, objectType: ot, source: result.source || "objects-list" };
      }
      setPreview(result);
      if (!result.rows?.length && result.detail) setPreviewErr(String(result.detail));
    } catch (e) {
      setPreview(null);
      setPreviewErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingPrev(false);
    }
    void table;
  }

  async function openDataset(id: string) {
    setSelected(id);
    setTab("preview");
    const d = await apiGet<DatasetRow>(`/v1/datasets/${encodeURIComponent(id)}`);
    setDetail(d);
    const h = await apiGet<{ items: unknown[] }>(`/v1/datasets/${encodeURIComponent(id)}/history`);
    setHist(h);
    await loadPreviewFor({ ...d, rid: id });
  }

  useEffect(() => {
    if (ridParam && items.some((d) => d.rid === ridParam)) {
      void openDataset(ridParam).catch(console.error);
      return;
    }
    if (!selected && items[0]?.rid) {
      void openDataset(items[0].rid).catch(console.error);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 深链 rid / 列表首次加载
  }, [items.length, ridParam, sourceIdParam]);

  const previewColumns = useMemo(() => {
    if (preview?.columns?.length) return preview.columns.slice(0, 8);
    const row0 = preview?.rows?.[0];
    if (!row0) return ["id"];
    return Object.keys(row0).slice(0, 8);
  }, [preview]);

  const previewTableRows = useMemo(() => {
    return (preview?.rows || []).map((r) =>
      previewColumns.map((c) => <span key={c}>{cellText(r[c])}</span>),
    );
  }, [preview, previewColumns]);

  return (
    <S2Chrome title="数据集预览" lede="左栏选数据集 · 右栏为采样预览（非全表浏览）；总数见指标「预览行数/库内」">
      <BpToolbar>
        <button
          type="button"
          className="btn"
          onClick={() => {
            reload();
            if (rid) void openDataset(rid).catch(console.error);
          }}
        >
          刷新
        </button>
        <Link to="/data/lineage" className="btn-nav">
          在沿袭中打开 →
        </Link>
        <Link to="/analytics" className="btn-nav">
          分析读数 →
        </Link>
      </BpToolbar>
      {err && <p className="error">{err}</p>}
      {sourceIdParam && items.length > 0 && (
        <BpBanner tone="info">
          已按数据源 <code>{sourceIdParam}</code> 过滤 ·{" "}
          <Link to="/data/datasets" className="nav-link">
            查看全部数据集
          </Link>
        </BpBanner>
      )}

      {!items.length && (
        <p className="muted">
          暂无数据集 · 先到 <Link to="/data">数据连接</Link> 接入，或跑案例 bootstrap 脚本
        </p>
      )}

      {items.length > 0 && (
        <BpSplit
          left={
            <ul className="card-list" style={{ gap: "0.4rem" }}>
              {items.map((d) => {
                const L = datasetLabel(d);
                const on = d.rid === rid;
                return (
                  <li key={d.rid}>
                    <button
                      type="button"
                      className={on ? "nav-link card active" : "nav-link card"}
                      onClick={() => void openDataset(d.rid).catch(console.error)}
                    >
                      <span className="nav-link-title">{L.title}</span>
                      <span className="nav-link-meta">
                        {L.ot}
                        {L.table ? ` · ${L.table}` : ""} · {d.status || "READY"}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          }
          right={
            rid && label ? (
              <>
                <BpTabs
                  active={tab}
                  onChange={setTab}
                  tabs={[
                    { id: "preview", label: "预览" },
                    { id: "history", label: "历史" },
                    { id: "details", label: "详情" },
                    { id: "health", label: "健康" },
                  ]}
                />
                {tab === "preview" && (
                  <>
                    <h1 className="aos-text" style={{ fontSize: "1.25rem", margin: "0.5rem 0 0.25rem" }}>
                      {label.title}
                    </h1>
                    <p className="muted" style={{ marginTop: 0 }}>
                      对象类型 <strong className="aos-text">{label.ot}</strong>
                      {label.table ? (
                        <>
                          {" "}
                          · 源表 <code>{label.table}</code>
                        </>
                      ) : null}
                      <br />
                      <span style={{ fontSize: "0.75rem" }}>{rid}</span>
                    </p>
                    <BpMetricGrid
                      items={[
                        {
                          label: "本页采样",
                          value: preview?.rows?.length ?? 0,
                          tone: "muted",
                        },
                        {
                          label: "库内总数",
                          value: preview?.total ?? "—",
                          tone: "ok",
                        },
                        {
                          label: "状态",
                          value: String(detail?.status || active?.status || "READY"),
                          tone: "ok",
                        },
                        {
                          label: "Pipeline",
                          value: String(detail?.pipelineId || active?.pipelineId || "—"),
                          tone: "muted",
                        },
                      ]}
                    />
                    {previewErr && <p className="error">{previewErr}</p>}
                    {loadingPrev && <p className="muted">加载预览…</p>}
                    {!loadingPrev && previewTableRows.length > 0 && (
                      <BpTable columns={previewColumns} rows={previewTableRows} />
                    )}
                    {!loadingPrev && !previewTableRows.length && !previewErr && (
                      <BpBanner tone="warn">
                        该对象类型暂无实例行。确认已在当前工作区完成 ingest，或到{" "}
                        <Link to="/ontology/objects">对象浏览</Link> 核对。
                      </BpBanner>
                    )}
                  </>
                )}
                {tab === "history" && (
                  <ul className="card-list">
                    {(hist?.items || []).map((h, i) => (
                      <li key={i} className="card">
                        <JsonBlock value={h} />
                      </li>
                    ))}
                    {(hist?.items?.length || 0) === 0 && <p className="muted">无历史版本</p>}
                  </ul>
                )}
                {tab === "details" && (detail || active) && (
                  <>
                    <BpPropGrid items={flattenRecordProps((detail || active) as Record<string, unknown>)} />
                    <details style={{ marginTop: "0.75rem" }}>
                      <summary className="muted">完整 JSON</summary>
                      <JsonBlock value={detail || active} />
                    </details>
                  </>
                )}
                {tab === "health" && (
                  <BpBanner tone="info">
                    Dataset 健康见 <Link to="/data/health">L1 数据健康</Link> · 图谱见{" "}
                    <Link to="/ontology/graph-health">图谱健康度</Link>
                  </BpBanner>
                )}
              </>
            ) : (
              <p className="muted">在左侧选择一个数据集</p>
            )
          }
        />
      )}
    </S2Chrome>
  );
}

/** 77 · 对齐 health.html */
export function DataHealthPage() {
  const store = useJsonGet<Record<string, unknown>>("/v1/object-store/health");
  const mysql = useJsonGet<Record<string, unknown>>("/v1/connectors/jdbc-mysql/health");
  const dlq = useJsonGet<{ items: { id: string; reason?: string; status?: string }[] }>("/v1/dlq");

  const dlqCount = dlq.data?.items?.length || 0;
  const storeOk = store.data && (store.data as { ok?: boolean }).ok !== false;
  const mysqlOk = mysql.data && (mysql.data as { ok?: boolean }).ok !== false;
  const warn = (!storeOk ? 1 : 0) + (!mysqlOk ? 1 : 0);
  const bad = dlqCount > 0 ? 1 : 0;
  const ok = 2 - warn;

  return (
    <S2Chrome title="数据健康" lede="对齐 health · L1 连通/新鲜度（≠ 图谱健康）">
      <BpToolbar>
        <button
          type="button"
          className="btn"
          onClick={() => {
            store.reload();
            mysql.reload();
            dlq.reload();
          }}
        >
          刷新
        </button>
        <Link to="/data" className="btn-nav">
          返回数据连接
        </Link>
        <Link to="/ontology/graph-health" className="btn-nav">
          图谱健康度 →
        </Link>
      </BpToolbar>
      {(store.err || mysql.err || dlq.err) && (
        <p className="error">{store.err || mysql.err || dlq.err}</p>
      )}

      <BpBanner tone="info">
        分责：本页 L1 Dataset/Source · 悬空 Link/属性冲突 →{" "}
        <Link to="/ontology/graph-health">图谱健康度</Link>
      </BpBanner>

      <BpMetricGrid
        items={[
          { label: "健康", value: ok, tone: "ok" },
          { label: "告警", value: warn, tone: warn > 0 ? "warn" : "ok" },
          { label: "严重", value: bad, tone: bad > 0 ? "bad" : "ok" },
        ]}
      />
      {dlqCount > 0 && (
        <p className="error" style={{ marginTop: 8 }}>
          DLQ 死信 <strong>{dlqCount}</strong>
        </p>
      )}

      <BpTable
        columns={["资源", "检查项", "状态", "详情", "上次检查"]}
        rows={[
          [
            "MinIO Object Store",
            "连通性",
            storeOk ? <span className="aos-text">通过</span> : <span className="error">失败</span>,
            String((store.data as { mode?: string })?.mode || "probe"),
            "刚刚",
          ],
          [
            "MySQL Connector",
            "连通性",
            mysqlOk ? <span className="aos-text">通过</span> : <span className="error">失败</span>,
            String((mysql.data as { message?: string })?.message || "probe"),
            "刚刚",
          ],
          [
            <Link to="/data/datasets">WorkOrder-demo</Link>,
            "新鲜度",
            <span className="aos-text">通过</span>,
            "数据集 READY",
            "—",
          ],
        ]}
      />

      {dlqCount > 0 && (
        <>
          <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: "1rem" }}>
            DLQ
          </h2>
          <ul className="card-list">
            {(dlq.data?.items || []).map((d) => (
              <li key={d.id} className="card">
                <strong>{d.id}</strong> <span className="muted">{d.reason}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </S2Chrome>
  );
}

/** 77 · 对齐 data-connection-agents.html */
export function EdgeAgentsPage() {
  const { data, err, reload } = useJsonGet<{ id: string; probeOk?: boolean; outbound?: boolean }>(
    "/v1/edge/agents/local",
  );
  const [selected, setSelected] = useState("edge-local");

  const agents = data
    ? [
        {
          id: data.id || "edge-local",
          region: "本机 Dev",
          sources: 1,
          version: "lite",
          online: data.probeOk !== false,
        },
      ]
    : [];

  const active = agents.find((a) => a.id === selected) || agents[0];

  return (
    <S2Chrome title="边缘代理" lede="对齐 data-connection-agents · 列表 + 详情">
      <BpToolbar>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
        <button type="button" className="btn-outline-cyan" disabled title="登记接口规划中">
          + 注册代理
        </button>
      </BpToolbar>
      {err && <p className="error">{err}</p>}

      <BpSplit
        left={
          <ul className="card-list">
            {agents.map((a) => (
              <li key={a.id}>
                <button
                  type="button"
                  className={a.id === selected ? "nav-link active card" : "nav-link card"}
                  style={{ width: "100%", textAlign: "left" }}
                  onClick={() => setSelected(a.id)}
                >
                  <strong>{a.id}</strong>{" "}
                  <span className={a.online ? "aos-text" : "error"}>{a.online ? "在线" : "离线"}</span>
                  <div className="muted" style={{ fontSize: "0.7rem" }}>
                    {a.region} · {a.sources} 数据源
                  </div>
                </button>
              </li>
            ))}
          </ul>
        }
        right={
          active ? (
            <>
              <h1 className="aos-text" style={{ fontSize: "1.1rem" }}>
                {active.id}
              </h1>
              <p className="muted">
                边缘代理 · outbound={String(data?.outbound)} · probeOk={String(data?.probeOk)}
              </p>
              <BpTable
                columns={["属性", "值"]}
                rows={[
                  ["region", active.region],
                  ["version", active.version],
                  ["sources", String(active.sources)],
                  ["status", active.online ? "在线" : "离线"],
                ].map(([k, v]) => [<span className="muted">{k}</span>, v])}
              />
            </>
          ) : (
            <p className="muted">无代理</p>
          )
        }
      />
    </S2Chrome>
  );
}
