import { describe, expect, it } from "vitest";
import {
  MOCK_THEMES,
  PRIMARY_COLORS,
  ACCENT_COLORS,
  FONTS,
  FONT_SIZES,
  LINE_HEIGHTS,
  LIGHT_CONFIG,
  configForMode,
  buildCssVars,
  isValidHex,
  modeLabel,
} from "./StylesPage";

describe("StylesPage · MOCK_THEMES 预设主题完整性", () => {
  it("包含 3 个预设主题", () => {
    expect(MOCK_THEMES).toHaveLength(3);
  });

  it("3 个预设主题覆盖 light/dark/contrast 模式", () => {
    const modes = MOCK_THEMES.map((t) => t.mode).sort();
    expect(modes).toEqual(["contrast", "dark", "light"]);
  });

  it("所有主题都有 previewBg 和 previewColor", () => {
    for (const t of MOCK_THEMES) {
      expect(t.previewBg.length).toBeGreaterThan(0);
      expect(t.previewColor.length).toBeGreaterThan(0);
      expect(t.isBuiltIn).toBe(true);
    }
  });
});

describe("StylesPage · configForMode 主题模式映射", () => {
  it("light 模式返回浅色配置", () => {
    const c = configForMode("light");
    expect(c.bg).toBe("#F0F2F5");
    expect(c.surface).toBe("#FFFFFF");
    expect(c.text).toBe("#111827");
  });

  it("dark 模式返回深色配置", () => {
    const c = configForMode("dark");
    expect(c.bg).toBe("#1F2937");
    expect(c.surface).toBe("#374151");
    expect(c.text).toBe("#F9FAFB");
  });

  it("contrast 模式返回高对比度配置（radius=0）", () => {
    const c = configForMode("contrast");
    expect(c.bg).toBe("#000000");
    expect(c.text).toBe("#FFFFFF");
    expect(c.radius).toBe(0);
  });

  it("3 种模式的主色相同（仅背景/文字不同）", () => {
    const light = configForMode("light");
    const dark = configForMode("dark");
    const contrast = configForMode("contrast");
    // primary 在 light/dark 一致
    expect(light.primary).toBe(dark.primary);
    // contrast 模式 primary 改为纯蓝
    expect(contrast.primary).toBe("#0000FF");
  });
});

describe("StylesPage · buildCssVars CSS 变量生成", () => {
  it("生成包含所有必需变量的 :root 块", () => {
    const css = buildCssVars(LIGHT_CONFIG);
    expect(css).toContain(":root {");
    expect(css).toContain("--color-primary: #2563EB");
    expect(css).toContain("--color-accent: #3B82F6");
    expect(css).toContain("--color-background: #F0F2F5");
    expect(css).toContain("--color-surface: #FFFFFF");
    expect(css).toContain("--color-text: #111827");
    expect(css).toContain("--font-family:");
    expect(css).toContain("--spacing-base:");
    expect(css).toContain("--border-radius:");
    expect(css).toContain("}");
  });

  it("fontSize/lineHeight 正确输出", () => {
    const c = { ...LIGHT_CONFIG, fontSize: 16, lineHeight: 1.75 };
    const css = buildCssVars(c);
    expect(css).toContain("--font-size: 16px");
    expect(css).toContain("--line-height: 1.75");
  });

  it("padding/margin 三档变量正确输出", () => {
    const c = { ...LIGHT_CONFIG, paddingSm: 4, paddingMd: 12, paddingLg: 20, marginSm: 4, marginMd: 12, marginLg: 20 };
    const css = buildCssVars(c);
    expect(css).toContain("--padding-sm: 4px");
    expect(css).toContain("--padding-md: 12px");
    expect(css).toContain("--padding-lg: 20px");
    expect(css).toContain("--margin-sm: 4px");
    expect(css).toContain("--margin-md: 12px");
    expect(css).toContain("--margin-lg: 20px");
  });

  it("字体名取中文部分", () => {
    const c = { ...LIGHT_CONFIG, fontId: "noto" };
    const css = buildCssVars(c);
    expect(css).toContain("思源黑体");
  });
});

describe("StylesPage · isValidHex 颜色校验", () => {
  it("接受 6 位十六进制", () => {
    expect(isValidHex("#2563EB")).toBe(true);
    expect(isValidHex("#000000")).toBe(true);
    expect(isValidHex("#FFFFFF")).toBe(true);
  });

  it("接受 3 位简写", () => {
    expect(isValidHex("#FFF")).toBe(true);
    expect(isValidHex("#abc")).toBe(true);
  });

  it("接受带空格", () => {
    expect(isValidHex("  #2563EB  ")).toBe(true);
  });

  it("拒绝非 # 前缀", () => {
    expect(isValidHex("2563EB")).toBe(false);
    expect(isValidHex("red")).toBe(false);
  });

  it("拒绝错误长度", () => {
    expect(isValidHex("#2563E")).toBe(false);
    expect(isValidHex("#2563EBB")).toBe(false);
  });

  it("拒绝非法字符", () => {
    expect(isValidHex("#2563EG")).toBe(false);
  });
});

describe("StylesPage · modeLabel 标签映射", () => {
  it("light → 浅色", () => {
    expect(modeLabel("light")).toBe("浅色");
  });
  it("dark → 暗色", () => {
    expect(modeLabel("dark")).toBe("暗色");
  });
  it("contrast → 高对比度", () => {
    expect(modeLabel("contrast")).toBe("高对比度");
  });
});

describe("StylesPage · 常量数据完整性", () => {
  it("PRIMARY_COLORS 有 8 个颜色且格式合法", () => {
    expect(PRIMARY_COLORS).toHaveLength(8);
    for (const c of PRIMARY_COLORS) {
      expect(isValidHex(c)).toBe(true);
    }
  });

  it("ACCENT_COLORS 有 8 个颜色且格式合法", () => {
    expect(ACCENT_COLORS).toHaveLength(8);
    for (const c of ACCENT_COLORS) {
      expect(isValidHex(c)).toBe(true);
    }
  });

  it("FONTS 至少 3 个字体", () => {
    expect(FONTS.length).toBeGreaterThanOrEqual(3);
    for (const f of FONTS) {
      expect(f.id.length).toBeGreaterThan(0);
      expect(f.name.length).toBeGreaterThan(0);
      expect(f.stack.length).toBeGreaterThan(0);
    }
  });

  it("FONT_SIZES 升序且包含常用 14px", () => {
    for (let i = 1; i < FONT_SIZES.length; i++) {
      expect(FONT_SIZES[i]).toBeGreaterThan(FONT_SIZES[i - 1]);
    }
    expect(FONT_SIZES).toContain(14);
  });

  it("LINE_HEIGHTS 升序且在 [1, 3] 范围", () => {
    for (let i = 1; i < LINE_HEIGHTS.length; i++) {
      expect(LINE_HEIGHTS[i]).toBeGreaterThan(LINE_HEIGHTS[i - 1]);
    }
    for (const lh of LINE_HEIGHTS) {
      expect(lh).toBeGreaterThanOrEqual(1);
      expect(lh).toBeLessThanOrEqual(3);
    }
  });
});
