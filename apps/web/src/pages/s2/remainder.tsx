import { useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost, JsonBlock, S2Chrome, useJsonGet } from "./shared";

/** S2 knife-3 ([49]) — remaining stubs → live / honest deferred */

export function OkfFunnelPage() {
  const funnel = useJsonGet<Record<string, unknown>>("/v1/funnel/WorkOrder/status");
  const modules = useJsonGet<{ items: unknown[] }>("/v1/modules");
  const [lint, setLint] = useState<unknown>(null);
  const [msg, setMsg] = useState("");

  async function runLint() {
    setMsg("");
    const r = await apiPost("/v1/ontology/constitution/lint", {
      id: "WorkOrder",
      name: "WorkOrder",
      published: true,
      properties: [{ name: "status", type: "string" }],
    });
    setLint(r);
    setMsg("Constitution lint 完成");
  }

  return (
    <S2Chrome title="OKF 行业漏斗" lede="对齐 okf-funnel · Constitution + Funnel + Module（行业全量后置）">
      <button type="button" className="btn" onClick={() => void runLint().catch((e) => setMsg(String(e)))}>
        跑 Constitution Lint
      </button>
      <button
        type="button"
        className="btn"
        style={{ marginLeft: 8 }}
        onClick={() => {
          funnel.reload();
          modules.reload();
        }}
      >
        刷新
      </button>
      {msg && <p className="aos-text">{msg}</p>}
      {(funnel.err || modules.err) && <p className="error">{funnel.err || modules.err}</p>}
      <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
        Funnel · WorkOrder
      </h2>
      <JsonBlock value={funnel.data} />
      <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
        Modules（OKF 绑包入口）
      </h2>
      <JsonBlock value={modules.data?.items} />
      {lint != null && (
        <>
          <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
            Lint
          </h2>
          <JsonBlock value={lint} />
        </>
      )}
      <p className="muted">
        相关：
        <Link to="/ontology/funnel"> 通用漏斗</Link> ·
        <Link to="/workshop/module-interface"> 模块接口</Link>
      </p>
    </S2Chrome>
  );
}

export function PipelineProposalsPage() {
  const { data, err, reload } = useJsonGet<{ items: unknown[] }>("/v1/pipelines");
  const [msg, setMsg] = useState("");

  async function propose() {
    const id = `prop-${Date.now().toString(36)}`;
    await apiPost("/v1/pipelines", { id, sourceId: "src-demo" });
    setMsg(`已创建管道提案 ${id}`);
    reload();
  }

  return (
    <S2Chrome title="管道提案" lede="对齐 pipeline-proposals · 管道即提案（MVP）">
      <button type="button" className="btn" onClick={() => void propose().catch((e) => setMsg(String(e)))}>
        新建提案
      </button>
      <button type="button" className="btn" style={{ marginLeft: 8 }} onClick={() => reload()}>
        刷新
      </button>
      {msg && <p className="aos-text">{msg}</p>}
      {err && <p className="error">{err}</p>}
      <JsonBlock value={data?.items} />
      <p className="muted">
        构建明细见 <Link to="/data/pipelines">管道构建</Link>
      </p>
    </S2Chrome>
  );
}

export function CodeReposPage() {
  const { data, err, reload } = useJsonGet<{ items: unknown[]; store?: string }>("/v1/code-repos");
  return (
    <S2Chrome title="代码库" lede="对齐 code-repositories · Dev 目录（非 Git 主机）">
      <button type="button" className="btn" onClick={() => reload()}>
        刷新
      </button>
      {err && <p className="error">{err}</p>}
      <p className="muted">store={data?.store ?? "—"}</p>
      <JsonBlock value={data?.items} />
    </S2Chrome>
  );
}

export function DataLineagePage() {
  const datasets = useJsonGet<{ items: { rid: string; name?: string }[] }>("/v1/datasets");
  const syncs = useJsonGet<{ items: unknown[] }>("/v1/syncs");
  const [history, setHistory] = useState<unknown>(null);
  const [rid, setRid] = useState("");

  async function loadHistory(target: string) {
    setRid(target);
    const r = await apiGet(`/v1/datasets/${encodeURIComponent(target)}/history`);
    setHistory(r);
  }

  return (
    <S2Chrome title="数据沿袭" lede="对齐 data lineage · datasets history + syncs（≠ AIP 决策谱系）">
      <button
        type="button"
        className="btn"
        onClick={() => {
          datasets.reload();
          syncs.reload();
        }}
      >
        刷新
      </button>
      {(datasets.err || syncs.err) && <p className="error">{datasets.err || syncs.err}</p>}
      <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
        Datasets
      </h2>
      <ul className="card-list">
        {(datasets.data?.items || []).map((d) => (
          <li key={d.rid} className="card">
            <strong>{d.name || d.rid}</strong>{" "}
            <span className="muted">{d.rid}</span>
            <button
              type="button"
              className="btn"
              style={{ marginLeft: 8 }}
              onClick={() => void loadHistory(d.rid).catch(console.error)}
            >
              History
            </button>
          </li>
        ))}
      </ul>
      {history != null && (
        <>
          <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
            History · {rid}
          </h2>
          <JsonBlock value={history} />
        </>
      )}
      <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
        Syncs
      </h2>
      <JsonBlock value={syncs.data?.items} />
      <p className="muted">
        决策谱系请用 <Link to="/aip/lineage">AIP 谱系</Link>
      </p>
    </S2Chrome>
  );
}

type ApolloChannel = {
  id: string;
  name?: string;
  status: string;
  rank: number;
  promotedFrom?: string | null;
  promotedAt?: string | null;
  recalledFrom?: string | null;
  recalledAt?: string | null;
};

const CHANNEL_ORDER = ["dev", "staging", "stable"] as const;

function nextChannel(id: string): string | null {
  const i = CHANNEL_ORDER.indexOf(id as (typeof CHANNEL_ORDER)[number]);
  if (i < 0 || i + 1 >= CHANNEL_ORDER.length) return null;
  return CHANNEL_ORDER[i + 1];
}

function prevChannel(id: string): string | null {
  const i = CHANNEL_ORDER.indexOf(id as (typeof CHANNEL_ORDER)[number]);
  if (i <= 0) return null;
  return CHANNEL_ORDER[i - 1];
}

export function ApolloReleasePage() {
  const fleet = useJsonGet<Record<string, unknown>>("/v1/apollo/fleet");
  const channels = useJsonGet<{ items: ApolloChannel[] }>("/v1/apollo/channels");
  const [upgrade, setUpgrade] = useState<unknown>(null);
  const [action, setAction] = useState<unknown>(null);
  const [msg, setMsg] = useState("");

  function refreshAll() {
    fleet.reload();
    channels.reload();
  }

  async function runUpgrade() {
    const r = await apiPost("/v1/apollo/upgrade", { from: "0.2.0-dev", to: "0.3.0-dev" });
    setUpgrade(r);
    setMsg("Lite upgrade 演练完成");
    refreshAll();
  }

  async function runPromote(id: string) {
    setMsg("");
    try {
      const r = await apiPost(`/v1/apollo/channels/${encodeURIComponent(id)}/promote`, {});
      setAction(r);
      setMsg(`Promote OK · ${id} → ${(r as { to?: string }).to ?? "?"}`);
      refreshAll();
    } catch (e) {
      const err = e as Error & { status?: number; body?: { code?: string } };
      setMsg(`${err.status ?? "?"} · ${err.body?.code ?? "ERR"} · ${err.message}`);
    }
  }

  async function runRecall(id: string) {
    setMsg("");
    try {
      const r = await apiPost(`/v1/apollo/channels/${encodeURIComponent(id)}/recall`, {});
      setAction(r);
      setMsg(`Recall OK · ${id} → ${(r as { to?: string }).to ?? "?"}`);
      refreshAll();
    } catch (e) {
      const err = e as Error & { status?: number; body?: { code?: string } };
      setMsg(`${err.status ?? "?"} · ${err.body?.code ?? "ERR"} · ${err.message}`);
    }
  }

  return (
    <S2Chrome title="Release 通道" lede="对齐 apollo-release · Channel 目录 promote/recall（Full 运行时仍延期）">
      <button type="button" className="btn" onClick={() => void runUpgrade().catch((e) => setMsg(String(e)))}>
        Lite Upgrade
      </button>
      <button type="button" className="btn" style={{ marginLeft: 8 }} onClick={() => refreshAll()}>
        刷新
      </button>
      {msg && <p className="aos-text">{msg}</p>}
      {(fleet.err || channels.err) && <p className="error">{fleet.err || channels.err}</p>}
      <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
        Channels
      </h2>
      <ul className="card-list">
        {(channels.data?.items || []).map((c) => {
          const nxt = nextChannel(c.id);
          const prev = prevChannel(c.id);
          return (
            <li key={c.id} className="card">
              <strong>{c.name || c.id}</strong>{" "}
              <span className="muted">
                {c.status} · rank={c.rank}
                {c.promotedFrom ? ` · promotedFrom=${c.promotedFrom}` : ""}
                {c.recalledFrom ? ` · recalledFrom=${c.recalledFrom}` : ""}
              </span>
              <div style={{ marginTop: 8 }}>
                {nxt && c.status === "open" && (
                  <button type="button" className="btn" onClick={() => void runPromote(c.id)}>
                    Promote → {nxt}
                  </button>
                )}
                {prev && (
                  <button
                    type="button"
                    className="btn"
                    style={{ marginLeft: nxt && c.status === "open" ? 8 : 0 }}
                    onClick={() => void runRecall(c.id)}
                  >
                    Recall → {prev}
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ul>
      <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
        Fleet
      </h2>
      <JsonBlock value={fleet.data} />
      {action != null && <JsonBlock value={action} />}
      {upgrade != null && <JsonBlock value={upgrade} />}
      <p className="muted">
        变更审批 <Link to="/apollo/change">Change</Link> · 资产包 <Link to="/apollo/assets">Assets</Link> ·
        Full Spoke 运行时仍延期（目录骨架 ✅）
      </p>
    </S2Chrome>
  );
}

export function ApolloFerryPage() {
  const status = useJsonGet<Record<string, unknown>>("/v1/apollo/ferry/status");
  const [exportMsg, setExportMsg] = useState("");
  const [bundleB64, setBundleB64] = useState("");
  const [importMsg, setImportMsg] = useState("");

  async function doExport() {
    setExportMsg("");
    setImportMsg("");
    const r = (await apiPost("/v1/apollo/ferry/export", {
      env: "dev",
      channel: "lite",
    })) as { filename?: string; bundleId?: string; contentBase64?: string; sizeBytes?: number };
    setBundleB64(r.contentBase64 || "");
    setExportMsg(
      `export OK · ${r.filename} · ${r.bundleId} · ${r.sizeBytes ?? "?"} bytes`,
    );
  }

  async function doImport(strip = false) {
    setImportMsg("");
    if (!bundleB64) {
      setImportMsg("请先 Export");
      return;
    }
    try {
      const r = (await apiPost("/v1/apollo/ferry/import", {
        contentBase64: bundleB64,
        stripSignature: strip || undefined,
      })) as { ok?: boolean; bundleId?: string; verified?: boolean };
      setImportMsg(`import OK · bundleId=${r.bundleId} · verified=${String(r.verified)}`);
    } catch (e) {
      const err = e as Error & { status?: number; body?: { code?: string } };
      setImportMsg(`${err.status ?? "?"} · ${err.body?.code ?? "ERR"} · ${err.message}`);
    }
  }

  return (
    <S2Chrome title="Ferry 摆渡" lede="对齐 apollo-ferry · T5.6 签名 tar.gz + 镜像清单（HMAC；cosign/skopeo 探针）">
      <button type="button" className="btn" onClick={() => status.reload()}>
        刷新 status
      </button>
      <button type="button" className="btn" style={{ marginLeft: 8 }} onClick={() => void doExport().catch((e) => setExportMsg(String(e)))}>
        Export
      </button>
      <button type="button" className="btn" style={{ marginLeft: 8 }} onClick={() => void doImport(false)}>
        Import
      </button>
      <button type="button" className="btn" style={{ marginLeft: 8 }} onClick={() => void doImport(true)}>
        Import 去签（预期拒）
      </button>
      {status.err && <p className="error">{status.err}</p>}
      <JsonBlock value={status.data} />
      {exportMsg && <p className="aos-text">{exportMsg}</p>}
      {importMsg && <p className="aos-text">{importMsg}</p>}
      <p className="muted">
        镜像层：默认含 artifacts/images.json + images.sig（cosign-dev-hmac；PATH 有 cosign/skopeo 时增强）。
        相关：
        <Link to="/apollo/assets"> Asset Bundle</Link> ·
        <Link to="/apollo/spoke"> Spoke Lite</Link>
      </p>
    </S2Chrome>
  );
}

export function ApolloChangePage() {
  const { data, err, reload } = useJsonGet<{
    items: { id: string; title?: string; status: string; objectType: string; objectId: string }[];
  }>("/v1/aip/drafts");
  const channels = useJsonGet<{ items: ApolloChannel[] }>("/v1/apollo/channels");
  const fleet = useJsonGet<Record<string, unknown>>("/v1/apollo/fleet");

  function refreshAll() {
    reload();
    channels.reload();
    fleet.reload();
  }

  return (
    <S2Chrome title="变更审批" lede="对齐 apollo-change-mgmt · Draft + Channel 梯子摘要（无独立审批引擎）">
      <button type="button" className="btn" onClick={() => refreshAll()}>
        刷新
      </button>
      {(err || channels.err) && <p className="error">{err || channels.err}</p>}
      <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
        Drafts
      </h2>
      <ul className="card-list">
        {(data?.items || []).map((d) => (
          <li key={d.id} className="card">
            <strong>{d.title || d.id}</strong>{" "}
            <span className="muted">
              {d.status} · {d.objectType}/{d.objectId}
            </span>
          </li>
        ))}
      </ul>
      <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
        Channel 梯子
      </h2>
      <ul className="card-list">
        {(channels.data?.items || []).map((c) => (
          <li key={c.id} className="card">
            <strong>{c.name || c.id}</strong>{" "}
            <span className="muted">
              {c.status} · rank={c.rank}
              {c.promotedAt ? ` · promotedAt=${c.promotedAt}` : ""}
              {c.recalledAt ? ` · recalledAt=${c.recalledAt}` : ""}
            </span>
          </li>
        ))}
      </ul>
      {fleet.data && <JsonBlock value={{ hub: (fleet.data as { hub?: unknown }).hub, channels: (fleet.data as { channels?: unknown }).channels }} />}
      <p className="muted">
        晋升/召回操作：
        <Link to="/apollo/release"> Release 通道</Link> · 审批入口：
        <Link to="/aip/drafts"> Draft 收件箱</Link>
      </p>
    </S2Chrome>
  );
}
