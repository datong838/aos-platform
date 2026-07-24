import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost, apiPut } from "../../api/client";
import { useOntologyDrafts } from "../../api/ontologyHooks";
import {
  BpBanner,
  BpDebugPanel,
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

type OkfCol = { src: string; dst: string; ok: boolean };
type OkfMapping = {
  industry: string;
  objectType?: string;
  label?: string;
  columns: OkfCol[];
};

/** 89 · OKF 映射真持久化 + Lint errors */
export function OkfFunnelPage() {
  const funnel = useJsonGet<Record<string, unknown>>("/v1/funnel/WorkOrder/status");
  const modules = useJsonGet<{ items: { id: string; name?: string }[] }>("/v1/modules");
  const [industry, setIndustry] = useState("ecom");
  const [mapping, setMapping] = useState<OkfMapping | null>(null);
  const [lint, setLint] = useState<{ ok?: boolean; errors?: { rule?: string; message?: string }[] } | null>(
    null,
  );
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function loadMapping(ind: string) {
    setErr("");
    try {
      const m = await apiGet<OkfMapping>(`/v1/ontology/okf-mappings/${encodeURIComponent(ind)}`);
      setMapping(m);
    } catch (e) {
      setErr(String((e as Error).message || e));
      setMapping(null);
    }
  }

  useEffect(() => {
    void loadMapping(industry);
  }, [industry]);

  const columns = mapping?.columns || [];

  async function runLint() {
    setMsg("");
    setErr("");
    const ot = mapping?.objectType || "WorkOrder";
    const r = await apiPost<{ ok?: boolean; errors?: { rule?: string; message?: string }[] }>(
      "/v1/ontology/constitution/lint",
      {
        id: ot,
        name: ot,
        published: true,
        properties: columns.filter((c) => c.ok).map((c) => ({
          name: c.dst.split(".").pop() || c.src,
          type: "string",
        })),
      },
    );
    setLint(r);
    setMsg(r.ok ? "Lint 通过" : `Lint 有告警 · ${r.errors?.length ?? 0} 条`);
  }

  async function saveMapping() {
    if (!mapping) return;
    setBusy(true);
    setMsg("");
    setErr("");
    try {
      const saved = await apiPut<OkfMapping>(
        `/v1/ontology/okf-mappings/${encodeURIComponent(industry)}`,
        mapping,
      );
      setMapping(saved);
      setMsg(`已保存 ${industry} 映射 · ${saved.columns.length} 列`);
    } catch (e) {
      setErr(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  function toggleCol(idx: number) {
    if (!mapping) return;
    const next = mapping.columns.map((c, i) => (i === idx ? { ...c, ok: !c.ok } : c));
    setMapping({ ...mapping, columns: next });
  }

  return (
    <S2Chrome
      title="OKF 行业漏斗"
      lede="行业模板 · 列 → Object Type 映射（可保存）· Constitution Lint"
    >
      <div className="ont-page">
      <BpToolbar>
        <button
          type="button"
          className="btn-outline-cyan"
          onClick={() => void runLint().catch((e) => setErr(String(e)))}
        >
          Lint 检查
        </button>
        <button type="button" className="btn-primary" disabled={busy || !mapping} onClick={() => void saveMapping()}>
          {busy ? "保存中…" : "保存映射"}
        </button>
        <button
          type="button"
          className="btn"
          onClick={() => {
            funnel.reload();
            modules.reload();
            void loadMapping(industry);
          }}
        >
          刷新
        </button>
        <Link to="/ontology/funnel" className="btn-nav">
          通用漏斗 →
        </Link>
        <Link to="/ontology" className="btn-nav">
          ← 本体管理
        </Link>
      </BpToolbar>
      {msg && <p className="bp-prop-ok">{msg}</p>}
      {(funnel.err || modules.err || err) && (
        <p className="error">{funnel.err || modules.err || err}</p>
      )}

      <BpSplit
        left={
          <aside className="okf-industry-pane">
            <h2 className="okf-industry-title">行业模板</h2>
            <p className="okf-industry-hint">垂直行业定制 · 选中后右侧编辑映射</p>
            {[
              { id: "ecom", label: "跨境电商 · WorkOrder" },
              { id: "env", label: "环科院 · Pollutant" },
              { id: "bio", label: "生物 · Batch" },
            ].map((i) => (
              <button
                key={i.id}
                type="button"
                className={`okf-industry-item${industry === i.id ? " is-active" : ""}`}
                onClick={() => setIndustry(i.id)}
              >
                {i.label}
              </button>
            ))}
            <p className="muted" style={{ fontSize: "0.75rem", marginTop: 12 }}>
              源 Dataset: <Link to="/data/datasets">WorkOrder-demo</Link>
              <br />
              Object Type: <span className="aos-text">{mapping?.objectType || "—"}</span>
            </p>
          </aside>
        }
        right={
          <div className="okf-map-pane">
            <div className="mp-section-head">
              <h2 className="aos-text" style={{ fontSize: "0.95rem", margin: 0 }}>
                列映射工作台
              </h2>
              <span className="mp-section-hint">{mapping?.label || industry}</span>
            </div>
            <BpMetricGrid
              items={[
                {
                  label: "完成度",
                  value:
                    columns.length === 0
                      ? "—"
                      : `${Math.round((columns.filter((c) => c.ok).length / columns.length) * 100)}%`,
                  tone: "ok",
                },
                { label: "Funnel stage", value: String(funnel.data?.stage || "—"), tone: "muted" },
                { label: "Modules", value: modules.data?.items?.length ?? 0, tone: "muted" },
              ]}
            />
            <BpTable
              columns={["源列", "目标 Property", "状态", ""]}
              rows={columns.map((c, idx) => [
                c.src,
                c.dst,
                c.ok ? <span className="aos-text">已映射</span> : <span className="error">待补</span>,
                <button
                  key={`tog-${c.src}`}
                  type="button"
                  className="bp-action-link"
                  onClick={() => toggleCol(idx)}
                >
                  {c.ok ? "标为待补" : "标为已映射"}
                </button>,
              ])}
            />
            {lint && (
              <BpBanner tone={lint.ok ? "info" : "warn"}>
                Constitution lint ok={String(lint.ok)} · errors={lint.errors?.length ?? 0}
                {(lint.errors || []).length > 0 && (
                  <ul style={{ margin: "0.5rem 0 0", paddingLeft: "1.1rem", fontSize: "0.8rem" }}>
                    {lint.errors!.map((e, i) => (
                      <li key={i}>
                        {e.rule}: {e.message}
                      </li>
                    ))}
                  </ul>
                )}
              </BpBanner>
            )}
            <BpLinkRow links={[{ to: "/workshop/module-interface", label: "模块接口 →" }]} />
          </div>
        }
      />
      </div>
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
    const seedSource =
      (data?.items || []).find((p) => p.sourceId && p.sourceId !== "demo-file-wo")?.sourceId ||
      "src-qyh-jdbc";
    await apiPost("/v1/pipelines", { id, sourceId: seedSource });
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
        <Link to="/data/pipelines" className="btn-nav">
          ← 管道列表
        </Link>
        {(data?.items || [])[0] && (
          <Link
            to={`/data/pipelines/${encodeURIComponent((data?.items || [])[0].id)}`}
            className="btn-nav-accent"
          >
            打开管道画布 →
          </Link>
        )}
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
                +1 节点 Use LLM · 输出 summary_zh
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
          Diff 预览 · {diffId} · + Use LLM 节点 · + summary_zh 字段
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
    <S2Chrome title="代码库" lede="对齐 code-repositories · 工程目录（非 Git 主机）">
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
        <Link to="/aip/lineage" className="btn-nav">
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
          空 · <Link to="/data">数据连接</Link>
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
    <S2Chrome title="Release 通道" lede="Channel 目录 promote/recall · 健康门控/Asset 同绑（160）· 真舰队仍延期">
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
  const matrix = useJsonGet<{
    hubVersion?: string;
    notes?: string;
    rules?: { component: string; label?: string; min: string; recommended: string }[];
  }>("/v1/ops/version-matrix");
  const [exportMsg, setExportMsg] = useState("");
  const [bundleB64, setBundleB64] = useState("");
  const [importMsg, setImportMsg] = useState("");
  const [desktopVer, setDesktopVer] = useState("0.2.0");
  const [spokeVer, setSpokeVer] = useState("0.3.0");
  const [ferryVer, setFerryVer] = useState("1.0");
  const [checkMsg, setCheckMsg] = useState("");

  async function doCompatCheck() {
    setCheckMsg("");
    try {
      const r = (await apiPost("/v1/ops/version-matrix/check", {
        desktop: desktopVer || undefined,
        spoke: spokeVer || undefined,
        ferryBundle: ferryVer || undefined,
      })) as {
        overall?: string;
        items?: { component: string; status: string; reason?: string; actual?: string }[];
      };
      const lines = (r.items || []).map(
        (i) => `${i.component}=${i.status}${i.actual ? `(${i.actual})` : ""} · ${i.reason || ""}`,
      );
      setCheckMsg(`overall=${r.overall} · ${lines.join("；")}`);
    } catch (e) {
      setCheckMsg(String(e));
    }
  }

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
      <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: 16 }}>
        版本矩阵（TWB.7 · 气隙端对照）
      </h2>
      {matrix.err && <p className="error">{matrix.err}</p>}
      {matrix.data?.notes && <p className="muted">{matrix.data.notes}</p>}
      {matrix.data?.rules && (
        <BpPropGrid
          items={(matrix.data.rules || []).map((r) => ({
            label: r.label || r.component,
            value: `min ${r.min} · 荐 ${r.recommended}`,
          }))}
        />
      )}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8, alignItems: "center" }}>
        <label className="muted">
          desktop{" "}
          <input value={desktopVer} onChange={(e) => setDesktopVer(e.target.value)} style={{ width: 88 }} />
        </label>
        <label className="muted">
          spoke{" "}
          <input value={spokeVer} onChange={(e) => setSpokeVer(e.target.value)} style={{ width: 88 }} />
        </label>
        <label className="muted">
          ferry{" "}
          <input value={ferryVer} onChange={(e) => setFerryVer(e.target.value)} style={{ width: 72 }} />
        </label>
        <button type="button" className="btn" onClick={() => void doCompatCheck()}>
          兼容检查
        </button>
        <button type="button" className="btn" onClick={() => matrix.reload()}>
          刷新矩阵
        </button>
      </div>
      {checkMsg && <p className="aos-text">{checkMsg}</p>}
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
  const ontologyDrafts = useOntologyDrafts();
  const changes = useJsonGet<{ items?: { id?: string; title?: string; kind?: string; status?: string; emergency?: boolean; decidedBy?: string; channelId?: string }[] }>(
    "/v1/apollo/changes",
  );
  const channels = useJsonGet<{ items: ApolloChannel[] }>("/v1/apollo/channels");
  const fleet = useJsonGet<Record<string, unknown>>("/v1/apollo/fleet");
  const [chgTitle, setChgTitle] = useState("channel-promote-review");
  const [chgKind, setChgKind] = useState<"channel" | "hotfix" | "config">("channel");
  const [localErr, setLocalErr] = useState<string | null>(null);

  function refreshAll() {
    ontologyDrafts.reload();
    changes.reload();
    channels.reload();
    fleet.reload();
  }

  async function createChange() {
    setLocalErr(null);
    try {
      await apiPost("/v1/apollo/changes", {
        title: chgTitle.trim() || "change",
        kind: chgKind,
        channelId: chgKind === "hotfix" ? "hotfix" : "staging",
        summary: "apollo-ops-160",
        emergency: chgKind === "hotfix",
      });
      changes.reload();
    } catch (e) {
      setLocalErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function decide(id: string, approve: boolean) {
    setLocalErr(null);
    try {
      await apiPost(
        `/v1/apollo/changes/${encodeURIComponent(id)}/${approve ? "approve" : "reject"}`,
        { note: approve ? "ok" : "reject" },
      );
      changes.reload();
    } catch (e) {
      setLocalErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function mergeStable(id: string) {
    setLocalErr(null);
    try {
      await apiPost(`/v1/apollo/changes/${encodeURIComponent(id)}/merge-stable`, {});
      changes.reload();
    } catch (e) {
      setLocalErr(e instanceof Error ? e.message : String(e));
    }
  }

  const hub = fleet.data as {
    hub?: { apolloOpsDeepeningReady?: boolean; fullSpokeRuntimeDeferred?: boolean };
  };

  return (
    <S2Chrome
      title="变更审批"
      lede="Apollo 运维深水 MVP（160）· 环境 Change 单 · ≠ Ontology Draft · ≠ 真多集群"
    >
      <BpToolbar>
        <button type="button" className="btn" onClick={() => refreshAll()}>
          刷新
        </button>
        <Link to="/apollo/release" className="btn-nav">
          Release 通道
        </Link>
      </BpToolbar>
      {(ontologyDrafts.err || channels.err || changes.err || localErr) && (
        <p className="error">{ontologyDrafts.err || channels.err || changes.err || localErr}</p>
      )}
      <p className="muted" style={{ fontSize: "0.75rem" }}>
        opsDeepening=
        {hub?.hub?.apolloOpsDeepeningReady ? "ready" : "—"} · fullK8s=
        {hub?.hub?.fullSpokeRuntimeDeferred ? "deferred" : "—"}
      </p>

      <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
        环境 Change
      </h2>
      <div
        style={{
          display: "grid",
          gap: 8,
          gridTemplateColumns: "1fr auto auto",
          maxWidth: 520,
          fontSize: "0.8rem",
          alignItems: "end",
          marginBottom: 8,
        }}
      >
        <label>
          title
          <input
            value={chgTitle}
            onChange={(e) => setChgTitle(e.target.value)}
            style={{ display: "block", width: "100%", marginTop: 4 }}
          />
        </label>
        <label>
          kind
          <select
            value={chgKind}
            onChange={(e) => setChgKind(e.target.value as "channel" | "hotfix" | "config")}
            style={{ display: "block", marginTop: 4 }}
          >
            <option value="channel">channel</option>
            <option value="hotfix">hotfix</option>
            <option value="config">config</option>
          </select>
        </label>
        <button type="button" className="btn" onClick={() => void createChange()}>
          创建
        </button>
      </div>
      <ul className="card-list">
        {(changes.data?.items || []).map((c) => (
          <li key={c.id} className="card">
            <strong>{c.title || c.id}</strong>{" "}
            <span className="muted">
              {c.kind} · {c.status}
              {c.emergency ? " · emergency" : ""}
              {c.channelId ? ` · ${c.channelId}` : ""}
              {c.decidedBy ? ` · by ${c.decidedBy}` : ""}
            </span>
            <div style={{ marginTop: 6, display: "flex", gap: 8, flexWrap: "wrap" }}>
              {c.status === "pending" && (
                <>
                  <button type="button" className="btn" onClick={() => void decide(String(c.id), true)}>
                    批准
                  </button>
                  <button
                    type="button"
                    className="btn-nav"
                    onClick={() => void decide(String(c.id), false)}
                  >
                    驳回
                  </button>
                </>
              )}
              {c.kind === "hotfix" && c.status === "approved" && (
                <button type="button" className="btn" onClick={() => void mergeStable(String(c.id))}>
                  合并回 stable（stub）
                </button>
              )}
            </div>
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

      <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
        Ontology Drafts（旁路 · 非环境变更）
      </h2>
      <ul className="card-list">
        {(ontologyDrafts.data?.items || []).slice(0, 5).map((d) => (
          <li key={d.id} className="card">
            <strong>{d.title || d.id}</strong>{" "}
            <span className="muted">
              {d.status} · {d.objectType}/{d.objectId}
            </span>
          </li>
        ))}
      </ul>
      <p className="muted">
        晋升/召回：
        <Link to="/apollo/release"> Release 通道</Link> · Ontology 审批：
        <Link to="/aip/drafts"> Draft 收件箱</Link>
      </p>
    </S2Chrome>
  );
}

/** 数据源与同步 · 同步配置 — 管理同步任务与调度参数 */
export function SyncConfigPage() {
  const schedules = useJsonGet<{ items: { id: string; name?: string; cron?: string; active?: boolean }[] }>("/v1/schedules");
  const [msg, setMsg] = useState("");

  async function toggle(id: string, active: boolean) {
    try {
      await apiPost(`/v1/schedules/${encodeURIComponent(id)}/status`, { active });
      setMsg(`已${active ? "启用" : "停用"} ${id}`);
      schedules.reload();
    } catch (e) {
      setMsg(String((e as Error).message || e));
    }
  }

  const rows = (schedules.data?.items || []).map((s) => [
    s.id,
    s.name || "—",
    s.cron || "—",
    s.active ? "运行中" : "停用",
    <button
      key={s.id}
      type="button"
      className="bp-action-link"
      onClick={() => void toggle(s.id, !s.active)}
    >
      {s.active ? "停用" : "启用"}
    </button>,
  ]);

  return (
    <S2Chrome title="同步配置" lede="管理数据源同步计划与任务启停 · 与计划编辑器联动">
      <BpToolbar>
        <Link to="/data/schedules" className="btn-nav">
          打开计划编辑器 →
        </Link>
        <Link to="/data" className="btn-nav">
          数据链接器 →
        </Link>
        <button type="button" className="btn" onClick={() => schedules.reload()}>
          刷新
        </button>
      </BpToolbar>
      {schedules.err && <p className="error">{schedules.err}</p>}
      {msg && <p className="aos-text">{msg}</p>}
      <BpTable
        columns={["id", "名称", "Cron", "状态", ""]}
        rows={rows.length ? rows : [["—", "—", "—", "—", "—"]]}
      />
      <BpBanner tone="info">
        同步配置聚焦「任务是否启用、调度参数」；具体 Cron 与上游触发请在「计划编辑器」编辑。
      </BpBanner>
    </S2Chrome>
  );
}

/** 数据源与同步 · 同步路由 — 按源/目标/规则查看同步分发路径 */
export function SyncRoutesPage() {
  const routes = useJsonGet<{ items: { id: string; source?: string; target?: string; rule?: string }[] }>("/v1/sync-routes");
  const [msg, setMsg] = useState("");

  const rows = (routes.data?.items || []).map((r) => [
    r.id,
    r.source || "—",
    r.target || "—",
    r.rule || "—",
  ]);

  return (
    <S2Chrome title="同步路由" lede="按源、目标、规则查看同步分发路径 · 支持路由规则调试">
      <BpToolbar>
        <Link to="/data" className="btn-nav">
          数据链接器 →
        </Link>
        <Link to="/data/sync-config" className="btn-nav">
          同步配置 →
        </Link>
        <button type="button" className="btn" onClick={() => routes.reload()}>
          刷新
        </button>
      </BpToolbar>
      {routes.err && <p className="error">{routes.err}</p>}
      {msg && <p className="aos-text">{msg}</p>}
      <BpTable
        columns={["id", "源", "目标", "规则"]}
        rows={rows.length ? rows : [["—", "—", "—", "—"]]}
      />
      <BpBanner tone="info">
        路由规则决定数据从哪个源同步到哪个目标；与「同步配置」中的任务一一对应。
      </BpBanner>
    </S2Chrome>
  );
}

/** 本体 · 数字孪生 · OKF 概览 — 行业模板与映射活动概览 */
export function OkfOverviewPage() {
  const funnel = useJsonGet<Record<string, unknown>>("/v1/funnel/WorkOrder/status");
  const [industries] = useState([
    { id: "ecom", name: "电商", mapped: true },
    { id: "supply", name: "供应链", mapped: true },
    { id: "finance", name: "金融", mapped: false },
    { id: "healthcare", name: "医疗", mapped: false },
  ]);

  return (
    <S2Chrome title="OKF 概览" lede="行业漏斗模板与映射活动概览 · 选择行业查看详情">
      <BpToolbar>
        <Link to="/ontology/okf-funnel" className="btn-nav">
          OKF 行业漏斗 →
        </Link>
        <Link to="/ontology/funnel" className="btn-nav">
          漏斗管道 →
        </Link>
        <button type="button" className="btn" onClick={() => funnel.reload()}>
          刷新
        </button>
      </BpToolbar>
      {funnel.err && <p className="error">{funnel.err}</p>}

      <div className="bp-ws-section-title">行业模板</div>
      <div className="bp-index-grid bp-index-grid-4" style={{ marginBottom: "1rem" }}>
        {industries.map((ind) => (
          <Link
            key={ind.id}
            to={`/ontology/okf-funnel?industry=${ind.id}`}
            className="bp-discover-card bp-discover-violet"
            style={{ textDecoration: "none" }}
          >
            <div className="bp-discover-head">
              <span className="bp-discover-title">{ind.name}</span>
              <span className={`bp-tag ${ind.mapped ? "bp-tag-ok" : "bp-tag-warn"}`}>
                {ind.mapped ? "已映射" : "待映射"}
              </span>
            </div>
            <p className="bp-discover-meta">{ind.id}</p>
          </Link>
        ))}
      </div>

      <BpBanner tone="info">
        OKF（Ontology Kernel Framework）行业漏斗将外部数据模型映射为本体属性；
        每个行业有预置模板，可在「OKF 行业漏斗」页面编辑映射规则。
      </BpBanner>
    </S2Chrome>
  );
}

/** 运维交付 · 接入案例 — 端到端链路案例展示 */
export function IntegrationCasesPage() {
  const [cases] = useState([
    {
      id: "ecom-e2e",
      title: "电商平台端到端链路",
      platforms: 9,
      connectors: 12,
      status: "live",
      stages: ["数据接入", "同步", "管道清洗", "OKF 映射", "本体实例化", "应用层消费"],
    },
    {
      id: "supply-chain",
      title: "供应链全程追溯",
      platforms: 5,
      connectors: 8,
      status: "live",
      stages: ["数据接入", "同步", "管道清洗", "OKF 映射", "本体实例化", "应用层消费"],
    },
    {
      id: "finance-risk",
      title: "金融风控实时告警",
      platforms: 3,
      connectors: 4,
      status: "wip",
      stages: ["数据接入", "同步", "管道清洗", "OKF 映射"],
    },
  ]);

  return (
    <S2Chrome title="接入案例" lede="从数据接入到应用层消费的端到端案例 · 每条案例展示一条完整链路">
      <BpToolbar>
        <Link to="/data" className="btn-nav">
          数据链接器 →
        </Link>
        <Link to="/ontology" className="btn-nav">
          本体管理 →
        </Link>
      </BpToolbar>

      <BpMetricGrid
        items={[
          { label: "平台总数", value: "9", tone: "ok" },
          { label: "总连接器数", value: "24", tone: "muted" },
          { label: "已上线", value: "7", tone: "ok" },
          { label: "进行中", value: "2", tone: "warn" },
        ]}
      />

      <div className="bp-discover-grid" style={{ marginTop: "1rem" }}>
        {cases.map((c) => (
          <div key={c.id} className="bp-discover-card bp-discover-violet">
            <div className="bp-discover-head">
              <span className="bp-discover-title">{c.title}</span>
              <span className={`bp-tag ${c.status === "live" ? "bp-tag-ok" : "bp-tag-warn"}`}>
                {c.status === "live" ? "已上线" : "进行中"}
              </span>
            </div>
            <p className="bp-discover-meta">
              {c.platforms} 平台 · {c.connectors} 连接器
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 8 }}>
              {c.stages.map((s, i) => (
                <span key={s} className="bp-tag" style={{ fontSize: "0.65rem" }}>
                  {i + 1}. {s}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>

      <BpBanner tone="info">
        每个案例展示一条完整链路：数据接入 → 同步 → 管道清洗 → OKF 映射 → 本体实例化 → 应用层消费。
      </BpBanner>
    </S2Chrome>
  );
}
