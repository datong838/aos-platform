/**
 * WidgetPluginRegistry · 插件化组件注册中心
 *
 * 设计目标：
 *   - 新增 widget 只需在 widgets/ 目录写一个 plugin 文件并 registerWidget() 一次
 *   - 调色板 / 属性面板 / 运行态渲染三处统一从 registry 读，零侵入扩展
 *
 * 详见 docs/palantier/20_tech/223-widget-palette-expansion.md
 */
import type { ComponentType, ReactNode } from "react";
import type { ComponentTree } from "../ComponentRenderer";

// ── Types ───────────────────────────────────────────────────────────────────

export type WidgetCategory =
  | "layout"
  | "data"
  | "filter"
  | "action"
  | "chart"
  | "ai"
  | "time"
  | "extra";

export type PropFieldType = "text" | "number" | "select" | "color" | "textarea" | "boolean";

export type PropFieldGroup = "basic" | "data" | "style" | "advanced";

export interface PropFieldDef {
  key: string;
  label: string;
  type: PropFieldType;
  group?: PropFieldGroup;
  options?: { label: string; value: string }[];
  placeholder?: string;
  min?: number;
}

export interface WidgetContext {
  components: ComponentTree;
  depth: number;
}

export interface WidgetPlugin {
  type: string;
  name: string;
  icon: string;
  category: WidgetCategory;
  defaultConfig: Record<string, any>;
  isContainer?: boolean;
  render: (
    config: Record<string, any>,
    ctx: WidgetContext,
    children?: ReactNode,
  ) => ReactNode;
  propsSchema: PropFieldDef[];
}

// ── Registry ────────────────────────────────────────────────────────────────

const REGISTRY = new Map<string, WidgetPlugin>();

export function registerWidget(plugin: WidgetPlugin): void {
  REGISTRY.set(plugin.type, plugin);
}

export function getWidgetPlugin(type: string): WidgetPlugin | undefined {
  return REGISTRY.get(type);
}

export function getAllWidgets(): WidgetPlugin[] {
  return Array.from(REGISTRY.values());
}

export function getWidgetsByCategory(): Record<WidgetCategory, WidgetPlugin[]> {
  const grouped: Record<WidgetCategory, WidgetPlugin[]> = {
    layout: [],
    data: [],
    filter: [],
    action: [],
    chart: [],
    ai: [],
    time: [],
    extra: [],
  };
  for (const plugin of REGISTRY.values()) {
    grouped[plugin.category].push(plugin);
  }
  return grouped;
}

export const CATEGORY_LABEL: Record<WidgetCategory, string> = {
  layout: "Layout",
  data: "数据",
  filter: "筛选",
  action: "操作",
  chart: "图表",
  ai: "AI / 协作",
  time: "时间 / 事件",
  extra: "扩展组件",
};

export const PROP_GROUP_LABEL: Record<PropFieldGroup, string> = {
  basic: "基础",
  data: "数据源",
  style: "样式",
  advanced: "高级",
};

export const PROP_GROUP_ORDER: PropFieldGroup[] = ["basic", "data", "style", "advanced"];

// 占位组件类型（用于未注册 type 的兜底渲染）
export type { ComponentType, ComponentTree };
