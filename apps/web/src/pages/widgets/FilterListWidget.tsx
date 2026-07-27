/**
 * Widget · 筛选列表 (filter-list)
 * 占位渲染 · 左侧 200px 筛选栏 · 3 分组复选框 · 底部输出提示
 * 视觉参考：风险告警管理 workshop 左栏
 */
import type { CSSProperties } from "react";
import { registerWidget } from "./registry";
import { CARD_STYLE, MUTED_TEXT, TITLE_TEXT } from "./shared";

interface FilterOption {
  label: string;
  checked: boolean;
}

interface FilterGroup {
  name: string;
  options: FilterOption[];
}

const DEMO_GROUPS: FilterGroup[] = [
  {
    name: "状态",
    options: [
      { label: "待复核", checked: true },
      { label: "已发货", checked: true },
      { label: "已取消", checked: false },
    ],
  },
  {
    name: "优先级",
    options: [
      { label: "高", checked: true },
      { label: "中", checked: true },
      { label: "低", checked: false },
    ],
  },
  {
    name: "日期",
    options: [
      { label: "近 7 天", checked: true },
      { label: "本月", checked: false },
    ],
  },
];

const ACCENT = "var(--aos-accent)";

const wrapStyle: CSSProperties = {
  ...CARD_STYLE,
  width: 200,
  padding: 12,
  display: "flex",
  flexDirection: "column",
  gap: 12,
};

const groupTitleStyle: CSSProperties = {
  fontSize: 10,
  fontWeight: 700,
  letterSpacing: 0.6,
  textTransform: "uppercase",
  color: "var(--aos-text-muted)",
  marginBottom: 4,
};

const optionStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 6,
  fontSize: 12,
  color: "var(--aos-text)",
  padding: "3px 0",
  cursor: "pointer",
};

const checkboxStyle: CSSProperties = {
  width: 13,
  height: 13,
  accentColor: "#4f46e5",
  cursor: "pointer",
};

const dividerStyle: CSSProperties = {
  height: 1,
  background: "var(--aos-border)",
  margin: "2px 0",
};

const outputStyle: CSSProperties = {
  fontSize: 10,
  fontWeight: 600,
  color: ACCENT,
  background: "rgba(79, 70, 229, 0.10)",
  border: "1px dashed rgba(79, 70, 229, 0.45)",
  borderRadius: 6,
  padding: "6px 8px",
  textAlign: "center",
};

function FilterListWidget({ config }: { config: Record<string, any> }) {
  const title = String(config?.title ?? "筛选");

  return (
    <div style={wrapStyle} role="group" aria-label={title}>
      <div style={TITLE_TEXT}>{title}</div>

      {DEMO_GROUPS.map((g) => (
        <div key={g.name}>
          <div style={groupTitleStyle}>{g.name}</div>
          {g.options.map((opt) => (
            <label key={opt.label} style={optionStyle}>
              <input type="checkbox" defaultChecked={opt.checked} style={checkboxStyle} />
              <span>{opt.label}</span>
            </label>
          ))}
        </div>
      ))}

      <div style={dividerStyle} />

      <div style={outputStyle}>输出 → Object Set Filter</div>

      <div style={MUTED_TEXT}>已选 4 / 8 项</div>
    </div>
  );
}

registerWidget({
  type: "filter-list",
  name: "筛选列表",
  icon: "🧮",
  category: "filter",
  defaultConfig: {
    title: "筛选",
  },
  render: (config) => <FilterListWidget config={config} />,
  propsSchema: [{ key: "title", label: "标题", type: "text" }],
});
