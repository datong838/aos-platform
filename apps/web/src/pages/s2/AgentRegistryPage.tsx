import { useState, useMemo, useEffect } from "react";
import { Link } from "react-router-dom";
import { PageChrome } from "../../components/PageChrome";
import { apiGet } from "../../api/client";

export type AgentSource = "builtin" | "plugin" | "external";
export type AgentStatus = "running" | "draft" | "stopped" | "ready" | "session";

export type AgentTag = {
  label: string;
  tone: "indigo" | "yellow" | "orange" | "green" | "blue" | "purple";
};

export type AgentCard = {
  id: string;
  name: string;
  category: string;
  source: AgentSource;
  sourceLabel: string;
  status: AgentStatus;
  statusLabel: string;
  description: string;
  tags: AgentTag[];
  toolCount: number;
  callCount: number;
  iconBg: string;
  iconColor: string;
  iconType: string;
  detailLink: string;
  detailLabel: string;
  adapterInfo?: string;
};

/** 筛选器类型 */
export type AgentFilter = {
  source: AgentSource | "all";
  status: AgentStatus | "all";
  tag: string;
};

/** 计算指标卡统计数据（纯函数，便于测试） */
export function computeRegistryStats(agents: AgentCard[]) {
  const total = agents.length;
  const active = agents.filter(
    (a) => a.status === "running" || a.status === "ready" || a.status === "session",
  ).length;
  const draft = agents.filter((a) => a.status === "draft").length;
  const stopped = agents.filter((a) => a.status === "stopped").length;
  const totalCalls = agents.reduce((sum, a) => sum + a.callCount, 0);
  const totalTools = agents.reduce((sum, a) => sum + a.toolCount, 0);
  const avgCalls = total > 0 ? Math.round(totalCalls / total) : 0;
  const guardrailCoverage =
    total > 0
      ? Math.round(
          (agents.filter((a) => a.tags.some((t) => t.label.includes("HITL") || t.label.includes("L0") || t.label.includes("L1"))).length /
            total) *
            100,
        )
      : 0;
  return {
    total,
    active,
    draft,
    stopped,
    totalCalls,
    totalTools,
    avgCalls,
    guardrailCoverage,
  };
}

/** 提取所有可用标签（纯函数） */
export function extractAllTags(agents: AgentCard[]): string[] {
  const set = new Set<string>();
  agents.forEach((a) => a.tags.forEach((t) => set.add(t.label)));
  return Array.from(set).sort();
}

/** 按多条件筛选 Agent（纯函数，便于测试） */
export function filterAgents(agents: AgentCard[], filter: AgentFilter, search: string): AgentCard[] {
  const q = search.trim().toLowerCase();
  return agents.filter((a) => {
    if (filter.source !== "all" && a.source !== filter.source) return false;
    if (filter.status !== "all" && a.status !== filter.status) return false;
    if (filter.tag !== "all" && !a.tags.some((t) => t.label === filter.tag)) return false;
    if (q && !a.name.toLowerCase().includes(q) && !a.description.toLowerCase().includes(q) && !a.category.toLowerCase().includes(q))
      return false;
    return true;
  });
}

const MOCK_AGENTS: AgentCard[] = [
  {
    id: "repair-buddy",
    name: "维修派单 Buddy",
    category: "设备运维",
    source: "builtin",
    sourceLabel: "平台内创建",
    status: "running",
    statusLabel: "运行中",
    description: "接收设备故障工单，自动匹配维修人员、预估时长、生成备件清单。支持 L2 人机协作审批。",
    tags: [
      { label: "工单分配", tone: "indigo" },
      { label: "人员匹配", tone: "indigo" },
      { label: "备件预判", tone: "indigo" },
      { label: "L2 · HITL", tone: "yellow" },
    ],
    toolCount: 5,
    callCount: 1280,
    iconBg: "#FEF3C7",
    iconColor: "#D97706",
    iconType: "wrench",
    detailLink: "/aip/studio",
    detailLabel: "配置 →",
  },
  {
    id: "video-agent",
    name: "短视频生产 Agent",
    category: "内容创作",
    source: "builtin",
    sourceLabel: "平台内创建",
    status: "running",
    statusLabel: "运行中",
    description: "从选品到脚本到素材混剪，自动生成电商短视频。调用 Media Job Capability 提交 GPU 渲染任务。",
    tags: [
      { label: "脚本生成", tone: "indigo" },
      { label: "素材混剪", tone: "indigo" },
      { label: "字幕烧录", tone: "indigo" },
      { label: "L3 · 自主", tone: "orange" },
    ],
    toolCount: 4,
    callCount: 860,
    iconBg: "#DBEAFE",
    iconColor: "#2563EB",
    iconType: "video",
    detailLink: "/aip/studio",
    detailLabel: "配置 →",
  },
  {
    id: "risk-agent",
    name: "风险告警分析 Agent",
    category: "风控分析",
    source: "builtin",
    sourceLabel: "平台内创建",
    status: "draft",
    statusLabel: "Draft",
    description: "实时监控订单异常模式，识别刷单、退货欺诈、价格异常。产出风险评分并写入 RiskAlert 对象。",
    tags: [
      { label: "异常检测", tone: "indigo" },
      { label: "风险评分", tone: "indigo" },
      { label: "告警分发", tone: "indigo" },
      { label: "L1 · 建议", tone: "blue" },
    ],
    toolCount: 6,
    callCount: 420,
    iconBg: "#FEE2E2",
    iconColor: "#DC2626",
    iconType: "alert",
    detailLink: "/aip/studio",
    detailLabel: "配置 →",
  },
  {
    id: "order-agent",
    name: "订单客服 Agent",
    category: "电商客服",
    source: "builtin",
    sourceLabel: "平台内创建",
    status: "running",
    statusLabel: "运行中",
    description: "处理售前咨询、订单查询、物流追踪、退换货发起。支持多轮对话上下文，可直接发起退款 Action。",
    tags: [
      { label: "多轮对话", tone: "indigo" },
      { label: "订单查询", tone: "indigo" },
      { label: "退款发起", tone: "indigo" },
      { label: "L2 · HITL", tone: "yellow" },
    ],
    toolCount: 3,
    callCount: 3200,
    iconBg: "#DCFCE7",
    iconColor: "#16A34A",
    iconType: "chat",
    detailLink: "/aip/studio",
    detailLabel: "配置 →",
  },
  {
    id: "doc-agent",
    name: "文档问答 Agent",
    category: "知识检索",
    source: "builtin",
    sourceLabel: "平台内创建",
    status: "stopped",
    statusLabel: "已停用",
    description: "基于 Wiki 和文档库的 RAG 问答，支持引用溯源。只读模式，不触发任何写操作。",
    tags: [
      { label: "RAG 检索", tone: "indigo" },
      { label: "引用溯源", tone: "indigo" },
      { label: "L0 · 只读", tone: "green" },
    ],
    toolCount: 2,
    callCount: 156,
    iconBg: "#EDE9FE",
    iconColor: "#7C3AED",
    iconType: "doc",
    detailLink: "/aip/studio",
    detailLabel: "配置 →",
  },
  {
    id: "cap-video-gen",
    name: "短视频生成",
    category: "媒体能力",
    source: "plugin",
    sourceLabel: "插件引入",
    status: "ready",
    statusLabel: "就绪",
    description: "C1 Job 类型能力。提交文本/图片输入，异步生成 MP4 短视频，产物写入 MediaSet 对象。",
    tags: [
      { label: "C1 · Job", tone: "green" },
      { label: "GPU 渲染", tone: "indigo" },
      { label: "MediaSet", tone: "indigo" },
    ],
    toolCount: 0,
    callCount: 640,
    iconBg: "#FCE7F3",
    iconColor: "#DB2777",
    iconType: "play",
    detailLink: "/aip/capabilities",
    detailLabel: "管理 →",
    adapterInfo: "Adapter: HTTP API",
  },
  {
    id: "cap-live-script",
    name: "直播稿引擎",
    category: "内容能力",
    source: "plugin",
    sourceLabel: "插件引入",
    status: "ready",
    statusLabel: "就绪",
    description: "根据商品信息和营销策略，实时生成直播口播稿。C0 同步能力，可升级为 C1 异步批处理。",
    tags: [
      { label: "C0 · Sync", tone: "green" },
      { label: "口播稿", tone: "indigo" },
      { label: "LiveScript", tone: "indigo" },
    ],
    toolCount: 0,
    callCount: 320,
    iconBg: "#CCFBF1",
    iconColor: "#0D9488",
    iconType: "monitor",
    detailLink: "/aip/capabilities",
    detailLabel: "管理 →",
    adapterInfo: "Adapter: HTTP API",
  },
  {
    id: "cap-avatar-ecom",
    name: "电商可交互数字人",
    category: "交互能力",
    source: "plugin",
    sourceLabel: "插件引入",
    status: "session",
    statusLabel: "会话中",
    description: "C2 Session 类型。实时驱动的虚拟主播，支持弹幕互动、商品讲解、限时促销口播。WebSocket 会话管理。",
    tags: [
      { label: "C2 · Session", tone: "blue" },
      { label: "虚拟主播", tone: "indigo" },
      { label: "弹幕互动", tone: "indigo" },
    ],
    toolCount: 0,
    callCount: 85,
    iconBg: "#E0E7FF",
    iconColor: "#4F46E5",
    iconType: "avatar",
    detailLink: "/aip/capabilities",
    detailLabel: "管理 →",
    adapterInfo: "Adapter: Session GW",
  },
  {
    id: "cap-avatar-edu",
    name: "教育可交互数字人",
    category: "交互能力",
    source: "plugin",
    sourceLabel: "插件引入",
    status: "stopped",
    statusLabel: "已停用",
    description: "面向在线教育的虚拟教师，按课纲 Wiki 自动生成讲解内容。当前停用，等待课纲库扩充后重新启用。",
    tags: [
      { label: "C2 · Session", tone: "blue" },
      { label: "虚拟教师", tone: "indigo" },
      { label: "课纲 Wiki", tone: "indigo" },
    ],
    toolCount: 0,
    callCount: 12,
    iconBg: "#F3F4F6",
    iconColor: "#6B7280",
    iconType: "avatar",
    detailLink: "/aip/capabilities",
    detailLabel: "管理 →",
    adapterInfo: "Adapter: Session GW",
  },
  {
    id: "ext-autogen",
    name: "AutoGen 多 Agent 协作",
    category: "awesome-llm-apps",
    source: "external",
    sourceLabel: "外部接入",
    status: "running",
    statusLabel: "运行中",
    description: "Microsoft AutoGen 框架。多个 Agent 在对话中协作完成复杂任务（如代码评审→修改→测试→部署建议）。",
    tags: [
      { label: "Process Wrapper", tone: "orange" },
      { label: "多角色协作", tone: "indigo" },
      { label: "代码评审", tone: "indigo" },
      { label: "L2 · HITL", tone: "yellow" },
    ],
    toolCount: 0,
    callCount: 45,
    iconBg: "#FFEDD5",
    iconColor: "#EA580C",
    iconType: "multi-agent",
    detailLink: "/aip/capabilities",
    detailLabel: "管理 →",
    adapterInfo: "沙箱子进程",
  },
  {
    id: "ext-crewai",
    name: "CrewAI 角色编排",
    category: "awesome-llm-apps",
    source: "external",
    sourceLabel: "外部接入",
    status: "draft",
    statusLabel: "Draft",
    description: "定义 Crew 角色组（研究员、作家、审核员），按任务链自动编排。适用于内容生产流水线。",
    tags: [
      { label: "Process Wrapper", tone: "orange" },
      { label: "角色编排", tone: "indigo" },
      { label: "任务链", tone: "indigo" },
      { label: "L1 · 建议", tone: "blue" },
    ],
    toolCount: 0,
    callCount: 28,
    iconBg: "#FFEDD5",
    iconColor: "#EA580C",
    iconType: "crew",
    detailLink: "/aip/capabilities",
    detailLabel: "管理 →",
    adapterInfo: "沙箱子进程",
  },
];

const SOURCE_TABS: { id: AgentSource | "all"; label: string; dotColor: string }[] = [
  { id: "all", label: "全部", dotColor: "" },
  { id: "builtin", label: "平台内创建", dotColor: "#6366F1" },
  { id: "plugin", label: "插件引入", dotColor: "#10B981" },
  { id: "external", label: "外部接入", dotColor: "#F97316" },
];

export const STATUS_TABS: { id: AgentStatus | "all"; label: string; color: string }[] = [
  { id: "all", label: "全部状态", color: "#6B7280" },
  { id: "running", label: "运行中", color: "#16A34A" },
  { id: "ready", label: "就绪", color: "#2563EB" },
  { id: "session", label: "会话中", color: "#4F46E5" },
  { id: "draft", label: "草稿", color: "#D97706" },
  { id: "stopped", label: "已停用", color: "#9CA3AF" },
];

const SORT_OPTIONS = [
  { value: "recent", label: "最近更新" },
  { value: "name", label: "名称" },
  { value: "calls", label: "调用量" },
];

function statusStyle(status: AgentStatus) {
  switch (status) {
    case "running":
    case "ready":
      return { bg: "#DCFCE7", color: "#166534" };
    case "draft":
      return { bg: "#FEF3C7", color: "#92400E" };
    case "stopped":
      return { bg: "#F3F4F6", color: "#6B7280" };
    case "session":
      return { bg: "#DBEAFE", color: "#1D4ED8" };
  }
}

function tagStyle(tone: string) {
  switch (tone) {
    case "indigo":
      return { bg: "#EEF2FF", color: "#4F46E5" };
    case "yellow":
      return { bg: "#FEF9C3", color: "#A16207" };
    case "orange":
      return { bg: "#FFEDD5", color: "#C2410C" };
    case "green":
      return { bg: "#DCFCE7", color: "#15803D" };
    case "blue":
      return { bg: "#DBEAFE", color: "#1D4ED8" };
    case "purple":
      return { bg: "#EDE9FE", color: "#7C3AED" };
    default:
      return { bg: "#F3F4F6", color: "#6B7280" };
  }
}

function AgentIcon({ type, bg, color }: { type: string; bg: string; color: string }) {
  return (
    <div
      style={{
        width: 40,
        height: 40,
        borderRadius: 12,
        background: bg,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
      }}
    >
      <svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.5}>
        {type === "wrench" && (
          <path
            d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}
        {type === "video" && (
          <>
            <rect x="3" y="5" width="18" height="14" rx="1" />
            <path d="M3 10h18M9 10v9M15 10v9" />
          </>
        )}
        {type === "alert" && (
          <>
            <path d="M12 9v4M12 17h.01" strokeLinecap="round" />
            <path
              d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </>
        )}
        {type === "chat" && (
          <path
            d="M21 11.5a8.5 8.5 0 01-8.5 8.5H5l-3 3V11.5A8.5 8.5 0 0110.5 3h2A8.5 8.5 0 0121 11.5z"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}
        {type === "doc" && (
          <>
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" strokeLinejoin="round" />
            <path d="M14 2v6h6" strokeLinejoin="round" />
            <path d="M16 13H8M16 17H8M10 9H8" strokeLinecap="round" />
          </>
        )}
        {type === "play" && (
          <path
            d="M23 7l-7 5 7 5V7zM14 5H3a2 2 0 00-2 2v10a2 2 0 002 2h11a2 2 0 002-2V7a2 2 0 00-2-2z"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}
        {type === "monitor" && (
          <>
            <rect x="2" y="3" width="20" height="14" rx="2" />
            <path d="M8 21h8M12 17v4" strokeLinecap="round" />
          </>
        )}
        {type === "avatar" && (
          <>
            <circle cx="12" cy="8" r="4" />
            <path d="M4 20c0-4 4-6 8-6s8 2 8 6" strokeLinecap="round" />
          </>
        )}
        {type === "multi-agent" && (
          <>
            <circle cx="6" cy="6" r="2" />
            <circle cx="18" cy="6" r="2" />
            <circle cx="12" cy="18" r="2" />
            <path d="M8 6h8M7 7.5L10 16M17 7.5L14 16" strokeLinecap="round" />
          </>
        )}
        {type === "crew" && (
          <>
            <circle cx="9" cy="8" r="3" />
            <circle cx="17" cy="8" r="3" />
            <path d="M3 20c0-3 3-5 6-5s6 2 6 5M11 20c0-3 3-5 6-5s6 2 6 5" strokeLinecap="round" />
          </>
        )}
      </svg>
    </div>
  );
}

export function AgentRegistryPage() {
  const [agents, setAgents] = useState<AgentCard[]>(MOCK_AGENTS);
  const [sourceTab, setSourceTab] = useState<AgentSource | "all">("all");
  const [statusTab, setStatusTab] = useState<AgentStatus | "all">("all");
  const [tagFilter, setTagFilter] = useState<string>("all");
  const [sortBy, setSortBy] = useState("recent");
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);

  // 尝试调 API，fallback 到 mock 数据
  useEffect(() => {
    setLoading(true);
    apiGet<{ items: AgentCard[] }>("/v1/aip/agent-registry")
      .then((data) => {
        if (data?.items?.length) setAgents(data.items);
      })
      .catch(() => {
        // API 未就绪，保留默认 mock 数据
        setAgents(MOCK_AGENTS);
      })
      .finally(() => setLoading(false));
  }, []);

  const stats = useMemo(() => computeRegistryStats(agents), [agents]);

  const allTags = useMemo(() => extractAllTags(agents), [agents]);

  const filteredAgents = useMemo(() => {
    let result = filterAgents(agents, { source: sourceTab, status: statusTab, tag: tagFilter }, searchQuery);
    if (sortBy === "name") {
      result = [...result].sort((a, b) => a.name.localeCompare(b.name));
    } else if (sortBy === "calls") {
      result = [...result].sort((a, b) => b.callCount - a.callCount);
    }
    return result;
  }, [agents, sourceTab, statusTab, tagFilter, sortBy, searchQuery]);

  const sourceCounts = useMemo(() => {
    return {
      all: agents.length,
      builtin: agents.filter((a) => a.source === "builtin").length,
      plugin: agents.filter((a) => a.source === "plugin").length,
      external: agents.filter((a) => a.source === "external").length,
    };
  }, [agents]);

  const statusCounts = useMemo(() => {
    return {
      all: agents.length,
      running: agents.filter((a) => a.status === "running").length,
      ready: agents.filter((a) => a.status === "ready").length,
      session: agents.filter((a) => a.status === "session").length,
      draft: agents.filter((a) => a.status === "draft").length,
      stopped: agents.filter((a) => a.status === "stopped").length,
    };
  }, [agents]);

  const metricsCards = [
    { label: "已注册 Agent", value: stats.total, color: "#4F46E5", bg: "#EEF2FF", icon: "agents" },
    { label: "活跃 Agent", value: stats.active, color: "#16A34A", bg: "#DCFCE7", icon: "active" },
    { label: "本月调用量", value: stats.totalCalls.toLocaleString(), color: "#2563EB", bg: "#DBEAFE", icon: "calls" },
    { label: "工具总数", value: stats.totalTools, color: "#D97706", bg: "#FEF3C7", icon: "tools" },
    { label: "平均调用", value: stats.avgCalls.toLocaleString(), color: "#7C3AED", bg: "#EDE9FE", icon: "avg" },
    { label: "护栏覆盖率", value: `${stats.guardrailCoverage}%`, color: "#0891B2", bg: "#ECFEFF", icon: "guard" },
  ];

  return (
    <PageChrome title="智能体目录" lede="平台全部智能体的浏览与发现。涵盖平台内创建、插件市场引入、外部 Adapter 接入三种来源。">
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {/* 标题 + 新建按钮 */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 600, color: "#111827", margin: 0 }}>智能体目录</h1>
            <p style={{ fontSize: 13, color: "#6B7280", margin: "4px 0 0", lineHeight: 1.5 }}>
              平台全部智能体的浏览与发现。涵盖平台内创建、插件市场引入、外部 Adapter 接入三种来源。
            </p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Link
              to="/s2/aip/agents/new"
              style={{
                padding: "8px 16px",
                fontSize: 13,
                fontWeight: 500,
                borderRadius: 8,
                background: "#4F46E5",
                color: "#fff",
                textDecoration: "none",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <span style={{ fontSize: 16, lineHeight: 1 }}>+</span> 新建智能体
            </Link>
          </div>
        </div>

        {/* 指标卡网格 */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(6, 1fr)",
            gap: 12,
          }}
        >
          {metricsCards.map((m, i) => (
            <div
              key={i}
              style={{
                borderRadius: 10,
                border: "1px solid #E5E7EB",
                background: "#fff",
                padding: 14,
                display: "flex",
                flexDirection: "column",
                gap: 4,
              }}
            >
              <div style={{ fontSize: 10, color: "#6B7280", fontWeight: 500 }}>{m.label}</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: m.color }}>{m.value}</div>
              <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 2 }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: m.color, display: "inline-block" }} />
                <span style={{ fontSize: 9, color: "#9CA3AF" }}>
                  {m.icon === "active" ? `${stats.total} 总计中` : m.icon === "guard" ? "HITL 覆盖" : ""}
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* 来源筛选 Tab */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          {SOURCE_TABS.map((tab) => {
            const active = sourceTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setSourceTab(tab.id)}
                style={{
                  padding: "6px 12px",
                  borderRadius: 8,
                  fontSize: 12,
                  fontWeight: 500,
                  border: `1px solid ${active ? "#4F46E5" : "#E5E7EB"}`,
                  background: active ? "#4F46E5" : "#fff",
                  color: active ? "#fff" : "#374151",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  transition: "all 0.15s",
                }}
              >
                {tab.dotColor && (
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: "50%",
                      background: tab.dotColor,
                      display: "inline-block",
                    }}
                  />
                )}
                {tab.label}
                <span style={{ fontSize: 10, opacity: 0.7 }}>
                  ({sourceCounts[tab.id]})
                </span>
              </button>
            );
          })}
        </div>

        {/* 状态筛选 Tab */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          {STATUS_TABS.map((tab) => {
            const active = statusTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setStatusTab(tab.id)}
                style={{
                  padding: "4px 10px",
                  borderRadius: 6,
                  fontSize: 11,
                  fontWeight: 500,
                  border: `1px solid ${active ? tab.color : "#E5E7EB"}`,
                  background: active ? `${tab.color}15` : "#fff",
                  color: active ? tab.color : "#6B7280",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  transition: "all 0.15s",
                }}
              >
                {tab.label}
                <span style={{ fontSize: 9, opacity: 0.7 }}>
                  ({statusCounts[tab.id as keyof typeof statusCounts]})
                </span>
              </button>
            );
          })}
          <div style={{ flex: 1 }} />
          {/* 标签筛选 */}
          <select
            value={tagFilter}
            onChange={(e) => setTagFilter(e.target.value)}
            style={{
              padding: "4px 10px",
              fontSize: 11,
              border: "1px solid #E5E7EB",
              borderRadius: 6,
              background: "#fff",
              color: "#374151",
              outline: "none",
              cursor: "pointer",
            }}
          >
            <option value="all">全部标签</option>
            {allTags.map((tag) => (
              <option key={tag} value={tag}>
                {tag}
              </option>
            ))}
          </select>
          {/* 搜索框 */}
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索智能体…"
            style={{
              padding: "6px 10px",
              fontSize: 12,
              border: "1px solid #E5E7EB",
              borderRadius: 8,
              width: 200,
              outline: "none",
            }}
          />
          {/* 排序 */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            style={{
              padding: "6px 10px",
              fontSize: 12,
              border: "1px solid #E5E7EB",
              borderRadius: 8,
              background: "#fff",
              color: "#374151",
              outline: "none",
              cursor: "pointer",
            }}
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        {/* loading 提示 */}
        {loading && (
          <div style={{ textAlign: "center", padding: "12px", color: "#9CA3AF", fontSize: 12 }}>
            加载中…
          </div>
        )}

        {/* 卡片网格 */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
            gap: 16,
          }}
        >
          {filteredAgents.map((agent) => {
            const ss = statusStyle(agent.status);
            const isExternal = agent.source === "external";
            return (
              <div
                key={agent.id}
                style={{
                  borderRadius: 12,
                  border: `1px solid ${isExternal ? "#FED7AA" : "#E5E7EB"}`,
                  background: isExternal ? "#FFF7ED" : "#fff",
                  padding: 16,
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                  transition: "all 0.2s",
                  cursor: "pointer",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = "#818CF8";
                  e.currentTarget.style.boxShadow = "0 4px 12px rgba(79,70,229,0.1)";
                  e.currentTarget.style.transform = "translateY(-1px)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = isExternal ? "#FED7AA" : "#E5E7EB";
                  e.currentTarget.style.boxShadow = "none";
                  e.currentTarget.style.transform = "translateY(0)";
                }}
              >
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <AgentIcon type={agent.iconType} bg={agent.iconBg} color={agent.iconColor} />
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 600, color: "#111827" }}>{agent.name}</div>
                      <div style={{ fontSize: 10, color: "#6B7280", marginTop: 2 }}>
                        {agent.category} · {agent.sourceLabel}
                      </div>
                    </div>
                  </div>
                  <span
                    style={{
                      padding: "2px 8px",
                      borderRadius: 4,
                      fontSize: 10,
                      fontWeight: 500,
                      background: ss.bg,
                      color: ss.color,
                      whiteSpace: "nowrap",
                    }}
                  >
                    {agent.statusLabel}
                  </span>
                </div>

                <p style={{ fontSize: 12, color: "#4B5563", margin: 0, lineHeight: 1.6 }}>{agent.description}</p>

                <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {agent.tags.map((tag, i) => {
                    const ts = tagStyle(tag.tone);
                    return (
                      <span
                        key={i}
                        style={{
                          padding: "2px 8px",
                          borderRadius: 4,
                          fontSize: 10,
                          background: ts.bg,
                          color: ts.color,
                          whiteSpace: "nowrap",
                        }}
                      >
                        {tag.label}
                      </span>
                    );
                  })}
                </div>

                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    paddingTop: 8,
                    borderTop: `1px solid ${isExternal ? "#FED7AA" : "#F3F4F6"}`,
                  }}
                >
                  <span style={{ fontSize: 10, color: "#9CA3AF" }}>
                    {agent.adapterInfo
                      ? `${agent.adapterInfo} · ${agent.callCount.toLocaleString()} 次调用`
                      : `${agent.toolCount} 工具 · ${agent.callCount.toLocaleString()} 次调用`}
                  </span>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <Link
                      to={agent.detailLink}
                      title="查看详情"
                      style={{ fontSize: 11, color: "#4F46E5", fontWeight: 500, textDecoration: "none" }}
                    >
                      详情
                    </Link>
                    <span style={{ color: "#E5E7EB" }}>|</span>
                    <Link
                      to={agent.detailLink}
                      title="编辑配置"
                      style={{ fontSize: 11, color: "#6B7280", textDecoration: "none" }}
                    >
                      编辑
                    </Link>
                    <span style={{ color: "#E5E7EB" }}>|</span>
                    <button
                      type="button"
                      title={agent.status === "running" ? "暂停" : "启动"}
                      style={{
                        fontSize: 11,
                        color: agent.status === "running" ? "#D97706" : "#16A34A",
                        background: "none",
                        border: "none",
                        cursor: "pointer",
                        padding: 0,
                        fontWeight: 500,
                      }}
                    >
                      {agent.status === "running" ? "暂停" : "启动"}
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {filteredAgents.length === 0 && (
          <div
            style={{
              textAlign: "center",
              padding: "48px 24px",
              color: "#9CA3AF",
              fontSize: 13,
            }}
          >
            暂无匹配的智能体
          </div>
        )}
      </div>
    </PageChrome>
  );
}
