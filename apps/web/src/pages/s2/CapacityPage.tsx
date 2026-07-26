import { useState } from "react";
import { PageChrome } from "../../components/PageChrome";

type RateLimit = {
  model: string;
  provider: string;
  tokensPerMin: string;
  requestsPerMin: string;
};

const RATE_LIMITS: RateLimit[] = [
  { model: "GPT-5.4 Pro", provider: "OpenAI", tokensPerMin: "1.5M", requestsPerMin: "1K" },
  { model: "GPT-5.5", provider: "OpenAI", tokensPerMin: "7M", requestsPerMin: "3.5K" },
  { model: "GPT-5.4 mini", provider: "OpenAI", tokensPerMin: "7.5M", requestsPerMin: "3.8K" },
  { model: "Claude Opus 4.7", provider: "Anthropic", tokensPerMin: "8M", requestsPerMin: "900" },
  { model: "Claude Sonnet 4.6", provider: "Anthropic", tokensPerMin: "7M", requestsPerMin: "2.5K" },
  { model: "Claude Haiku 4.5", provider: "Anthropic", tokensPerMin: "6M", requestsPerMin: "2.5K" },
  { model: "Grok 4.3", provider: "xAI", tokensPerMin: "1M", requestsPerMin: "200" },
  { model: "Llama 4 Maverick 17B", provider: "Meta", tokensPerMin: "300K", requestsPerMin: "450" },
  { model: "text-embedding-ada-002", provider: "OpenAI", tokensPerMin: "4.2M", requestsPerMin: "4.2K" },
  { model: "Text Embedding 3 Large", provider: "OpenAI", tokensPerMin: "2M", requestsPerMin: "4K" },
];

type TabId = "usage" | "rate-limits" | "reserved";

export function CapacityPage() {
  const [tab, setTab] = useState<TabId>("rate-limits");

  return (
    <PageChrome title="容量管理" lede="管理 LLM 使用限制、速率限制和预留容量">
      <div style={{ maxWidth: "960px", margin: "0 auto" }}>
        {/* Tab 导航 */}
        <div style={{ borderBottom: "1px solid #E5E7EB", background: "#fff", marginBottom: 16 }}>
          <div style={{ display: "flex", gap: 8 }}>
            {([
              { id: "usage", label: "查看使用量" },
              { id: "rate-limits", label: "管理速率限制" },
              { id: "reserved", label: "预留容量" },
            ] as const).map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                style={{
                  padding: "12px 16px",
                  fontSize: 13,
                  fontWeight: tab === t.id ? 500 : 400,
                  borderBottom: tab === t.id ? "2px solid #4F46E5" : "2px solid transparent",
                  color: tab === t.id ? "#4F46E5" : "#6B7280",
                  background: "none",
                  border: "none",
                  borderTop: "none",
                  borderLeft: "none",
                  borderRight: "none",
                  cursor: "pointer",
                }}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* 信息横幅 */}
        <div style={{ background: "#EFF6FF", border: "1px solid #BFDBFE", borderRadius: 8, padding: 16, marginBottom: 24 }}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#3B82F6" strokeWidth="1.5" style={{ flexShrink: 0, marginTop: 2 }}>
              <circle cx="12" cy="12" r="10" /><path d="M12 16v-4M12 8h.01" strokeLinecap="round" />
            </svg>
            <p style={{ fontSize: 13, color: "#1E40AF", margin: 0, lineHeight: 1.6 }}>
              所有容量的 <span style={{ fontWeight: 600 }}>20%</span> 始终保留用于实时交互式 AIP 使用。如需额外容量，请联系 Palantir 支持。
              <a href="#" style={{ textDecoration: "underline", marginLeft: 4 }}>了解更多</a>
            </p>
          </div>
        </div>

        {tab === "rate-limits" && (
          <>
            {/* 速率限制卡片 */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
              <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 8, padding: 20 }}>
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <div style={{ width: 40, height: 40, borderRadius: 8, background: "#F3F4F6", display: "flex", alignItems: "center", justifyContent: "center" }}>
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#4B5563" strokeWidth="1.5"><path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" strokeLinecap="round" strokeLinejoin="round" /></svg>
                    </div>
                    <div>
                      <h3 style={{ fontSize: 14, fontWeight: 600, color: "#111827", margin: 0 }}>项目速率限制</h3>
                      <p style={{ fontSize: 12, color: "#6B7280", marginTop: 4, margin: "4px 0 0", lineHeight: 1.5 }}>管理所有项目范围的 LLM 使用限制，包括 AIP Agents、AIP Logic、Pipeline Builder 等应用。</p>
                    </div>
                  </div>
                </div>
                <div style={{ marginTop: 16 }}>
                  <button style={{ display: "inline-flex", alignItems: "center", fontSize: 13, fontWeight: 500, color: "#4F46E5", background: "none", border: "none", cursor: "pointer" }}>
                    管理
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ marginLeft: 4 }}><path d="M9 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" /></svg>
                  </button>
                </div>
              </div>

              <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 8, padding: 20 }}>
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <div style={{ width: 40, height: 40, borderRadius: 8, background: "#F3F4F6", display: "flex", alignItems: "center", justifyContent: "center" }}>
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#4B5563" strokeWidth="1.5"><circle cx="12" cy="8" r="4" /><path d="M4 20c0-4 4-6 8-6s8 2 8 6" strokeLinecap="round" /></svg>
                    </div>
                    <div>
                      <h3 style={{ fontSize: 14, fontWeight: 600, color: "#111827", margin: 0 }}>用户速率限制</h3>
                      <p style={{ fontSize: 12, color: "#6B7280", marginTop: 4, margin: "4px 0 0", lineHeight: 1.5 }}>管理所有用户范围的 LLM 使用限制，包括 AIP/IDE、AIP Analyst、Claude Code 等应用。</p>
                    </div>
                  </div>
                </div>
                <div style={{ marginTop: 16 }}>
                  <button style={{ display: "inline-flex", alignItems: "center", fontSize: 13, fontWeight: 500, color: "#4F46E5", background: "none", border: "none", cursor: "pointer" }}>
                    管理
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ marginLeft: 4 }}><path d="M9 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" /></svg>
                  </button>
                </div>
              </div>
            </div>

            {/* 登记限制表 */}
            <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 8, overflow: "hidden" }}>
              <div style={{ padding: "16px 20px", borderBottom: "1px solid #E5E7EB" }}>
                <h3 style={{ fontSize: 14, fontWeight: 600, color: "#111827", margin: 0 }}>登记限制</h3>
                <p style={{ fontSize: 12, color: "#6B7280", marginTop: 4, margin: "4px 0 0" }}>为组织中启用的每个模型设置默认速率限制</p>
              </div>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: "left", padding: "12px 20px", background: "#F9FAFB", borderBottom: "1px solid #E5E7EB", fontWeight: 600, color: "#6B7280", fontSize: 12 }}>模型名称</th>
                      <th style={{ textAlign: "left", padding: "12px 20px", background: "#F9FAFB", borderBottom: "1px solid #E5E7EB", fontWeight: 600, color: "#6B7280", fontSize: 12 }}>每分钟 Token 数</th>
                      <th style={{ textAlign: "left", padding: "12px 20px", background: "#F9FAFB", borderBottom: "1px solid #E5E7EB", fontWeight: 600, color: "#6B7280", fontSize: 12 }}>每分钟请求数</th>
                    </tr>
                  </thead>
                  <tbody>
                    {RATE_LIMITS.map((r) => (
                      <tr key={r.model} style={{ borderBottom: "1px solid #F3F4F6" }}>
                        <td style={{ padding: "12px 20px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <span style={{ width: 8, height: 8, borderRadius: "50%", background: r.provider === "OpenAI" ? "#10A37F" : r.provider === "Anthropic" ? "#D97706" : r.provider === "xAI" ? "#1D4ED8" : "#7C3AED" }} />
                            <span style={{ fontWeight: 500, color: "#111827" }}>{r.model}</span>
                            <span style={{ fontSize: 10, padding: "1px 6px", borderRadius: 3, background: "#F3F4F6", color: "#6B7280" }}>{r.provider}</span>
                          </div>
                        </td>
                        <td style={{ padding: "12px 20px", color: "#374151" }}>{r.tokensPerMin}</td>
                        <td style={{ padding: "12px 20px", color: "#374151" }}>{r.requestsPerMin}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {tab === "usage" && (
          <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 8, padding: 40, textAlign: "center" }}>
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#9CA3AF" strokeWidth="1.5" style={{ margin: "0 auto 12px" }}>
              <path d="M3 3v18h18M7 14l3-3 3 3 5-5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <p style={{ fontSize: 14, fontWeight: 500, color: "#374151", margin: 0 }}>使用量统计</p>
            <p style={{ fontSize: 12, color: "#9CA3AF", marginTop: 8, margin: "8px 0 0" }}>
              切换到"管理速率限制" Tab 查看和配置模型速率限制。
            </p>
          </div>
        )}

        {tab === "reserved" && (
          <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 8, padding: 40, textAlign: "center" }}>
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#9CA3AF" strokeWidth="1.5" style={{ margin: "0 auto 12px" }}>
              <rect x="3" y="4" width="18" height="6" rx="1" /><rect x="3" y="14" width="18" height="6" rx="1" />
            </svg>
            <p style={{ fontSize: 14, fontWeight: 500, color: "#374151", margin: 0 }}>预留容量</p>
            <p style={{ fontSize: 12, color: "#9CA3AF", marginTop: 8, margin: "8px 0 0" }}>
              预留容量功能即将上线。如需提前使用，请联系 Palantir 支持。
            </p>
          </div>
        )}
      </div>
    </PageChrome>
  );
}
