/**
 * 186w · Pipeline 画布页 · 对齐 foundry/html/pipeline.html（图1）
 * 层次：顶栏操作 · 中网格 DAG · 底预览 · 右输出属性
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiPost } from "../../api/client";
import { BpBanner, BpToolbar } from "./blueprintUi";
import { S2Chrome, useJsonGet } from "./shared";
import {
  buildStatusBadge,
  pipelineDisplayTitle,
  tableKeyFromBlob,
  TABLE_LABELS,
  type PipelineMeta,
} from "./pipelineMeta";

type PreviewResult = {
  columns?: string[];
  rows?: Record<string, unknown>[];
  total?: number;
  objectType?: string;
};

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
  return s.length > 48 ? `${s.slice(0, 45)}…` : s;
}

export function PipelineCanvasPage() {
  const { pipelineId = "" } = useParams();
  const { data, err, reload } = useJsonGet<{ items: PipelineMeta[] }>("/v1/pipelines");
  const pipe = useMemo(
    () => (data?.items || []).find((p) => p.id === pipelineId) || null,
    [data?.items, pipelineId],
  );
  const title = pipe ? pipelineDisplayTitle(pipe) : pipelineId || "管道";
  const badge = buildStatusBadge(pipe?.lastBuild?.status);
  const table = tableKeyFromBlob(pipe?.id, pipe?.datasetRid);
  const outLabel = table ? TABLE_LABELS[table]?.zh || pipe?.datasetRid : pipe?.datasetRid || "输出数据集";
  const otHint = pipe?.objectTypeHint || (table ? TABLE_LABELS[table]?.ot : undefined);

  const [selected, setSelected] = useState<"input" | "transform" | "output">("output");
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [previewErr, setPreviewErr] = useState<string | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  useEffect(() => {
    setSelected("output");
    setPreview(null);
    setPreviewErr(null);
  }, [pipelineId]);

  useEffect(() => {
    if (!pipe?.datasetRid && !otHint) return;
    let cancelled = false;
    (async () => {
      setPreviewBusy(true);
      setPreviewErr(null);
      try {
        const body: Record<string, unknown> = { limit: 8 };
        if (otHint) body.objectType = otHint;
        if (pipe?.datasetRid) body.datasetRid = pipe.datasetRid;
        const result = await apiPost<PreviewResult>("/v1/analytics/datasets/preview", body);
        if (!cancelled) setPreview(result);
      } catch (e) {
        if (!cancelled) setPreviewErr(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setPreviewBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pipe?.datasetRid, otHint]);

  const cols = preview?.columns?.slice(0, 6) || [];
  const rows = preview?.rows?.slice(0, 5) || [];

  return (
    <S2Chrome title={title} lede="Pipeline Builder · 画布">
      <BpToolbar>
        <Link to="/data/pipelines" className="btn-nav">
          ← 管道列表
        </Link>
        <select className="bp-pipe-branch" aria-label="分支" defaultValue="master" disabled>
          <option value="master">master</option>
        </select>
        <button type="button" className="btn" disabled title="DAG 算子编辑未接线 · 见 183w">
          保存
        </button>
        <Link to="/data/pipeline-proposals" className="btn-nav">
          提议
        </Link>
        <Link to="/data/schedules" className="btn-nav">
          打开计划编辑器
        </Link>
        <Link to="/data/builds" className="btn-primary">
          部署
        </Link>
        <span className={`bp-pipe-badge bp-pipe-badge-${badge.tone}`}>
          <span className="bp-pipe-badge-dot" />
          {pipe?.lastBuild?.id ? `Build ${pipe.lastBuild.id}` : "Build"} · {badge.label}
        </span>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
      </BpToolbar>

      {err && <p className="error">{err}</p>}
      {!err && !pipe && <BpBanner tone="warn">未找到管道 {pipelineId}</BpBanner>}

      {pipe && (
        <div className="bp-pipe-canvas-shell">
          <div className="bp-pipe-canvas-main">
            <div className="grid-pattern bp-pipe-dag">
              <svg className="bp-pipe-flow-svg" preserveAspectRatio="none" viewBox="0 0 720 200" aria-hidden>
                <path className="flow-line flow-line-active" d="M 160 100 C 200 100, 220 100, 260 100" />
                <path className="flow-line flow-line-active" d="M 400 100 C 440 100, 460 100, 500 100" />
              </svg>
              <div className="bp-pipe-nodes">
                <button
                  type="button"
                  className={`pipeline-node bp-pipe-node bp-pipe-node-input${selected === "input" ? " is-selected" : ""}`}
                  onClick={() => setSelected("input")}
                >
                  <div className="bp-pipe-node-head">
                    <span className="bp-pipe-node-icon bp-pipe-node-icon-amber" />
                    <span className="bp-pipe-node-kind bp-pipe-kind-amber">输入</span>
                  </div>
                  <div className="bp-pipe-node-title">{pipe.sourceId || "source"}</div>
                  <div className="bp-pipe-node-sub">Source</div>
                </button>

                <button
                  type="button"
                  className={`pipeline-node bp-pipe-node bp-pipe-node-xform${selected === "transform" ? " is-selected" : ""}`}
                  onClick={() => setSelected("transform")}
                >
                  <div className="bp-pipe-node-head">
                    <span className="bp-pipe-node-icon bp-pipe-node-icon-cyan" />
                    <span className="bp-pipe-node-kind bp-pipe-kind-cyan">变换</span>
                  </div>
                  <div className="bp-pipe-node-title">Ingest</div>
                  <div className="bp-pipe-node-sub">表 → 对象实例</div>
                </button>

                <button
                  type="button"
                  className={`pipeline-node bp-pipe-node bp-pipe-node-out${selected === "output" ? " is-selected" : ""}`}
                  onClick={() => setSelected("output")}
                >
                  <div className="bp-pipe-node-head">
                    <span className="bp-pipe-node-icon bp-pipe-node-icon-emerald" />
                    <span className="bp-pipe-node-kind bp-pipe-kind-emerald">输出</span>
                  </div>
                  <div className="bp-pipe-node-title">{outLabel}</div>
                  <div className="bp-pipe-node-sub">{pipe.datasetRid || "dataset"}</div>
                </button>
              </div>
            </div>

            <div className="bp-pipe-preview">
              <div className="bp-pipe-preview-bar">
                <span>输出预览 · {outLabel}</span>
                <span className="muted">
                  {previewBusy ? "加载中…" : preview?.total != null ? `${preview.total} 行` : "采样"}
                </span>
              </div>
              <div className="bp-pipe-preview-body">
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
                  <p className="muted">暂无预览行 · 可到数据集页核对对象实例</p>
                )}
              </div>
            </div>
          </div>

          <aside className="bp-pipe-inspector">
            <div className="bp-pipe-inspector-block">
              <h3 className="bp-pipe-inspector-title">
                {selected === "input" && "输入源"}
                {selected === "transform" && "变换"}
                {selected === "output" && "输出数据集"}
              </h3>
              <p className="muted bp-pipe-inspector-lede">
                {selected === "input" && (pipe.sourceId || "—")}
                {selected === "transform" && "Ingest · 当前管道为源表直写入对象（无自定义 Join 图）"}
                {selected === "output" && `${outLabel}${otHint ? ` · ${otHint}` : ""}`}
              </p>
            </div>

            {selected === "output" && (
              <>
                <label className="bp-pipe-field">
                  <span>格式</span>
                  <select disabled defaultValue="parquet">
                    <option value="parquet">Parquet</option>
                  </select>
                </label>
                <label className="bp-pipe-field">
                  <span>表格式</span>
                  <select disabled defaultValue="objects">
                    <option value="objects">对象实例（PG）</option>
                  </select>
                </label>
                <label className="bp-pipe-field">
                  <span>写入模式</span>
                  <select disabled defaultValue="snapshot">
                    <option value="snapshot">SNAPSHOT</option>
                  </select>
                </label>
                <div className="bp-pipe-schema">
                  <div className="bp-section-label">Schema</div>
                  {cols.length === 0 ? (
                    <p className="muted">预览后显示列</p>
                  ) : (
                    <table className="bp-pipe-schema-table">
                      <thead>
                        <tr>
                          <th>列</th>
                          <th>类型</th>
                        </tr>
                      </thead>
                      <tbody>
                        {cols.map((c) => (
                          <tr key={c}>
                            <td className="mono">{c}</td>
                            <td className="muted">—</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </>
            )}

            <Link to="/data/builds" className="btn-primary bp-pipe-deploy">
              部署并搭建
            </Link>
            {pipe.datasetRid && (
              <Link to={`/data/datasets?rid=${encodeURIComponent(pipe.datasetRid)}`} className="btn-nav bp-pipe-deploy">
                打开数据集 →
              </Link>
            )}

            <button
              type="button"
              className="btn bp-pipe-advanced-toggle"
              onClick={() => setAdvancedOpen((v) => !v)}
            >
              {advancedOpen ? "收起高级" : "高级 · 向量索引"}
            </button>
            {advancedOpen && (
              <p className="muted" style={{ fontSize: "0.75rem" }}>
                向量索引接线见列表旧入口已迁出主舞台；请用 AIP / embed API 或后续专页，避免污染画布层次。
              </p>
            )}
          </aside>
        </div>
      )}
    </S2Chrome>
  );
}
