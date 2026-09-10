# 原批次版本水位验证

2026-09-11，基线6d4ae1b7，任务A0V-BATCH-WATERMARK-20260911。

新增read_committed_batch_revision：原命令exact Receipt匹配后，按租户/平台/店铺/authority_tx_id与基础事件类型获取原批Outbox数量和max revision；数量不符、缺Receipt、ignored拒绝。新增prepare_derived_commands_for_batch核验scope/pipeline与规范原输入，使用原批水位。旧全局水位接口和现有executor路径保持原行为，后续装配新接口。

验证：新增4测试先失败；实现后Store/prepare/input/recovery四文件47通过；新增真实SQLite Store组合后Store/prepare两文件37通过，合计48独立用例通过。组合证明基础写入→prepare→无关后续写入→再次prepare命令不变→派生首次提交/幂等重放。Store测试还证明原水位稳定、exact冲突、缺回执/Outbox拒绝和ignored拒绝。diff-check通过。7既有警告与pytest退出JDBC日志错误未改。

限制：SQLite与部分Mock，未作新接口PG/真实源验证。水位是原批提交边界，不是逐项关联聚合来源版本证明；已保存派生命令仍须复用，不能重新prepare已提交派生。尚未装配实际恢复claim、输入辅助来源验证、投影/Dataset接续；API未重载，完整真实首链及八工作台未完成。不push，230 L0挂起。
