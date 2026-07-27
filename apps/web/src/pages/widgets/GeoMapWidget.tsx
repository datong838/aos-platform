/**
 * Widget · 地图 (geo-map)
 * SVG 自绘 · 风格化世界轮廓 + 点阵底纹 + 彩色定位点 · 占位渲染
 */
import { registerWidget } from "./registry";
import { CARD_STYLE, MUTED_TEXT, TITLE_TEXT, COLOR_MAP } from "./shared";

const VIEW_W = 320;
const VIEW_H = 180;

interface Continent {
  cx: number;
  cy: number;
  rx: number;
  ry: number;
}

const CONTINENTS: Continent[] = [
  { cx: 70, cy: 58, rx: 34, ry: 24 },
  { cx: 96, cy: 132, rx: 16, ry: 28 },
  { cx: 178, cy: 52, rx: 56, ry: 26 },
  { cx: 172, cy: 112, rx: 22, ry: 30 },
  { cx: 262, cy: 138, rx: 22, ry: 14 },
];

interface Pin {
  x: number;
  y: number;
  color: string;
}

const PINS: Pin[] = [
  { x: 60, y: 54, color: COLOR_MAP.blue },
  { x: 198, y: 48, color: COLOR_MAP.green },
  { x: 176, y: 116, color: COLOR_MAP.amber },
  { x: 258, y: 138, color: COLOR_MAP.red },
];

const GRID_STEP = 12;

function GeoMapWidget({ config }: { config: Record<string, any> }) {
  const title = String(config?.title ?? "全球站点分布");

  const dots: { x: number; y: number }[] = [];
  for (let x = GRID_STEP; x < VIEW_W; x += GRID_STEP) {
    for (let y = GRID_STEP; y < VIEW_H - 8; y += GRID_STEP) {
      dots.push({ x, y });
    }
  }

  return (
    <div style={CARD_STYLE}>
      <div style={{ ...TITLE_TEXT, marginBottom: 8 }}>{title}</div>
      <svg viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} width="100%" height="180" role="img" aria-label={title}>
        <rect x={0} y={0} width={VIEW_W} height={VIEW_H} fill="var(--aos-bg)" opacity={0.5} />

        <g fill="var(--aos-text-muted)" opacity={0.22}>
          {dots.map((d, i) => (
            <circle key={i} cx={d.x} cy={d.y} r={0.9} />
          ))}
        </g>

        <g fill="var(--aos-text-muted)" opacity={0.35}>
          {CONTINENTS.map((c, i) => (
            <ellipse key={i} cx={c.cx} cy={c.cy} rx={c.rx} ry={c.ry} />
          ))}
        </g>

        <g>
          {PINS.map((p, i) => (
            <g key={i}>
              <circle cx={p.x} cy={p.y} r={10} fill={p.color} opacity={0.18} />
              <circle cx={p.x} cy={p.y} r={5} fill={p.color} opacity={0.45} />
              <circle cx={p.x} cy={p.y} r={2.4} fill={p.color} />
            </g>
          ))}
        </g>
      </svg>
      <div style={{ ...MUTED_TEXT, display: "flex", gap: 14, flexWrap: "wrap", marginTop: 6 }}>
        <LegendDot color={COLOR_MAP.blue} text="主站点" />
        <LegendDot color={COLOR_MAP.green} text="区域中心" />
        <LegendDot color={COLOR_MAP.amber} text="仓储" />
        <LegendDot color={COLOR_MAP.red} text="告警" />
      </div>
    </div>
  );
}

function LegendDot({ color, text }: { color: string; text: string }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
      <span
        style={{
          display: "inline-block",
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: color,
        }}
      />
      {text}
    </span>
  );
}

registerWidget({
  type: "geo-map",
  name: "地图",
  icon: "🗺️",
  category: "chart",
  defaultConfig: {
    title: "全球站点分布",
  },
  render: (config) => <GeoMapWidget config={config} />,
  propsSchema: [{ key: "title", label: "标题", type: "text" }],
});
