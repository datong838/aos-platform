# 首链绑定前置权威

2026-09-12，基线 d71b2275。D01/D02/D03 r2 已发布，尚无冻结 EvalContract/EvidenceBundle 或 Binding。先不改变可用性标记。

1. 新 scripts/a0v_firstchain_eval_contracts.py 从每个已发布 Skill 的 exact ReleaseGate/PublicationEvent 读取本库权威，验证租户、来源 evaluated parent、Gate hash/有效期、Report 完整性及最新发布事件仍 published。沿 AipProductionContractStore.create_eval_contract/freeze_eval_contract，suite 指向原报告套件，artifact schema 明确是技能发布契约；不是经营质量评测，不会把隔离 adapter 当成真实业务效果。键来自当前 Skill hash，重放回读已冻结 head。
2. 先唯一克隆，再主库；缺失/过期/错误目标/撤销拒绝测试。保留原 Store 的 exact 检查，不新增手填通过入口。实现目录 scripts/、services/aos-api/tests/extension_runtime/。
3. 许可依据来自本库 Skill source_license=internal 和本次开发授权，当前 EvidenceBundle=0。后续用生产 Brief/Evidence/Bundle Owner 保存真实内部用途、范围和禁止对外承诺，不能伪造供应商商用许可。所有真实经营数据仍须单独 SourceReadiness/分类/租户校验。
4. 先 material.collect/strategy.plan 的文本能力和三项 Skill Binding；建立时显式依赖上述 exact refs、当前模型 Route/Policy/Budget/Provider，以及健康证据。尚不宣称其他媒体能力可用。之后经营参谋职责、四来源配置启用和自然首链。

许可证据实现细化：scripts/a0v_firstchain_internal_license.py 使用单个明确 aip.governance Task，计划仅“核验并记录内部开发用途”，不创建经营 Case/Run 或调用 Provider。读 D01/D02/D03 r2 的 source_license=internal、发布租户和模型治理，规范 TAOR 记录事实 ID 与 exact refs；沿 TaskBrief freeze、EvidenceBundle build，required_fact_ids 非空，coverage 由服务计算。摘要明确仅内部开发用途、不是第三方商用/外发许可；原始证据来自本次 Owner 读取与会话授权。幂等键绑定实际技能 hash；回放不更改 cutoff，不新造 Evidence。先克隆演练与目标/来源拒绝自测，再主库。

集成核查：TaskStore.record_step_phase 正式 Evidence payload 有固定 stepRunId/stepKey/payload 外层，EvidenceBundle 的事实读取器只读顶层，无法消费该标准路径。services/aos-api/aos_api/aip_production_contract_store.py 的 _evidence_fact_ids 增加仅限该精确外层形状的一层读取（非空步骤标识、dict payload）；顶层原格式保持，未知/任意嵌套不解包。许可证据脚本核对完整外层内事实，沿原 Evidence exact hash 构建 Bundle，不改既有证据。新增旧格式、标准 TAOR、畸形/多余字段、缺失事实测试后恢复原治理任务，不重复造任务。

## 2026-09-12 首链能力绑定执行细化

新增 scripts/a0v_firstchain_capability_bindings.py。先只读派生本库 D01/D02/D03 published r2 的 requiredCapabilities，读取各自 frozen EvalContract、内部许可 Bundle、当前 Route/Policy/Provider/Budget exact refs，再由 PostgresBindingDependencyAuthority 与同一数据库 ModelRuntimeStore 计算 readiness；不使用默认外部数据库连接。每个技能及 capability 使用独立固定 Binding 标识，避免共享能力却丢失技能评测归属。许可需核验 exact 内部用途和本租户三技能 subject，EvalContract 需匹配技能的发布 Gate；旧证据文件只作线索，不能直接作为权威写入。缺证据/过期健康时先不创建可用标记。后续通过现有 create/evaluate/update Owner 路径、固定幂等键、版本 CAS；克隆先验证拒绝和重放，再主库。数字同事仅开放本次实际已绑定技能，其他 D04-D06 仍无运行权威。

只读预检暴露实际接线缺陷：AipModelRuntimeResolver._gate_passed 新建默认 AipEvalAuthorityStore，_health_is_fresh 直接 db_connect，绕开注入的 ModelRuntimeStore。修改 services/aos-api/aos_api/aip_model_runtime_resolver.py，从同一 Store 继承 connect_factory 和 eval_authority_store；默认构造仍使用原默认连接，测试替身缺省行为保留。新增服务级回归验证 exact target/租户传递、健康查询仅使用注入连接、过期和 provider hash 不符拒绝；不得用测试通过替代真实健康。

健康探针 v1 超时；独立 v2 于 02:36:52Z 成功，4225ms，有效至 02:51:52Z。克隆演练复用这条实际 Provider 观测：仅当两库当前 Provider exact ref 相同且生命周期 active 时，通过克隆库 record_health Owner 保存原始 observation_id/observed_at/expires_at/latency，不延长时间，不宣称新调用。主库不反向导入克隆证据。能力创建固定 ID，create→evaluate→active，实际健康来自本库可追溯观测；已 active 且 exact 依赖不变的重放只回读。部分完成仅从真实 Owner 当前状态接续，不重复 Provider 调用、不改变其他能力。
