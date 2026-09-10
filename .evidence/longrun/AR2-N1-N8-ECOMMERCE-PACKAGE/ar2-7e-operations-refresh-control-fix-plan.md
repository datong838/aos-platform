# AR2-7E 统一运营刷新控件可达性修复方案

日期：2026-09-10

分支：`m1`

基线：`5e16b467`

权威：`AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN`

状态：产品代码修改前冻结

## 1. 缺口证据

- Operations 非空三视口验收已完成筛选、详情、内部提案、替代版本、撤回和 Receipt 回读，但在刷新阶段连续失败关闭。
- 主视觉 CSS 将 `.operations-toolbar` 整体裁剪为 1×1 隐藏区域，而该区域包含页面唯一的“重新读取”控件；Playwright 在 `1280×720` 与 `1440×900` 均确认按钮被业务内容遮挡，无法真实指针点击。
- 现状违反 231-6 第 161 条“刷新并回读”的逐页验收要求。不得用 `force`、DOM 注入或直接调用 React handler 掩盖缺口。

## 2. 最小修复

- 在 Operations 主视觉顶栏增加可见的“重新读取”动作，并将它标记为可执行。
- 顶栏动作只派发页内 `aos-workshop-operation-refresh` 事件；Operations 页面复用既有 `load()`，不新增 API、不改变租户头、不改变读取并发和失败关闭行为。
- 保持被隐藏的技术 toolbar 与现有布局不变，避免增加重复标题或改变三栏尺寸。
- 为 AppShell 补动作可用性／事件派发测试，为 OperationsPage 补收到事件后重新请求三项只读依赖的测试。

## 3. 文件与 preHash

- `apps/web/src/shell/AppShell.tsx`：`dc438e9df8a01baa138d3c450f5dfd7a9dafb709bace39724cacec13f62518c4`
- `apps/web/src/shell/AppShell.workshop.test.tsx`：`792cc25bf089628cd32c5ddfc4a9464a8faf9bd0262b1f71e33147426839c62a`
- `apps/web/src/components/workshop/OperationsPage.tsx`：`9bbfe04c78a0774a3fd3c0a536e5b62691c12e65763b9e98da835cef36daa757`
- `apps/web/src/components/workshop/OperationsPage.test.tsx`：`70fdaa1909c477ef53e9b877c2e196bd060bab343cd8dcb81c3270b1fdb60824`

不修改 API、parser、样式、其他工作台或业务数据。

## 4. 验证与退出条件

- 单元测试证明 Operations 顶栏显示可用“重新读取”，点击后事件只触发一次；页面收到事件后 operations view、command readiness、case workspace 各追加一次 GET。
- Operations 富数据三视口 `3/3 PASS`；刷新后正式 fixture 不变，15 个内部提案写请求全部被截获，其他写请求与外部效果为零。
- Web 全量测试、production build、closure phase `ar2-7` 与 `git diff --check` 全绿。
- 若顶栏动作造成水平溢出或其他工作台行为漂移，失败关闭并回退本修复，不扩大到全局 header 重构。
