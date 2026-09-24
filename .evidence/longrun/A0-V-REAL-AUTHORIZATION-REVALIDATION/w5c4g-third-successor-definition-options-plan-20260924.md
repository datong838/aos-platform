# W5c4g 第三继任者定义选项只读核验方案（2026-09-24）

前提：W5c4f `ba532510` 已把 P01–P12 的最新 ScheduleBinding 全部迁到第三继任者，12 个 schedule 仍 disabled，旧 DR definition 已退休、current member0。下一步必须由正式 `PipelineSnapshotScheduleService.options` 返回可选 policyRef 和 12 个精确 bindingRef，不能凭旧定义或本地推断配置。

1. 只读重新审计 W5c4f、第三继任者 Runtime/Host/三 held、业务和 canary；核对第三继任者安装/代际精确值。
2. 调用正式 `options(actor, installation_id, generation)` 一次；要求 `status=ready`、canonical 12 pipeline/schedule/binding 与 W5c4f ref 一一一致、definitionId 均空、policyRef 候选非空且唯一或明确选择依据。私有 0600 证据保存完整响应；Git verification 只写非敏感摘要。
3. 核对当前治理窗口/预算到期时间、日常安全 cron 与下一可运行时刻；本波仅产出下一波配置/启用的风险判断，**不配置/启用 definition，不读商城源行，不手工 Run**。
4. 任一状态未知或选项不一致即冻结本波并验证落盘；不重发正式写操作。核验通过后 verification/commit，再进入 disabled definition 配置的独立波次。
