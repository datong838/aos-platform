# AO qcursor 有界重载与自然后继 attempt 验证

## 结果

`AO_QCURSOR_BOUNDED_RELOAD_FAILURE_BOUNDARY_FROZEN`

本波消除了旧进程无限续租，但 AO saved recovery 没有成功。Worker 已停止，禁止继续自然领取；Store 未跨越提交边界，后续转正式 definition pause、installation retirement 与 direct successor。

## 重载与宿主边界

- 代码门禁提交：`2b55dd7c fix(a0v): guard AO natural recovery chain`。
- qcursor/API/Snapshot Worker：PID `64439` → `79092`；加载时间 `2026-09-19T04:49:59Z`。
- 独立 Runtime Host 始终保持 PID `59258`，未被重载；8434 Web 未变。
- 18181 direct health 与 8434 proxy health 均恢复 `{"status":"ok"}`。
- 新进程加载的 `recoverable_store_attempt.py` hash 为 `sha256:fbfd42394ce870f491fe9f2cd34ca2f480af3140053886897036493860327f91`。

## attempt 链

1. 原 attempt `67c2331d-b73f-4863-b881-0d67e6c55508` 在旧 Worker 停止续租后，于 `04:51:14.492568Z` 被 Runtime Host 正式置为 `abandoned` revision255，reason `ATTEMPT_LEASE_EXPIRED`。
2. 自然 Worker 于 `04:51:33.725001Z` 领取 ordinal-2 `dbcde37a-95ef-4f95-a586-61ab283cf5bb`；operation key、request hash 不变，幂等键仅从 `:1` 推进到 `:2`。
3. ordinal-2 在 `04:56:52.022117Z` 以 revision11 `failed`，reason `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED`、error type `IngressJournalConflict` 终结，证明 300 秒绝对上限已生效。
4. Worker 在停止命令到达前已于 `04:57:20.618466Z` 提交 ordinal-3 claim `70241ae9-7b18-40f5-9309-563594cd3e37`。进程随后被 bootout，该 attempt 没有 heartbeat；它必须由 Runtime Host 正式 expired-abandon 后才能进入 pause。该竞态不授权第四次领取。

## 数据与副作用边界

- 十二 Run 仍 frozen-running，十二 Dataset Receipt、一个 relationship、一个 link command/linkCount1168 不变。
- retirement=0、原 link Store Receipt=0、`ecom_link`=0、link Outbox=0、projection pending=0。
- AO 九路由和三资源保持；`dev-org/dev-project` canary=0。
- 没有手工 `run_definition`、源重读、Store 重发、installation 创建或 route 写入。
- qcursor LaunchAgent 已 bootout；Runtime Host 继续运行并负责回收 ordinal-3 Lease。

## 测试与限制

- AO guard/router/saved-recovery 专项：49 passed。
- recoverable attempt 加 AO 累计纯回归：60 passed。
- Python 编译与差异检查通过。
- 一次累计命令引用了不存在的 `test_generation_attempts.py`，pytest 在收集前退出；改用实际存在的纯测试集合后 60 项全绿。该命令错误不属于产品失败。

## 下一波

等待 ordinal-3 被正式 `ATTEMPT_LEASE_EXPIRED` 后，按新方案实现并执行 exact `pause-failed`，把 definition rev59 推进为 disabled rev60；随后实现 AO failed retirement/detach，再以 exact detach Receipt 创建 AP direct successor。全过程继续复用冻结输入和原 Store idempotency key，不启动 qcursor，直到 definition 已禁用且新代码/验收门禁完成。
