# AR2-7E 任务总控非空隔离功能验收

日期：2026-09-10

分支：`m1`

方案基线：`7259d976`

权威：`AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN`

结论：`PASS`（本切片通过，AR2-7E 整体尚未完成）

## 1. 执行范围

- 执行器：`ar2-7e-task-cockpit-rich-browser.mjs`
- 机器证据：`ar2-7e-task-cockpit-rich-browser.json`
- 三视口截图：`1280×720`、`1440×900`、`1920×1080`
- 数据边界：仅使用不含真实凭据、客户信息或经营结果的隔离合同 fixture。
- 写入边界：每个视口只允许第二次确认触发一个被 Playwright 截获的 `/api/v1/aip/tasks` POST；请求未到达 AOS 后端或数据库。

## 2. 浏览器结果

| 检查项 | 结果 |
|---|---:|
| 三视口 | `3/3 PASS` |
| 安全预检 POST | `0` |
| 隔离 Task POST | `3`，每视口恰好 `1` |
| Task 创建后权威列表回读 | `3/3` |
| 数字同事浮层 | `18`，每视口 `6` |
| 共享能力浮层 | `30`，每视口 `10` |
| 复盘区 | 每视口固定 `今日复盘 / AI 改进建议 / Wiki 今日入库` 三段 |
| 执行/策划栏 | 每视口 `2` 栏 |
| 状态筛选、日历、侧栏、滚动到底 | `3/3` 完成往返 |
| Workshop 写请求 | `0` |
| 其他写请求 | `0` |
| 未声明 GET / tenant header 漂移 | `0 / 0` |
| HTTP 5xx / page error / console error | `0 / 0 / 0` |
| 水平溢出 | `0` |

Task POST 逐项核对了：

- 类型固定为 `ecommerce.workshop.business_task`；
- 标题来自经营参谋 exact 指标推荐，含中文业务语义；
- `Idempotency-Key` 使用 `workshop-task-*`；
- 建议承接角色为 `shopping_advisor / 导购顾问`；
- `sourceEvidence` 同时携带订单、商品的 MetricDefinition 与 MetricObservation exact 引用及数据 cutoff；
- 返回 `fixture-task-1` 后，总控再次 GET 并显示“已在任务流回读”。

## 3. 失败关闭与修正记录

首次执行时 Analyst 顶层 readiness 与严格 parser 不一致，推荐区失败关闭；连续两个视口失败后执行器按方案停止，POST 为 `0`。修正为现行 `degraded` 合同后，核心业务路径通过。随后仅剩测试执行器定位范围和 fixture 守恒问题：状态筛选文本定位过宽、创建后待规划总数由一项变为两项、Memory 的 SourceRef 与 payload/contentHash 不一致。修正严格合同和定位器后，未降低任何产品断言，最终三视口全绿。失败诊断截图已删除，正式证据仅保留最终态。

## 4. 回归与一致性

- Web 全量：`280 files / 2507 tests PASS`。
- Production build：TypeScript 与 Vite build 通过，`375 modules transformed`；仅保留既有 chunk-size warning。
- Closure：`verify_closure.py --phase ar2-7` 通过；扫描 `1711` 个 Python 模块，`classified=93`、`migrated=57`，所有 error 数组为空。
- `git diff --check`：通过。
- 方案一致性：三视口、两阶段确认、唯一隔离 Task POST、创建后回读、六同事、十能力、三复盘、双栏、明日预告、筛选、日历、侧栏和滚动检查均已落实。

## 5. 风险与下一步

- 本证据证明 Task Cockpit 的隔离非空合同路径与浏览器交互，不证明真实租户数据或真实 Task mutation；真实只读经营数据继续留在 A0-V/A1 边界。
- Task POST 由浏览器路由截获，因此没有 Provider、费用、客户触达、发布、迁移或外部副作用。
- AR2-7E 尚不能关闭；下一切片继续按 231-6 对其余七个 Workshop 页面执行非空数据、按钮、刷新、跳转与回读验收。
