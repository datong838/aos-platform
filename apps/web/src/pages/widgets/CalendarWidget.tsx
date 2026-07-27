/**
 * Widget · 月历 (calendar)
 * 占位渲染 · CSS Grid 7 列 · 当前月份 · 今天紫底高亮 · 事件日带圆点
 */
import type { CSSProperties } from "react";
import { registerWidget } from "./registry";
import { CARD_STYLE, MUTED_TEXT, TITLE_TEXT } from "./shared";

const ACCENT = "var(--aos-accent)";
const WEEK_HEADERS = ["一", "二", "三", "四", "五", "六", "日"];
const EVENT_DAYS = new Set([5, 12, 18, 22, 27]);

const headerRowStyle: CSSProperties = {
  display: "flex",
  alignItems: "baseline",
  justifyContent: "space-between",
  marginBottom: 8,
};

const monthLabelStyle: CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  color: ACCENT,
};

const gridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(7, 1fr)",
  gap: 2,
};

const weekCellStyle: CSSProperties = {
  textAlign: "center",
  fontSize: 10,
  fontWeight: 700,
  color: "var(--aos-text-muted)",
  padding: "4px 0",
};

const cellStyle: CSSProperties = {
  position: "relative",
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  gap: 2,
  aspectRatio: "1 / 1",
  borderRadius: 2,
  fontSize: 12,
  color: "var(--aos-text)",
};

const emptyCellStyle: CSSProperties = {
  ...cellStyle,
  color: "var(--aos-text-muted)",
  opacity: 0.35,
};

const todayBadgeStyle: CSSProperties = {
  width: 24,
  height: 24,
  borderRadius: "50%",
  background: ACCENT,
  color: "#ffffff",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: 12,
  fontWeight: 700,
  boxShadow: "0 4px 10px rgba(79, 70, 229, 0.35)",
};

const dayNumStyle: CSSProperties = {
  fontSize: 12,
  fontWeight: 500,
  color: "var(--aos-text)",
};

const eventDotStyle: CSSProperties = {
  width: 4,
  height: 4,
  borderRadius: "50%",
  background: ACCENT,
  display: "inline-block",
};

function buildMonthLabel(raw: unknown, today: Date): string {
  const text = String(raw ?? "").trim();
  if (text) return text;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "long",
  }).format(today);
}

function CalendarWidget({ config }: { config: Record<string, any> }) {
  const title = String(config?.title ?? "月历");
  const today = new Date();
  const monthLabel = buildMonthLabel(config?.month, today);

  const year = today.getFullYear();
  const month = today.getMonth();
  const todayDate = today.getDate();
  const firstWeekday = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const leadBlanks = (firstWeekday + 6) % 7;

  const cells: number[] = [];
  for (let i = 0; i < leadBlanks; i++) cells.push(0);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(0);

  return (
    <div style={CARD_STYLE}>
      <div style={TITLE_TEXT}>{title}</div>

      <div style={headerRowStyle}>
        <span style={monthLabelStyle}>{monthLabel}</span>
        <span style={MUTED_TEXT}>{EVENT_DAYS.size} 个事件</span>
      </div>

      <div style={gridStyle}>
        {WEEK_HEADERS.map((w) => (
          <div key={w} style={weekCellStyle}>
            {w}
          </div>
        ))}

        {cells.map((d, i) => {
          if (d === 0) {
            return <div key={`e-${i}`} style={emptyCellStyle} />;
          }
          const isToday = d === todayDate;
          const hasEvent = EVENT_DAYS.has(d);
          return (
            <div key={`d-${d}`} style={cellStyle}>
              {isToday ? (
                <span style={todayBadgeStyle}>{d}</span>
              ) : (
                <span style={dayNumStyle}>{d}</span>
              )}
              {hasEvent && !isToday ? <span style={eventDotStyle} /> : <span />}
            </div>
          );
        })}
      </div>
    </div>
  );
}

registerWidget({
  type: "calendar",
  name: "月历",
  icon: "🗓️",
  category: "extra",
  defaultConfig: {
    title: "月历",
    month: "",
  },
  render: (config) => <CalendarWidget config={config} />,
  propsSchema: [
    { key: "title", label: "标题", type: "text" },
    {
      key: "month",
      label: "月份标签",
      type: "text",
      placeholder: "留空则显示当前月份",
    },
  ],
});
