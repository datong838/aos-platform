# W5c4q 第三继任者自然调度启用方案（2026-09-24）

W5c4p `0812ddd7` 已恢复唯一独立 18181 worker；W5c4o `df3d3ca8` 的定义 rev2 disabled、12 schedule off。当前 cron `0 4 * * *` 按 `Asia/Shanghai` 下次为 2026-09-24 20:00 UTC；新 24 小时控制至 2026-09-25 08:16 UTC，预算 rev13 至 2026-09-25 02:52 UTC，均覆盖该 slot 及数小时后续。启用只授予未来自然调度，不等于业务成功。

1. 即时只读核 definition rev2 exact、12 latest Selection/Control/Binding ref、current member12、Host PID17302/三 held、九路 extension/unfenced、claim gate unpaused、18181 唯一监听且状态 IDLE/alive/independent/无本进程 Host、8080 单例、预算/窗口覆盖下次 slot 后至少 1800 秒、无 running/unknown attempt/Run、canary0、业务计数不变，启用 key0。
2. 上述全绿才写 0600 intent（expectedRef rev2、唯一 key、next slot、窗口和预算、resend=false），通过原 `SnapshotScheduleService.transition(intent=enable)` **调用一次**，立即保存正式结果。任何未知回执冻结，按 key/head 只读对账，不重发。
3. 独立只读确认 definition rev3 enabled、12 current member/12 schedule enabled、worker/Host/九路/业务计数仍稳；verification/commit。本波不手工 `run_definition`，不读取商城源行。
4. 下一波 W5c4r 单轮 50 秒间隔只读守候下次自然 slot、唯一 attempt 到正式终态；一旦出现失败/未知按原 fail-closed 退休/恢复路径，不重发。用户没有授权把 pending 当成功。
