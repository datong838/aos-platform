import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost } from "../api/client";
import { PageChrome } from "../components/PageChrome";
import {
  BpBanner,
  BpLinkRow,
  BpMetricGrid,
  BpPropGrid,
  BpStagePipeline,
  BpTable,
  BpTabs,
  BpToolbar,
} from "./s2/blueprintUi";

type DatasetRow = {
  rid?: string;
  name?: string;
  status?: string;
  pipelineId?: string;
  objectTypeHint?: string;
};

type BuildRow = {
  id?: string;
  status?: string;
  pipelineId?: string;
};

type DlqRow = {
  id?: string;
  status?: string;
  reason?: string;
  pipelineId?: string;
};

type RouteOut = {
  route: string;
  sizeBytes: number;
  threshold: number;
  reason?: string;
  target?: string | null;
};

type SourceRow = { id?: string; type?: string; status?: string };
type SyncRow = { id?: string; sourceId?: string; status?: string };
type PipelineRow = { id?: string; sourceId?: string; status?: string };

/** 100 · data hub + Source 向导 · Hub live 指标 + L1 链路态 */
export function DataPage() {
  const [tab, setTab] = useState("hub");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [datasets, setDatasets] = useState<DatasetRow[]>([]);
  const [builds, setBuilds] = useState<BuildRow[]>([]);
  const [dlq, setDlq] = useState<DlqRow[]>([]);
  const [sources, setSources] = useState<SourceRow[]>([]);
  const [syncs, setSyncs] = useState<SyncRow[]>([]);
  const [pipelines, setPipelines] = useState<PipelineRow[]>([]);
  const [mediaCount, setMediaCount] = useState(0);
  const [workOrders, setWorkOrders] = useState(0);
  const [selectedSource, setSelectedSource] = useState<SourceRow | null>(null);
  const [sizeKb, setSizeKb] = useState("64");
  const [target, setTarget] = useState("dataset");
  const [routeOut, setRouteOut] = useState<RouteOut | null>(null);
  const [newSourceId, setNewSourceId] = useState("");
  const [connectorType, setConnectorType] = useState("file");
  const [wizardStep, setWizardStep] = useState(1);

  async function refresh() {
    const [ds, b, d, src, syn, pipes, media, story] = await Promise.all([
      apiGet<{ items: DatasetRow[] }>("/v1/datasets"),
      apiGet<{ items: BuildRow[] }>("/v1/builds"),
      apiGet<{ items: DlqRow[] }>("/v1/dlq"),
      apiGet<{ items: SourceRow[] }>("/v1/sources"),
      apiGet<{ items: SyncRow[] }>("/v1/syncs"),
      apiGet<{ items: PipelineRow[] }>("/v1/pipelines"),
      apiGet<{ items: unknown[] }>("/v1/media-sets"),
      apiGet<{ snapshot?: { objectCount?: number } }>("/v1/demo/story"),
    ]);
    setDatasets(ds.items || []);
    setBuilds(b.items || []);
    setDlq(d.items || []);
    setSources(src.items || []);
    setSyncs(syn.items || []);
    setPipelines(pipes.items || []);
    setMediaCount((media.items || []).length);
    setWorkOrders(story.snapshot?.objectCount ?? 0);
    if (selectedSource?.id) {
      const found = (src.items || []).find((s) => s.id === selectedSource.id);
      if (found) setSelectedSource(found);
    }
  }

  useEffect(() => {
    refresh().catch((e) => setErr(String(e.message || e)));
  }, []);

  async function ensureSeed() {
    setErr(null);
    try {
      await apiPost("/v1/demo/ensure-seed", {});
      setMsg("业务数据已初始化 · Dataset/Build/DLQ 可指屏");
      await refresh();
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  async function demoPipeline() {
    setErr(null);
    try {
      await apiPost("/v1/sources", { id: "file-ui", type: "file" });
      const media = await apiPost<{ rid: string }>("/v1/media-sets", {
        name: "ui-clip.bin",
        bytesBase64: "dWk=",
      });
      await apiPost("/v1/pipelines", { id: "ui-p1", sourceId: "file-ui" });
      await apiPost("/v1/schedules", { id: "ui-sch", pipelineId: "ui-p1" });
      setMsg(`现场 Pipeline OK · Media ${media.rid}`);
      await refresh();
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  async function probeRoute() {
    setErr(null);
    try {
      const sizeBytes = Math.max(0, Math.round(Number(sizeKb) * 1024));
      const out = await apiPost<RouteOut>("/v1/sync-routing", { sizeBytes, target });
      setRouteOut(out);
      setMsg(`Router → ${out.route}${out.reason ? ` · ${out.reason}` : ""}`);
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  async function createFromRoute() {
    setErr(null);
    try {
      const sizeBytes = Math.max(0, Math.round(Number(sizeKb) * 1024));
      const routed = await apiPost<RouteOut>("/v1/sync-routing", { sizeBytes, target });
      setRouteOut(routed);
      const sid = `src-router-${Date.now().toString(36)}`;
      await apiPost("/v1/sources", { id: sid, type: "file" });
      const sync = await apiPost<{ id: string }>("/v1/syncs", { sourceId: sid });
      setMsg(`已建 source=${sid} · sync=${sync.id} · route=${routed.route}`);
      await refresh();
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  async function createSource() {
    const id = newSourceId.trim() || `src-${Date.now().toString(36)}`;
    setErr(null);
    try {
      await apiPost("/v1/sources", { id, type: connectorType });
      setMsg(`已创建 Source ${id}`);
      setNewSourceId("");
      setWizardStep(4);
      await refresh();
      setSelectedSource({ id, type: connectorType, status: "active" });
      setTab("detail");
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  const linkedSyncs = syncs.filter((s) => s.sourceId === selectedSource?.id);
  const linkedPipelines = pipelines.filter((p) => p.sourceId === selectedSource?.id);
  const seedReady = datasets.length > 0 && workOrders > 0;

  const pipelineLinkForSource = (sourceId?: string) =>
    sourceId ? `/data/pipelines?sourceId=${encodeURIComponent(sourceId)}` : "/data/pipelines";

  const l1Stages = [
    {
      step: "① Connector",
      title: `Sources · ${sources.length}`,
      subtitle: "file / jdbc · 注册入口",
      status: sources.length > 0 ? "已接入" : "待建",
      tone: (sources.length > 0 ? "done" : "wait") as "done" | "wait",
      href: sources.length ? "#data-sources" : undefined,
      linkLabel: "Sources 列表 →",
    },
    {
      step: "② Sync",
      title: `Sync Jobs · ${syncs.length}`,
      subtitle: "Source → 路由 · sync-routing",
      status: syncs.length > 0 ? "运行中" : "—",
      tone: (syncs.length > 0 ? "done" : "wait") as "done" | "wait",
      href: syncs.length ? "#data-syncs" : undefined,
      linkLabel: "Sync 列表 →",
    },
    {
      step: "③ Pipeline",
      title: `Pipelines · ${pipelines.length} · Builds ${builds.length}`,
      subtitle: `Datasets ${datasets.length} · DLQ ${dlq.length}`,
      status: datasets.length > 0 ? "有产物" : "待 seed",
      tone: (datasets.length > 0 ? "active" : "wait") as "active" | "wait",
      href: "/data/pipelines",
      linkLabel: "管道构建 →",
    },
    {
      step: "④ 故事",
      title: `WorkOrder · ${workOrders}`,
      subtitle: "Ontology 实例 · Inbox/Buddy 同源",
      status: workOrders > 0 ? "可演示" : "初始化业务数据",
      tone: (workOrders > 0 ? "done" : "wait") as "done" | "wait",
    },
  ];

  return (
    <PageChrome title="数据连接" lede="Sources/Syncs + Storage Router · 对齐 data-connection / source-new">
      <BpToolbar>
        <button type="button" className="btn" onClick={() => void ensureSeed()}>
          初始化业务数据
        </button>
        <button type="button" className="btn" onClick={() => void demoPipeline()}>
          再跑一趟文件 Pipeline
        </button>
        <button type="button" className="btn" onClick={() => void refresh().catch((e) => setErr(String(e)))}>
          刷新
        </button>
      </BpToolbar>

      <BpTabs
        tabs={[
          { id: "hub", label: "连接 Hub" },
          { id: "new", label: "新建 Source" },
          { id: "detail", label: "Source 详情" },
        ]}
        active={tab}
        onChange={setTab}
      />

      {msg && <p className="aos-text">{msg}</p>}
      {err && <p className="error">{err}</p>}

      {tab === "hub" && (
        <>
          {!seedReady && (
            <BpBanner tone="warn">
              L1 故事未就绪（Dataset 或 WorkOrder 为 0）· 点上方「初始化业务数据」后再指屏演示。
            </BpBanner>
          )}

          <BpMetricGrid
            items={[
              { label: "Sources", value: sources.length, tone: sources.length ? "ok" : "warn" },
              { label: "Syncs", value: syncs.length, tone: "muted" },
              { label: "Pipelines", value: pipelines.length, tone: "muted" },
              { label: "Datasets", value: datasets.length, tone: datasets.length ? "ok" : "warn" },
              { label: "Builds", value: builds.length, tone: "muted" },
              { label: "DLQ", value: dlq.length, tone: dlq.length ? "warn" : "ok" },
              { label: "MediaSets", value: mediaCount, tone: "muted" },
              { label: "WorkOrder", value: workOrders, tone: workOrders ? "ok" : "warn" },
            ]}
          />

          <div style={{ marginTop: "1rem" }}>
            <div className="bp-ws-section-title">L1 链路态</div>
            <BpStagePipeline stages={l1Stages} />
          </div>

          <BpLinkRow
            links={[
              { to: "/data/datasets", label: "Datasets" },
              { to: "/data/schedules", label: "计划编辑器" },
              { to: "/data/builds", label: "Builds" },
              { to: "/data/health", label: "健康" },
            ]}
          />

          <div className="bp-object-panel" style={{ marginTop: "1rem" }}>
            <div className="bp-ws-section-title">Storage Router（sync-routing）</div>
            <div className="filter-bar">
              <label className="muted">
                大小 KB{" "}
                <input value={sizeKb} onChange={(e) => setSizeKb(e.target.value)} style={{ width: 72 }} />
              </label>
              <label className="muted">
                目标{" "}
                <select value={target} onChange={(e) => setTarget(e.target.value)}>
                  <option value="dataset">Dataset</option>
                  <option value="mediaset">MediaSet</option>
                  <option value="stream">Stream</option>
                </select>
              </label>
              <button type="button" className="btn" onClick={() => void probeRoute()}>
                探测路由
              </button>
              <button type="button" className="btn" onClick={() => void createFromRoute()}>
                按路由建 Source+Sync
              </button>
            </div>
            {routeOut && (
              <BpPropGrid
                items={[
                  { label: "route", value: routeOut.route },
                  { label: "sizeBytes", value: String(routeOut.sizeBytes) },
                  { label: "threshold", value: String(routeOut.threshold) },
                  { label: "reason", value: routeOut.reason || "—" },
                ]}
              />
            )}
          </div>

          <div className="canvas-grid" style={{ marginTop: "1rem" }}>
            <div id="data-sources">
              <div className="bp-ws-section-title">Sources（{sources.length}）</div>
              <BpTable
                columns={["id", "type", "status", ""]}
                rows={
                  sources.length
                    ? sources.map((s) => [
                        s.id,
                        s.type,
                        s.status || "—",
                        <button
                          key={String(s.id)}
                          type="button"
                          className="nav-link"
                          onClick={() => {
                            setSelectedSource(s);
                            setTab("detail");
                          }}
                        >
                          详情
                        </button>,
                      ])
                    : [["—", "—", "—", ""]]
                }
              />
            </div>
            <div id="data-syncs">
              <div className="bp-ws-section-title">Syncs（{syncs.length}）</div>
              <BpTable
                columns={["id", "sourceId", "status", ""]}
                rows={
                  syncs.length
                    ? syncs.map((s) => [
                        s.id,
                        s.sourceId,
                        s.status || "—",
                        <Link key={String(s.id)} to={pipelineLinkForSource(s.sourceId)} className="nav-link">
                          Pipeline →
                        </Link>,
                      ])
                    : [["—", "—", "—", ""]]
                }
              />
            </div>
          </div>

          <div className="bp-ws-section-title" style={{ marginTop: "1rem" }}>
            Datasets / Builds / DLQ
          </div>
          <BpTable
            columns={["Dataset", "status", "pipeline"]}
            rows={datasets.map((d) => [d.name || d.rid, d.status, d.pipelineId || "—"])}
          />
          <BpTable
            columns={["Build", "status", "pipeline"]}
            rows={builds.map((b) => [b.id, b.status, b.pipelineId || "—"])}
          />
          {dlq.length > 0 && (
            <BpTable
              columns={["DLQ", "status", "reason"]}
              rows={dlq.map((row) => [row.id, row.status, row.reason || "—"])}
            />
          )}
        </>
      )}

      {tab === "new" && (
        <div className="bp-object-panel">
          <div className="bp-ws-section-title">新建数据源 · 4 步向导</div>
          <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem", fontSize: "0.75rem" }}>
            {[1, 2, 3, 4].map((n) => (
              <span
                key={n}
                className={`bp-tag${wizardStep >= n ? " bp-tag-ok" : ""}`}
                style={{ borderRadius: "999px", padding: "0.2rem 0.5rem" }}
              >
                {n}. {["连接器", "运行时", "连接", "凭证"][n - 1]}
              </span>
            ))}
          </div>

          {wizardStep === 1 && (
            <>
              <p className="muted" style={{ fontSize: "0.875rem" }}>
                P0 文件类型优先 · P1 JDBC/MySQL 结构化入库
              </p>
              <div className="bp-discover-grid">
                {[
                  { id: "file", title: "文件 · 文档", desc: "Word · Excel · PDF · csv", tone: "violet" as const },
                  { id: "jdbc", title: "JDBC · MySQL", desc: "结构化入库 · T4.6", tone: "muted" as const },
                ].map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    className={`bp-discover-card bp-discover-${c.tone}`}
                    style={{
                      cursor: "pointer",
                      textAlign: "left",
                      borderColor: connectorType === c.id ? "rgba(56,189,248,0.5)" : undefined,
                    }}
                    onClick={() => setConnectorType(c.id)}
                  >
                    <div className="bp-discover-title">{c.title}</div>
                    <p className="bp-discover-meta">{c.desc}</p>
                  </button>
                ))}
              </div>
              <button type="button" className="btn" style={{ marginTop: 8 }} onClick={() => setWizardStep(2)}>
                下一步 →
              </button>
            </>
          )}

          {wizardStep >= 2 && wizardStep < 4 && (
            <>
              <BpBanner tone="info">
                步骤 {wizardStep} · 运行时/连接（MVP 默认 local agent · 凭证 vault ref 后置）
              </BpBanner>
              <label className="muted" style={{ display: "block", marginTop: 8 }}>
                Source id{" "}
                <input
                  value={newSourceId}
                  onChange={(e) => setNewSourceId(e.target.value)}
                  placeholder="prod-mysql-orders"
                />
              </label>
              <BpToolbar>
                <button type="button" className="btn" onClick={() => setWizardStep((s) => Math.max(1, s - 1))}>
                  上一步
                </button>
                <button type="button" className="btn" onClick={() => setWizardStep((s) => s + 1)}>
                  下一步
                </button>
              </BpToolbar>
            </>
          )}

          {wizardStep >= 4 && (
            <>
              <BpPropGrid
                items={[
                  { label: "连接器", value: connectorType },
                  { label: "运行时", value: "local-agent" },
                  { label: "凭证", value: "vault://data/sources#ref" },
                ]}
              />
              <button type="button" className="btn" onClick={() => void createSource()}>
                创建 Source
              </button>
            </>
          )}
        </div>
      )}

      {tab === "detail" && (
        <div className="bp-object-panel">
          {selectedSource ? (
            <>
              <div className="bp-object-title">{selectedSource.id}</div>
              <BpPropGrid
                items={[
                  { label: "type", value: selectedSource.type || "—" },
                  { label: "status", value: selectedSource.status || "—" },
                  { label: "Sync 数", value: String(linkedSyncs.length) },
                ]}
              />
              <div className="bp-ws-section-title">关联 Sync</div>
              <BpTable
                columns={["syncId", "status", ""]}
                rows={
                  linkedSyncs.length
                    ? linkedSyncs.map((s) => [
                        s.id,
                        s.status || "—",
                        <Link key={String(s.id)} to={pipelineLinkForSource(s.sourceId)} className="nav-link">
                          Pipeline →
                        </Link>,
                      ])
                    : [["—", "—", ""]]
                }
              />
              <div className="bp-ws-section-title">关联 Pipeline</div>
              <BpTable
                columns={["pipelineId", "status", ""]}
                rows={
                  linkedPipelines.length
                    ? linkedPipelines.map((p) => [
                        p.id,
                        p.status || "—",
                        <span key={String(p.id)}>
                          <Link to="/data/pipelines" className="nav-link">
                            管道
                          </Link>
                          {" · "}
                          <Link to="/data/builds" className="nav-link">
                            Builds
                          </Link>
                          {" · "}
                          <Link to="/data/datasets" className="nav-link">
                            Datasets
                          </Link>
                        </span>,
                      ])
                    : [["—", "—", ""]]
                }
              />
              <BpLinkRow
                links={[
                  { to: pipelineLinkForSource(selectedSource.id), label: "按 Source 过滤管道" },
                  { to: "/data/datasets", label: "Datasets" },
                ]}
              />
            </>
          ) : (
            <p className="muted">请从 Hub 表或新建 Source 后选择一条记录</p>
          )}
        </div>
      )}
    </PageChrome>
  );
}
