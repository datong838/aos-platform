# W4_DONE · B1 画布功能面板

> 分支：`feature/223-worker-4`  
> 方案：`W4_B1_PLAN.md`  
> 目标：`/workshop/canvas` 55% → ~70%（功能面板，非全像素）

## 补了哪些面板

| 面板 | 改动 |
|------|------|
| **变量 Tab（只读）** | `VariablesTab` 改接 `GET /v1/modules/:id/variables`；去掉新建/编辑表单；可复制 `$name` 引用 |
| **属性 · 样式** | 布局方向 / 间距 / 背景色写入 `node.config` |
| **属性 · 事件** | 本地事件列表可增删改，写入 `node.config.events` |
| **属性 · 数据** | 列出模块变量，点击绑定/取消 `config.boundVariable` |
| **预览 ↔ 编辑** | `switchCanvasMode`；Esc 退出预览；预览条文案加固 |
| **组件树联动** | 左栏搜索过滤；`ComponentTreeEditor` 布局树点选 ↔ 画布 `selectedId`；变量 Tab 只读拉 API |

## Checklist 对照（§7.1 功能项）

| 项 | 状态 |
|----|------|
| F1 变量 pop-panel / 变量 Tab 真 API | ✅ |
| F2 属性面板 4 Tab 可配置（样式/事件/数据） | ✅ |
| F3 预览/编辑切换加固 | ✅ |
| F4 组件树 ↔ 画布选中联动 + 搜索 | ✅ |
| Topbar 完整 / 工作流深度 / 全像素 | ❌ 不做（226 / P1） |
| VariablesPage / 变量写 API | ❌ 禁止（W1） |

覆盖约一半功能项（4/8）。

## 改动文件

- `apps/web/src/pages/CanvasPage.tsx`
- `apps/web/src/pages/CanvasTabs.tsx`
- `apps/web/src/pages/ComponentTreeEditor.tsx`
- `apps/web/src/pages/canvasWidgets.tsx`
- `apps/web/src/pages/canvasWidgets.b1.test.ts`（新增）
- `apps/web/src/styles.css`（末尾 `/* === W4-B1 === */`）
- `W4_B1_PLAN.md` / `W4_DONE.md`

## 自测

- `vitest`：`canvasWidgets.b1.test.ts` + `ComponentRenderer.test.ts` → 21 passed
- `tsc`：上述可写文件无新增错误
- 与方案文档一致：只读变量、属性可写本地 config、预览 Esc、树点选联动

## 风险

- 变量 Tab 变为只读；写变量仍归 W1 `/workshop/variables`
- 属性写入仅本地 dirty，依赖既有保存路径；不新增后端
- 事件 Tab 首次编辑前展示默认样例，编辑后写入 config（不污染未触碰节点）
