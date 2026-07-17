import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet } from "../api/client";

type Branch = { id: string; name: string; baseRef: string; readonly: boolean };
type Health = { score: number; metrics: Record<string, unknown> };

export function OntologyPage() {
  const [types, setTypes] = useState<{ id: string; name: string }[]>([]);
  const [objects, setObjects] = useState<Record<string, unknown>[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [neighbors, setNeighbors] = useState<unknown[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [branchId, setBranchId] = useState("main");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      apiGet<{ items: { id: string; name: string }[] }>("/v1/ontology/object-types"),
      apiGet<{ items: Branch[] }>("/v1/ontology/branches"),
      apiGet<Health>("/v1/ontology/graph-health"),
    ])
      .then(([t, b, h]) => {
        setTypes(t.items);
        setBranches(b.items);
        setHealth(h);
      })
      .catch((e) => setErr(String(e.message || e)));
  }, []);

  async function openType(id: string) {
    setSelected(id);
    setDetail(null);
    setNeighbors([]);
    const list = await apiGet<{ items: Record<string, unknown>[] }>(
      `/v1/objects/${id}`,
    );
    setObjects(list.items);
  }

  async function openObject(type: string, id: string) {
    const d = await apiGet<Record<string, unknown>>(`/v1/objects/${type}/${id}`);
    setDetail(d);
    const n = await apiGet<{ items: unknown[] }>(
      `/v1/objects/${type}/${id}/neighbors`,
    );
    setNeighbors(n.items);
  }

  return (
    <section>
      <h1>本体管理（数字孪生）</h1>
      <p className="muted">
        分支{" "}
        <select
          aria-label="branch"
          value={branchId}
          onChange={(e) => setBranchId(e.target.value)}
        >
          {branches.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
              {b.readonly ? " (只读)" : ""}
            </option>
          ))}
        </select>
        {health && (
          <span>
            {" "}
            · 图谱健康 {health.score} · edges=
            {String(health.metrics.edges)}
          </span>
        )}
      </p>
      <p className="muted">
        <Link to="/ontology/funnel">Funnel 状态</Link>
        {" · "}
        <Link to="/ontology/wiki">Wiki</Link>
        {" · "}
        <Link to="/ontology/graph-health">图谱健康深页</Link>
        {" · "}
        <Link to="/demo">演示导航</Link>
      </p>
      {err && <p className="error">{err}</p>}
      <div className="canvas-grid">
        <ul className="card-list">
          {types.map((t) => (
            <li key={t.id} className="card">
              <button
                type="button"
                className="nav-link"
                onClick={() => void openType(t.id)}
              >
                {t.name} <span className="muted">({t.id})</span>
              </button>
            </li>
          ))}
        </ul>
        <div>
          {selected && (
            <>
              <h2>
                {selected} @ {branchId}
              </h2>
              <ul className="card-list">
                {objects.map((o) => (
                  <li key={String(o.id)} className="card">
                    <button
                      type="button"
                      className="nav-link"
                      onClick={() => void openObject(selected, String(o.id))}
                    >
                      {String(o.id)} · {String(o.title || "")}
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
          {detail && (
            <div className="card">
              <h3>详情</h3>
              <pre style={{ whiteSpace: "pre-wrap" }}>
                {JSON.stringify(detail, null, 2)}
              </pre>
              <h3>邻居 (1-hop)</h3>
              <pre style={{ whiteSpace: "pre-wrap" }}>
                {JSON.stringify(neighbors, null, 2)}
              </pre>
              <p>
                <Link to="/ontology/funnel">查看 Funnel</Link>
                {" · "}
                <Link to="/workshop/inbox">回运营台（已绑 PG query）</Link>
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
