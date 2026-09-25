# W5c5q RecoverableStoreAttempt 心跳/收尾围栏方案（2026-09-25）

上位 W5c5h–W5c5p；真实 DB/Host 仍未启用 `a0v_093/a0v_094`。`PipelineSnapshotGroupCompletion` 在原有外层事务中 claim，提交后才进入 `with attempt`；心跳与 settle 各有独立 `consumer_connection`，失败/未知提交一律不能重发。故本波只加 opt-in 事务 guard，不触碰 claim 的上游整体事务，也不改变失败分类或重试策略。

## 文件级九步

1. 复习 `recoverable_store_attempt.py` 心跳、settle、取消及旧自然 attempt 的正式失败证据；复核 `consumer_connection` 和 W5c5k worker fence。
2. 本方案；只改 `recoverable_store_attempt.py` 的 Owner/Attempt 可选精确 `OptInHostLease` 依赖，并新增 `test_a0v_w5c5q_recoverable_attempt_fence_pg.py` 与 verification。`pipeline_snapshot_group_completion.py`、真实 Host、DB/迁移不改。
3. 默认 None 保持旧路径。显式 opt-in 时心跳/settle 分别在各自事务第一步 guard；租约失效中止心跳与 settle，不得借旧 attempt 执行任何新业务。若心跳提交结果未知，维持 stop/fail closed，不自动复用旧 revision。
4. 隔离 PG 专项覆盖有效/默认心跳与 settle 的同事务 guard、未 acquire/错 epoch/过期/错租户拒绝；旧 unit/PG Attempt 合同复测。不可制造真实旧 attempt。
5. W5c3–W5c5q 累计分组；记录跨模块 `AOS_DATABASE_URL` 夹具顺序债，隔离 PG 停用。
6. 浏览器只读核 A0-V rev4 disabled；不保存/运行/冲刷队列。
7. 本波不是完整 Host/外部 effect/Owner 围栏；不应用真实迁移，不启用 flag，不重发/重建旧 attempt；真实关闭门仍独立。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5r：盘点 `PipelineSnapshotGroupCompletion` claim 上游事务及其它未围栏 Owner 写路径，按危险度拆波，不用本波的局部覆盖宣称全链路安全。

m1 单写不 push；商城源行不读；230 L0 挂起；dev-org 零 canary。
