import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost } from "../api/client";
import { PageChrome } from "../components/PageChrome";
import {
  BpLinkRow,
  BpMetricGrid,
  BpPropGrid,
  BpTable,
  BpToolbar,
} from "./s2/blueprintUi";

type Channel = {
  id: string;
  name?: string;
  status?: string;
  promotedFrom?: string | null;
  promotedAt?: string | null;
  rank?: number;
};

type Spoke = {
  id: string;
  kind?: string;
  channelId?: string;
  status?: string;
  runtime?: string;
};

type FleetPayload = {
  hub?: {
    id?: string;
    mode?: string;
    status?: string;
    channelCatalogReady?: boolean;
    fullSpokeRuntimeDeferred?: boolean;
  };
  spokes?: Spoke[];
  channels?: Channel[];
};

/** 84 · Hub 舰队 · Fleet/Channel/Assets 三列 bp-ui（禁 JSON 主面板） */
export function ApolloPage() {
  const [fleet, setFleet] = useState<FleetPayload | null>(null);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [spokes, setSpokes] = useState<Spoke[]>([]);
  const [selectedCh, setSelectedCh] = useState<string>("");
  const [channelDetail, setChannelDetail] = useState<Record<string, unknown> | null>(null);
  const [bundle, setBundle] = useState<Record<string, unknown> | null>(null);
  const [contents, setContents] = useState("WorkOrder,CloseWorkOrder");
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setErr(null);
    const [f, ch, sp] = await Promise.all([
      apiGet<FleetPayload>("/v1/apollo/fleet"),
      apiGet<{ items: Channel[] }>("/v1/apollo/channels"),
      apiGet<{ items: Spoke[] }>("/v1/apollo/spokes"),
    ]);
    setFleet(f);
    setChannels(ch.items || []);
    setSpokes(sp.items || []);
    const prefer = ch.items?.[0]?.id || f.channels?.[0]?.id || "";
    if (prefer) {
      setSelectedCh(prefer);
      const detail = await apiGet<Record<string, unknown>>(
        `/v1/apollo/channels/${encodeURIComponent(prefer)}`,
      );
      setChannelDetail(detail);
    }
  }, []);

  useEffect(() => {
    refresh().catch((e) => setErr(String(e.message || e)));
  }, [refresh]);

  async function selectChannel(id: string) {
    setSelectedCh(id);
    setErr(null);
    try {
      const detail = await apiGet<Record<string, unknown>>(
        `/v1/apollo/channels/${encodeURIComponent(id)}`,
      );
      setChannelDetail(detail);
      setMsg(`已加载 Channel ${id}`);
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  async function promoteSelected() {
    if (!selectedCh) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await apiPost<Record<string, unknown>>(
        `/v1/apollo/channels/${encodeURIComponent(selectedCh)}/promote`,
        {},
      );
      setChannelDetail(r);
      setMsg(`已 promote ${selectedCh}`);
      await refresh();
    } catch (e) {
      setErr(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  async function packAssets() {
    setBusy(true);
    setErr(null);
    try {
      const list = contents
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const b = await apiPost<Record<string, unknown>>("/v1/apollo/assets", {
        hotfix: false,
        contents: list.length ? list : ["WorkOrder"],
      });
      setBundle(b);
      setMsg(`Asset Bundle ${String(b.bundleId || "")} · validated=${String(b.validated)}`);
    } catch (e) {
      setErr(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  const hub = fleet?.hub;

  return (
    <PageChrome
      title="Hub 舰队总览"
      lede="中心 Hub 管理各 Spoke 环境 · Probe 健康度 · Full Ferry 仍延期"
    >
      <BpToolbar>
        <button type="button" className="btn" onClick={() => void refresh().catch((e) => setErr(String(e)))}>
          刷新舰队
        </button>
        <Link to="/apollo/release" className="muted">
          发布通道 →
        </Link>
        <Link to="/apollo/ferry" className="muted">
          Ferry 向导
        </Link>
      </BpToolbar>

      {msg && <p className="aos-text">{msg}</p>}
      {err && <p className="error">{err}</p>}

      {hub && (
        <BpMetricGrid
          items={[
            { label: "Hub 区域", value: hub.id || "—", tone: "ok" },
            { label: "Hub 状态", value: hub.status || "—", tone: "ok" },
            {
              label: "在线 Spoke",
              value: `${spokes.filter((s) => s.status !== "offline").length} / ${spokes.length || "—"}`,
              tone: "ok",
            },
            {
              label: "Full 运行时",
              value: hub.fullSpokeRuntimeDeferred ? "延期" : "—",
              tone: "warn",
            },
          ]}
        />
      )}

      <div className="canvas-grid canvas-grid-3">
        <div className="card">
          <h2 className="bp-ws-section-title">1 · Fleet · Spokes</h2>
          <BpTable
            columns={["Spoke", "kind", "channel", "status"]}
            rows={spokes.map((s) => [
              <Link key={s.id} to="/apollo/spoke">
                {s.id}
              </Link>,
              s.kind || "—",
              s.channelId || "—",
              s.status || "—",
            ])}
          />
          {spokes.length === 0 && <p className="muted">暂无 Spoke</p>}
        </div>

        <div className="card">
          <h2 className="bp-ws-section-title">2 · Channel</h2>
          <ul className="card-list">
            {channels.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  className={c.id === selectedCh ? "nav-link active card" : "nav-link card"}
                  style={{ width: "100%", textAlign: "left" }}
                  onClick={() => void selectChannel(c.id)}
                >
                  {c.name || c.id}{" "}
                  <span className="muted">
                    {c.status}
                    {c.promotedFrom ? ` · from ${c.promotedFrom}` : ""}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <button
            type="button"
            className="btn"
            disabled={!selectedCh || busy}
            onClick={() => void promoteSelected()}
          >
            Promote 选中 Channel
          </button>
          {channelDetail && (
            <BpPropGrid
              items={[
                { label: "id", value: String(channelDetail.id ?? selectedCh) },
                { label: "status", value: String(channelDetail.status ?? "—") },
                { label: "rank", value: String(channelDetail.rank ?? "—") },
                {
                  label: "promotedFrom",
                  value: String(channelDetail.promotedFrom ?? "—"),
                },
              ]}
            />
          )}
        </div>

        <div className="card">
          <h2 className="bp-ws-section-title">3 · Assets</h2>
          <label className="muted" style={{ display: "block" }}>
            contents（逗号分隔）{" "}
            <input value={contents} onChange={(e) => setContents(e.target.value)} />
          </label>
          <button
            type="button"
            className="btn"
            style={{ marginTop: 12 }}
            disabled={busy}
            onClick={() => void packAssets()}
          >
            {busy ? "打包中…" : "打包 Asset Bundle"}
          </button>
          {bundle && (
            <BpPropGrid
              items={[
                { label: "bundleId", value: String(bundle.bundleId ?? "—") },
                { label: "validated", value: String(bundle.validated ?? "—") },
                {
                  label: "contents",
                  value: Array.isArray(bundle.contents)
                    ? (bundle.contents as string[]).join(", ")
                    : "—",
                },
              ]}
            />
          )}
          <p className="muted" style={{ marginTop: 8, fontSize: "0.75rem" }}>
            深页 <Link to="/apollo/assets">/apollo/assets</Link> · Ferry{" "}
            <Link to="/apollo/ferry">/apollo/ferry</Link>
          </p>
        </div>
      </div>

      <BpLinkRow
        links={[
          { to: "/apollo/spoke", label: "Spoke 详情" },
          { to: "/apollo/config", label: "配置与密钥" },
          { to: "/apollo/change", label: "变更审批" },
        ]}
      />
    </PageChrome>
  );
}
