import { useState } from "react";
import { Link } from "react-router-dom";
import { S2Chrome } from "./shared";
import { BpBanner, BpMetricGrid, BpToolbar } from "./blueprintUi";
import { BpBadge, BpCard } from "../../components/bp";

/* ============================================================
 * 类型定义
 * ============================================================ */

export type PlatformStatus = "live" | "ref" | "wip";

export type PlatformCase = {
  id: string;
  name: string;
  icon: string;
  iconBg: string;
  iconColor: string;
  protocol: string;
  auth: string;
  stars: number;
  status: PlatformStatus;
  tables: number;
  apis: number;
  syncs: number;
  objects: number;
  desc: string;
  tag?: string;
};

export type StatItem = {
  code: string;
  label: string;
  value: string;
  trend: string;
  trendUp: boolean;
  hint: string;
  tone: "ok" | "warn" | "muted";
};

export type Blocker = {
  id: string;
  title: string;
  impact: string[];
  priority: "P0" | "P1" | "P2";
  solution: string;
  eta: string;
};

export type E2EStep = {
  id: string;
  step: number;
  label: string;
  icon: string;
  detail: string;
  href: string;
};

/* ============================================================
 * 数据：6 个统计指标
 * ============================================================ */

export const STATS: StatItem[] = [
  {
    code: "PLAT",
    label: "接入平台",
    value: "9",
    trend: "+2",
    trendUp: true,
    hint: "7 已上线 · 2 引用",
    tone: "ok",
  },
  {
    code: "CONN",
    label: "活跃连接器",
    value: "12",
    trend: "+3",
    trendUp: true,
    hint: "REST · GraphQL · JDBC",
    tone: "ok",
  },
  {
    code: "TASK",
    label: "数据同步任务",
    value: "28",
    trend: "+5",
    trendUp: true,
    hint: "日均 1.2M 行",
    tone: "ok",
  },
  {
    code: "REC",
    label: "今日同步记录",
    value: "1.2M",
    trend: "+8.3%",
    trendUp: true,
    hint: "峰值 50K/min",
    tone: "ok",
  },
  {
    code: "E2E",
    label: "端到端链路",
    value: "5",
    trend: "+1",
    trendUp: true,
    hint: "电商 · 供应链 · 金融",
    tone: "muted",
  },
  {
    code: "LAT",
    label: "平均延迟",
    value: "340ms",
    trend: "-12ms",
    trendUp: true,
    hint: "P95 < 800ms",
    tone: "ok",
  },
];

/* ============================================================
 * 数据：9 大平台案例
 * ============================================================ */

export const PLATFORM_CASES: PlatformCase[] = [
  {
    id: "weishop",
    name: "微商城",
    icon: "🏪",
    iconBg: "var(--aos-red-border)",
    iconColor: "var(--aos-red)",
    protocol: "JDBC",
    auth: "自建库",
    stars: 1,
    status: "live",
    tables: 302,
    apis: 341,
    syncs: 12,
    objects: 8,
    desc: "完整可用作模板",
    tag: "模板",
  },
  {
    id: "taobao",
    name: "淘宝/天猫",
    icon: "🛒",
    iconBg: "var(--aos-amber-bg)",
    iconColor: "var(--aos-red)",
    protocol: "REST",
    auth: "HMAC-SHA256",
    stars: 2,
    status: "live",
    tables: 180,
    apis: 156,
    syncs: 8,
    objects: 6,
    desc: "字段级对照，合并方案",
    tag: "合并方案",
  },
  {
    id: "pdd",
    name: "拼多多",
    icon: "🟠",
    iconBg: "var(--aos-red-border)",
    iconColor: "var(--aos-red)",
    protocol: "REST",
    auth: "MD5",
    stars: 2,
    status: "live",
    tables: 95,
    apis: 32,
    syncs: 6,
    objects: 4,
    desc: "32 接口，订单+售后",
  },
  {
    id: "jd",
    name: "京东",
    icon: "🔴",
    iconBg: "var(--aos-red-border)",
    iconColor: "var(--aos-red)",
    protocol: "REST",
    auth: "HMAC-SHA256",
    stars: 3,
    status: "live",
    tables: 210,
    apis: 42,
    syncs: 7,
    objects: 6,
    desc: "POP/自营差异分析",
  },
  {
    id: "douyin",
    name: "抖音电商",
    icon: "🎵",
    iconBg: "var(--aos-red-border)",
    iconColor: "var(--aos-text)",
    protocol: "REST",
    auth: "Token",
    stars: 4,
    status: "live",
    tables: 150,
    apis: 42,
    syncs: 5,
    objects: 5,
    desc: "内容+电商，达人佣金",
  },
  {
    id: "shopify",
    name: "Shopify",
    icon: "🟢",
    iconBg: "var(--aos-green-border)",
    iconColor: "var(--aos-green-700)",
    protocol: "GraphQL",
    auth: "Webhook",
    stars: 3,
    status: "live",
    tables: 85,
    apis: 38,
    syncs: 9,
    objects: 4,
    desc: "18Q + 7M + 13Webhook",
  },
  {
    id: "amazon",
    name: "Amazon",
    icon: "📦",
    iconBg: "var(--aos-amber-bg)",
    iconColor: "var(--aos-amber)",
    protocol: "SP-API",
    auth: "AWS4",
    stars: 5,
    status: "live",
    tables: 320,
    apis: 40,
    syncs: 10,
    objects: 5,
    desc: "40 接口，多区域部署",
  },
  {
    id: "tmall",
    name: "天猫",
    icon: "🐈",
    iconBg: "var(--aos-amber-bg)",
    iconColor: "var(--aos-red)",
    protocol: "→ 淘宝方案",
    auth: "共用",
    stars: 2,
    status: "ref",
    tables: 0,
    apis: 0,
    syncs: 0,
    objects: 0,
    desc: "主方案已覆盖",
    tag: "引用",
  },
  {
    id: "shopify-cross",
    name: "跨境Shopify",
    icon: "🌍",
    iconBg: "var(--aos-green-border)",
    iconColor: "var(--aos-green-700)",
    protocol: "→ Shopify方案",
    auth: "多币种",
    stars: 3,
    status: "ref",
    tables: 0,
    apis: 0,
    syncs: 0,
    objects: 3,
    desc: "多币种+多语言",
    tag: "引用",
  },
];

/* ============================================================
 * 数据：10 个阻塞项
 * ============================================================ */

export const BLOCKERS: Blocker[] = [
  {
    id: "G1",
    title: "REST API Connector",
    impact: ["淘宝", "京东", "拼多多", "抖音"],
    priority: "P0",
    solution: "W2+ G1",
    eta: "Week 4",
  },
  {
    id: "G2",
    title: "OAuth Token Manager",
    impact: ["淘宝", "京东", "拼多多", "抖音", "Shopify", "Amazon"],
    priority: "P0",
    solution: "W2+ G2",
    eta: "Week 4",
  },
  {
    id: "G3",
    title: "GraphQL Connector",
    impact: ["Shopify", "跨境Shopify"],
    priority: "P1",
    solution: "W2+ G3",
    eta: "Week 5",
  },
  {
    id: "G4",
    title: "Webhook Handler",
    impact: ["Shopify"],
    priority: "P1",
    solution: "W2+ G4",
    eta: "Week 5",
  },
  {
    id: "G5",
    title: "SP-API 签名器",
    impact: ["Amazon"],
    priority: "P1",
    solution: "W2+ G5",
    eta: "Week 5",
  },
  {
    id: "G6",
    title: "HMAC-SHA256 签名",
    impact: ["淘宝", "京东"],
    priority: "P1",
    solution: "W2+ G6",
    eta: "Week 5",
  },
  {
    id: "G7",
    title: "AWS4 签名",
    impact: ["Amazon"],
    priority: "P1",
    solution: "W2+ G7",
    eta: "Week 5",
  },
  {
    id: "G8",
    title: "达人佣金模型",
    impact: ["抖音"],
    priority: "P2",
    solution: "W2+ G8",
    eta: "Week 6",
  },
  {
    id: "G9",
    title: "抖店云部署",
    impact: ["抖音"],
    priority: "P2",
    solution: "W2+ G9",
    eta: "Week 6",
  },
  {
    id: "G10",
    title: "多区域路由",
    impact: ["Amazon"],
    priority: "P2",
    solution: "W2+ G10",
    eta: "Week 6",
  },
];

/* ============================================================
 * 数据：端到端链路 7 步
 * ============================================================ */

export const E2E_STEPS: E2EStep[] = [
  {
    id: "source",
    step: 1,
    label: "源平台 API",
    icon: "🌐",
    detail: "9 个平台的 API 入口",
    href: "/data",
  },
  {
    id: "connector",
    step: 2,
    label: "Connector",
    icon: "🔌",
    detail: "REST / GraphQL / SP-API",
    href: "/data",
  },
  {
    id: "sync",
    step: 3,
    label: "数据同步",
    icon: "🔄",
    detail: "全量 / 增量 / CDC",
    href: "/data/sync-config",
  },
  {
    id: "pipeline",
    step: 4,
    label: "Pipeline 变换",
    icon: "⚙️",
    detail: "字段映射 + 清洗 + 聚合",
    href: "/data/pipelines",
  },
  {
    id: "ontology",
    step: 5,
    label: "Ontology 物化",
    icon: "🏗️",
    detail: "9 大实体域",
    href: "/ontology",
  },
  {
    id: "aip",
    step: 6,
    label: "AIP 决策",
    icon: "🤖",
    detail: "Agent + Logic + Eval",
    href: "/aip/tools",
  },
  {
    id: "action",
    step: 7,
    label: "Action 回写",
    icon: "✏️",
    detail: "库存 / 价格 / 发货",
    href: "/ontology",
  },
];

/* ============================================================
 * 辅助函数
 * ============================================================ */

/** 状态元信息 */
export const STATUS_META: Record<PlatformStatus, { label: string; variant: "success" | "warning" | "default" }> = {
  live: { label: "✅ 生产", variant: "success" },
  ref: { label: "📎 引用", variant: "warning" },
  wip: { label: "🔨 开发中", variant: "default" },
};

/** 优先级颜色 */
export const PRIORITY_VARIANT: Record<Blocker["priority"], "danger" | "warning" | "success"> = {
  P0: "danger",
  P1: "warning",
  P2: "success",
};

/** 渲染星级 */
export function renderStars(count: number): string {
  return "⭐".repeat(Math.max(0, Math.min(5, count)));
}

/* ============================================================
 * 页面组件
 * ============================================================ */

export function IntegrationCasesPage() {
  const [selectedCase, setSelectedCase] = useState<string | null>(null);
  const [expandedBlocker, setExpandedBlocker] = useState<string | null>(null);
  const [expandedStep, setExpandedStep] = useState<string | null>(null);

  return (
    <S2Chrome
      title="接入案例 · 电商平台端到端链路"
      lede="从外部数据源接入到本体数字孪生最终到上层消费的端到端案例"
    >
      <BpToolbar>
        <Link to="/data" className="btn-nav">
          数据链接器 →
        </Link>
        <Link to="/ontology" className="btn-nav">
          本体管理 →
        </Link>
        <Link to="/data/sync-config" className="btn-nav">
          同步配置 →
        </Link>
      </BpToolbar>

      {/* ====================================================
       * 区域 1: 统计指标栏（6 个指标卡）
       * ==================================================== */}
      <BpMetricGrid
        items={STATS.map((s) => ({
          code: s.code,
          label: s.label,
          value: (
            <span>
              {s.value}{" "}
              <span
                style={{
                  fontSize: "0.7rem",
                  color: s.trendUp ? "var(--aos-green-600)" : "var(--aos-red)",
                  fontWeight: 600,
                }}
              >
                {s.trendUp ? "↑" : "↓"} {s.trend}
              </span>
            </span>
          ),
          hint: s.hint,
          tone: s.tone,
        }))}
      />

      {/* ====================================================
       * 区域 4: 端到端链路展示（放在案例列表前，作为概览）
       * ==================================================== */}
      <div style={{ marginTop: "1.5rem" }}>
        <h2 className="bp-ws-section-title">端到端链路（Stage 1 → Stage 7）</h2>
        <p className="muted" style={{ fontSize: "0.8rem", marginBottom: "0.75rem" }}>
          7 个阶段从源平台到 Action 回写的全链路。点击节点查看详情。
        </p>
        <div
          style={{
            display: "flex",
            alignItems: "stretch",
            gap: 0,
            overflowX: "auto",
            paddingBottom: "0.5rem",
          }}
        >
          {E2E_STEPS.map((step, i) => (
            <div key={step.id} style={{ display: "flex", alignItems: "stretch", flexShrink: 0 }}>
              <div
                onClick={() => setExpandedStep(expandedStep === step.id ? null : step.id)}
                style={{
                  minWidth: 130,
                  padding: "0.75rem",
                  borderRadius: 8,
                  border: "1px solid var(--aos-border)",
                  cursor: "pointer",
                  background: expandedStep === step.id ? "var(--aos-accent-light)" : "var(--aos-surface)",
                  transition: "background 0.15s",
                }}
              >
                <div style={{ fontSize: "1.5rem" }}>{step.icon}</div>
                <div style={{ fontSize: "0.65rem", color: "var(--aos-text-secondary)", marginTop: 2 }}>
                  Step {step.step}
                </div>
                <div style={{ fontWeight: 600, fontSize: "0.8rem", margin: "2px 0" }}>{step.label}</div>
                <div style={{ fontSize: "0.65rem", color: "var(--aos-text-secondary)" }}>{step.detail}</div>
              </div>
              {i < E2E_STEPS.length - 1 && (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    padding: "0 4px",
                    color: "var(--aos-text-tertiary)",
                    fontWeight: 700,
                  }}
                >
                  →
                </div>
              )}
            </div>
          ))}
        </div>
        {expandedStep && (
          <BpCard variant="filled" padding="sm">
            <strong>{E2E_STEPS.find((s) => s.id === expandedStep)?.label}</strong>:{" "}
            {E2E_STEPS.find((s) => s.id === expandedStep)?.detail}
            <Link
              to={E2E_STEPS.find((s) => s.id === expandedStep)?.href || "#"}
              className="nav-link"
              style={{ marginLeft: 8, fontSize: "0.75rem" }}
            >
              查看专题 →
            </Link>
          </BpCard>
        )}
      </div>

      {/* ====================================================
       * 区域 2: 9 大平台案例卡片网格
       * ==================================================== */}
      <div style={{ marginTop: "1.5rem" }}>
        <h2 className="bp-ws-section-title">9 个平台案例</h2>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
            gap: "0.75rem",
          }}
        >
          {PLATFORM_CASES.map((pc) => {
            const isSelected = selectedCase === pc.id;
            return (
              <BpCard
                key={pc.id}
                variant="elevated"
                padding="md"
                hover
                clickable
                onClick={() => setSelectedCase(isSelected ? null : pc.id)}
                title={
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        justifyContent: "center",
                        width: 32,
                        height: 32,
                        borderRadius: 8,
                        background: pc.iconBg,
                        color: pc.iconColor,
                        fontSize: "1.1rem",
                      }}
                    >
                      {pc.icon}
                    </span>
                    <span>{pc.name}</span>
                    {pc.tag && (
                      <BpBadge variant="info" size="sm">
                        {pc.tag}
                      </BpBadge>
                    )}
                  </div>
                }
                subtitle={`${pc.protocol} · ${pc.auth} · ${renderStars(pc.stars)}`}
                actions={
                  <BpBadge variant={STATUS_META[pc.status].variant} size="sm">
                    {STATUS_META[pc.status].label}
                  </BpBadge>
                }
              >
                <p className="muted" style={{ fontSize: "0.75rem", marginBottom: "0.5rem" }}>
                  {pc.desc}
                </p>
                {/* 核心数据统计 */}
                <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
                  {pc.tables > 0 && (
                    <div style={{ textAlign: "center" }}>
                      <div style={{ fontSize: "0.65rem", color: "var(--aos-text-tertiary)" }}>表数</div>
                      <div style={{ fontWeight: 700, fontSize: "0.9rem" }}>{pc.tables}</div>
                    </div>
                  )}
                  {pc.apis > 0 && (
                    <div style={{ textAlign: "center" }}>
                      <div style={{ fontSize: "0.65rem", color: "var(--aos-text-tertiary)" }}>API</div>
                      <div style={{ fontWeight: 700, fontSize: "0.9rem" }}>{pc.apis}</div>
                    </div>
                  )}
                  {pc.syncs > 0 && (
                    <div style={{ textAlign: "center" }}>
                      <div style={{ fontSize: "0.65rem", color: "var(--aos-text-tertiary)" }}>同步</div>
                      <div style={{ fontWeight: 700, fontSize: "0.9rem" }}>{pc.syncs}</div>
                    </div>
                  )}
                  <div style={{ textAlign: "center" }}>
                    <div style={{ fontSize: "0.65rem", color: "var(--aos-text-tertiary)" }}>本体对象</div>
                    <div style={{ fontWeight: 700, fontSize: "0.9rem" }}>{pc.objects}</div>
                  </div>
                </div>
                {/* 链路进度条 */}
                {isSelected && (
                  <div
                    style={{
                      marginTop: "0.5rem",
                      padding: "0.5rem",
                      background: "var(--aos-bg-secondary)",
                      borderRadius: 6,
                      fontSize: "0.7rem",
                    }}
                  >
                    <strong>端到端链路:</strong>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 4 }}>
                      {E2E_STEPS.map((s, i) => (
                        <span key={s.id} className="bp-tag bp-tag-ok" style={{ fontSize: "0.6rem" }}>
                          {i + 1}. {s.label}
                        </span>
                      ))}
                    </div>
                    <Link
                      to="/data"
                      className="nav-link"
                      style={{ fontSize: "0.7rem", display: "inline-block", marginTop: 4 }}
                    >
                      查看链路详情 →
                    </Link>
                  </div>
                )}
              </BpCard>
            );
          })}
        </div>
      </div>

      {/* ====================================================
       * 区域 3: 10 个阻塞项看板
       * ==================================================== */}
      <div style={{ marginTop: "1.5rem" }}>
        <h2 className="bp-ws-section-title">G1-G10 公共阻塞项</h2>
        <p className="muted" style={{ fontSize: "0.8rem", marginBottom: "0.75rem" }}>
          跨平台共通的阻塞项，按优先级排列。点击展开详情。
        </p>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
            gap: "0.5rem",
          }}
        >
          {BLOCKERS.map((b) => {
            const isExpanded = expandedBlocker === b.id;
            return (
              <div
                key={b.id}
                onClick={() => setExpandedBlocker(isExpanded ? null : b.id)}
                style={{
                  padding: "0.6rem 0.75rem",
                  borderRadius: 8,
                  border: "1px solid var(--aos-border)",
                  cursor: "pointer",
                  background: isExpanded ? "var(--aos-amber-bg)" : "var(--aos-surface)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <BpBadge
                    variant={PRIORITY_VARIANT[b.priority]}
                    size="sm"
                  >
                    {b.priority}
                  </BpBadge>
                  <span
                    style={{
                      fontWeight: 700,
                      fontSize: "0.75rem",
                      color: "var(--aos-text-secondary)",
                      minWidth: 28,
                    }}
                  >
                    {b.id}
                  </span>
                  <span style={{ fontWeight: 600, fontSize: "0.8rem", flex: 1 }}>{b.title}</span>
                </div>
                <div style={{ fontSize: "0.7rem", color: "var(--aos-text-secondary)", marginTop: 4 }}>
                  影响 {b.impact.length} 平台: {b.impact.join("、")}
                </div>
                {isExpanded && (
                  <div style={{ marginTop: 6, fontSize: "0.7rem", color: "var(--aos-text-secondary)" }}>
                    <div>
                      <strong>解决方案:</strong> {b.solution}
                    </div>
                    <div>
                      <strong>预计解除:</strong> {b.eta}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <BpBanner tone="info">
        每个案例展示一条完整链路：数据接入 → 同步 → 管道清洗 → OKF 映射 → 本体实例化 → AIP 决策 →
        Action 回写。点击案例卡片可展开详情。
      </BpBanner>
    </S2Chrome>
  );
}
