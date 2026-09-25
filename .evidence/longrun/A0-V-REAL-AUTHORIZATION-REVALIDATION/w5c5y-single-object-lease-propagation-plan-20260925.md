# W5c5y Single Executor→Object opt-in lease 传递方案（2026-09-25）

上位 W5c5r–x：Single ingress 原事务已可 opt-in guard，但 Single Executor 与 Object 未传 lease；Object 自身 `_transaction` guard 已可用，内部 `resume_saved/_finish` 独立事务仍无租约。真实 DB/Host 未启用，Store effect 不属于原 metadata 事务。

## 文件级九步

1. 复习 Single Executor 构造、Object 调用与 `finalize_saved_dataset` 独立 effect，核上层 Link/Retirement/Completion 的传递现状。
2. 本方案先提交。只改 `pipeline_controlled_executor.py`：可选精确 `OptInHostLease` 并原样传给 `ControlledSnapshotIngress`；`pipeline_snapshot_group_object_executor.py`：同一 lease 传给内部 Single。新增 `test_a0v_w5c5y_single_object_lease_propagation.py`，更新 W5c5r 静态合同。上层 Link/Retirement/Completion、Store 不改。
3. 默认 None 不变；显式 opt-in 时 Object 局部事务和内部 Single ingress 各独立 metadata 事务都由同一 holder guard。不得把 guard 表述为跨 Store commit 原子围栏。
4. 测构造精确类型与同一实例传递，隔离 PG 对内外事务成功/失权；旧 Single/Object 无 effect 边界定向。
5. W5c5k–y 围栏/结构累计回归，旧套件 skipped 如实记载，隔离 PG 停用。
6. 浏览器只读核 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 真实关闭门禁只读复核；未从 Completion/Link/Retirement 顶层传 lease，也未锁住 Store effect，真实组不关闭。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文和 Prime 独立受管记忆并读回。
9. 下一波 W5c5z：Link→Object、Retirement→Link 与 Completion→Retirement 的可选 lease 逐层传递；Store effect 保持独立风险门。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
