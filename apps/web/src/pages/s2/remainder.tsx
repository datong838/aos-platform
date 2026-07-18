import { useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost } from "../../api/client";
import {
  BpBanner,
  BpDebugPanel,
  BpKvList,
  BpLineageTimeline,
  BpLinkRow,
  BpMetricGrid,
  BpPropGrid,
  BpSplit,
  BpTable,
  BpTabs,
  BpToolbar,
} from "./blueprintUi";
import { JsonBlock, S2Chrome, useJsonGet } from "./shared";

/** 77 · 对齐 okf-funnel / funnel.html */
export function OkfFunnelPage() {
  const funnel = useJsonGet<Record<string, unknown>>("/v1/funnel/WorkOrder/status");
  const modules = useJsonGet<{ items: { id: string; name?: string }[] }>("/v1/modules");
  const [industry, setIndustry] = useState("ecom");
  const [lint, setLint] = useState<{ ok?: boolean; issues?: unknown[] } | null>(null);
  const [msg, setMsg] = useState("");

  const columns = [
    { src: "order_id", dst: "WorkOrder.id", ok: true },
    { src: "title", dst: "WorkOrder.title", ok: true },
    { src: "status", dst: "WorkOrder.status", ok: true },
    { src: "site", dst: "WorkOrder.site", ok: true },
  ];

  async function runLint() {
    setMsg("");
    const r = await apiPost<{ ok?: boolean; issues?: unknown[] }>("/v1/ontology/constitution/lint", {
      id: "WorkOrder",
      name: "WorkOrder",
      published: true,
      properties: [
        { name: "status", type: "string" },
        { name: "site", type: "string" },
      ],
    });
    setLint(r);
    setMsg(r.ok ? "Lint 通过" : "Lint 有告警");
  }

  return (
    <S2Chrome title="OKF 行业漏斗" lede="对齐 okf-funnel · 行业模板 + 列映射 + Constitution">
      <BpToolbar>
        <button type="button" className="btn" onClick={() => void runLint().catch((e) => setMsg(String(e)))}>
          Lint 检查
        </button>
        <button type="button" className="btn" onClick={() => { funnel.reload(); modules.reload(); }}>
          刷新
        </button>
        <Link to="/ontology/funnel" className="muted">
          通用漏斗 →
        </Link>
      </BpToolbar>
      {msg && <p className="aos-text">{msg}</p>}
      {(funnel.err || modules.err) && <p className="error">{funnel.err || modules.err}</p>}

      <BpSplit
        left={
          <>
            <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
              OKF · 行业垂直定制
            </h2>
            {[
              { id: "ecom", label: "跨境电商 · WorkOrder" },
              { id: "env", label: "环科院 · Pollutant" },
              { id: "bio", label: "生物 · Batch" },
            ].map((i) => (
              <button
                key={i.id}
                type="button"
                className={industry === i.id ? "nav-link active card" : "nav-link card"}
                style={{ width: "100%", textAlign: "left", marginBottom: 4 }}
                onClick={() => setIndustry(i.id)}
              >
                {i.label}
              </button>
            ))}
            <p className="muted" style={{ fontSize: "0.75rem", marginTop: 12 }}>
              源 Dataset: <Link to="/data/datasets">WorkOrder-demo</Link>
            </p>
          </>
        }
        right={
          <>
            <h1 className="aos-text" style={{ fontSize: "1rem" }}>
              列 → Object Type 映射
            </h1>
            <BpMetricGrid
              items={[
                { label: "完成度", value: `${Math.round((columns.filter((c) => c.ok).length / columns.length) * 100)}%`, tone: "ok" },
                { label: "Funnel stage", value: String(funnel.data?.stage || "—"), tone: "muted" },
                { label: "Modules", value: modules.data?.items?.length ?? 0, tone: "muted" },
              ]}
            />
            <BpTable
              columns={["源列", "目标 Property", "状态"]}
              rows={columns.map((c) => [
                c.src,
                c.dst,
                c.ok ? <span className="aos-text">已映射</span> : <span className="error">待补</span>,
              ])}
            />
            {lint && (
              <BpBanner tone={lint.ok ? "info" : "warn"}>
                Constitution lint ok={String(lint.ok)} · issues={lint.issues?.length ?? 0}
              </BpBanner>
            )}
            <BpLinkRow
              links={[
                { to: "/workshop/module-interface", label: "模块接口" },
                { to: "/ontology", label: "本体管理" },
              ]}
            />
          </>
        }
      />
    </S2Chrome>
  );
}

/** 85 · 对齐 pipeline-proposals · 待审/历史 Tab + 提案卡 */
export function PipelineProposalsPage() {
  const { data, err, reload } = useJsonGet<{ items: { id: string; sourceId?: string; target?: string }[] }>(
    "/v1/pipelines",
  );
  const [tab, setTab] = useState<"proposals" | "history">("proposals");
  const [msg, setMsg] = useState("");
  const [diffId, setDiffId] = useState<string | null>(null);

  async function propose() {
    const id = `prop-${Date.now().toString(36)}`;
    await apiPost("/v1/pipelines", { id, sourceId: "demo-file-wo" });
    setMsg(`已创建管道提案 ${id}`);
    reload();
  }

  const historyRows = [
    ["v12 · 合并提案 #prop-115", "7 天前 · 张三"],
    ["v11 · 修复空值过滤", "14 天前 · 李四"],
    ["v10 · 初始上线", "30 天前 · 系统"],
  ];

  return (
    <S2Chrome title="管道提案与历史" lede="变更提案审阅与版本回溯 · 管道即提案">
      <BpToolbar>
        <button type="button" className="btn" onClick={() => void propose().catch((e) => setMsg(String(e)))}>
          新建提案
        </button>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
        <Link to="/data/pipelines" className="muted">
          打开管道画布 →
        </Link>
      </BpToolbar>

      <BpTabs
        tabs={[
          { id: "proposals", label: "待审提案" },
          { id: "history", label: "历史版本" },
        ]}
        active={tab}
        onChange={(id) => setTab(id as "proposals" | "history")}
      />

      {msg && <p className="aos-text">{msg}</p>}
      {err && <p className="error">{err}</p>}

      {tab === "proposals" && (
        <div className="bp-discover-grid">
          {(data?.items || []).slice(0, 5).map((p, i) => (
            <div
              key={p.id}
              className={`bp-discover-card bp-discover-${i === 0 ? "violet" : "muted"}`}
            >
              <div className="bp-discover-head">
                <span className="bp-discover-title">提案 {p.id}</span>
                <span className="bp-tag bp-tag-warn">待审</span>
              </div>
              <p className="bp-discover-meta">
                source={p.sourceId} → {p.target || "dataset"}
              </p>
              <p className="muted" style={{ fontSize: "0.75rem" }}>
                +1 节点 Use LLM · 输出 summary_zh（示意）
              </p>
              <div className="bp-object-actions">
                <button type="button" className="btn">
                  合并到主分支
                </button>
                <button type="button" className="btn" onClick={() => setDiffId(p.id)}>
                  预览 Diff
                </button>
              </div>
            </div>
          ))}
          {(data?.items?.length || 0) === 0 && (
            <p className="muted">暂无提案 · 点「新建提案」</p>
          )}
        </div>
      )}

      {tab === "history" && (
        <BpTable columns={["版本", "说明"]} rows={historyRows} />
      )}

      {diffId && (
        <BpBanner tone="info">
          Diff 预览 · {diffId} · + Use LLM 节点 · + summary_zh 字段（引擎后置 · 当前为蓝图占位）
        </BpBanner>
      )}

      <BpLinkRow links={[{ to: "/data/pipelines", label: "← 管道列表" }]} />
    </S2Chrome>
  );
}

/** 77 · 对齐 code-repositories.html */
export function CodeReposPage() {
  const { data, err, reload } = useJsonGet<{
    items: { id: string; name: string; url?: string; branch?: string; status?: string }[];
    store?: string;
  }>("/v1/code-repos");

  return (
    <S2Chrome title="代码库" lede="对齐 code-repositories · Dev 目录（非 Git 主机）">
      <BpToolbar>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
      </BpToolbar>
      {err && <p className="error">{err}</p>}
      <p className="muted">store={data?.store ?? "—"}</p>
      <BpTable
        columns={["仓库", "URL", "分支", "状态"]}
        rows={(data?.items || []).map((r) => [
          <strong>{r.name}</strong>,
          <span className="muted">{r.url}</span>,
          r.branch || "—",
          r.status || "—",
        ])}
      />
    </S2Chrome>
  );
}

/** 77 · 对齐 lineage.html */
export function DataLineagePage() {
  const datasets = useJsonGet<{ items: { rid: string; name?: string; pipelineId?: string; sourceId?: string }[] }>(
    "/v1/datasets",
  );
  const syncs = useJsonGet<{ items: { id: string; sourceId?: string; status?: string }[] }>("/v1/syncs");
  const [history, setHistory] = useState<unknown>(null);
  const [rid, setRid] = useState("");

  async function loadHistory(target: string) {
    setRid(target);
    const r = await apiGet(`/v1/datasets/${encodeURIComponent(target)}/history`);
    setHistory(r);
  }

  return (
    <S2Chrome title="数据沿袭" lede="对齐 lineage · Source → Sync → Dataset → Build">
      <BpToolbar>
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
        <Link to="/aip/lineage" className="muted">
          AIP 决策谱系 →
        </Link>
      </BpToolbar>
      {(datasets.err || syncs.err) && <p className="error">{datasets.err || syncs.err}</p>}

      <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
        沿袭链
      </h2>
      {(datasets.data?.items || []).map((d) => {
        const syncId =
          (syncs.data?.items || []).find((s) => s.sourceId === d.sourceId)?.id || "—";
        return (
          <div key={d.rid} style={{ marginBottom: "1rem" }}>
            <div className="bp-section-label">{d.name || d.rid}</div>
            <BpLineageTimeline
              steps={[
                { phase: "Source", title: d.sourceId || "—", tone: "input" },
                { phase: "Sync", title: syncId, subtitle: d.sourceId, tone: "process" },
                { phase: "Pipeline", title: d.pipelineId || "—", tone: "process" },
                { phase: "Dataset", title: d.rid, subtitle: d.name, tone: "output" },
              ]}
            />
            <button
              type="button"
              className="btn"
              style={{ marginTop: 8 }}
              onClick={() => void loadHistory(d.rid).catch(console.error)}
            >
              查看 History
            </button>
          </div>
        );
      })}

      {(syncs.data?.items || []).length > 0 && (
        <>
          <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: "1rem" }}>
            Syncs
          </h2>
          <BpTable
            columns={["Sync", "Source", "状态"]}
            rows={(syncs.data?.items || []).map((s) => [s.id, s.sourceId || "—", s.status || "—"])}
          />
        </>
      )}

      {history != null && (
        <>
          <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
            History · {rid}
          </h2>
          <JsonBlock value={history} />
        </>
      )}
      {(datasets.data?.items?.length || 0) === 0 && (
        <p className="muted">
          空 · <Link to="/data">确保演示种子</Link>
        </p>
      )}
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
        Hub 舰队
      </h2>
      {fleet.data && (
        <>
          <BpMetricGrid
            items={[
              {
                label: "Hub",
                value: String((fleet.data as { hub?: { id?: string; status?: string } }).hub?.id || "—"),
                tone: "ok",
              },
              {
                label: "Hub 状态",
                value: String((fleet.data as { hub?: { status?: string } }).hub?.status || "—"),
                tone: "ok",
              },
              {
                label: "Spokes",
                value: String((fleet.data as { spokes?: unknown[] }).spokes?.length ?? 0),
                tone: "muted",
              },
              {
                label: "Full 运行时",
                value: (fleet.data as { hub?: { fullSpokeRuntimeDeferred?: boolean } }).hub
                  ?.fullSpokeRuntimeDeferred
                  ? "延期"
                  : "—",
                tone: "warn",
              },
            ]}
          />
          <BpTable
            columns={["Channel", "状态", "rank"]}
            rows={(
              (fleet.data as { channels?: { id: string; name?: string; status?: string; rank?: number }[] })
                .channels || []
            ).map((c) => [c.name || c.id, c.status || "—", String(c.rank ?? "—")])}
          />
        </>
      )}
      {action != null && (
        <BpDebugPanel value={action} title="最近操作 JSON" />
      )}
      {upgrade != null && (
        <BpDebugPanel value={upgrade} title="Upgrade JSON" />
      )}
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
      {status.data && (
        <BpPropGrid
          items={Object.entries(status.data)
            .slice(0, 8)
            .map(([k, v]) => ({
              label: k,
              value:
                v == null
                  ? "—"
                  : typeof v === "object"
                    ? Array.isArray(v)
                      ? `[${(v as unknown[]).length}]`
                      : "{…}"
                    : String(v),
            }))}
        />
      )}
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
      {fleet.data && (
        <BpMetricGrid
          items={[
            {
              label: "Hub",
              value: String((fleet.data as { hub?: { id?: string } }).hub?.id || "—"),
              tone: "ok",
            },
            {
              label: "Channels",
              value: String((fleet.data as { channels?: unknown[] }).channels?.length ?? 0),
              tone: "muted",
            },
          ]}
        />
      )}
      <p className="muted">
        晋升/召回操作：
        <Link to="/apollo/release"> Release 通道</Link> · 审批入口：
        <Link to="/aip/drafts"> Draft 收件箱</Link>
      </p>
    </S2Chrome>
  );
}
