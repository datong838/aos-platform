import { Link } from "react-router-dom";
import { S2Chrome, useJsonGet } from "./shared";
import { BpBanner, BpLinkRow, BpToolbar } from "./blueprintUi";

export type Spoke = {
  id: string; name: string; status: string; heartbeatOk: boolean;
  channelId?: string; channel?: string; kind?: string; mode?: string;
  version?: string; runtime?: string;
};

export type FleetPayload = {
  hub?: { id?: string; status?: string; mode?: string };
  spokes?: Spoke[];
  channels?: Array<{ id: string; name?: string; status?: string }>;
};

export function spokeHealthLabel(spoke: Spoke) {
  if (!spoke.heartbeatOk) return "未通过探活";
  return spoke.status === "online" ? "在线" : "状态待核验";
}

/** Hub 舰队总览：只展示当前租户 Apollo catalog，不注入运行节点。 */
export function HubFleetPage() {
  const fleet = useJsonGet<FleetPayload>("/v1/apollo/fleet");
  const spokes = Array.isArray(fleet.data?.spokes) ? fleet.data.spokes : [];
  const channels = Array.isArray(fleet.data?.channels) ? fleet.data.channels : [];
  const online = spokes.filter((item) => item.status === "online" && item.heartbeatOk).length;
  return (
    <S2Chrome title="运行节点总览" lede="查看当前工作区已登记的管理中心、运行节点与发布通道">
      <BpToolbar>
        <button type="button" className="btn" onClick={fleet.reload}>刷新舰队</button>
        <Link to="/apollo/release" className="btn-nav">发布通道 →</Link>
        <Link to="/apollo/ferry" className="btn-nav">离线摆渡 →</Link>
      </BpToolbar>
      {fleet.err && <BpBanner tone="warn">舰队权威读取失败：{fleet.err}</BpBanner>}
      <div className="bp-banner bp-banner-info" style={{ display: "flex", gap: 32, flexWrap: "wrap" }}>
        <div><span className="muted">管理中心</span><div className="bp-metric-value">{fleet.data?.hub?.id || "未登记"}</div></div>
        <div><span className="muted">管理中心状态</span><div className="bp-metric-value">{fleet.data?.hub?.status || "未知"}</div></div>
        <div><span className="muted">在线节点</span><div className="bp-metric-value">{online} / {spokes.length}</div></div>
        <div><span className="muted">已登记通道</span><div className="bp-metric-value">{channels.length}</div></div>
      </div>
      {spokes.length === 0 ? (
        <section className="bp-domain bp-domain-apollo" style={{ marginTop: "1rem" }}>
          <h2 className="bp-domain-heading">当前工作区尚未登记运行节点</h2>
          <p className="muted">这里不会用演示节点补齐。完成节点注册和探活后，舰队卡片会显示权威状态。</p>
        </section>
      ) : (
        <div className="bp-metric-grid" style={{ gap: "1rem", marginTop: "1rem" }}>
          {spokes.map((spoke) => (
            <Link key={spoke.id} to={`/apollo/spoke?id=${encodeURIComponent(spoke.id)}`} className="card" style={{ padding: "1.25rem", textDecoration: "none", color: "inherit" }}>
              <strong>{spoke.name || spoke.id}</strong>
              <div className="muted">{spokeHealthLabel(spoke)}</div>
              <div className="muted">通道 {spoke.channelId || spoke.channel || "未登记"} · 版本 {spoke.version || "未知"}</div>
              <div className="muted">形态 {spoke.kind || spoke.mode || "未知"} · 运行时 {spoke.runtime || "未知"}</div>
            </Link>
          ))}
        </div>
      )}
      <BpLinkRow links={[{ to: "/apollo/release", label: "发布通道" }, { to: "/apollo/ferry", label: "离线摆渡" }]} />
    </S2Chrome>
  );
}
