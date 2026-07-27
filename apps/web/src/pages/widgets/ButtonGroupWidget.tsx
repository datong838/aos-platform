/**
 * Widget · 按钮组 (button-group)
 * 占位渲染 · 横向按钮组 · primary 紫底白字 / default 白底紫边
 * 配置 buttons 格式："发起申诉|primary,冻结库存|default,Assist|default"
 */
import type { CSSProperties } from "react";
import { registerWidget } from "./registry";
import { CARD_STYLE, TITLE_TEXT } from "./shared";

type ButtonVariant = "primary" | "default";

interface ButtonDef {
  label: string;
  variant: ButtonVariant;
}

const ACCENT = "var(--aos-accent)";

const DEFAULT_BUTTONS: ButtonDef[] = [
  { label: "发起申诉", variant: "primary" },
  { label: "冻结库存", variant: "default" },
  { label: "Assist", variant: "default" },
];

function parseButtons(raw: unknown): ButtonDef[] {
  const text = String(raw ?? "").trim();
  if (!text) return DEFAULT_BUTTONS;

  const out: ButtonDef[] = [];
  for (const part of text.split(",")) {
    const seg = part.trim();
    if (!seg) continue;
    const [labelRaw, variantRaw] = seg.split("|");
    const label = (labelRaw ?? "").trim();
    if (!label) continue;
    const variant: ButtonVariant = variantRaw?.trim() === "primary" ? "primary" : "default";
    out.push({ label, variant });
  }
  return out.length >= 1 ? out : DEFAULT_BUTTONS;
}

const groupStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 8,
  marginTop: 8,
};

const baseBtn: CSSProperties = {
  padding: "7px 14px",
  fontSize: 12,
  fontWeight: 600,
  borderRadius: 2,
  cursor: "pointer",
  border: "1px solid transparent",
  lineHeight: 1.2,
};

const primaryBtn: CSSProperties = {
  ...baseBtn,
  background: ACCENT,
  color: "#ffffff",
  border: "1px solid var(--aos-accent)",
  boxShadow: "0 4px 12px rgba(79, 70, 229, 0.25)",
};

const defaultBtn: CSSProperties = {
  ...baseBtn,
  background: "var(--aos-surface)",
  color: ACCENT,
  border: `1px solid ${ACCENT}`,
};

function ButtonGroupWidget({ config }: { config: Record<string, any> }) {
  const title = String(config?.title ?? "操作");
  const buttons = parseButtons(config?.buttons);

  return (
    <div style={CARD_STYLE}>
      <div style={TITLE_TEXT}>{title}</div>
      <div style={groupStyle} role="group" aria-label={title}>
        {buttons.map((b, i) => (
          <button
            key={`${b.label}-${i}`}
            type="button"
            style={b.variant === "primary" ? primaryBtn : defaultBtn}
          >
            {b.label}
          </button>
        ))}
      </div>
    </div>
  );
}

registerWidget({
  type: "button-group",
  name: "按钮组",
  icon: "🔘",
  category: "action",
  defaultConfig: {
    title: "操作",
    buttons: "发起申诉|primary,冻结库存|default,Assist|default",
  },
  render: (config) => <ButtonGroupWidget config={config} />,
  propsSchema: [
    { key: "title", label: "标题", type: "text" },
    {
      key: "buttons",
      label: "按钮(逗号分隔)",
      type: "text",
      placeholder: "发起申诉|primary,冻结库存|default",
    },
  ],
});
