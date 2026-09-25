# W5c5w Snapshot Object Executor metadata opt-in 围栏方案（2026-09-25）

上位 W5c5r–v；Object Executor 自身 `_transaction` 委派 Single ingress 的 metadata 事务，用于 group relationship preparation/readback；`_single.resume_saved/_finish` 内部又开独立事务并可能触发不可回滚 Store effect，不能由本波 Object guard 代替。真实 DB/Host 未启用。

## 文件级九步

1. 复习 Object `execute` 各 `_transaction`、Single ingress 角色、W5c5s 原形角色探针与 W5c5v Completion 边界。
2. 本方案；只改 `pipeline_snapshot_group_object_executor.py` 可选精确 `OptInHostLease`，包装 Object 自身 `_transaction` guard；新增 `test_a0v_w5c5w_object_metadata_fence_pg.py` 与 verification。Single/Link/Retirement/Store 不改。
3. 默认 None 原样；显式 opt-in 时 Object 自身各 metadata 事务在 body 前独立 guard。未 acquire/错 scope/epoch/过期 fail closed。不能宣称 Single 内部事务、Store effect 或上层 Link 已受保护。
4. 隔离 PG 同形 connector 覆盖默认/有效/失权，旧 Object 无 effect 边界定向测试。
5. W5c3–W5c5w 累计分组；旧 Schedule 完整套件超时、Attempt PG 17 skipped 债保留，隔离 PG 停用。
6. 浏览器只读核 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 真实 Host/DB 不启用，旧 attempt 不重发；本波只是可组合的局部事务能力。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5x：Single ingress `_transaction/_run_transaction` 原事务 opt-in guard，再审 `finalize_saved_dataset` 的独立 Store effect。

m1 单写不 push；商城源行不读；230 L0 挂起；dev-org 零 canary。
