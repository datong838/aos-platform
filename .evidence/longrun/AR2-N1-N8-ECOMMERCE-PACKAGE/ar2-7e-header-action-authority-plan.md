# AR2-7E 专用页头动作 authority 门控方案

日期：2026-09-10
分支：`m1`
基线：`cbdb97d9`
权威：`AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN`
状态：编码前冻结

## 1. 确定性缺口

浏览器正向目录使用八个 `readiness=available` module，但 `permissions.actionTypes=[]`，业务读取明确返回 403。`AppShell` 仍按按钮中文文案把以下页头动作设为可用并分发页面事件：

- operations：`＋ 新建处理`
- creator-growth：`导入达人`、`＋ 新建邀约批次`
- media-studio：`＋ 新建内容任务`

当前已发布、候选和源 Workshop manifests 的 `actionTypes` 全部为空；不存在可把这些 Host 页头动作绑定到精确 ActionType 的声明。现实现的 `isExecutableAction` 只看 label/pathname，绕过 module action authority。页面正文自己的内部草稿控制由页面读取合同和服务端命令单独治理，不授权 Host 页头旁路。

安全的本地只读控制只有：

- `筛选`：聚焦/过滤当前已加载页面，不创建业务记录；
- `查看内容计划`：导航到另一个 canonical 路由，由目标 Catalog/Host 再次失败关闭。

## 2. 最小修改

修改：

- `apps/web/src/shell/AppShell.tsx`
- `apps/web/src/shell/AppShell.workshop.test.tsx`
- `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/ar2-7e-eight-workbench-browser.mjs`

`WorkshopPrimaryVisualHeader` 只把 `筛选` 和 `查看内容计划` 视为本地只读控制。所有会打开新建/导入/发布/监测/触达准备的 Host 页头按钮保持原生 `disabled`，直到 module manifest 定义精确 `actionTypes` 且另有类型化映射方案；本切片不猜测未来 action id，也不改变页面正文内部工作流。

## 3. RED 与退出

- 先扩浏览器执行器：当 Catalog `actionTypes=[]` 时，除 `筛选`、`查看内容计划` 外，任何可用的专用页头按钮都判 FAIL。
- 在当前实现上重跑受影响 operations/creator/media 单元，必须因可用业务页头动作实际 RED。
- 更新 AppShell 专项：operations 仅筛选可用；creator 两动作均禁用；media 仅查看内容计划可用；content/price/customer 继续全禁用。disabled 按钮点击不得分发新建事件。
- 修复后运行 AppShell 专项、关联 30 项、Web 全量、build、完整 24+13 浏览器矩阵、closure 和 diff check。

风险是误伤本地只读搜索/导航或页面正文内部草稿；分别由筛选焦点、内容计划导航和既有页面组件测试防回归。无 Provider、真实 mutation、发布、迁移或 push；`230 L0` 保持挂起。
