# Pending preparation directory 与 owner factory 验证

日期：2026-09-12

## 结论

新增 tenant-scoped `PostgresPendingPreparationDirectory`，只在 `aos_runtime` 独立事务中读取 immutable
event/outbox/operation 联结，输出尚未投递的 runtime-apply Installation descriptor。输出 UUID 排序、去重
且最多 100；它不 claim、不 ACK、不读 active binding、不派生授权。

`LiveInstallationOwnerFactory` 只接受 exact `PreparationWorker`、`LivePreparedJobDirectory`、connector 和
TenantScope，将 exact descriptor 组合成未启动的 `LiveInstallationLifecycleOwner`。跨租户 descriptor 和
伪依赖均拒绝。

## 实测

- directory/factory、上一波 owner 与 runtime host 邻接：31 passed。
- directory PG 与 preparation consumer PG：15 passed。
- 合计 46 passed；`py_compile` 与 `git diff --check` 通过。
- PG 覆盖 exact tenant、canary scope 零结果、delivered 过滤、verify-only 零创建、错误特权角色和脏连接
  查询前拒绝。全部只使用 18432 临时 schema，串行执行。

7 条既有框架 warning 和 pytest 退出后的 JDBC closed-stream 日志未改变成功 exit code。

## 一致性与剩余风险

- 实现满足方案中的只读、有界、固定 kind/consumer、租户隔离和 exact factory 边界。
- pending descriptor 只允许创建路径；apply ACK 后 owner 是否继续保留必须由下一波进程 scheduler 的
  cache 决定，不能用 descriptor 消失作为 stop 信号。
- active binding 不进入创建目录，防止重启后冒领已经丢失的 session；对应 recovery/reapply 编排仍待
  production host 集成。
- 正式 `PreparationWorker` 的签名制品 loader、schema conditions、三种 CurrentControlPermission 和 OCI
  driver composition 尚未接入。真实租户、Provider、安装状态和 1.4.0 均未改变。

## 下一波

实现有界 `LiveInstallationScheduler`：对新 descriptor 创建 owner，对已创建 owner 持续 tick；descriptor
消失不停止 live job，assignment 撤销或 host stop 才按 identity 收敛全部 owner。随后再接 recovery-first
host 顺序。
