import { useEffect, useMemo, useState } from "react";
import { PageChrome } from "../../components/PageChrome";
import { apiGet } from "../../api/client";

/* ============================================================================
 * 类型定义（导出用于测试）
 * ========================================================================== */

export type Severity = "critical" | "warning" | "info";
export type AlertStatus = "open" | "processing" | "resolved";

export interface RiskAlert {
  id: string;
  time: string;
  type: string;
  severity: Severity;
  source: string;
  status: AlertStatus;
  title: string;
  description?: string;
  assignee?: string;
  detail?: {
    trigger: string;
    threshold?: string;
    actual?: string;
    affectedObjects?: number;
    action?: string;
  };
}

/* ============================================================================
 * 常量（导出用于测试）
 * ========================================================================== */

export const SEVERITY_META: Record<Severity, { label: string; color: string; bg: string; icon: string }> = {
  critical: { label: "严重", color: "var(--aos-red)", bg: "var(--aos-red-bg)", icon: "🔴" },
  warning: { label: "警告", color: "var(--aos-amber-600)", bg: "var(--aos-amber-bg)", icon: "🟡" },
  info: { label: "提示", color: "var(--aos-blue-600)", bg: "var(--aos-accent-light)", icon: "🔵" },
};

export const STATUS_META: Record<AlertStatus, { label: string; color: string; bg: string }> = {
  open: { label: "待处理", color: "var(--aos-red)", bg: "var(--aos-red-bg)" },
  processing: { label: "处理中", color: "var(--aos-amber-600)", bg: "var(--aos-amber-bg)" },
  resolved: { label: "已解决", color: "var(--aos-green-600)", bg: "var(--aos-green-bg)" },
};

export const SEVERITY_FILTERS: { id: Severity | "all"; label: string }[] = [
  { id: "all", label: "全部" },
  { id: "critical", label: "严重" },
  { id: "warning", label: "警告" },
  { id: "info", label: "提示" },
];

export const MOCK_ALERTS: RiskAlert[] = [
  {
    id: "alert-001",
    time: new Date(Date.now() - 30 * 60_000).toISOString(),
    type: "交易异常",
    severity: "critical",
    source: "风控引擎",
    status: "open",
    title: "大额异常交易告警",
    description: "检测到用户 user_58291 在 5 分钟内发起 12 笔交易，总额 ¥850,000，超出日常均值 15 倍。",
    assignee: "—",
    detail: {
      trigger: "单用户 5 分钟交易频次 > 10",
      threshold: "频次 ≤ 10 笔 / 5min",
      actual: "12 笔 / 5min",
      affectedObjects: 12,
      action: "自动冻结账户 · 发送人工审核通知",
    },
  },
  {
    id: "alert-002",
    time: new Date(Date.now() - 2 * 3600_000).toISOString(),
    type: "登录异常",
    severity: "critical",
    source: "身份认证",
    status: "processing",
    title: "异地登录+新设备组合",
    description: "用户 user_33441 从 IP 185.220.x.x（境外）使用新设备登录，同时触发异地和新设备风控规则。",
    assignee: "张三",
    detail: {
      trigger: "异地登录 AND 新设备",
      threshold: "信任设备 OR 同城 IP",
      actual: "境外 IP + 未注册设备指纹",
      affectedObjects: 1,
      action: "要求二次验证 · 通知用户确认",
    },
  },
  {
    id: "alert-003",
    time: new Date(Date.now() - 4 * 3600_000).toISOString(),
    type: "库存预警",
    severity: "warning",
    source: "库存系统",
    status: "open",
    title: "热销商品库存低于安全线",
    description: "商品 SKU-9382（无线耳机）当前库存 23 件，低于安全库存线 50 件。近 7 天日均销量 18 件。",
    assignee: "—",
    detail: {
      trigger: "库存 < 安全库存线",
      threshold: "库存 ≥ 50 件",
      actual: "23 件",
      affectedObjects: 1,
      action: "建议补货 200 件",
    },
  },
  {
    id: "alert-004",
    time: new Date(Date.now() - 6 * 3600_000).toISOString(),
    type: "系统性能",
    severity: "warning",
    source: "监控平台",
    status: "processing",
    title: "API 响应延迟超阈值",
    description: "API /v1/orders/search P95 延迟达 2.3s，超过阈值 1s。持续 15 分钟。",
    assignee: "李四",
    detail: {
      trigger: "P95 > 1s 持续 > 10min",
      threshold: "P95 ≤ 1s",
      actual: "2.3s",
      affectedObjects: 0,
      action: "已扩容 2 个 Pod · 正在观察",
    },
  },
  {
    id: "alert-005",
    time: new Date(Date.now() - 12 * 3600_000).toISOString(),
    type: "数据质量",
    severity: "info",
    source: "数据管道",
    status: "resolved",
    title: "数据同步延迟提醒",
    description: "Customer 表同步延迟 35 分钟，已在 10:25 恢复正常。建议检查源系统 CDC 任务。",
    assignee: "王五",
    detail: {
      trigger: "同步延迟 > 30min",
      threshold: "延迟 ≤ 10min",
      actual: "35min（已恢复）",
      affectedObjects: 0,
      action: "无 — 已自动恢复",
    },
  },
  {
    id: "alert-006",
    time: new Date(Date.now() - 18 * 3600_000).toISOString(),
    type: "合规检查",
    severity: "info",
    source: "合规引擎",
    status: "resolved",
    title: "月度合规审计完成",
    description: "7 月数据合规审计完成，未发现违规项。共检查 1,234 条数据规则，通过率 100%。",
    assignee: "赵六",
    detail: {
      trigger: "月度定时任务",
      threshold: "通过率 ≥ 95%",
      actual: "100%",
      affectedObjects: 1234,
      action: "无",
    },
  },
  {
    id: "alert-007",
    time: new Date(Date.now() - 26 * 3600_000).toISOString(),
    type: "交易异常",
    severity: "critical",
    source: "风控引擎",
    status: "resolved",
    title: "疑似套现行为",
    description: "用户 user_77233 通过循环交易疑似套现 ¥120,000，已确认并冻结账户。",
    assignee: "张三",
    detail: {
      trigger: "信用卡还款后立即消费 > 3 次",
      threshold: "还款-消费间隔 > 1h",
      actual: "平均间隔 2.3min",
      affectedObjects: 6,
      action: "已冻结 · 移交风控调查",
    },
  },
];

/* ============================================================================
 * 纯函数（导出用于测试）
 * ========================================================================== */

export function filterBySeverity(alerts: RiskAlert[], severity: Severity | "all"): RiskAlert[] {
  if (severity === "all") return alerts;
  return alerts.filter((a) => a.severity === severity);
}

export interface AlertStats {
  total: number;
  critical: number;
  processing: number;
  resolved: number;
}

export function computeStats(alerts: RiskAlert[]): AlertStats {
  return {
    total: alerts.length,
    critical: alerts.filter((a) => a.severity === "critical").length,
    processing: alerts.filter((a) => a.status === "processing").length,
    resolved: alerts.filter((a) => a.status === "resolved").length,
  };
}

export function formatAlertTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  return `${days} 天前`;
}

/* ============================================================================
 * 页面组件
 * ========================================================================== */

export function RiskAlertPage() {
  const [alerts, setAlerts] = useState<RiskAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [severityFilter, setSeverityFilter] = useState<Severity | "all">("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    apiGet<{ items: RiskAlert[] }>("/v1/risk-alerts")
      .then((j) => {
        setAlerts(j.items?.length ? j.items : MOCK_ALERTS);
        setLoading(false);
      })
      .catch(() => {
        // API 不可用时使用 mock 数据
        setAlerts(MOCK_ALERTS);
        setLoading(false);
      });
  }, []);

  const stats = useMemo(() => computeStats(alerts), [alerts]);

  const filteredAlerts = useMemo(
    () => filterBySeverity(alerts, severityFilter),
    [alerts, severityFilter],
  );

  return (
    <PageChrome title="风险告警" lede="实时监控业务风险 · 快速响应处置">
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "24px 0" }}>
        {/* 顶部统计卡片 */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: 12,
            marginBottom: 24,
          }}
          data-testid="stats-cards"
        >
          <StatCard
            label="今日告警"
            value={stats.total}
            color="var(--aos-blue-600)"
            bg="var(--aos-accent-light)"
            icon={
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M15 17h5l-1.4-1.4A2 2 0 0118 14.2V11a6 6 0 10-12 0v3.2c0 .5-.2 1-.6 1.4L4 17h5M10 20a2 2 0 002-2h-2a2 2 0 002 2z" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            }
          />
          <StatCard
            label="严重告警"
            value={stats.critical}
            color="var(--aos-red)"
            bg="var(--aos-red-bg)"
            icon={
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M12 9v4M12 17h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            }
          />
          <StatCard
            label="处理中"
            value={stats.processing}
            color="var(--aos-amber-600)"
            bg="var(--aos-amber-bg)"
            icon={
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 6v6l4 2" strokeLinecap="round" />
              </svg>
            }
          />
          <StatCard
            label="已解决"
            value={stats.resolved}
            color="var(--aos-green-600)"
            bg="var(--aos-green-bg)"
            icon={
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            }
          />
        </div>

        {/* 严重度筛选 */}
        <div
          style={{ display: "flex", gap: 8, marginBottom: 16 }}
          data-testid="severity-filters"
        >
          {SEVERITY_FILTERS.map((sf) => (
            <button
              key={sf.id}
              type="button"
              data-testid={`sev-filter-${sf.id}`}
              onClick={() => setSeverityFilter(sf.id)}
              style={{
                padding: "6px 14px",
                borderRadius: 6,
                fontSize: 12,
                fontWeight: 500,
                cursor: "pointer",
                border: severityFilter === sf.id ? "1.5px solid var(--aos-blue-600)" : "1px solid var(--aos-border)",
                background: severityFilter === sf.id ? "var(--aos-accent-light)" : "var(--aos-surface)",
                color: severityFilter === sf.id ? "var(--aos-blue-600)" : "var(--aos-text-secondary)",
                transition: "all 0.15s",
              }}
            >
              {sf.label}
              {sf.id !== "all" && (
                <span style={{ marginLeft: 4, fontSize: 11, opacity: 0.7 }}>
                  ({alerts.filter((a) => a.severity === sf.id).length})
                </span>
              )}
            </button>
          ))}
        </div>

        {/* 告警列表表格 */}
        {loading ? (
          <div style={{ textAlign: "center", padding: 48, color: "var(--aos-text-tertiary)" }}>加载中...</div>
        ) : filteredAlerts.length === 0 ? (
          <div
            style={{
              textAlign: "center",
              padding: 48,
              color: "var(--aos-text-tertiary)",
              border: "1px solid var(--aos-border)",
              borderRadius: 8,
              background: "var(--aos-surface)",
            }}
          >
            暂无告警记录
          </div>
        ) : (
          <div
            style={{
              border: "1px solid var(--aos-border)",
              borderRadius: 8,
              overflow: "hidden",
              background: "var(--aos-surface)",
            }}
            data-testid="alert-table"
          >
            {/* 表头 */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "120px 100px 80px 120px 100px 1fr 40px",
                gap: 0,
                padding: "10px 16px",
                background: "var(--aos-surface-hover)",
                borderBottom: "1px solid var(--aos-border)",
                fontSize: 11,
                fontWeight: 600,
                color: "var(--aos-text-secondary)",
                textTransform: "uppercase",
                letterSpacing: "0.03em",
              }}
            >
              <div>时间</div>
              <div>类型</div>
              <div>严重度</div>
              <div>来源</div>
              <div>状态</div>
              <div>告警标题</div>
              <div></div>
            </div>
            {/* 表体 */}
            <div data-testid="alert-rows">
              {filteredAlerts.map((alert) => {
                const sevMeta = SEVERITY_META[alert.severity];
                const statusMeta = STATUS_META[alert.status];
                const expanded = expandedId === alert.id;
                return (
                  <div key={alert.id} data-testid={`alert-row-${alert.id}`}>
                    <div
                      onClick={() => setExpandedId(expanded ? null : alert.id)}
                      style={{
                        display: "grid",
                        gridTemplateColumns: "120px 100px 80px 120px 100px 1fr 40px",
                        gap: 0,
                        padding: "12px 16px",
                        borderBottom: expanded ? "none" : "1px solid var(--aos-gray-100)",
                        cursor: "pointer",
                        transition: "background 0.1s",
                        alignItems: "center",
                      }}
                      className="wl-alert-row"
                    >
                      <div style={{ fontSize: 11, color: "var(--aos-text-secondary)" }}>
                        {formatAlertTime(alert.time)}
                      </div>
                      <div style={{ fontSize: 12, color: "var(--aos-text)" }}>{alert.type}</div>
                      <div>
                        <span
                          style={{
                            display: "inline-block",
                            fontSize: 11,
                            fontWeight: 500,
                            padding: "2px 8px",
                            borderRadius: 4,
                            background: sevMeta.bg,
                            color: sevMeta.color,
                          }}
                        >
                          {sevMeta.label}
                        </span>
                      </div>
                      <div style={{ fontSize: 11, color: "var(--aos-text-secondary)" }}>{alert.source}</div>
                      <div>
                        <span
                          style={{
                            display: "inline-block",
                            fontSize: 11,
                            fontWeight: 500,
                            padding: "2px 8px",
                            borderRadius: 4,
                            background: statusMeta.bg,
                            color: statusMeta.color,
                          }}
                        >
                          {statusMeta.label}
                        </span>
                      </div>
                      <div
                        style={{
                          fontSize: 12,
                          fontWeight: 500,
                          color: "var(--aos-text)",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {alert.title}
                      </div>
                      <div style={{ fontSize: 14, color: "var(--aos-text-tertiary)", textAlign: "center" }}>
                        {expanded ? "▴" : "▾"}
                      </div>
                    </div>

                    {/* 展开详情 */}
                    {expanded && (
                      <div
                        style={{
                          padding: "16px 20px",
                          background: "var(--aos-surface-hover)",
                          borderBottom: "1px solid var(--aos-gray-100)",
                          borderLeft: `3px solid ${sevMeta.color}`,
                        }}
                        data-testid={`alert-detail-${alert.id}`}
                      >
                        <p style={{ fontSize: 12, color: "var(--aos-text)", lineHeight: 1.6, margin: "0 0 12px 0" }}>
                          {alert.description}
                        </p>
                        {alert.detail && (
                          <div
                            style={{
                              display: "grid",
                              gridTemplateColumns: "repeat(2, 1fr)",
                              gap: 12,
                            }}
                          >
                            <DetailItem label="触发规则" value={alert.detail.trigger} />
                            {alert.detail.threshold && (
                              <DetailItem label="阈值" value={alert.detail.threshold} />
                            )}
                            {alert.detail.actual && (
                              <DetailItem label="实际值" value={alert.detail.actual} />
                            )}
                            {alert.detail.affectedObjects !== undefined && (
                              <DetailItem
                                label="影响对象"
                                value={`${alert.detail.affectedObjects} 个`}
                              />
                            )}
                            {alert.detail.action && (
                              <DetailItem label="处置动作" value={alert.detail.action} />
                            )}
                          </div>
                        )}
                        <div
                          style={{
                            display: "flex",
                            gap: 12,
                            marginTop: 12,
                            fontSize: 11,
                            color: "var(--aos-text-tertiary)",
                          }}
                        >
                          <span>告警 ID：{alert.id}</span>
                          <span>·</span>
                          <span>处理人：{alert.assignee || "未分派"}</span>
                          <span>·</span>
                          <span>
                            时间：{new Date(alert.time).toLocaleString("zh-CN")}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </PageChrome>
  );
}

/* ============================================================================
 * 子组件
 * ========================================================================== */

function StatCard({
  label,
  value,
  color,
  bg,
  icon,
}: {
  label: string;
  value: number;
  color: string;
  bg: string;
  icon: React.ReactNode;
}) {
  return (
    <div
      style={{
        border: "1px solid var(--aos-border)",
        borderRadius: 8,
        padding: 16,
        background: "var(--aos-surface)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 6,
            background: bg,
            color,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {icon}
        </div>
        <span style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>{label}</span>
      </div>
      <div style={{ fontSize: 24, fontWeight: 700, color }} data-testid={`stat-value-${label}`}>
        {value}
      </div>
    </div>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: "var(--aos-text-tertiary)", marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 12, color: "var(--aos-text)", fontWeight: 500 }}>{value}</div>
    </div>
  );
}
