# G 首链模型依赖后继方案

## 已证实的问题
真实健康探针单次成功（579ms，59 tokens），当前模型路由4/策略5/模型4 ready。六职责及八个已绑定技能仍是路由2/策略3的历史发布；只刷新readiness会被正确拒绝。未执行任何CapabilityBinding evaluate写入。

## 实施顺序与边界
1. 对照当前八个技能绑定和逻辑图，冻结精确前序与目标模型引用，仅org-org/dev-project。保持G事件暂停。
2. 新增 scripts/a0v_firstchain_model_successor.py：复用既有逻辑图构建器，核查除模型别名外内容完全一致，按expected revision通过LogicGraphStore.replace产生新修订，保留旧修订。每图先保存不可重复intent，再执行；未知结果先读取历史，禁止重发。
3. 按新图与当前模型重新生成真实隔离合约评估、发布后继Skill修订；评估证据必须绑定新图，不复用旧报告冒充新模型实测。此阶段仍不计业务成功。
4. 正式发布后继评估合同及内部许可引用，建立新能力/技能绑定；旧绑定仅在新项可用后暂停，保证唯一活跃选择及可恢复性。不得隐式选latest或变更负租户。
5. 由职责服务形成精确后继计划，经安装配置正式切换；处理有效窗口与17unknown的正式核对恢复，不SQL重置。
6. 恢复自然首链，后续有来源建议、exact评审、产物、续跑/Wiki、八工作台真实场景仍按总清单执行。

测试目录 services/aos-api/tests/extension_runtime/test_firstchain_model_successor.py：拒绝结构/工具/图ID漂移，限定模型替换，expected revision，已有intent不重发。先纯逻辑测试，再克隆预演，最后主库固定执行。回滚保留新旧不可变修订，通过正式当前配置/绑定选择恢复；不删除历史。

## 预演补充
新增 scripts/a0v_firstchain_model_successor_rehearsal.py：固定独立克隆 aos_model_successor_20260916_test；复用已经验证的快照备份/全表指纹函数，只调用备份与恢复，不调用迁移或主库写入。源必须a0v_059，克隆不存在，私有输出存在即拒绝重复。克隆只允许显式内部Owner操作，不启动Host/调度/Provider。
第一批纯逻辑测试7 passed（先确认7个缺模块失败再实现）；尚未主库更新任何图/技能/绑定。

克隆实测八个graph revision2全部成功且历史保留。Skill发布在首个D01评估套件固定ID冲突前停止，尚无新Skill。补改 scripts/a0v_firstchain_skill_publication.py：新逻辑评估按graph hash生成独立suite/report关联，验证评估target exact；既有成功report重放路径保持原suite。新增同目录测试覆盖跨graph区分及拒绝target漂移。不得覆盖旧评估套件。

## 第二轮克隆结果与下一波
逻辑证据ID修复后20测试通过。克隆首个D01逻辑新评估及发布已成功，但Skill发布遇到旧幂等键/新reasonHash冲突；未产生新Skill。发现七个 scripts/aip/bootstrap_*_skill_authority.py 的run_key固定为suite-run-r1，需新增 scripts/aip/skill_eval_revision_key.py：graph revision1保持旧key；后继修订key绑定revision/full hash，七入口仅接入该函数。scripts/a0v_firstchain_skill_publication.py 后继发布key同时绑定graph hash、route/policy及authority scope，旧revision1路径保持不变。测试覆盖旧key兼容、新修订隔离、同revision不同hash隔离。不得把旧成功report计为新评估。下一波完成此修复并在现有克隆按独立意图恢复正式发布流程。

第三轮克隆8个Skill r3发布成功，隔离合约59例通过，旧修订保留。后续许可/评估合同旧执行器固定r2；补改 scripts/a0v_firstchain_internal_license.py 与 scripts/a0v_firstchain_eval_contracts.py，抽取显式连接+目标校验回调的materialize入口，接受固定skill_revision 2或3，默认历史run仍2，不放宽原数据库allowlist。新克隆显式传3并匹配已成功发布Receipt。先合同/许可预演再新绑定。

许可与合同克隆实测：两组内部许可EvidenceBundle均complete/fresh；八个新Skill对应EvalContract全部frozen，业务Runs=0、ProviderCalls=0。34相关测试通过。下一步补 scripts/a0v_firstchain_capability_bindings.py 显式连接/目标校验/skill revision与后继binding前缀，旧run默认保持原2版；新增后继绑定执行器先全部preview再创建能力、评估、激活及SkillBinding替换，单步intent/CAS、未知不重发。活动旧SkillBinding只在新后继准备就绪后暂停，新项激活前保留可恢复旧项。职责计划重新读取而非手工改ready。
