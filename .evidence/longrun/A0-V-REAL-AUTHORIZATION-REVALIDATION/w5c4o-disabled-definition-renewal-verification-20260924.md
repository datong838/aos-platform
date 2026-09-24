# W5c4o disabled definition rev2 续期验证（2026-09-24）

方案 `1be6f4aa`；执行 `scripts/a0v_w5c4o_disabled_definition_renewal.py`。0600 exact intent/result 位于仓库外 `../.aos-recovery-20260920/state/q-advisor-baseline/20260924-w5c4o-disabled-definition-renewal/`。

- 08:27 UTC `W5C4O_CONFIGURE_PREFLIGHT_GREEN`：正式 `SnapshotScheduleService.options` 返回唯一 policyRef 与 12 最新 Binding，全部 definitionId 指向旧 disabled 定义；head rev1/hash 精确、新 key0、Host PID17302/三 held、attempt0/canary0、业务 claims40/runs53，窗口有效。
- intent 先落盘，正式 `configure` 调用一次，返回原定义 `38c5d08c-ee40-4167-b129-8f95276e0c7a` rev2、`state=disabled`、hash `sha256:a3a105d2018df1ec448a25e2b61797937c65354634b78db3b56fa373792d149e`，随即保存 result。
- 08:28 UTC 独立审计 `W5C4O_DISABLED_DEFINITION_REV2_GREEN`：previousHash=rev1、policy/cron 未改、12 current members 均 rev2 且引用新 Binding，12 schedule off、Host/业务不变。`py_compile` 通过。

本波没有 enable、手工 Run 或商城源行读取。下一波单独核预算/窗口覆盖 20:00 UTC slot、独立 snapshot worker 单例、Host/资源/路由、零在途及 canary，再决定正式 enable 与 50 秒只读监督；配置成功本身不是执行通过。
