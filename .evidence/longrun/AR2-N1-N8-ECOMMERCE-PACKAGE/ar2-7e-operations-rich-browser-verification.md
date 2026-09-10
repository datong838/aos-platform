# AR2-7E 统一运营非空隔离功能验收记录

日期：2026-09-10

分支：`m1`

计划基线：`331bf8c4`

方案提交：`5e16b467`、`17c576c3`

权威：`AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN`

结论：`AR2_7E_OPERATIONS_RICH_BROWSER_GREEN`

## 1. 产品缺口与最小修复

- 初始验收发现主视觉 CSS 将 `.operations-toolbar` 整体裁剪隐藏，其中包含页面唯一的“重新读取”按钮；三个目标视口无法真实指针点击。
- 未使用 `force`、DOM 注入或直接调用 handler 绕过。按 `ar2-7e-operations-refresh-control-fix-plan.md` 在主视觉顶栏增加可见“重新读取”，点击后派发页内事件；Operations 复用原 `load()` 并行重读 operations view、command readiness、case workspace。
- 未修改 API、parser、样式、租户头、读取合同或其他工作台行为。
- 产品 postHash：
  - `apps/web/src/shell/AppShell.tsx`：`ea2a9a576ce666fff11600aca8d54e80124610b8459a1afd35d41837e735477d`
  - `apps/web/src/shell/AppShell.workshop.test.tsx`：`7aa1cdaecefe8b33a715a1ef568df9084eaa552f2f9b97afdd53907c2e05c675`
  - `apps/web/src/components/workshop/OperationsPage.tsx`：`90d44887145102539c9dbf044ec573903dfc04fb5bb9043d76ace2f6dd2a53e4`
  - `apps/web/src/components/workshop/OperationsPage.test.tsx`：`92c8ad0f2bdf1ba589cd078e20615224a2082346842282f7f2ad5273efcb17c6`

## 2. 三视口结果

| 视口 | 结果 | 四筛选 | 订单／售后详情 | 内部提案版本 | Receipt | 刷新 | 侧栏／滚动 | 水平溢出 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1280×720 | PASS | 4/4 | 4/4 | 1 → 2 → withdrawn | PASS | PASS | PASS | 0 |
| 1440×900 | PASS | 4/4 | 4/4 | 1 → 2 → withdrawn | PASS | PASS | PASS | 0 |
| 1920×1080 | PASS | 4/4 | 4/4 | 1 → 2 → withdrawn | PASS | PASS | PASS | 0 |

每个视口还完成：订单搜索命中、无匹配可信空、清空恢复；建议依据、页面 SOP、内部处理 SOP；`新建处理 → 采纳建议 → 保存并提交审批 → 处理日志 → 修改 → 提交修改 → 批准预览 → 驳回/撤回`；侧栏折叠／展开与主内容滚动到底。

## 3. 请求与副作用账本

- Action Proposal 截获写请求：`15`，每视口严格为：
  1. `POST /api/v1/aip/action-drafts`
  2. `POST /api/v1/aip/action-drafts/draft-isolated-v1/submit`
  3. `POST /api/v1/aip/action-drafts`
  4. `POST /api/v1/aip/action-drafts/draft-isolated-v2/submit`
  5. `POST /api/v1/aip/action-proposals/proposal-isolated-v2/withdraw`
- 所有 15 个 Idempotency-Key 非空且单视口唯一；两次 submit 均校验自身 draft revision/hash，withdraw 精确校验 proposal version `2` 与 proposal hash。
- timeline GET：每视口 `1`；请求级 observation GET：合计 `3`，均回读 ActionReceipt、OperationAuthorityReceipt 与 `replayAllowed=false`。
- `otherWrites=0`、`forbiddenWrites=0`、`unknownGets=0`、tenant 漂移 `0`、HTTP 5xx `0`、page error `0`、console error `0`。
- 批准 `0`、租约 `0`、执行 `0`、退款 `0`、发货 mutation `0`、Provider `0`、外部发布 `0`、真实业务 mutation `0`。

## 4. 验证命令结果

- OperationsPage + AppShell 定向测试：`24/24 PASS`。
- Web 全量：`280/280` files、`2508/2508` tests PASS。
- Production build：TypeScript 与 Vite PASS，`375 modules transformed`；保留既有单 chunk 大于 500 kB 的非阻断 warning。
- `verify_closure.py --phase ar2-7`：`scannedPythonModules=1711`、`classifiedModules=93`、`migratedModules=57`；`hashErrors`、正反向未分类依赖、跨层 import、动态引用错误均为空。
- `git diff --check`：PASS。

## 5. 证据哈希与边界

- 执行器：`138eac0ec532e887ae62827a4a8cfa8b2f7f4dcbd38df2e7c20ef3f65d2bc5ea`
- 机器证据：`44e5f9eb8a646fc93564496c0afe6b7a3f4e2939d64ecf5c1e0ece1bc031757a`
- `1280×720`：`9ed0f5884e68221f624e8780a2e75a3191700e076c5672366b3cf4113af406da`
- `1440×900`：`a14f323e123a226b017421d35229931d9d90f86abf098ad6e66d78f00981c86c`
- `1920×1080`：`ed77eb70399501cef8636c850c5b83d1d9f1273909fea13b9ffc251495e1554d`

所有运营 facts、命令就绪度、候选和观察均来自隔离合同 fixture；不含真实客户、订单、售后、库存或经营结果。批准预览只展示前置条件，没有产生批准或执行权威。本切片不前推 7E 总体标记，下一项为价格治理富数据功能验收。

## 6. 失败收敛记录

- 首次执行因筛选状态与可访问名称假设过严而停止，写请求为 `0`；改为明确回到“全部”并按可见文本定位。
- 第二次执行发现 timeline fixture 使用了错误字段名，页面正确失败关闭；改为合同要求的 `eventId/eventType`。
- 随后发现隐藏刷新控件的真实产品缺口，先冻结修复方案再完成产品修复与测试。
- 最后一次失败仅为两个隔离草稿复用了 fixture contentHash；改为按 draft id 生成独立哈希后，正式三视口一次全绿。未删除业务动作或降低断言。
