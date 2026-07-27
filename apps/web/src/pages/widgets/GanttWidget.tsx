/**
 * Widget · 甘特图 (gantt)
 * 占位渲染 · SVG 自绘 · 左侧任务名 + 右侧横条 · 顶部 W1-W4 时间轴标尺
 */
import type { CSSProperties } from "react";
import { registerWidget } from "./registry";
import { CARD_STYLE, MUTED_TEXT, TITLE_TEXT, COLOR_MAP } from "./shared";

interface GanttTask {
  name: string;
  start: number;
  end: number;
  color: string;
}

const VIEW_W = 480;
const VIEW_H = 200;
const LEFT_PAD = 108;
const RIGHT_PAD = 10;
const TIME_H = 26;
const ROW_H = 32;
const BAR_H = 16;

const chartW = VIEW_W - LEFT_PAD - RIGHT_PAD;
const weekW = chartW / 4;
const weekCenters = [0, 1, 2, 3].map((i) => LEFT_PAD + weekW * (i + 0.5));

const TASKS: GanttTask[] = [
  { name: "规则评估", start: 0, end: 2, color: COLOR_MAP.indigo },
  { name: "库存冻结", start: 1, end: 3, color: COLOR_MAP.amber },
  { name: "申诉审核", start: 1, end: 4, color: COLOR_MAP.violet },
  { name: "复核完成", start: 2, end: 4, color: COLOR_MAP.green },
];

const wrapStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 6,
};

function GanttWidget({ config }: { config: Record<string, any> }) {
  const title = String(config?.title ?? "项目排期");

  return (
    <div style={CARD_STYLE}>
      <div style={{ ...TITLE_TEXT, marginBottom: 4 }}>{title}</div>
      <div style={wrapStyle}>
        <svg
          viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
          width="100%"
          height="180"
          role="img"
          aria-label={title}
        >
          {weekCenters.map((cx, i) => (
            <text
              key={`wk-${i}`}
              x={cx}
              y={16}
              textAnchor="middle"
              fontSize={10}
              fontWeight={700}
              fill="var(--aos-text-muted)"
            >
              {`W${i + 1}`}
            </text>
          ))}

          {[0, 1, 2, 3, 4].map((i) => {
            const x = LEFT_PAD + weekW * i;
            return (
              <line
                key={`grid-${i}`}
                x1={x}
                x2={x}
                y1={TIME_H}
                y2={VIEW_H - 4}
                stroke="var(--aos-border)"
                strokeWidth={1}
                strokeDasharray={i === 0 ? undefined : "2 4"}
                opacity={i === 0 ? 0.9 : 0.55}
              />
            );
          })}

          <line
            x1={LEFT_PAD}
            x2={VIEW_W - RIGHT_PAD}
            y1={TIME_H}
            y2={TIME_H}
            stroke="var(--aos-text-muted)"
            strokeWidth={1}
          />

          {TASKS.map((t, i) => {
            const rowY = TIME_H + 10 + ROW_H * i;
            const barY = rowY + (ROW_H - BAR_H) / 2;
            const x = LEFT_PAD + weekW * t.start;
            const w = weekW * (t.end - t.start);
            return (
              <g key={t.name}>
                <text
                  x={LEFT_PAD - 8}
                  y={barY + BAR_H / 2 + 3}
                  textAnchor="end"
                  fontSize={11}
                  fontWeight={600}
                  fill="var(--aos-text)"
                >
                  {t.name}
                </text>
                <rect x={x} y={barY} width={w} height={BAR_H} rx={4} fill={t.color} opacity={0.9} />
                <text
                  x={x + w / 2}
                  y={barY + BAR_H / 2 + 3}
                  textAnchor="middle"
                  fontSize={9}
                  fontWeight={700}
                  fill="#ffffff"
                >
                  {`W${t.start + 1}-W${t.end}`}
                </text>
              </g>
            );
          })}
        </svg>
        <div style={MUTED_TEXT}>{TASKS.length} 个任务 · 跨 4 周</div>
      </div>
    </div>
  );
}

registerWidget({
  type: "gantt",
  name: "甘特图",
  icon: "📅",
  category: "extra",
  defaultConfig: {
    title: "项目排期",
  },
  render: (config) => <GanttWidget config={config} />,
  propsSchema: [{ key: "title", label: "标题", type: "text" }],
});
