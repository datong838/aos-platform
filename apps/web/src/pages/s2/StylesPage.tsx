import { useState } from "react";
import { PageChrome } from "../../components/PageChrome";
import { BpToolbar } from "../../components/bp/BpToolbar";

type ThemeId = "light" | "dark" | "brand" | "auto";

const THEMES: { id: ThemeId; name: string; desc: string; previewBg: string; previewColor: string }[] = [
  { id: "light", name: "AOS 浅色", desc: "默认主题 · 当前", previewBg: "#F0F2F5", previewColor: "#111827" },
  { id: "dark", name: "AOS 深色", desc: "暗色模式", previewBg: "#1F2937", previewColor: "#F9FAFB" },
  { id: "brand", name: "品牌定制", desc: "企业品牌色", previewBg: "linear-gradient(135deg,#4F46E5,#7C3AED)", previewColor: "#fff" },
  { id: "auto", name: "跟随系统", desc: "auto", previewBg: "linear-gradient(135deg,#F0F2F5 50%,#1F2937 50%)", previewColor: "#6B7280" },
];

const PRIMARY_COLORS = ["#2563EB", "#4F46E5", "#7C3AED", "#059669", "#DC2626", "#EA580C", "#0891B2", "#4B5563"];
const ACCENT_COLORS = ["#3B82F6", "#818CF8", "#A78BFA", "#34D399", "#F87171", "#FB923C", "#22D3EE", "#9CA3AF"];

const FONTS = [
  { id: "pingfang", name: "苹方 / PingFang SC", stack: "'PingFang SC', 'Helvetica Neue', sans-serif" },
  { id: "noto", name: "思源黑体 / Noto Sans", stack: "'Noto Sans SC', sans-serif" },
  { id: "yahei", name: "微软雅黑 / YaHei", stack: "'Microsoft YaHei', sans-serif" },
];

export function StylesPage() {
  const [theme, setTheme] = useState<ThemeId>("light");
  const [primaryColor, setPrimaryColor] = useState("#2563EB");
  const [accentColor, setAccentColor] = useState("#3B82F6");
  const [font, setFont] = useState("pingfang");
  const [spacing, setSpacing] = useState(16);
  const [radius, setRadius] = useState(8);
  const [sidebarWidth, setSidebarWidth] = useState(260);
  const [gridCols, setGridCols] = useState(12);
  const [query, setQuery] = useState("");

  const currentFont = FONTS.find((f) => f.id === font) ?? FONTS[0];

  return (
    <PageChrome title="主题与样式" lede="订单管理 · 配置主题、颜色、字体和间距">
      <div className="st-page">
        <div className="vr-header">
          <div>
            <h1>主题与样式</h1>
            <p>订单管理 · 配置主题、颜色、字体和间距</p>
          </div>
        </div>

        <BpToolbar
          search={{ value: query, onChange: setQuery, placeholder: "搜索样式设置…" }}
        />

        <div className="st-section">
          <h2 className="st-section-title">主题预设</h2>
          <div className="st-theme-grid" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
            {THEMES.map((t) => (
              <div
                key={t.id}
                className={theme === t.id ? "st-theme-card is-active" : "st-theme-card"}
                onClick={() => setTheme(t.id)}
              >
                <div className="st-theme-preview" style={{ background: t.previewBg, color: t.previewColor }}>
                  {t.name}
                </div>
                <div className="st-theme-name">{t.desc}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="st-section">
          <h2 className="st-section-title">品牌色调色板</h2>
          <div className="grid grid-cols-2 gap-6">
            <div>
              <label style={{ fontSize: 13, fontWeight: 500, color: "#374151", display: "block", marginBottom: 8 }}>
                主色（Primary）
              </label>
              <div className="flex gap-2 flex-wrap">
                {PRIMARY_COLORS.map((c) => (
                  <div
                    key={c}
                    className={primaryColor === c ? "st-swatch is-active" : "st-swatch"}
                    style={{ background: c }}
                    onClick={() => setPrimaryColor(c)}
                  />
                ))}
              </div>
              <div style={{ marginTop: 8, fontSize: 12, color: "#6B7280" }}>
                当前：<code style={{ background: "#F3F4F6", padding: "2px 6px", borderRadius: 3 }}>--color-primary: {primaryColor}</code>
              </div>
            </div>
            <div>
              <label style={{ fontSize: 13, fontWeight: 500, color: "#374151", display: "block", marginBottom: 8 }}>
                辅色（Accent）
              </label>
              <div className="flex gap-2 flex-wrap">
                {ACCENT_COLORS.map((c) => (
                  <div
                    key={c}
                    className={accentColor === c ? "st-swatch is-active" : "st-swatch"}
                    style={{ background: c }}
                    onClick={() => setAccentColor(c)}
                  />
                ))}
              </div>
              <div style={{ marginTop: 8, fontSize: 12, color: "#6B7280" }}>
                当前：<code style={{ background: "#F3F4F6", padding: "2px 6px", borderRadius: 3 }}>--color-accent: {accentColor}</code>
              </div>
            </div>
          </div>
        </div>

        <div className="st-section">
          <h2 className="st-section-title">背景与文字</h2>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label style={{ fontSize: 13, fontWeight: 500, color: "#374151", display: "block", marginBottom: 8 }}>背景色</label>
              <div className="flex items-center gap-2">
                <div style={{ width: 32, height: 32, borderRadius: 6, background: "#F0F2F5", border: "1px solid #E5E7EB" }} />
                <code style={{ fontSize: 12, color: "#6B7280" }}>#F0F2F5</code>
              </div>
            </div>
            <div>
              <label style={{ fontSize: 13, fontWeight: 500, color: "#374151", display: "block", marginBottom: 8 }}>卡片背景</label>
              <div className="flex items-center gap-2">
                <div style={{ width: 32, height: 32, borderRadius: 6, background: "#fff", border: "1px solid #E5E7EB" }} />
                <code style={{ fontSize: 12, color: "#6B7280" }}>#FFFFFF</code>
              </div>
            </div>
            <div>
              <label style={{ fontSize: 13, fontWeight: 500, color: "#374151", display: "block", marginBottom: 8 }}>文字色</label>
              <div className="flex items-center gap-2">
                <div style={{ width: 32, height: 32, borderRadius: 6, background: "#111827", border: "1px solid #E5E7EB" }} />
                <code style={{ fontSize: 12, color: "#6B7280" }}>#111827</code>
              </div>
            </div>
          </div>
        </div>

        <div className="st-section">
          <h2 className="st-section-title">字体设置</h2>
          <div className="st-font-grid">
            {FONTS.map((f) => (
              <div
                key={f.id}
                className={font === f.id ? "st-font-card is-active" : "st-font-card"}
                onClick={() => setFont(f.id)}
              >
                <div className="st-font-preview" style={{ fontFamily: f.stack }}>{f.name}</div>
                <div className="st-font-name">AaBbCc 你好世界 123</div>
                {font === f.id && <div style={{ fontSize: 11, color: "#0F6E56", marginTop: 8 }}>✓ 当前使用</div>}
              </div>
            ))}
          </div>
        </div>

        <div className="st-section">
          <h2 className="st-section-title">间距与圆角</h2>
          <div style={{ background: "#fff", borderRadius: 8, padding: 20, boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
            <div className="st-color-row">
              <span style={{ fontSize: 13, color: "#374151" }}>内容区间距（spacing-base）</span>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min={0}
                  max={32}
                  value={spacing}
                  style={{ width: 120 }}
                  onChange={(e) => setSpacing(Number(e.target.value))}
                />
                <code style={{ fontSize: 12, color: "#0F6E56", width: 48 }}>{spacing}px</code>
              </div>
            </div>
            <div className="st-color-row">
              <span style={{ fontSize: 13, color: "#374151" }}>卡片圆角（border-radius）</span>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min={0}
                  max={20}
                  value={radius}
                  style={{ width: 120 }}
                  onChange={(e) => setRadius(Number(e.target.value))}
                />
                <code style={{ fontSize: 12, color: "#0F6E56", width: 48 }}>{radius}px</code>
              </div>
            </div>
            <div className="st-color-row">
              <span style={{ fontSize: 13, color: "#374151" }}>侧边栏宽度</span>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min={200}
                  max={320}
                  step={20}
                  value={sidebarWidth}
                  style={{ width: 120 }}
                  onChange={(e) => setSidebarWidth(Number(e.target.value))}
                />
                <code style={{ fontSize: 12, color: "#0F6E56", width: 48 }}>{sidebarWidth}px</code>
              </div>
            </div>
            <div className="st-color-row" style={{ borderBottom: "none" }}>
              <span style={{ fontSize: 13, color: "#374151" }}>栅格列数</span>
              <div className="flex gap-2">
                {[12, 8, 6].map((cols) => (
                  <button
                    key={cols}
                    style={{
                      padding: "4px 12px",
                      border: `1px solid ${gridCols === cols ? "#0F6E56" : "#E5E7EB"}`,
                      background: gridCols === cols ? "#ECFDF5" : "#fff",
                      color: gridCols === cols ? "#0F6E56" : "#374151",
                      borderRadius: 4,
                      fontSize: 12,
                      cursor: "pointer",
                    }}
                    onClick={() => setGridCols(cols)}
                  >
                    {cols} 列
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="st-section">
          <h2 className="st-section-title">全局 CSS 变量</h2>
          <div style={{ background: "#1F2937", borderRadius: 8, padding: 16, fontFamily: "monospace", fontSize: 12, lineHeight: 1.8 }}>
            <div style={{ color: "#6B7280" }}>/* 自动生成 — 修改上方设置后实时更新 */</div>
            <div style={{ color: "#C4B5FD" }}>:root {"{"}</div>
            <div style={{ color: "#F9FAFB", paddingLeft: 20 }}>--color-primary: <span style={{ color: "#FCD34D" }}>{primaryColor}</span>;</div>
            <div style={{ color: "#F9FAFB", paddingLeft: 20 }}>--color-accent: <span style={{ color: "#FCD34D" }}>{accentColor}</span>;</div>
            <div style={{ color: "#F9FAFB", paddingLeft: 20 }}>--color-background: <span style={{ color: "#FCD34D" }}>#F0F2F5</span>;</div>
            <div style={{ color: "#F9FAFB", paddingLeft: 20 }}>--color-surface: <span style={{ color: "#FCD34D" }}>#FFFFFF</span>;</div>
            <div style={{ color: "#F9FAFB", paddingLeft: 20 }}>--color-text: <span style={{ color: "#FCD34D" }}>#111827</span>;</div>
            <div style={{ color: "#F9FAFB", paddingLeft: 20 }}>--color-text-muted: <span style={{ color: "#FCD34D" }}>#6B7280</span>;</div>
            <div style={{ color: "#F9FAFB", paddingLeft: 20 }}>--color-border: <span style={{ color: "#FCD34D" }}>#E5E7EB</span>;</div>
            <div style={{ color: "#F9FAFB", paddingLeft: 20 }}>--font-family: <span style={{ color: "#FCD34D" }}>'{currentFont.name.split(" / ")[0]}', sans-serif</span>;</div>
            <div style={{ color: "#F9FAFB", paddingLeft: 20 }}>--spacing-base: <span style={{ color: "#FCD34D" }}>{spacing}px</span>;</div>
            <div style={{ color: "#F9FAFB", paddingLeft: 20 }}>--border-radius: <span style={{ color: "#FCD34D" }}>{radius}px</span>;</div>
            <div style={{ color: "#F9FAFB", paddingLeft: 20 }}>--sidebar-width: <span style={{ color: "#FCD34D" }}>{sidebarWidth}px</span>;</div>
            <div style={{ color: "#F9FAFB", paddingLeft: 20 }}>--grid-columns: <span style={{ color: "#FCD34D" }}>{gridCols}</span>;</div>
            <div style={{ color: "#C4B5FD" }}>{"}"}</div>
          </div>
        </div>

        <div className="st-section">
          <h2 className="st-section-title">实时预览</h2>
          <div style={{ background: "#F0F2F5", borderRadius: 8, padding: 24, border: "1px solid #E5E7EB" }}>
            <div style={{ background: "#fff", borderRadius: 8, padding: 20, marginBottom: 16 }}>
              <div className="flex items-center justify-between mb-3">
                <h3 style={{ fontSize: 16, fontWeight: 600, color: "#111827", margin: 0 }}>订单管理</h3>
                <button style={{ background: primaryColor, color: "#fff", border: "none", padding: "6px 16px", borderRadius: 4, fontSize: 13, cursor: "pointer" }}>
                  + 新建订单
                </button>
              </div>
              <div className="flex gap-2 mb-3">
                <span style={{ background: "#DBEAFE", color: "#1E40AF", padding: "2px 8px", borderRadius: 4, fontSize: 12 }}>待处理</span>
                <span style={{ background: "#D1FAE5", color: "#065F47", padding: "2px 8px", borderRadius: 4, fontSize: 12 }}>已完成</span>
                <span style={{ background: "#FEF3C7", color: "#92400E", padding: "2px 8px", borderRadius: 4, fontSize: 12 }}>退货中</span>
                <span style={{ background: "#FEE2E2", color: "#991B1B", padding: "2px 8px", borderRadius: 4, fontSize: 12 }}>异常</span>
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid #E5E7EB" }}>
                    <th style={{ textAlign: "left", padding: 8, color: "#374151" }}>订单号</th>
                    <th style={{ textAlign: "left", padding: 8, color: "#374151" }}>客户</th>
                    <th style={{ textAlign: "left", padding: 8, color: "#374151" }}>金额</th>
                    <th style={{ textAlign: "left", padding: 8, color: "#374151" }}>状态</th>
                  </tr>
                </thead>
                <tbody>
                  <tr style={{ borderBottom: "1px solid #F3F4F6" }}>
                    <td style={{ padding: 8 }}>#20250725-001</td>
                    <td style={{ padding: 8 }}>张三</td>
                    <td style={{ padding: 8 }}>¥1,280.00</td>
                    <td style={{ padding: 8 }}>
                      <span style={{ background: "#FEF3C7", color: "#92400E", padding: "2px 8px", borderRadius: 4, fontSize: 12 }}>退货中</span>
                    </td>
                  </tr>
                  <tr>
                    <td style={{ padding: 8 }}>#20250725-002</td>
                    <td style={{ padding: 8 }}>李四</td>
                    <td style={{ padding: 8 }}>¥3,560.00</td>
                    <td style={{ padding: 8 }}>
                      <span style={{ background: "#D1FAE5", color: "#065F47", padding: "2px 8px", borderRadius: 4, fontSize: 12 }}>已完成</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p style={{ fontSize: 12, color: "#6B7280", textAlign: "center", margin: 0 }}>
              ↑ 以上预览反映了当前主题/颜色/字体/间距的设置效果
            </p>
          </div>
        </div>
      </div>
    </PageChrome>
  );
}
