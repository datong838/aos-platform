/**
 * Widget · 实时事件流 (event-stream)
 * 占位渲染 · 5 条事件 · 彩色圆点（红/黄/蓝）+ 时间戳 + 文本 · 整体可滚动
 */
import type { CSSProperties } from "react";
import { registerWidget } from "./registry";
import { CARD_STYLE, MUTED_TEXT, TITLE_TEXT } from "./shared";

interface StreamEvent {
  level: "danger" | "warning" | "info";
  time: string;
  text: string;
}

const LEVEL_COLOR: Record<StreamEvent["level"], string> = {
  danger: "#ef4444",
  warning: "#f59e0b",
  info: "#3b82f6",
};

const DEMO: StreamEvent[] = [
  { level: "danger", time: "10:12:03", text: "ORD-8821 命中风控规则 R-07" },
  { level: "warning", time: "10:11:48", text: "华东 F2 产能低于阈值 60%" },
  { level: "info", time: "10:10:21", text: "Buddy 已接入会话上下文" },
  { level: "warning", time: "10:09:55", text: "SKU-3301 库存预计 2h 内告罄" },
  { level: "info", time: "10:08:12", text: "日报同步完成，共 18 条指标" },
];

const headerStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
};

const liveDotStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
  fontSize: 10,
  fontWeight: 700,
  letterSpacing: 0.4,
  color: "#10b981",
};

const pulseStyle: CSSProperties = {
  width: 6,
  height: 6,
  borderRadius: "50%",
  background: "#10b981",
  display: "inline-block",
  boxShadow: "0 0 0 3px rgba(16,185,129,0.25)",
};

const scrollStyle: CSSProperties = {
  marginTop: 10,
  display: "flex",
  flexDirection: "column",
  gap: 2,
  maxHeight: 220,
  overflowY: "auto",
  paddingRight: 4,
};

const rowStyle: CSSProperties = {
  display: "flex",
  alignItems: "flex-start",
  gap: 10,
  padding: "8px 4px",
  borderBottom: "1px dashed var(--aos-border)",
};

const dotStyle = (color: string): CSSProperties => ({
  width: 8,
  height: 8,
  borderRadius: "50%",
  background: color,
  display: "inline-block",
  marginTop: 4,
  flexShrink: 0,
  boxShadow: `0 0 0 2px ${color}33`,
});

const bodyStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 2,
  flex: 1,
  minWidth: 0,
};

const timeStyle: CSSProperties = {
  ...MUTED_TEXT,
  fontSize: 10,
  fontVariantNumeric: "tabular-nums",
};

const textStyle: CSSProperties = {
  fontSize: 12,
  lineHeight: 1.45,
  color: "var(--aos-text)",
  wordBreak: "break-word",
};

function EventStreamWidget({ config }: { config: Record<string, any> }) {
  const title = String(config?.title ?? "实时事件流");

  return (
    <div style={CARD_STYLE}>
      <div style={headerStyle}>
        <div style={TITLE_TEXT}>{title}</div>
        <span style={liveDotStyle}>
          <span style={pulseStyle} />
          LIVE
        </span>
      </div>
      <div style={scrollStyle}>
        {DEMO.map((ev, i) => {
          const color = LEVEL_COLOR[ev.level];
          return (
            <div key={i} style={rowStyle}>
              <span style={dotStyle(color)} />
              <div style={bodyStyle}>
                <span style={timeStyle}>{ev.time}</span>
                <span style={textStyle}>{ev.text}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

registerWidget({
  type: "event-stream",
  name: "实时事件流",
  icon: "📡",
  category: "time",
  defaultConfig: {
    title: "实时事件流",
  },
  render: (config) => <EventStreamWidget config={config} />,
  propsSchema: [{ key: "title", label: "标题", type: "text" }],
});
