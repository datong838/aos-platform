import { useState } from "react";
import { S2Chrome, useJsonGet } from "./shared";
import {
  BpToolbar,
  BpTabs,
  BpTable,
  BpMetricGrid,
  BpBanner,
} from "./blueprintUi";

/* ──────────────── Types ──────────────── */

export interface AssetBundle {
  id: string;
  name: string;
  version: string;
  channel: "stable" | "beta" | "rc";
  contentType: string;
  status: "published" | "draft" | "deprecated";
  components: { name: string; version: string; type: string }[];
  changelog: string;
}

/* ──────────────── MOCK fallback ──────────────── */

export const MOCK_ASSET_BUNDLES: AssetBundle[] = [
  {
    id: "asset-apollo-core-2.14.1",
    name: "apollo-core",
    version: "2.14.1",
    channel: "stable",
    contentType: "platform-runtime",
    status: "published",
    components: [
      { name: "platform-core", version: "2.14.1", type: "runtime" },
      { name: "ontology-engine", version: "2.14.1", type: "runtime" },
      { name: "pipeline-runner", version: "2.14.0", type: "runtime" },
    ],
    changelog: "修复本体索引性能问题；升级 pipeline-runner 至 2.14.0。",
  },
  {
    id: "asset-fde-repair-1.8.0-rc.2",
    name: "fde-维修派单",
    version: "1.8.0-rc.2",
    channel: "beta",
    contentType: "fde-module",
    status: "published",
    components: [
      { name: "fde-repair-workshop", version: "1.8.0-rc.2", type: "module" },
      { name: "fde-repair-rules", version: "1.8.0-rc.2", type: "ruleset" },
      { name: "dispatch-widget", version: "1.5.0", type: "widget" },
    ],
    changelog: "新增智能派单规则引擎；支持多工种协同派单。",
  },
  {
    id: "asset-fde-inventory-0.9.4",
    name: "fde-库存预警",
    version: "0.9.4",
    channel: "rc",
    contentType: "fde-module",
    status: "published",
    components: [
      { name: "inventory-alert-engine", version: "0.9.4", type: "engine" },
      { name: "stock-threshold-rules", version: "0.9.4", type: "ruleset" },
    ],
    changelog: "RC 候选版本：增加多仓库库存联动预警，阈值规则可配置化。",
  },
  {
    id: "asset-config-overrides-sh-2.14.1",
    name: "config-overrides-sh",
    version: "2.14.1+local.3",
    channel: "stable",
    contentType: "config-pack",
    status: "draft",
    components: [
      { name: "spoke-prod-sh-overrides", version: "2.14.1", type: "config" },
      { name: "regional-env-vars", version: "local.3", type: "config" },
    ],
    changelog: "上海区域配置覆盖：增加 db.connection.poolSize 调优；新增 integration.apiKey。",
  },
];

/* ──────────────── Page ──────────────── */

export const CHANNEL_TABS = [
  { id: "all", label: "全部" },
  { id: "stable", label: "Stable" },
  { id: "beta", label: "Beta" },
  { id: "rc", label: "RC" },
];

export function AssetBundlesPage() {
  const resp = useJsonGet<{ items: AssetBundle[] } | AssetBundle[]>("/v1/assets");
  const raw = resp.data;
  const bundles =
    raw && Array.isArray(raw) && raw.length > 0 ? raw : MOCK_ASSET_BUNDLES;

  const [activeTab, setActiveTab] = useState("all");
  const [expandedId, setExpandedId] = useState<string>("");

  const filtered =
    activeTab === "all"
      ? bundles
      : bundles.filter((b) => b.channel === activeTab);

  const counts = {
    total: bundles.length,
    stable: bundles.filter((b) => b.channel === "stable").length,
    beta: bundles.filter((b) => b.channel === "beta").length,
    rc: bundles.filter((b) => b.channel === "rc").length,
    published: bundles.filter((b) => b.status === "published").length,
  };

  function toggleRow(id: string) {
    setExpandedId(expandedId === id ? "" : id);
  }

  return (
    <S2Chrome title="FDE 资产包" lede="管理 FDE 模块、平台运行时和配置包的发布通道与版本">
      {/* Top metrics */}
      <BpMetricGrid
        items={[
          { label: "资产包总数", value: String(counts.total), tone: "ok" },
          { label: "Stable", value: String(counts.stable), tone: "ok" },
          { label: "Beta", value: String(counts.beta), tone: "warn" },
          { label: "RC", value: String(counts.rc), tone: "muted" },
          { label: "已发布", value: String(counts.published), tone: "ok" },
        ]}
      />

      {/* Channel filter */}
      <div style={{ marginTop: "1rem" }}>
        <BpToolbar>
          <BpTabs tabs={CHANNEL_TABS} active={activeTab} onChange={setActiveTab} />
        </BpToolbar>
      </div>

      {/* Table */}
      <BpTable
        columns={["名称", "版本", "通道", "内容类型", "状态", ""]}
        rows={filtered.flatMap((b) => {
          const isExpanded = expandedId === b.id;
          const mainRow = [
            <span key="name" style={{ fontWeight: 600 }}>
              {b.name}
            </span>,
            <span key="ver" className="mono">
              {b.version}
            </span>,
            <span
              key="ch"
              className={
                b.channel === "stable"
                  ? "status-ok"
                  : b.channel === "beta"
                    ? "status-warn"
                    : "muted"
              }
            >
              {b.channel}
            </span>,
            <span key="ct" className="muted">
              {b.contentType}
            </span>,
            <span
              key="st"
              className={
                b.status === "published"
                  ? "status-ok"
                  : b.status === "deprecated"
                    ? "status-warn"
                    : "muted"
              }
            >
              {b.status === "published"
                ? "已发布"
                : b.status === "deprecated"
                  ? "已废弃"
                  : "草稿"}
            </span>,
            <button
              key="btn"
              type="button"
              className="btn-link"
              onClick={() => toggleRow(b.id)}
              style={{
                border: "none",
                background: "none",
                cursor: "pointer",
                color: "#3b82f6",
                fontSize: "0.75rem",
              }}
            >
              {isExpanded ? "收起 ▲" : "展开 ▼"}
            </button>,
          ];

          if (isExpanded) {
            return [
              mainRow,
              [
                <td key="detail" colSpan={6} style={{ padding: "0.75rem 1rem", background: "var(--bg-hover, #f8f9fa)" }}>
                  <div style={{ display: "flex", gap: "2rem", flexWrap: "wrap" }}>
                    <div style={{ flex: "1 1 300px" }}>
                      <h4 style={{ marginBottom: "0.4rem" }}>组件清单</h4>
                      <BpTable
                        columns={["组件", "版本", "类型"]}
                        rows={b.components.map((c) => [
                          <span key="cn">{c.name}</span>,
                          <span key="cv" className="mono">
                            {c.version}
                          </span>,
                          <span key="ct" className="muted">
                            {c.type}
                          </span>,
                        ])}
                      />
                    </div>
                    <div style={{ flex: "1 1 250px" }}>
                      <h4 style={{ marginBottom: "0.4rem" }}>变更日志</h4>
                      <div
                        className="card"
                        style={{
                          padding: "0.75rem",
                          fontSize: "0.8rem",
                          whiteSpace: "pre-wrap",
                        }}
                      >
                        {b.changelog}
                      </div>
                    </div>
                  </div>
                </td>,
                <td key="_" style={{ display: "none" }} />,
                <td key="2_" style={{ display: "none" }} />,
                <td key="3_" style={{ display: "none" }} />,
                <td key="4_" style={{ display: "none" }} />,
                <td key="5_" style={{ display: "none" }} />,
              ],
            ];
          }
          return [mainRow];
        })}
      />

      <div style={{ marginTop: "0.75rem" }}>
        <BpBanner tone="info">
          Stable 通道资产包已通过完整验收流程，可直接 Ferry 到生产 Spoke。Beta / RC
          通道资产包需经变更审批后方可部署。
        </BpBanner>
      </div>
    </S2Chrome>
  );
}
