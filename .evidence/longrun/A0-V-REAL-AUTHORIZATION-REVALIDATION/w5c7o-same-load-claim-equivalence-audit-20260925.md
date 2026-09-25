# W5c7o 同一 `_load` Claim 复用负例与风险审计

W5c7n 的 383.229 秒 current claim 与 105.341 秒 completed claim 是性能证据，不是等价性授权。W5c7o 在专用 18432 隔离 PG 中新增三项**原行为**负例：完整原始 2-member 组每次消费有 callback 前后两次 `_load`，每次遍历成员再 `_bound_parent`；第一次 GroupClaim 读回已通过而 parent 独立重验拒绝时，consumer 未执行；callback 后当前发布权限撤销时，第二次 `_load` 拒绝。原 InputOwner 12 项与新 3 项合计 15 passed。completed 原质量 Owner 的读/禁写与 callback 当前发布复核 2 passed；recovery Authority 的持久权限复核 1 passed。测试临时 `aos_test_%` 库及 `ar1c_%` schema 均 0。

源码/迁移核对：`PipelineSourceClaimOwner.read_current` 通过 `_check_source_claim_loop` 保持同连接、同线程、同事务、同成员身份，在 `_operate` 内重新经过当前控制与 Schedule 守卫、run lock、原 claim 精确绑定。`GroupClaimOwner._operate` 与 `ControlledIngressJournal.verify_running_schedule` 分别调用它；后者仍执行原 Run/Schedule/Graph/Source 验证。`a0v_024` 的 claim 行 RLS、immutable trigger 与 runtime SELECT/INSERT grant 只保护历史行；不能推出安装/控制/运行状态在所有时间与所有可见性路径中不变。completed 用 `read_completed_current`/只读完成守卫；saved recovery 的 `_run_recovery` 是独立路径，不能混用 running 快照或新 source-call 权限。

**结论：未证明同一 `_load` 跳过第二次 claim Owner 读等价，生产优化不授权。** 测试注入拒绝证明保留重复读时会 fail closed，但不能证明任何替代算法可保持锁序、RLS/当前事务时钟、并发状态变化、完成/恢复路径与原异常语义。下一波需在专用 PG 精确验证 claim 锁序及并发改变/会话身份/角色的可见性，若仍不充分，保持原实现。真实 A0-V closure 一直无授权；不触商城源行、不重发旧 attempt。
