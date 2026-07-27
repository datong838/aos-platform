/**
 * Widget · 拓扑图 / 网络图 (network-graph)
 * SVG 自绘 · 中央节点 + 外围节点 + 虚线连线 · 占位渲染
 */
import { registerWidget } from "./registry";
import { CARD_STYLE, MUTED_TEXT, TITLE_TEXT, COLOR_MAP, seededRand } from "./shared";

const PALETTE = Object.values(COLOR_MAP);
const CX = 160;
const CY = 100;
const RADIUS = 76;
const VIEW_W = 320;
const VIEW_H = 200;

interface NodePos {
  x: number;
  y: number;
  label: string;
  color: string;
}

const NODE_LABELS = ["供应商 A", "工厂 B", "仓储 C", "物流 D", "客户 E", "上游 F"];

function buildNodes(): NodePos[] {
  const count = NODE_LABELS.length;
  return NODE_LABELS.map((label, i) => {
    const jitter = (seededRand(i + 1) - 0.5) * 0.18;
    const ang = (i / count) * Math.PI * 2 - Math.PI / 2 + jitter;
    return {
      x: CX + Math.cos(ang) * RADIUS,
      y: CY + Math.sin(ang) * RADIUS,
      label,
      color: PALETTE[i % PALETTE.length],
    };
  });
}

function NetworkGraphWidget({ config }: { config: Record<string, any> }) {
  const title = String(config?.title ?? "供应链拓扑");
  const nodes = buildNodes();

  return (
    <div style={CARD_STYLE}>
      <div style={{ ...TITLE_TEXT, marginBottom: 8 }}>{title}</div>
      <svg viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} width="100%" height="190" role="img" aria-label={title}>
        <g stroke="var(--aos-border)" strokeWidth={1.2} strokeDasharray="4 4">
          {nodes.map((n, i) => (
            <line key={`e-${i}`} x1={CX} y1={CY} x2={n.x} y2={n.y} />
          ))}
        </g>

        <g>
          {nodes.map((n, i) => (
            <g key={`n-${i}`}>
              <circle cx={n.x} cy={n.y} r={15} fill={n.color} opacity={0.92} />
              <circle cx={n.x} cy={n.y} r={15} fill="none" stroke="var(--aos-surface)" strokeWidth={2} />
              <text
                x={n.x}
                y={n.y + 28}
                textAnchor="middle"
                fontSize={10}
                fill="var(--aos-text)"
              >
                {n.label}
              </text>
            </g>
          ))}
        </g>

        <circle cx={CX} cy={CY} r={24} fill="var(--aos-accent)" />
        <circle cx={CX} cy={CY} r={24} fill="none" stroke="var(--aos-surface)" strokeWidth={2} />
        <text x={CX} y={CY - 1} textAnchor="middle" fontSize={11} fontWeight={700} fill="#ffffff">
          核心
        </text>
        <text x={CX} y={CY + 11} textAnchor="middle" fontSize={8} fill="#ffffff" opacity={0.85}>
          hub
        </text>
      </svg>
      <div style={MUTED_TEXT}>1 核心 · {nodes.length} 外围节点</div>
    </div>
  );
}

registerWidget({
  type: "network-graph",
  name: "拓扑图",
  icon: "🕸️",
  category: "chart",
  defaultConfig: {
    title: "供应链拓扑",
  },
  render: (config) => <NetworkGraphWidget config={config} />,
  propsSchema: [{ key: "title", label: "标题", type: "text" }],
});
