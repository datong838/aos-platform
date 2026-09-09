# AR2-7D 独立 Codex 只读复核

日期：2026-09-10
复核目标：`m1@e4aa1534`
结论：`VERDICT: PASS`
性质：独立 Codex 只读复核，不是 Prime 复核，不解除 231-6 的 Prime 门禁。

## 1. 首次复核 BLOCK

- `apps/web/src/navigation/items.ts` 固定显示 `/workshop/orders` 与 `/workshop/inventory`；目录为空或失败时 `catalog.modules=[]`，`AppShell` 无 replacement 可过滤，旧链接继续显示。
- 原 AppShell 测试只检查 `.ecommerce-workshop-host-state` 正文，没有检查全壳侧栏；原验证文档也记录了因全局“订单管理”文本存在而缩窄断言。
- 方案把一个参数化 Canonical POST path 承载九个固定 `operation_id` 误写为九条 path。

首次结论：`VERDICT: BLOCK`。全程未修改文件、未提交、未运行数据库测试。

## 2. 修复后二次复核 PASS

- `apps/web/src/navigation/items.ts:59-77` 保留两条旧深链定义，但均标记 `hidden: true`；`AppShell.tsx:562-572` 对 hidden 页面无条件跳过，空/失败目录不再泄漏旧侧栏链接。
- `apps/web/src/shell/AppShell.workshop.test.tsx:138-182` 分别覆盖空目录与读取失败，断言全壳两个旧 href 均不存在且动态 Workshop 模块入口为 0。
- 方案和验证证据已经统一表述为一个参数化 Canonical POST path 加九个固定 `operation_id`。
- 已安装旧深链仍由当前 catalog 的 `legacyRoutes` replace 到 canonical；动态安装导航仍只遍历 `catalog.modules`；canonical 深层路径和唯一 active 行为未回归。
- `e4aa1534^..e4aa1534` diff check 通过，目标文件在复核时没有后续漂移。

二次结论：`VERDICT: PASS`。全程未修改文件、未提交、未运行测试或数据库操作。

## 3. 主执行器的新鲜验证交叉核对

- RED：新增全壳断言 2 failed / 10 passed，精确捕获两条旧链接。
- GREEN：AppShell、导航、Catalog 聚焦 4 files / 35 tests；Web 全量 280 files / 2502 tests。
- TypeScript 与 Vite production build 通过，375 modules transformed；仅既有 chunk-size warning。
- closure `ar2-7`：1711 scanned / 93 classified / 57 migrated，五类错误为空。
- Provider、真实业务 mutation、生产迁移、发布、push 均为 0；`230 L0` 继续挂起。

## 4. 剩余门禁

Prime ChatGPT OAuth 在 token exchange 阶段被区域策略拒绝，Prime 没有生成审查正文。根据 231-6 第 160、276 条，本 PASS 仅证明已知代码 blocker 关闭，不能冒充 Prime PASS，不能据此前推 `AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN` authority。
