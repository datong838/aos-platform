import { useState } from "react";
import { apiPost } from "../api/client";

/** T3.12 — Logic canvas minimal: dryRun only, never writes production. */
export function LogicPage() {
  const [out, setOut] = useState("");
  const [err, setErr] = useState<string | null>(null);

  async function dryRun() {
    setErr(null);
    try {
      const res = await apiPost<{
        dryRun: boolean;
        proposedEdits: unknown[];
        productionWritten: boolean;
      }>("/v1/aip/logic/run", {
        dryRun: true,
        edits: [
          {
            objectType: "WorkOrder",
            objectId: "wo-1001",
            set: { note: "logic-ui" },
          },
        ],
      });
      setOut(JSON.stringify(res, null, 2));
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  return (
    <section>
      <h1>Logic 画布（最小）</h1>
      <p className="muted">T3.12 · dryRun 不落库 · 写生产须经 Draft</p>
      <div className="card-list">
        <div className="card">节点：Query → Function → Propose Edits</div>
        <div className="card">边：示例串行图</div>
      </div>
      <button type="button" onClick={() => void dryRun()}>
        试跑 dryRun
      </button>
      {err && <p className="error">{err}</p>}
      {out && <pre className="card">{out}</pre>}
    </section>
  );
}
