import { useState } from "react";
import { PageChrome } from "../../components/PageChrome";

interface AgentItem {
  id: string;
  name: string;
  domain: string;
  level: string;
  levelLabel: string;
  status: "active" | "draft" | "stopped";
  toolCount: number;
  icon: string;
  iconBg: string;
  iconColor: string;
}

const AGENTS: AgentItem[] = [
  {
    id: "repair-buddy",
    name: "维修派单 Buddy",
    domain: "设备运维",
    level: "L2",
    levelLabel: "L2 HITL",
    status: "active",
    toolCount: 5,
    icon: "⚙",
    iconBg: "#FEF3C7",
    iconColor: "#D97706",
  },
  {
    id: "video-agent",
    name: "短视频生产 Agent",
    domain: "内容创作",
    level: "L3",
    levelLabel: "L3 Capability",
    status: "active",
    toolCount: 4,
    icon: "📊",
    iconBg: "#DBEAFE",
    iconColor: "#2563EB",
  },
  {
    id: "risk-agent",
    name: "风险告警分析 Agent",
    domain: "风控分析",
    level: "L1",
    levelLabel: "L1 Draft",
    status: "draft",
    toolCount: 6,
    icon: "⚠",
    iconBg: "#FEE2E2",
    iconColor: "#DC2626",
  },
  {
    id: "order-agent",
    name: "订单客服 Agent",
    domain: "电商客服",
    level: "L2",
    levelLabel: "L2 HITL",
    status: "active",
    toolCount: 3,
    icon: "💬",
    iconBg: "#DCFCE7",
    iconColor: "#16A34A",
  },
  {
    id: "doc-agent",
    name: "文档问答 Agent",
    domain: "知识检索",
    level: "L0",
    levelLabel: "L0 只读",
    status: "stopped",
    toolCount: 2,
    icon: "📄",
    iconBg: "#EDE9FE",
    iconColor: "#7C3AED",
  },
];

const TOOLS = [
  { name: "Action · 派单维修", code: "create_work_order", type: "action", badge: "HITL 确认", badgeType: "hitl" },
  { name: "Object Query · 设备对象", code: "Device", type: "query", badge: "已开启", badgeType: "on" },
  { name: "Function · health_score", code: "设备健康度计算", type: "function", badge: "已开启", badgeType: "on" },
  { name: "Wiki 字段 Tool", code: "结构化优先", type: "wiki", badge: "★ 推荐", badgeType: "rec" },
  { name: "Request Clarification", code: "向用户澄清", type: "clarify", badge: "已开启", badgeType: "on" },
];

export function AgentsPage() {
  const [selectedId, setSelectedId] = useState("repair-buddy");
  const [activeTab, setActiveTab] = useState("prompt");
  const [showWizard, setShowWizard] = useState(false);
  const [wizardStep, setWizardStep] = useState(1);

  const selected = AGENTS.find((a) => a.id === selectedId) || AGENTS[0];

  const statusLabel = (s: string) =>
    s === "active" ? "运行中" : s === "draft" ? "Draft" : "已停用";
  const statusColor = (s: string) =>
    s === "active"
      ? { bg: "#DCFCE7", text: "#15803D" }
      : s === "draft"
        ? { bg: "#FEF3C7", text: "#B45309" }
        : { bg: "#E5E7EB", text: "#6B7280" };

  const toolStyle = (t: typeof TOOLS[0]) => {
    if (t.badgeType === "hitl")
      return { border: "#FCD34D", bg: "#FFFBEB" };
    if (t.badgeType === "rec")
      return { border: "rgba(251, 146, 60, 0.3)", bg: "rgba(251, 146, 60, 0.05)" };
    return { border: "#E5E7EB", bg: "#fff" };
  };

  const badgeStyle = (type: string) => {
    if (type === "hitl")
      return { bg: "#FEF3C7", text: "#B45309" };
    if (type === "on")
      return { bg: "#DCFCE7", text: "#15803D" };
    if (type === "rec")
      return { bg: "#FFEDD5", text: "#EA580C" };
    return { bg: "#F3F4F6", text: "#6B7280" };
  };

  return (
    <PageChrome title="对话机器人" lede="配置壳：提示词 · 工具 · 本体/Wiki 上下文 · L4 须 Evals 绿 + Draft 默认">
      <div style={{ display: "flex", height: "calc(100vh - 120px)", minHeight: 0 }}>
        {/* 左侧：Agent 列表 */}
        <aside
          style={{
            width: 256,
            flexShrink: 0,
            borderRight: "1px solid var(--aos-border)",
            background: "#fff",
            overflow: "auto",
          }}
        >
          <div style={{ padding: 12, borderBottom: "1px solid #F3F4F6" }}>
            <span style={{ fontSize: 13, fontWeight: 500, color: "#111827" }}>智能体列表</span>
            <button
              onClick={() => {
                setShowWizard(true);
                setWizardStep(1);
              }}
              style={{
                marginTop: 8,
                width: "100%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 6,
                padding: "8px 12px",
                borderRadius: 8,
                fontSize: 12,
                fontWeight: 500,
                color: "#fff",
                background: "#4F46E5",
                border: "none",
                cursor: "pointer",
              }}
            >
              <span style={{ fontSize: 14, lineHeight: 1 }}>+</span>
              <span>新建智能体</span>
            </button>
          </div>

          {AGENTS.map((a) => {
            const isSelected = a.id === selectedId;
            const sc = statusColor(a.status);
            return (
              <div
                key={a.id}
                onClick={() => setSelectedId(a.id)}
                style={{
                  padding: 12,
                  borderBottom: "1px solid #F9FAFB",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 8,
                  background: isSelected ? "#EEF2FF" : "transparent",
                  borderLeft: isSelected ? "2px solid #6366F1" : "2px solid transparent",
                  transition: "background 0.15s",
                }}
              >
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 8,
                    background: a.iconBg,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                    fontSize: 14,
                  }}
                >
                  {a.icon}
                </div>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ fontSize: 12, fontWeight: 500, color: "#111827", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {a.name}
                  </div>
                  <div style={{ fontSize: 9, color: "#6B7280", marginTop: 2 }}>
                    {a.domain} · {a.levelLabel}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 4 }}>
                    <span
                      style={{
                        padding: "1px 6px",
                        borderRadius: 3,
                        fontSize: 9,
                        background: sc.bg,
                        color: sc.text,
                      }}
                    >
                      {statusLabel(a.status)}
                    </span>
                    <span
                      style={{
                        padding: "1px 6px",
                        borderRadius: 3,
                        fontSize: 9,
                        background: "#F3F4F6",
                        color: "#6B7280",
                      }}
                    >
                      {a.toolCount} 工具
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </aside>

        {/* 右侧：详情配置区 */}
        <div style={{ flex: 1, overflow: "auto", minWidth: 0 }}>
          <div style={{ maxWidth: 768, margin: "0 auto", padding: 24 }}>
            {/* 标题行 */}
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 16 }}>
              <div>
                <h1 style={{ fontSize: 18, fontWeight: 600, color: "#111827", margin: 0 }}>
                  {selected.name}
                </h1>
                <p style={{ fontSize: 12, color: "#6B7280", margin: "4px 0 0 0" }}>
                  配置壳：提示词 · 工具 · 本体/Wiki 上下文 · L4 须 Evals 绿 + Draft 默认
                </p>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <button
                  onClick={() => {
                    setShowWizard(true);
                    setWizardStep(1);
                  }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                    padding: "6px 12px",
                    borderRadius: 8,
                    fontSize: 12,
                    fontWeight: 500,
                    color: "#fff",
                    background: "#4F46E5",
                    border: "none",
                    cursor: "pointer",
                  }}
                >
                  <span style={{ fontSize: 12, lineHeight: 1 }}>+</span>
                  <span>新建智能体</span>
                </button>
                <span
                  style={{
                    padding: "4px 8px",
                    borderRadius: 4,
                    fontSize: 9,
                    fontWeight: 500,
                    ...statusColor(selected.status),
                  }}
                >
                  {statusLabel(selected.status)}
                </span>
                <span
                  style={{
                    padding: "4px 8px",
                    borderRadius: 4,
                    fontSize: 9,
                    fontWeight: 500,
                    background: "#FEF3C7",
                    color: "#B45309",
                  }}
                >
                  {selected.levelLabel}
                </span>
              </div>
            </div>

            {/* Tab 导航 */}
            <div style={{ borderBottom: "1px solid #E5E7EB", display: "flex", gap: 24, marginBottom: 16 }}>
              {[
                { key: "prompt", label: "提示词" },
                { key: "tools", label: "工具箱" },
                { key: "try", label: "试运行" },
                { key: "publish", label: "发布" },
              ].map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  style={{
                    padding: "10px 0",
                    fontSize: 12,
                    fontWeight: activeTab === tab.key ? 500 : 400,
                    color: activeTab === tab.key ? "#4F46E5" : "#6B7280",
                    borderBottom: activeTab === tab.key ? "2px solid #4F46E5" : "2px solid transparent",
                    background: "transparent",
                    cursor: "pointer",
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Tab: 提示词 */}
            {activeTab === "prompt" && (
              <div
                style={{
                  borderRadius: 12,
                  border: "1px solid #E5E7EB",
                  background: "#fff",
                  padding: 20,
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                }}
              >
                <label style={{ fontSize: 11, color: "#6B7280" }}>系统提示词</label>
                <textarea
                  readOnly
                  defaultValue="你是维修派单助手。优先读 Object 与 Wiki 结构化字段，禁止臆造字段。写回必须走 Action / Draft。"
                  style={{
                    width: "100%",
                    height: 128,
                    borderRadius: 8,
                    background: "#F0F2F5",
                    border: "1px solid #E5E7EB",
                    padding: 12,
                    fontSize: 12,
                    color: "#374151",
                    outline: "none",
                    resize: "none",
                    boxSizing: "border-box",
                    fontFamily: "inherit",
                    lineHeight: 1.5,
                  }}
                />
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  <span
                    style={{
                      padding: "4px 8px",
                      borderRadius: 4,
                      border: "1px solid #C4B5FD",
                      color: "#7C3AED",
                      fontSize: 9,
                    }}
                  >
                    /Order.status
                  </span>
                  <span
                    style={{
                      padding: "4px 8px",
                      borderRadius: 4,
                      border: "1px solid rgba(251, 146, 60, 0.4)",
                      color: "#EA580C",
                      fontSize: 9,
                    }}
                  >
                    /Wiki.sla
                  </span>
                  <span
                    style={{
                      padding: "4px 8px",
                      borderRadius: 4,
                      border: "1px solid #FCD34D",
                      color: "#B45309",
                      fontSize: 9,
                    }}
                  >
                    模型路由 → 模型路由
                  </span>
                </div>
              </div>
            )}

            {/* Tab: 工具箱 */}
            {activeTab === "tools" && (
              <div
                style={{
                  borderRadius: 12,
                  border: "1px solid #E5E7EB",
                  background: "#fff",
                  padding: 20,
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span style={{ fontSize: 12, fontWeight: 500, color: "#111827" }}>已启用工具</span>
                  <span style={{ fontSize: 10, color: "#6B7280" }}>共 5 个工具</span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {TOOLS.map((t, i) => {
                    const ts = toolStyle(t);
                    const bs = badgeStyle(t.badgeType);
                    return (
                      <div
                        key={i}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          border: `1px solid ${ts.border}`,
                          background: ts.bg,
                          borderRadius: 8,
                          padding: "8px 12px",
                        }}
                      >
                        <div>
                          <span style={{ fontSize: 12, color: "#111827", fontWeight: 500 }}>{t.name}</span>
                          <span style={{ marginLeft: 8, fontSize: 9, color: "#6B7280" }}>{t.code}</span>
                        </div>
                        <span
                          style={{
                            padding: "2px 8px",
                            borderRadius: 4,
                            fontSize: 9,
                            background: bs.bg,
                            color: bs.text,
                            fontWeight: t.badgeType === "hitl" || t.badgeType === "rec" ? 500 : 400,
                          }}
                        >
                          {t.badge}
                        </span>
                      </div>
                    );
                  })}
                </div>
                <div style={{ paddingTop: 12, borderTop: "1px solid #F3F4F6" }}>
                  <a
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 4,
                      padding: "6px 12px",
                      borderRadius: 8,
                      background: "#EEF2FF",
                      color: "#4F46E5",
                      fontSize: 10,
                      fontWeight: 500,
                      cursor: "pointer",
                    }}
                  >
                    <span>🔧</span>
                    打开完整工具面板
                  </a>
                </div>
              </div>
            )}

            {/* Tab: 试运行 */}
            {activeTab === "try" && (
              <div
                style={{
                  borderRadius: 12,
                  border: "1px solid #E5E7EB",
                  background: "#fff",
                  padding: 20,
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                }}
              >
                <div
                  style={{
                    borderRadius: 8,
                    background: "#F0F2F5",
                    border: "1px solid #E5E7EB",
                    padding: 12,
                    fontSize: 12,
                    display: "flex",
                    flexDirection: "column",
                    gap: 6,
                  }}
                >
                  <div style={{ color: "#2563EB", fontSize: 10, fontWeight: 500 }}>用户</div>
                  <div style={{ color: "#374151" }}>ORD-8821 超时了，怎么派？</div>
                  <div style={{ color: "#D97706", fontSize: 10, fontWeight: 500, marginTop: 8 }}>Buddy</div>
                  <div style={{ color: "#111827" }}>
                    已读 Order + Wiki.sla。建议 Action「派单维修」→ 进入 Draft（示意）。
                  </div>
                </div>
                <a
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                    fontSize: 10,
                    color: "#2563EB",
                    cursor: "pointer",
                  }}
                >
                  在工作台预览 Buddy 组件 →
                </a>
              </div>
            )}

            {/* Tab: 发布 */}
            {activeTab === "publish" && (
              <div
                style={{
                  borderRadius: 12,
                  border: "1px solid rgba(251, 113, 133, 0.3)",
                  background: "rgba(254, 242, 242, 0.5)",
                  padding: 20,
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                }}
              >
                <h2 style={{ fontSize: 13, fontWeight: 500, color: "#111827", margin: 0 }}>
                  L4 发布为 Function
                </h2>
                <label
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    fontSize: 12,
                    color: "#4B5563",
                    cursor: "not-allowed",
                  }}
                >
                  <input type="checkbox" disabled style={{ opacity: 0.5 }} />
                  启用无人值守写回
                </label>
                <p style={{ fontSize: 10, color: "#DC2626", margin: 0 }}>
                  未满足门控：Evals 须绿 · Draft 须默认暂存。当前不可勾选。
                </p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  <a
                    style={{
                      padding: "6px 12px",
                      borderRadius: 8,
                      border: "1px solid #FCD34D",
                      color: "#B45309",
                      fontSize: 10,
                      cursor: "pointer",
                    }}
                  >
                    去跑 Evals
                  </a>
                  <a
                    style={{
                      padding: "6px 12px",
                      borderRadius: 8,
                      border: "1px solid #E5E7EB",
                      color: "#6B7280",
                      fontSize: 10,
                      cursor: "pointer",
                    }}
                  >
                    成熟度楼梯
                  </a>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 新建智能体向导 */}
      {showWizard && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 50,
            background: "rgba(0, 0, 0, 0.4)",
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "center",
            padding: "24px 16px",
            overflow: "auto",
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowWizard(false);
          }}
        >
          <div
            style={{
              background: "#fff",
              borderRadius: 16,
              boxShadow: "0 25px 50px -12px rgba(0,0,0,0.25)",
              width: "100%",
              maxWidth: 768,
              maxHeight: "90vh",
              overflow: "auto",
            }}
          >
            {/* 向导头部 */}
            <div
              style={{
                position: "sticky",
                top: 0,
                zIndex: 1,
                background: "#fff",
                borderBottom: "1px solid #E5E7EB",
                padding: "16px 24px",
                borderRadius: "16px 16px 0 0",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div>
                  <h2 style={{ fontSize: 16, fontWeight: 600, color: "#111827", margin: 0 }}>新建智能体</h2>
                  <p style={{ fontSize: 10, color: "#6B7280", margin: "2px 0 0 0" }}>
                    通过四步配置创建一个新的 AI Agent
                  </p>
                </div>
                <button
                  onClick={() => setShowWizard(false)}
                  style={{
                    width: 32,
                    height: 32,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    borderRadius: 8,
                    color: "#9CA3AF",
                    background: "transparent",
                    border: "none",
                    cursor: "pointer",
                    fontSize: 16,
                  }}
                >
                  ×
                </button>
              </div>
              {/* 步进指示器 */}
              <div style={{ display: "flex", alignItems: "center", marginTop: 12 }}>
                {[1, 2, 3, 4].map((s, i) => {
                  const isActive = wizardStep === s;
                  const isDone = wizardStep > s;
                  const labels = ["基础信息", "能力配置", "安全等级", "确认创建"];
                  return (
                    <div key={s} style={{ display: "flex", alignItems: "center" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <div
                          style={{
                            width: 28,
                            height: 28,
                            borderRadius: "50%",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: 10,
                            fontWeight: 500,
                            background: isDone || isActive ? "#4F46E5" : "#E5E7EB",
                            color: isDone || isActive ? "#fff" : "#6B7280",
                          }}
                        >
                          {isDone ? "✓" : s}
                        </div>
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: isActive ? 500 : 400,
                            color: isActive ? "#4F46E5" : isDone ? "#4F46E5" : "#9CA3AF",
                          }}
                        >
                          {labels[i]}
                        </span>
                      </div>
                      {i < 3 && (
                        <div style={{ width: 48, height: 1, background: "#E5E7EB", margin: "0 8px" }} />
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 步骤内容 */}
            <div style={{ padding: "20px 24px" }}>
              {/* Step 1: 基础信息 */}
              {wizardStep === 1 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                  <div>
                    <h3 style={{ fontSize: 12, fontWeight: 600, color: "#111827", margin: "0 0 4px 0" }}>
                      第一步：填写智能体基础信息
                    </h3>
                    <p style={{ fontSize: 10, color: "#6B7280", margin: 0 }}>设定名称、图标、业务域和用途描述。</p>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <label style={{ fontSize: 10, fontWeight: 500, color: "#374151" }}>
                      智能体名称 <span style={{ color: "#EF4444" }}>*</span>
                    </label>
                    <input
                      placeholder="例：售后退换货 Buddy"
                      style={{
                        width: "100%",
                        padding: "6px 12px",
                        borderRadius: 8,
                        border: "1px solid #D1D5DB",
                        fontSize: 12,
                        outline: "none",
                        boxSizing: "border-box",
                        color: "#1F2937",
                      }}
                    />
                    <p style={{ fontSize: 9, color: "#9CA3AF", margin: 0 }}>3-20 个字符，在同一项目内唯一</p>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <label style={{ fontSize: 10, fontWeight: 500, color: "#374151" }}>
                      图标 <span style={{ color: "#EF4444" }}>*</span>
                    </label>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 8 }}>
                      {[
                        { icon: "💬", active: true, color: "#4F46E5" },
                        { icon: "⚙", active: false, color: "#6B7280" },
                        { icon: "⚠", active: false, color: "#6B7280" },
                        { icon: "📊", active: false, color: "#6B7280" },
                        { icon: "📄", active: false, color: "#6B7280" },
                        { icon: "📦", active: false, color: "#6B7280" },
                      ].map((ic, i) => (
                        <div
                          key={i}
                          style={{
                            width: 40,
                            height: 40,
                            borderRadius: 8,
                            background: ic.active ? "#EEF2FF" : "#F9FAFB",
                            border: `2px solid ${ic.active ? "#6366F1" : "#E5E7EB"}`,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            cursor: "pointer",
                            fontSize: 16,
                          }}
                        >
                          {ic.icon}
                        </div>
                      ))}
                    </div>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <label style={{ fontSize: 10, fontWeight: 500, color: "#374151" }}>
                      业务域 <span style={{ color: "#EF4444" }}>*</span>
                    </label>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                      {[
                        { label: "设备运维", active: true },
                        { label: "电商客服", active: false },
                        { label: "风控分析", active: false },
                        { label: "内容创作", active: false },
                        { label: "知识检索", active: false },
                        { label: "财务报销", active: false },
                      ].map((d, i) => (
                        <span
                          key={i}
                          style={{
                            padding: "4px 12px",
                            borderRadius: 999,
                            fontSize: 10,
                            fontWeight: d.active ? 500 : 400,
                            background: d.active ? "#EEF2FF" : "#fff",
                            color: d.active ? "#4F46E5" : "#4B5563",
                            border: `1px solid ${d.active ? "#C7D2FE" : "#E5E7EB"}`,
                            cursor: "pointer",
                          }}
                        >
                          {d.label}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <label style={{ fontSize: 10, fontWeight: 500, color: "#374151" }}>用途描述</label>
                    <textarea
                      placeholder="一句话说明这个智能体的职责和适用场景…"
                      rows={3}
                      style={{
                        width: "100%",
                        padding: "6px 12px",
                        borderRadius: 8,
                        border: "1px solid #D1D5DB",
                        fontSize: 12,
                        outline: "none",
                        resize: "none",
                        boxSizing: "border-box",
                        fontFamily: "inherit",
                        color: "#1F2937",
                      }}
                    />
                  </div>
                </div>
              )}

              {/* Step 2: 能力配置 */}
              {wizardStep === 2 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                  <div>
                    <h3 style={{ fontSize: 12, fontWeight: 600, color: "#111827", margin: "0 0 4px 0" }}>
                      第二步：配置智能体能力
                    </h3>
                    <p style={{ fontSize: 10, color: "#6B7280", margin: 0 }}>选择模型、编写系统提示词、勾选初始工具集。</p>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <label style={{ fontSize: 10, fontWeight: 500, color: "#374151" }}>
                      LLM 模型 <span style={{ color: "#EF4444" }}>*</span>
                    </label>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
                      {[
                        { name: "GLM-4-Plus", desc: "通用旗舰 · 128K 上下文", active: true },
                        { name: "GLM-4-Air", desc: "轻量高速 · 低延迟", active: false },
                        { name: "DeepSeek-V3", desc: "推理增强 · 开源", active: false },
                      ].map((m, i) => (
                        <div
                          key={i}
                          style={{
                            borderRadius: 8,
                            border: m.active ? "2px solid #6366F1" : "1px solid #E5E7EB",
                            background: m.active ? "#EEF2FF" : "#fff",
                            padding: "8px 10px",
                            cursor: "pointer",
                          }}
                        >
                          <div style={{ fontSize: 12, fontWeight: 500, color: "#111827" }}>{m.name}</div>
                          <div style={{ fontSize: 9, color: "#6B7280", marginTop: 2 }}>{m.desc}</div>
                        </div>
                      ))}
                    </div>
                    <a style={{ fontSize: 9, color: "#2563EB", cursor: "pointer", marginTop: 2 }}>
                      在模型目录中浏览全部 →
                    </a>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <label style={{ fontSize: 10, fontWeight: 500, color: "#374151" }}>
                      系统提示词 (System Prompt) <span style={{ color: "#EF4444" }}>*</span>
                    </label>
                    <textarea
                      placeholder="你是[智能体名称]。你的职责是…优先读 Object 与 Wiki 结构化字段，禁止臆造字段。写回操作必须走 Action / Draft 审批。"
                      rows={5}
                      style={{
                        width: "100%",
                        padding: "6px 12px",
                        borderRadius: 8,
                        border: "1px solid #D1D5DB",
                        fontSize: 12,
                        outline: "none",
                        resize: "none",
                        boxSizing: "border-box",
                        fontFamily: "inherit",
                        color: "#1F2937",
                      }}
                    />
                    <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 9, color: "#9CA3AF" }}>
                      <span>可用变量：/Order.status /Wiki.sla</span>
                      <span style={{ color: "#2563EB", cursor: "pointer" }}>AI 辅助生成提示词 →</span>
                    </div>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <label style={{ fontSize: 10, fontWeight: 500, color: "#374151" }}>
                      本体上下文（Agent 可访问的对象类型）
                    </label>
                    <div
                      style={{
                        borderRadius: 8,
                        border: "1px solid #E5E7EB",
                        background: "#F9FAFB",
                        padding: 10,
                        display: "flex",
                        flexDirection: "column",
                        gap: 6,
                      }}
                    >
                      {[
                        { name: "Order（订单）", desc: "工单编号、状态、SLA、负责人", checked: true },
                        { name: "Device（设备）", desc: "设备编号、位置、健康度、维保记录", checked: true },
                        { name: "WorkOrder（工单）", desc: "工单类型、优先级、处理人", checked: false },
                        { name: "KnowledgeDoc（知识文档）", desc: "Wiki 知识库关联文档", checked: false },
                      ].map((o, i) => (
                        <div key={i} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <input type="checkbox" defaultChecked={o.checked} style={{ accentColor: "#6366F1" }} />
                          <span style={{ fontSize: 10, color: "#374151" }}>{o.name}</span>
                          <span style={{ fontSize: 9, color: "#9CA3AF" }}>— {o.desc}</span>
                        </div>
                      ))}
                      <a style={{ fontSize: 9, color: "#2563EB", cursor: "pointer", marginTop: 2 }}>
                        在本体管理中查看全部对象类型 →
                      </a>
                    </div>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <label style={{ fontSize: 10, fontWeight: 500, color: "#374151" }}>
                        初始工具集（可后续在工具面板中调整）
                      </label>
                      <a style={{ fontSize: 9, color: "#2563EB", cursor: "pointer" }}>管理全部工具 →</a>
                    </div>
                    <div style={{ borderRadius: 8, border: "1px solid #E5E7EB", background: "#F9FAFB", overflow: "hidden" }}>
                      <div style={{ display: "flex", borderBottom: "1px solid #E5E7EB", background: "#fff" }}>
                        <button
                          style={{
                            flex: 1,
                            padding: "6px 0",
                            fontSize: 10,
                            fontWeight: 500,
                            color: "#4338CA",
                            borderBottom: "2px solid #6366F1",
                            background: "rgba(238, 242, 255, 0.5)",
                            cursor: "pointer",
                          }}
                        >
                          平台内置 <span style={{ color: "#9CA3AF", fontWeight: 400 }}>4 项</span>
                        </button>
                        <button
                          style={{
                            flex: 1,
                            padding: "6px 0",
                            fontSize: 10,
                            fontWeight: 400,
                            color: "#6B7280",
                            borderBottom: "2px solid transparent",
                            background: "transparent",
                            cursor: "pointer",
                          }}
                        >
                          外部工具扩展 <span style={{ color: "#9CA3AF" }}>6 项可用</span>
                        </button>
                      </div>
                      <div style={{ padding: 10, display: "flex", flexDirection: "column", gap: 6 }}>
                        {[
                          { name: "Object Query · 对象查询", desc: "读取本体数据的基础能力", checked: true },
                          { name: "Request Clarification · 澄清追问", desc: "向用户追问不明确的参数", checked: true },
                          { name: "Action · 动作执行", desc: "写回操作（需 HITL 审批）", checked: false },
                          { name: "Function · 函数调用", desc: "调用 AIP Logic 注册的函数", checked: false },
                        ].map((t, i) => (
                          <div
                            key={i}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between",
                            }}
                          >
                            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                              <input type="checkbox" defaultChecked={t.checked} style={{ accentColor: "#6366F1" }} />
                              <span style={{ fontSize: 10, color: "#374151", fontWeight: 500 }}>{t.name}</span>
                            </div>
                            <span style={{ fontSize: 9, color: "#9CA3AF" }}>{t.desc}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Step 3: 安全等级 */}
              {wizardStep === 3 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                  <div>
                    <h3 style={{ fontSize: 12, fontWeight: 600, color: "#111827", margin: "0 0 4px 0" }}>
                      第三步：设定安全等级与护栏
                    </h3>
                    <p style={{ fontSize: 10, color: "#6B7280", margin: 0 }}>
                      根据智能体的写回权限，选择成熟度等级。可后续通过「成熟度楼梯」升级。
                    </p>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <label style={{ fontSize: 10, fontWeight: 500, color: "#374151" }}>
                      成熟度等级 <span style={{ color: "#EF4444" }}>*</span>
                    </label>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      {[
                        { level: "L0", title: "只读问答", desc: "仅查询 Object/Wiki，不做任何写回。适合知识检索型 Agent。", color: "gray", checked: false },
                        { level: "L1", title: "Draft 暂存", desc: "写操作自动进入 Draft 审批台，人工审批后才生效。", color: "amber", checked: false },
                        { level: "L2", title: "HITL 人机协同", desc: "写操作执行前弹出确认窗口，人工一键批准。适合大多数业务场景。", color: "indigo", checked: true, recommended: true },
                        { level: "L3", title: "Capability 委托", desc: "通过 Capability 接入其他智能体执行写操作。需要被委托智能体已发布。", color: "blue", checked: false },
                        { level: "L4", title: "无人值守写回", desc: "全自动执行写回，无需人工确认。须 Evals 门控全绿方可启用。", color: "red", checked: false, risky: true },
                      ].map((l, i) => {
                        const levelBg =
                          l.color === "indigo"
                            ? "#EEF2FF"
                            : l.color === "amber"
                              ? "#FFFBEB"
                              : l.color === "blue"
                                ? "#EFF6FF"
                                : l.color === "red"
                                  ? "#FEF2F2"
                                  : "#F9FAFB";
                        const levelText =
                          l.color === "indigo"
                            ? "#4338CA"
                            : l.color === "amber"
                              ? "#B45309"
                              : l.color === "blue"
                                ? "#1D4ED8"
                                : l.color === "red"
                                  ? "#DC2626"
                                  : "#4B5563";
                        return (
                          <div
                            key={i}
                            style={{
                              display: "flex",
                              alignItems: "flex-start",
                              gap: 10,
                              borderRadius: 8,
                              border: l.checked
                                ? "2px solid #6366F1"
                                : l.risky
                                  ? "1px solid #FDA4AF"
                                  : "1px solid #E5E7EB",
                              background: l.checked ? levelBg : "#fff",
                              padding: "8px 10px",
                              cursor: "pointer",
                            }}
                          >
                            <input type="radio" name="level" defaultChecked={l.checked} style={{ marginTop: 2, accentColor: "#6366F1" }} />
                            <div style={{ flex: 1 }}>
                              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                <span
                                  style={{
                                    padding: "1px 6px",
                                    borderRadius: 3,
                                    fontSize: 9,
                                    fontWeight: 500,
                                    background: levelBg,
                                    color: levelText,
                                  }}
                                >
                                  {l.level}
                                </span>
                                <span style={{ fontSize: 11, fontWeight: 500, color: "#111827" }}>{l.title}</span>
                                {l.recommended && (
                                  <span
                                    style={{
                                      padding: "1px 6px",
                                      borderRadius: 3,
                                      fontSize: 9,
                                      background: "#4F46E5",
                                      color: "#fff",
                                    }}
                                  >
                                    推荐
                                  </span>
                                )}
                                {l.risky && (
                                  <span
                                    style={{
                                      padding: "1px 6px",
                                      borderRadius: 3,
                                      fontSize: 9,
                                      background: "#DC2626",
                                      color: "#fff",
                                    }}
                                  >
                                    高风险
                                  </span>
                                )}
                              </div>
                              <p
                                style={{
                                  fontSize: 9,
                                  color: l.risky ? "#DC2626" : "#6B7280",
                                  margin: "2px 0 0 0",
                                  lineHeight: 1.4,
                                }}
                              >
                                {l.desc}
                              </p>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <label style={{ fontSize: 10, fontWeight: 500, color: "#374151" }}>安全护栏</label>
                    <div
                      style={{
                        borderRadius: 8,
                        border: "1px solid #E5E7EB",
                        background: "#F9FAFB",
                        padding: 10,
                        display: "flex",
                        flexDirection: "column",
                        gap: 6,
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                        <span style={{ fontSize: 10, color: "#374151" }}>禁止臆造字段（强制结构化优先）</span>
                        <input type="checkbox" defaultChecked style={{ accentColor: "#6366F1" }} />
                      </div>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                        <span style={{ fontSize: 10, color: "#374151" }}>Token 上限（防超量调用）</span>
                        <span style={{ fontSize: 9, color: "#9CA3AF" }}>10,000 tokens/会话</span>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                        <span style={{ fontSize: 10, color: "#374151" }}>速率限制（防 DDoS）</span>
                        <span style={{ fontSize: 9, color: "#9CA3AF" }}>30 次/分钟</span>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                        <span style={{ fontSize: 10, color: "#374151" }}>创建后自动进入 Draft 审批台</span>
                        <input type="checkbox" defaultChecked style={{ accentColor: "#6366F1" }} />
                      </div>
                    </div>
                    <a style={{ fontSize: 9, color: "#2563EB", cursor: "pointer" }}>
                      在成熟度楼梯中查看详细等级说明 →
                    </a>
                  </div>
                </div>
              )}

              {/* Step 4: 确认创建 */}
              {wizardStep === 4 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  <div>
                    <h3 style={{ fontSize: 12, fontWeight: 600, color: "#111827", margin: "0 0 4px 0" }}>
                      第四步：确认配置并创建
                    </h3>
                    <p style={{ fontSize: 10, color: "#6B7280", margin: 0 }}>检查以下配置，创建后可在编辑器中进一步调整。</p>
                  </div>

                  <div style={{ borderRadius: 12, border: "1px solid #E5E7EB", background: "#F9FAFB", overflow: "hidden" }}>
                    <div
                      style={{
                        padding: "12px 16px",
                        background: "#fff",
                        borderBottom: "1px solid #E5E7EB",
                        display: "flex",
                        alignItems: "center",
                        gap: 12,
                      }}
                    >
                      <div
                        style={{
                          width: 40,
                          height: 40,
                          borderRadius: 8,
                          background: "#E0E7FF",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontSize: 18,
                        }}
                      >
                        💬
                      </div>
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 600, color: "#111827" }}>售后退换货 Buddy</div>
                        <div style={{ fontSize: 9, color: "#6B7280" }}>设备运维 · L2 HITL</div>
                      </div>
                      <span
                        style={{
                          marginLeft: "auto",
                          padding: "4px 8px",
                          borderRadius: 4,
                          fontSize: 9,
                          background: "#F3F4F6",
                          color: "#6B7280",
                        }}
                      >
                        Draft
                      </span>
                    </div>
                    <div style={{ padding: "12px 16px", display: "flex", flexDirection: "column", gap: 8, fontSize: 10 }}>
                      <div style={{ display: "flex" }}>
                        <span style={{ width: 72, color: "#9CA3AF", flexShrink: 0 }}>模型</span>
                        <span style={{ color: "#374151" }}>GLM-4-Plus（128K 上下文）</span>
                      </div>
                      <div style={{ display: "flex" }}>
                        <span style={{ width: 72, color: "#9CA3AF", flexShrink: 0 }}>提示词</span>
                        <span style={{ color: "#374151" }}>你是售后退换货助手。优先读 Order 与 Wiki 结构化字段…</span>
                      </div>
                      <div style={{ display: "flex" }}>
                        <span style={{ width: 72, color: "#9CA3AF", flexShrink: 0 }}>本体上下文</span>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                          <span style={{ padding: "1px 6px", borderRadius: 3, fontSize: 9, background: "#DBEAFE", color: "#1D4ED8" }}>Order</span>
                          <span style={{ padding: "1px 6px", borderRadius: 3, fontSize: 9, background: "#DBEAFE", color: "#1D4ED8" }}>Device</span>
                        </div>
                      </div>
                      <div style={{ display: "flex" }}>
                        <span style={{ width: 72, color: "#9CA3AF", flexShrink: 0 }}>初始工具</span>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                          <span style={{ padding: "1px 6px", borderRadius: 3, fontSize: 9, background: "#DCFCE7", color: "#15803D" }}>Object Query</span>
                          <span style={{ padding: "1px 6px", borderRadius: 3, fontSize: 9, background: "#DCFCE7", color: "#15803D" }}>Request Clarification</span>
                        </div>
                      </div>
                      <div style={{ display: "flex" }}>
                        <span style={{ width: 72, color: "#9CA3AF", flexShrink: 0 }}>安全等级</span>
                        <span
                          style={{
                            padding: "2px 8px",
                            borderRadius: 4,
                            fontSize: 9,
                            fontWeight: 500,
                            background: "#E0E7FF",
                            color: "#4338CA",
                          }}
                        >
                          L2 · HITL 人机协同
                        </span>
                      </div>
                      <div style={{ display: "flex" }}>
                        <span style={{ width: 72, color: "#9CA3AF", flexShrink: 0 }}>护栏</span>
                        <span style={{ color: "#374151" }}>禁止臆造 · 10K tokens · 30 次/分 · 自动入 Draft</span>
                      </div>
                    </div>
                  </div>

                  <div
                    style={{
                      borderRadius: 8,
                      background: "#FFFBEB",
                      border: "1px solid #FCD34D",
                      padding: "12px 14px",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                      <span style={{ color: "#D97706", flexShrink: 0, marginTop: 1 }}>⚠</span>
                      <div style={{ fontSize: 10, color: "#92400E" }}>
                        <p style={{ fontWeight: 500, margin: "0 0 4px 0" }}>创建后你需要：</p>
                        <ol
                          style={{
                            margin: 0,
                            paddingLeft: 16,
                            color: "#B45309",
                            fontSize: 9,
                            lineHeight: 1.6,
                          }}
                        >
                          <li>在「试运行」Tab 中验证 Agent 对话效果</li>
                          <li>通过 Evals 门控测试（至少通过率 ≥ 80%）</li>
                          <li>根据需要通过「成熟度楼梯」升级安全等级</li>
                          <li>在 Workshop 画布中将 Agent 组件拖入页面</li>
                        </ol>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* 底部操作栏 */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "12px 24px",
                borderTop: "1px solid #E5E7EB",
              }}
            >
              <button
                onClick={() => setWizardStep(Math.max(1, wizardStep - 1))}
                disabled={wizardStep === 1}
                style={{
                  padding: "6px 20px",
                  fontSize: 12,
                  borderRadius: 8,
                  border: "1px solid #D1D5DB",
                  background: "#fff",
                  color: wizardStep === 1 ? "#9CA3AF" : "#374151",
                  cursor: wizardStep === 1 ? "not-allowed" : "pointer",
                  visibility: wizardStep === 1 ? "hidden" : "visible",
                }}
              >
                上一步
              </button>
              <div style={{ display: "flex", gap: 6 }}>
                <button
                  onClick={() => setShowWizard(false)}
                  style={{
                    padding: "6px 20px",
                    fontSize: 12,
                    borderRadius: 8,
                    border: "1px solid #D1D5DB",
                    background: "#fff",
                    color: "#374151",
                    cursor: "pointer",
                  }}
                >
                  取消
                </button>
                {wizardStep < 4 ? (
                  <button
                    onClick={() => setWizardStep(wizardStep + 1)}
                    style={{
                      padding: "6px 20px",
                      fontSize: 12,
                      fontWeight: 500,
                      borderRadius: 8,
                      border: "none",
                      background: "#4F46E5",
                      color: "#fff",
                      cursor: "pointer",
                    }}
                  >
                    下一步
                  </button>
                ) : (
                  <button
                    onClick={() => setShowWizard(false)}
                    style={{
                      padding: "6px 20px",
                      fontSize: 12,
                      fontWeight: 500,
                      borderRadius: 8,
                      border: "none",
                      background: "#059669",
                      color: "#fff",
                      cursor: "pointer",
                    }}
                  >
                    创建智能体
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </PageChrome>
  );
}
