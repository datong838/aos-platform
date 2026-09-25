# W5c5x Single ingress metadata opt-in 围栏方案（2026-09-25）

上位 W5c5r–w 与 A0-V 真实关闭门禁：`ControlledSnapshotIngress._transaction` 是 claim/prepare、`_run_transaction` 与 Single `_finish` 的共同原 metadata 事务入口；`finalize_saved_dataset` 还有跨事务及 Store effect，不能以本波局部 guard 代替。真实 DB 仍 `a0v_092`，Host flag 关闭。

## 文件级九步

1. 复习 `pipeline_controlled_snapshot_ingress.py` 原事务、Single `_finish`、W5c5s 同形角色探针及 W5c5w Object 边界。
2. 本方案先提交。只改生产文件 `pipeline_controlled_snapshot_ingress.py`：构造器可选精确 `OptInHostLease`，在原 `_transaction` 的租户 GUC 之后、任何业务 body/绑定检查之前 guard；`_run_transaction` 复用该入口。新增 `test_a0v_w5c5x_single_ingress_metadata_fence_pg.py`；更新 W5c5r 静态合同及 W5c5s 无构造器测试替身的默认字段。Single Executor、Object 上层传参及 Store 本波不改。
3. 默认 None 与原路径一致；显式 opt-in 时每笔原 metadata 事务独立校验 holder。未 acquire/错 scope/epoch/过期 fail closed；不执行真实 claim/读源/Store。
4. 隔离 PG 同形 connector 覆盖默认、有效多笔、拒绝；旧 ingress 无 effect 边界定向测试。
5. W5c3–W5c5x 累计分组；保留旧 Schedule 完整套件超时、Attempt PG 17 skipped 债；停隔离 PG。
6. 浏览器只读核 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 复审原 metadata 事务共用入口与独立 Store effect；不把局部 guard 说成全链路排他。真实关闭门禁仍只读。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5y：从 Single Executor/上层 Object 显式传递同一 opt-in lease，逐层核独立 Store effect；Link/Retirement 另列。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
