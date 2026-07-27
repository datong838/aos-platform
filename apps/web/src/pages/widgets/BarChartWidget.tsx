/**
 * Widget · 柱状图 (bar-chart)
 * SVG 自绘 · 占位渲染 · 不依赖外部图表库
 */
import { registerWidget } from "./registry";
import { CARD_STYLE, MUTED_TEXT, TITLE_TEXT, COLOR_MAP } from "./shared";

const VIEW_W = 320;
const VIEW_H = 180;
const PAD_LEFT = 32;
const PAD_RIGHT = 12;
const PAD_TOP = 12;
const PAD_BOTTOM = 24;

function parseSeries(raw: string): number[] {
  const out: number[] = [];
  for (const part of String(raw || "").split(",")) {
    const n = Number(part.trim());
    if (Number.isFinite(n) && n >= 0) out.push(n);
  }
  return out;
}

function BarChartWidget({ config }: { config: Record<string, any> }) {
  const title = String(config?.title ?? "柱状图");
  const colorKey = String(config?.color ?? "indigo");
  const barColor = COLOR_MAP[colorKey] || COLOR_MAP.indigo;

  const data = parseSeries(config?.series);
  const values = data.length >= 2 ? data : [12, 19, 8, 15, 22, 14];

  const chartW = VIEW_W - PAD_LEFT - PAD_RIGHT;
  const chartH = VIEW_H - PAD_TOP - PAD_BOTTOM;
  const baselineY = PAD_TOP + chartH;
  const max = Math.max(...values, 1);
  const slot = chartW / values.length;
  const barW = slot * 0.6;

  const ticks = [0, 0.5, 1].map((r) => Math.round(max * r));

  return (
    <div style={CARD_STYLE}>
      <div style={{ ...TITLE_TEXT, marginBottom: 8 }}>{title}</div>
      <svg
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        width="100%"
        height="160"
        role="img"
        aria-label={title}
      >
        {ticks.map((t, i) => {
          const y = baselineY - (t / max) * chartH;
          return (
            <g key={i}>
              <line
                x1={PAD_LEFT}
                x2={VIEW_W - PAD_RIGHT}
                y1={y}
                y2={y}
                stroke="var(--aos-border)"
                strokeWidth={1}
                strokeDasharray={i === 0 ? undefined : "2 4"}
                opacity={i === 0 ? 0.9 : 0.5}
              />
              <text x={PAD_LEFT - 6} y={y + 3} textAnchor="end" fontSize={9} fill="var(--aos-text-muted)">
                {t}
              </text>
            </g>
          );
        })}

        {values.map((v, i) => {
          const h = (v / max) * chartH;
          const x = PAD_LEFT + slot * i + (slot - barW) / 2;
          const y = baselineY - h;
          return (
            <g key={i}>
              <rect x={x} y={y} width={barW} height={h} rx={3} fill={barColor} />
              <text
                x={x + barW / 2}
                y={y - 4}
                textAnchor="middle"
                fontSize={9}
                fill="var(--aos-text)"
                fontWeight={600}
              >
                {v}
              </text>
            </g>
          );
        })}

        <line
          x1={PAD_LEFT}
          x2={VIEW_W - PAD_RIGHT}
          y1={baselineY}
          y2={baselineY}
          stroke="var(--aos-text-muted)"
          strokeWidth={1}
        />
      </svg>
      <div style={MUTED_TEXT}>共 {values.length} 项 · 最大值 {max}</div>
    </div>
  );
}

registerWidget({
  type: "bar-chart",
  name: "柱状图",
  icon: "📊",
  category: "chart",
  defaultConfig: {
    title: "周度产量",
    series: "12,19,8,15,22,14,18,11",
    color: "indigo",
  },
  render: (config) => <BarChartWidget config={config} />,
  propsSchema: [
    { key: "title", label: "标题", type: "text" },
    { key: "series", label: "数据(逗号分隔)", type: "text", placeholder: "如 12,19,8,15" },
    {
      key: "color",
      label: "颜色",
      type: "select",
      options: Object.keys(COLOR_MAP).map((k) => ({ label: k, value: k })),
    },
  ],
});
