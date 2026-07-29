# W4 · B1 画布功能面板方案（55%→70%）

> 分支：`feature/223-worker-4`  
> 依据：`227-未完成项补齐计划.md` W1·B1；`223-deep-checklist.md` §7.1  
> 原则：功能面板补齐，非全像素；最小改动；不依赖 W1 新建文件

## 1. Checklist 对照（功能项）

| # | 功能项（§7.1） | 现状 | 本波动作 | 验收 |
|---|---------------|------|----------|------|
| F1 | 变量 pop-panel / 变量 Tab | 错接 `workshop-compute-api` | **做**：只读接 `GET /v1/modules/:id/variables` | 列表来自模块变量 API；失败可降级提示 |
| F2 | 属性面板 4 Tab（内容/样式/事件/数据） | 内容可写；其余偏静态 | **做**：样式/事件/数据写入 `node.config`；数据 Tab 绑定变量 | 改动能反映到选中 widget |
| F3 | 预览 ↔ 编辑模式 | 有三模式，预览可回编辑 | **做**：Esc 退出预览；预览条加固；切预览时同步 `previewOn` | 预览态只读展示、可一键回编辑 |
| F4 | 组件树 ↔ 画布选中联动 | widget 路径已联动；ComponentTree 布局 Tab 不可点选 | **做**：布局树可点选同步 `selectedId`；左栏搜索过滤 | 点树选中画布节点，点画布高亮树 |
| — | Topbar / 工作流深度 / 全像素 | — | **不做**（归 226 / P1） | — |
| — | VariablesPage / 变量写 API | — | **禁止**（W1 所有权） | — |

目标覆盖功能项约一半：F1–F4（4/8 核心清单项）。

## 2. 文件与改动边界

| 文件 | 改动 |
|------|------|
| `apps/web/src/pages/CanvasTabs.tsx` | `VariablesTab` 改为只读；类型对齐 `module_variables`；导出纯函数供测 |
| `apps/web/src/pages/CanvasPage.tsx` | 属性侧栏样式/事件/数据可写 + 变量绑定；预览加固；树搜索；传 `moduleId` |
| `apps/web/src/pages/ComponentTreeEditor.tsx` | `moduleId`；变量 Tab 只读拉 API；布局树点选联动 |
| `apps/web/src/pages/canvasWidgets.tsx` | 变量绑定/引用格式纯函数 |
| `apps/web/src/pages/CanvasTabs.test.ts` / `canvasWidgets` 相关 test | 新增纯函数单测 |
| `apps/web/src/styles.css` | 末尾仅追加 `/* === W4-B1 === */` |

**禁止**：VariablesPage、DraftInbox、ModuleInterface、extras、后端、nav、push、改 m1。

## 3. API 契约（只读）

`GET /v1/modules/:id/variables` → `{ moduleId, items: [{ id, name, varType, group, initialValue, currentValue, description }], count }`

失败时 VariablesTab 显示错误，不写 MOCK 造数据（可空列表）。

## 4. 风险与回滚

- 风险：VariablesTab 去掉新建表单 → 底部「变量」Tab 变为只读；写操作仍归 `/workshop/variables`（W1）。
- 风险：属性写入仅本地 `nodes`/`dirty`，保存仍走既有 save 路径，不新增后端。
- 回滚：还原上述 4 个 TSX + CSS 段 + 测试即可。

## 5. 自测清单

1. 打开 `/workshop/canvas`，切底部「变量」→ 见模块变量列表（或空/错误提示）。
2. 选中 widget → 数据 Tab 可绑定变量名到 config。
3. 样式 Tab 改间距/背景 → `node.config` 更新。
4. 切「预览」→ Esc 回组件编辑态。
5. ComponentTree 模式：布局 Tab 点节点 → 右侧属性同步。
6. `pnpm/npm test` 相关单测通过。
