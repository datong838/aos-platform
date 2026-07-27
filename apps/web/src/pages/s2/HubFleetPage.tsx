import { useState } from "react";
import { Link } from "react-router-dom";
import { S2Chrome, useJsonGet, apiPost } from "./shared";
import { BpLinkRow, BpToolbar } from "./blueprintUi";

type Health = "online" | "degraded" | "offline";
type Channel = "stable" | "beta" | "rc";
type SpokeType = "full" | "lite";

type Spoke = {
  id: string;
  name: string;
  health: Health;
  channel: Channel;
  spokeType: SpokeType;
  bundle: string;
  latencyMs: number;
  probeStatus: "normal" | "partial" | "none";
  lastProbe: string;
  region: string;
};

type HubData = {
  hubRegion: string;
  onlineCount: number;
  totalCount: number;
  lastProbe: string;
};

const MOCK_HUB: HubData = {
  hubRegion: "cn-east-hub-01",
  onlineCount: 5,
  totalCount: 6,
  lastProbe: "12 秒前 · 全部通道同步",
};

const MOCK_SPOKES: Spoke[] = [
  {
    id: "spoke-prod-sh",
    name: "spoke-prod-sh",
    health: "online",
    channel: "stable",
    spokeType: "full",
    bundle: "2.14.1",
    latencyMs: 42,
    probeStatus: "normal",
    lastProbe: "刚",
    region: "上海",
  },
  {
    id: "spoke-prod-bj",
    name: "spoke-prod-bj",
    health: "online",
    channel: "stable",
    spokeType: "full",
    bundle: "2.14.1",
    latencyMs: 38,
    probeStatus: "normal",
    lastProbe: "刚",
    region: "北京",
  },
  {
    id: "spoke-pilot-gz",
    name: "spoke-pilot-gz",
    health: "degraded",
    channel: "beta",
    spokeType: "lite",
    bundle: "2.15.0-rc.3",
    latencyMs: 210,
    probeStatus: "partial",
    lastProbe: "刚",
    region: "广州",
  },
  {
    id: "spoke-staging",
    name: "spoke-staging",
    health: "online",
    channel: "rc",
    spokeType: "full",
    bundle: "2.15.0-rc.5",
    latencyMs: 0,
    probeStatus: "normal",
    lastProbe: "刚",
    region: "测试",
  },
  {
    id: "spoke-edge-factory",
    name: "spoke-edge-factory",
    health: "offline",
    channel: "stable",
    spokeType: "lite",
    bundle: "—",
    latencyMs: 0,
    probeStatus: "none",
    lastProbe: "3 天前",
    region: "工厂边缘",
  },
];

function healthLabel(h: Health) {
  switch (h) {
    case "online":
      return "健康";
    case "degraded":
      return "降级";
    case "offline":
      return "离线";
  }
}

function healthBadgeClass(h: Health) {
  switch (h) {
    case "online":
      return "bp-discover-badge bp-discover-badge-ok";
    case "degraded":
      return "bp-discover-badge bp-discover-badge-warn";
    case "offline":
      return "bp-discover-badge bp-discover-badge-bad";
  }
}

function probeText(s: Spoke) {
  switch (s.probeStatus) {
    case "normal":
      return (
        <>
          <span className="bp-metric-value" style={{ color: "var(--status-ok, #16a34a)" }}>
            ● 正常
          </span>
          {s.latencyMs > 0 && <span className="muted"> · 延迟 {s.latencyMs}ms</span>}
        </>
      );
    case "partial":
      return (
        <>
          <span style={{ color: "var(--status-warn, #ca8a04)" }}>○ 部分失败</span>
          {s.latencyMs > 0 && <span className="muted"> · 延迟 {s.latencyMs}ms</span>}
        </>
      );
    case "none":
      return <span style={{ color: "var(--status-err, #dc2626)" }}>✕ 无响应</span>;
  }
}

function spokeCardBorder(h: Health) {
  switch (h) {
    case "online":
      return "border: 1px solid var(--border-green, #86efac)";
    case "degraded":
      return "border: 1px solid var(--border-yellow, #fde047)";
    case "offline":
      return "border: 1px solid var(--border-red, #fca5a5)";
  }
}

function spokeTypeTag(st: SpokeType) {
  switch (st) {
    case "full":
      return "Full Spoke · 出站轮询开启";
    case "lite":
      return "Lite Spoke · 仅出站轮询";
  }
}

function channelLabel(ch: Channel) {
  return ch;
}

/** Hub 舰队总览 */
export function HubFleetPage() {
  const hubResp = useJsonGet<HubData>("/v1/hub");
  const spokesResp = useJsonGet<{ items: Spoke[] }>("/v1/spokes");

  const hub = hubResp.data || MOCK_HUB;
  const spokes = spokesResp.data?.items?.length ? spokesResp.data.items : MOCK_SPOKES;
  const err = hubResp.err || spokesResp.err;

  return (
    <S2Chrome
      title="Hub 舰队总览"
      lede="中心 Hub 管理各 Spoke 环境；Probe 健康度每 60s 轮询。"
    >
      <BpToolbar>
        <button
          type="button"
          className="btn"
          onClick={() => {
            hubResp.reload();
            spokesResp.reload();
          }}
        >
          刷新舰队
        </button>
        <Link to="/apollo/release" className="btn-nav">
          Release 通道 →
        </Link>
        <Link to="/apollo/spoke" className="btn-nav">
          Spoke 详情 →
        </Link>
      </BpToolbar>

      {err && <p className="error">{err}</p>}

      {/* Summary bar */}
      <div
        className="bp-banner bp-banner-info"
        style={{ display: "flex", flexWrap: "wrap", gap: 24, alignItems: "center" }}
      >
        <div>
          <span className="muted" style={{ fontSize: "0.65rem" }}>
            Hub 区域
          </span>
          <div className="bp-metric-value">{hub.hubRegion}</div>
        </div>
        <div>
          <span className="muted" style={{ fontSize: "0.65rem" }}>
            在线 Spoke
          </span>
          <div style={{ color: "var(--status-ok, #16a34a)", fontWeight: 600 }}>
            {hub.onlineCount} / {hub.totalCount}
          </div>
        </div>
        <div>
          <span className="muted" style={{ fontSize: "0.65rem" }}>
            最近 Probe
          </span>
          <div className="bp-metric-value">{hub.lastProbe}</div>
        </div>
        <div style={{ marginLeft: "auto", alignSelf: "center" }}>
          <Link to="/apollo/release" className="nav-link" style={{ fontSize: "0.75rem" }}>
            Release 通道 →
          </Link>
        </div>
      </div>

      {/* Spoke cards grid */}
      <div
        className="bp-metric-grid"
        style={{ gap: "1rem", marginTop: "1rem" }}
      >
        {spokes.map((s) => (
          <Link
            key={s.id}
            to={`/apollo/spoke?id=${encodeURIComponent(s.id)}`}
            className="card"
            style={{
              ...spokeCardBorder(s.health),
              padding: "1.25rem",
              textDecoration: "none",
              color: "inherit",
              borderRadius: "0.75rem",
              transition: "border-color 0.2s",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: "0.75rem",
              }}
            >
              <span style={{ fontWeight: 500 }}>{s.name}</span>
              <span className={healthBadgeClass(s.health)} style={{ fontSize: "0.625rem" }}>
                {healthLabel(s.health)}
              </span>
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--fg-muted, #6b7280)", lineHeight: 1.6 }}>
              <div>
                Probe {probeText(s)}
              </div>
              <div>
                通道 {channelLabel(s.channel)} · Bundle {s.bundle}
              </div>
              <div>{spokeTypeTag(s.spokeType)}</div>
            </div>
          </Link>
        ))}

        {/* Add new spoke placeholder */}
        <div
          className="card"
          style={{
            border: "1px dashed var(--border-muted, #d1d5db)",
            background: "var(--bg-muted, #f3f4f6)",
            padding: "1.25rem",
            textAlign: "center",
            borderRadius: "0.75rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            minHeight: 130,
          }}
        >
          <span className="muted" style={{ fontSize: "0.875rem" }}>
            + 注册新 Spoke
          </span>
        </div>
      </div>

      {/* Fleet health summary */}
      <section
        className="bp-domain bp-domain-apollo"
        style={{ marginTop: "1rem" }}
      >
        <h2 style={{ fontSize: "0.875rem", margin: "0 0 0.5rem" }}>舰队健康概览</h2>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", fontSize: "0.75rem" }}>
          {(["online", "degraded", "offline"] as Health[]).map((h) => {
            const cnt = spokes.filter((s) => s.health === h).length;
            const pct = spokes.length > 0 ? Math.round((cnt / spokes.length) * 100) : 0;
            return (
              <div
                key={h}
                className={
                  h === "online"
                    ? "bp-metric bp-metric-ok"
                    : h === "degraded"
                      ? "bp-metric bp-metric-warn"
                      : "bp-metric bp-metric-muted"
                }
                style={{ flex: 1, minWidth: 100 }}
              >
                <div className="bp-metric-value">{cnt}</div>
                <div className="bp-metric-label">{healthLabel(h)}</div>
                <div className="bp-metric-hint">{pct}%</div>
              </div>
            );
          })}
        </div>
      </section>

      <BpLinkRow
        links={[
          { to: "/apollo/release", label: "Release 通道" },
          { to: "/apollo/spoke", label: "Spoke 详情" },
          { to: "/apollo/ferry", label: "Ferry 摆渡" },
        ]}
      />
    </S2Chrome>
  );
}
