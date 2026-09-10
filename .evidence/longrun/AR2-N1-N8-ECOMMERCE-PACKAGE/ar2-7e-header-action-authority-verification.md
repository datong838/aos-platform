# AR2-7E 专用页头动作 authority 门控验证

日期：2026-09-10
分支：`m1`
权威：`AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN`
对应方案：`ar2-7e-header-action-authority-plan.md`
结论：`AR2_7E_HEADER_ACTION_AUTHORITY_GREEN`

## 1. RED

浏览器执行器在 `permissions.actionTypes=[]`、页面业务读取 403 的安装目录中加入未授权可用页头动作断言。现实现结果：

```text
positive operations 1280x720: FAIL unauthorized_header_actions_＋ 新建处理
positive operations 1440x900: FAIL unauthorized_header_actions_＋ 新建处理
positive matrix stopped after two consecutive failures
```

AppShell 专项同步获得 2 个失败：operations 新建处理没有 disabled；creator/media 非只读按钮仍被文案规则启用。

## 2. 最小实现

- `WorkshopPrimaryVisualHeader` 只允许本地只读 `筛选` 和 canonical 导航 `查看内容计划`。
- `＋ 新建处理`、`导入达人`、`＋ 新建邀约批次`、`＋ 新建内容任务` 以及既有发布/监测/触达按钮全部保留原生 disabled。
- operations disabled 按钮点击不再分发 `aos-workshop-operation-new`。
- 页面正文内部草稿仍由各自读取合同和服务端命令治理，本切片没有删除或改写页面工作流。

## 3. GREEN

```text
AppShell + Operations + CreatorGrowth + MediaStudio
Test Files  4 passed (4)
Tests  50 passed (50)

Web full suite
Test Files  280 passed (280)
Tests  2507 passed (2507)

production build
tsc + vite: PASS, 375 modules transformed
```

完整浏览器重跑中 24/24 正向与 13/13 反向通过，`unauthorizedEnabledHeaderActions=0`、Workshop 非 GET=0。筛选焦点、内容计划导航和页面正文组件回归均未受影响。

## 4. 边界

当前 manifests 的 `actionTypes` 全为空，因此没有猜测或新增 ActionType。未来若需要从 Host 页头启用业务准备动作，必须先定义 manifest 中的精确 action id、类型化 label/action 映射和服务端授权回读，再另行施工。

本结论不授权 Provider、真实业务 mutation、发布或迁移，不单独代表 7E 整波完成。
