# W5CB1｜容量启动中途检查点（未完成，2026-09-26）

## 边界结论

- W5CB1 方案因公共 `AipAgentRunService.transition` 与容量 Gate 各自提交而修订：容量启动与预算生成命令分为 W5CB1/W5CB2，不能声称单事务原子成功。此检查点不代表 W5CB1 完成，更不代表真实内容生成。
- 新 `a0v_103` 持久意图由 W5CB0 AgentRun ack 同事务写 pending；旧 accepted 不后补。一次 claim 后，任何容量／AgentRun 提交未知都留 claimed，不自动再次 transition。ack 必须读到同 TaskRun AgentRun running 和当前有效容量预留；`dev-org/dev-project` 零可见。
- 新容量 Owner 在 effect 前复验当前 Review/Brief/方法、不可变 Plan 责任槽、Skill 和 READY Route，并复核 queued AgentRun snapshot；经公共 AIP Owner transition 后独立读回 Reservation，再 ack。Worker 默认关闭，要求同进程 ACTIVE Host 和 runtime-only DSN。尚未应用生产迁移、未启 Worker、未调用 Provider。

## 新鲜验证

- RED：新容量 Owner 模块不存在时失败；新 `a0v_103` 文件不存在时 PG 测试失败。
- 专用 PostgreSQL 16：W5CAZ/W5CB0/W5CB1 最小意图夹具 **5 passed**，包括同事务 put、禁止历史补写、运行态与有效容量 ack、跨租户零可见。隔离容器 `aos-w5cb1-regression-pg` 已停止并自动移除。
- 邻接累计 **58 passed，7 既有 warnings**；包括容量 Owner 失败/成功路径、W5CAZ/W5CB0、真实公共 AIP 容量 transition 与责任槽夹具。`alembic heads`=`a0v_103`，Python compile 和 `git diff --check` 通过。

## 未关闭门和继续入口

- 尚缺同一个完整 PostgreSQL schema 内的真实 Handoff→Plan/Run→queued AgentRun 一体化夹具，以及新容量 Owner 的完整 schema 运行。现有是分段 PG 权威测试与 Owner 组装测试，不可宣称自然首链或生产运行成功。继续 W5CB1：补一体化夹具、检查 runtime-only 权限与跨提交对账、累计回归，浏览器可用时验收；完成 verification 后才能把本波判 GREEN。
- 审批、费用价格、事实来源、预算 HELD/Journal PENDING 属 W5CB2；ProviderRequestReceipt、MeasuredUsage、Artifact、人工评审、TaskRun 终态与 Wiki 更后置。原 12 Run 不重发，230 L0 挂起，不读商城源。
