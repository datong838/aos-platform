import { useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost, JsonBlock, S2Chrome, useJsonGet } from "./shared";

const STAIRS = [
  { level: "L0", title: "探活", desc: "Health / Ready / 日志可追踪" },
  { level: "L1", title: "对象可读", desc: "Object Type · Inbox · Selection" },
  { level: "L2", title: "写经 Draft", desc: "Action validate → Draft → approve" },
  { level: "L3", title: "AIP 决策", desc: "Logic · Evals 门控 · Tool 注册" },
  { level: "L4", title: "可交付", desc: "Apollo Lite · Asset Bundle · 配置 Vault ref" },
];

export function MaturityPage() {
  const evals = useJsonGet<Record<string, unknown>>("/v1/aip/evals/status");
  return (
    <S2Chrome title="成熟度楼梯" lede="对齐 aip-maturity · 叙事楼梯（非评测引擎）">
      <ol className="card-list">
        {STAIRS.map((s) => (
          <li key={s.level} className="card">
            <strong>
              {s.level} · {s.title}
            </strong>
            <p className="muted">{s.desc}</p>
          </li>
        ))}
      </ol>
      <p className="muted">
        相关：
        <Link to="/aip/evals"> Evals</Link> ·
        <Link to="/aip/logic"> Logic</Link> ·
        <Link to="/aip/drafts"> Draft</Link>
      </p>
      {evals.err && <p className="error">{evals.err}</p>}
      {evals.data && (
        <>
          <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
            当前 Evals
          </h2>
          <JsonBlock value={evals.data} />
        </>
      )}
    </S2Chrome>
  );
}

export function CopPage() {
  const health = useJsonGet<Record<string, unknown>>("/v1/ontology/graph-health");
  const metrics = useJsonGet<Record<string, unknown>>("/v1/metrics");
  const evals = useJsonGet<Record<string, unknown>>("/v1/aip/evals/status");
  return (
    <S2Chrome title="态势大屏" lede="对齐 workshop-cop · 健康度 + RED 指标 + Evals（MVP 面板）">
      <button
        type="button"
        className="btn"
        onClick={() => {
          health.reload();
          metrics.reload();
          evals.reload();
        }}
      >
        刷新态势
      </button>
      {(health.err || metrics.err || evals.err) && (
        <p className="error">{health.err || metrics.err || evals.err}</p>
      )}
      <div className="canvas-grid" style={{ marginTop: "1rem" }}>
        <div className="card">
          <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
            图谱健康
          </h2>
          <p className="aos-text">score={String(health.data?.score ?? "—")}</p>
          <JsonBlock value={health.data?.metrics ?? health.data} />
        </div>
        <div className="card">
          <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
            RED 指标（TX.2）
          </h2>
          <JsonBlock value={metrics.data?.totals ?? metrics.data} />
        </div>
        <div className="card">
          <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
            Evals
          </h2>
          <JsonBlock value={evals.data} />
        </div>
      </div>
      <p className="muted">
        明细：
        <Link to="/ontology/graph-health"> 健康度</Link> ·
        <Link to="/aip/evals"> Evals</Link>
      </p>
    </S2Chrome>
  );
}

export function ModuleInterfacePage() {
  const { data, err, reload } = useJsonGet<{ items: { id: string; name: string }[] }>(
    "/v1/modules",
  );
  const [runtime, setRuntime] = useState<unknown>(null);
  const [msg, setMsg] = useState("");

  async function createMod() {
    await apiPost("/v1/modules", {
      name: "接口台 Module",
      description: "从模块接口页创建",
      objectType: "WorkOrder",
      entryPath: "/workshop/inbox",
      widgets: ["table", "filters", "selection"],
      buddyBound: true,
    });
    setMsg("已创建");
    reload();
  }

  async function openRuntime(id: string) {
    const r = await apiGet(`/v1/modules/${encodeURIComponent(id)}/runtime`);
    setRuntime(r);
  }

  return (
    <S2Chrome title="模块接口" lede="对齐 workshop-module-interface · 创建 / runtime / entryPath">
      <button type="button" className="btn" onClick={() => void createMod().catch(console.error)}>
        创建 Module
      </button>
      <button type="button" className="btn" style={{ marginLeft: 8 }} onClick={() => reload()}>
        刷新
      </button>
      {msg && <p className="aos-text">{msg}</p>}
      {err && <p className="error">{err}</p>}
      <ul className="card-list">
        {(data?.items || []).map((m) => (
          <li key={m.id} className="card">
            <strong>{m.name}</strong> <span className="muted">({m.id})</span>
            <button
              type="button"
              className="btn"
              style={{ marginLeft: 8 }}
              onClick={() => void openRuntime(m.id)}
            >
              Runtime
            </button>
          </li>
        ))}
      </ul>
      {runtime != null && <JsonBlock value={runtime} />}
    </S2Chrome>
  );
}
