/**
 * Widget · 消息列表 (message-log)
 * 占位渲染 · 用户消息靠右紫色气泡 · Buddy 消息靠左灰色气泡 · 带时间戳
 */
import type { CSSProperties } from "react";
import { registerWidget } from "./registry";
import { CARD_STYLE, MUTED_TEXT, TITLE_TEXT } from "./shared";

interface DemoMsg {
  from: "user" | "buddy";
  text: string;
  time: string;
}

const DEMO: DemoMsg[] = [
  { from: "buddy", text: "检测到 ORD-8821 异常，建议复核风控规则。", time: "10:02" },
  { from: "user", text: "帮我查一下这条订单的决策谱系。", time: "10:03" },
  { from: "buddy", text: "已关联 Ontology: Order + Wiki，共 3 条上游证据。", time: "10:03" },
  { from: "user", text: "好的，发起申诉并冻结库存。", time: "10:05" },
];

const rowStyle = (mine: boolean): CSSProperties => ({
  display: "flex",
  justifyContent: mine ? "flex-end" : "flex-start",
});

const bubbleBase: CSSProperties = {
  maxWidth: "78%",
  padding: "8px 10px",
  borderRadius: 2,
  fontSize: 12,
  lineHeight: 1.45,
};

const userBubble: CSSProperties = {
  ...bubbleBase,
  background: "var(--aos-accent)",
  color: "#ffffff",
  borderBottomRightRadius: 3,
};

const buddyBubble: CSSProperties = {
  ...bubbleBase,
  background: "var(--aos-bg)",
  color: "var(--aos-text)",
  border: "1px solid var(--aos-border)",
  borderBottomLeftRadius: 3,
};

const timeStyle: CSSProperties = {
  ...MUTED_TEXT,
  fontSize: 10,
  marginTop: 3,
};

function MessageLogWidget({ config }: { config: Record<string, any> }) {
  const title = String(config?.title ?? "会话记录");

  return (
    <div style={{ ...CARD_STYLE, display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={TITLE_TEXT}>{title}</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {DEMO.map((m, i) => {
          const mine = m.from === "user";
          return (
            <div key={i} style={rowStyle(mine)}>
              <div style={{ display: "flex", flexDirection: "column", alignItems: mine ? "flex-end" : "flex-start" }}>
                <div style={mine ? userBubble : buddyBubble}>{m.text}</div>
                <span style={timeStyle}>{m.time}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

registerWidget({
  type: "message-log",
  name: "消息列表",
  icon: "🗒️",
  category: "ai",
  defaultConfig: {
    title: "会话记录",
  },
  render: (config) => <MessageLogWidget config={config} />,
  propsSchema: [{ key: "title", label: "标题", type: "text" }],
});
