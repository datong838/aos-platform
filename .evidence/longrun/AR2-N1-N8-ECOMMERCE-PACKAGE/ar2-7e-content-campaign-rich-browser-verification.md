# AR2-7E 内容活动非空隔离功能验收

日期：2026-09-10

分支：`m1`

方案基线：`3c07d3be`

权威：`AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN`

结论：`PASS`（本切片通过，AR2-7E 整体尚未完成）

## 1. 浏览器结果

| 检查项 | 结果 |
|---|---:|
| 三视口 | `3/3 PASS` |
| workflow 命令 | `18`，每视口 `6` |
| 审批前预览 | `3`，每视口 `1` |
| 其他写请求 | `0` |
| 未声明 GET | `0` |
| page / console error | `0 / 0` |
| 提前停止 | `false` |

每个视口完成同一命令序列：

`generate → save → regenerate → apply_risk_decision(discount_margin) → apply_risk_decision(inventory_supply) → undo_risk_decision`

版本从 `1` 严格递增至 `6`；除首次 generate 外，每个请求的 `expectedVersion` 与 `draftRef.revision` 均精确指向前一版。六个 `Idempotency-Key` 互不重复。每个响应的 Provider 调用、Approval 创建、TaskRun 创建、外部发布和外部业务 mutation 均为 `0`。

## 2. 页面功能覆盖

- 三主页签：活动策划、内容日历、日常模板。
- 内容日历：内容排期与任务计划表往返，并回读一项隔离活动排期。
- 日常模板：全部、运行中、已暂停三筛选均可操作，且保持无正式模板的可信空边界。
- 活动列表：全部、内部草稿、正式记录三筛选往返。
- 正式输入：两件隔离商品、一项低库存 SKU、一项活动排期；选择第二件商品后详情回读匹配。
- 正式事实：CampaignRevision、CalendarEntryRevision、MasterContentIntentRevision、ContentVariant 及 `variant_of` lineage 均存在，三切片 ledger 与 page count 守恒。
- 内部草稿：新建入口清空旧状态，经营建议回填目标，生成／保存／重新生成、两类风险决策与撤销均返回新版本和 Receipt。
- 审批按钮：仅形成 `needs_input` 预览，显示“补充正式预算与素材评审条件”，没有创建批准或发布。
- 页内重新读取：正式 view 与 inputs 均新增 GET，fixture hash/count 未被草稿命令污染。
- 八菜单、唯一 H1、侧栏折叠恢复、滚动到末尾及三视口截图均通过，无水平溢出。

## 3. 失败关闭记录

首次浏览器执行使用折叠审计详情中的 `CampaignRevision` 作为可见加载标记，连续两个视口等待超时后按方案停止，workflow/preview POST 均为 `0`。数据实际已经加载，产品按设计把精确类型放在 `<details>` 中。执行器改为等待可见活动切片，并通过 DOM 审计文本验证折叠 lineage；未修改产品源码，也未降低数据和动作断言。第二次执行三视口全绿，失败诊断截图已删除。

## 4. 回归、一致性与边界

- Web 全量：`280 files / 2507 tests PASS`。
- Production build：`375 modules transformed`，TypeScript 与 Vite build 通过；仅有既有 chunk-size warning。
- Closure：扫描 `1711` 个 Python 模块，`classified=93`、`migrated=57`，五类 error 数组为空。
- `git diff --check`：通过。
- 产品源码三个 preHash 保持不变，本切片只新增执行器和证据。
- 所有 POST 均由 Playwright 路由截获，没有到达真实后端、数据库、Provider 或发布通道；证据不代表 A0-V/A1 的真实经营数据验收。
- 下一切片继续 `OperationsPage.tsx` 的来源计数、筛选、详情、处理草稿、审批预览和 Receipt，不前推 7E authority。
