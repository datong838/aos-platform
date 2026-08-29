import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { S2Chrome, useJsonGet } from "./shared";
import { BpBanner, BpKvList, BpTabs, BpToolbar } from "./blueprintUi";
import type { Spoke } from "./HubFleetPage";

export const TABS = [
  { id: "overview", label: "概览" },
  { id: "plan", label: "部署计划" },
  { id: "plan-diff", label: "计划差异" },
  { id: "config", label: "配置" },
  { id: "maintenance", label: "维护窗口" },
];

/** Spoke 详情：必须由舰队中的精确节点 ID 进入。 */
export function SpokeDetailPage() {
  const [params] = useSearchParams();
  const spokeId = params.get("id")?.trim() || null;
  const detail = useJsonGet<Spoke>(spokeId ? `/v1/apollo/spokes/${encodeURIComponent(spokeId)}` : null);
  const [tab, setTab] = useState("overview");
  const spoke = detail.data?.id ? detail.data : null;
  return (
    <S2Chrome title={spoke?.name || "运行节点详情"} lede="查看当前工作区精确登记的节点状态">
      <BpToolbar>
        <Link to="/apollo" className="btn-nav">← Hub 舰队</Link>
        <button type="button" className="btn" disabled={!spokeId} onClick={detail.reload}>刷新</button>
      </BpToolbar>
      {!spokeId && <BpBanner tone="info">请先从 Hub 舰队选择一个已登记运行节点。</BpBanner>}
      {spokeId && detail.err && <BpBanner tone="warn">节点权威读取失败：{detail.err}</BpBanner>}
      {spoke && (
        <>
          <section className="bp-domain bp-domain-apollo">
            <h2 className="bp-domain-heading">{spoke.name || spoke.id}</h2>
            <BpKvList rows={[
              { key: "节点 ID", value: spoke.id, mono: true },
              { key: "状态", value: spoke.status || "未知" },
              { key: "探活", value: spoke.heartbeatOk ? "已通过" : "未通过" },
              { key: "通道", value: spoke.channelId || spoke.channel || "未登记" },
              { key: "版本", value: spoke.version || "未知", mono: true },
              { key: "形态", value: spoke.kind || spoke.mode || "未知" },
              { key: "运行时", value: spoke.runtime || "未知" },
            ]} />
          </section>
          <BpTabs tabs={TABS} active={tab} onChange={setTab} />
          {tab === "overview" ? (
            <BpBanner tone={spoke.heartbeatOk ? "info" : "warn"}>当前节点状态来自租户隔离的 Apollo 节点目录；页面不推断未返回的延迟、资源或最近同步时间。</BpBanner>
          ) : (
            <section className="bp-domain bp-domain-apollo">
              <h2 className="bp-domain-heading">{TABS.find((item) => item.id === tab)?.label}</h2>
              <p className="muted">当前节点尚无该类独立权威记录；页面不会用客户端常量补齐。</p>
            </section>
          )}
        </>
      )}
    </S2Chrome>
  );
}
