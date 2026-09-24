# W5c4s 失败自然定义停用与权限诊断方案（2026-09-25）

上位约束：231 的 A0-V→A1 与 231-9 的 BG-00→BG-01/02；W5c4r 正式失败验证 `0c9a8c42`。当前目标是**阻止 rev3 enabled 定义明日再次自然触发**，不是恢复本次 Run，不是 A0-V 成功。唯一 attempt 已 `failed / RECOVERABLE_EXECUTION_EXCEPTION / PermissionError`；Host PID17302 因 `HealthObservationStale` 停止，12 Run 仍 running、Store/link/projection 本次零增量。原 generation 不手工 `run_definition`、不重发、不读商城源行。

## 本波九步与文件级清单

1. 复习上位方案和当前代码：`pipeline_snapshot_schedule_definition.py` 的 `disable` 可从 enabled 进入 disabled，保留 12 current member、将 12 schedule 设 off；`retire` 必须先 disabled，且运行中/未知 Run 为 0，故**本波只能先正式 disable，不能跳过阻断直接 retire**。复核 `pipeline_snapshot_schedule_service.py`、W5c4q 启用 intent/ref、W5c4r 失败证据。
2. 文件级范围：新增本方案、`scripts/a0v_w5c4s_disable_failed_definition.py`、`services/aos-api/tests/extension_runtime/test_a0v_w5c4s_disable_failed_definition.py`、本波 verification。仅此脚本的 `disable` 阶段可能产生定义/调度控制写入；诊断、preflight、audit 均只读。
3. 最小实现：先只读读回精确 rev3/hash/状态、唯一 cron group/attempt 及 12 Run、Store26/live link0/pending0/canary0、18181 唯一 worker、Host 已停止、目标 disable key 尚未使用；必要权限 `service.read` 必须通过。使用固定新 key `a0v-w5c4s-disable-after-natural-failure-20260925-v1`，调用前将 exact intent 0600 独占落盘，随后原 `SnapshotScheduleService.transition(intent='disable', expected_ref=rev3)` **只调用一次**。若调用拒绝或结果未知，保留 intent，只读查 key/head，不重发、不手工改表。
4. 专项测试：先 RED 后最小实现，覆盖精确失败门、第二 attempt/副作用/Host 复活/定义漂移/已用 key 拒绝、调用仅一次与未知结果不重试；不使用商城源数据。
5. 累计回归：隔离测试库运行 W5c4r 与 W5c4s 及定义 transition 相关测试；不得用共享数据库。失败只陈述实际范围。
6. 浏览器验收：AOS 独立前端只读查看 12 条计划 off 与整组配置；页面缺已安装实例时记 `BROWSER_PARTIAL`，仍以原 Owner/DB 为控制验收，不点队列冲刷/运行。
7. 一致性复审：result/ref、head rev4 disabled、唯一 key revision、12 current member rev4、12 schedule off、原 group/attempt/Run 与 Store/link/projection 不变；Host/worker 变化或任何权限不明冻结。诊断 `PermissionError` 与 `HealthObservationStale` 只做源代码、日志、当前权限的只读定位，不在本波重载 Host 或尝试恢复。
8. 证据/上下文：先最终 verification 并提交 m1，再按 expected revision CAS 更新 AOS项目开发上下文与 Prime 受管投影；保护 docs 其他 dirty 文件。
9. 下一波 W5c4t：以 disabled 定义和唯一失败组为锚点，正式收敛/退休旧 Run 与定义的资格，定位并最小修复具体权限/健康门；只有正式退休及独立回读后才设计 direct successor。禁止旧代重发，230 L0 继续挂起，dev-org 仅零 canary。

停笔条件：任何头/ref、group/attempt、Run、Store/link/projection、tenant、permission、key 或提交边界与本方案不符，即只读冻结，不调用 `disable`；调用后未知不补第二次。特别是 `disable` 与 `retire` 语义不得混淆，停用不是完成或释放 Run。
