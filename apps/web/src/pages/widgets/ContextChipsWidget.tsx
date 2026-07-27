/**
 * Widget · 上下文 Chip 组 (context-chips)
 * 占位 · 蓝/紫/黄 三色 chip · 可点击样式
 */
import type { CSSProperties } from "react";
import { registerWidget } from "./registry";
import { CARD_STYLE, COLOR_MAP, MUTED_TEXT, TITLE_TEXT } from "./shared";

interface Chip {
  label: string;
  color: string;
}

const CHIPS: Chip[] = [
  { label: "Selection: ORD-8821", color: COLOR_MAP.blue },
  { label: "Ontology: Order + Wiki", color: COLOR_MAP.violet },
  { label: "查看决策谱系", color: COLOR_MAP.amber },
];

function chipStyle(color: string): CSSProperties {
  return {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    fontSize: 12,
    fontWeight: 500,
    padding: "5px 10px",
    borderRadius: 999,
    color: "#ffffff",
    background: color,
    cursor: "pointer",
    border: `1px solid ${color}`,
    boxShadow: "0 1px 2px rgba(0,0,0,0.06)",
    userSelect: "none",
  };
}

const dotStyle = (color: string): CSSProperties => ({
  width: 6,
  height: 6,
  borderRadius: "50%",
  background: "rgba(255,255,255,0.9)",
  outline: `2px solid ${color}`,
  outlineOffset: -2,
});

function ContextChipsWidget({ config }: { config: Record<string, any> }) {
  const title = String(config?.title ?? "上下文");

  return (
    <div style={{ ...CARD_STYLE, display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={TITLE_TEXT}>{title}</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {CHIPS.map((c, i) => (
          <span key={i} style={chipStyle(c.color)}>
            <span style={dotStyle(c.color)} />
            {c.label}
          </span>
        ))}
      </div>
      <div style={MUTED_TEXT}>点击 chip 切换 Buddy 上下文（占位）</div>
    </div>
  );
}

registerWidget({
  type: "context-chips",
  name: "上下文 Chip",
  icon: "🏷️",
  category: "ai",
  defaultConfig: {
    title: "上下文",
  },
  render: (config) => <ContextChipsWidget config={config} />,
  propsSchema: [{ key: "title", label: "标题", type: "text" }],
});
