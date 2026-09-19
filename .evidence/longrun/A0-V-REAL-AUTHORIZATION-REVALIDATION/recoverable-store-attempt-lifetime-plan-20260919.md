# Recoverable Store Attempt 有界寿命方案（2026-09-19）

## 上位问题

AO 证明 Worker 外层 deadline 不足以约束一个不返回的下层调用：`RecoverableStoreAttempt` 的心跳线程只等待上下文退出，当前实现没有绝对寿命，因此即使业务线程不再产生持久事实，attempt 和资源 Lease 仍可永久续期。既有数据库 Owner 已支持运行 Lease 到期后由 `abandon_expired_reads` 记为 `abandoned / ATTEMPT_LEASE_EXPIRED`，并只允许同 request hash、原幂等业务身份进入后续恢复。

## 最小设计

1. `RecoverableStoreAttemptOwner` 新增服务器固定 `max_execution_seconds`，默认 300 秒；必须为有限数，且大于 heartbeat 间隔、不超过 300 秒。
2. attempt 在 `__enter__` 时建立 monotonic 绝对截止时间。心跳每次等待取 heartbeat 周期与剩余寿命的较小值；到期时设置既有 `INGRESS_DEADLINE_EXCEEDED` 错误并停止续租。
3. 组合 cancellation 随 `_stop` 立即生效。遵守 cancellation 的业务阶段会退出并由上下文按既有固定终态原因结算；不遵守的阻塞调用不被强杀，attempt Lease 自然过期后由既有 recovery Owner 标记 abandoned。
4. 心跳线程自身触发的 deadline 仍归类为 `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED`，不得误写成数据库心跳失败；真实 heartbeat 数据库错误继续为 `RECOVERABLE_HEARTBEAT_FAILED`。
5. 不增加自动重试、业务重发、源读取、Store 调用或数据库迁移。当前 AO 旧进程不热加载，本波只保护正式重载后的后续执行。

## 文件级清单与验证

- 修改 `services/aos-api/aos_api/extension_runtime/recoverable_store_attempt.py`。
- 修改 `services/aos-api/tests/extension_runtime/test_recoverable_store_attempt.py`：参数边界和 deadline 归类。
- 修改 `services/aos-api/tests/extension_runtime/test_generation_attempts_pg.py`：真实心跳到达寿命后停止、attempt 以固定 deadline 原因失败；原 fence/settle 行为保持。
- 跑纯单元、隔离 PostgreSQL、snapshot recovery 相关累计回归、AR2 ar2-7 验证器、浏览器只读验收。
- 退出条件：无无限心跳路径；无强杀/重发；旧正常完成、外部取消、数据库心跳失败和过期 abandoned 语义不回归；证据与提交完成后立即进入 AO 正式 Host 重载/旧 attempt 失联处置波次。
