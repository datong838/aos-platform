import { useMemo } from "react";

export function BpSparkline({
  data,
  width = 120,
  height = 28,
  stroke,
  fill = true,
  ariaLabel,
}: {
  data: number[];
  width?: number;
  height?: number;
  stroke?: string;
  fill?: boolean;
  ariaLabel?: string;
}) {
  const path = useMemo(() => buildPath(data, width, height), [data, width, height]);
  if (data.length === 0) {
    return (
      <span className="bp-sparkline" aria-label={ariaLabel ?? "趋势图"}>
        <svg width={width} height={height} role="img" aria-label={ariaLabel ?? "趋势图"}>
          <line
            x1={0}
            y1={height - 1}
            x2={width}
            y2={height - 1}
            stroke="var(--aos-divider)"
            strokeWidth={1}
          />
        </svg>
      </span>
    );
  }
  const strokeColor = stroke ?? "var(--aos-accent)";
  return (
    <span className="bp-sparkline">
      <svg width={width} height={height} role="img" aria-label={ariaLabel ?? "趋势图"}>
        {fill ? <path d={path.area} fill={strokeColor} opacity={0.12} /> : null}
        <path
          d={path.line}
          stroke={strokeColor}
          strokeWidth={1.5}
          fill="none"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      </svg>
    </span>
  );
}

function buildPath(data: number[], width: number, height: number) {
  if (data.length === 0) return { line: "", area: "" };
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const pad = 2;
  const innerH = height - pad * 2;
  const stepX = data.length === 1 ? 0 : (width - pad * 2) / (data.length - 1);
  const points = data.map((v, i) => {
    const x = pad + i * stepX;
    const y = pad + innerH - ((v - min) / range) * innerH;
    return { x, y };
  });
  const line = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(2)},${p.y.toFixed(2)}`)
    .join(" ");
  const area = `${line} L${points[points.length - 1].x.toFixed(2)},${height} L${points[0].x.toFixed(2)},${height} Z`;
  return { line, area };
}
