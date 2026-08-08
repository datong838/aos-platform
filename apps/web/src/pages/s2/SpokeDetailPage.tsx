import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { S2Chrome, useJsonGet } from "./shared";
import { BpBanner, BpKvList, BpLinkRow, BpTabs, BpToolbar } from "./blueprintUi";

export type SpokeDetail = {
  id: string;
  name: string;
  region: string;
  spokeType: "full" | "lite";
  health: "online" | "degraded" | "offline";
  channel: "stable" | "beta" | "rc";
  bundle: string;
  version: string;
  runtime: string;
  pollingIntervalMin: number;
  lastSync: string;
  probeStatus: string;
  probeLatencyMs: number;
};

export type PlanEntry = {
  id: string;
  name: string;
  version: string;
  status: "applied" | "pending" | "failed";
};

export type PlanDiffItem = {
  path: string;
  current: string;
  expected: string;
  diffType: "added" | "changed" | "removed";
};

export type ConfigOverride = {
  key: string;
  value: string;
  source: "spoke" | "hub" | "vault";
  description?: string;
};

export type MaintenanceWindow = {
  start: string;
  end: string;
  description: string;
  active: boolean;
};

export type SpokeDetailData = {
  spoke: SpokeDetail;
  plans: PlanEntry[];
  planDiff: PlanDiffItem[];
  config: ConfigOverride[];
  maintenanceWindow: MaintenanceWindow | null;
};

export const MOCK_SPOKE_DETAIL: SpokeDetailData = {
  spoke: {
    id: "spoke-prod-sh",
    name: "上海生产运行节点",
    region: "上海生产区",
    spokeType: "full",
    health: "online",
    channel: "stable",
    bundle: "2.14.1",
    version: "platform-2.14.1",
    runtime: "Full Foundry 运行时",
    pollingIntervalMin: 5,
    lastSync: "2 分钟前",
    probeStatus: "正常",
    probeLatencyMs: 42,
  },
  plans: [
    { id: "bundle-core", name: "Bundle apollo-core", version: "2.14.1", status: "applied" },
    { id: "bundle-fde", name: "FDE 维修派单资产包", version: "1.8.0", status: "pending" },
    { id: "cfg-override", name: "Config Override", version: "2 项覆盖", status: "applied" },
  ],
  planDiff: [
    { path: "bundle/version", current: "2.14.1", expected: "2.14.2-beta.1", diffType: "changed" },
    { path: "config/logLevel", current: "info", expected: "debug", diffType: "changed" },
    { path: "runtime/limits/cpu", current: "2", expected: "4", diffType: "changed" },
    { path: "config/newFeature", current: "—", expected: "enabled", diffType: "added" },
    { path: "config/deprecatedApi", current: "v1/old", expected: "—", diffType: "removed" },
  ],
  config: [
    { key: "log_level", value: "info", source: "spoke", description: "日志级别覆盖" },
    { key: "max_connections", value: "500", source: "hub", description: "最大连接数" },
    { key: "api_secret_ref", value: "vault:spoke-sh/api-secret", source: "vault", description: "API 密钥引用" },
  ],
  maintenanceWindow: {
    start: "2026-07-28 22:00",
    end: "2026-07-29 02:00",
    description: "计划内维护 · 暂停非紧急 Plan 推送",
    active: true,
  },
};

export const TABS = [
  { id: "overview", label: "Overview" },
  { id: "plan", label: "Plan" },
  { id: "plan-diff", label: "Plan Diff" },
  { id: "config", label: "Config" },
  { id: "maintenance", label: "Maintenance Window" },
];

function healthColor(h: SpokeDetail["health"]) {
  switch (h) {
    case "online":
      return "var(--status-ok, #16a34a)";
    case "degraded":
      return "var(--status-warn, #ca8a04)";
    case "offline":
      return "var(--status-err, #dc2626)";
  }
}

export function healthLabel(h: SpokeDetail["health"]) {
  switch (h) {
    case "online":
      return "健康";
    case "degraded":
      return "降级";
    case "offline":
      return "离线";
  }
}

export function planStatusBadge(s: PlanEntry["status"]) {
  switch (s) {
    case "applied":
      return { label: "已应用", cls: "bp-discover-badge bp-discover-badge-ok" };
    case "pending":
      return { label: "待应用", cls: "bp-discover-badge bp-discover-badge-warn" };
    case "failed":
      return { label: "失败", cls: "bp-discover-badge bp-discover-badge-bad" };
  }
}

function diffTypeIcon(t: PlanDiffItem["diffType"]) {
  switch (t) {
    case "added":
      return <span style={{ color: "var(--status-ok, #16a34a)" }}>+</span>;
    case "changed":
      return <span style={{ color: "var(--status-warn, #ca8a04)" }}>~</span>;
    case "removed":
      return <span style={{ color: "var(--status-err, #dc2626)" }}>-</span>;
  }
}

/** Spoke 详情 */
export function SpokeDetailPage() {
  const [searchParams] = useSearchParams();
  const spokeId = searchParams.get("id") || "spoke-prod-sh";
  const [activeTab, setActiveTab] = useState("overview");

  const detailResp = useJsonGet<SpokeDetail>(`/v1/spokes/${encodeURIComponent(spokeId)}`);
  const planResp = useJsonGet<{ items: PlanEntry[] }>(`/v1/spokes/${encodeURIComponent(spokeId)}/plan`);
  const diffResp = useJsonGet<{ items: PlanDiffItem[] }>(`/v1/spokes/${encodeURIComponent(spokeId)}/plan-diff`);
  const configResp = useJsonGet<{ items: ConfigOverride[] }>(`/v1/spokes/${encodeURIComponent(spokeId)}/config`);

  const spoke = detailResp.data?.id ? detailResp.data : MOCK_SPOKE_DETAIL.spoke;
  const plans = planResp.data?.items?.length ? planResp.data.items : MOCK_SPOKE_DETAIL.plans;
  const diffs = diffResp.data?.items?.length ? diffResp.data.items : MOCK_SPOKE_DETAIL.planDiff;
  const config = configResp.data?.items?.length ? configResp.data.items : MOCK_SPOKE_DETAIL.config;
  const mw = MOCK_SPOKE_DETAIL.maintenanceWindow;
  const err = detailResp.err || planResp.err || diffResp.err || configResp.err;

  // Simulate Maintenance Window data (no separate API yet)
  const maintenanceWindow: MaintenanceWindow | null = mw;

  return (
    <S2Chrome title={spoke.name} lede={`${spoke.region} · Entity 同步目标 · 通道 ${spoke.channel}`}>
      <BpToolbar>
        <button
          type="button"
          className="btn"
          onClick={() => {
            detailResp.reload();
            planResp.reload();
            diffResp.reload();
            configResp.reload();
          }}
        >
          刷新
        </button>
        <Link to="/apollo" className="btn-nav">
          ← Hub 舰队
        </Link>
        <Link to="/apollo/config" className="btn-nav">
          配置覆盖 →
        </Link>
      </BpToolbar>

      {err && <p className="error">{err}</p>}

      {/* Spoke info card */}
      <div
        className="bp-domain bp-domain-apollo"
        style={{ borderColor: healthColor(spoke.health) }}
      >
        <div style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "center" }}>
          <div>
            <span
              style={{
                display: "inline-block",
                width: 10,
                height: 10,
                borderRadius: "50%",
                background: healthColor(spoke.health),
                marginRight: 6,
              }}
            />
            <span style={{ fontWeight: 500 }}>{spoke.name}</span>
          </div>
          <span
            className="bp-discover-badge bp-discover-badge-ok"
            style={{ fontSize: "0.625rem" }}
          >
            {healthLabel(spoke.health)}
          </span>
          <span className="muted" style={{ fontSize: "0.75rem" }}>
            {spoke.region} · {spoke.spokeType.toUpperCase()} · {spoke.channel}
          </span>
        </div>

        <BpKvList
          rows={[
            { key: "版本", desc: "SemVer", value: spoke.version, mono: true },
            { key: "Bundle", value: spoke.bundle, mono: true },
            { key: "Runtime", value: spoke.runtime, mono: true },
            { key: "Probe 延迟", value: `${spoke.probeLatencyMs}ms` },
            { key: "轮询间隔", value: `${spoke.pollingIntervalMin} 分钟` },
            { key: "最近同步", value: spoke.lastSync },
          ]}
        />
      </div>

      {/* Outbound polling callout */}
      <BpBanner tone="info">
        <div style={{ fontWeight: 500, marginBottom: 4 }}>
          ↗ 出站轮询（Outbound Polling）
        </div>
        <p style={{ fontSize: "0.75rem", margin: 0 }}>
          Spoke 主动拉取 Hub 变更队列；气隙环境无入站时仅此路径可用。轮询间隔{" "}
          {spoke.pollingIntervalMin} 分钟 · 最近同步 {spoke.lastSync}。
        </p>
      </BpBanner>

      {/* Spoke type toggle */}
      <div className="bp-domain bp-domain-apollo">
        <h2 className="bp-domain-heading">Spoke 形态</h2>
        <div style={{ display: "flex", gap: 8, padding: 4, borderRadius: 2, background: "var(--bg-muted, #f0f2f5)", width: "fit-content", border: "1px solid var(--border-muted, #d1d5db)" }}>
          <button
            type="button"
            className={spoke.spokeType === "full" ? "btn" : "btn-muted"}
            style={spoke.spokeType === "full" ? {
              background: "var(--bg-green, #dcfce7)",
              color: "var(--status-ok, #16a34a)",
              border: "1px solid var(--border-green, #86efac)",
              fontSize: "0.75rem",
              fontWeight: 500,
            } : { fontSize: "0.75rem" }}
          >
            Full Spoke
          </button>
          <button
            type="button"
            className={spoke.spokeType === "lite" ? "btn" : "btn-muted"}
            style={spoke.spokeType === "lite" ? {
              background: "var(--bg-green, #dcfce7)",
              color: "var(--status-ok, #16a34a)",
              border: "1px solid var(--border-green, #86efac)",
              fontSize: "0.75rem",
              fontWeight: 500,
            } : { fontSize: "0.75rem" }}
          >
            Lite Spoke
          </button>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: "1rem",
            marginTop: "1rem",
          }}
        >
          <div
            className="card"
            style={{
              background: spoke.spokeType === "full" ? "var(--bg-green, #f0fdf4)" : undefined,
              border: spoke.spokeType === "full" ? "1px solid var(--border-green, #86efac)" : undefined,
              padding: "0.75rem",
              fontSize: "0.75rem",
            }}
          >
            <div
              style={{
                fontWeight: 500,
                color: "var(--status-ok, #16a34a)",
                marginBottom: 4,
              }}
            >
              Full{spoke.spokeType === "full" ? " · 当前" : ""}
            </div>
            <ul className="muted" style={{ paddingLeft: "1rem", margin: 0, lineHeight: 1.6 }}>
              <li>完整 Foundry 运行时</li>
              <li>双向同步 + 出站轮询</li>
              <li>Ontology / Pipeline 本地执行</li>
            </ul>
          </div>
          <div
            className="card"
            style={{
              opacity: spoke.spokeType !== "lite" ? 0.7 : 1,
              padding: "0.75rem",
              fontSize: "0.75rem",
            }}
          >
            <div
              style={{
                fontWeight: 500,
                color: "var(--fg-muted, #6b7280)",
                marginBottom: 4,
              }}
            >
              Lite{spoke.spokeType === "lite" ? " · 当前" : ""}
            </div>
            <ul className="muted" style={{ paddingLeft: "1rem", margin: 0, lineHeight: 1.6 }}>
              <li>轻量代理 · 仅出站轮询</li>
              <li>无本地计算平面</li>
              <li>适合边缘 / 高合规区</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Tab navigation */}
      <BpTabs tabs={TABS} active={activeTab} onChange={setActiveTab} />

      {/* Tab content */}
      <div style={{ marginTop: "1rem" }}>
        {activeTab === "overview" && (
          <div className="space-y-1">
            <div className="card" style={{ padding: "1rem" }}>
              <h2 className="bp-ws-section-title">Probe 详情</h2>
              <BpKvList
                rows={[
                  { key: "状态", value: spoke.probeStatus === "正常" ? "● 正常" : "✕ 异常" },
                  { key: "延迟", value: `${spoke.probeLatencyMs}ms` },
                  { key: "最近同步", value: spoke.lastSync },
                  { key: "轮询间隔", value: `${spoke.pollingIntervalMin} 分钟` },
                ]}
              />
            </div>
            <div className="card" style={{ padding: "1rem", marginTop: "1rem" }}>
              <h2 className="bp-ws-section-title">资源使用</h2>
              <BpKvList
                rows={[
                  { key: "Runtime", value: spoke.runtime, mono: true },
                  { key: "版本", value: spoke.version, mono: true },
                  { key: "Bundle", value: spoke.bundle, mono: true },
                  { key: "通道", value: spoke.channel, mono: true },
                ]}
              />
            </div>
          </div>
        )}

        {activeTab === "plan" && (
          <div className="card" style={{ padding: "1rem" }}>
            <h2 className="bp-ws-section-title">部署计划</h2>
            <div className="bp-kv-list">
              {plans.map((p) => {
                const badge = planStatusBadge(p.status);
                return (
                  <div key={p.id} className="bp-kv-row">
                    <div>
                      <div className="bp-kv-key">{p.name}</div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span className={badge.cls} style={{ fontSize: "0.625rem" }}>
                        {badge.label}
                      </span>
                      <span className="bp-kv-value">{p.version}</span>
                    </div>
                  </div>
                );
              })}
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: "0.75rem" }}>
              <button
                type="button"
                className="btn"
                onClick={() => alert("Plan Diff 预览")}
              >
                预览 Plan Diff
              </button>
              <Link to="/apollo/config" className="btn-nav">
                配置覆盖 →
              </Link>
            </div>
          </div>
        )}

        {activeTab === "plan-diff" && (
          <div className="card" style={{ padding: "1rem" }}>
            <h2 className="bp-ws-section-title">当前 vs 期望对比</h2>
            <div className="bp-kv-list">
              {diffs.map((d, i) => (
                <div key={i} className="bp-kv-row">
                  <div>
                    <div className="bp-kv-key">
                      {diffTypeIcon(d.diffType)} {d.path}
                    </div>
                    <div className="bp-kv-desc">
                      当前: {d.current} → 期望: {d.expected}
                    </div>
                  </div>
                  <span className="bp-kv-value" style={{ fontSize: "0.625rem" }}>
                    {d.diffType === "added" ? "新增" : d.diffType === "changed" ? "变更" : "移除"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === "config" && (
          <div className="card" style={{ padding: "1rem" }}>
            <h2 className="bp-ws-section-title">配置覆盖项</h2>
            <div className="bp-kv-list">
              {config.map((c) => (
                <div key={c.key} className="bp-kv-row">
                  <div>
                    <div className="bp-kv-key">
                      <code>{c.key}</code>
                    </div>
                    <div className="bp-kv-desc">
                      {c.description || c.source}
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span
                      className="bp-discover-badge"
                      style={{
                        fontSize: "0.625rem",
                        background:
                          c.source === "vault"
                            ? "var(--bg-violet, #ede9fe)"
                            : c.source === "spoke"
                              ? "var(--bg-green, #dcfce7)"
                              : "var(--bg-amber, #fef3c7)",
                        border: "1px solid var(--border-muted, #d1d5db)",
                        color:
                          c.source === "vault"
                            ? "var(--fg-violet, #7c3aed)"
                            : c.source === "spoke"
                              ? "var(--status-ok, #16a34a)"
                              : "var(--status-warn, #ca8a04)",
                      }}
                    >
                      {c.source}
                    </span>
                    <span className="bp-kv-value mono">{c.value}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === "maintenance" && (
          <div className="card" style={{ padding: "1rem" }}>
            <h2 className="bp-ws-section-title">维护窗口</h2>
            {maintenanceWindow ? (
              <>
                <BpBanner tone={maintenanceWindow.active ? "warn" : "info"}>
                  <div style={{ fontWeight: 500, marginBottom: 4 }}>
                    {maintenanceWindow.active ? "计划内维护" : "无活跃维护窗口"}
                  </div>
                  <p style={{ fontSize: "0.75rem", margin: 0 }}>
                    {maintenanceWindow.description}
                  </p>
                </BpBanner>
                <BpKvList
                  rows={[
                    { key: "开始时间", value: maintenanceWindow.start },
                    { key: "结束时间", value: maintenanceWindow.end },
                    {
                      key: "状态",
                      value: maintenanceWindow.active ? "进行中" : "已结束",
                    },
                  ]}
                />
              </>
            ) : (
              <p className="muted">暂无维护窗口</p>
            )}
          </div>
        )}
      </div>

      <BpLinkRow
        links={[
          { to: "/apollo", label: "← Hub 舰队" },
          { to: "/apollo/release", label: "Release 通道 →" },
        ]}
      />
    </S2Chrome>
  );
}
