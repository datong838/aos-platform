# Recoverable Store Host 续租与健康时钟闭包验证

## 1. 结果

- recoverable Store fast path 在 installation 与 binding 同时被另一事务行锁时仍能完成三资源续订。
- 最终资源 UPDATE 前 binding revision 漂移时，三项 expiry 不变且不写 renewal event，整笔回滚。
- 健康时钟以同一数据库时钟夹住完整探针；只有正向 stale 在首事务结算后完整重探一次，未来时间立即失败。
- 本波没有迁移真实库、重载 Host、创建 successor、读取商城、调用 Store 或模型。

## 2. 真实锁竞争验证

- 显式 `AOS_EXTENSION_PG_TEST=1`，使用 18432 隔离 PostgreSQL 临时 schema。
- 场景一由 blocker 事务同时 `FOR UPDATE` 锁住 installation 与 binding；worker 仍在 2 秒断言内锁定 exact
  attempt/operation/resources，以 binding statement-time CAS 推进全部三个 expiry 并写一个
  `runtime_inflight_lease_renewed`。
- 场景二在资源 UPDATE 前由第二连接递增 binding revision；UPDATE 返回零行，Owner 抛
  `live Store resources expired before renewal commit`，事务回滚后三个 expiry 与 event 数量均保持原值。
- 结果：2 passed、7 个既有依赖 warning，4.17s。

## 3. 专项与累计回归

- lease renewal、PreparationOwner、PreparationWorker、owned verification：72 passed、7 warnings，4.59s。
- session health、persistent supervisor、Runtime Host、lifecycle、disable executor：48 passed、5 skipped、
  7 warnings，4.17s；5 个 skipped 为既有环境条件分支，没有计作通过。
- a0v089 attempt/UI PG 35 passed、saved recovery/Worker/UI recovery 17 passed 继续作为相邻累计证据。
- Python compile、`git diff --check` 及方案/代码逐项复审通过。

## 4. 方案一致性与风险

- 快路径不读取或修改 installation current，不修改 binding、attempt、definition、control 或业务记录；无 live
  attempt 时原完整 permission/revalidation 路径不变。
- ordinary binding read 只用于取得 exact CAS 参数；最终资源 UPDATE 同时验证 binding revision、epoch、enabled、
  unfenced、ready 与完整 resource handle，避免把旧快照当成授权。
- attempt、operation 与 resources 仍串行锁定；attempt terminal/过期/不新鲜、资源过期或 proof 漂移均拒绝。
- 健康重探最多一次，不能把数据库故障或未来时间变成循环重试；第二次失败由原 Owner 关闭流程处理。
- 这证明 Host 能维持合法在途资源，不证明业务 Store 完成，也不授权重发未知结果。

## 5. 下一波

单独关闭 OCI unknown-cleanup 的双标识 absent 确认；随后在无 running attempt 空窗执行 a0v089 备份迁移，
重载 Host/Worker 并完成只读基线，最后才允许 Worker 通过正式 definition 自然产生 AN direct successor。
