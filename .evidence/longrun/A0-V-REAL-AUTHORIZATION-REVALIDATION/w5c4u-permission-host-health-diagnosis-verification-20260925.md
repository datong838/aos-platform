# W5c4u 独立失败链只读诊断核验（2026-09-25）

上位 231 A0-V、231-9 BG-00；本波方案 `w5c4u-permission-host-health-diagnosis-plan-20260925.md`，先行提交 `6752fa41`。本波没有代码或业务库写入，没有 Host 重启、closure、retire、旧代补跑或商城源行读取。

## 九步结果

1. 复习 W5c4r/s/t 权威证据与原 Owner。唯一 attempt `a5e60b0d-2d97-44d0-88bf-9f08990624d1` 在 `2026-09-24 20:06:20.003281 UTC` 正式 failed，类型 `PermissionError`；Host PID17302 同期 stopped。
2. 实际文件范围仅本方案和本 verification，未改生产代码。复核 `pipeline_snapshot_group_recovery_authority.py`、`pipeline_snapshot_group_completion.py`、`recoverable_store_attempt.py`、`lease_renewal.py`、`verification_commit.py`、`preparation_worker.py` 及原 Host stdout/stderr。
3. Host stdout 的原异常栈精确到 `preparation_worker._renew`→`lease_renewal.renew_verified_lease` 第177行→`verification_commit._fresh_health` 第31行。`_fresh_health` 在 DB clock 与可信探测时间差大于 3 秒时抛 `HealthObservationStale`；原记录只证明跨过该门，**不能证明耗时来自哪一次锁等待、DB 调用或调度延迟**。Host stdout 报 `HOST_RUNTIME_FAILED`；stderr 未记录该 attempt 的 PermissionError 消息。
4. `recoverable_store_attempt._terminal_failure` 对一般异常只保留 `RECOVERABLE_EXECUTION_EXCEPTION` 与错误类型，不存原文/栈。可达候选分支包括原 executor 不一致、当前 recovery definition/executor 权限、group common window、安装 invocation 权限等；现有正式 attempt 行不能唯一定位。当前权限值即使可读也不能反推事故时值。结论 `PERMISSION_THROW_SITE_UNKNOWN`，不可猜测修复或放宽权限。
5. 无代码变更；沿用 W5c4t 隔离累计回归 **102 passed**，本波再次执行只读资格脚本仍为 `STALLED_WAIT_24H`、`automaticAction=false`、effect 非零拒绝未接受路径。未使用共享测试库。
6. 浏览器 5174 `/data/schedules` 再次只读看到 12 单路计划；页面不提供原异常链/整组正式 rev4 证明，`BROWSER_PARTIAL`。未触发同步或队列冲刷；临时页和前端均关闭。
7. 方案一致性：Host 的健康过期和 attempt 的 PermissionError 是两条已观测失败链，时间相近不等于因果；18181 仍只有 worker PID37241 listener，Host 已停，不混同。定义 rev4 disabled、12 Run running、正式关闭/退休未完成，24h 严格门不变。
8. 本 verification 先提交，再 CAS 同步 AOS 项目开发上下文与 Prime 独立受管记忆，读回单列 docs 提交。
9. 下一波 W5c4v：先设计**不改变权限判定、不泄露敏感信息**的错误分类可观测性和 Host 续租探测时序测试/最小修复；先 RED，再最小编码、累计回归、浏览器、证据。若当前无法可证伪复现，明确 UNKNOWN；严格 24h 到达后另波正式 Owner 收敛，不拿诊断代替关闭。

停止/冻结：第二 attempt、定义/效果/Receipt 漂移、提交边界未知均禁止重发。A0-V/BG-00 仍未通过，230 L0 仍挂起。
