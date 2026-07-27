/**
 * Widget · 下钻面板 (drill-panel)
 * 占位渲染 · 3 张可点击卡片（华东 F1/F2、华南 F3）· 状态徽章 + 3 KPI · 整体可滚动
 */
import type { CSSProperties } from "react";
import { registerWidget } from "./registry";
import { CARD_STYLE, MUTED_TEXT, TITLE_TEXT } from "./shared";

type FactoryStatus = "running" | "stopped";

interface DrillItem {
  name: string;
  status: FactoryStatus;
  kpi: { running: string; capacity: string; leadTime: string };
}

const DEMO: DrillItem[] = [
  {
    name: "华东 F1",
    status: "running",
    kpi: { running: "92%", capacity: "1.2K/日", leadTime: "3 天" },
  },
  {
    name: "华东 F2",
    status: "stopped",
    kpi: { running: "0%", capacity: "0/日", leadTime: "—" },
  },
  {
    name: "华南 F3",
    status: "running",
    kpi: { running: "78%", capacity: "980/日", leadTime: "5 天" },
  },
];

const scrollStyle: CSSProperties = {
  marginTop: 8,
  display: "flex",
  flexDirection: "column",
  gap: 10,
  maxHeight: 260,
  overflowY: "auto",
  paddingRight: 4,
};

const itemStyle: CSSProperties = {
  padding: 12,
  borderRadius: 2,
  border: "1px solid var(--aos-border)",
  background: "var(--aos-bg)",
  cursor: "pointer",
  display: "flex",
  flexDirection: "column",
  gap: 10,
  transition: "border-color 0.15s",
};

const itemHeadStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
};

const itemNameStyle: CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  color: "var(--aos-text)",
};

const badgeBase: CSSProperties = {
  fontSize: 10,
  fontWeight: 700,
  letterSpacing: 0.3,
  padding: "2px 8px",
  borderRadius: 999,
  display: "inline-flex",
  alignItems: "center",
  gap: 4,
};

const badgeRunning: CSSProperties = {
  ...badgeBase,
  color: "#059669",
  background: "rgba(16, 185, 129, 0.14)",
};

const badgeStopped: CSSProperties = {
  ...badgeBase,
  color: "#dc2626",
  background: "rgba(239, 68, 68, 0.14)",
};

const dotStyle = (color: string): CSSProperties => ({
  width: 6,
  height: 6,
  borderRadius: "50%",
  background: color,
  display: "inline-block",
});

const kpiRowStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(3, 1fr)",
  gap: 8,
};

const kpiBlockStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 2,
};

const kpiValueStyle: CSSProperties = {
  fontSize: 13,
  fontWeight: 700,
  color: "var(--aos-text)",
};

function DrillPanelWidget({ config }: { config: Record<string, any> }) {
  const title = String(config?.title ?? "工厂下钻");

  return (
    <div style={CARD_STYLE}>
      <div style={TITLE_TEXT}>{title}</div>
      <div style={scrollStyle}>
        {DEMO.map((it) => {
          const running = it.status === "running";
          return (
            <div key={it.name} style={itemStyle} role="button" tabIndex={0} aria-label={`${it.name} 下钻`}>
              <div style={itemHeadStyle}>
                <span style={itemNameStyle}>{it.name}</span>
                <span style={running ? badgeRunning : badgeStopped}>
                  <span style={dotStyle(running ? "#10b981" : "#ef4444")} />
                  {running ? "在产" : "停机"}
                </span>
              </div>
              <div style={kpiRowStyle}>
                <div style={kpiBlockStyle}>
                  <span style={MUTED_TEXT}>在产</span>
                  <span style={kpiValueStyle}>{it.kpi.running}</span>
                </div>
                <div style={kpiBlockStyle}>
                  <span style={MUTED_TEXT}>产能</span>
                  <span style={kpiValueStyle}>{it.kpi.capacity}</span>
                </div>
                <div style={kpiBlockStyle}>
                  <span style={MUTED_TEXT}>交期</span>
                  <span style={kpiValueStyle}>{it.kpi.leadTime}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

registerWidget({
  type: "drill-panel",
  name: "下钻面板",
  icon: "🔍",
  category: "data",
  defaultConfig: {
    title: "工厂下钻",
  },
  render: (config) => <DrillPanelWidget config={config} />,
  propsSchema: [{ key: "title", label: "标题", type: "text" }],
});
