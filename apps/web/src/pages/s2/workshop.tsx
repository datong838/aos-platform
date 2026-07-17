import { useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost, JsonBlock, S2Chrome, useJsonGet } from "./shared";

/** 知识图谱 — 选 Object → 1-hop neighbors */
export function GraphExplorerPage() {
  const { data: types, err: tErr } = useJsonGet<{ items: { id: string; name: string }[] }>(
    "/v1/ontology/object-types",
  );
  const [typeId, setTypeId] = useState("WorkOrder");
  const [objects, setObjects] = useState<Record<string, unknown>[]>([]);
  const [detail, setDetail] = useState<unknown>(null);
  const [neighbors, setNeighbors] = useState<unknown[]>([]);
  const [err, setErr] = useState<string | null>(null);

  async function loadObjects(t: string) {
    setTypeId(t);
    setDetail(null);
    setNeighbors([]);
    try {
      const r = await apiGet<{ items: Record<string, unknown>[] }>(`/v1/objects/${t}`);
      setObjects(r.items);
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  async function openObject(id: string) {
    setErr(null);
    try {
      const d = await apiGet(`/v1/objects/${typeId}/${id}`);
      const n = await apiGet<{ items: unknown[] }>(`/v1/objects/${typeId}/${id}/neighbors`);
      setDetail(d);
      setNeighbors(n.items);
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  return (
    <S2Chrome title="知识图谱" lede="对齐 workshop-object-view · 邻接表 1-hop">
      {(tErr || err) && <p className="error">{tErr || err}</p>}
      <div className="canvas-grid">
        <ul className="card-list">
          {(types?.items || []).map((t) => (
            <li key={t.id} className="card">
              <button type="button" className="nav-link" onClick={() => void loadObjects(t.id)}>
                {t.name} <span className="muted">({t.id})</span>
              </button>
            </li>
          ))}
        </ul>
        <div>
          <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
            {typeId} 实例
          </h2>
          <ul className="card-list">
            {objects.map((o) => (
              <li key={String(o.id)} className="card">
                <button
                  type="button"
                  className="nav-link"
                  onClick={() => void openObject(String(o.id))}
                >
                  {String(o.id)} · {String(o.title || "")}
                </button>
              </li>
            ))}
          </ul>
          {detail != null && (
            <>
              <h3 className="aos-text" style={{ fontSize: "0.875rem" }}>
                详情 / 邻居
              </h3>
              <JsonBlock value={{ detail, neighbors }} />
              <p className="muted">
                <Link to="/ontology">本体管理</Link> · <Link to="/ontology/graph-health">健康度</Link>
              </p>
            </>
          )}
        </div>
      </div>
    </S2Chrome>
  );
}

export function EventsPage() {
  const { data, err, reload } = useJsonGet<{ items: unknown[] }>("/v1/actions/webhooks");
  const [msg, setMsg] = useState("");

  async function register() {
    await apiPost("/v1/actions/webhooks", {
      url: "http://127.0.0.1:9999/hook",
      event: "action.approved",
    });
    setMsg("已注册 Demo webhook");
    reload();
  }

  return (
    <S2Chrome title="事件配置" lede="对齐 workshop-events · Action webhooks">
      <button type="button" className="btn" onClick={() => void register().catch((e) => setMsg(String(e)))}>
        注册 Demo Webhook
      </button>
      <button type="button" className="btn" style={{ marginLeft: 8 }} onClick={() => reload()}>
        刷新
      </button>
      {msg && <p className="aos-text">{msg}</p>}
      {err && <p className="error">{err}</p>}
      <JsonBlock value={data?.items ?? []} />
    </S2Chrome>
  );
}
