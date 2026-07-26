import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { PageChrome } from "../../components/PageChrome";
import { apiPost } from "../../api/client";

type ShopRow = {
  id: string;
  name: string;
  coords: string;
  rating: number;
};

type ThinkingStep = {
  id: string;
  title: string;
  detail: string;
  tags: string[];
};

type ChatTab = {
  id: string;
  label: string;
  query: string;
  result?: AnalysisResult;
  loading?: boolean;
  error?: { code: string; message: string };
};

type AnalysisResult = {
  answer: string;
  route?: string;
  provider?: string;
  offline?: boolean;
  objects: ShopRow[];
  thinking: ThinkingStep[];
};

type ChatResponse = {
  answer?: string;
  route?: string;
  provider?: string;
  toolCalls?: Array<{
    toolId: string;
    ok: boolean;
    result?: { objects?: ShopRow[]; count?: number };
    error?: string;
  }>;
};

const DEFAULT_OBJECTS: ShopRow[] = [
  { id: "s1", name: "Walter and Sons", coords: "52.2134545,-0.9453956", rating: 5 },
  { id: "s2", name: "Kuhic, Murphy and Shan...", coords: "52.1809635,-1.0050892", rating: 4 },
  { id: "s3", name: "Hickle - Blick", coords: "52.1957506,-0.8179289", rating: 5 },
];

const DEFAULT_THINKING: ThinkingStep[] = [
  {
    id: "step1",
    title: "查找咖啡店",
    detail:
      "尝试 4 种不同的搜索，其中可见性为 显著 或 普通，状态为 认可、活跃 或 实验性",
    tags: ['"coffee" → 16 结果', '"shop" → 20 结果', '"cafe" → 16 结果', '"location" → 18 结果'],
  },
  {
    id: "step2",
    title: "分析查询结果",
    detail:
      "正在从 Object Set 中提取北安普顿 10 公里范围内的咖啡店数据，按评分排序。",
    tags: ["过滤半径: 10km", "排序: rating DESC", "结果: 3 条"],
  },
];

const SUGGESTIONS = ["销售趋势分析", "库存预警查询", "客户分群", "异常检测"];

export function AipAnalystPage() {
  const [input, setInput] = useState("");
  const [chatTabs, setChatTabs] = useState<ChatTab[]>([
    { id: "tab1", label: "北安普顿附近的咖啡店", query: "" },
  ]);
  const [activeTabId, setActiveTabId] = useState("tab1");
  const [thinkingOpen, setThinkingOpen] = useState<Record<string, boolean>>({});
  const scrollRef = useRef<HTMLDivElement>(null);

  const activeTab = chatTabs.find((t) => t.id === activeTabId) ?? chatTabs[0];

  // 自动滚动到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [activeTab.result, activeTab.loading]);

  function toggleThinking(id: string) {
    setThinkingOpen((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  function addTab() {
    const id = `tab${chatTabs.length + 1}`;
    setChatTabs((prev) => [...prev, { id, label: "新查询", query: "" }]);
    setActiveTabId(id);
  }

  async function callApi(tabId: string, query: string): Promise<void> {
    setChatTabs((prev) =>
      prev.map((t) =>
        t.id === tabId
          ? { ...t, loading: true, error: undefined, result: undefined }
          : t,
      ),
    );
    try {
      const res = await apiPost<ChatResponse>("/v1/aip/chat", {
        query,
        withTools: true,
        tools: ["query.objects"],
      });
      const answer = res.answer || "(空回复)";
      const objects =
        res.toolCalls?.find((tc) => tc.ok && tc.result?.objects)?.result
          ?.objects || [];
      const result: AnalysisResult = {
        answer,
        route: res.route,
        provider: res.provider,
        objects: objects.length > 0 ? objects : DEFAULT_OBJECTS,
        thinking: DEFAULT_THINKING,
      };
      setChatTabs((prev) =>
        prev.map((t) => (t.id === tabId ? { ...t, loading: false, result } : t)),
      );
    } catch (ex) {
      const err = ex as { code?: string; message?: string };
      const code = err.code || "UNKNOWN";
      if (code === "EVAL_GATE") {
        setChatTabs((prev) =>
          prev.map((t) =>
            t.id === tabId
              ? {
                  ...t,
                  loading: false,
                  error: {
                    code,
                    message: "Evals 未达标，AIP 分析师暂不可用",
                  },
                }
              : t,
          ),
        );
      } else {
        // LLM 不可用 → 降级到本地模拟数据，标注离线模式
        const result: AnalysisResult = {
          answer:
            "在北安普顿 10 公里范围内找到 3 家咖啡店。其中 **Walter and Sons** 和 **Hickle - Blick** 评分最高（5 星）。未发现明显的连锁品牌集中趋势，均为独立咖啡店。建议进一步分析消费偏好和客流数据。",
          objects: DEFAULT_OBJECTS,
          thinking: DEFAULT_THINKING,
          offline: true,
        };
        setChatTabs((prev) =>
          prev.map((t) => (t.id === tabId ? { ...t, loading: false, result } : t)),
        );
      }
    }
  }

  function askQuestion(e: FormEvent) {
    e.preventDefault();
    const q = input.trim();
    if (!q || activeTab.loading) return;
    setChatTabs((prev) =>
      prev.map((t) =>
        t.id === activeTabId ? { ...t, label: q.slice(0, 24), query: q } : t,
      ),
    );
    setInput("");
    void callApi(activeTabId, q);
  }

  function retry() {
    if (!activeTab.query) return;
    void callApi(activeTab.id, activeTab.query);
  }

  return (
    <PageChrome title="AIP 分析师" lede="AI 驱动的数据分析与洞察">
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          height: "calc(100vh - 140px)",
        }}
      >
        {/* Tab 导航 */}
        <div
          style={{
            borderBottom: "1px solid #E5E7EB",
            background: "#fff",
            padding: "0 16px",
            display: "flex",
            alignItems: "center",
            gap: 4,
            flexShrink: 0,
          }}
        >
          {chatTabs.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setActiveTabId(t.id)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "8px 12px",
                fontSize: 13,
                background: activeTabId === t.id ? "#F3F4F6" : "transparent",
                borderRadius: 8,
                border: "none",
                color: "#374151",
                cursor: "pointer",
              }}
            >
              <span>{t.label}</span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#9CA3AF" strokeWidth="1.5">
                <path d="M19 9l-7 7-7-7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          ))}
          <button
            type="button"
            onClick={addTab}
            title="新查询"
            style={{
              padding: 4,
              background: "none",
              border: "none",
              color: "#9CA3AF",
              cursor: "pointer",
              borderRadius: 4,
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M12 4v16m8-8H4" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        {/* 三栏内容区 */}
        <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
          {/* 中栏：聊天内容 */}
          <div
            ref={scrollRef}
            style={{
              flex: 1,
              overflowY: "auto",
              padding: 24,
              background: "#FAFAFA",
            }}
          >
            <div
              style={{
                maxWidth: "896px",
                margin: "0 auto",
                display: "flex",
                flexDirection: "column",
                gap: 24,
              }}
            >
              {!activeTab.result && !activeTab.loading && !activeTab.error ? (
                // 初始态
                <div style={{ textAlign: "center", padding: "60px 20px" }}>
                  <div
                    style={{
                      width: 64,
                      height: 64,
                      borderRadius: 16,
                      background: "linear-gradient(135deg, #6366F1, #8B5CF6)",
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      marginBottom: 16,
                    }}
                  >
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.5">
                      <circle cx="12" cy="12" r="10" />
                      <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2z" />
                    </svg>
                  </div>
                  <h2 style={{ fontSize: 18, fontWeight: 600, color: "#111827", margin: 0 }}>
                    AIP Analyst
                  </h2>
                  <p
                    style={{
                      fontSize: 13,
                      color: "#6B7280",
                      marginTop: 8,
                      margin: "8px 0 24px",
                    }}
                  >
                    AI 驱动的数据分析和洞察。输入自然语言问题，获取结构化分析结果。
                  </p>
                  <div
                    style={{
                      display: "flex",
                      flexWrap: "wrap",
                      gap: 8,
                      justifyContent: "center",
                      maxWidth: 480,
                      margin: "0 auto",
                    }}
                  >
                    {SUGGESTIONS.map((q) => (
                      <button
                        key={q}
                        type="button"
                        onClick={() => setInput(q)}
                        style={{
                          padding: "8px 14px",
                          fontSize: 12,
                          borderRadius: 8,
                          border: "1px solid #E5E7EB",
                          background: "#fff",
                          color: "#374151",
                          cursor: "pointer",
                        }}
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              ) : activeTab.error ? (
                // 错误态
                <div
                  style={{
                    background: "#FEF2F2",
                    border: "1px solid #FECACA",
                    borderRadius: 8,
                    padding: 16,
                    color: "#991B1B",
                    fontSize: 13,
                  }}
                >
                  <strong>⚠ {activeTab.error.code}</strong> · {activeTab.error.message}
                  {activeTab.error.code === "EVAL_GATE" && (
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
                      onClick={retry}
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
              ) : (
                // 结果态
                <>
                  {/* 用户查询气泡 */}
                  {activeTab.query && (
                    <div style={{ display: "flex", justifyContent: "flex-end" }}>
                      <div
                        style={{
                          background: "#F3F4F6",
                          borderRadius: 8,
                          padding: "10px 14px",
                          maxWidth: 480,
                        }}
                      >
                        <p
                          style={{
                            fontSize: 13,
                            color: "#374151",
                            margin: 0,
                            lineHeight: 1.5,
                          }}
                        >
                          {activeTab.query}
                        </p>
                      </div>
                    </div>
                  )}

                  {/* AI 回复 */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                    {/* Loading 占位 */}
                    {activeTab.loading && (
                      <div
                        style={{
                          border: "1px solid #E5E7EB",
                          borderRadius: 12,
                          padding: 16,
                          background:
                            "linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)",
                          color: "#fff",
                          display: "flex",
                          gap: 12,
                          alignItems: "center",
                        }}
                      >
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
                          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.5">
                            <circle cx="12" cy="12" r="10" />
                          </svg>
                        </div>
                        <div style={{ display: "flex", gap: 4 }}>
                          <span className="aip-analyst-dot" style={{ animationDelay: "0ms" }} />
                          <span className="aip-analyst-dot" style={{ animationDelay: "150ms" }} />
                          <span className="aip-analyst-dot" style={{ animationDelay: "300ms" }} />
                        </div>
                      </div>
                    )}

                    {activeTab.result && (
                      <>
                        {/* 思考过程卡 1 */}
                        {activeTab.result.thinking.map((step) => (
                          <div
                            key={step.id}
                            style={{
                              border: "1px solid #E5E7EB",
                              borderRadius: 8,
                              background: "#fff",
                              overflow: "hidden",
                            }}
                          >
                            <button
                              type="button"
                              onClick={() => toggleThinking(step.id)}
                              style={{
                                width: "100%",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "space-between",
                                padding: "10px 14px",
                                background: "#F9FAFB",
                                border: "none",
                                cursor: "pointer",
                              }}
                            >
                              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                <svg
                                  width="16"
                                  height="16"
                                  viewBox="0 0 24 24"
                                  fill="none"
                                  stroke="#9CA3AF"
                                  strokeWidth="1.5"
                                  style={{
                                    transform: thinkingOpen[step.id]
                                      ? "rotate(-90deg)"
                                      : "none",
                                    transition: "transform 0.15s",
                                  }}
                                >
                                  <path d="M19 9l-7 7-7-7" strokeLinecap="round" strokeLinejoin="round" />
                                </svg>
                                <span style={{ fontSize: 13, fontWeight: 500, color: "#374151" }}>
                                  显示思考过程
                                </span>
                              </div>
                              <span style={{ fontSize: 11, color: "#9CA3AF" }}>AIP Analyst</span>
                            </button>
                            {thinkingOpen[step.id] && (
                              <div style={{ padding: "16px 14px", borderTop: "1px solid #F3F4F6" }}>
                                <p
                                  style={{
                                    fontSize: 13,
                                    fontWeight: 500,
                                    color: "#111827",
                                    margin: "0 0 8px",
                                  }}
                                >
                                  {step.title}
                                </p>
                                <p
                                  style={{
                                    fontSize: 12,
                                    color: "#6B7280",
                                    margin: "0 0 12px",
                                    lineHeight: 1.5,
                                  }}
                                >
                                  {step.detail}
                                </p>
                                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                                  {step.tags.map((tag) => (
                                    <span
                                      key={tag}
                                      style={{
                                        padding: "4px 8px",
                                        background: "#F3F4F6",
                                        borderRadius: 4,
                                        fontSize: 11,
                                        color: "#6B7280",
                                      }}
                                    >
                                      {tag}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        ))}

                        {/* Object 卡片 */}
                        <div
                          style={{
                            border: "1px solid #E5E7EB",
                            borderRadius: 8,
                            background: "#fff",
                            padding: 12,
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
                              background: "#DBEAFE",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              flexShrink: 0,
                            }}
                          >
                            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="1.5">
                              <path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                          </div>
                          <div style={{ flex: 1 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="#F97316">
                                <path d="M18 1.5c.9 0 1.5.6 1.5 1.5v12c0 .9-.6 1.5-1.5 1.5h-12c-.9 0-1.5-.6-1.5-1.5V3c0-.9.6-1.5 1.5-1.5h12z" />
                              </svg>
                              <span style={{ fontSize: 14, fontWeight: 500, color: "#111827" }}>
                                咖啡店（示例）
                              </span>
                            </div>
                            <p style={{ fontSize: 12, color: "#6B7280", margin: "2px 0 0" }}>
                              1K 对象
                            </p>
                          </div>
                          <div style={{ display: "flex", gap: 4 }}>
                            <button
                              title="收藏"
                              style={{
                                padding: 6,
                                background: "none",
                                border: "none",
                                cursor: "pointer",
                                color: "#9CA3AF",
                                borderRadius: 4,
                              }}
                            >
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                <path d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" strokeLinecap="round" strokeLinejoin="round" />
                              </svg>
                            </button>
                            <button
                              title="通知"
                              style={{
                                padding: 6,
                                background: "none",
                                border: "none",
                                cursor: "pointer",
                                color: "#9CA3AF",
                                borderRadius: 4,
                              }}
                            >
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                <path d="M15 17h5l-1.4-1.4A2 2 0 0118 14.2V11a6 6 0 10-12 0v3.2c0 .5-.2 1-.6 1.4L4 17h5M10 20a2 2 0 002-2h-2a2 2 0 002 2z" strokeLinecap="round" strokeLinejoin="round" />
                              </svg>
                            </button>
                          </div>
                        </div>

                        {/* 结果表格 */}
                        <div
                          style={{
                            border: "1px solid #E5E7EB",
                            borderRadius: 8,
                            overflow: "hidden",
                            background: "#fff",
                          }}
                        >
                          <div
                            style={{
                              padding: "10px 14px",
                              background: "#F9FAFB",
                              borderBottom: "1px solid #E5E7EB",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between",
                            }}
                          >
                            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#9CA3AF" strokeWidth="1.5">
                                <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" strokeLinecap="round" strokeLinejoin="round" />
                              </svg>
                              <span style={{ fontSize: 13, fontWeight: 500, color: "#374151" }}>
                                Northampton 附近的商店
                              </span>
                            </div>
                            <div style={{ display: "flex", gap: 4 }}>
                              <button
                                title="分享"
                                style={{
                                  padding: 6,
                                  background: "none",
                                  border: "none",
                                  cursor: "pointer",
                                  color: "#9CA3AF",
                                  borderRadius: 4,
                                }}
                              >
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                  <path d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" strokeLinecap="round" strokeLinejoin="round" />
                                </svg>
                              </button>
                              <button
                                title="代码"
                                style={{
                                  padding: 6,
                                  background: "none",
                                  border: "none",
                                  cursor: "pointer",
                                  color: "#9CA3AF",
                                  borderRadius: 4,
                                }}
                              >
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                  <path d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" strokeLinecap="round" />
                                </svg>
                              </button>
                              <button
                                title="分支"
                                style={{
                                  padding: 6,
                                  background: "none",
                                  border: "none",
                                  cursor: "pointer",
                                  color: "#9CA3AF",
                                  borderRadius: 4,
                                }}
                              >
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                  <path d="M13 5l7 7-7 7M5 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" />
                                </svg>
                              </button>
                            </div>
                          </div>
                          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                            <thead>
                              <tr>
                                <th style={{ textAlign: "left", padding: "8px 14px", background: "#F9FAFB", borderBottom: "1px solid #E5E7EB", fontWeight: 500, color: "#6B7280", fontSize: 12 }}>名称</th>
                                <th style={{ textAlign: "left", padding: "8px 14px", background: "#F9FAFB", borderBottom: "1px solid #E5E7EB", fontWeight: 500, color: "#6B7280", fontSize: 12 }}>店铺坐标</th>
                                <th style={{ textAlign: "left", padding: "8px 14px", background: "#F9FAFB", borderBottom: "1px solid #E5E7EB", fontWeight: 500, color: "#6B7280", fontSize: 12, width: 48 }}></th>
                              </tr>
                            </thead>
                            <tbody>
                              {activeTab.result.objects.map((row) => (
                                <tr
                                  key={row.id}
                                  style={{ borderBottom: "1px solid #F3F4F6", transition: "background 0.15s" }}
                                  onMouseEnter={(e) => {
                                    (e.currentTarget as HTMLTableRowElement).style.background = "#F9FAFB";
                                  }}
                                  onMouseLeave={(e) => {
                                    (e.currentTarget as HTMLTableRowElement).style.background = "#fff";
                                  }}
                                >
                                  <td style={{ padding: "10px 14px", color: "#111827", fontWeight: 500 }}>{row.name}</td>
                                  <td style={{ padding: "10px 14px", color: "#6B7280", fontSize: 12, fontFamily: "monospace" }}>{row.coords}</td>
                                  <td style={{ padding: "10px 14px", color: "#9CA3AF" }}>{row.rating}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          <div
                            style={{
                              padding: "8px 14px",
                              background: "#F9FAFB",
                              borderTop: "1px solid #E5E7EB",
                              fontSize: 12,
                              color: "#6B7280",
                            }}
                          >
                            显示 {activeTab.result.objects.length} 条结果
                          </div>
                        </div>

                        {/* 地图可视化 */}
                        <div
                          style={{
                            border: "1px solid #E5E7EB",
                            borderRadius: 8,
                            overflow: "hidden",
                            background: "#fff",
                          }}
                        >
                          <div
                            style={{
                              padding: "8px 14px",
                              background: "#F9FAFB",
                              borderBottom: "1px solid #E5E7EB",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between",
                            }}
                          >
                            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
                              <span style={{ color: "#6B7280" }}>使用</span>
                              <span
                                style={{
                                  padding: "2px 8px",
                                  background: "#DBEAFE",
                                  color: "#1D4ED8",
                                  borderRadius: 4,
                                  fontSize: 11,
                                  fontWeight: 500,
                                }}
                              >
                                咖啡店（示例）
                              </span>
                            </div>
                            <select
                              style={{
                                fontSize: 11,
                                border: "1px solid #E5E7EB",
                                borderRadius: 4,
                                padding: "2px 8px",
                                color: "#6B7280",
                                background: "#fff",
                              }}
                              defaultValue="店铺坐标"
                            >
                              <option>店铺坐标</option>
                            </select>
                          </div>
                          <div
                            className="aip-analyst-map"
                            style={{
                              height: 300,
                              background:
                                "linear-gradient(135deg, #E0F2FE 0%, #F0FDF4 100%)",
                              position: "relative",
                              overflow: "hidden",
                            }}
                          >
                            {/* 蓝色 cluster */}
                            <div
                              className="aip-analyst-map-cluster"
                              style={{ left: "45%", top: "40%" }}
                            />
                            {/* 橙色 markers */}
                            <div className="aip-analyst-map-marker" style={{ left: "48%", top: "45%" }} />
                            <div className="aip-analyst-map-marker" style={{ left: "50%", top: "42%" }} />
                            <div className="aip-analyst-map-marker" style={{ left: "46%", top: "43%" }} />
                            <div className="aip-analyst-map-marker" style={{ left: "52%", top: "48%" }} />
                            <div className="aip-analyst-map-marker" style={{ left: "44%", top: "46%" }} />
                            {/* 城市标签 */}
                            <span className="aip-analyst-map-city" style={{ left: "47%", top: "50%", color: "#374151", fontWeight: 500 }}>Northampton</span>
                            <span className="aip-analyst-map-city" style={{ left: "20%", top: "30%", color: "#9CA3AF" }}>Birmingham</span>
                            <span className="aip-analyst-map-city" style={{ left: "35%", top: "45%", color: "#9CA3AF" }}>Coventry</span>
                            <span className="aip-analyst-map-city" style={{ left: "55%", top: "35%", color: "#9CA3AF" }}>Leicester</span>
                            <span className="aip-analyst-map-city" style={{ left: "65%", top: "55%", color: "#9CA3AF" }}>Cambridge</span>
                            {/* 底部版权 */}
                            <div
                              style={{
                                position: "absolute",
                                bottom: 8,
                                left: 8,
                                fontSize: 10,
                                color: "#9CA3AF",
                              }}
                            >
                              © Mapbox © OpenStreetMap
                            </div>
                            <div
                              style={{
                                position: "absolute",
                                bottom: 8,
                                right: 8,
                                fontSize: 10,
                                color: "#9CA3AF",
                              }}
                            >
                              50 km
                            </div>
                          </div>
                          <div
                            style={{
                              padding: "8px 14px",
                              background: "#F9FAFB",
                              borderTop: "1px solid #E5E7EB",
                              fontSize: 12,
                              color: "#6B7280",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between",
                            }}
                          >
                            <span>{activeTab.result.objects.length} 对象</span>
                            <button
                              type="button"
                              style={{
                                fontSize: 12,
                                color: "#4F46E5",
                                background: "none",
                                border: "none",
                                cursor: "pointer",
                                fontWeight: 500,
                              }}
                            >
                              展开 →
                            </button>
                          </div>
                        </div>

                        {/* 分析总结（增强保留） */}
                        <div
                          style={{
                            border: "1px solid #BFDBFE",
                            borderRadius: 8,
                            background: "#EFF6FF",
                            padding: 16,
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                            <svg
                              width="20"
                              height="20"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="#2563EB"
                              strokeWidth="1.5"
                              style={{ flexShrink: 0, marginTop: 2 }}
                            >
                              <circle cx="12" cy="12" r="10" />
                              <path d="M12 16v-4M12 8h.01" strokeLinecap="round" />
                            </svg>
                            <div style={{ flex: 1 }}>
                              <p style={{ fontSize: 13, fontWeight: 600, color: "#1E40AF", margin: "0 0 8px" }}>
                                分析总结
                                {activeTab.result.offline && (
                                  <span
                                    style={{
                                      marginLeft: 8,
                                      padding: "1px 6px",
                                      background: "#FEF3C7",
                                      color: "#92400E",
                                      borderRadius: 3,
                                      fontSize: 10,
                                      fontWeight: 500,
                                    }}
                                  >
                                    离线模式
                                  </span>
                                )}
                              </p>
                              <p
                                style={{
                                  fontSize: 13,
                                  color: "#374151",
                                  lineHeight: 1.6,
                                  margin: 0,
                                  whiteSpace: "pre-wrap",
                                }}
                              >
                                {activeTab.result.answer}
                              </p>
                              {(activeTab.result.route || activeTab.result.provider) && (
                                <div
                                  style={{
                                    marginTop: 8,
                                    paddingTop: 8,
                                    borderTop: "1px solid #BFDBFE",
                                    fontSize: 11,
                                    color: "#3B82F6",
                                    display: "flex",
                                    gap: 8,
                                    flexWrap: "wrap",
                                  }}
                                >
                                  {activeTab.result.route && <span>路线：{activeTab.result.route}</span>}
                                  {activeTab.result.provider && <span>· 供应商：{activeTab.result.provider}</span>}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>

          {/* 右栏：本体面板 */}
          <aside
            style={{
              width: 256,
              flexShrink: 0,
              borderLeft: "1px solid #E5E7EB",
              background: "#fff",
              overflow: "auto",
              padding: 16,
            }}
          >
            <h3 style={{ fontSize: 14, fontWeight: 600, color: "#111827", margin: 0 }}>本体</h3>
            <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 8 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: 8,
                  background: "#F9FAFB",
                  borderRadius: 8,
                }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="#F97316">
                  <path d="M18 1.5c.9 0 1.5.6 1.5 1.5v12c0 .9-.6 1.5-1.5 1.5h-12c-.9 0-1.5-.6-1.5-1.5V3c0-.9.6-1.5 1.5-1.5h12z" />
                </svg>
                <span style={{ fontSize: 12, color: "#374151" }}>咖啡店（示例）</span>
              </div>
            </div>
          </aside>
        </div>

        {/* 底部输入区 */}
        <div
          style={{
            borderTop: "1px solid #E5E7EB",
            background: "#fff",
            padding: 16,
            flexShrink: 0,
          }}
        >
          <div style={{ maxWidth: "896px", margin: "0 auto" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                marginBottom: 8,
                fontSize: 12,
                color: "#6B7280",
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <span>统计附近店铺</span>
            </div>
            <form onSubmit={askQuestion} style={{ position: "relative" }}>
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="提出问题..."
                disabled={activeTab.loading}
                className="aip-analyst-input"
                style={{
                  width: "100%",
                  border: "1px solid #E5E7EB",
                  borderRadius: 12,
                  padding: "12px 200px 12px 16px",
                  fontSize: 14,
                  outline: "none",
                  transition: "border-color 0.15s, box-shadow 0.15s",
                  opacity: activeTab.loading ? 0.6 : 1,
                }}
              />
              <div
                style={{
                  position: "absolute",
                  right: 8,
                  bottom: 8,
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                <button
                  type="button"
                  title="编辑"
                  style={{
                    padding: 6,
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    color: "#9CA3AF",
                    borderRadius: 4,
                  }}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
                <select
                  title="模型选择"
                  style={{
                    fontSize: 11,
                    border: "1px solid #E5E7EB",
                    borderRadius: 4,
                    padding: "4px 8px",
                    color: "#6B7280",
                    background: "#fff",
                  }}
                  defaultValue="GPT-5.5"
                >
                  <option>GPT-5.5</option>
                  <option>Claude 4</option>
                  <option>GLM-5.2</option>
                </select>
                <button
                  type="button"
                  title="语音输入"
                  style={{
                    padding: 6,
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    color: "#9CA3AF",
                    borderRadius: 4,
                  }}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
                <button
                  type="submit"
                  disabled={activeTab.loading || !input.trim()}
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 8,
                    background:
                      activeTab.loading || !input.trim() ? "#C7D2FE" : "#4F46E5",
                    color: "#fff",
                    border: "none",
                    cursor:
                      activeTab.loading || !input.trim() ? "not-allowed" : "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                    transition: "background 0.15s",
                  }}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M5 12h14M12 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </PageChrome>
  );
}
