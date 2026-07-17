import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiPost } from "../api/client";

export type CanvasNode = {
  id: string;
  kind: "table" | "filter" | "buddy";
  title: string;
};

const DEFAULT_LAYOUT: CanvasNode[] = [
  { id: "n-filter", kind: "filter", title: "Filter · site=DC-East" },
  { id: "n-table", kind: "table", title: "Object Table · WorkOrder" },
  { id: "n-buddy", kind: "buddy", title: "Buddy Chip" },
];

type Row = { objectId?: string; id?: string; props?: Record<string, unknown>; title?: string; status?: string };

/** T1.11 + TB.5 — layout tree + live Object Table/Filter preview. */
export function CanvasPage() {
  const [selected, setSelected] = useState(DEFAULT_LAYOUT[0].id);
  const [site, setSite] = useState("DC-East");
  const [rows, setRows] = useState<Row[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [previewOn, setPreviewOn] = useState(true);

  const node = useMemo(
    () => DEFAULT_LAYOUT.find((n) => n.id === selected) ?? DEFAULT_LAYOUT[0],
    [selected],
  );

  async function runPreview() {
    setErr(null);
    try {
      const r = await apiPost<{ items?: Row[]; objects?: Row[] }>("/v1/object-sets/query", {
        objectType: "WorkOrder",
        filters: site ? [{ field: "site", op: "eq", value: site }] : [],
        pageSize: 10,
      });
      setRows(r.items || r.objects || []);
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  useEffect(() => {
    if (previewOn) void runPreview();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- site-keyed
  }, [site, previewOn]);

  return (
    <section className="canvas-grid">
      <div>
        <h1>画布编辑</h1>
        <p className="muted">TB.5 · Layout + 预览运行态（Object Table / Filter）</p>
        <ul className="card-list">
          {DEFAULT_LAYOUT.map((n) => (
            <li key={n.id}>
              <button
                type="button"
                className={n.id === selected ? "nav-link active" : "nav-link"}
                onClick={() => setSelected(n.id)}
              >
                {n.kind}: {n.title}
              </button>
            </li>
          ))}
        </ul>
        <p>
          <Link to="/demo">客户演示导航</Link>
        </p>
      </div>
      <div className="card">
        <h2>预览运行态</h2>
        <p>
          选中：<strong>{node.title}</strong>
        </p>
        <label className="muted">
          Filter site{" "}
          <input value={site} onChange={(e) => setSite(e.target.value)} style={{ marginLeft: 8 }} />
        </label>
        <div style={{ marginTop: 8 }}>
          <button type="button" className="btn" onClick={() => void runPreview()}>
            刷新 Object Table
          </button>
          <button
            type="button"
            className="btn"
            style={{ marginLeft: 8 }}
            onClick={() => setPreviewOn((v) => !v)}
          >
            {previewOn ? "暂停预览" : "开启预览"}
          </button>
        </div>
        {err && <p className="error">{err}</p>}
        <ul className="card-list" style={{ marginTop: 12 }}>
          {rows.map((row, i) => {
            const id = String(row.id || row.objectId || `row-${i}`);
            const title = String(row.title || (row.props?.title as string) || id);
            const status = String(row.status || (row.props?.status as string) || "");
            return (
              <li key={id} className="card">
                <strong>{id}</strong>{" "}
                <span className="muted">
                  {title} · {status}
                </span>
              </li>
            );
          })}
        </ul>
        {rows.length === 0 && !err && <p className="muted">无行 · 可改 site 或先跑 /demo 确保种子</p>}
      </div>
    </section>
  );
}

export function layoutNodeCount(nodes: CanvasNode[] = DEFAULT_LAYOUT): number {
  return nodes.length;
}
