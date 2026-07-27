/**
 * Widget · 看板 (kanban)
 * 占位渲染 · 3 列看板（待处理/进行中/已完成）· 卡片(标题+标签) · 横向滚动
 */
import type { CSSProperties } from "react";
import { registerWidget } from "./registry";
import { CARD_STYLE, COLOR_MAP, TITLE_TEXT } from "./shared";

interface KanbanCard {
  id: string;
  tag: string;
}

interface KanbanColumn {
  key: string;
  title: string;
  dot: string;
  cards: KanbanCard[];
}

const COLUMNS: KanbanColumn[] = [
  {
    key: "todo",
    title: "待处理",
    dot: COLOR_MAP.amber,
    cards: [
      { id: "ORD-8821", tag: "风控" },
      { id: "ORD-8830", tag: "地址" },
    ],
  },
  {
    key: "doing",
    title: "进行中",
    dot: COLOR_MAP.indigo,
    cards: [
      { id: "ORD-8715", tag: "申诉" },
      { id: "ORD-8720", tag: "复核" },
      { id: "ORD-8741", tag: "加急" },
    ],
  },
  {
    key: "done",
    title: "已完成",
    dot: COLOR_MAP.green,
    cards: [
      { id: "ORD-8600", tag: "正常" },
      { id: "ORD-8602", tag: "正常" },
    ],
  },
];

const TAG_COLOR: Record<string, string> = {
  风控: COLOR_MAP.red,
  地址: COLOR_MAP.amber,
  申诉: COLOR_MAP.violet,
  复核: COLOR_MAP.indigo,
  加急: COLOR_MAP.pink,
  正常: COLOR_MAP.green,
};

const boardStyle: CSSProperties = {
  display: "flex",
  gap: 12,
  overflowX: "auto",
  paddingBottom: 4,
  marginTop: 10,
};

const colStyle: CSSProperties = {
  flex: "0 0 200px",
  display: "flex",
  flexDirection: "column",
  gap: 8,
};

const colHeaderStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 6,
  fontSize: 12,
  fontWeight: 700,
  color: "var(--aos-text)",
};

const dotStyle = (color: string): CSSProperties => ({
  width: 8,
  height: 8,
  borderRadius: "50%",
  background: color,
  display: "inline-block",
});

const countStyle: CSSProperties = {
  marginLeft: "auto",
  fontSize: 10,
  fontWeight: 600,
  color: "var(--aos-text-muted)",
  background: "var(--aos-bg)",
  borderRadius: 999,
  padding: "1px 6px",
};

const cardStyle: CSSProperties = {
  background: "var(--aos-bg)",
  border: "1px solid var(--aos-border)",
  borderRadius: 6,
  padding: "8px 10px",
  display: "flex",
  alignItems: "center",
  gap: 8,
};

const idStyle: CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  color: "var(--aos-text)",
};

const tagStyle = (color: string): CSSProperties => ({
  fontSize: 10,
  fontWeight: 600,
  color: color,
  background: `${color}1a`,
  borderRadius: 999,
  padding: "1px 6px",
});

function KanbanWidget({ config }: { config: Record<string, any> }) {
  const title = String(config?.title ?? "处置看板");

  return (
    <div style={CARD_STYLE}>
      <div style={TITLE_TEXT}>{title}</div>
      <div style={boardStyle} role="list" aria-label={title}>
        {COLUMNS.map((col) => (
          <div key={col.key} style={colStyle} role="listitem">
            <div style={colHeaderStyle}>
              <span style={dotStyle(col.dot)} />
              {col.title}
              <span style={countStyle}>{col.cards.length}</span>
            </div>
            {col.cards.map((c) => {
              const color = TAG_COLOR[c.tag] || COLOR_MAP.indigo;
              return (
                <div key={c.id} style={cardStyle}>
                  <span style={idStyle}>{c.id}</span>
                  <span style={tagStyle(color)}>{c.tag}</span>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

registerWidget({
  type: "kanban",
  name: "看板",
  icon: "📋",
  category: "extra",
  defaultConfig: {
    title: "处置看板",
  },
  render: (config) => <KanbanWidget config={config} />,
  propsSchema: [{ key: "title", label: "标题", type: "text" }],
});
