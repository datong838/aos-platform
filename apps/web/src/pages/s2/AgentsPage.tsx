import { useMemo, useState } from "react";
import { PageChrome } from "../../components/PageChrome";
import { apiPost } from "../../api/client";
import { useJsonGet } from "./shared";
import { CreateAgentWizard } from "./CreateAgentWizard";
import {
  // 常量与类型
  MOCK_AGENTS,
  MOCK_MODELS,
  HITL_PULSE_ANIMATION_NAME,
  HITL_PULSE_STYLE_TEXT,
  SOURCE_FILTERS,
  SOURCE_LABELS,
  SOURCE_BADGE_STYLE,
  TOOL_KIND_LABEL,
  TOOL_KIND_STYLE,
  type AgentItem,
  type AgentSource,
  type AgentTool,
  type AgentStatus,
  type CatalogModel,
  type SourceFilter,
  // 纯函数
  filterAgents,
  statusLabel,
  statusStyle,
  toolStateLabel,
  toolStateStyle,
  isHitlPending,
  toggleTool,
  approveHitl,
  rejectHitl,
  countToolStates,
  extractPromptVars,
  renderPrompt,
  formatCalls,
  parseModelsPayload,
  resolveModelLabel,
  generateTrialReply,
} from "./agentsCore";

export { CreateAgentWizard };

// -------------------- 试运行消息类型 --------------------

interface TrialMessage {
  role: "user" | "assistant";
  content: string;
}

// -------------------- 主页面 --------------------

export function AgentsPage() {
  // 数据：Agent 列表（本地状态，支持新建后追加） + 模型目录
  const [agents, setAgents] = useState<AgentItem[]>(MOCK_AGENTS);
  const modelsApi = useJsonGet<{ items?: unknown[] } | unknown[]>("/v1/aip/models");
  const models: CatalogModel[] = useMemo(
    () => parseModelsPayload(modelsApi.data ?? MOCK_MODELS),
    [modelsApi.data],
  );

  const [selectedId, setSelectedId] = useState(MOCK_AGENTS[0].id);
  const [activeTab, setActiveTab] = useState<"prompt" | "tools" | "try" | "publish">("prompt");
  const [showWizard, setShowWizard] = useState(false);

  // 左侧列表状态
  const [keyword, setKeyword] = useState("");
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("all");

  // 试运行状态
  const [trialInput, setTrialInput] = useState("");
  const [trialMessages, setTrialMessages] = useState<TrialMessage[]>([]);

  // 发布历史
  const [publishHistory] = useState([
    { env: "prod", version: "v1.2.0", time: "2025-07-20 14:32", status: "已发布" },
    { env: "staging", version: "v1.3.0-rc1", time: "2025-07-25 09:15", status: "灰度中" },
    { env: "dev", version: "v1.3.0-dev", time: "2025-07-27 10:08", status: "构建中" },
  ]);

  const selected = agents.find((a) => a.id === selectedId) ?? agents[0];
  const filtered = filterAgents(agents, sourceFilter, keyword);
  const toolCounts = countToolStates(selected.tools);
  const promptVars = extractPromptVars(selected.prompt);

  function handleCreate(agent: AgentItem) {
    setAgents((prev) => [agent, ...prev]);
    setSelectedId(agent.id);
    setShowWizard(false);
  }

  function handleToggleTool(toolId: string) {
    setAgents((prev) =>
      prev.map((a) =>
        a.id === selected.id
          ? {
              ...a,
              tools: a.tools.map((t) => (t.id === toolId ? toggleTool(t) : t)),
            }
          : a,
      ),
    );
  }

  function handleApproveHitl(toolId: string) {
    setAgents((prev) =>
      prev.map((a) =>
        a.id === selected.id
          ? {
              ...a,
              tools: a.tools.map((t) =>
                t.id === toolId ? approveHitl(t) : t,
              ),
            }
          : a,
      ),
    );
  }

  function handleRejectHitl(toolId: string) {
    setAgents((prev) =>
      prev.map((a) =>
        a.id === selected.id
          ? {
              ...a,
              tools: a.tools.map((t) =>
                t.id === toolId ? rejectHitl(t) : t,
              ),
            }
          : a,
      ),
    );
  }

  async function handleSendTrial() {
    const text = trialInput.trim();
    if (!text) return;
    const userMsg: TrialMessage = { role: "user", content: text };
    const replyMsg: TrialMessage = {
      role: "assistant",
      content: generateTrialReply(selected, text),
    };
    setTrialMessages((prev) => [...prev, userMsg, replyMsg]);
    setTrialInput("");
    // 尝试调用后端 chat（失败静默，已有 mock 回复兜底）
    try {
      await apiPost("/v1/aip/agents/trial", {
        agentId: selected.id,
        message: text,
      });
    } catch {
      /* 后端未就绪时静默使用 mock 回复 */
    }
  }

  return (
    <PageChrome title="对话机器人" lede="4 步向导创建智能体 · 提示词变量插值 · 工具箱 HITL 确认 · 试运行">
      {/* 注入 HITL 脉冲动画 */}
      <style dangerouslySetInnerHTML={{ __html: HITL_PULSE_STYLE_TEXT }} />
      <div style={{ display: "flex", height: "calc(100vh - 120px)", minHeight: 0 }}>
        {/* ===== 左侧 Agent 列表 256px ===== */}
        <aside
          style={{
            width: 256,
            flexShrink: 0,
            borderRight: "1px solid var(--aos-border)",
            background: "var(--aos-surface)",
            overflow: "auto",
            display: "flex",
            flexDirection: "column",
          }}
        >
          {/* 搜索框 */}
          <div style={{ padding: 12, borderBottom: "1px solid var(--aos-gray-100)" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 500, color: "var(--aos-text)" }}>智能体列表</span>
              <span style={{ fontSize: 9, color: "var(--aos-text-tertiary)" }}>{agents.length} 个</span>
            </div>
            <input
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="搜索名称 / 描述…"
              style={{
                width: "100%",
                padding: "6px 10px",
                borderRadius: 2,
                border: "1px solid var(--aos-border)",
                fontSize: 11,
                outline: "none",
                boxSizing: "border-box",
                marginBottom: 8,
              }}
            />
            {/* 来源筛选 Tab */}
            <div style={{ display: "flex", gap: 4, marginBottom: 8 }}>
              {SOURCE_FILTERS.map((f) => {
                const sel = sourceFilter === f;
                const label =
                  f === "all" ? "全部" : SOURCE_LABELS[f as AgentSource];
                return (
                  <button
                    key={f}
                    onClick={() => setSourceFilter(f)}
                    style={{
                      flex: 1,
                      padding: "4px 0",
                      fontSize: 10,
                      fontWeight: sel ? 500 : 400,
                      color: sel ? "var(--aos-indigo-600)" : "var(--aos-text-secondary)",
                      background: sel ? "var(--aos-indigo-bg)" : "transparent",
                      border: sel ? "1px solid var(--aos-indigo-border)" : "1px solid transparent",
                      borderRadius: 2,
                      cursor: "pointer",
                    }}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
            <button
              onClick={() => setShowWizard(true)}
              style={{
                width: "100%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 6,
                padding: "8px 12px",
                borderRadius: 2,
                fontSize: 12,
                fontWeight: 500,
                color: "var(--text-on-brand)",
                background: "var(--aos-indigo-600)",
                border: "none",
                cursor: "pointer",
              }}
            >
              <span style={{ fontSize: 14, lineHeight: 1 }}>+</span>
              <span>新建智能体</span>
            </button>
          </div>

          {/* Agent 卡片列表 */}
          <div style={{ flex: 1, overflow: "auto" }}>
            {filtered.length === 0 && (
              <div style={{ padding: 24, textAlign: "center", fontSize: 11, color: "var(--aos-text-tertiary)" }}>
                未匹配到智能体
              </div>
            )}
            {filtered.map((a) => {
              const isSelected = a.id === selectedId;
              const sc = statusStyle(a.status);
              const ss = SOURCE_BADGE_STYLE[a.source];
              return (
                <div
                  key={a.id}
                  onClick={() => setSelectedId(a.id)}
                  style={{
                    padding: 12,
                    borderBottom: "1px solid var(--aos-surface-hover)",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 8,
                    background: isSelected ? "var(--aos-indigo-bg)" : "transparent",
                    borderLeft: isSelected ? "2px solid var(--aos-indigo-600)" : "2px solid transparent",
                  }}
                >
                  <div
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: 2,
                      background: "var(--aos-gray-100)",
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
                      {a.name}
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 3 }}>
                      {/* 来源标签 */}
                      <span
                        style={{
                          padding: "1px 6px",
                          borderRadius: 3,
                          fontSize: 9,
                          background: ss.bg,
                          color: ss.text,
                        }}
                      >
                        {SOURCE_LABELS[a.source]}
                      </span>
                      {/* 状态 */}
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
                    </div>
                    {/* 调用次数 */}
                    <div style={{ fontSize: 9, color: "var(--aos-text-tertiary)", marginTop: 3 }}>
                      调用 {formatCalls(a.calls)} 次 · {a.tools.length} 工具
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </aside>

        {/* ===== 右侧 4 Tab 详情面板 ===== */}
        <div style={{ flex: 1, overflow: "auto", minWidth: 0 }}>
          <div style={{ maxWidth: 768, margin: "0 auto", padding: 24 }}>
            {/* 标题行 */}
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 16 }}>
              <div>
                <h1 style={{ fontSize: 18, fontWeight: 600, color: "var(--aos-text)", margin: 0 }}>
                  {selected.icon} {selected.name}
                </h1>
                <p style={{ fontSize: 12, color: "var(--aos-text-secondary)", margin: "4px 0 0 0" }}>
                  {selected.description}
                </p>
                <div style={{ fontSize: 10, color: "var(--aos-text-tertiary)", marginTop: 4 }}>
                  模型：<span style={{ color: "var(--aos-text)", fontWeight: 500 }}>{resolveModelLabel(selected, models)}</span>
                  {" · "}累计调用 {formatCalls(selected.calls)} 次
                </div>
              </div>
            </div>

            {/* Tab 导航 */}
            <div style={{ borderBottom: "1px solid var(--aos-border)", display: "flex", gap: 24, marginBottom: 16 }}>
              {([
                { key: "prompt", label: "提示词", count: undefined },
                { key: "tools", label: "工具箱", count: selected.tools.length },
                { key: "try", label: "试运行", count: undefined },
                { key: "publish", label: "发布", count: undefined },
              ] as const).map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  style={{
                    padding: "10px 0",
                    fontSize: 12,
                    fontWeight: activeTab === tab.key ? 500 : 400,
                    color: activeTab === tab.key ? "var(--aos-indigo-600)" : "var(--aos-text-secondary)",
                    borderBottom:
                      activeTab === tab.key ? "2px solid var(--aos-indigo-600)" : "2px solid transparent",
                    background: "transparent",
                    cursor: "pointer",
                  }}
                >
                  {tab.label}
                  {tab.count != null && (
                    <span style={{ marginLeft: 4, fontSize: 10, color: "var(--aos-text-tertiary)" }}>
                      {tab.count}
                    </span>
                  )}
                </button>
              ))}
            </div>

            {/* ===== Tab 1: 提示词 ===== */}
            {activeTab === "prompt" && (
              <div style={cardStyle}>
                <label style={{ fontSize: 11, color: "var(--aos-text-secondary)" }}>系统提示词</label>
                <textarea
                  readOnly
                  value={selected.prompt}
                  style={{
                    width: "100%",
                    height: 128,
                    borderRadius: 2,
                    background: "var(--aos-bg)",
                    border: "1px solid var(--aos-border)",
                    padding: 12,
                    fontSize: 12,
                    color: "var(--aos-text)",
                    outline: "none",
                    resize: "none",
                    boxSizing: "border-box",
                    fontFamily: "monospace",
                    lineHeight: 1.5,
                  }}
                />
                {/* 变量预览 */}
                <div>
                  <div style={{ fontSize: 10, fontWeight: 500, color: "var(--aos-text)", marginBottom: 6 }}>
                    变量预览（$user / $context）
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {promptVars.length === 0 && (
                      <span style={{ fontSize: 10, color: "var(--aos-text-tertiary)" }}>本提示词未引用变量</span>
                    )}
                    {promptVars.map((v) => (
                      <span
                        key={v.raw}
                        style={{
                          padding: "4px 8px",
                          borderRadius: 4,
                          fontSize: 9,
                          background: v.scope === "user" ? "var(--aos-accent-light)" : "var(--aos-indigo-bg)",
                          color: v.scope === "user" ? "var(--aos-blue-600)" : "var(--aos-purple-600)",
                          border: `1px solid ${v.scope === "user" ? "var(--aos-accent-border)" : "var(--aos-indigo-border)"}`,
                        }}
                      >
                        {v.raw}
                      </span>
                    ))}
                  </div>
                </div>
                {/* 渲染预览 */}
                {promptVars.length > 0 && (
                  <div
                    style={{
                      padding: 10,
                      borderRadius: 2,
                      background: "var(--aos-surface-hover)",
                      border: "1px dashed var(--aos-border)",
                      fontSize: 10,
                      color: "var(--aos-text-secondary)",
                      fontFamily: "monospace",
                    }}
                  >
                    <div style={{ fontWeight: 500, marginBottom: 4, color: "var(--aos-text)" }}>
                      渲染示例（user.name=张三, context.wiki=WikiDoc）：
                    </div>
                    {renderPrompt(selected.prompt, {
                      user: { name: "张三", order: "ORD-123" },
                      context: { wiki: "WikiDoc", sla: "SLA-24h", risk: "RiskScanner", erp: "ErpBridge", brand: "BrandX" },
                    })}
                  </div>
                )}
              </div>
            )}

            {/* ===== Tab 2: 工具箱 ===== */}
            {activeTab === "tools" && (
              <div style={cardStyle}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span style={{ fontSize: 12, fontWeight: 500, color: "var(--aos-text)" }}>已启用工具</span>
                  <span style={{ fontSize: 10, color: "var(--aos-text-secondary)" }}>
                    已开 {toolCounts.on} · 推荐 {toolCounts.recommended} · 禁用 {toolCounts.disabled} ·
                    HITL 确认中 {toolCounts.hitl}
                  </span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {selected.tools.length === 0 && (
                    <div style={{ padding: 16, textAlign: "center", fontSize: 11, color: "var(--aos-text-tertiary)" }}>
                      该智能体暂未配置工具
                    </div>
                  )}
                  {selected.tools.map((t) => {
                    const ks = TOOL_KIND_STYLE[t.kind];
                    const ts = toolStateStyle(t.state);
                    const hitl = isHitlPending(t);
                    return (
                      <div
                        key={t.id}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          border: `1px solid ${hitl ? "var(--aos-amber-border)" : "var(--aos-border)"}`,
                          background: hitl ? "var(--aos-amber-bg)" : "var(--aos-surface)",
                          borderRadius: 2,
                          padding: "8px 12px",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          {/* 开关按钮 */}
                          <ToggleSwitch
                            state={t.state}
                            onToggle={() => handleToggleTool(t.id)}
                          />
                          <div>
                            <span style={{ fontSize: 12, color: "var(--aos-text)", fontWeight: 500 }}>
                              {t.name}
                            </span>
                            <div style={{ display: "flex", gap: 4, marginTop: 2 }}>
                              {/* kind 标签 */}
                              <span
                                style={{
                                  padding: "1px 6px",
                                  borderRadius: 3,
                                  fontSize: 9,
                                  background: ks.bg,
                                  color: ks.text,
                                }}
                              >
                                {TOOL_KIND_LABEL[t.kind]}
                              </span>
                              {/* 状态徽章（含 HITL 脉冲动画） */}
                              <span
                                className={hitl ? HITL_PULSE_ANIMATION_NAME : undefined}
                                style={{
                                  padding: "1px 6px",
                                  borderRadius: 3,
                                  fontSize: 9,
                                  background: ts.bg,
                                  color: ts.text,
                                  fontWeight: hitl ? 600 : 400,
                                }}
                              >
                                {toolStateLabel(t.state)}
                                {hitl && t.hitlCallId ? ` · ${t.hitlCallId}` : ""}
                              </span>
                            </div>
                          </div>
                        </div>
                        {/* HITL 确认按钮 */}
                        {hitl && (
                          <div style={{ display: "flex", gap: 4 }}>
                            <button
                              onClick={() => handleApproveHitl(t.id)}
                              style={{
                                padding: "3px 10px",
                                borderRadius: 2,
                                fontSize: 10,
                                fontWeight: 500,
                                color: "var(--text-on-brand)",
                                background: "var(--aos-green-600)",
                                border: "none",
                                cursor: "pointer",
                              }}
                            >
                              批准
                            </button>
                            <button
                              onClick={() => handleRejectHitl(t.id)}
                              style={{
                                padding: "3px 10px",
                                borderRadius: 2,
                                fontSize: 10,
                                fontWeight: 500,
                                color: "var(--aos-red)",
                                background: "var(--aos-surface)",
                                border: "1px solid var(--aos-red-border)",
                                cursor: "pointer",
                              }}
                            >
                              拒绝
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* ===== Tab 3: 试运行 ===== */}
            {activeTab === "try" && (
              <div style={{ ...cardStyle, padding: 0 }}>
                <div
                  style={{
                    padding: "10px 14px",
                    borderBottom: "1px solid var(--aos-gray-100)",
                    fontSize: 12,
                    fontWeight: 500,
                    color: "var(--aos-text)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <span>试运行 · {selected.name}</span>
                  {trialMessages.length > 0 && (
                    <button
                      onClick={() => setTrialMessages([])}
                      style={btnGhostSmall}
                    >
                      清空
                    </button>
                  )}
                </div>
                <div
                  style={{
                    height: 320,
                    overflow: "auto",
                    padding: 14,
                    display: "flex",
                    flexDirection: "column",
                    gap: 10,
                    background: "var(--aos-surface-hover)",
                  }}
                >
                  {trialMessages.length === 0 && (
                    <div style={{ margin: "auto", textAlign: "center", color: "var(--aos-text-tertiary)", fontSize: 11 }}>
                      发送一条消息开始测试 Agent
                    </div>
                  )}
                  {trialMessages.map((m, i) => (
                    <div
                      key={i}
                      style={{
                        alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                        maxWidth: "80%",
                        padding: "8px 12px",
                        borderRadius: 2,
                        fontSize: 12,
                        lineHeight: 1.5,
                        background:
                          m.role === "user" ? "var(--aos-indigo-600)" : "var(--aos-surface)",
                        color: m.role === "user" ? "var(--aos-surface)" : "var(--aos-text)",
                        border:
                          m.role === "assistant"
                            ? "1px solid var(--aos-border)"
                            : "none",
                      }}
                    >
                      {m.role === "assistant" && (
                        <div style={{ fontSize: 9, color: "var(--aos-text-secondary)", marginBottom: 2 }}>
                          {selected.name}
                        </div>
                      )}
                      {m.content}
                    </div>
                  ))}
                </div>
                <div
                  style={{
                    display: "flex",
                    gap: 8,
                    padding: "10px 14px",
                    borderTop: "1px solid var(--aos-gray-100)",
                  }}
                >
                  <input
                    value={trialInput}
                    onChange={(e) => setTrialInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSendTrial();
                      }
                    }}
                    placeholder={`向 ${selected.name} 发送消息…`}
                    style={{
                      flex: 1,
                      padding: "8px 12px",
                      borderRadius: 2,
                      border: "1px solid var(--aos-border)",
                      fontSize: 12,
                      outline: "none",
                    }}
                  />
                  <button onClick={handleSendTrial} style={btnPrimary}>
                    发送
                  </button>
                </div>
              </div>
            )}

            {/* ===== Tab 4: 发布 ===== */}
            {activeTab === "publish" && (
              <div style={cardStyle}>
                <h2 style={{ fontSize: 13, fontWeight: 500, color: "var(--aos-text)", margin: "0 0 12px 0" }}>
                  发布管理
                </h2>
                {/* 环境选择 */}
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 10, fontWeight: 500, color: "var(--aos-text)", marginBottom: 6 }}>
                    目标环境
                  </div>
                  <div style={{ display: "flex", gap: 6 }}>
                    {[
                      { env: "dev", label: "开发", color: "var(--aos-text-tertiary)" },
                      { env: "staging", label: "预发", color: "var(--aos-amber-600)" },
                      { env: "prod", label: "生产", color: "var(--aos-red)" },
                    ].map((e) => (
                      <span
                        key={e.env}
                        style={{
                          padding: "4px 12px",
                          borderRadius: 2,
                          fontSize: 10,
                          fontWeight: 500,
                          border: `1px solid ${e.color}40`,
                          color: e.color,
                          background: `${e.color}0A`,
                        }}
                      >
                        {e.label}
                      </span>
                    ))}
                  </div>
                </div>
                {/* 发布门控提示 */}
                {selected.status !== "active" && (
                  <div
                    style={{
                      padding: 10,
                      borderRadius: 2,
                      background: "var(--aos-amber-bg)",
                      border: "1px solid var(--aos-amber-border)",
                      fontSize: 10,
                      color: "var(--aos-amber-700)",
                      marginBottom: 12,
                    }}
                  >
                    ⚠ 当前状态为 {statusLabel(selected.status)}，发布前需通过 Evals 门控并切到 active。
                  </div>
                )}
                {/* 发布历史 */}
                <div>
                  <div style={{ fontSize: 10, fontWeight: 500, color: "var(--aos-text)", marginBottom: 6 }}>
                    发布历史
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    {publishHistory.map((h, i) => (
                      <div
                        key={i}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          padding: "8px 12px",
                          borderRadius: 2,
                          border: "1px solid var(--aos-border)",
                          fontSize: 11,
                        }}
                      >
                        <div>
                          <span style={{ color: "var(--aos-text)", fontWeight: 500 }}>{h.version}</span>
                          <span
                            style={{
                              marginLeft: 8,
                              padding: "1px 6px",
                              borderRadius: 3,
                              fontSize: 9,
                              background: "var(--aos-gray-100)",
                              color: "var(--aos-text-secondary)",
                            }}
                          >
                            {h.env}
                          </span>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span style={{ fontSize: 10, color: "var(--aos-text-tertiary)" }}>{h.time}</span>
                          <span
                            style={{
                              padding: "1px 6px",
                              borderRadius: 3,
                              fontSize: 9,
                              background:
                                h.status === "已发布"
                                  ? "var(--aos-green-bg)"
                                  : h.status === "灰度中"
                                    ? "var(--aos-amber-bg)"
                                    : "var(--aos-accent-light)",
                              color:
                                h.status === "已发布"
                                  ? "var(--aos-green-700)"
                                  : h.status === "灰度中"
                                    ? "var(--aos-amber-600)"
                                    : "var(--aos-blue-600)",
                            }}
                          >
                            {h.status}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 4 步创建向导 */}
      {showWizard && (
        <CreateAgentWizard
          models={models}
          onClose={() => setShowWizard(false)}
          onCreate={handleCreate}
        />
      )}
    </PageChrome>
  );
}

// -------------------- 内部组件：开关 --------------------

function ToggleSwitch({
  state,
  onToggle,
}: {
  state: AgentTool["state"];
  onToggle: () => void;
}) {
  const on = state === "on" || state === "recommended" || state === "hitl";
  let bg = "var(--aos-border)";
  if (state === "on") bg = "var(--aos-green-600)";
  else if (state === "recommended") bg = "var(--aos-amber-600)";
  else if (state === "hitl") bg = "var(--aos-amber)";
  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={state === "hitl"}
      aria-label={on ? "关闭工具" : "开启工具"}
      style={{
        width: 32,
        height: 18,
        borderRadius: 999,
        background: bg,
        border: "none",
        cursor: state === "hitl" ? "not-allowed" : "pointer",
        position: "relative",
        flexShrink: 0,
        opacity: state === "hitl" ? 0.85 : 1,
        transition: "background 0.2s",
      }}
    >
      <span
        style={{
          position: "absolute",
          top: 2,
          left: on ? 16 : 2,
          width: 14,
          height: 14,
          borderRadius: "50%",
          background: "var(--aos-surface)",
          boxShadow: "0 1px 2px rgba(0,0,0,0.2)",
          transition: "left 0.2s",
        }}
      />
    </button>
  );
}

// -------------------- 样式常量 --------------------

const cardStyle: React.CSSProperties = {
  borderRadius: 2,
  border: "1px solid var(--aos-border)",
  background: "var(--aos-surface)",
  padding: 20,
  display: "flex",
  flexDirection: "column",
  gap: 12,
};

const btnPrimary: React.CSSProperties = {
  padding: "6px 20px",
  fontSize: 12,
  fontWeight: 500,
  borderRadius: 2,
  border: "none",
  background: "var(--aos-indigo-600)",
  color: "var(--text-on-brand)",
  cursor: "pointer",
};

const btnGhostSmall: React.CSSProperties = {
  padding: "3px 10px",
  fontSize: 10,
  borderRadius: 2,
  border: "1px solid var(--aos-border)",
  background: "var(--aos-surface)",
  color: "var(--aos-text-secondary)",
  cursor: "pointer",
};

// 保留 AgentStatus 类型引用（用于将来扩展状态过滤）
export type { AgentStatus };
