/**
 * Widget · Buddy 聊天侧栏 (chat-aside)
 * 容器组件 · 右侧悬浮 · 标题栏 + 消息列表区(children) + 底部输入占位
 */
import type { CSSProperties, ReactNode } from "react";
import { registerWidget, type WidgetContext } from "./registry";
import { CARD_STYLE, MUTED_TEXT, TITLE_TEXT } from "./shared";

const ACCENT = "var(--aos-accent)";

const asideStyle: CSSProperties = {
  ...CARD_STYLE,
  width: 320,
  padding: 0,
  display: "flex",
  flexDirection: "column",
  boxShadow: "0 8px 28px rgba(79, 70, 229, 0.18)",
  overflow: "hidden",
};

const headerStyle: CSSProperties = {
  padding: "10px 14px",
  borderBottom: "1px solid var(--aos-border)",
  display: "flex",
  alignItems: "center",
  gap: 8,
  background: "var(--aos-bg)",
};

const dotStyle: CSSProperties = {
  width: 8,
  height: 8,
  borderRadius: "50%",
  background: "#10B981",
  boxShadow: "0 0 0 3px rgba(16,185,129,0.18)",
};

const bodyStyle: CSSProperties = {
  padding: 12,
  minHeight: 220,
  flex: 1,
  display: "flex",
  flexDirection: "column",
  gap: 8,
  overflow: "auto",
};

const footerStyle: CSSProperties = {
  padding: "10px 12px",
  borderTop: "1px solid var(--aos-border)",
  display: "flex",
  alignItems: "center",
  gap: 8,
  background: "var(--aos-bg)",
};

const inputPlaceholderStyle: CSSProperties = {
  flex: 1,
  fontSize: 12,
  color: "var(--aos-text-muted)",
  padding: "6px 10px",
  border: "1px dashed var(--aos-border)",
  borderRadius: 2,
  background: "transparent",
};

const sendBtnStyle: CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  color: "#ffffff",
  background: ACCENT,
  border: "none",
  borderRadius: 2,
  padding: "6px 12px",
  cursor: "not-allowed",
  opacity: 0.85,
};

function ChatAsideWidget(
  config: Record<string, any>,
  _ctx: WidgetContext,
  children?: ReactNode,
) {
  const title = String(config?.title ?? "Buddy 助手");
  const buddyName = String(config?.buddyName ?? "Aria");

  return (
    <div style={asideStyle} role="complementary" aria-label={title}>
      <div style={headerStyle}>
        <span style={dotStyle} />
        <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.2 }}>
          <span style={TITLE_TEXT}>{title}</span>
          <span style={MUTED_TEXT}>{buddyName} · 风控 Buddy 在线</span>
        </div>
      </div>

      <div style={bodyStyle}>
        {children ?? (
          <div style={MUTED_TEXT}>
            消息列表占位（可将「消息列表 / Message Log」组件拖入此处）
          </div>
        )}
      </div>

      <div style={footerStyle}>
        <span style={inputPlaceholderStyle}>输入消息与 Buddy 对话…</span>
        <span style={sendBtnStyle}>发送</span>
      </div>
    </div>
  );
}

registerWidget({
  type: "chat-aside",
  name: "Buddy 聊天侧栏",
  icon: "💬",
  category: "ai",
  isContainer: true,
  defaultConfig: {
    title: "Buddy 助手",
    buddyName: "Aria",
  },
  render: (config, ctx, children) => (
    <ChatAsideWidget config={config} ctx={ctx} children={children} />
  ),
  propsSchema: [
    { key: "title", label: "标题", type: "text" },
    { key: "buddyName", label: "Buddy 名称", type: "text" },
  ],
});
