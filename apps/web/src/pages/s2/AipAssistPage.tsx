import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { PageChrome } from "../../components/PageChrome";
import { apiPost } from "../../api/client";

type Message =
  | {
      id: string;
      role: "user";
      content: string;
    }
  | {
      id: string;
      role: "ai";
      content: string;
      streaming?: boolean;
      route?: string;
      provider?: string;
      toolCalls?: Array<{ toolId: string; ok: boolean; error?: string }>;
      offline?: boolean;
    }
  | {
      id: string;
      role: "error";
      code: string;
      message: string;
    };

type ChatResponse = {
  answer?: string;
  route?: string;
  provider?: string;
  toolCalls?: Array<{ toolId: string; ok: boolean; error?: string }>;
};

const SUGGESTIONS = [
  "如何与协作者分享我的笔记本？",
  "如何在笔记本中嵌入其他应用的内容？",
  "如何创建 Object Set 并绑定到 Widget？",
  "如何配置 AIP Agent 的工具面板？",
];

const INITIAL_MESSAGES: Message[] = [
  {
    id: "init",
    role: "ai",
    content:
      "您好！我是 AIP Assist，一个基于 Palantir 产品文档和相关信息的智能助手。我可以帮助您了解如何使用平台功能。\n\n💡 提示：我也可以说其他语言！",
  },
];

export function AipAssistPage() {
  const [messages, setMessages] = useState<Message[]>(INITIAL_MESSAGES);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const typingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 自动滚动到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  // 清理打字机定时器
  useEffect(() => {
    return () => {
      if (typingTimerRef.current) clearInterval(typingTimerRef.current);
    };
  }, []);

  // 打字机效果：逐字显示 AI 回复
  function streamAnswer(
    msgId: string,
    fullText: string,
    extras?: Partial<Pick<Extract<Message, { role: "ai" }>, "route" | "provider" | "toolCalls" | "offline">>,
  ) {
    if (fullText.length === 0) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === msgId && m.role === "ai"
            ? { ...m, ...extras, streaming: false, content: "" }
            : m,
        ),
      );
      return;
    }
    let i = 0;
    if (typingTimerRef.current) clearInterval(typingTimerRef.current);
    typingTimerRef.current = setInterval(() => {
      i += 2; // 每帧 2 字符，节奏舒适
      if (i >= fullText.length) {
        if (typingTimerRef.current) clearInterval(typingTimerRef.current);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === msgId && m.role === "ai"
              ? { ...m, content: fullText, streaming: false, ...extras }
              : m,
          ),
        );
      } else {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === msgId && m.role === "ai"
              ? { ...m, content: fullText.slice(0, i), streaming: true }
              : m,
          ),
        );
      }
    }, 16);
  }

  async function callApi(query: string): Promise<void> {
    const msgId = `a_${Date.now()}`;
    // 占位 loading 气泡
    setMessages((prev) => [
      ...prev,
      { id: msgId, role: "ai", content: "", streaming: true },
    ]);
    try {
      const res = await apiPost<ChatResponse>("/v1/aip/chat", {
        query,
        withTools: false,
      });
      const answer = res.answer || "(空回复)";
      streamAnswer(msgId, answer, {
        route: res.route,
        provider: res.provider,
        toolCalls: res.toolCalls,
      });
    } catch (ex) {
      const err = ex as { code?: string; message?: string };
      const code = err.code || "UNKNOWN";
      // 错误气泡 + 关键词兜底降级
      if (code === "EVAL_GATE") {
        // 直接将占位 ai 气泡替换为 error 气泡
        setMessages((prev) => [
          ...prev.filter((m) => m.id !== msgId),
          {
            id: msgId,
            role: "error",
            code,
            message: "Evals 未达标，AIP 助手暂不可用",
          },
        ]);
      } else {
        // LLM 不可用 → 关键词兜底（标注离线模式）
        const fallback = generateOfflineResponse(query);
        streamAnswer(msgId, fallback, { offline: true });
      }
    }
  }

  function sendMessage(e: FormEvent) {
    e.preventDefault();
    const q = input.trim();
    if (!q || loading) return;
    const userMsg: Message = { id: `u_${Date.now()}`, role: "user", content: q };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    void callApi(q).finally(() => setLoading(false));
  }

  function useSuggestion(q: string) {
    if (loading) return;
    setInput(q);
  }

  function retryLast() {
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUser || lastUser.role !== "user") return;
    const q = lastUser.content;
    // 移除最后一个 error 气泡
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (last && last.role === "error") {
        return prev.slice(0, -1);
      }
      return prev;
    });
    setLoading(true);
    void callApi(q).finally(() => setLoading(false));
  }

  return (
    <PageChrome title="AIP 助手" lede="基于产品文档的智能助手">
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          height: "calc(100vh - 140px)",
          maxWidth: 720,
          margin: "0 auto",
        }}
      >
        {/* 顶部免责声明 */}
        <div style={{ textAlign: "center", marginBottom: 16 }}>
          <p
            style={{
              fontSize: 11,
              color: "#9CA3AF",
              fontStyle: "italic",
              maxWidth: 480,
              margin: "0 auto",
            }}
          >
            AIP Assist 使用第三方大语言模型（LLM）处理查询，符合 Palantir 安全标准。请根据组织政策使用。
          </p>
        </div>

        {/* 消息列表 */}
        <div
          ref={scrollRef}
          style={{
            flex: 1,
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            gap: 16,
            paddingRight: 4,
          }}
        >
          {messages.map((m) => {
            if (m.role === "error") {
              return (
                <div
                  key={m.id}
                  style={{
                    background: "#FEF2F2",
                    border: "1px solid #FECACA",
                    borderRadius: 12,
                    padding: 12,
                    color: "#991B1B",
                    fontSize: 13,
                  }}
                >
                  <strong>⚠ {m.code}</strong> · {m.message}
                  {m.code === "EVAL_GATE" && (
                    <div style={{ marginTop: 8 }}>
                      <Link
                        to="/aip/evals"
                        style={{
                          color: "#991B1B",
                          textDecoration: "underline",
                          fontSize: 12,
                        }}
                      >
                        查看 Evals 门控 →
                      </Link>
                    </div>
                  )}
                  <div style={{ marginTop: 8 }}>
                    <button
                      type="button"
                      onClick={retryLast}
                      style={{
                        fontSize: 12,
                        padding: "4px 10px",
                        borderRadius: 6,
                        border: "1px solid #FCA5A5",
                        background: "#fff",
                        color: "#991B1B",
                        cursor: "pointer",
                      }}
                    >
                      重试
                    </button>
                  </div>
                </div>
              );
            }
            if (m.role === "ai") {
              return (
                <div key={m.id}>
                  <div
                    style={{
                      borderRadius: 12,
                      padding: 16,
                      background:
                        "linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)",
                      color: "#fff",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
                      <div
                        style={{
                          width: 32,
                          height: 32,
                          borderRadius: 8,
                          background: "rgba(255,255,255,0.2)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                        }}
                      >
                        <svg
                          width="20"
                          height="20"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="#fff"
                          strokeWidth="1.5"
                        >
                          <circle cx="12" cy="12" r="10" />
                          <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2z" />
                        </svg>
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        {m.content === "" && m.streaming ? (
                          // Loading 三点动画
                          <div style={{ display: "flex", gap: 4, alignItems: "center", height: 22 }}>
                            <span className="aip-assist-dot" style={{ animationDelay: "0ms" }} />
                            <span className="aip-assist-dot" style={{ animationDelay: "150ms" }} />
                            <span className="aip-assist-dot" style={{ animationDelay: "300ms" }} />
                          </div>
                        ) : (
                          <p
                            style={{
                              fontSize: 13,
                              lineHeight: 1.6,
                              margin: 0,
                              whiteSpace: "pre-wrap",
                              wordBreak: "break-word",
                            }}
                          >
                            {m.content}
                            {m.streaming && <span className="aip-assist-cursor">▌</span>}
                          </p>
                        )}
                        {/* 路由信息 */}
                        {(m.route || m.provider) && !m.streaming && (
                          <div
                            style={{
                              marginTop: 8,
                              paddingTop: 8,
                              borderTop: "1px solid rgba(255,255,255,0.2)",
                              fontSize: 11,
                              color: "rgba(255,255,255,0.75)",
                              display: "flex",
                              gap: 8,
                              flexWrap: "wrap",
                            }}
                          >
                            {m.route && <span>路线：{m.route}</span>}
                            {m.provider && <span>· 供应商：{m.provider}</span>}
                            {m.offline && (
                              <span
                                style={{
                                  background: "rgba(245, 158, 11, 0.25)",
                                  padding: "1px 6px",
                                  borderRadius: 3,
                                }}
                              >
                                离线模式
                              </span>
                            )}
                          </div>
                        )}
                        {/* 工具调用结果 */}
                        {m.toolCalls && m.toolCalls.length > 0 && !m.streaming && (
                          <div
                            style={{
                              marginTop: 8,
                              padding: 8,
                              background: "rgba(255,255,255,0.1)",
                              borderRadius: 6,
                              fontSize: 11,
                            }}
                          >
                            <div style={{ opacity: 0.85, marginBottom: 4 }}>
                              工具调用 ({m.toolCalls.length})
                            </div>
                            {m.toolCalls.map((tc, i) => (
                              <div key={i} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                <span>{tc.ok ? "✅" : "❌"}</span>
                                <span style={{ fontFamily: "monospace" }}>{tc.toolId}</span>
                                {tc.error && (
                                  <span style={{ opacity: 0.7 }}>· {tc.error}</span>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            }
            // user 气泡
            return (
              <div
                key={m.id}
                style={{ display: "flex", justifyContent: "flex-end" }}
              >
                <div
                  style={{
                    background: "#F3F4F6",
                    borderRadius: 12,
                    padding: "10px 14px",
                    maxWidth: 480,
                    marginLeft: 48,
                  }}
                >
                  <p
                    style={{
                      fontSize: 13,
                      color: "#374151",
                      margin: 0,
                      lineHeight: 1.5,
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-word",
                    }}
                  >
                    {m.content}
                  </p>
                </div>
              </div>
            );
          })}

          {/* 建议问题（仅在初始状态显示） */}
          {messages.length === 1 && !loading && (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <p style={{ fontSize: 13, color: "#6B7280", margin: 0 }}>
                以下是您可以问我的几个问题...
              </p>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 8,
                }}
              >
                {SUGGESTIONS.map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => useSuggestion(q)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "12px 16px",
                      borderRadius: 8,
                      border: "1px solid #E5E7EB",
                      background: "#fff",
                      cursor: loading ? "not-allowed" : "pointer",
                      textAlign: "left",
                      fontSize: 13,
                      color: "#374151",
                      transition: "all 0.15s",
                    }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLButtonElement).style.background = "#F9FAFB";
                      (e.currentTarget as HTMLButtonElement).style.borderColor = "#D1D5DB";
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLButtonElement).style.background = "#fff";
                      (e.currentTarget as HTMLButtonElement).style.borderColor = "#E5E7EB";
                    }}
                  >
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="#9CA3AF"
                      strokeWidth="1.5"
                      style={{ flexShrink: 0 }}
                    >
                      <path
                        d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.86 9.86 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* 权限标签 */}
          <div
            style={{
              display: "flex",
              gap: 8,
              fontSize: 11,
              color: "#9CA3AF",
              marginTop: 8,
              flexWrap: "wrap",
            }}
          >
            <span
              style={{
                padding: "2px 8px",
                background: "#F3F4F6",
                borderRadius: 4,
              }}
            >
              当前应用：AIP Assist
            </span>
            <span
              style={{
                padding: "2px 8px",
                background: "#F3F4F6",
                borderRadius: 4,
              }}
            >
              权限感知：仅回答有权限的数据
            </span>
          </div>
        </div>

        {/* 底部输入区 */}
        <div
          style={{
            borderTop: "1px solid #E5E7EB",
            background: "#fff",
            padding: 16,
            marginTop: 8,
          }}
        >
          <div
            style={{
              fontSize: 11,
              color: "#9CA3AF",
              marginBottom: 8,
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            <span>建议问题</span>
            <button
              type="button"
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                color: "#9CA3AF",
                padding: 0,
              }}
              title="点击随机一条建议"
              onClick={() => {
                const random = SUGGESTIONS[Math.floor(Math.random() * SUGGESTIONS.length)];
                setInput(random);
              }}
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
              >
                <circle cx="12" cy="12" r="10" />
                <path
                  d="M9 9a3 3 0 115 2.9c0 1.1-.9 2.1-2 2.1H12M12 17h.01"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          </div>
          <form onSubmit={sendMessage} style={{ position: "relative" }}>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="提出问题..."
              disabled={loading}
              className="aip-assist-input"
              style={{
                width: "100%",
                border: "1px solid #E5E7EB",
                borderRadius: 12,
                padding: "12px 48px 12px 16px",
                fontSize: 14,
                outline: "none",
                transition: "border-color 0.15s, box-shadow 0.15s",
                opacity: loading ? 0.6 : 1,
              }}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              style={{
                position: "absolute",
                right: 8,
                bottom: 8,
                width: 32,
                height: 32,
                borderRadius: 8,
                background: loading ? "#C7D2FE" : "#4F46E5",
                color: "#fff",
                border: "none",
                cursor: loading || !input.trim() ? "not-allowed" : "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
                transition: "background 0.15s",
              }}
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path
                  d="M5 12h14M12 5l7 7-7 7"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          </form>
        </div>
      </div>
    </PageChrome>
  );
}

/**
 * 离线兜底：当 /v1/aip/chat 不可用时（无 LLM、网络错误、熔断），
 * 基于关键词给出可读回答，标注"离线模式"。
 * 这不是真实 AI，仅用于演示不空着报错。
 */
function generateOfflineResponse(query: string): string {
  if (query.includes("分享") && query.includes("笔记本")) {
    return "在 Foundry 中分享笔记本有两种方式：\n\n1. **直接分享**：在笔记本右上角点击「分享」按钮，输入协作者的用户名或邮箱，选择权限级别（查看/编辑/管理）。\n\n2. **通过项目分享**：将笔记本添加到一个项目中，然后将协作者添加到该项目，他们会自动获得项目中所有资源的访问权限。\n\n💡 建议：对于长期协作，推荐使用项目方式，便于权限统一管理。";
  }
  if (query.includes("嵌入") && query.includes("应用")) {
    return "在笔记本中嵌入其他应用内容：\n\n1. 使用 Embed 组件，在代码单元格中调用 display(Embed(url=...))\n2. 支持嵌入：Workshop 应用、Map 画布、Graph 画布、Object Explorer\n3. 嵌入内容支持双向交互（筛选、选中、Action）\n\n💡 注意：嵌入的应用需要有对应的访问权限。";
  }
  if (query.includes("Object Set") || query.includes("绑定")) {
    return "创建 Object Set 并绑定到 Widget 的流程：\n\n1. 在 Ontology Manager 中定义 Object Type\n2. 在 Workshop 中添加 Object Table Widget\n3. 在 Widget 配置面板的「Data」Tab 中选择 Object Set\n4. 可选：添加筛选器限制数据范围\n\n💡 Object Set 支持链式操作：filter、select、aggregate。";
  }
  if (query.includes("Agent") || query.includes("工具面板")) {
    return "配置 AIP Agent 工具面板：\n\n1. 在 AIP Studio 中创建或选择 Agent\n2. 进入「工具」Tab\n3. 添加可用工具：Query Object Set、Execute Action、Search Document、Call API\n4. 为每个工具配置参数和权限范围\n5. 设置工具使用策略：自动选择 vs 人工确认\n\n💡 安全提示：写操作工具建议启用 HITL（Human-in-the-loop）审批。";
  }
  return `您的问题是：「${query}」\n\n这是一个很好的问题。AIP Assist 基于产品文档和最佳实践来回答。如果您需要更详细的帮助，可以：\n\n1. 查看相关文档\n2. 联系平台管理员\n3. 在社区论坛提问\n\n💡 提示：尽量使用具体的关键词，我可以给出更精准的回答。`;
}
