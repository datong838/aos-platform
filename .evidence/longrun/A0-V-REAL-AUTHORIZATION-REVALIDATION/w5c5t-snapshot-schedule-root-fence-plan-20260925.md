# W5c5t Snapshot Schedule Runtime 入口事务 opt-in 围栏方案（2026-09-25）

上位 W5c5r/s：原 metadata connector 在隔离 PG 的原 `_transaction` 内可采用 `aos_runtime` 调用 `a0v_094`。但 Schedule Runtime 的入口 claim/route 事务只是整组执行链开头；不能替代 Ingress、Completion、Store 外部 effect 围栏。真实 DB/Host 仍未启用。

## 文件级九步

1. 复习 `PipelineSnapshotScheduleRuntime.execute` 的 definition 读、整组 claim、route 两个 `_transaction`，与 W5c5s 原形连接角色证明。
2. 本方案；只改 `pipeline_snapshot_schedule_runtime.py` 的可选精确 `OptInHostLease` 及 `_transaction` 入体 guard，新增 `test_a0v_w5c5t_schedule_root_fence_pg.py` 与 verification。Recovery/Completion/Ingress/Store 不改。
3. 默认 None 原样；显式 opt-in 时每个 Schedule metadata 事务在任何 definition/claim/route 状态读写前，同事务 guard。未 acquire、错 scope/token/epoch、过期 fail closed；禁止以入口通过声称整个 execute 已获权。
4. 隔离 PG 原形 connector 覆盖默认/有效 holder 和失权故障注入；旧 Schedule 合同复测。
5. W5c3–W5c5t 累计回归，隔离 PG 停用。
6. 浏览器只读核 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 真实 Host flag 不启用，旧 attempt 不重发；下层事务和外部 Store effect 继续独立阻断。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5u：Recovery Runtime 入口事务 opt-in 围栏，继而分波覆盖 Completion/Ingress/Store；每步只认独立证据。

m1 单写不 push；商城源行不读；230 L0 挂起；dev-org 零 canary。
