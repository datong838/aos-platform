/**
 * Widget · 时间线 (timeline)
 * 占位渲染 · 垂直时间线 · 左侧彩色圆点 + 竖线 · 时间 / 标题 / 描述
 */
import type { CSSProperties } from "react";
import { registerWidget } from "./registry";
import { CARD_STYLE, MUTED_TEXT, TITLE_TEXT } from "./shared";
import { COLOR_MAP } from "./shared";

interface TimelineItem {
  time: string;
  title: string;
  desc: string;
  color: string;
}

const DEMO: TimelineItem[] = [
  {
    time: "10:02",
    title: "规则 R-07 命中",
    desc: "ORD-8821 触发高频地址变更告警。",
    color: COLOR_MAP.red,
  },
  {
    time: "10:05",
    title: "库存冻结",
    desc: "关联 SKU 已临时冻结，等待复核。",
    color: COLOR_MAP.amber,
  },
  {
    time: "10:08",
    title: "Buddy 介入",
    desc: "已生成处置建议并通知负责人。",
    color: COLOR_MAP.indigo,
  },
  {
    time: "10:12",
    title: "申诉发起",
    desc: "工单 #WO-3310 已创建，进入审核队列。",
    color: COLOR_MAP.green,
  },
];

const listStyle: CSSProperties = {
  position: "relative",
  marginTop: 10,
  paddingLeft: 4,
};

const lineStyle: CSSProperties = {
  position: "absolute",
  left: 11,
  top: 6,
  bottom: 6,
  width: 2,
  background: "var(--aos-border)",
};

const rowStyle: CSSProperties = {
  position: "relative",
  paddingLeft: 30,
  paddingBottom: 16,
};

const dotStyle = (color: string): CSSProperties => ({
  position: "absolute",
  left: 4,
  top: 2,
  width: 14,
  height: 14,
  borderRadius: "50%",
  background: "var(--aos-surface)",
  border: `3px solid ${color}`,
  boxSizing: "border-box",
});

const timeStyle: CSSProperties = {
  ...MUTED_TEXT,
  fontSize: 10,
  marginBottom: 2,
};

const titleRowStyle: CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  color: "var(--aos-text)",
  marginBottom: 2,
};

const descStyle: CSSProperties = {
  fontSize: 12,
  lineHeight: 1.5,
  color: "var(--aos-text-muted)",
};

function TimelineWidget({ config }: { config: Record<string, any> }) {
  const title = String(config?.title ?? "事件时间线");

  return (
    <div style={CARD_STYLE}>
      <div style={TITLE_TEXT}>{title}</div>
      <div style={listStyle}>
        <span style={lineStyle} />
        {DEMO.map((it, i) => (
          <div key={i} style={rowStyle}>
            <span style={dotStyle(it.color)} />
            <div style={timeStyle}>{it.time}</div>
            <div style={titleRowStyle}>{it.title}</div>
            <div style={descStyle}>{it.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

registerWidget({
  type: "timeline",
  name: "时间线",
  icon: "🕒",
  category: "time",
  defaultConfig: {
    title: "事件时间线",
  },
  render: (config) => <TimelineWidget config={config} />,
  propsSchema: [{ key: "title", label: "标题", type: "text" }],
});
