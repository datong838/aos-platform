/**
 * 把 ComponentRenderer 里已实现的内置 widget 注册到 registry
 * 这些 widget 保留真实 API 逻辑（object-table / stat-card 等会查 /v1/objects）
 */
import { registerWidget } from "./registry";
import {
  PageHeader,
  StatCardWidget,
  FilterBarWidget,
  ObjectTableWidget,
  DetailDrawerWidget,
  TrendChartWidget,
} from "../ComponentRenderer";

// ── page-layout ──────────────────────────────────────────────────────────────

registerWidget({
  type: "page-layout",
  name: "页面布局",
  icon: "📐",
  category: "layout",
  defaultConfig: { padding: 24, gap: 16 },
  isContainer: true,
  render: (config, _ctx, children) => (
    <div
      style={{
        padding: config.padding ?? 24,
        display: "flex",
        flexDirection: "column",
        gap: config.gap ?? 16,
      }}
    >
      {children}
    </div>
  ),
  propsSchema: [
    { key: "padding", label: "内边距", type: "number", min: 0 },
    { key: "gap", label: "间距", type: "number", min: 0 },
  ],
});

// ── horizontal-grid ─────────────────────────────────────────────────────────

registerWidget({
  type: "horizontal-grid",
  name: "水平网格",
  icon: "⊞",
  category: "layout",
  defaultConfig: { cols: 4, gap: 16 },
  isContainer: true,
  render: (config, _ctx, children) => (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: `repeat(${config.cols ?? 4}, 1fr)`,
        gap: config.gap ?? 16,
      }}
    >
      {children}
    </div>
  ),
  propsSchema: [
    { key: "cols", label: "列数", type: "number", min: 1 },
    { key: "gap", label: "间距", type: "number", min: 0 },
  ],
});

// ── page-header ─────────────────────────────────────────────────────────────

registerWidget({
  type: "page-header",
  name: "页头",
  icon: "🏷",
  category: "layout",
  defaultConfig: { title: "新页面", subtitle: "页面副标题" },
  render: (config) => <PageHeader config={config} />,
  propsSchema: [
    { key: "title", label: "标题", type: "text" },
    { key: "subtitle", label: "副标题", type: "text" },
  ],
});

// ── stat-card ───────────────────────────────────────────────────────────────

registerWidget({
  type: "stat-card",
  name: "统计卡片",
  icon: "🔢",
  category: "data",
  defaultConfig: { title: "统计项", objectType: "", color: "blue", metric: "count" },
  render: (config) => <StatCardWidget config={config} />,
  propsSchema: [
    { key: "title", label: "标题", type: "text" },
    { key: "objectType", label: "对象类型", type: "text" },
    {
      key: "color",
      label: "颜色",
      type: "select",
      options: [
        { label: "蓝色", value: "blue" },
        { label: "琥珀", value: "amber" },
        { label: "绿色", value: "green" },
        { label: "靛蓝", value: "indigo" },
        { label: "紫色", value: "violet" },
      ],
    },
    {
      key: "metric",
      label: "聚合",
      type: "select",
      options: [
        { label: "计数", value: "count" },
        { label: "求和", value: "sum" },
      ],
    },
    { key: "field", label: "求和字段", type: "text" },
  ],
});

// ── filter-bar ──────────────────────────────────────────────────────────────

registerWidget({
  type: "filter-bar",
  name: "筛选栏",
  icon: "📋",
  category: "filter",
  defaultConfig: {
    objectType: "",
    tabs: [
      { key: "all", label: "全部" },
      { key: "pending", label: "待处理" },
      { key: "done", label: "已完成" },
    ],
  },
  render: (config) => <FilterBarWidget config={config} />,
  propsSchema: [
    { key: "objectType", label: "对象类型", type: "text" },
  ],
});

// ── object-table ────────────────────────────────────────────────────────────

registerWidget({
  type: "object-table",
  name: "对象表格",
  icon: "📊",
  category: "data",
  defaultConfig: {
    objectType: "",
    columns: [
      { key: "title", label: "名称" },
      { key: "status", label: "状态" },
    ],
  },
  render: (config) => <ObjectTableWidget config={config} />,
  propsSchema: [
    { key: "objectType", label: "对象类型", type: "text" },
  ],
});

// ── detail-drawer ───────────────────────────────────────────────────────────

registerWidget({
  type: "detail-drawer",
  name: "详情抽屉",
  icon: "🗂",
  category: "data",
  defaultConfig: {
    objectType: "",
    sections: [{ title: "基本信息", fields: [{ key: "title", label: "名称" }] }],
  },
  render: (config) => <DetailDrawerWidget config={config} />,
  propsSchema: [
    { key: "objectType", label: "对象类型", type: "text" },
  ],
});

// ── trend-chart ─────────────────────────────────────────────────────────────

registerWidget({
  type: "trend-chart",
  name: "趋势图",
  icon: "📉",
  category: "chart",
  defaultConfig: { objectType: "", title: "趋势图" },
  render: (config) => <TrendChartWidget config={config} />,
  propsSchema: [
    { key: "title", label: "标题", type: "text" },
    { key: "objectType", label: "对象类型", type: "text" },
  ],
});
