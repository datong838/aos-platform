# W5c4f 第三继任者 12 ScheduleBinding 验证（2026-09-24）

方案基线：`w5c4f-third-successor-schedule-bindings-plan-20260924.md`，已先行提交于 `372a42fa`。执行入口为 `scripts/a0v_w5c4f_successor_bindings.py`；私有 0600 intent/result 位于仓库外 `../.aos-recovery-20260920/state/q-advisor-baseline/20260924-w5c4f-successor-bindings/`，不提交到 Git。

1. 08:03 UTC `preflight` 返回 `W5C4F_BINDING_PREFLIGHT_GREEN`：Host PID 17302、业务 claims40/runs53、目标12，旧 DS 最新绑定对应每一目标，新安装绑定0、current member0、schedule enabled0；当前 controls/retirement/resume 门禁均通过。
2. P01→P12 各先写私有意图，再调用正式 `PipelineControlServices.bind_schedule` 一次，立即保存逐条 ref；`issue` 返回 `W5C4F_BINDINGS_ACCEPTED`、members12。没有重发、手工 Run、读取商城源行或启用 schedule。
3. 08:03 UTC 独立只读 `audit` 返回 `W5C4F_TWELVE_BINDINGS_GREEN`：新安装/代际绑定12，逐条 controlRef 精确匹配，沿用旧 binding ID 且 revision 连续+1、previousHash 精确匹配；current member0、enabled0，业务计数仍 claims40/runs53，Runtime/Host/退休/恢复状态未漂移。
4. `py_compile` 通过。执行前修正审计中数据库 UUID 与 ref 字符串的比较类型；未改变正式 Owner 的行为。

本波结论：**12/12 ScheduleBinding 完成，定义尚未配置或启用，自然 worker 未启动。** 下一波先只读取得正式 `SnapshotScheduleService.options` 的当前 policyRef/12 members，再独立配置 disabled definition；启用必须另波核对控制窗口和预算有效期，不能据此验证代替生产授权。
