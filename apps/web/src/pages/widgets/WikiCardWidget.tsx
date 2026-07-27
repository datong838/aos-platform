/**
 * Widget · 知识卡片 (wiki-card)
 * 占位渲染 · 橙色高亮 · 左竖条强调 · 标题 + 来源 + 内容
 */
import type { CSSProperties } from "react";
import { registerWidget } from "./registry";

const ACCENT = "#f59e0b";

const cardStyle: CSSProperties = {
  position: "relative",
  padding: "14px 16px 14px 18px",
  borderRadius: 2,
  border: `1px solid ${ACCENT}`,
  background: "rgba(245, 158, 11, 0.08)",
  overflow: "hidden",
};

const barStyle: CSSProperties = {
  position: "absolute",
  left: 0,
  top: 0,
  bottom: 0,
  width: 4,
  background: ACCENT,
};

const titleStyle: CSSProperties = {
  fontSize: 14,
  fontWeight: 700,
  color: "var(--aos-text)",
  marginBottom: 4,
};

const sourceStyle: CSSProperties = {
  fontSize: 11,
  fontWeight: 600,
  letterSpacing: 0.3,
  color: ACCENT,
  marginBottom: 8,
};

const contentStyle: CSSProperties = {
  fontSize: 12.5,
  lineHeight: 1.6,
  color: "var(--aos-text)",
};

function WikiCardWidget({ config }: { config: Record<string, any> }) {
  const title = String(config?.title ?? "风控知识条目");
  const source = String(config?.source ?? "Wiki · R-07");
  const content = String(
    config?.content ??
      "当订单在 24h 内出现 ≥ 3 次收货地址变更，且伴随异常支付渠道时，应触发复核流程并临时冻结库存，避免下游履约风险。",
  );

  return (
    <div style={cardStyle} role="article" aria-label={title}>
      <span style={barStyle} />
      <div style={titleStyle}>{title}</div>
      <div style={sourceStyle}>来源：{source}</div>
      <div style={contentStyle}>{content}</div>
    </div>
  );
}

registerWidget({
  type: "wiki-card",
  name: "知识卡片",
  icon: "📚",
  category: "data",
  defaultConfig: {
    title: "风控知识条目",
    source: "Wiki · R-07",
    content:
      "当订单在 24h 内出现 ≥ 3 次收货地址变更，且伴随异常支付渠道时，应触发复核流程并临时冻结库存。",
  },
  render: (config) => <WikiCardWidget config={config} />,
  propsSchema: [
    { key: "title", label: "标题", type: "text" },
    { key: "source", label: "来源", type: "text" },
    { key: "content", label: "内容", type: "textarea" },
  ],
});
