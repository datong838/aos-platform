/**
 * Widget 插件聚合入口
 *
 * 任何地方只要 `import "./widgets"` 或 `import "@/pages/widgets"`，
 * 所有 widget 都会自动注册到 registry，调色板/属性面板/运行态渲染立即可用。
 *
 * 新增 widget 时：
 *   1. 在本目录新建 XxxWidget.tsx，文件末尾调用 registerWidget({...})
 *   2. 在本文件加一行 `import "./XxxWidget";`
 *   3. 完成 ✓
 */

// 内置 widget（来自 ComponentRenderer，保留真实 API 逻辑）
import "./BuiltinWidgets";

// ── 图表类 ──
import "./BarChartWidget";
import "./PieChartWidget";
import "./NetworkGraphWidget";
import "./GeoMapWidget";

// ── AI / 协作 ──
import "./ChatAsideWidget";
import "./MessageLogWidget";
import "./ChatInputWidget";
import "./ContextChipsWidget";
import "./AssistPopoverWidget";
import "./BuddyChipWidget";

// ── 数据展示 ──
import "./WikiCardWidget";
import "./DrillPanelWidget";
import "./StatusBadgeWidget";

// ── 时间 / 事件 ──
import "./TimelineWidget";
import "./EventStreamWidget";

// ── 操作 ──
import "./ButtonGroupWidget";

// ── 筛选 ──
import "./FilterListWidget";

// ── 扩展组件 ──
import "./KanbanWidget";
import "./GanttWidget";
import "./CalendarWidget";

export { registerWidget, getWidgetPlugin, getAllWidgets, getWidgetsByCategory, CATEGORY_LABEL } from "./registry";
export type { WidgetPlugin, WidgetCategory, PropFieldDef, PropFieldType } from "./registry";
