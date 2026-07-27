/**
 * Widget · AI 助手浮卡 (assist-popover)
 * 占位 · 紫色边框 + 阴影 · AI 解答文本 + 2 个操作链接
 */
import type { CSSProperties } from "react";
import { registerWidget } from "./registry";
import { MUTED_TEXT, TITLE_TEXT } from "./shared";

const ACCENT = "var(--aos-accent)";

const cardStyle: CSSProperties = {
  position: "relative",
  padding: 14,
  borderRadius: 2,
  border: `1.5px solid ${ACCENT}`,
  background: "var(--aos-surface)",
  boxShadow: "0 10px 30px rgba(79, 70, 229, 0.22)",
  display: "flex",
  flexDirection: "column",
  gap: 10,
};

const headerStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
};

const badgeStyle: CSSProperties = {
  fontSize: 10,
  fontWeight: 700,
  letterSpacing: 0.4,
  textTransform: "uppercase",
  color: "#ffffff",
  background: ACCENT,
  padding: "2px 8px",
  borderRadius: 999,
};

const answerStyle: CSSProperties = {
  fontSize: 12.5,
  lineHeight: 1.6,
  color: "var(--aos-text)",
};

const linkRowStyle: CSSProperties = {
  display: "flex",
  gap: 14,
  borderTop: "1px dashed var(--aos-border)",
  paddingTop: 10,
};

const linkStyle: CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  color: ACCENT,
  cursor: "pointer",
  textDecoration: "none",
  display: "inline-flex",
  alignItems: "center",
  gap: 4,
};

function AssistPopoverWidget({ config }: { config: Record<string, any> }) {
  const title = String(config?.title ?? "Buddy 建议");

  return (
    <div style={cardStyle} role="dialog" aria-label={title}>
      <div style={headerStyle}>
        <span style={badgeStyle}>AI</span>
        <span style={TITLE_TEXT}>{title}</span>
      </div>

      <div style={answerStyle}>
        ORD-8821 命中风控规则 R-07（高频地址变更 + 异常支付）。建议先
        <strong>冻结库存</strong> 并由负责人 <strong>发起申诉</strong>，
        避免下游履约风险。
      </div>

      <div style={linkRowStyle}>
        <span style={linkStyle}>↗ 发起申诉</span>
        <span style={linkStyle}>❄ 冻结库存</span>
      </div>

      <div style={MUTED_TEXT}>基于 Ontology: Order + Wiki · 置信度 0.92</div>
    </div>
  );
}

registerWidget({
  type: "assist-popover",
  name: "AI 助手浮卡",
  icon: "✨",
  category: "ai",
  defaultConfig: {
    title: "Buddy 建议",
  },
  render: (config) => <AssistPopoverWidget config={config} />,
  propsSchema: [{ key: "title", label: "标题", type: "text" }],
});
