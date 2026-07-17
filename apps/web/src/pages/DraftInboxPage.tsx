import { useEffect, useState } from "react";
import { apiGet, apiPost, API_BASE } from "../api/client";

type Draft = {
  id: string;
  title: string;
  status: string;
  actionTypeId: string;
  objectId?: string;
};

export function DraftInboxPage() {
  const [items, setItems] = useState<Draft[]>([]);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState<string | null>(null);

  async function reload() {
    const res = await apiGet<{ items: Draft[] }>("/v1/aip/drafts");
    setItems(res.items);
  }

  useEffect(() => {
    reload().catch((e) => setErr(String(e.message || e)));
  }, []);

  async function createSample() {
    setErr(null);
    try {
      const d = await apiPost<Draft>("/v1/aip/drafts", {
        actionTypeId: "CloseWorkOrder",
        objectType: "WorkOrder",
        objectId: "wo-1001",
        proposed: { reason: "ui-demo" },
        title: "UI 关闭工单提案",
      });
      setMsg(`已创建 ${d.id}（未写生产）`);
      await reload();
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  async function approve(id: string) {
    setErr(null);
    try {
      const res = await fetch(`${API_BASE}/v1/aip/drafts/${id}/approve`, {
        method: "POST",
        headers: {
          Authorization: "Bearer dev",
          "X-Org-Id": "dev-org",
          "X-Project-Id": "dev-project",
          "Idempotency-Key": `ui-approve-${id}`,
          "X-Allow-Conflicts": "true",
        },
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.message || res.statusText);
      setMsg(
        `已批准并写生产 · object=${body.objectId} · lineage=${body.lineageId}`,
      );
      await reload();
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  return (
    <section>
      <h1>Draft 审批台</h1>
      <p className="muted">T3.3/T3.14 · 批准走 T3.4 写生产</p>
      <button type="button" onClick={() => void createSample()}>
        新建示例 Draft
      </button>
      {msg && <p>{msg}</p>}
      {err && <p className="error">{err}</p>}
      <ul className="card-list">
        {items.map((d) => (
          <li key={d.id} className="card">
            <strong>{d.title}</strong>
            <span className="muted">
              {" "}
              · {d.status} · {d.actionTypeId} · {d.objectId}
            </span>
            {d.status === "proposed" && (
              <div>
                <button type="button" onClick={() => void approve(d.id)}>
                  批准写生产
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
