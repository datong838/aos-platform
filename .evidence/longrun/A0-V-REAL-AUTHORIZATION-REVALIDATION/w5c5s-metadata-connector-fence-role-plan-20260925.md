# W5c5s Snapshot metadata connector 与 worker fence 角色探针方案（2026-09-25）

上位 W5c5r：Snapshot Schedule/Recovery/Completion 由 `PipelineControlServicesFactory.build_snapshot_worker` 传入 `runtime_worker_connection`；事务用 `apply_asset_transaction_scope`，其角色切换取决于当前 schema/RLS 契约。`a0v_094` 需要 runtime 登录成员、exact session/current role 与 Host assignment。真实 DB 仍未迁移。

## 文件级九步

1. 复习生产构造 `pipeline_control_service.py`、`runtime_connections.py`、`tenant_transaction.py` 与 `a0v_094` 精确 role 检查。
2. 本方案；只新增 `test_a0v_w5c5s_metadata_fence_role_pg.py` 与 verification，不改生产连接或权限。隔离 PG fixture 模拟与生产同形的无预设 SET ROLE 连接，进入 `ControlledSnapshotIngress._transaction` 前后读回 `session_user/current_user/GUC`，调用同事务 Worker fence；不得读取商城数据行。
3. 有效 holder 与未 acquire/错 epoch/错租户/过期必须 fail closed。若角色不兼容，只记录不强接线；不得改真实权限。
4. 隔离 PG 专项测试精确角色、guard 可调用性、事务结束角色/GUC 复原；无外部 effect。
5. W5c3–W5c5s 累计回归；隔离 PG 停用。
6. 浏览器只读核 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 结果只能证明隔离环境兼容性，不能证明真实 DB 已迁移或 Host 全链路排他；生产接线另波。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5t：若探针绿，给 Snapshot metadata 根事务加可选 Host lease guard，并明确每个下游独立事务和 Store effect 仍需分波；若红，先设计专用 metadata fence。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
