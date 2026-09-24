# W5c4h 第三继任者 disabled definition 配置方案（2026-09-24）

W5c4g `e42d3634` 的正式 options 为 ready、12/12 精确 binding、唯一 policyRef。新 definition ID 固定 `38c5d08c-ee40-4167-b129-8f95276e0c7a`，新 key `a0v-w5c4h-third-successor-definition-configure-20260924-v1`；历史安全 cron `0 4 * * *`，时区由 Owner 固定 `Asia/Shanghai`。该 cron 不等于“04:00 UTC”：必须以下一波对官方 schedule/worker 的时区语义独立核实触发点，不能只凭旧文档推算。

1. 只读确认 W5c4f binding/current member/schedule off，W5c4g 私有选项及唯一 policyRef 仍精确，第三继任者 Runtime/Host/三 held、预算/窗口当前有效、业务/canary/在途不漂移；新 definition ID/key 在正式表中均为0。
2. 0600 意图固定新 ID、cron、policyRef、12 exact memberRefs、预期 head 空和 key；经原 `PipelineSnapshotScheduleService.configure` **调用一次**，立即保存正式结果。未知结果即冻结、按 key/head 只读对账，不重复调用。
3. 独立只读核 definition rev1/state disabled、12 current members 精确指向新绑定、12 schedule 仍 off、业务计数不变；落 verification/commit。
4. 下一波先核明日/下次真实触发点、当前控制/预算是否覆盖、官方 enable 前置条件，再决定治理续期与自然 worker 监督。不得在本波 enable、手工 Run、读取商城源行。
