# W5CB2-P1｜内容预算意图与 Task 创建 Ref 合同阶段验证

## 定位与范围

- m1 单写者；上位 W5CB2 plan 为 `efbf583e`，本次先施工其 P1，W5CB2 **尚未完成**。
- 文件：`a0v_104_ecommerce_content_budget_command_intent.py`、`ecommerce_content_capacity_owner.py`、`aip_budget_reservation_store.py`、`ecommerce_content_budget_command_owner.py` 及相邻专项测试。
- `a0v_104` 仅提供默认无 Worker 的持久意图；容量 ack 与预算意图 put 同一事务，失败一起回滚。claim 最多一次；ack 要求同键预算 HELD、Journal PENDING、原生 Runtime Receipt 和原安装代次。未启生产迁移、未调 Provider、未读商城源，旧 12 Run 不动。
- 内容 Host 固定使用 Handoff 的 Task 创建 Ref，Plan/Run 增加当前 Task.version。预算 Store 原先只接受当前 version，形成必失败合同。现仅对正式 `public` schema 的 `ecommerce_growth_content_generate` 验创建 payload/request_hash、Task 执行态、当前已批准 Plan 的唯一 running Run；其他 operation 和原隔离 schema 合同保持旧行为。正式 Host 自身另验 Handoff/TaskBrief 原链。
- 价格 helper 只计算当前数值价格与 token 上限下的保守分位下界，要求原批准额度覆盖；它**尚未解析批准事件/价格快照**，不是可执行 Owner。

## RED / GREEN 与回归

- RED：新 Task Ref 测试先因 `_task_authority` 无 operation 参数失败 2 项；预算 Owner 测试先因模块不存在失败。既有预算 PG 回归首次暴露其隔离小 schema 无 `request_hash`，故将新合同严格限定正式 `public` schema 后重测。
- GREEN：预算 Task Ref + 价格边界 + 内容路由/容量邻近 28/28；`a0v_104` 隔离 PG 6/6；既有预算 PG/合同 14/14；真实 AIP Task Plan/Run 同事务创建后固定创建 Ref 验收 1/1。
- `alembic heads` 为单 head `a0v_104`；`git diff --check` 通过。浏览器验收不适用：本阶段无页面或启用入口。

## 仍未满足的退出门与立即下一步

1. 从当前 Review/Brief/AgentRun/容量/安装组、当前 Budget/Price/Approval/事实来源解析 12 项 exact Ref 和唯一合法命令；不制造额度或 Ref。
2. 预检后单次 claim，通过正式 `ContentCapabilityRequest` + Host Port 提交；未知结果冻结。独立读回 HELD+PENDING+Receipt 后才能 ack。
3. 默认关闭 Worker 接线、专项拒绝矩阵、累计回归和同库完整 Handoff→容量→预算链；然后另写 W5CB2 完整 verification，并同步 D-waves/AOS/Prime。任何生产激活另设硬门。

结论：P1 代码门 GREEN；业务链仍无内容预算命令的自然执行，更无生成产物。下一施工段为 W5CB2-P2，不进入 W5CB3。
