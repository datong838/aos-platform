import { useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost, ItemsPage, JsonBlock, S2Chrome, useJsonGet } from "./shared";

export function MediaSetsPage() {
  const { data, err, reload } = useJsonGet<{ items: { rid: string; name?: string }[] }>(
    "/v1/media-sets",
  );
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
    <S2Chrome title="媒体集" lede="对齐 media-sets · 上传 + 解析插件 extract">
      <button type="button" className="btn" onClick={() => void uploadAndParse()}>
        上传 CSV 并解析
      </button>
      <button type="button" className="btn" style={{ marginLeft: 8 }} onClick={() => reload()}>
        刷新
      </button>
      <p className="muted">
        解析插件列表 · <Link to="/data">数据连接</Link>
      </p>
      {(err || localErr) && <p className="error">{err || localErr}</p>}
      <JsonBlock value={data?.items ?? []} />
      {parseOut != null && (
        <>
          <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
            解析结果
          </h2>
          <JsonBlock value={parseOut} />
        </>
      )}
    </S2Chrome>
  );
}

export function PipelinesPage() {
  return (
    <ItemsPage title="管道构建" lede="对齐 pipeline-list · /v1/pipelines" path="/v1/pipelines" />
  );
}

export function BuildsPage() {
  return <ItemsPage title="搭建" lede="对齐 builds · /v1/builds" path="/v1/builds" />;
}

export function SchedulesPage() {
  return (
    <ItemsPage title="计划编辑器" lede="对齐 schedules · /v1/schedules" path="/v1/schedules" />
  );
}

export function DatasetsPage() {
  const { data, err, reload } = useJsonGet<{ items: { rid: string }[] }>("/v1/datasets");
  const [hist, setHist] = useState<unknown>(null);

  async function openHistory(rid: string) {
    const h = await apiGet(`/v1/datasets/${encodeURIComponent(rid)}/history`);
    setHist(h);
  }

  return (
    <S2Chrome title="数据集预览" lede="对齐 dataset · /v1/datasets（G-ALIGN-04）">
      <button type="button" className="btn" onClick={() => reload()}>
        刷新
      </button>
      <p className="muted">
        空列表时请先到 <Link to="/data">数据连接</Link> 跑通 Pipeline
      </p>
      {err && <p className="error">{err}</p>}
      <ul className="card-list">
        {(data?.items || []).map((d) => (
          <li key={d.rid} className="card">
            <button type="button" className="nav-link" onClick={() => void openHistory(d.rid)}>
              {d.rid}
            </button>
          </li>
        ))}
      </ul>
      {hist != null && <JsonBlock value={hist} />}
      {!hist && data && <JsonBlock value={data.items} />}
    </S2Chrome>
  );
}

export function DataHealthPage() {
  const store = useJsonGet<Record<string, unknown>>("/v1/object-store/health");
  const mysql = useJsonGet<Record<string, unknown>>("/v1/connectors/mysql/health");
  return (
    <S2Chrome title="数据健康" lede="对齐 health · Object Store + MySQL probe">
      <button
        type="button"
        className="btn"
        onClick={() => {
          store.reload();
          mysql.reload();
        }}
      >
        刷新
      </button>
      {(store.err || mysql.err) && <p className="error">{store.err || mysql.err}</p>}
      <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
        Object Store
      </h2>
      <JsonBlock value={store.data} />
      <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
        MySQL
      </h2>
      <JsonBlock value={mysql.data} />
    </S2Chrome>
  );
}

export function EdgeAgentsPage() {
  const { data, err, reload } = useJsonGet<Record<string, unknown>>("/v1/edge/agents/local");
  return (
    <S2Chrome title="边缘代理" lede="对齐 data-connection-agents · /v1/edge/agents/local">
      <button type="button" className="btn" onClick={() => reload()}>
        刷新
      </button>
      {err && <p className="error">{err}</p>}
      <JsonBlock value={data} />
    </S2Chrome>
  );
}
