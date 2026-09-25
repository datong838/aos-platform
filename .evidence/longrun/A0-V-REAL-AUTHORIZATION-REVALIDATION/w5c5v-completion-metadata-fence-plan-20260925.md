# W5c5v Snapshot Completion metadata + Attempt opt-in 围栏方案（2026-09-25）

上位 W5c5r–u；Completion 的 `_transaction` 委派至原 Snapshot ingress，W5c5s 隔离 PG 已证明该连接在原事务内采用 `aos_runtime`、可调用 `a0v_094`。Completion 的 claim、completed replay 读取、stopped recovery、最终 `_finish` 属于本类 `_transaction`；下层 Retirement/Link/Object/Single 内部各自事务及不可回滚 Store effect 仍独立。真实 DB/Host 未启用。

## 文件级九步

1. 复习 Completion `complete/_finish` 各 `_transaction`、Attempt claim-before-execution/heartbeat/settle 与 W5c5q Attempt 可选 guard。
2. 本方案；只改 `pipeline_snapshot_group_completion.py` 的可选精确 `OptInHostLease`，包装其 `_transaction` 在原事务入体 guard，并把同一 lease 传给内部 `RecoverableStoreAttemptOwner`；新增 `test_a0v_w5c5v_completion_metadata_fence_pg.py` 与 verification。下层委派执行器与 Store 不改。
3. 默认 None 原样。opt-in 时 Completion 每笔 metadata 事务与该类创建的 Attempt heartbeat/settle 各自独立 guard；不能以一次通过覆盖后续事务。未 acquire/错 scope/epoch/过期 fail closed。未知提交不重试旧 attempt。
4. 隔离 PG 同形 connector 覆盖默认/有效/失权及同一 lease 传递；旧 Completion 合同仅选可有界运行项。
5. W5c3–W5c5v 累计分组，保留旧 Schedule 完整套件超时与 Attempt PG 17 skipped 债；隔离 PG 停用。
6. 浏览器只读核 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 本波不触碰下层 Object/Link/Retirement/Single 独立事务或 Store effect；不启用真实 Host/迁移，不执行旧组关闭。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5w：逐层设计/接线 Object→Single 原 metadata 事务，再按独立 Store effect 边界推进；不得宣称全链路排他。

m1 单写不 push；商城源行不读；230 L0 挂起；dev-org 零 canary。
