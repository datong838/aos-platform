# 首链绑定前置权威

2026-09-12，基线 d71b2275。D01/D02/D03 r2 已发布，尚无冻结 EvalContract/EvidenceBundle 或 Binding。先不改变可用性标记。

1. 新 scripts/a0v_firstchain_eval_contracts.py 从每个已发布 Skill 的 exact ReleaseGate/PublicationEvent 读取本库权威，验证租户、来源 evaluated parent、Gate hash/有效期、Report 完整性及最新发布事件仍 published。沿 AipProductionContractStore.create_eval_contract/freeze_eval_contract，suite 指向原报告套件，artifact schema 明确是技能发布契约；不是经营质量评测，不会把隔离 adapter 当成真实业务效果。键来自当前 Skill hash，重放回读已冻结 head。
2. 先唯一克隆，再主库；缺失/过期/错误目标/撤销拒绝测试。保留原 Store 的 exact 检查，不新增手填通过入口。实现目录 scripts/、services/aos-api/tests/extension_runtime/。
3. 许可依据来自本库 Skill source_license=internal 和本次开发授权，当前 EvidenceBundle=0。后续用生产 Brief/Evidence/Bundle Owner 保存真实内部用途、范围和禁止对外承诺，不能伪造供应商商用许可。所有真实经营数据仍须单独 SourceReadiness/分类/租户校验。
4. 先 material.collect/strategy.plan 的文本能力和三项 Skill Binding；建立时显式依赖上述 exact refs、当前模型 Route/Policy/Budget/Provider，以及健康证据。尚不宣称其他媒体能力可用。之后经营参谋职责、四来源配置启用和自然首链。

许可证据实现细化：scripts/a0v_firstchain_internal_license.py 使用单个明确 aip.governance Task，计划仅“核验并记录内部开发用途”，不创建经营 Case/Run 或调用 Provider。读 D01/D02/D03 r2 的 source_license=internal、发布租户和模型治理，规范 TAOR 记录事实 ID 与 exact refs；沿 TaskBrief freeze、EvidenceBundle build，required_fact_ids 非空，coverage 由服务计算。摘要明确仅内部开发用途、不是第三方商用/外发许可；原始证据来自本次 Owner 读取与会话授权。幂等键绑定实际技能 hash；回放不更改 cutoff，不新造 Evidence。先克隆演练与目标/来源拒绝自测，再主库。

集成核查：TaskStore.record_step_phase 正式 Evidence payload 有固定 stepRunId/stepKey/payload 外层，EvidenceBundle 的事实读取器只读顶层，无法消费该标准路径。services/aos-api/aos_api/aip_production_contract_store.py 的 _evidence_fact_ids 增加仅限该精确外层形状的一层读取（非空步骤标识、dict payload）；顶层原格式保持，未知/任意嵌套不解包。许可证据脚本核对完整外层内事实，沿原 Evidence exact hash 构建 Bundle，不改既有证据。新增旧格式、标准 TAOR、畸形/多余字段、缺失事实测试后恢复原治理任务，不重复造任务。
