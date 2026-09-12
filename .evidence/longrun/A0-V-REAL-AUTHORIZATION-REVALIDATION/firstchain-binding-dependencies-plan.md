# 首链绑定前置权威

2026-09-12，基线 d71b2275。D01/D02/D03 r2 已发布，尚无冻结 EvalContract/EvidenceBundle 或 Binding。先不改变可用性标记。

1. 新 scripts/a0v_firstchain_eval_contracts.py 从每个已发布 Skill 的 exact ReleaseGate/PublicationEvent 读取本库权威，验证租户、来源 evaluated parent、Gate hash/有效期、Report 完整性及最新发布事件仍 published。沿 AipProductionContractStore.create_eval_contract/freeze_eval_contract，suite 指向原报告套件，artifact schema 明确是技能发布契约；不是经营质量评测，不会把隔离 adapter 当成真实业务效果。键来自当前 Skill hash，重放回读已冻结 head。
2. 先唯一克隆，再主库；缺失/过期/错误目标/撤销拒绝测试。保留原 Store 的 exact 检查，不新增手填通过入口。实现目录 scripts/、services/aos-api/tests/extension_runtime/。
3. 许可依据来自本库 Skill source_license=internal 和本次开发授权，当前 EvidenceBundle=0。后续用生产 Brief/Evidence/Bundle Owner 保存真实内部用途、范围和禁止对外承诺，不能伪造供应商商用许可。所有真实经营数据仍须单独 SourceReadiness/分类/租户校验。
4. 先 material.collect/strategy.plan 的文本能力和三项 Skill Binding；建立时显式依赖上述 exact refs、当前模型 Route/Policy/Budget/Provider，以及健康证据。尚不宣称其他媒体能力可用。之后经营参谋职责、四来源配置启用和自然首链。
