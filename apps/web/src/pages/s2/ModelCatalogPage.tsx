import { useState } from "react";
import { Link } from "react-router-dom";
import { PageChrome } from "../../components/PageChrome";

type ModelFamily = {
  id: string;
  name: string;
  provider: string;
  status: "enabled" | "disabled";
  models: string[];
};

const MODEL_FAMILIES: ModelFamily[] = [
  { id: "openai", name: "OpenAI GPT", provider: "Azure", status: "enabled", models: ["GPT-5.4 Pro", "GPT-5.5", "GPT-5.4 mini"] },
  { id: "anthropic", name: "Anthropic Claude", provider: "AWS Bedrock", status: "enabled", models: ["Claude Opus 4.7", "Claude Sonnet 4.6", "Claude Haiku 4.5"] },
  { id: "xai", name: "xAI Grok", provider: "Palantir Hub", status: "enabled", models: ["Grok 4.3"] },
  { id: "meta", name: "Meta Llama", provider: "Palantir Hub", status: "disabled", models: ["Llama 4 Maverick 17B"] },
  { id: "embedding", name: "Embedding Models", provider: "Azure", status: "enabled", models: ["text-embedding-ada-002", "Text Embedding 3 Large"] },
];

type TabId = "settings" | "enablement" | "registered";

export function ModelCatalogPage() {
  const [tab, setTab] = useState<TabId>("settings");
  const [aipEnabled, setAipEnabled] = useState(true);
  const [orgRestricted, setOrgRestricted] = useState(true);
  const [orgs, setOrgs] = useState<Record<string, boolean>>({
    "组织 Alpha": true,
    "组织 Beta": false,
    "组织 Gamma": false,
    "组织 Delta": false,
    "组织 Epsilon": false,
    "组织 Zeta": false,
  });
  const [orgSearch, setOrgSearch] = useState("");

  const filteredOrgs = Object.entries(orgs).filter(([name]) =>
    name.toLowerCase().includes(orgSearch.toLowerCase()),
  );

  return (
    <PageChrome title="模型目录" lede="管理 AIP 启用状态、模型家族和已注册模型">
      <div style={{ maxWidth: "960px", margin: "0 auto" }}>
        {/* 三层架构定位条 */}
        <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 8, padding: 16, display: "flex", alignItems: "center", gap: 0, marginBottom: 16 }}>
          {[
            { label: "L1", name: "模型供应商", desc: "凭证管理", href: "/aip/model-providers", active: false },
            { label: "L2", name: "模型路由", desc: "流量策略 · 熔断", href: "/aip/model-router", active: false },
            { label: "L3 · 当前", name: "模型目录", desc: "可发现 → 注册", href: null, active: true },
            { label: "AIP", name: "智能体调用", desc: "选模型 → 推理", href: null, active: false, green: true },
          ].map((item, idx, arr) => (
            <div key={item.label} style={{ display: "flex", alignItems: "center", flex: 1 }}>
              <div style={{
                flex: 1,
                textAlign: "center",
                padding: 12,
                borderRadius: 6,
                background: item.active ? "#EFF6FF" : item.green ? "#F0FDF4" : "#F9FAFB",
                border: item.active ? "2px solid #2563EB" : item.green ? "1px solid #6EE7B7" : "none",
              }}>
                <div style={{
                  fontSize: 11,
                  color: item.active ? "#2563EB" : item.green ? "#059669" : "#6B7280",
                  fontWeight: 600,
                  textTransform: "uppercase",
                  marginBottom: 4,
                }}>{item.label}</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: item.active ? "#111827" : item.green ? "#065F46" : "#374151" }}>{item.name}</div>
                <div style={{ fontSize: 11, color: item.active ? "#3B82F6" : item.green ? "#059669" : "#9CA3AF", marginTop: 2 }}>{item.desc}</div>
                {item.href && (
                  <Link to={item.href} style={{ display: "inline-block", marginTop: 6, fontSize: 11, color: "#2563EB", textDecoration: "none" }}>进入 →</Link>
                )}
              </div>
              {idx < arr.length - 1 && (
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#D1D5DB" strokeWidth="1.5" style={{ flexShrink: 0 }}>
                  <path d="M5 12h14M13 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </div>
          ))}
        </div>

        {/* 目录 vs 已注册 差异说明 */}
        <div style={{ background: "#EFF6FF", border: "1px solid #BFDBFE", borderRadius: 8, padding: 16, marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="1.5" style={{ flexShrink: 0, marginTop: 2 }}>
              <circle cx="12" cy="12" r="9" /><path d="M12 16v-4M12 8h.01" strokeLinecap="round" />
            </svg>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: "#1E40AF", marginBottom: 8 }}>模型目录 vs 已注册模型</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, fontSize: 12 }}>
                <div>
                  <strong style={{ color: "#1E40AF" }}>📋 模型目录（Tab 2）</strong>
                  <p style={{ color: "#374151", margin: "4px 0 0", lineHeight: 1.5 }}>所有<b>可发现的</b>模型清单，来自已接入的供应商。浏览规格、能力、价格，但尚未授权给 AIP 使用。</p>
                </div>
                <div>
                  <strong style={{ color: "#059669" }}>✅ 已注册模型（Tab 3）</strong>
                  <p style={{ color: "#374151", margin: "4px 0 0", lineHeight: 1.5 }}>已授权并<b>配置了用户配额</b>的模型，暴露给 AIP 智能体选择。从目录中选择模型 → 配置配额 → 注册。</p>
                </div>
              </div>
              <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid #BFDBFE", fontSize: 12, color: "#1E40AF" }}>
                💡 流程：<strong>供应商配置(L1)</strong> → <strong>路由策略(L2)</strong> → <strong>目录浏览</strong> → <strong>注册模型(L3)</strong> → AIP 可选
              </div>
            </div>
          </div>
        </div>

        {/* Tab 导航 */}
        <div style={{ display: "flex", gap: 4, borderBottom: "1px solid #E5E7EB", marginBottom: 16 }}>
          {([
            { id: "settings", label: "AIP 设置" },
            { id: "enablement", label: "模型启用" },
            { id: "registered", label: "已注册模型" },
          ] as const).map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              style={{
                padding: "8px 16px",
                fontSize: 13,
                fontWeight: tab === t.id ? 500 : 400,
                borderBottom: tab === t.id ? "2px solid #2563EB" : "2px solid transparent",
                color: tab === t.id ? "#111827" : "#6B7280",
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

        {/* Tab 内容 */}
        {tab === "settings" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ borderRadius: 8, border: "1px solid #E5E7EB", background: "#fff", overflow: "hidden" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 16px", borderBottom: "1px solid #F3F4F6" }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#7C3AED" strokeWidth="1.5"><circle cx="12" cy="12" r="10" /><path d="M12 16v-4M12 8h.01" strokeLinecap="round" /></svg>
                <h2 style={{ fontSize: 14, fontWeight: 600, color: "#111827", margin: 0 }}>AIP 启用</h2>
              </div>
              <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 20 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div style={{ flex: 1 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 500, color: "#111827", margin: 0 }}>启用初始 AIP 功能</h3>
                    <p style={{ fontSize: 12, color: "#6B7280", marginTop: 4, lineHeight: 1.6, margin: "4px 0 0" }}>
                      Palantir AIP 将生成式 AI 与业务运营连接。这些功能和辅助服务利用托管在 Palantir Microsoft Azure 环境中的大语言模型。启用这些功能即表示您同意遵守 Palantir 的 AIP 补充协议。
                    </p>
                  </div>
                  <ToggleSwitch checked={aipEnabled} onChange={setAipEnabled} />
                </div>

                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div style={{ flex: 1 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 500, color: "#111827", margin: 0 }}>限制 AIP 到指定组织</h3>
                    <p style={{ fontSize: 12, color: "#6B7280", marginTop: 4, lineHeight: 1.6, margin: "4px 0 0" }}>
                      将 AIP 启用限制到特定组织。如果启用此设置，则只有下方选中的组织才能使用 AIP，其他组织将无法使用。
                    </p>
                  </div>
                  <ToggleSwitch checked={orgRestricted} onChange={setOrgRestricted} />
                </div>

                {orgRestricted && (
                  <div style={{ borderTop: "1px solid #F3F4F6", paddingTop: 16 }}>
                    <div style={{ position: "relative", marginBottom: 8 }}>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#9CA3AF" strokeWidth="2" style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)" }}>
                        <circle cx="11" cy="11" r="7" /><path d="M20 20l-3-3" strokeLinecap="round" />
                      </svg>
                      <input
                        type="search"
                        placeholder="搜索组织..."
                        value={orgSearch}
                        onChange={(e) => setOrgSearch(e.target.value)}
                        style={{ width: "100%", paddingLeft: 36, paddingRight: 16, padding: "8px 16px 8px 36px", fontSize: 13, border: "1px solid #E5E7EB", borderRadius: 8, outline: "none" }}
                      />
                    </div>
                    <div style={{ maxHeight: 160, overflowY: "auto" }}>
                      {filteredOrgs.map(([name, checked]) => (
                        <label key={name} style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 12px", cursor: "pointer", borderRadius: 6, fontSize: 13, color: "#374151" }}>
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => setOrgs((prev) => ({ ...prev, [name]: !prev[name] }))}
                            style={{ accentColor: "#2563EB" }}
                          />
                          {name}
                        </label>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, paddingTop: 16, borderTop: "1px solid #F3F4F6" }}>
              <button style={{ padding: "6px 16px", fontSize: 12, border: "1px solid #E5E7EB", borderRadius: 6, background: "#fff", color: "#374151", cursor: "pointer" }}>取消</button>
              <button style={{ padding: "6px 16px", fontSize: 12, border: "none", borderRadius: 6, background: "#2563EB", color: "#fff", cursor: "pointer" }}>保存到分支</button>
            </div>

            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", fontSize: 12 }}>
              <span style={{ color: "#6B7280", alignSelf: "center" }}>相关:</span>
              <Link to="/aip/model-router" style={{ padding: "6px 12px", borderRadius: 6, border: "1px solid #E5E7EB", color: "#111827", textDecoration: "none" }}>模型路由 →</Link>
              <Link to="/aip/model-providers" style={{ padding: "6px 12px", borderRadius: 6, border: "1px solid #E5E7EB", color: "#111827", textDecoration: "none" }}>模型供应商 →</Link>
            </div>
          </div>
        )}

        {tab === "enablement" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ background: "#F3F4F6", border: "1px solid #E5E7EB", borderRadius: 8, padding: "12px 16px" }}>
              <p style={{ fontSize: 12, color: "#6B7280", lineHeight: 1.6, margin: 0 }}>
                本页面反映的是从法律角度已启用的模型家族。实际可用的模型可能是这些模型的子集，具体取决于与 Palantir Hub 的连接情况以及地理限制对某些模型可用性的影响。
              </p>
            </div>
            <div style={{ borderRadius: 8, border: "1px solid #E5E7EB", background: "#fff", overflow: "hidden" }}>
              <div style={{ padding: "12px 16px", borderBottom: "1px solid #F3F4F6", fontSize: 14, fontWeight: 600, color: "#111827" }}>
                模型家族 ({MODEL_FAMILIES.length})
              </div>
              {MODEL_FAMILIES.map((f) => (
                <div key={f.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 16px", borderBottom: "1px solid #F3F4F6", fontSize: 13 }}>
                  <div>
                    <div style={{ fontWeight: 500, color: "#111827" }}>{f.name}</div>
                    <div style={{ fontSize: 12, color: "#6B7280" }}>{f.provider}</div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <span style={{
                      padding: "2px 10px",
                      borderRadius: 12,
                      fontSize: 11,
                      fontWeight: 500,
                      background: f.status === "enabled" ? "#DBEAFE" : "#F3F4F6",
                      color: f.status === "enabled" ? "#1E40AF" : "#6B7280",
                    }}>
                      {f.status === "enabled" ? "已启用" : "未启用"}
                    </span>
                    <button style={{ fontSize: 12, color: "#2563EB", background: "none", border: "none", cursor: "pointer", fontWeight: 500 }}>管理</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === "registered" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ borderRadius: 8, border: "1px solid #E5E7EB", background: "#fff", overflow: "hidden" }}>
              <div style={{ padding: "12px 16px", borderBottom: "1px solid #F3F4F6", fontSize: 14, fontWeight: 600, color: "#111827" }}>
                已注册模型 ({MODEL_FAMILIES.filter((f) => f.status === "enabled").flatMap((f) => f.models).length})
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left", padding: "10px 16px", background: "#F9FAFB", borderBottom: "1px solid #E5E7EB", fontWeight: 600, color: "#6B7280", fontSize: 11 }}>模型名称</th>
                    <th style={{ textAlign: "left", padding: "10px 16px", background: "#F9FAFB", borderBottom: "1px solid #E5E7EB", fontWeight: 600, color: "#6B7280", fontSize: 11 }}>供应商</th>
                    <th style={{ textAlign: "left", padding: "10px 16px", background: "#F9FAFB", borderBottom: "1px solid #E5E7EB", fontWeight: 600, color: "#6B7280", fontSize: 11 }}>配额状态</th>
                  </tr>
                </thead>
                <tbody>
                  {MODEL_FAMILIES.filter((f) => f.status === "enabled").flatMap((f) =>
                    f.models.map((m) => ({ model: m, provider: f.provider, family: f.name })),
                  ).map((row) => (
                    <tr key={row.model} style={{ borderBottom: "1px solid #F3F4F6" }}>
                      <td style={{ padding: "10px 16px", fontWeight: 500, color: "#111827" }}>{row.model}</td>
                      <td style={{ padding: "10px 16px", color: "#6B7280", fontSize: 12 }}>{row.provider}</td>
                      <td style={{ padding: "10px 16px" }}>
                        <span style={{ padding: "2px 8px", borderRadius: 12, fontSize: 11, background: "#D1FAE5", color: "#059669" }}>已配额</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </PageChrome>
  );
}

function ToggleSwitch({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      style={{
        width: 48,
        height: 24,
        borderRadius: 12,
        background: checked ? "#2563EB" : "#E5E7EB",
        position: "relative",
        border: "none",
        cursor: "pointer",
        transition: "background 0.15s",
        flexShrink: 0,
      }}
    >
      <div style={{
        position: "absolute",
        top: 2,
        left: checked ? 26 : 2,
        width: 20,
        height: 20,
        borderRadius: "50%",
        background: "#fff",
        transition: "left 0.15s",
        boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
      }} />
    </button>
  );
}
