# AO 保存恢复有界执行与心跳诚实性方案（2026-09-19）

## 现状与问题

AO `recoverable_store` attempt `67c2331d-b73f-4863-b881-0d67e6c55508` 自 `2026-09-19T02:41:41Z` 起持续运行。只读复核至 attempt revision 203：心跳与 Lease 持续续期，十二 Run、十二 Dataset Receipt、一个关系和一个 1168 链接命令保持原边界；Retirement、链接 Store Receipt、`ecom_link` 与链接 Outbox 均为零。进程、数据库活动与离线命令校验共同表明，没有证据证明 Store 阶段正在推进。

上位方案要求受控执行有界，`Phase5PipelineEngine` 已把执行上限限制为 300 秒；但 `PipelineSnapshotScheduleWorker.run_definition()` 在自然承接保存恢复时把调用方的 `deadline=None` 原样传给 `PipelineSnapshotGroupRecoveryRuntime.resume_saved()`。因此 `_check_active` 没有截止时间，attempt 心跳线程可继续续租，使只看 90 秒心跳的 AO 守卫把“超过受控执行上限、无新持久事实”误报成健康推进。

## 本波目标与边界

1. Worker 对每次保存恢复建立固定 300 秒单次执行截止时间；调用方已有更早 deadline 时只取更早值，不能扩权或延长。
2. 截止时间继续通过既有 `deadline` 参数逐层传递，由原 Authority、幂等 Receipt 与未知结果规则处理；不新增重试、不重读源、不创建新 Run、不合成失败事实。
3. AO 只读守卫把“心跳健康但 attempt 已超过 300 秒且 Store 后段仍完全为零”识别为 `RUNNING_HEARTBEAT_ONLY_DIAGNOSE`。该结果仍为 `automaticAction=false`，只允许冻结边界诊断，不能退休、重发或启动 successor。
4. 当前 AO 运行进程不热加载本次修改，也不被终止。本次修复约束后续自然恢复；当前未知边界继续只读观察到明确 succeeded/failed 或控制窗口终止。

## 文件级清单

- 修改 `services/aos-api/aos_api/pipeline_snapshot_schedule_worker.py`：在保存恢复入口生成有界 deadline。
- 修改 `services/aos-api/tests/extension_runtime/test_snapshot_worker_recovery_pg.py`：验证默认 deadline、调用方更早 deadline 和过期拒绝。
- 修改 `scripts/a0v_ao_attempt_guard.py`：加入超过执行上限且无 Store 进展的只读诊断分类。
- 修改 `services/aos-api/tests/extension_runtime/test_a0v_ao_attempt_guard.py`：覆盖健康短时、心跳仅续期、部分 Store 未知边界。
- 修改 `scripts/a0v_ao_continuation_router.py` 与对应测试：把新分类唯一映射到 AO 有界执行诊断。
- 新增本波验证文档，记录测试、实时只读结果、浏览器验收、风险和下一波。

## 验证与退出条件

- 专项单元/隔离 PostgreSQL 测试覆盖新 deadline 与新分类，旧正常、stale、success、failed 路由不回归。
- AO 实时只读守卫必须输出新诊断，且所有持久业务计数与调用前一致；禁止把它解释成失败或重发授权。
- 累计 A0-V 专项回归与清册验证器通过；浏览器仍能访问当前服务并保持租户禁入/页面基线。
- 方案与代码复审确认没有新的写入口、重试、源读取或越权副作用；仅提交本清单文件。
- 完成本波后立即进入“当前 AO 未知边界终态守护/正式退休决策”下一波；若 AO 已 succeeded，改走 inspect/disable；若 failed，先冻结并核对未知提交边界。
