/**
 * Widget · 饼图 / 圆环图 (pie-chart)
 * SVG 自绘 donut · 占位渲染
 */
import { registerWidget } from "./registry";
import { CARD_STYLE, MUTED_TEXT, TITLE_TEXT, COLOR_MAP } from "./shared";

interface Segment {
  label: string;
  value: number;
}

const PALETTE = Object.values(COLOR_MAP);
const CX = 78;
const CY = 92;
const R_OUT = 58;
const R_IN = 36;
const VIEW_W = 320;
const VIEW_H = 184;

function parseSegments(raw: string): Segment[] {
  const out: Segment[] = [];
  for (const part of String(raw || "").split(",")) {
    const seg = part.split(":");
    if (seg.length < 2) continue;
    const label = seg[0].trim();
    const value = Number(seg[1].trim());
    if (label && Number.isFinite(value) && value > 0) {
      out.push({ label, value });
    }
  }
  return out;
}

function polar(cx: number, cy: number, r: number, deg: number): { x: number; y: number } {
  const a = ((deg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
}

function donutPath(
  cx: number,
  cy: number,
  rOut: number,
  rIn: number,
  startDeg: number,
  endDeg: number,
): string {
  const large = endDeg - startDeg > 180 ? 1 : 0;
  const p1 = polar(cx, cy, rOut, startDeg);
  const p2 = polar(cx, cy, rOut, endDeg);
  const p3 = polar(cx, cy, rIn, endDeg);
  const p4 = polar(cx, cy, rIn, startDeg);
  return [
    `M ${p1.x.toFixed(2)} ${p1.y.toFixed(2)}`,
    `A ${rOut} ${rOut} 0 ${large} 1 ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`,
    `L ${p3.x.toFixed(2)} ${p3.y.toFixed(2)}`,
    `A ${rIn} ${rIn} 0 ${large} 0 ${p4.x.toFixed(2)} ${p4.y.toFixed(2)}`,
    "Z",
  ].join(" ");
}

function PieChartWidget({ config }: { config: Record<string, any> }) {
  const title = String(config?.title ?? "类别占比");
  const segs = parseSegments(config?.segments);
  const segments = segs.length >= 2 ? segs : [
    { label: "在线", value: 45 },
    { label: "离线", value: 25 },
    { label: "告警", value: 20 },
    { label: "故障", value: 10 },
  ];
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;

  let acc = 0;
  const arcs = segments.map((s, i) => {
    const start = (acc / total) * 360;
    acc += s.value;
    const end = (acc / total) * 360;
    return {
      ...s,
      color: PALETTE[i % PALETTE.length],
      pct: Math.round((s.value / total) * 100),
      d: donutPath(CX, CY, R_OUT, R_IN, start, Math.min(end, 359.99)),
    };
  });

  return (
    <div style={CARD_STYLE}>
      <div style={{ ...TITLE_TEXT, marginBottom: 8 }}>{title}</div>
      <svg viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} width="100%" height="180" role="img" aria-label={title}>
        <g>
          {arcs.map((a, i) => (
            <path key={i} d={a.d} fill={a.color} stroke="var(--aos-surface)" strokeWidth={1} />
          ))}
        </g>
        <text x={CX} y={CY - 2} textAnchor="middle" fontSize={20} fontWeight={700} fill="var(--aos-text)">
          {total}
        </text>
        <text x={CX} y={CY + 14} textAnchor="middle" fontSize={9} fill="var(--aos-text-muted)">
          合计
        </text>

        {arcs.map((a, i) => {
          const rowY = 24 + i * 22;
          return (
            <g key={`l-${i}`}>
              <rect x={168} y={rowY - 9} width={10} height={10} rx={2} fill={a.color} />
              <text x={184} y={rowY} fontSize={11} fill="var(--aos-text)">
                {a.label}
              </text>
              <text x={VIEW_W - 8} y={rowY} textAnchor="end" fontSize={11} fill="var(--aos-text-muted)">
                {a.pct}%
              </text>
            </g>
          );
        })}
      </svg>
      <div style={MUTED_TEXT}>{segments.length} 个分类</div>
    </div>
  );
}

registerWidget({
  type: "pie-chart",
  name: "饼图",
  icon: "🥧",
  category: "chart",
  defaultConfig: {
    title: "类别占比",
    segments: "在线:45,离线:25,告警:20,故障:10",
  },
  render: (config) => <PieChartWidget config={config} />,
  propsSchema: [
    { key: "title", label: "标题", type: "text" },
    { key: "segments", label: "分段(标签:值)", type: "text", placeholder: "如 A:30,B:40,C:30" },
  ],
});
