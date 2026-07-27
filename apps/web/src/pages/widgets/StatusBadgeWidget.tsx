/**
 * Widget · 状态徽章 (status-badge)
 * 占位渲染 · 单个圆点 + 文字 · success/warning/danger/info 四色
 */
import type { CSSProperties } from "react";
import { registerWidget } from "./registry";
import { CARD_STYLE } from "./shared";

type BadgeStatus = "success" | "warning" | "danger" | "info";

const STATUS_COLOR: Record<BadgeStatus, string> = {
  success: "#10b981",
  warning: "#f59e0b",
  danger: "#ef4444",
  info: "#3b82f6",
};

const STATUS_LABEL: Record<BadgeStatus, string> = {
  success: "正常",
  warning: "预警",
  danger: "告警",
  info: "信息",
};

function resolveStatus(raw: unknown): BadgeStatus {
  const v = String(raw ?? "info");
  return v in STATUS_COLOR ? (v as BadgeStatus) : "info";
}

const badgeStyle = (color: string): CSSProperties => ({
  display: "inline-flex",
  alignItems: "center",
  gap: 8,
  padding: "6px 12px",
  borderRadius: 999,
  border: `1px solid ${color}`,
  background: `${color}1a`,
  fontSize: 12,
  fontWeight: 600,
  color: "var(--aos-text)",
  width: "fit-content",
});

const dotStyle = (color: string): CSSProperties => ({
  width: 8,
  height: 8,
  borderRadius: "50%",
  background: color,
  display: "inline-block",
  boxShadow: `0 0 0 3px ${color}33`,
});

function StatusBadgeWidget({ config }: { config: Record<string, any> }) {
  const label = String(config?.label ?? "状态");
  const status = resolveStatus(config?.status);
  const color = STATUS_COLOR[status];
  const text = config?.label ? label : STATUS_LABEL[status];

  return (
    <div style={CARD_STYLE}>
      <span style={badgeStyle(color)} role="status" aria-label={text}>
        <span style={dotStyle(color)} />
        {text}
      </span>
    </div>
  );
}

registerWidget({
  type: "status-badge",
  name: "状态徽章",
  icon: "🏷️",
  category: "data",
  defaultConfig: {
    label: "正常",
    status: "success",
  },
  render: (config) => <StatusBadgeWidget config={config} />,
  propsSchema: [
    { key: "label", label: "文字", type: "text", placeholder: "留空则使用状态默认名" },
    {
      key: "status",
      label: "状态",
      type: "select",
      options: [
        { label: "正常 success", value: "success" },
        { label: "预警 warning", value: "warning" },
        { label: "告警 danger", value: "danger" },
        { label: "信息 info", value: "info" },
      ],
    },
  ],
});
