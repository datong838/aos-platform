import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost } from "../api/client";
import { PageChrome } from "../components/PageChrome";

type AgentItem = {
  id: string;
  name: string;
  category: string;
  level: string;
  levelLabel: string;
  status: "running" | "draft" | "stopped";
  toolCount: number;
  iconBg: string;
  iconColor: string;
  iconPath: string;
};

const AGENTS: AgentItem[] = [
  {
    id: "repair-buddy",
    name: "维修派单 Buddy",
    category: "设备运维",
    level: "L2",
    levelLabel: "L2 HITL",
    status: "running",
    toolCount: 5,
    iconBg: "var(--aos-amber-bg)",
    iconColor: "var(--aos-amber-600)",
    iconPath:
      "M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z",
  },
  {
    id: "video-agent",
    name: "短视频生产 Agent",
    category: "内容创作",
    level: "L3",
    levelLabel: "L3 Capability",
    status: "running",
    toolCount: 4,
    iconBg: "var(--aos-accent-light)",
    iconColor: "var(--aos-blue-600)",
    iconPath: "",
  },
  {
    id: "risk-agent",
    name: "风险告警分析 Agent",
    category: "风控分析",
    level: "L1",
    levelLabel: "L1 Draft",
    status: "draft",
    toolCount: 6,
    iconBg: "var(--aos-red-bg)",
    iconColor: "var(--aos-red)",
    iconPath:
      "M12 9v4M12 17h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z",
  },
  {
    id: "order-agent",
    name: "订单客服 Agent",
    category: "电商客服",
    level: "L2",
    levelLabel: "L2 HITL",
    status: "running",
    toolCount: 3,
    iconBg: "var(--aos-green-bg)",
    iconColor: "var(--aos-green-600)",
    iconPath:
      "M21 11.5a8.5 8.5 0 01-8.5 8.5H5l-3 3V11.5A8.5 8.5 0 0110.5 3h2A8.5 8.5 0 0121 11.5z",
  },
  {
    id: "doc-agent",
    name: "文档问答 Agent",
    category: "知识检索",
    level: "L0",
    levelLabel: "L0 只读",
    status: "stopped",
    toolCount: 2,
    iconBg: "var(--aos-indigo-bg)",
    iconColor: "var(--aos-purple-600)",
    iconPath:
      "M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8",
  },
];

const STUDIO_TABS = [
  { id: "prompt", label: "提示词" },
  { id: "tools", label: "工具箱" },
  { id: "try", label: "试运行" },
  { id: "publish", label: "发布" },
];

const DEMO_TOOLS = [
  { id: "action.dispatch", name: "Action · 派单维修", code: "create_work_order", status: "HITL 确认", tone: "warn" },
  { id: "query.device", name: "Object Query · 设备对象", code: "Device", status: "已开启", tone: "ok" },
  { id: "function.health", name: "Function · health_score", code: "设备健康度计算", status: "已开启", tone: "ok" },
  { id: "wiki.fields", name: "Wiki 字段 Tool", code: "结构化优先", status: "★ 推荐", tone: "wiki" },
  { id: "clarify", name: "Request Clarification", code: "向用户澄清", status: "已开启", tone: "ok" },
];

function statusBadge(status: AgentItem["status"]) {
  if (status === "running") return { label: "运行中", bg: "var(--aos-green-bg)", color: "var(--aos-green-700)" };
  if (status === "draft") return { label: "Draft", bg: "var(--aos-amber-bg)", color: "var(--aos-amber-700)" };
  return { label: "已停用", bg: "var(--aos-gray-100)", color: "var(--aos-text-secondary)" };
}

export function StudioPage() {
  const [tab, setTab] = useState("prompt");
  const [activeId, setActiveId] = useState("repair-buddy");
  const selectedTools = ["query.objects"];
  const [systemPrompt, setSystemPrompt] = useState(
    "你是维修派单助手。优先读 Object 与 Wiki 结构化字段，禁止臆造字段。写回必须走 Action / Draft。",
  );
  const [defaultModel, setDefaultModel] = useState("—");
  const [lastRoute, setLastRoute] = useState<string | null>(null);
  const [query, setQuery] = useState("ORD-8821 超时了，怎么派？");
  const [answer, setAnswer] = useState("");
  const [toolCalls, setToolCalls] = useState<unknown[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const activeAgent = AGENTS.find((a) => a.id === activeId) || AGENTS[0];

  useEffect(() => {
    apiGet<{ defaultTextModel?: string }>("/v1/aip/models")
      .then((r) => setDefaultModel(r.defaultTextModel || "—"))
      .catch(() => setDefaultModel("—"));
  }, []);

  async function onChat(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      const res = await apiPost<{
        answer: string;
        toolCalls: unknown[];
        route?: string;
        provider?: string;
      }>("/v1/aip/chat", {
        query: `【System】${systemPrompt}\n\n【User】${query}`,
        withTools: selectedTools.length > 0,
        tools: selectedTools,
      });
      setAnswer(res.answer);
      setLastRoute(`${res.route || "?"} · ${res.provider || "?"}`);
      setToolCalls(res.toolCalls || []);
      setTab("try");
    } catch (ex) {
      setErr(String((ex as Error).message || ex));
    }
  }

  return (
    <PageChrome title="对话机器人 Studio" lede="配置壳：提示词 · 工具 · 本体/Wiki 上下文 · L4 须 Evals 绿 + Draft 默认">
      <div
        style={{
          margin: "-20px -20px -24px",
          display: "flex",
          minHeight: "calc(100vh - 140px)",
        }}
      >
        {/* 左侧：智能体列表 */}
        <div
          style={{
            width: 256,
            flexShrink: 0,
            borderRight: "1px solid var(--aos-border)",
            background: "var(--aos-surface)",
            overflowY: "auto",
          }}
        >
          <div
            style={{
              padding: 12,
              borderBottom: "1px solid var(--aos-gray-100)",
            }}
          >
            <div style={{ fontSize: 14, fontWeight: 500, color: "var(--aos-text)" }}>智能体列表</div>
            <button
              type="button"
              style={{
                marginTop: 8,
                width: "100%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 6,
                padding: "8px 12px",
                borderRadius: 8,
                background: "var(--aos-indigo-600)",
                color: "var(--text-on-brand)",
                border: "none",
                fontSize: 13,
                fontWeight: 500,
                cursor: "pointer",
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 5v14M5 12h14" strokeLinecap="round" />
              </svg>
              新建智能体
            </button>
          </div>

          {AGENTS.map((a) => {
            const active = a.id === activeId;
            const sb = statusBadge(a.status);
            return (
              <div
                key={a.id}
                onClick={() => setActiveId(a.id)}
                style={{
                  padding: 12,
                  borderBottom: "1px solid var(--aos-surface-hover)",
                  cursor: "pointer",
                  background: active ? "var(--aos-indigo-bg)" : "var(--aos-surface)",
                  borderLeft: active ? "2px solid var(--aos-indigo)" : "2px solid transparent",
                  transition: "background 0.15s",
                }}
              >
                <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
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
                    }}
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={a.iconColor} strokeWidth="1.5">
                      {a.id === "repair-buddy" && (
                        <path
                          d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      )}
                      {a.id === "video-agent" && (
                        <>
                          <rect x="3" y="5" width="18" height="14" rx="1" />
                          <path d="M3 10h18M9 10v9M15 10v9" />
                        </>
                      )}
                      {a.id === "risk-agent" && (
                        <>
                          <path d="M12 9v4M12 17h.01" strokeLinecap="round" />
                          <path
                            d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </>
                      )}
                      {a.id === "order-agent" && (
                        <path
                          d="M21 11.5a8.5 8.5 0 01-8.5 8.5H5l-3 3V11.5A8.5 8.5 0 0110.5 3h2A8.5 8.5 0 0121 11.5z"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      )}
                      {a.id === "doc-agent" && (
                        <>
                          <path
                            d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"
                            strokeLinejoin="round"
                          />
                          <path d="M14 2v6h6" strokeLinejoin="round" />
                          <path d="M16 13H8M16 17H8M10 9H8" strokeLinecap="round" />
                        </>
                      )}
                    </svg>
                  </div>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: 500,
                        color: "var(--aos-text)",
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      {a.name}
                    </div>
                    <div style={{ fontSize: 10, color: "var(--aos-text-secondary)", marginTop: 2 }}>
                      {a.category} · {a.levelLabel}
                    </div>
                    <div style={{ display: "flex", gap: 4, marginTop: 4 }}>
                      <span
                        style={{
                          padding: "1.5px 6px",
                          borderRadius: 4,
                          fontSize: 9,
                          background: sb.bg,
                          color: sb.color,
                          fontWeight: 500,
                        }}
                      >
                        {sb.label}
                      </span>
                      <span
                        style={{
                          padding: "1.5px 6px",
                          borderRadius: 4,
                          fontSize: 9,
                          background: "var(--aos-gray-100)",
                          color: "var(--aos-text-secondary)",
                        }}
                      >
                        {a.toolCount} 工具
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* 右侧：详情 */}
        <div style={{ flex: 1, overflowY: "auto", minWidth: 0 }}>
          <div style={{ maxWidth: 768, margin: "0 auto", padding: 24 }}>
            {/* Agent 标题 */}
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 16 }}>
              <div>
                <h1 style={{ fontSize: 20, fontWeight: 600, color: "var(--aos-text)", margin: 0 }}>
                  {activeAgent.name}
                </h1>
                <p style={{ fontSize: 13, color: "var(--aos-text-secondary)", margin: "4px 0 0", lineHeight: 1.5 }}>
                  配置壳：提示词 · 工具 · 本体/Wiki 上下文 · L4 须 Evals 绿 + Draft 默认
                </p>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span
                  style={{
                    padding: "2px 8px",
                    borderRadius: 4,
                    fontSize: 10,
                    background: "var(--aos-green-bg)",
                    color: "var(--aos-green-700)",
                    fontWeight: 500,
                  }}
                >
                  运行中
                </span>
                <span
                  style={{
                    padding: "2px 8px",
                    borderRadius: 4,
                    fontSize: 10,
                    background: "var(--aos-amber-bg)",
                    color: "var(--aos-amber-700)",
                    fontWeight: 500,
                  }}
                >
                  {activeAgent.levelLabel}
                </span>
              </div>
            </div>

            {/* Tab 导航 */}
            <div style={{ borderBottom: "1px solid var(--aos-border)", marginBottom: 16 }}>
              <div style={{ display: "flex", gap: 24 }}>
                {STUDIO_TABS.map((t) => {
                  const active = tab === t.id;
                  return (
                    <button
                      key={t.id}
                      type="button"
                      onClick={() => setTab(t.id)}
                      style={{
                        padding: "10px 0",
                        fontSize: 13,
                        fontWeight: active ? 500 : 400,
                        color: active ? "var(--aos-indigo-600)" : "var(--aos-text-secondary)",
                        background: "none",
                        border: "none",
                        borderBottom: active ? "2px solid var(--aos-indigo-600)" : "2px solid transparent",
                        cursor: "pointer",
                      }}
                    >
                      {t.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Tab: 提示词 */}
            {tab === "prompt" && (
              <div
                style={{
                  borderRadius: 12,
                  border: "1px solid var(--aos-border)",
                  background: "var(--aos-surface)",
                  padding: 20,
                }}
              >
                <label style={{ display: "block", fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 8, fontWeight: 500 }}>
                  系统提示词 (System Prompt) <span style={{ color: "var(--aos-red)" }}>*</span>
                </label>
                <textarea
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  rows={7}
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    fontSize: 13,
                    borderRadius: 8,
                    border: "1px solid var(--aos-border)",
                    background: "var(--aos-surface-hover)",
                    color: "var(--aos-text)",
                    resize: "vertical",
                    lineHeight: 1.6,
                    fontFamily: "inherit",
                    boxSizing: "border-box",
                  }}
                />
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
                  <span
                    style={{
                      padding: "3px 8px",
                      borderRadius: 4,
                      border: "1px solid var(--aos-purple-600)",
                      color: "var(--aos-purple-600)",
                      fontSize: 10,
                    }}
                  >
                    /Order.status
                  </span>
                  <span
                    style={{
                      padding: "3px 8px",
                      borderRadius: 4,
                      border: "1px solid var(--aos-amber-border)",
                      color: "var(--aos-amber-600)",
                      fontSize: 10,
                    }}
                  >
                    /Wiki.sla
                  </span>
                  <span
                    style={{
                      padding: "3px 8px",
                      borderRadius: 4,
                      border: "1px solid var(--aos-amber-border)",
                      color: "var(--aos-amber-700)",
                      fontSize: 10,
                    }}
                  >
                    模型路由 → {defaultModel}
                  </span>
                </div>
              </div>
            )}

            {/* Tab: 工具箱 */}
            {tab === "tools" && (
              <div
                style={{
                  borderRadius: 12,
                  border: "1px solid var(--aos-border)",
                  background: "var(--aos-surface)",
                  padding: 20,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: "var(--aos-text)" }}>已启用工具</div>
                  <span style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>共 {DEMO_TOOLS.length} 个工具</span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {DEMO_TOOLS.map((t) => {
                    const isWarn = t.tone === "warn";
                    const isWiki = t.tone === "wiki";
                    return (
                      <div
                        key={t.id}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          padding: "10px 12px",
                          borderRadius: 8,
                          border: `1px solid ${isWarn ? "var(--aos-amber-border)" : isWiki ? "var(--aos-amber-border)" : "var(--aos-border)"}`,
                          background: isWarn ? "var(--aos-amber-bg)" : isWiki ? "var(--aos-amber-bg)" : "var(--aos-surface)",
                        }}
                      >
                        <div>
                          <span style={{ fontSize: 13, color: "var(--aos-text)", fontWeight: 500 }}>{t.name}</span>
                          <span style={{ marginLeft: 8, fontSize: 10, color: isWarn ? "var(--aos-amber-700)" : "var(--aos-text-secondary)" }}>
                            {t.code}
                          </span>
                        </div>
                        <span
                          style={{
                            padding: "2px 8px",
                            borderRadius: 4,
                            fontSize: 11,
                            background: isWarn
                              ? "var(--aos-amber-bg)"
                              : isWiki
                                ? "var(--aos-amber-bg)"
                                : "var(--aos-green-bg)",
                            color: isWarn ? "var(--aos-amber-700)" : isWiki ? "var(--aos-amber-700)" : "var(--aos-green-700)",
                            fontWeight: 500,
                          }}
                        >
                          {t.status}
                        </span>
                      </div>
                    );
                  })}
                </div>
                <div style={{ paddingTop: 12, marginTop: 12, borderTop: "1px solid var(--aos-gray-100)" }}>
                  <Link
                    to="/aip/tools"
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      padding: "6px 12px",
                      borderRadius: 8,
                      background: "var(--aos-indigo-bg)",
                      color: "var(--aos-indigo-600)",
                      fontSize: 12,
                      fontWeight: 500,
                      textDecoration: "none",
                    }}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path
                        d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                    打开完整工具面板
                  </Link>
                </div>
                {err && <p style={{ color: "var(--aos-red)", fontSize: 12, marginTop: 12 }}>{err}</p>}
              </div>
            )}

            {/* Tab: 试运行 */}
            {tab === "try" && (
              <div
                style={{
                  borderRadius: 12,
                  border: "1px solid var(--aos-border)",
                  background: "var(--aos-surface)",
                  padding: 20,
                }}
              >
                <div
                  style={{
                    borderRadius: 8,
                    background: "var(--aos-surface-hover)",
                    border: "1px solid var(--aos-border)",
                    padding: 12,
                    fontSize: 13,
                    lineHeight: 1.6,
                  }}
                >
                  <div style={{ color: "var(--aos-blue-600)", fontSize: 11, fontWeight: 500, marginBottom: 4 }}>用户</div>
                  <div style={{ color: "var(--aos-text)" }}>{query}</div>
                  <div style={{ color: "var(--aos-amber-600)", fontSize: 11, fontWeight: 500, marginTop: 12, marginBottom: 4 }}>
                    Buddy
                  </div>
                  <div style={{ color: "var(--aos-text)" }}>
                    {answer || "已读 Order + Wiki.sla。建议 Action「派单维修」→ 进入 Draft（示意）。"}
                  </div>
                  {lastRoute && (
                    <div style={{ fontSize: 10, color: "var(--aos-text-tertiary)", marginTop: 8 }}>
                      路由：{lastRoute}
                    </div>
                  )}
                </div>
                <form
                  onSubmit={onChat}
                  style={{ display: "flex", gap: 8, marginTop: 12 }}
                >
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    style={{
                      flex: 1,
                      padding: "8px 12px",
                      fontSize: 13,
                      borderRadius: 8,
                      border: "1px solid var(--aos-border)",
                      background: "var(--aos-surface)",
                    }}
                    placeholder="输入测试问题…"
                  />
                  <button
                    type="submit"
                    style={{
                      padding: "8px 16px",
                      borderRadius: 8,
                      background: "var(--aos-indigo-600)",
                      color: "var(--text-on-brand)",
                      border: "none",
                      fontSize: 13,
                      fontWeight: 500,
                      cursor: "pointer",
                    }}
                  >
                    发送
                  </button>
                </form>
                {err && <p style={{ color: "var(--aos-red)", fontSize: 12, marginTop: 8 }}>{err}</p>}
                <Link
                  to="/aip/assist"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                    marginTop: 12,
                    fontSize: 12,
                    color: "var(--aos-blue-600)",
                    textDecoration: "none",
                  }}
                >
                  在工作台预览 Buddy 组件 →
                </Link>
                {toolCalls.length > 0 && (
                  <div style={{ marginTop: 16 }}>
                    <div style={{ fontSize: 12, fontWeight: 500, color: "var(--aos-text)", marginBottom: 8 }}>
                      工具调用
                    </div>
                    <table
                      style={{
                        width: "100%",
                        fontSize: 11,
                        borderCollapse: "collapse",
                        borderRadius: 6,
                        overflow: "hidden",
                        border: "1px solid var(--aos-border)",
                      }}
                    >
                      <thead>
                        <tr style={{ background: "var(--aos-surface-hover)", textAlign: "left" }}>
                          <th style={{ padding: "6px 10px", fontWeight: 500, color: "var(--aos-text-secondary)", fontSize: 10 }}>工具</th>
                          <th style={{ padding: "6px 10px", fontWeight: 500, color: "var(--aos-text-secondary)", fontSize: 10 }}>状态</th>
                          <th style={{ padding: "6px 10px", fontWeight: 500, color: "var(--aos-text-secondary)", fontSize: 10 }}>详情</th>
                        </tr>
                      </thead>
                      <tbody>
                        {toolCalls.map((tc, i) => {
                          const t = tc as Record<string, unknown>;
                          return (
                            <tr key={i} style={{ borderTop: "1px solid var(--aos-gray-100)" }}>
                              <td style={{ padding: "6px 10px", fontFamily: "monospace" }}>
                                {String(t.id || t.tool || `#${i + 1}`)}
                              </td>
                              <td style={{ padding: "6px 10px" }}>{String(t.status || "—")}</td>
                              <td style={{ padding: "6px 10px" }}>{String(t.summary || t.result || "—")}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* Tab: 发布 */}
            {tab === "publish" && (
              <div
                style={{
                  borderRadius: 12,
                  border: "1px solid var(--aos-amber-border)",
                  background: "var(--aos-amber-bg)",
                  padding: 20,
                }}
              >
                <h2 style={{ fontSize: 14, fontWeight: 600, color: "var(--aos-amber-700)", margin: "0 0 8px" }}>
                  L4 门控状态
                </h2>
                <p style={{ fontSize: 12, color: "var(--aos-amber-700)", margin: "0 0 12px", lineHeight: 1.6 }}>
                  须 Eval ≥ 92% 且 Draft 审批通过后方可申请 L4 上线。当前 Eval 通过率 87%，未达门槛。
                </p>
                <label
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    fontSize: 12,
                    color: "var(--aos-amber-700)",
                    opacity: 0.6,
                    cursor: "not-allowed",
                  }}
                >
                  <input type="checkbox" disabled style={{ width: 14, height: 14 }} />
                  启用无人值守写回（L4）
                </label>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 16 }}>
                  <Link
                    to="/aip/evals"
                    style={{
                      padding: "6px 12px",
                      borderRadius: 6,
                      background: "var(--aos-surface)",
                      border: "1px solid var(--aos-amber-border)",
                      color: "var(--aos-amber-700)",
                      fontSize: 12,
                      textDecoration: "none",
                      fontWeight: 500,
                    }}
                  >
                    去跑 Evals →
                  </Link>
                  <Link
                    to="/aip/drafts"
                    style={{
                      padding: "6px 12px",
                      borderRadius: 6,
                      background: "var(--aos-surface)",
                      border: "1px solid var(--aos-amber-border)",
                      color: "var(--aos-amber-700)",
                      fontSize: 12,
                      textDecoration: "none",
                      fontWeight: 500,
                    }}
                  >
                    Draft 审批台 →
                  </Link>
                  <Link
                    to="/aip/maturity"
                    style={{
                      padding: "6px 12px",
                      borderRadius: 6,
                      background: "var(--aos-surface)",
                      border: "1px solid var(--aos-amber-border)",
                      color: "var(--aos-amber-700)",
                      fontSize: 12,
                      textDecoration: "none",
                      fontWeight: 500,
                    }}
                  >
                    成熟度楼梯 →
                  </Link>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </PageChrome>
  );
}
