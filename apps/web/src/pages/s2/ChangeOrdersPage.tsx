import { useState } from "react";
import { S2Chrome, useJsonGet, apiPost } from "./shared";
import {
  BpToolbar,
  BpTabs,
  BpTable,
  BpSplit,
  BpKvList,
  BpStagePipeline,
  BpMetricGrid,
  BpBanner,
} from "./blueprintUi";

/* ──────────────── Types ──────────────── */

interface ApprovalStep {
  step: string;
  title: string;
  reviewer: string;
  status: "done" | "pending" | "rejected";
  decidedAt?: string;
}

interface ChangeOrder {
  id: string;
  type: string;
  status: "pending" | "approved" | "rejected";
  applicant: string;
  appliedAt: string;
  description: string;
  targetSpoke: string;
  bundleVersion: string;
  plannedWindow: string;
  impactScope: string;
  approvals: ApprovalStep[];
}

/* ──────────────── MOCK fallback ──────────────── */

const MOCK_CHANGE_ORDERS: ChangeOrder[] = [
  {
    id: "CHG-2026-0412",
    type: "资产包升级",
    status: "pending",
    applicant: "张运维",
    appliedAt: "2026-07-25 09:30",
    description:
      "将 apollo-core 从 2.14.0 升级至 2.14.1，修复本体索引性能问题。影响 platform-core、ontology-engine 两个运行时组件。",
    targetSpoke: "spoke-prod-sh",
    bundleVersion: "apollo-core-2.14.1",
    plannedWindow: "2026-07-28 02:00 ~ 04:00",
    impactScope: "生产环境短暂中断约 5 分钟，本体查询在升级期间不可用。",
    approvals: [
      {
        step: "①",
        title: "提交",
        reviewer: "张运维",
        status: "done",
        decidedAt: "2026-07-25 09:30",
      },
      {
        step: "②",
        title: "安全评审",
        reviewer: "李安全",
        status: "done",
        decidedAt: "2026-07-25 14:00",
      },
      {
        step: "③",
        title: "变更委员会",
        reviewer: "王总监",
        status: "pending",
      },
    ],
  },
  {
    id: "CHG-2026-0408",
    type: "配置变更",
    status: "approved",
    applicant: "陈SRE",
    appliedAt: "2026-07-22 11:00",
    description:
      "调整 spoke-prod-bj 的 db.connection.poolSize 从 20 → 50，应对高峰期连接池耗尽问题。",
    targetSpoke: "spoke-prod-bj",
    bundleVersion: "config-overrides-bj-1.2.0",
    plannedWindow: "2026-07-24 01:00 ~ 01:30",
    impactScope: "数据库连接池热加载，无用户感知中断。",
    approvals: [
      {
        step: "①",
        title: "提交",
        reviewer: "陈SRE",
        status: "done",
        decidedAt: "2026-07-22 11:00",
      },
      {
        step: "②",
        title: "安全评审",
        reviewer: "李安全",
        status: "done",
        decidedAt: "2026-07-22 15:00",
      },
      {
        step: "③",
        title: "变更委员会",
        reviewer: "王总监",
        status: "done",
        decidedAt: "2026-07-23 10:00",
      },
    ],
  },
  {
    id: "CHG-2026-0395",
    type: "新模块部署",
    status: "rejected",
    applicant: "刘PM",
    appliedAt: "2026-07-20 16:00",
    description:
      "部署 fde-库存预警 0.9.4 RC 版本到 spoke-staging-gz，进行多仓库联动预警预生产验证。",
    targetSpoke: "spoke-staging-gz",
    bundleVersion: "fde-库存预警-0.9.4",
    plannedWindow: "2026-07-23 03:00 ~ 05:00",
    impactScope: "仅 staging 环境，不影响生产。",
    approvals: [
      {
        step: "①",
        title: "提交",
        reviewer: "刘PM",
        status: "done",
        decidedAt: "2026-07-20 16:00",
      },
      {
        step: "②",
        title: "安全评审",
        reviewer: "李安全",
        status: "rejected",
        decidedAt: "2026-07-21 09:00",
      },
      {
        step: "③",
        title: "变更委员会",
        reviewer: "—",
        status: "pending",
      },
    ],
  },
];

/* ──────────────── Page ──────────────── */

const STATUS_TABS = [
  { id: "all", label: "全部" },
  { id: "pending", label: "待审批" },
  { id: "approved", label: "已通过" },
  { id: "rejected", label: "已驳回" },
];

export function ChangeOrdersPage() {
  const resp = useJsonGet<{ items: ChangeOrder[] } | ChangeOrder[]>("/v1/changes");
  const raw = resp.data;
  const orders =
    raw && Array.isArray(raw) && raw.length > 0 ? raw : MOCK_CHANGE_ORDERS;

  const [activeTab, setActiveTab] = useState("all");
  const [selectedId, setSelectedId] = useState<string>("");
  const [actionMsg, setActionMsg] = useState<string>("");

  const filtered =
    activeTab === "all" ? orders : orders.filter((o) => o.status === activeTab);

  const selected =
    orders.find((o) => o.id === selectedId) || filtered[0] || null;

  const counts = {
    total: orders.length,
    pending: orders.filter((o) => o.status === "pending").length,
    approved: orders.filter((o) => o.status === "approved").length,
    rejected: orders.filter((o) => o.status === "rejected").length,
  };

  async function approve(id: string) {
    setActionMsg("");
    try {
      await apiPost(`/v1/changes/${id}/approve`, {});
      setActionMsg(`变更单 ${id} 已批准`);
    } catch {
      setActionMsg(`批准失败`);
    }
  }

  async function reject(id: string) {
    setActionMsg("");
    try {
      await apiPost(`/v1/changes/${id}/reject`, {});
      setActionMsg(`变更单 ${id} 已驳回`);
    } catch {
      setActionMsg(`驳回失败`);
    }
  }

  return (
    <S2Chrome title="变更审批" lede="管理运维变更单的全生命周期审批流程">
      {/* Metrics */}
      <BpMetricGrid
        items={[
          { label: "变更单总数", value: String(counts.total), tone: "ok" },
          { label: "待审批", value: String(counts.pending), tone: "warn" },
          { label: "已通过", value: String(counts.approved), tone: "ok" },
          { label: "已驳回", value: String(counts.rejected), tone: "bad" },
        ]}
      />

      {/* Status filter */}
      <div style={{ marginTop: "1rem" }}>
        <BpToolbar>
          <BpTabs
            tabs={STATUS_TABS}
            active={activeTab}
            onChange={(id) => {
              setActiveTab(id);
              setSelectedId("");
              setActionMsg("");
            }}
          />
        </BpToolbar>
      </div>

      <BpSplit
        left={
          <div>
            <BpTable
              columns={["编号", "类型", "状态", "申请人", "申请时间"]}
              rows={filtered.map((o) => {
                const isSel = (selected?.id || "") === o.id;
                return [
                  <button
                    key="id"
                    type="button"
                    onClick={() => {
                      setSelectedId(o.id);
                      setActionMsg("");
                    }}
                    style={{
                      border: "none",
                      background: "none",
                      cursor: "pointer",
                      fontWeight: isSel ? 700 : 400,
                      color: "#3b82f6",
                    }}
                  >
                    {o.id}
                  </button>,
                  <span key="type">{o.type}</span>,
                  <span
                    key="st"
                    className={
                      o.status === "approved"
                        ? "status-ok"
                        : o.status === "rejected"
                          ? "status-warn"
                          : "status-pending"
                    }
                  >
                    {o.status === "approved"
                      ? "已通过"
                      : o.status === "rejected"
                        ? "已驳回"
                        : "待审批"}
                  </span>,
                  <span key="app">{o.applicant}</span>,
                  <span key="at" className="mono muted" style={{ fontSize: "0.75rem" }}>
                    {o.appliedAt}
                  </span>,
                ];
              })}
            />
          </div>
        }
        right={
          selected ? (
            <div>
              <h3 style={{ marginBottom: "0.5rem" }}>
                {selected.id} — {selected.type}
              </h3>
              <BpKvList
                rows={[
                  { key: "变更描述", value: selected.description },
                  { key: "目标 Spoke", value: selected.targetSpoke, mono: true },
                  {
                    key: "Bundle 版本",
                    value: selected.bundleVersion,
                    mono: true,
                  },
                  { key: "计划窗口", value: selected.plannedWindow, mono: true },
                  { key: "影响范围", value: selected.impactScope },
                  { key: "申请人", value: selected.applicant },
                ]}
              />

              <h4 style={{ marginTop: "1rem", marginBottom: "0.5rem" }}>审批流</h4>
              <BpStagePipeline
                stages={selected.approvals.map((a) => ({
                  step: a.step,
                  title: a.title,
                  subtitle: `审核人: ${a.reviewer}${a.decidedAt ? ` · ${a.decidedAt}` : ""}`,
                  status:
                    a.status === "done"
                      ? "已通过"
                      : a.status === "rejected"
                        ? "已驳回"
                        : "待审核",
                  tone:
                    a.status === "done"
                      ? ("done" as const)
                      : a.status === "rejected"
                        ? ("active" as const)
                        : ("wait" as const),
                }))}
              />

              {actionMsg && (
                <div style={{ marginTop: "0.75rem" }}>
                  <BpBanner tone={actionMsg.includes("失败") ? "warn" : "info"}>
                    {actionMsg}
                  </BpBanner>
                </div>
              )}

              {selected.status === "pending" && (
                <div
                  style={{
                    marginTop: "1rem",
                    display: "flex",
                    gap: "0.75rem",
                  }}
                >
                  <button
                    type="button"
                    onClick={() => approve(selected.id)}
                    style={{
                      padding: "0.5rem 1.5rem",
                      borderRadius: 4,
                      border: "none",
                      background: "#22c55e",
                      color: "#fff",
                      cursor: "pointer",
                      fontWeight: 600,
                    }}
                  >
                    批准
                  </button>
                  <button
                    type="button"
                    onClick={() => reject(selected.id)}
                    style={{
                      padding: "0.5rem 1.5rem",
                      borderRadius: 4,
                      border: "none",
                      background: "#ef4444",
                      color: "#fff",
                      cursor: "pointer",
                      fontWeight: 600,
                    }}
                  >
                    驳回
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="muted">请选择左侧的变更单</div>
          )
        }
      />
    </S2Chrome>
  );
}
