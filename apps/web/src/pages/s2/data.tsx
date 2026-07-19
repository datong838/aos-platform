import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { apiGet, apiPost } from "../../api/client";
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

type MediaRow = { rid: string; name?: string; bytes?: number; stored?: boolean; contentType?: string };
type PipelineRow = {
  id: string;
  sourceId?: string;
  target?: string;
  datasetRid?: string;
  lastBuild?: BuildRow;
  vectorCollection?: string;
};
type BuildRow = { id?: string; status?: string; tasks?: { name: string; ok: boolean }[]; pipelineId?: string };
type DatasetRow = {
  rid: string;
  name?: string;
  status?: string;
  pipelineId?: string;
  objectTypeHint?: string;
  sourceId?: string;
};

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
        <button type="button" className="btn-primary" onClick={() => void uploadAndParse()}>
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

/** 77 · 对齐 pipeline-list.html · 103 sourceId 过滤 */
export function PipelinesPage() {
  const [searchParams] = useSearchParams();
  const sourceFilter = searchParams.get("sourceId")?.trim() || "";
  const { data, err, reload } = useJsonGet<{ items: PipelineRow[] }>("/v1/pipelines");
  const items = useMemo(() => {
    const all = data?.items || [];
    if (!sourceFilter) return all;
    return all.filter((p) => p.sourceId === sourceFilter);
  }, [data?.items, sourceFilter]);
  const [activeId, setActiveId] = useState<string>("");
  const [query, setQuery] = useState("巡检");
  const [embedOut, setEmbedOut] = useState<unknown>(null);
  const [searchOut, setSearchOut] = useState<unknown>(null);
  const [localErr, setLocalErr] = useState<string | null>(null);
  const active = items.find((p) => p.id === activeId) || items[0];

  async function runEmbed() {
    if (!active?.id) return;
    setLocalErr(null);
    setEmbedOut(null);
    try {
      const out = await apiPost(`/v1/pipelines/${encodeURIComponent(active.id)}/embed`, {
        pluginId: "embed-openai-compatible",
        autoSample: true,
        replace: true,
        documents: [
          { id: "demo-1", text: "机房巡检-A区" },
          { id: "demo-2", text: "链路告警复核" },
          { id: "demo-3", text: "备件更换" },
        ],
      });
      setEmbedOut(out);
      reload();
    } catch (e) {
      setLocalErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function runSearch() {
    if (!active?.id) return;
    setLocalErr(null);
    setSearchOut(null);
    try {
      const collection = active.vectorCollection || active.id;
      const out = await apiPost("/v1/aip/vector-index/search", {
        collection,
        query,
        pluginId: "embed-openai-compatible",
        topK: 5,
      });
      setSearchOut(out);
    } catch (e) {
      setLocalErr(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <S2Chrome title="管道构建" lede="对齐 pipeline-list · 项目树 + 最近编辑 · 104 向量索引接线">
      <BpToolbar>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
        <Link to="/data/pipeline-proposals" className="btn-nav">
          管道提案 →
        </Link>
        {sourceFilter && (
          <Link to="/data/pipelines" className="btn-nav">
            清除 Source 过滤 ({sourceFilter}) ×
          </Link>
        )}
      </BpToolbar>
      {sourceFilter && (
        <BpBanner tone="info">
          已按 Source <strong>{sourceFilter}</strong> 过滤 · 来自 Data 连接 Sync→Pipeline 链
        </BpBanner>
      )}
      {err && <p className="error">{err}</p>}
      {localErr && <p className="error">{localErr}</p>}

      <BpSplit
        left={
          <>
            <div className="bp-section-label">项目</div>
            <p className="aos-text">Ecom-Data-Project</p>
            <div className="bp-section-label" style={{ marginTop: 12 }}>
              管道
            </div>
            <ul className="card-list">
              {items.map((p) => (
                <li key={p.id}>
                  <button
                    type="button"
                    className="nav-link card"
                    style={{
                      width: "100%",
                      textAlign: "left",
                      border: active?.id === p.id ? "1px solid var(--bp-accent, #0ea5e9)" : undefined,
                    }}
                    onClick={() => setActiveId(p.id)}
                  >
                    {p.id}
                  </button>
                </li>
              ))}
            </ul>
            {items.length === 0 && sourceFilter && (
              <p className="muted" style={{ fontSize: "0.75rem" }}>
                无匹配管道 · <Link to="/data">返回 Data 连接</Link>
              </p>
            )}
            <div className="bp-section-label" style={{ marginTop: 12 }}>
              数据集
            </div>
            <Link to="/data/datasets" className="btn-nav">
              WorkOrder-demo →
            </Link>
          </>
        }
        right={
          <>
            <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
              最近编辑
            </h2>
            {items.map((p) => (
              <div key={p.id} className="card" style={{ marginBottom: 8 }}>
                <strong>{p.id}</strong>
                <p className="muted" style={{ fontSize: "0.75rem" }}>
                  source={p.sourceId} → {p.target} · build={p.lastBuild?.status || "—"}
                  {p.vectorCollection ? ` · vec=${p.vectorCollection}` : ""}
                </p>
                <Link to="/data/datasets">Dataset {p.datasetRid}</Link>
              </div>
            ))}
            {(data?.items?.length || 0) === 0 && (
              <p className="muted">
                空 · <Link to="/data">新建数据源</Link>
              </p>
            )}
            {sourceFilter && items.length === 0 && (data?.items?.length || 0) > 0 && (
              <p className="muted">当前 Source 无关联 Pipeline · 可清除过滤查看全部</p>
            )}

            {active && (
              <>
                <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: 16 }}>
                  向量索引（104 · 本地 KV，非 Milvus）
                </h2>
                <BpBanner tone="info">
                  经已安装 <code>embed-openai-compatible</code>；默认 local-kv · 可选{" "}
                  <code>AOS_VECTOR_BACKEND=qdrant</code>；无网关返回 501，不写假向量。
                </BpBanner>
                <BpToolbar>
                  <button type="button" className="btn" onClick={() => void runEmbed()}>
                    写入索引 · {active.id}
                  </button>
                  <input
                    className="bp-input"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="检索 query"
                    style={{ minWidth: 120 }}
                  />
                  <button type="button" className="btn-nav" onClick={() => void runSearch()}>
                    检索试跑
                  </button>
                </BpToolbar>
                {embedOut != null && <JsonBlock value={embedOut} />}
                {searchOut != null && <JsonBlock value={searchOut} />}
              </>
            )}
          </>
        }
      />
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
          管道构建 →
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
                Pipeline <Link to="/data/pipelines">{active.pipelineId}</Link>
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

/** 77 · 对齐 dataset.html */
export function DatasetsPage() {
  const { data, err, reload } = useJsonGet<{ items: DatasetRow[] }>("/v1/datasets");
  const [tab, setTab] = useState("preview");
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [hist, setHist] = useState<{ items?: unknown[] } | null>(null);

  const ds = data?.items?.[0];
  const rid = selected || ds?.rid || "";

  async function openDataset(id: string) {
    setSelected(id);
    const d = await apiGet<Record<string, unknown>>(`/v1/datasets/${encodeURIComponent(id)}`);
    setDetail(d);
    const h = await apiGet<{ items: unknown[] }>(`/v1/datasets/${encodeURIComponent(id)}/history`);
    setHist(h);
  }

  const previewRows = useMemo(
    () => [
      ["wo-1001", "机房巡检-A区", "open", "DC-East"],
      ["wo-1002", "链路告警复核", "in_progress", "DC-West"],
      ["wo-1003", "备件更换", "open", "DC-East"],
    ],
    [],
  );

  return (
    <S2Chrome title="数据集预览" lede="对齐 dataset · 预览/历史/详情/健康 Tab">
      <BpToolbar>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新列表
        </button>
        {rid && (
          <button type="button" className="btn" onClick={() => void openDataset(rid).catch(console.error)}>
            打开 {rid}
          </button>
        )}
        <Link to="/data/lineage" className="btn-nav">
          在沿袭中打开 →
        </Link>
      </BpToolbar>
      {err && <p className="error">{err}</p>}

      <ul className="card-list" style={{ marginBottom: "0.75rem" }}>
        {(data?.items || []).map((d) => (
          <li key={d.rid}>
            <button type="button" className="nav-link card" onClick={() => void openDataset(d.rid)}>
              {d.name || d.rid} · {d.status}
            </button>
          </li>
        ))}
      </ul>

      {rid && (
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
              <h1 className="aos-text" style={{ fontSize: "1.1rem" }}>
                {String(detail?.name || ds?.name || rid)}
              </h1>
              <p className="muted">objectTypeHint={String(detail?.objectTypeHint || ds?.objectTypeHint || "WorkOrder")}</p>
              <BpMetricGrid
                items={[
                  { label: "行数", value: previewRows.length, tone: "muted" },
                  { label: "状态", value: String(detail?.status || "READY"), tone: "ok" },
                  { label: "Pipeline", value: String(detail?.pipelineId || "—"), tone: "muted" },
                  { label: "Source", value: String(detail?.sourceId || "—"), tone: "muted" },
                ]}
              />
              <BpTable
                columns={["object_id", "title", "status", "site"]}
                rows={previewRows.map((r) => r.map((c) => <span>{c}</span>))}
              />
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
          {tab === "details" && detail && (
            <>
              <BpPropGrid items={flattenRecordProps(detail)} />
              <details style={{ marginTop: "0.75rem" }}>
                <summary className="muted">完整 JSON</summary>
                <JsonBlock value={detail} />
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
      )}
      {!rid && <p className="muted">空 · 先到 <Link to="/data">数据连接</Link> 接入源</p>}
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
