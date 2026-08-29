# BI-W10 自然序列 P06～P08 连续验收

- 分支：`m1`
- 真实租户：`org-org/dev-project`
- 隔离 canary：`dev-org/dev-project`
- API 精确 owner：PID `14251`，唯一监听 `127.0.0.1:8080`，06:08 后未重启。
- 执行边界：只读取既有上海时区自然 Cron 结果；不手工运行 P01～P12、不重放 DLQ、不改时槽、不修改源业务数据、不触发 Provider 或发布。

## 时槽前工程复核

- P07/P08、SSH runtime 与 Cron guard 专项：`112 passed`。
- ecommerce、Workshop、SourceReadiness、JDBC 累计：`1269 passed`。
- Workshop Web 全量：`255` 个测试文件、`2314 passed`。
- TypeScript 与 production build：GREEN。
- 托管 SSH 隧道在时槽前持续监听且 TCP 可达；当前代码中的 P07 失效隧道精确驱逐/保活和 P08 可变快照观测版本逻辑均已加载到精确 API owner。

## 八菜单运行页功能复核

- 内置浏览器逐页重新打开日常任务、内容活动、统一运营、达人邀约、多媒体、经营参谋、价格治理、客户关系；每页恰好一个 H1，横向溢出为 `0`。
- 实际点击 16 个关键入口：日历、下达、活动新建/生成/保存/发布、运营筛选/新建处理、达人导入/邀约批次、多媒体任务、今日方案、价格导出/策略、客户导入/触达任务。
- 读操作确实切换视图；写入口在当前缺少正式业务意图时打开中文安全预检，未空点击、未崩溃、未写入伪业务记录、未触发外部效果。
- 日常任务页的客服专员、私域管家、导购顾问、数据参谋、内容官、活动策划师 6 个介绍浮层均逐个实际打开并关闭；每个浮层均展示专业能力、工作边界与当前状态，浮层完整位于视口内，未覆盖底部“明日预告”。
- 统一运营页逐个切换订单、订单明细、库存、发货、支付、售后、运营案例 7 个业务切片，标题与所选切片一致；6 个处理建议均进入中文安全预检，未触发真实业务操作。

## 自然运行事实

以下结果只在各自自然时槽后填写，禁止用代码测试或旧 run 代替。

| Pipeline | 上海自然时槽 | 新 run | source/projection | SourceReadiness | 裁决 |
|---|---:|---|---|---|---|
| P06 OrderLine | 07:00 | `2026-08-28T23:00:08.591057+00:00`，`succeeded`，`rowsWritten=936` | `234 / 234` | `ready` | 自然运行、同租户同截点计数与 readiness 闭合 |
| P07 Shipment | 08:00 | `2026-08-29T00:00:02.671566+00:00`，`failed`，`PIPELINE_EXECUTOR_FAILED` | `19 / 19` | `failed` | 自然运行证明缓存本地转发端口探活不能代表远端 DB 端到端可用；不得用既有计数覆盖失败 |
| P08 CustomerLite | 09:00 | 待自然时槽 | 待回读 | 待回读 | 待自然事实 |

P03 保留 04:00 自然失败事实；本记录不会把库存 reader 兼容性、现有 ProductSku source/projection 或其他 Pipeline 的成功冒充为 P03 自然恢复。

P07 本次失败后已按总计划 §117 最小修复：DB 建连通过 exact cached tunnel 失败时，按 cache key + 对象 identity 驱逐调用方实际使用的隧道；不在同一 run 内重试，不关闭并发 replacement。JDBC/Cron/P07/P08/Executor 专项 `83 passed`，compileall 与 scoped diff check GREEN。P07 业务恢复仍只等待下一自然时槽；修复将通过精确 API 重载供 P08 和后续自然运行消费。
