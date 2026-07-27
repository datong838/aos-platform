/**
 * Widget · 聊天输入 (chat-input)
 * 占位 · 不可输入 · 紫色发送按钮
 */
import type { CSSProperties } from "react";
import { registerWidget } from "./registry";

const ACCENT = "var(--aos-accent)";

const wrapStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  padding: 8,
  borderRadius: 2,
  border: "1px solid var(--aos-border)",
  background: "var(--aos-surface)",
};

const inputStyle: CSSProperties = {
  flex: 1,
  fontSize: 12,
  color: "var(--aos-text-muted)",
  padding: "8px 10px",
  border: "1px dashed var(--aos-border)",
  borderRadius: 2,
  background: "transparent",
  cursor: "not-allowed",
};

const btnStyle: CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  color: "#ffffff",
  background: ACCENT,
  border: "none",
  borderRadius: 2,
  padding: "8px 14px",
  cursor: "not-allowed",
  opacity: 0.9,
  display: "inline-flex",
  alignItems: "center",
  gap: 4,
};

function ChatInputWidget({ config }: { config: Record<string, any> }) {
  const placeholder = String(config?.placeholder ?? "输入消息与 Buddy 对话…");

  return (
    <div style={wrapStyle} role="search">
      <span style={inputStyle}>{placeholder}</span>
      <span style={btnStyle} aria-label="发送">
        ➤ 发送
      </span>
    </div>
  );
}

registerWidget({
  type: "chat-input",
  name: "聊天输入",
  icon: "⌨️",
  category: "ai",
  defaultConfig: {
    placeholder: "输入消息与 Buddy 对话…",
  },
  render: (config) => <ChatInputWidget config={config} />,
  propsSchema: [{ key: "placeholder", label: "占位文本", type: "text" }],
});
