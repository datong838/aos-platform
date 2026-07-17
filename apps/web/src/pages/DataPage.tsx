import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost } from "../api/client";
import { PageChrome } from "../components/PageChrome";

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

/** Wave-4 + TB.2 · data hub with seeded Dataset/Build/DLQ for customer demo. */
export function DataPage() {
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [datasets, setDatasets] = useState<DatasetRow[]>([]);
  const [builds, setBuilds] = useState<BuildRow[]>([]);
  const [dlq, setDlq] = useState<DlqRow[]>([]);

  async function refresh() {
    const [ds, b, d] = await Promise.all([
      apiGet<{ items: DatasetRow[] }>("/v1/datasets"),
      apiGet<{ items: BuildRow[] }>("/v1/builds"),
      apiGet<{ items: DlqRow[] }>("/v1/dlq"),
    ]);
    setDatasets(ds.items || []);
    setBuilds(b.items || []);
    setDlq(d.items || []);
  }

  useEffect(() => {
    refresh().catch((e) => setErr(String(e.message || e)));
  }, []);

  async function ensureSeed() {
    setErr(null);
    try {
      await apiPost("/v1/demo/ensure-seed", {});
      setMsg("演示种子已确保 · Dataset/Build/DLQ 可指屏");
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

  return (
    <PageChrome
      title="数据连接"
      lede="TB.2 · 文件→Pipeline→Dataset/Build · DLQ 失败可指 · 对齐 data-connection"
    >
      <button type="button" className="btn" onClick={() => void ensureSeed()}>
        确保演示种子
      </button>
      <button type="button" className="btn" style={{ marginLeft: 8 }} onClick={() => void demoPipeline()}>
        再跑一趟文件 Pipeline
      </button>
      <p className="muted" style={{ marginTop: "0.75rem" }}>
        <Link to="/data/datasets">Datasets 深页</Link>
        {" · "}
        <Link to="/data/builds">Builds</Link>
        {" · "}
        <Link to="/data/health">健康/MySQL probe</Link>
        {" · "}
        <Link to="/demo">演示导航</Link>
      </p>
      {msg && <p className="aos-text">{msg}</p>}
      {err && <p className="error">{err}</p>}

      <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: "1.5rem" }}>
        Datasets（{datasets.length}）
      </h2>
      {datasets.length === 0 ? (
        <p className="muted">空 · 点「确保演示种子」预置 WorkOrder-demo</p>
      ) : (
        <ul className="card-list">
          {datasets.map((d) => (
            <li key={String(d.rid)} className="card">
              <strong>{d.name || d.rid}</strong>{" "}
              <span className="muted">
                {d.status} · pipe={d.pipelineId}
                {d.objectTypeHint ? ` · → ${d.objectTypeHint}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}

      <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: "1rem" }}>
        Builds（{builds.length}）
      </h2>
      {builds.length === 0 ? (
        <p className="muted">空 · 种子或现场 Pipeline 后可见</p>
      ) : (
        <ul className="card-list">
          {builds.map((b) => (
            <li key={`${b.pipelineId}-${b.id}`} className="card">
              <strong>{b.id}</strong>{" "}
              <span className="muted">
                {b.status} · {b.pipelineId}
              </span>
            </li>
          ))}
        </ul>
      )}

      <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: "1rem" }}>
        DLQ（{dlq.length}）
      </h2>
      {dlq.length === 0 ? (
        <p className="muted">无失败样例</p>
      ) : (
        <ul className="card-list">
          {dlq.map((row) => (
            <li key={String(row.id)} className="card">
              <strong>{row.id}</strong>{" "}
              <span className="muted">
                {row.status} · {row.reason}
              </span>
            </li>
          ))}
        </ul>
      )}
    </PageChrome>
  );
}
