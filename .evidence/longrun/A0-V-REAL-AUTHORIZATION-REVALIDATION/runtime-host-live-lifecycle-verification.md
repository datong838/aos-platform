# Runtime host live lifecycle 编排验证

日期：2026-09-12

## 结论

`RuntimeTenantAssignment` 已支持 same-scope exact `LiveInstallationScheduler`，host 顺序固定为资源 recovery、
attempt recovery、live lifecycle、configure、disable。disable consumer 将旧 `run_once` 等价拆为 exact
`claim_once`/`finish_claimed`；带 lifecycle 时 host 持有 claim，按同 operation 的 Installation identity
撤销 live owner 后才执行原 executor 和 ACK/retry。

assignment identity 在 lifecycle 内或阶段间被替换/删除时，旧 scheduler 立即 stop，不依赖是否存在后续
consumer。host stop 即使 tick 失败也会收敛全部已追踪 scheduler。revoke cleanup 抛错时不调用
`finish_claimed`，因此零 disable execute、零 ACK。

## 实测

- runtime host、scheduler、owner：34 passed。
- disable/directory/preparation/owned-control 真实 18432 PG：43 passed。
- production selector/startup composition：28 passed。
- runtime host directory 真实角色/CAS PG：11 passed。
- 合计 116 passed；`py_compile` 与 `git diff --check` 通过。

开发中两项回归均先被测试捕获并修正：无 consumer 的 assignment replacement 曾漏 stop；disable 末次
回读曾沿用旧三字段解包。最终批次已完整覆盖。7 条既有 warning 和 JDBC 退出 closed-stream 日志不改变
exit code 0。

## 一致性与剩余风险

- claim、Installation identity、revoke、finish 顺序与方案一致；失败时 lease 保持未 ACK，等待既有租约/
  recovery 规则处理。
- production selector 当前仍创建 `lifecycle=None`，所以线上行为没有提前改变；正式 worker 依赖未齐时
  继续 fail closed。
- 下一波必须从持久 Registry 真值与 allowlisted bundle source 构造 record/artifact reader，并组合
  APPLY/VERIFY/ENABLE 当前权限、schema conditions、OCI driver 和 control-plane 唯一 directory。
- 本波未启动业务 OCI、未调用 Provider、未写真实租户、未改 1.4.0，也不构成 A0-V 完成证明。

## 下一波

实现正式 `ProductionPreparationDependencies` 与 builder，完整封装签名 Registry record/artifact 读取和
PreparationWorker 构造；先保持 selector 纯构造、零启动，再将 per-tenant directory/factory/scheduler
接入 production assignment。
