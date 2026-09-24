# W5c3a 唯一独立 Runtime Host 空载启动验证（2026-09-24）

## 结论

**GREEN，限空载 Host。** launchd label `com.aos.a0v-w5c3-runtime-host` 唯一 PID 14022，状态文件 `RUNTIME_HOST_ACTIVE`、positive tenant `org-org/dev-project`、canaryTenantCount0、`liveTargets=[]`；8080 API `/openapi.json` HTTP 200。没有为新 successor 提交 prepare，仍 approved/etag3。DS 保持 uninstalled、九路 legacy/fenced、12 schedules disabled。

## 执行与效果边界

- 按计划 `eff060de`，使用现行 0600 runtime 身份、签名 bundle 根/信任根，非 KeepAlive launchd job 只加载一次；原 Host singleton lock 生效。Plist 校验 OK、定向测试 1 passed，`git diff --check` 通过。状态每 2 秒由同进程的 `LivePreparedJobDirectory` 报告，观察期间仅此 PID，未触发自动复活。
- 启动前后只读元数据计数保持：`pipeline_controlled_source_claim=40`、`meta_schedule_run=53`、Runtime 未终态 operation=0、历史未投递 outbox=22（全是已 cancelled/failed 的 enable/verify 事件）；12/12 schedule 仍 disabled。空载 business worker counters 全 0；未读商城源、未执行业务 Run、canary0。
- Host 状态文件与日志位于 `../.aos-recovery-20260920/state/q-advisor-baseline/20260924-w5c3a-host/`，私有目录；stderr 未见 Traceback/ERROR/SAFE_BLOCKED。若后续 PID 或状态漂移，下一波先冻结，不把本次启动记录当持续健康保证。

## 下一波 W5c3b

先方案，精确核当前 Host PID/状态/唯一租户、新 successor approved/etag3、无运行中 operation、签名/预算和九路/调度门禁，再用原 lifecycle Owner **一次**发 prepare；观察自然 Host 消费到正式终态和同进程真实 PreparedJob，然后才发 verify。每个 operation 单独 intent/Receipt 与未知边界，Host 异常按 preparation-reset/direct successor 正式恢复，不手工伪造 Ready。
