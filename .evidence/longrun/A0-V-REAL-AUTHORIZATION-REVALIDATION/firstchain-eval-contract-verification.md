# 三项首链评测契约冻结

2026-09-12T01:54:07Z。D01/D02/D03 已发布 r2 的 exact 原技能、Suite、报告、Gate、最新发布事件及租户逐项验证后，沿 ProductionContract Owner 创建并冻结，均为 r2 frozen。契约 Schema 明确为 SkillPublicationContract.D01/D02/D03，不冒充经营画像或增长方案质量验收。

10 项测试涵盖当前有效、错误租户、未来/过期 Gate、目标/哈希漂移、事件或 Gate 不匹配、撤销和未发布拒绝。克隆正式执行后 524 表计数回放不变；补全租户/目标类型/事件 target 核验后再次回读正常。主库正式执行、重放，227 个 AIP 表计数不变，223 个租户 AIP 表 canary 排序内容摘要与克隆基线一致。exact 契约引用见 firstchain-eval-contract-main.json。

使用本轮已有 before-firstchain-contract 完整备份作为可恢复基线，主库仅三项契约 draft/frozen revision、head 和 Owner Receipt。ProviderCalls=0、业务 Runs=0、Binding/Agent 激活=0。AR2-7 闭包验证通过。

下一步从实际 source_license=internal 及用户开发授权，经治理 Task/Brief/Evidence/Bundle Owner 记录受限内部用途，随后 material.collect/strategy.plan 与 D01/D02/D03 Binding。无现成 EvidenceBundle，不可借其他租户许可或伪造商用许可。随后职责、四来源配置/启用与自然首链、八场景仍待完成。
