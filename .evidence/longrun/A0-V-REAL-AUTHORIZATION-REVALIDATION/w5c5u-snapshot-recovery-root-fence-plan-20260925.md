# W5c5u Snapshot Recovery Runtime 入口事务 opt-in 围栏方案（2026-09-25）

上位 W5c5r–t；Recovery `resume_saved` 在唯一入口 metadata 事务中核 recovery receipt/current definition/original claim，退出后再让 Completion 走独立执行链。W5c5s 已在隔离 PG 证明同形 metadata 连接可在事务内采用 `aos_runtime` 调用 `a0v_094`。真实 DB/Host 未启用。

## 文件级九步

1. 复习 Recovery `_transaction`、saved-only 不源读契约、Completion 原始事务/Store effect 边界及 W5c5t Schedule root 接线。
2. 本方案；仅 `pipeline_snapshot_group_recovery_runtime.py` 加可选精确 `OptInHostLease`，唯一入口事务入体 guard；新增 `test_a0v_w5c5u_recovery_root_fence_pg.py` 与 verification。Completion/Ingress/Store 不改。
3. 默认 None 原样；显式 opt-in 时 receipt/current definition/original claim 读取前验证 scope/token/epoch/expiry；失权不进入业务体。入口成功不授权后续 Completion/Store。
4. 隔离 PG 同形 connector 测默认/有效/未 acquire/错 scope/epoch/过期；旧 Recovery 合同定向复测，不做真实旧组恢复。
5. W5c3–W5c5u 累计分组；旧 Schedule 全套超时拆分定位并如实记录，隔离 PG 停用。
6. 浏览器只读核 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 不启用真实 Host flag/迁移，旧 attempt 不重发；未有全链路围栏或关闭授权。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5v：Completion claim/finish/stopped recovery 各事务 opt-in guard；下层独立事务和 Store effect 后续另波。

m1 单写不 push；商城源行不读；230 L0 挂起；dev-org 零 canary。
