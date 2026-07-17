import { useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost, ItemsPage, JsonBlock, S2Chrome, useJsonGet } from "./shared";

export function ToolsPage() {
  const { data, err, reload } = useJsonGet<{ items: { id: string; kind: string }[] }>(
    "/v1/aip/tools",
  );
  const plugins = useJsonGet<{ items: unknown[]; totals?: { all: number } }>("/v1/plugins");
  const [invokeOut, setInvokeOut] = useState<unknown>(null);
  const [localErr, setLocalErr] = useState<string | null>(null);

  async function invoke(id: string) {
    setLocalErr(null);
    try {
      const r = await apiPost(`/v1/aip/tools/${encodeURIComponent(id)}/invoke`, {
        objectType: "WorkOrder",
        objectId: "wo-1001",
      });
      setInvokeOut(r);
    } catch (e) {
      setLocalErr(String((e as Error).message || e));
    }
  }

  return (
    <S2Chrome title="Agent 工具面板" lede="对齐 aip-tools · 真 invoke · 统一插件目录 /v1/plugins">
      <button type="button" className="btn" onClick={() => reload()}>
        刷新 Tools
      </button>
      <button type="button" className="btn" style={{ marginLeft: 8 }} onClick={() => plugins.reload()}>
        刷新插件目录
      </button>
      <p className="muted">
        Studio 试聊 · <Link to="/aip/studio">打开</Link> · 插件总数{" "}
        {plugins.data?.totals?.all ?? "—"}
      </p>
      {(err || localErr || plugins.err) && (
        <p className="error">{err || localErr || plugins.err}</p>
      )}
      <ul className="card-list">
        {(data?.items || []).map((t) => (
          <li key={t.id} className="card">
            <strong>
              {t.kind}:{t.id}
            </strong>
            <button type="button" className="btn" style={{ marginLeft: 8 }} onClick={() => void invoke(t.id)}>
              Invoke
            </button>
          </li>
        ))}
      </ul>
      {invokeOut != null && (
        <>
          <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
            Invoke 结果
          </h2>
          <JsonBlock value={invokeOut} />
        </>
      )}
      <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: "1rem" }}>
        插件目录（tools + parsers + sources + capabilities）
      </h2>
      <JsonBlock value={plugins.data?.items ?? []} />
    </S2Chrome>
  );
}

export function ProvidersPage() {
  return (
    <ItemsPage
      title="模型供应商"
      lede="对齐 aip-model-providers · /v1/aip/providers"
      path="/v1/aip/providers"
    />
  );
}

export function ModelRouterPage() {
  const models = useJsonGet<{ items: { id: string; kind: string; ready: boolean }[]; sidecar?: string }>(
    "/v1/aip/models",
  );
  const { data, err, reload } = useJsonGet<{ items: unknown[] }>("/v1/aip/providers");
  const [modelId, setModelId] = useState("");
  const [query, setQuery] = useState("你好，介绍一下本系统的模型路由");
  const [chatOut, setChatOut] = useState<unknown>(null);
  const [warm, setWarm] = useState<unknown>(null);

  async function warmup() {
    const r = await apiGet("/v1/aip/models/warmup");
    setWarm(r);
  }

  async function tryChat() {
    const r = await apiPost("/v1/aip/chat", {
      query,
      withTools: false,
      model: modelId || undefined,
    });
    setChatOut(r);
  }

  return (
    <S2Chrome title="模型路由" lede="对齐 aip-model-router · /v1/aip/models + 试聊">
      <button type="button" className="btn" onClick={() => { reload(); models.reload(); }}>
        刷新
      </button>
      <button type="button" className="btn" style={{ marginLeft: 8 }} onClick={() => void warmup()}>
        Warmup
      </button>
      {(err || models.err) && <p className="error">{err || models.err}</p>}
      <p className="muted">sidecar={models.data?.sidecar || "—"}</p>
      <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
        可路由模型
      </h2>
      <ul className="card-list">
        {(models.data?.items || []).map((m) => (
          <li key={m.id} className="card">
            <label>
              <input
                type="radio"
                name="model"
                checked={modelId === m.id}
                onChange={() => setModelId(m.id)}
              />{" "}
              {m.id} · {m.kind} {m.ready ? "ready" : "cold"}
            </label>
          </li>
        ))}
      </ul>
      <div className="filter-bar" style={{ marginTop: "0.75rem" }}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ minWidth: "16rem" }}
          aria-label="router-query"
        />
        <button type="button" className="btn" onClick={() => void tryChat().catch(console.error)}>
          试聊
        </button>
      </div>
      {chatOut != null && <JsonBlock value={chatOut} />}
      {warm != null && (
        <>
          <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
            Warmup
          </h2>
          <JsonBlock value={warm} />
        </>
      )}
      <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
        Providers
      </h2>
      <JsonBlock value={data?.items ?? []} />
    </S2Chrome>
  );
}

export function EvalsPage() {
  const { data, err, reload } = useJsonGet<Record<string, unknown>>("/v1/aip/evals");
  const [msg, setMsg] = useState("");

  async function setGate(green: boolean) {
    await apiPost("/v1/aip/evals", { green });
    setMsg(green ? "门控已放行" : "门控已阻断");
    reload();
  }

  return (
    <S2Chrome title="Evals 门控" lede="对齐 aip-evals · status / set">
      <button type="button" className="btn" onClick={() => void setGate(true)}>
        放行
      </button>
      <button type="button" className="btn" style={{ marginLeft: 8 }} onClick={() => void setGate(false)}>
        阻断
      </button>
      <button type="button" className="btn" style={{ marginLeft: 8 }} onClick={() => reload()}>
        刷新
      </button>
      {msg && <p className="aos-text">{msg}</p>}
      {err && <p className="error">{err}</p>}
      <JsonBlock value={data} />
    </S2Chrome>
  );
}

export function DecisionLineagePage() {
  const { data: drafts, err } = useJsonGet<{ items: { id: string; status?: string }[] }>(
    "/v1/aip/drafts",
  );
  const [lineageId, setLineageId] = useState("");
  const [lineage, setLineage] = useState<unknown>(null);
  const [localErr, setLocalErr] = useState<string | null>(null);

  async function load() {
    setLocalErr(null);
    try {
      const r = await apiGet(`/v1/aip/lineage/${encodeURIComponent(lineageId)}`);
      setLineage(r);
    } catch (e) {
      setLocalErr(String((e as Error).message || e));
      setLineage(null);
    }
  }

  return (
    <S2Chrome title="决策谱系" lede="对齐 aip-decision-lineage · Draft 列表 + lineage 查询">
      {err && <p className="error">{err}</p>}
      <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
        近期 Draft
      </h2>
      <JsonBlock value={drafts?.items ?? []} />
      <label className="muted">
        lineageId{" "}
        <input
          value={lineageId}
          onChange={(e) => setLineageId(e.target.value)}
          placeholder="approve 后返回的 lineage id"
          style={{ minWidth: "16rem" }}
        />
      </label>
      <button type="button" className="btn" style={{ marginLeft: 8 }} onClick={() => void load()}>
        查询
      </button>
      {localErr && <p className="error">{localErr}</p>}
      {lineage != null && <JsonBlock value={lineage} />}
    </S2Chrome>
  );
}
