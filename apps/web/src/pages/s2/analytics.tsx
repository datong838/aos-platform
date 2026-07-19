import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost, JsonBlock, S2Chrome, useJsonGet } from "./shared";
import { BpBanner, BpLinkRow, BpTable, BpToolbar } from "./blueprintUi";

type Health = {
  status?: string;
  sidecar?: string;
  notebookUi?: string;
  mode?: string;
  detail?: string;
  sessionsCapable?: boolean;
};

type SessionRow = {
  id?: string;
  status?: string;
  uiUrl?: string;
  ticketExpiresAt?: string;
  objectType?: string;
};

type RailInstance = { id?: string; kind?: string; snippet?: string };
type RailType = {
  id?: string;
  name?: string;
  kind?: string;
  snippet?: string;
  instances?: RailInstance[];
};
type RailDataset = {
  rid?: string;
  name?: string;
  kind?: string;
  snippet?: string;
  objectTypeHint?: string;
};
type OntologyRail = {
  mode?: string;
  objectTypes?: RailType[];
  datasets?: RailDataset[];
};

type ReadResult = {
  mode?: string;
  kind?: string;
  columns?: string[];
  rows?: Record<string, unknown>[];
  total?: number;
  source?: string;
  detail?: string;
  objectType?: string;
  datasetRid?: string;
  governance?: {
    redactionApplied?: boolean;
    exportPolicy?: string;
    redactedFieldUnion?: string[];
  };
};

type DraftPropose = {
  id?: string;
  status?: string;
  productionWritten?: boolean;
  approvePath?: string;
  mode?: string;
  message?: string;
  objectId?: string;
};

type LineageItem = {
  id?: string;
  draftId?: string;
  actionTypeId?: string;
  uiPath?: string;
};

type ContourBucket = { key?: string; count?: number; share?: number };
type ContourExplore = {
  mode?: string;
  scheme?: string;
  groupBy?: string;
  groupByOptions?: string[];
  buckets?: ContourBucket[];
  totalRows?: number;
  disclaimer?: string;
};
type QuiverPoint = { t?: string; v?: number };
type QuiverSeries = {
  mode?: string;
  scheme?: string;
  points?: QuiverPoint[];
  metric?: string;
  maxV?: number;
  fillGaps?: boolean;
  note?: string;
  disclaimer?: string;
};
type VertexExp = {
  id?: string;
  name?: string;
  objectType?: string;
  metrics?: Record<string, unknown>;
  mediaRid?: string | null;
  status?: string;
  createdAt?: string;
};

/** 分析建模产品页 · 读数 / Draft / 治理 / 探索 · 对齐 75 去端面壳 */
export function AnalyticsPage() {
  const health = useJsonGet<Health>("/v1/analytics/health");
  const sessions = useJsonGet<{ items?: SessionRow[] }>("/v1/notebooks/sessions");
  const rail = useJsonGet<OntologyRail>("/v1/analytics/ontology-rail");
  const [createErr, setCreateErr] = useState<string | null>(null);
  const [sqlErr, setSqlErr] = useState<string | null>(null);
  const [readErr, setReadErr] = useState<string | null>(null);
  const [draftErr, setDraftErr] = useState<string | null>(null);
  const [exportErr, setExportErr] = useState<string | null>(null);
  const [lineageErr, setLineageErr] = useState<string | null>(null);
  const [lastCreated, setLastCreated] = useState<SessionRow | null>(null);
  const [cell, setCell] = useState("# 分析单元格 · 点击左侧 Ontology 插入片段\n");
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [selectedDataset, setSelectedDataset] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [copyHint, setCopyHint] = useState<string | null>(null);
  const [readResult, setReadResult] = useState<ReadResult | null>(null);
  const [wbObjectId, setWbObjectId] = useState("wo-1001");
  const [wbStatus, setWbStatus] = useState("closed");
  const [wbReason, setWbReason] = useState("analysis-writeback");
  const [lastDraft, setLastDraft] = useState<DraftPropose | null>(null);
  const [exportResult, setExportResult] = useState<ReadResult | null>(null);
  const [lineageItems, setLineageItems] = useState<LineageItem[]>([]);
  const [subsetTab, setSubsetTab] = useState<"contour" | "quiver" | "vertex">("contour");
  const [contour, setContour] = useState<ContourExplore | null>(null);
  const [quiver, setQuiver] = useState<QuiverSeries | null>(null);
  const [vertexItems, setVertexItems] = useState<VertexExp[]>([]);
  const [subsetErr, setSubsetErr] = useState<string | null>(null);
  const [vxName, setVxName] = useState("wo-risk-baseline");
  const [vxMetric, setVxMetric] = useState("0.82");
  const [vxMediaRid, setVxMediaRid] = useState("");
  const [contourGroupBy, setContourGroupBy] = useState("status");

  const types = rail.data?.objectTypes ?? [];
  const datasets = rail.data?.datasets ?? [];

  function appendSnippet(snippet: string | undefined, typeId?: string, datasetRid?: string) {
    if (!snippet) return;
    setCell((prev) => {
      const base = prev.trimEnd();
      const sep = base ? "\n\n" : "";
      return `${base}${sep}${snippet}`;
    });
    if (typeId) setSelectedType(typeId);
    if (datasetRid) setSelectedDataset(datasetRid);
    setCopyHint(null);
  }

  async function tryCreateSession() {
    setCreateErr(null);
    try {
      const row = await apiPost<SessionRow>("/v1/notebooks/sessions", {
        objectType: selectedType || "WorkOrder",
        purpose: "explore",
        ...(selectedDataset ? { datasetRid: selectedDataset } : {}),
      });
      setLastCreated(row);
      sessions.reload();
    } catch (e) {
      setCreateErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function tryRead() {
    setReadErr(null);
    setReadResult(null);
    try {
      let result: ReadResult;
      if (selectedDataset) {
        result = await apiPost<ReadResult>("/v1/analytics/datasets/preview", {
          datasetRid: selectedDataset,
          limit: 20,
        });
      } else {
        const ot = selectedType || "WorkOrder";
        result = await apiPost<ReadResult>("/v1/analytics/objects/list", {
          objectType: ot,
          limit: 20,
        });
        setSelectedType(ot);
      }
      setReadResult(result);
      const firstId = result.rows?.[0]?.id;
      if (typeof firstId === "string" && firstId) setWbObjectId(firstId);
      if (result.objectType) setSelectedType(result.objectType);
    } catch (e) {
      setReadErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function tryExport() {
    setExportErr(null);
    setExportResult(null);
    try {
      const body: Record<string, unknown> = { format: "json", limit: 20 };
      if (selectedDataset) body.datasetRid = selectedDataset;
      else body.objectType = selectedType || "WorkOrder";
      const result = await apiPost<ReadResult>("/v1/analytics/export", body);
      setExportResult(result);
    } catch (e) {
      setExportErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function tryLineage() {
    setLineageErr(null);
    setLineageItems([]);
    try {
      const ot = encodeURIComponent(selectedType || "WorkOrder");
      const oid = encodeURIComponent(wbObjectId.trim() || "wo-1001");
      const result = await apiGet<{ items?: LineageItem[] }>(
        `/v1/analytics/lineage?objectType=${ot}&objectId=${oid}&limit=5`,
      );
      setLineageItems(result.items || []);
    } catch (e) {
      setLineageErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function tryProposeDraft() {
    setDraftErr(null);
    setLastDraft(null);
    try {
      const ot = selectedType || "WorkOrder";
      const key = `analytics-wb-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      const row = await apiPost<DraftPropose>(
        "/v1/analytics/writeback/propose",
        {
          objectType: ot,
          objectId: wbObjectId.trim(),
          actionTypeId: "CloseWorkOrder",
          autoApprove: false,
          analysisNote: wbReason.trim(),
          proposed: {
            reason: wbReason.trim(),
            status: wbStatus.trim() || "closed",
          },
          title: `分析写回 · ${ot}/${wbObjectId.trim()}`,
        },
        { "Idempotency-Key": key },
      );
      setLastDraft(row);
    } catch (e) {
      setDraftErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function tryContour(groupByOverride?: string) {
    setSubsetErr(null);
    try {
      const ot = encodeURIComponent(selectedType || "WorkOrder");
      const gb = encodeURIComponent(groupByOverride || contourGroupBy || "status");
      const row = await apiGet<ContourExplore>(
        `/v1/analytics/contour/explore?objectType=${ot}&groupBy=${gb}&limit=200`,
      );
      setContour(row);
      if (row.groupBy) setContourGroupBy(row.groupBy);
      setSubsetTab("contour");
    } catch (e) {
      setSubsetErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function tryQuiver() {
    setSubsetErr(null);
    try {
      const ot = encodeURIComponent(selectedType || "WorkOrder");
      const row = await apiGet<QuiverSeries>(
        `/v1/analytics/quiver/series?objectType=${ot}&limitDays=14&fillGaps=true`,
      );
      setQuiver(row);
      setSubsetTab("quiver");
    } catch (e) {
      setSubsetErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function tryVertexList() {
    setSubsetErr(null);
    try {
      const row = await apiGet<{ items?: VertexExp[] }>(
        "/v1/analytics/vertex/experiments?limit=20",
      );
      setVertexItems(row.items || []);
      setSubsetTab("vertex");
    } catch (e) {
      setSubsetErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function tryVertexCreate() {
    setSubsetErr(null);
    try {
      const score = Number(vxMetric);
      await apiPost("/v1/analytics/vertex/experiments", {
        name: vxName.trim() || "exp",
        objectType: selectedType || "WorkOrder",
        params: { source: "analytics-159" },
        metrics: { score: Number.isFinite(score) ? score : 0 },
        ...(vxMediaRid.trim() ? { mediaRid: vxMediaRid.trim() } : {}),
        note: "experiment registry",
      });
      await tryVertexList();
    } catch (e) {
      setSubsetErr(e instanceof Error ? e.message : String(e));
    }
  }

  const quiverSpark = useMemo(() => {
    const pts = quiver?.points || [];
    if (!pts.length) return null;
    const max = Math.max(1, quiver?.maxV ?? Math.max(...pts.map((p) => Number(p.v) || 0), 0));
    const w = 280;
    const h = 56;
    const n = pts.length;
    const coords = pts.map((p, i) => {
      const x = n <= 1 ? 0 : (i / (n - 1)) * w;
      const y = h - ((Number(p.v) || 0) / max) * (h - 4) - 2;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
    return { w, h, polyline: coords.join(" "), max };
  }, [quiver]);

  async function trySqlPreview() {
    setSqlErr(null);
    setReadResult(null);
    try {
      const body: Record<string, unknown> = {
        sql: selectedType || selectedDataset ? "select *" : "select 1",
        limit: 20,
      };
      if (selectedDataset) body.datasetRid = selectedDataset;
      if (selectedType) body.objectType = selectedType;
      const result = await apiPost<ReadResult>("/v1/analytics/sql/preview", body);
      setReadResult(result);
    } catch (e) {
      setSqlErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function copyCell() {
    try {
      await navigator.clipboard.writeText(cell);
      setCopyHint("已复制到剪贴板");
    } catch {
      setCopyHint("复制失败（浏览器权限）");
    }
  }

  const h = health.data;
  const items = sessions.data?.items ?? [];
  const layout = useMemo(
    () =>
      ({
        display: "grid",
        gridTemplateColumns: "minmax(220px, 280px) 1fr",
        gap: "1rem",
        alignItems: "start",
        marginTop: 12,
      }) as const,
    [],
  );

  return (
    <S2Chrome
      title="分析建模"
      lede="读 Ontology / Dataset · 提交 Draft 写回 · Marking 治理 · 探索分析"
    >
      <BpToolbar>
        <button type="button" className="btn" onClick={() => { health.reload(); rail.reload(); }}>
          刷新
        </button>
        <button type="button" className="btn" onClick={() => void tryRead()}>
          读数
        </button>
        <button type="button" className="btn" onClick={() => void tryExport()}>
          导出
        </button>
        <button type="button" className="btn-nav" onClick={() => void tryLineage()}>
          查谱系
        </button>
        <button type="button" className="btn" onClick={() => void tryProposeDraft()}>
          提交为 Draft
        </button>
        <button type="button" className="btn-nav" onClick={() => void tryContour()}>
          分组探索
        </button>
        <button type="button" className="btn-nav" onClick={() => void tryQuiver()}>
          时序
        </button>
        <button type="button" className="btn-nav" onClick={() => void tryVertexList()}>
          实验登记
        </button>
        <button type="button" className="btn-nav" onClick={() => void tryCreateSession()}>
          创建会话
        </button>
        <button type="button" className="btn-nav" onClick={() => void trySqlPreview()}>
          SQL 预览
        </button>
        <Link to="/aip/drafts" className="btn-nav-accent">
          Draft 审批台 →
        </Link>
        <Link to="/aip/lineage" className="btn-nav">
          决策谱系 →
        </Link>
        <Link to="/workshop/canvas" className="btn-nav">
          工作台画布 →
        </Link>
      </BpToolbar>

      <BpBanner tone="info">
        写回须经 Draft 审批台批准后落库；本页不可自批。含 Marking 脱敏字段时导出将被拒绝。
        分组 / 时序 / 实验为探索子集（[159] 加深），不等于完整 BI / ML 平台，亦不捆绑 Superset/Metabase/Grafana。
      </BpBanner>

      {health.err && <p className="error">{health.err}</p>}
      {rail.err && <p className="error">rail: {rail.err}</p>}
      {createErr && <p className="error">create: {createErr}</p>}
      {readErr && <p className="error">read: {readErr}</p>}
      {exportErr && <p className="error">export: {exportErr}</p>}
      {lineageErr && <p className="error">lineage: {lineageErr}</p>}
      {draftErr && <p className="error">draft: {draftErr}</p>}
      {subsetErr && <p className="error">explore: {subsetErr}</p>}
      {sqlErr && <p className="error">sql: {sqlErr}</p>}

      <div style={layout}>
        <aside
          style={{
            border: "1px solid var(--aos-border, #2a3540)",
            padding: "0.75rem",
            minHeight: 320,
          }}
        >
          <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: 0 }}>
            Ontology
          </h2>
          <p className="muted" style={{ fontSize: "0.7rem" }}>
            type={selectedType || "—"} · dataset={selectedDataset || "—"}
          </p>
          <ul style={{ listStyle: "none", padding: 0, margin: "0.5rem 0 0" }}>
            {types.map((t) => {
              const tid = t.id || "";
              const open = Boolean(expanded[tid]);
              return (
                <li key={tid} style={{ marginBottom: 6 }}>
                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                    <button
                      type="button"
                      className="btn-nav"
                      style={{ fontSize: "0.75rem" }}
                      onClick={() => setExpanded((e) => ({ ...e, [tid]: !open }))}
                    >
                      {open ? "▾" : "▸"}
                    </button>
                    <button
                      type="button"
                      className="btn"
                      style={{ fontSize: "0.75rem" }}
                      onClick={() => {
                        setSelectedDataset(null);
                        appendSnippet(t.snippet, tid);
                      }}
                    >
                      {t.name || tid}
                    </button>
                  </div>
                  {open && (
                    <ul style={{ listStyle: "none", padding: "4px 0 0 1rem", margin: 0 }}>
                      {(t.instances || []).length === 0 && (
                        <li className="muted" style={{ fontSize: "0.7rem" }}>
                          （无实例抽样）
                        </li>
                      )}
                      {(t.instances || []).map((inst) => (
                        <li key={inst.id} style={{ marginBottom: 4 }}>
                          <button
                            type="button"
                            className="btn-nav"
                            style={{ fontSize: "0.7rem" }}
                            onClick={() => {
                              setSelectedDataset(null);
                              appendSnippet(inst.snippet, tid);
                            }}
                          >
                            {inst.id}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>

          <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: 16 }}>
            Datasets
          </h2>
          <ul style={{ listStyle: "none", padding: 0, margin: "0.5rem 0 0" }}>
            {datasets.length === 0 && (
              <li className="muted" style={{ fontSize: "0.7rem" }}>
                （暂无实例抽样）
              </li>
            )}
            {datasets.map((d) => (
              <li key={d.rid} style={{ marginBottom: 4 }}>
                <button
                  type="button"
                  className="btn-nav"
                  style={{ fontSize: "0.75rem" }}
                  onClick={() =>
                    appendSnippet(
                      d.snippet,
                      d.objectTypeHint || selectedType || undefined,
                      d.rid,
                    )
                  }
                >
                  {d.name || d.rid}
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <main>
          <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: 0 }}>
            单元格缓冲
          </h2>
          <textarea
            value={cell}
            onChange={(e) => setCell(e.target.value)}
            rows={10}
            spellCheck={false}
            style={{
              width: "100%",
              fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
              fontSize: "0.8rem",
              boxSizing: "border-box",
              padding: "0.75rem",
              background: "var(--aos-surface, #0f1419)",
              color: "inherit",
              border: "1px solid var(--aos-border, #2a3540)",
            }}
          />
          <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
            <button type="button" className="btn" onClick={() => void copyCell()}>
              复制
            </button>
            <button
              type="button"
              className="btn-nav"
              onClick={() => {
                setCell("# 分析单元格 · 点击左侧 Ontology 插入片段\n");
                setCopyHint(null);
              }}
            >
              清空
            </button>
            {copyHint && (
              <span className="muted" style={{ fontSize: "0.75rem", alignSelf: "center" }}>
                {copyHint}
              </span>
            )}
          </div>

          <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: 20 }}>
            读数结果
          </h2>
          <p className="muted" style={{ fontSize: "0.75rem" }}>
            {readResult
              ? `kind=${readResult.kind} · total=${readResult.total ?? 0} · source=${readResult.source || "—"}`
              : "尚未读数"}
          </p>
          {readResult?.governance && (
            <p className="muted" style={{ fontSize: "0.75rem" }}>
              governance · redacted=
              {(readResult.governance.redactedFieldUnion || []).join(",") || "（无）"} · policy=
              {readResult.governance.exportPolicy || "—"}
            </p>
          )}
          {readResult?.detail && (
            <p className="muted" style={{ fontSize: "0.75rem" }}>
              {readResult.detail}
            </p>
          )}
          {readResult && <JsonBlock value={readResult} />}

          <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: 20 }}>
            导出 / 谱系
          </h2>
          {exportResult && (
            <p className="muted" style={{ fontSize: "0.75rem" }}>
              export ok · total={exportResult.total ?? 0}
            </p>
          )}
          {exportResult && <JsonBlock value={exportResult} />}
          <p className="muted" style={{ fontSize: "0.75rem" }}>
            lineage items={lineageItems.length}
          </p>
          {lineageItems.length > 0 && <JsonBlock value={lineageItems} />}

          <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: 20 }}>
            写回 · 提交 Draft
          </h2>
          <p className="muted" style={{ fontSize: "0.75rem" }}>
            本页只提案，批准请到 Draft 审批台
          </p>
          <div
            style={{
              display: "grid",
              gap: 8,
              gridTemplateColumns: "1fr 1fr",
              maxWidth: 480,
              fontSize: "0.8rem",
            }}
          >
            <label>
              objectType
              <input
                value={selectedType || "WorkOrder"}
                onChange={(e) => setSelectedType(e.target.value)}
                style={{ display: "block", width: "100%", marginTop: 4 }}
              />
            </label>
            <label>
              objectId
              <input
                value={wbObjectId}
                onChange={(e) => setWbObjectId(e.target.value)}
                style={{ display: "block", width: "100%", marginTop: 4 }}
              />
            </label>
            <label>
              status
              <input
                value={wbStatus}
                onChange={(e) => setWbStatus(e.target.value)}
                style={{ display: "block", width: "100%", marginTop: 4 }}
              />
            </label>
            <label>
              reason
              <input
                value={wbReason}
                onChange={(e) => setWbReason(e.target.value)}
                style={{ display: "block", width: "100%", marginTop: 4 }}
              />
            </label>
          </div>
          {lastDraft && (
            <>
              <p className="muted" style={{ fontSize: "0.75rem", marginTop: 8 }}>
                draft=<strong>{lastDraft.id}</strong> · status=<strong>{lastDraft.status}</strong> ·
                productionWritten=<strong>{String(lastDraft.productionWritten)}</strong>
              </p>
              <p style={{ fontSize: "0.875rem" }}>
                <Link to="/aip/drafts">前往审批台批准 →</Link>
              </p>
              <JsonBlock value={lastDraft} />
            </>
          )}

          <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: 20 }}>
            探索分析
          </h2>
          <p className="muted" style={{ fontSize: "0.75rem" }}>
            分组桶 · 谱系日密度时序 · 实验元数据登记（子集加深 · 非完整 BI/ML）
          </p>
          {subsetErr && <p className="error">{subsetErr}</p>}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
            <button
              type="button"
              className={subsetTab === "contour" ? "btn" : "btn-nav"}
              onClick={() => void tryContour()}
            >
              分组
            </button>
            <button
              type="button"
              className={subsetTab === "quiver" ? "btn" : "btn-nav"}
              onClick={() => void tryQuiver()}
            >
              时序
            </button>
            <button
              type="button"
              className={subsetTab === "vertex" ? "btn" : "btn-nav"}
              onClick={() => void tryVertexList()}
            >
              实验
            </button>
          </div>
          {subsetTab === "contour" && (
            <>
              <label style={{ fontSize: "0.8rem", display: "inline-block", marginBottom: 8 }}>
                groupBy{" "}
                <select
                  value={contourGroupBy}
                  onChange={(e) => {
                    const next = e.target.value;
                    setContourGroupBy(next);
                    void tryContour(next);
                  }}
                  style={{ marginLeft: 6 }}
                >
                  {(contour?.groupByOptions || ["status", "site", "priority"]).map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              </label>
              {contour && (
                <>
                  <p className="muted" style={{ fontSize: "0.75rem" }}>
                    groupBy={contour.groupBy} · rows={contour.totalRows ?? 0}
                    {contour.scheme ? ` · scheme=${contour.scheme}` : ""}
                  </p>
                  <ul style={{ listStyle: "none", padding: 0, margin: "8px 0 0", maxWidth: 420 }}>
                    {(contour.buckets || []).map((b) => {
                      const max = Math.max(
                        1,
                        ...(contour.buckets || []).map((x) => Number(x.count) || 0),
                      );
                      const w = Math.round(((Number(b.count) || 0) / max) * 100);
                      const sharePct =
                        typeof b.share === "number" ? Math.round(b.share * 1000) / 10 : null;
                      return (
                        <li key={String(b.key)} style={{ marginBottom: 6, fontSize: "0.8rem" }}>
                          <div style={{ display: "flex", justifyContent: "space-between" }}>
                            <span>{b.key}</span>
                            <span>
                              {b.count}
                              {sharePct != null ? ` · ${sharePct}%` : ""}
                            </span>
                          </div>
                          <div
                            style={{
                              height: 6,
                              background: "var(--aos-border, #2a3540)",
                              marginTop: 2,
                            }}
                          >
                            <div
                              style={{
                                width: `${w}%`,
                                height: "100%",
                                background: "var(--aos-accent, #5b8def)",
                              }}
                            />
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </>
              )}
            </>
          )}
          {subsetTab === "quiver" && quiver && (
            <>
              <p className="muted" style={{ fontSize: "0.75rem" }}>
                指标={quiver.metric || "—"} · 点数={(quiver.points || []).length}
                {quiver.fillGaps ? " · fillGaps" : ""} · 非传感器时序
              </p>
              {quiverSpark && (
                <svg
                  width={quiverSpark.w}
                  height={quiverSpark.h}
                  viewBox={`0 0 ${quiverSpark.w} ${quiverSpark.h}`}
                  role="img"
                  aria-label="lineage density sparkline"
                  style={{ display: "block", margin: "8px 0", maxWidth: "100%" }}
                >
                  <polyline
                    fill="none"
                    stroke="var(--aos-accent, #5b8def)"
                    strokeWidth="2"
                    points={quiverSpark.polyline}
                  />
                </svg>
              )}
              {(quiver.points || []).every((p) => !Number(p.v)) ? (
                <p className="muted" style={{ fontSize: "0.75rem" }}>
                  （各日为 0 · 批准 Draft 写回后可出现谱系密度）
                </p>
              ) : (
                <ul style={{ listStyle: "none", padding: 0, margin: "8px 0 0", fontSize: "0.8rem" }}>
                  {(quiver.points || [])
                    .filter((p) => Number(p.v) > 0)
                    .map((p) => (
                      <li key={String(p.t)}>
                        {p.t} · {p.v}
                      </li>
                    ))}
                </ul>
              )}
            </>
          )}
          {subsetTab === "vertex" && (
            <>
              <div
                style={{
                  display: "grid",
                  gap: 8,
                  gridTemplateColumns: "1fr 1fr 1fr auto",
                  maxWidth: 640,
                  fontSize: "0.8rem",
                  alignItems: "end",
                }}
              >
                <label>
                  name
                  <input
                    value={vxName}
                    onChange={(e) => setVxName(e.target.value)}
                    style={{ display: "block", width: "100%", marginTop: 4 }}
                  />
                </label>
                <label>
                  metric.score
                  <input
                    value={vxMetric}
                    onChange={(e) => setVxMetric(e.target.value)}
                    style={{ display: "block", width: "100%", marginTop: 4 }}
                  />
                </label>
                <label>
                  mediaRid（可选）
                  <input
                    value={vxMediaRid}
                    onChange={(e) => setVxMediaRid(e.target.value)}
                    placeholder="ri.media…"
                    style={{ display: "block", width: "100%", marginTop: 4 }}
                  />
                </label>
                <button type="button" className="btn" onClick={() => void tryVertexCreate()}>
                  登记实验
                </button>
              </div>
              <p className="muted" style={{ fontSize: "0.75rem", marginTop: 8 }}>
                experiments={vertexItems.length} · 不写 Ontology · 非 MLflow Server
              </p>
              {vertexItems.length > 0 && (
                <BpTable
                  columns={["id", "name", "score", "mediaRid", "created"]}
                  rows={vertexItems.map((v) => [
                    v.id || "—",
                    v.name || "—",
                    String(v.metrics?.score ?? "—"),
                    v.mediaRid || "—",
                    (v.createdAt || "—").slice(0, 19),
                  ])}
                />
              )}
            </>
          )}

          <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: 20 }}>
            /v1/analytics/health
          </h2>
          <p className="muted" style={{ fontSize: "0.75rem" }}>
            status=<strong>{h?.status || "—"}</strong> · sidecar=<strong>{h?.sidecar || "—"}</strong> ·
            mode=<strong>{h?.mode || "—"}</strong>
          </p>
          {h && <JsonBlock value={h} />}

          {lastCreated?.uiUrl && (
            <>
              <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: 16 }}>
                最近创建
              </h2>
              <p style={{ fontSize: "0.875rem" }}>
                <a href={lastCreated.uiUrl} target="_blank" rel="noreferrer">
                  打开受控 Notebook UI →
                </a>
              </p>
            </>
          )}

          <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: 16 }}>
            会话列表
          </h2>
          <p className="muted" style={{ fontSize: "0.75rem" }}>
            items={items.length}
          </p>
          {items.length > 0 && <JsonBlock value={items} />}
        </main>
      </div>

      <BpLinkRow
        links={[
          { to: "/aip/drafts", label: "Draft 审批台（写回正道）" },
          { to: "/aip/lineage", label: "决策谱系" },
          { to: "/data/datasets", label: "Dataset" },
          { to: "/ontology", label: "Ontology" },
        ]}
      />
    </S2Chrome>
  );
}
