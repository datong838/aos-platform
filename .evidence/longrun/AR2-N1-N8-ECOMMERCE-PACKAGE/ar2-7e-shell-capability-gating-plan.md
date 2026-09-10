# AR2-7E AppShell 安装能力门控施工方案

日期：2026-09-10  
分支：`m1`  
权威：`AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN`  
状态：编码前冻结

## 1. Rules 与产品边界

- 依据 closure manifest、`dynamic-reference-phases.json`、231-6 第 161 行、7E 入场清单和当前已提交源码施工。
- m1 单人串行；先 RED、后最小实现；聚焦、Web 全量、build、closure 与证据通过后提交；不 push。
- 页面能力只能来自当前 tenant 的安装目录、权限和 slot registry。pathname 只负责定位，不能单独授予页面专用视觉、业务文案或动作。
- 本切片只修复壳层能力泄漏，不改变八页业务组件、Catalog API、路由、后端、数据库或权限合同。
- Provider 业务调用、真实业务 mutation、生产/共享迁移、外部发布均为 0；`230 L0` 继续挂起。

## 2. 已确认缺口

`AppShell.tsx` 已能用 `activeWorkshop` 生成动态 active 导航，但以下四个视觉判定仍只读取 `location.pathname`：

- `onAnalystVisualRoute`
- `onTaskCockpitVisualRoute`
- `onWorkshopPrimaryVisualRoute`
- `onWorkshopMappedHeaderRoute`

因此直接访问八条 canonical URL 时，即使 Catalog 为空、403、读取失败、当前 tenant 未安装或 module 不匹配，Host 正文会失败关闭，外壳仍显示 `栖月汇微商城`、专用标题、搜索框及日历/筛选/内部草稿动作，并套用专用视觉 class。这把静态 URL 误当成已安装能力。

## 3. 最小实现

修改：

- `apps/web/src/shell/AppShell.workshop.test.tsx`
- `apps/web/src/shell/AppShell.tsx`

实现上限：四个专用视觉判定统一增加 `Boolean(activeWorkshop)` 前置；不新增权限推断、状态枚举或页面映射。当前 Catalog 中能匹配 canonical/deep route 的 ready 或只读 degraded/stale module 保持原专用壳层；不存在匹配 module 时使用通用 AppShell 顶栏和品牌区，由 `EcommerceWorkshopHost` 独立显示 loading/forbidden/failed/empty/uninstalled 状态。

## 4. RED 与回归矩阵

先在 AppShell 专项增加表驱动反例：

1. empty Catalog 直达 `/workshop/operations`；
2. Catalog 读取失败直达 `/workshop/operations`；
3. 403/forbidden 直达 `/workshop/operations`；
4. tenant mismatch 或仅安装其他 module 时直达 `/workshop/operations`。

每例必须断言：

- `.p-app` 不含 `is-workshop-primary-visual`、`is-analyst-visual` 或 `is-task-cockpit-visual`；
- 不存在 `.workshop-visual-header-left`、`.workshop-visual-header-actions`、`.analyst-exact-header-left`、`.task-cockpit-exact-header-left`；
- 壳层不出现 `栖月汇微商城` 或目标业务标题/动作；
- 通用 `.topbar-left` 与 `.brand-block` 存在；
- Host 仍显示对应 forbidden/failed/uninstalled 状态，Workshop 动态导航为 0。

既有正例继续证明八个当前已安装 module 保持专用壳层、唯一 active、完整公共导航、深链与动作语义。

## 5. 退出与风险

- RED 必须在现实现上实际失败，并精确指向静态壳层泄漏；若测试因 fixture 或异步等待失败，不计产品 RED。
- 修复后运行 AppShell/Catalog/Host/InstalledModuleNavigation 聚焦测试、Web 全量、production build、`verify_closure.py --phase ar2-7` 和 `git diff --check`。
- 本切片通过只关闭 7E 第一个确定性缺口，不代表 24 单元八页三视口、全交互或整波 GREEN；随后继续浏览器矩阵。
- 风险集中在错误地隐藏已安装 module 的专用壳层；由八页正例、canonical deep route 和现有导航测试防回归。
