import { useState, useEffect, useMemo } from "react";
import { PageChrome } from "../../components/PageChrome";
import { BpToolbar } from "../../components/bp/BpToolbar";
import { apiGet } from "../../api/client";

/* ============================================================================
 * 类型定义
 * ========================================================================== */

type ThemeMode = "light" | "dark" | "contrast";

type ThemePreset = {
  id: string;
  name: string;
  mode: ThemeMode;
  desc: string;
  previewBg: string;
  previewColor: string;
  isBuiltIn: boolean;
};

type ThemeConfig = {
  primary: string;
  accent: string;
  bg: string;
  surface: string;
  text: string;
  textMuted: string;
  border: string;
  fontId: string;
  fontSize: number;
  lineHeight: number;
  spacingBase: number;
  paddingSm: number;
  paddingMd: number;
  paddingLg: number;
  marginSm: number;
  marginMd: number;
  marginLg: number;
  radius: number;
  sidebarWidth: number;
  gridCols: number;
};

type EditorTab = "colors" | "fonts" | "spacing";

/* ============================================================================
 * 常量 & 纯函数（便于测试）
 * ========================================================================== */

/** 3 个预设主题（浅色/暗色/高对比度）*/
export const MOCK_THEMES: ThemePreset[] = [
  {
    id: "light",
    name: "AOS 浅色",
    mode: "light",
    desc: "默认主题 · 当前",
    previewBg: "#F0F2F5",
    previewColor: "#111827",
    isBuiltIn: true,
  },
  {
    id: "dark",
    name: "AOS 深色",
    mode: "dark",
    desc: "暗色模式",
    previewBg: "#1F2937",
    previewColor: "#F9FAFB",
    isBuiltIn: true,
  },
  {
    id: "contrast",
    name: "高对比度",
    mode: "contrast",
    desc: "无障碍优先",
    previewBg: "#000000",
    previewColor: "#FFFFFF",
    isBuiltIn: true,
  },
];

export const PRIMARY_COLORS = [
  "#2563EB", "#4F46E5", "#7C3AED", "#059669",
  "#DC2626", "#EA580C", "#0891B2", "#4B5563",
];

export const ACCENT_COLORS = [
  "#3B82F6", "#818CF8", "#A78BFA", "#34D399",
  "#F87171", "#FB923C", "#22D3EE", "#9CA3AF",
];

export const FONTS = [
  { id: "pingfang", name: "苹方 / PingFang SC", stack: "'PingFang SC', 'Helvetica Neue', sans-serif" },
  { id: "noto", name: "思源黑体 / Noto Sans", stack: "'Noto Sans SC', sans-serif" },
  { id: "yahei", name: "微软雅黑 / YaHei", stack: "'Microsoft YaHei', sans-serif" },
];

export const FONT_SIZES = [12, 13, 14, 15, 16, 18, 20, 24];
export const LINE_HEIGHTS = [1.2, 1.4, 1.5, 1.6, 1.75, 1.8, 2.0];

/** 浅色主题的默认配置 */
export const LIGHT_CONFIG: ThemeConfig = {
  primary: "#2563EB",
  accent: "#3B82F6",
  bg: "#F0F2F5",
  surface: "#FFFFFF",
  text: "#111827",
  textMuted: "#6B7280",
  border: "#E5E7EB",
  fontId: "pingfang",
  fontSize: 14,
  lineHeight: 1.5,
  spacingBase: 16,
  paddingSm: 8,
  paddingMd: 16,
  paddingLg: 24,
  marginSm: 8,
  marginMd: 16,
  marginLg: 24,
  radius: 8,
  sidebarWidth: 260,
  gridCols: 12,
};

/** 根据主题模式生成对应的默认配置（纯函数，便于测试）*/
export function configForMode(mode: ThemeMode): ThemeConfig {
  if (mode === "dark") {
    return {
      ...LIGHT_CONFIG,
      bg: "#1F2937",
      surface: "#374151",
      text: "#F9FAFB",
      textMuted: "#9CA3AF",
      border: "#4B5563",
    };
  }
  if (mode === "contrast") {
    return {
      ...LIGHT_CONFIG,
      primary: "#0000FF",
      accent: "#0000CC",
      bg: "#000000",
      surface: "#000000",
      text: "#FFFFFF",
      textMuted: "#FFFFFF",
      border: "#FFFFFF",
      radius: 0,
    };
  }
  return { ...LIGHT_CONFIG };
}

/** 根据 config 生成 CSS 变量字符串（纯函数，便于测试）*/
export function buildCssVars(c: ThemeConfig): string {
  const font = FONTS.find((f) => f.id === c.fontId) || FONTS[0];
  const fontName = font.name.split(" / ")[0];
  return [
    ":root {",
  `  --color-primary: ${c.primary};`,
  `  --color-accent: ${c.accent};`,
  `  --color-background: ${c.bg};`,
  `  --color-surface: ${c.surface};`,
  `  --color-text: ${c.text};`,
  `  --color-text-muted: ${c.textMuted};`,
  `  --color-border: ${c.border};`,
  `  --font-family: '${fontName}', sans-serif;`,
  `  --font-size: ${c.fontSize}px;`,
  `  --line-height: ${c.lineHeight};`,
  `  --spacing-base: ${c.spacingBase}px;`,
  `  --padding-sm: ${c.paddingSm}px;`,
  `  --padding-md: ${c.paddingMd}px;`,
  `  --padding-lg: ${c.paddingLg}px;`,
  `  --margin-sm: ${c.marginSm}px;`,
  `  --margin-md: ${c.marginMd}px;`,
  `  --margin-lg: ${c.marginLg}px;`,
  `  --border-radius: ${c.radius}px;`,
  `  --sidebar-width: ${c.sidebarWidth}px;`,
  `  --grid-columns: ${c.gridCols};`,
  "}",
  ].join("\n");
}

/** 校验颜色字符串格式（纯函数，便于测试）*/
export function isValidHex(color: string): boolean {
  return /^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$/.test(color.trim());
}

/** 将 ThemeMode 映射为 UI 标签（纯函数，便于测试）*/
export function modeLabel(mode: ThemeMode): string {
  switch (mode) {
    case "light": return "浅色";
    case "dark": return "暗色";
    case "contrast": return "高对比度";
  }
}

/* ============================================================================
 * Page Component
 * ========================================================================== */

export function StylesPage() {
  const [themes, setThemes] = useState<ThemePreset[]>(MOCK_THEMES);
  const [activeThemeId, setActiveThemeId] = useState<string>("light");
  const [tab, setTab] = useState<EditorTab>("colors");
  const [config, setConfig] = useState<ThemeConfig>({ ...LIGHT_CONFIG });
  const [dirty, setDirty] = useState(false);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);

  /* GET /v1/themes —— 拉取主题列表，失败则用 MOCK_THEMES */
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiGet<{ items?: Array<{ id: string; name?: string; mode?: ThemeMode; description?: string }> }>("/v1/themes");
        if (cancelled) return;
        if (res.items && res.items.length) {
          const mapped: ThemePreset[] = res.items.map((it, idx) => ({
            id: it.id,
            name: it.name || `主题 ${idx + 1}`,
            mode: it.mode || "light",
            desc: it.description || "",
            previewBg: configForMode(it.mode || "light").bg,
            previewColor: configForMode(it.mode || "light").text,
            isBuiltIn: false,
          }));
          setThemes(mapped);
        }
      } catch {
        /* 降级到 MOCK_THEMES（已为初始值）*/
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const activeTheme = themes.find((t) => t.id === activeThemeId) || themes[0];
  const filteredThemes = useMemo(() => {
    if (!query.trim()) return themes;
    const q = query.toLowerCase();
    return themes.filter((t) => t.name.toLowerCase().includes(q) || t.desc.toLowerCase().includes(q));
  }, [themes, query]);

  function selectTheme(t: ThemePreset) {
    setActiveThemeId(t.id);
    setConfig(configForMode(t.mode));
    setDirty(false);
  }

  function patch(p: Partial<ThemeConfig>) {
    setConfig((prev) => ({ ...prev, ...p }));
    setDirty(true);
  }

  function newTheme() {
    const id = `theme_${Date.now()}`;
    const next: ThemePreset = {
      id,
      name: `新主题 ${themes.length + 1}`,
      mode: "light",
      desc: "自定义主题",
      previewBg: config.bg,
      previewColor: config.text,
      isBuiltIn: false,
    };
    setThemes((prev) => [...prev, next]);
    setActiveThemeId(id);
    setDirty(false);
  }

  function saveTheme() {
    setThemes((prev) =>
      prev.map((t) =>
        t.id === activeThemeId
          ? { ...t, previewBg: config.bg, previewColor: config.text }
          : t,
      ),
    );
    setDirty(false);
  }

  function resetTheme() {
    if (!activeTheme) return;
    setConfig(configForMode(activeTheme.mode));
    setDirty(false);
  }

  const cssVars = useMemo(() => buildCssVars(config), [config]);
  const currentFont = FONTS.find((f) => f.id === config.fontId) || FONTS[0];

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
          search={{ value: query, onChange: setQuery, placeholder: "搜索主题…" }}
          actions={
            <>
              <button className="p-btn p-btn-secondary p-btn-sm" onClick={newTheme}>+ 新建主题</button>
              <button
                className="p-btn p-btn-primary p-btn-sm"
                onClick={saveTheme}
                disabled={!dirty}
                style={!dirty ? { opacity: 0.5, cursor: "not-allowed" } : undefined}
              >
                保存{dirty ? " *" : ""}
              </button>
              <button className="p-btn p-btn-secondary p-btn-sm" onClick={resetTheme}>重置</button>
            </>
          }
          count={themes.length}
        />

        {/* === 两栏布局 === */}
        <div style={{ display: "grid", gridTemplateColumns: "260px 1fr", gap: 16, marginTop: 16 }}>

          {/* === 左栏：主题列表 === */}
          <aside style={{ background: "var(--aos-surface)", borderRadius: 2, padding: 12, border: "1px solid var(--aos-border)" }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: "#6B7280", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>
              主题列表 ({filteredThemes.length})
            </div>
            {loading && <div style={{ fontSize: 12, color: "#9CA3AF", padding: 12 }}>加载中…</div>}
            {!loading && filteredThemes.map((t) => (
              <div
                key={t.id}
                onClick={() => selectTheme(t)}
                style={{
                  padding: 10,
                  borderRadius: 2,
                  marginBottom: 6,
                  cursor: "pointer",
                  border: `1.5px solid ${activeThemeId === t.id ? config.primary : "#E5E7EB"}`,
                  background: activeThemeId === t.id ? "#EFF6FF" : "#fff",
                  transition: "all 0.15s",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div style={{
                    width: 28,
                    height: 28,
                    borderRadius: 4,
                    background: t.previewBg,
                    color: t.previewColor,
                    border: "1px solid #E5E7EB",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 9,
                    fontWeight: 700,
                    flexShrink: 0,
                  }}>
                    {modeLabel(t.mode).slice(0, 1)}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: "#111827", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {t.name}
                    </div>
                    <div style={{ fontSize: 10, color: "#9CA3AF" }}>{t.desc}</div>
                  </div>
                  {t.isBuiltIn && (
                    <span style={{ fontSize: 9, background: "#F3F4F6", color: "#6B7280", padding: "1px 4px", borderRadius: 2 }}>内置</span>
                  )}
                </div>
              </div>
            ))}
          </aside>

          {/* === 右栏：编辑区 === */}
          <main>
            {/* Tab 导航 */}
            <div style={{ display: "flex", gap: 2, borderBottom: "2px solid #E5E7EB", marginBottom: 0 }}>
              {([
                { id: "colors" as const, label: "颜色", icon: "🎨" },
                { id: "fonts" as const, label: "字体", icon: "🔤" },
                { id: "spacing" as const, label: "间距", icon: "📐" },
              ]).map((t) => (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  style={{
                    padding: "10px 20px",
                    fontSize: 13,
                    fontWeight: tab === t.id ? 600 : 500,
                    color: tab === t.id ? config.primary : "#6B7280",
                    border: "none",
                    borderBottom: `2px solid ${tab === t.id ? config.primary : "transparent"}`,
                    background: "none",
                    cursor: "pointer",
                    marginBottom: -2,
                  }}
                >
                  <span style={{ marginRight: 6 }}>{t.icon}</span>{t.label}
                </button>
              ))}
            </div>

            {/* Tab 内容 */}
            <div style={{ background: "#fff", borderRadius: "0 8px 8px 8px", padding: 20, border: "1px solid #E5E7EB", borderTop: "none" }}>

              {/* === 颜色 Tab === */}
              {tab === "colors" && (
                <div className="space-y-6">
                  {/* 主色 / 辅色：取色器 + 预设色板 */}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
                    <ColorField
                      label="主色（Primary）"
                      value={config.primary}
                      presets={PRIMARY_COLORS}
                      onChange={(c) => patch({ primary: c })}
                    />
                    <ColorField
                      label="辅色（Accent）"
                      value={config.accent}
                      presets={ACCENT_COLORS}
                      onChange={(c) => patch({ accent: c })}
                    />
                  </div>

                  {/* 背景与文字色 */}
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 8 }}>背景与文字</div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
                      <ColorField compact label="背景色" value={config.bg} onChange={(c) => patch({ bg: c })} />
                      <ColorField compact label="卡片背景" value={config.surface} onChange={(c) => patch({ surface: c })} />
                      <ColorField compact label="文字色" value={config.text} onChange={(c) => patch({ text: c })} />
                      <ColorField compact label="次要文字" value={config.textMuted} onChange={(c) => patch({ textMuted: c })} />
                      <ColorField compact label="边框色" value={config.border} onChange={(c) => patch({ border: c })} />
                    </div>
                  </div>
                </div>
              )}

              {/* === 字体 Tab === */}
              {tab === "fonts" && (
                <div className="space-y-6">
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 12 }}>字体族选择</div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
                      {FONTS.map((f) => (
                        <div
                          key={f.id}
                          onClick={() => patch({ fontId: f.id })}
                          style={{
                            padding: 14,
                            borderRadius: 2,
                            border: `1.5px solid ${config.fontId === f.id ? config.primary : "#E5E7EB"}`,
                            background: config.fontId === f.id ? "#EFF6FF" : "#fff",
                            cursor: "pointer",
                          }}
                        >
                          <div style={{ fontSize: 15, fontWeight: 600, color: "#111827", marginBottom: 4, fontFamily: f.stack }}>
                            {f.name}
                          </div>
                          <div style={{ fontSize: 12, color: "#6B7280", fontFamily: f.stack }}>AaBbCc 你好世界 123</div>
                          {config.fontId === f.id && (
                            <div style={{ fontSize: 10, color: config.primary, marginTop: 6 }}>✓ 当前使用</div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* 字号选择 */}
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 8 }}>
                      字号（font-size）
                      <span style={{ marginLeft: 8, fontSize: 11, color: "#9CA3AF" }}>当前：{config.fontSize}px</span>
                    </div>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      {FONT_SIZES.map((s) => (
                        <button
                          key={s}
                          onClick={() => patch({ fontSize: s })}
                          style={{
                            padding: "6px 12px",
                            border: `1px solid ${config.fontSize === s ? config.primary : "#E5E7EB"}`,
                            background: config.fontSize === s ? "#EFF6FF" : "#fff",
                            color: config.fontSize === s ? config.primary : "#374151",
                            borderRadius: 4,
                            fontSize: s > 16 ? 14 : s,
                            cursor: "pointer",
                            minWidth: 44,
                          }}
                        >
                          {s}px
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* 行高配置 */}
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 8 }}>
                      行高（line-height）
                      <span style={{ marginLeft: 8, fontSize: 11, color: "#9CA3AF" }}>当前：{config.lineHeight}</span>
                    </div>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      {LINE_HEIGHTS.map((lh) => (
                        <button
                          key={lh}
                          onClick={() => patch({ lineHeight: lh })}
                          style={{
                            padding: "6px 12px",
                            border: `1px solid ${config.lineHeight === lh ? config.primary : "#E5E7EB"}`,
                            background: config.lineHeight === lh ? "#EFF6FF" : "#fff",
                            color: config.lineHeight === lh ? config.primary : "#374151",
                            borderRadius: 4,
                            fontSize: 12,
                            cursor: "pointer",
                          }}
                        >
                          {lh}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* 字体预览 */}
                  <div style={{
                    padding: 20,
                    borderRadius: 2,
                    background: config.bg,
                    color: config.text,
                    fontFamily: currentFont.stack,
                    fontSize: config.fontSize,
                    lineHeight: config.lineHeight,
                    border: "1px solid #E5E7EB",
                  }}>
                    <div style={{ fontSize: config.fontSize + 4, fontWeight: 600, marginBottom: 8 }}>
                      字体预览 · {currentFont.name}
                    </div>
                    <p style={{ margin: 0 }}>
                      这是一段示例文字，用于预览当前字体族、字号 {config.fontSize}px 和行高 {config.lineHeight} 的效果。
                      AOS 平台提供主题与样式管理，让企业品牌保持一致的视觉表达。
                    </p>
                  </div>
                </div>
              )}

              {/* === 间距 Tab === */}
              {tab === "spacing" && (
                <div className="space-y-6">
                  {/* 基础间距 */}
                  <SpacingSlider
                    label="基础间距（spacing-base）"
                    value={config.spacingBase}
                    min={0} max={32}
                    onChange={(v) => patch({ spacingBase: v })}
                    color={config.primary}
                  />

                  {/* Padding 三档 */}
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 12 }}>Padding（内边距）</div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
                      <SpacingSlider label="小 (padding-sm)" value={config.paddingSm} min={0} max={20} onChange={(v) => patch({ paddingSm: v })} color={config.primary} />
                      <SpacingSlider label="中 (padding-md)" value={config.paddingMd} min={0} max={32} onChange={(v) => patch({ paddingMd: v })} color={config.primary} />
                      <SpacingSlider label="大 (padding-lg)" value={config.paddingLg} min={0} max={48} onChange={(v) => patch({ paddingLg: v })} color={config.primary} />
                    </div>
                  </div>

                  {/* Margin 三档 */}
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 12 }}>Margin（外边距）</div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
                      <SpacingSlider label="小 (margin-sm)" value={config.marginSm} min={0} max={20} onChange={(v) => patch({ marginSm: v })} color={config.primary} />
                      <SpacingSlider label="中 (margin-md)" value={config.marginMd} min={0} max={32} onChange={(v) => patch({ marginMd: v })} color={config.primary} />
                      <SpacingSlider label="大 (margin-lg)" value={config.marginLg} min={0} max={48} onChange={(v) => patch({ marginLg: v })} color={config.primary} />
                    </div>
                  </div>

                  {/* 其他布局参数 */}
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 12 }}>布局参数</div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
                      <SpacingSlider label="卡片圆角" value={config.radius} min={0} max={20} onChange={(v) => patch({ radius: v })} color={config.primary} />
                      <SpacingSlider label="侧边栏宽度" value={config.sidebarWidth} min={200} max={320} step={20} onChange={(v) => patch({ sidebarWidth: v })} color={config.primary} />
                      <div>
                        <label style={{ fontSize: 12, fontWeight: 500, color: "#374151", display: "block", marginBottom: 8 }}>栅格列数</label>
                        <div style={{ display: "flex", gap: 6 }}>
                          {[12, 8, 6].map((cols) => (
                            <button
                              key={cols}
                              onClick={() => patch({ gridCols: cols })}
                              style={{
                                padding: "4px 12px",
                                border: `1px solid ${config.gridCols === cols ? config.primary : "#E5E7EB"}`,
                                background: config.gridCols === cols ? "#EFF6FF" : "#fff",
                                color: config.gridCols === cols ? config.primary : "#374151",
                                borderRadius: 4,
                                fontSize: 12,
                                cursor: "pointer",
                              }}
                            >
                              {cols} 列
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* 间距预览 */}
                  <div style={{
                    background: config.bg,
                    borderRadius: config.radius,
                    padding: config.paddingMd,
                    border: `1px solid ${config.border}`,
                  }}>
                    <div style={{
                      background: config.surface,
                      borderRadius: config.radius,
                      padding: config.paddingMd,
                      color: config.text,
                      fontSize: 13,
                    }}>
                      <div style={{ fontWeight: 600, marginBottom: config.marginSm }}>
                        Padding / Margin / Radius 实时预览
                      </div>
                      <p style={{ margin: 0, fontSize: 12, color: config.textMuted }}>
                        padding-md={config.paddingMd}px · margin-sm={config.marginSm}px · radius={config.radius}px · spacing-base={config.spacingBase}px
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* === CSS 变量输出 === */}
            <div style={{ marginTop: 16 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: "#6B7280", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
                全局 CSS 变量（自动生成）
              </div>
              <pre style={{
                background: "#1F2937",
                color: "#F9FAFB",
                borderRadius: 2,
                padding: 16,
                fontSize: 12,
                fontFamily: "monospace",
                lineHeight: 1.8,
                margin: 0,
                overflowX: "auto",
              }}>
                {cssVars.split("\n").map((line, i) => {
                  if (line.includes(":root") || line === "}") {
                    return <div key={i} style={{ color: "#C4B5FD" }}>{line}</div>;
                  }
                  if (line.startsWith("  /*")) {
                    return <div key={i} style={{ color: "#6B7280" }}>{line}</div>;
                  }
                  const m = line.match(/^(  --[\w-]+): (.+);$/);
                  if (m) {
                    return (
                      <div key={i}>
                        <span style={{ color: "#F9FAFB" }}>{m[1]}</span>
                        <span style={{ color: "#9CA3AF" }}>: </span>
                        <span style={{ color: "#FCD34D" }}>{m[2]}</span>
                        <span style={{ color: "#9CA3AF" }}>;</span>
                      </div>
                    );
                  }
                  return <div key={i}>{line}</div>;
                })}
              </pre>
            </div>

            {/* === 实时预览卡片 === */}
            <div style={{ marginTop: 16 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: "#6B7280", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
                实时预览（改色立即更新）
              </div>
              <div style={{
                background: config.bg,
                borderRadius: config.radius,
                padding: config.paddingLg,
                border: `1px solid ${config.border}`,
                fontFamily: currentFont.stack,
              }}>
                <div style={{
                  background: config.surface,
                  borderRadius: config.radius,
                  padding: config.paddingMd,
                  color: config.text,
                  fontSize: config.fontSize,
                  lineHeight: config.lineHeight,
                }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: config.marginMd }}>
                    <h3 style={{ fontSize: config.fontSize + 2, fontWeight: 600, color: config.text, margin: 0 }}>订单管理</h3>
                    <button style={{
                      background: config.primary,
                      color: "#fff",
                      border: "none",
                      padding: `${config.paddingSm}px ${config.paddingMd}px`,
                      borderRadius: config.radius,
                      fontSize: config.fontSize - 1,
                      cursor: "pointer",
                    }}>
                      + 新建订单
                    </button>
                  </div>
                  <div style={{ display: "flex", gap: 8, marginBottom: config.marginMd }}>
                    {[
                      { label: "待处理", bg: "#DBEAFE", color: "#1E40AF" },
                      { label: "已完成", bg: "#D1FAE5", color: "#065F47" },
                      { label: "退货中", bg: "#FEF3C7", color: "#92400E" },
                      { label: "异常", bg: "#FEE2E2", color: "#991B1B" },
                    ].map((s) => (
                      <span key={s.label} style={{
                        background: s.bg,
                        color: s.color,
                        padding: "2px 8px",
                        borderRadius: config.radius,
                        fontSize: config.fontSize - 2,
                      }}>
                        {s.label}
                      </span>
                    ))}
                  </div>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: config.fontSize - 1 }}>
                    <thead>
                      <tr style={{ borderBottom: `2px solid ${config.border}` }}>
                        <th style={{ textAlign: "left", padding: config.paddingSm, color: config.textMuted, fontWeight: 500 }}>订单号</th>
                        <th style={{ textAlign: "left", padding: config.paddingSm, color: config.textMuted, fontWeight: 500 }}>客户</th>
                        <th style={{ textAlign: "left", padding: config.paddingSm, color: config.textMuted, fontWeight: 500 }}>金额</th>
                        <th style={{ textAlign: "left", padding: config.paddingSm, color: config.textMuted, fontWeight: 500 }}>状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        { id: "#20250725-001", name: "张三", amt: "¥1,280.00", st: { label: "退货中", bg: "#FEF3C7", color: "#92400E" } },
                        { id: "#20250725-002", name: "李四", amt: "¥3,560.00", st: { label: "已完成", bg: "#D1FAE5", color: "#065F47" } },
                      ].map((r) => (
                        <tr key={r.id} style={{ borderBottom: `1px solid ${config.border}` }}>
                          <td style={{ padding: config.paddingSm, color: config.text }}>{r.id}</td>
                          <td style={{ padding: config.paddingSm, color: config.text }}>{r.name}</td>
                          <td style={{ padding: config.paddingSm, color: config.text }}>{r.amt}</td>
                          <td style={{ padding: config.paddingSm }}>
                            <span style={{ background: r.st.bg, color: r.st.color, padding: "2px 8px", borderRadius: config.radius, fontSize: config.fontSize - 2 }}>
                              {r.st.label}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p style={{ fontSize: 11, color: config.textMuted, textAlign: "center", margin: `${config.marginSm}px 0 0` }}>
                  ↑ 以上预览反映了当前主题/颜色/字体/间距的设置效果
                </p>
              </div>
            </div>
          </main>
        </div>
      </div>
    </PageChrome>
  );
}

/* ============================================================================
 * 子组件
 * ========================================================================== */

/** 颜色字段：原生 color picker + 预设色板 + 十六进制输入 */
function ColorField({
  label,
  value,
  presets,
  onChange,
  compact,
}: {
  label: string;
  value: string;
  presets?: string[];
  onChange: (c: string) => void;
  compact?: boolean;
}) {
  return (
    <div>
      <label style={{ fontSize: compact ? 11 : 13, fontWeight: 500, color: "#374151", display: "block", marginBottom: 8 }}>
        {label}
      </label>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {/* 原生 color picker —— 点击弹出系统取色器 */}
        <input
          type="color"
          value={isValidHex(value) ? value : "#000000"}
          onChange={(e) => onChange(e.target.value.toUpperCase())}
          style={{
            width: 36,
            height: 36,
            border: "1px solid #E5E7EB",
            borderRadius: 2,
            cursor: "pointer",
            padding: 0,
            background: "none",
          }}
          aria-label={`${label} 取色器`}
        />
        <div style={{ flex: 1 }}>
          <input
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            style={{
              width: "100%",
              padding: "6px 8px",
              border: `1px solid ${isValidHex(value) ? "#E5E7EB" : "#EF4444"}`,
              borderRadius: 4,
              fontSize: 12,
              fontFamily: "monospace",
              color: "#374151",
            }}
            aria-label={`${label} 十六进制值`}
          />
          {!isValidHex(value) && (
            <div style={{ fontSize: 10, color: "#EF4444", marginTop: 2 }}>格式应为 #RGB 或 #RRGGBB</div>
          )}
        </div>
      </div>
      {/* 预设色板 */}
      {presets && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
          {presets.map((c) => (
            <div
              key={c}
              onClick={() => onChange(c)}
              style={{
                width: 28,
                height: 28,
                borderRadius: 4,
                background: c,
                cursor: "pointer",
                border: value.toUpperCase() === c.toUpperCase() ? "2px solid #111827" : "2px solid #fff",
                boxShadow: value.toUpperCase() === c.toUpperCase() ? "0 0 0 2px #2563EB" : "0 0 0 1px #E5E7EB",
                transition: "box-shadow 0.15s",
              }}
              title={c}
            />
          ))}
        </div>
      )}
      <div style={{ marginTop: 6, fontSize: 10, color: "#9CA3AF" }}>
        当前：<code style={{ background: "#F3F4F6", padding: "1px 4px", borderRadius: 2 }}>{value}</code>
      </div>
    </div>
  );
}

/** 间距滑块 */
function SpacingSlider({
  label,
  value,
  min,
  max,
  step = 1,
  onChange,
  color,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (v: number) => void;
  color: string;
}) {
  return (
    <div>
      <label style={{ fontSize: 12, fontWeight: 500, color: "#374151", display: "block", marginBottom: 6 }}>{label}</label>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          style={{ flex: 1, accentColor: color }}
        />
        <code style={{ fontSize: 11, color, width: 56, textAlign: "right" }}>{value}px</code>
      </div>
    </div>
  );
}
