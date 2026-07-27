/**
 * Widget · Buddy 头像卡片 (buddy-chip)
 * 占位 · 圆形头像 + 名字 + "风控 Buddy" 标签 · 悬浮角落
 */
import type { CSSProperties } from "react";
import { registerWidget } from "./registry";
import { COLOR_MAP } from "./shared";

const ACCENT = "var(--aos-accent)";

const chipStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 10,
  padding: "6px 12px 6px 6px",
  borderRadius: 999,
  background: "var(--aos-surface)",
  border: "1px solid var(--aos-border)",
  boxShadow: "0 6px 18px rgba(79, 70, 229, 0.18)",
  cursor: "pointer",
  width: "fit-content",
};

const avatarStyle: CSSProperties = {
  width: 32,
  height: 32,
  borderRadius: "50%",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: 14,
  fontWeight: 700,
  color: "#ffffff",
  background: `linear-gradient(135deg, ${ACCENT}, ${COLOR_MAP.violet})`,
  flexShrink: 0,
};

const metaStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  lineHeight: 1.25,
};

const nameStyle: CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  color: "var(--aos-text)",
};

const tagStyle: CSSProperties = {
  fontSize: 10,
  fontWeight: 600,
  letterSpacing: 0.3,
  color: ACCENT,
  background: "rgba(79, 70, 229, 0.10)",
  padding: "1px 6px",
  borderRadius: 999,
  width: "fit-content",
};

function BuddyChipWidget({ config }: { config: Record<string, any> }) {
  const name = String(config?.name ?? "Aria");
  const initial = name.trim().charAt(0).toUpperCase() || "B";

  return (
    <div style={chipStyle} role="button" aria-label={`${name} · 风控 Buddy`}>
      <span style={avatarStyle}>{initial}</span>
      <span style={metaStyle}>
        <span style={nameStyle}>{name}</span>
        <span style={tagStyle}>风控 Buddy</span>
      </span>
    </div>
  );
}

registerWidget({
  type: "buddy-chip",
  name: "Buddy 头像",
  icon: "🤖",
  category: "ai",
  defaultConfig: {
    name: "Aria",
  },
  render: (config) => <BuddyChipWidget config={config} />,
  propsSchema: [{ key: "name", label: "名称", type: "text" }],
});
